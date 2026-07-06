"""Stripe checkout routes."""
from datetime import datetime, timezone, timedelta

from emergentintegrations.payments.stripe.checkout import CheckoutSessionRequest
from fastapi import APIRouter, Depends, HTTPException, Request

from auth import get_current_user_id
from core import db, get_stripe, logger, now_iso

router = APIRouter(prefix="/api", tags=["checkout"])

PAYMENT_PACKAGES = {
    "practitioner_monthly": {"amount": 29.00, "currency": "usd", "label": "Practitioner — Monthly", "duration_days": 30, "tier": "practitioner"},
    "practitioner_annual": {"amount": 290.00, "currency": "usd", "label": "Practitioner — Annual", "duration_days": 365, "tier": "practitioner"},
    "professional_track": {"amount": 499.00, "currency": "usd", "label": "Professional Track (12 mo)", "duration_days": 365, "tier": "professional"},
    "team_monthly_per_seat": {"amount": 18.00, "currency": "usd", "label": "Team — Per seat / month", "duration_days": 30, "tier": "team"},
}


@router.get("/checkout/packages")
async def list_packages():
    return {"packages": {k: {"label": v["label"], "amount": v["amount"], "currency": v["currency"], "tier": v["tier"]} for k, v in PAYMENT_PACKAGES.items()}}


@router.post("/checkout/session")
async def create_checkout(payload: dict, request: Request, user_id: str = Depends(get_current_user_id)):
    package_id = payload.get("package_id")
    origin_url = payload.get("origin_url", "").rstrip("/")
    quantity = int(payload.get("quantity") or 1)

    if package_id not in PAYMENT_PACKAGES:
        raise HTTPException(status_code=400, detail="Invalid package_id")
    if not origin_url:
        raise HTTPException(status_code=400, detail="origin_url required")

    pkg = PAYMENT_PACKAGES[package_id]
    if package_id == "team_monthly_per_seat":
        quantity = max(10, min(100, quantity))
    else:
        quantity = 1

    amount = float(pkg["amount"]) * quantity
    success_url = f"{origin_url}/pricing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/pricing"
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    metadata = {"user_id": user_id, "email": user["email"], "package_id": package_id, "quantity": str(quantity), "tier": pkg["tier"]}

    stripe = get_stripe(request)
    session_req = CheckoutSessionRequest(amount=amount, currency=pkg["currency"], success_url=success_url, cancel_url=cancel_url, metadata=metadata)
    try:
        session = await stripe.create_checkout_session(session_req)
    except Exception as e:
        logger.exception("Stripe session creation failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    txn = {
        "session_id": session.session_id, "user_id": user_id, "email": user["email"],
        "package_id": package_id, "tier": pkg["tier"], "quantity": quantity,
        "amount": amount, "currency": pkg["currency"],
        "payment_status": "initiated", "status": "pending", "metadata": metadata,
        "created_at": now_iso(),
    }
    await db.payment_transactions.insert_one(txn)
    return {"url": session.url, "session_id": session.session_id}


@router.get("/checkout/status/{session_id}")
async def checkout_status(session_id: str, request: Request, user_id: str = Depends(get_current_user_id)):
    txn = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if txn["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your transaction")

    if txn.get("payment_status") == "paid" and txn.get("status") == "complete":
        return {"payment_status": "paid", "status": "complete", "package_id": txn["package_id"], "tier": txn["tier"], "amount": txn["amount"], "currency": txn["currency"]}

    stripe = get_stripe(request)
    try:
        status_resp = await stripe.get_checkout_status(session_id)
    except Exception as e:
        logger.exception("Stripe status fetch failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    updates = {"payment_status": status_resp.payment_status, "status": status_resp.status, "updated_at": now_iso()}
    if status_resp.payment_status == "paid" and txn.get("payment_status") != "paid":
        pkg = PAYMENT_PACKAGES.get(txn["package_id"])
        if pkg:
            expires_at = datetime.now(timezone.utc) + timedelta(days=pkg["duration_days"])
            await db.users.update_one({"id": txn["user_id"]}, {"$set": {"subscription_tier": pkg["tier"], "subscription_expires_at": expires_at.isoformat(), "subscription_package": txn["package_id"]}})
            updates["fulfilled_at"] = now_iso()
            # Payment-confirmation email (fire-and-forget)
            try:
                import asyncio as _asyncio
                from email_service import send_payment_confirmation_email
                user_doc = await db.users.find_one({"id": txn["user_id"]}, {"_id": 0, "email": 1, "full_name": 1})
                if user_doc:
                    _asyncio.create_task(send_payment_confirmation_email(
                        email=user_doc["email"], full_name=user_doc.get("full_name") or "",
                        item_description=f"{pkg.get('name', txn['package_id'])} — {pkg.get('duration_days', 0)}-day access",
                        amount=float(txn["amount"]), currency=txn.get("currency", "usd"),
                        invoice_id=session_id,
                    ))
            except Exception:
                logger.exception("Payment-confirm email dispatch failed (non-fatal)")
    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": updates})

    return {"payment_status": status_resp.payment_status, "status": status_resp.status, "package_id": txn["package_id"], "tier": txn["tier"], "amount": txn["amount"], "currency": txn["currency"], "amount_total_cents": status_resp.amount_total}


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    stripe = get_stripe(request)
    try:
        webhook_resp = await stripe.handle_webhook(body, signature)
    except Exception as e:
        logger.exception("Stripe webhook parse failed")
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    if not webhook_resp.session_id:
        return {"received": True}

    txn = await db.payment_transactions.find_one({"session_id": webhook_resp.session_id}, {"_id": 0})
    if not txn:
        return {"received": True, "known": False}

    updates = {"payment_status": webhook_resp.payment_status, "webhook_event_id": webhook_resp.event_id, "webhook_event_type": webhook_resp.event_type, "updated_at": now_iso()}
    if webhook_resp.payment_status == "paid" and txn.get("payment_status") != "paid":
        pkg = PAYMENT_PACKAGES.get(txn["package_id"])
        if pkg:
            expires_at = datetime.now(timezone.utc) + timedelta(days=pkg["duration_days"])
            await db.users.update_one({"id": txn["user_id"]}, {"$set": {"subscription_tier": pkg["tier"], "subscription_expires_at": expires_at.isoformat(), "subscription_package": txn["package_id"]}})
            updates["fulfilled_at"] = now_iso()
    await db.payment_transactions.update_one({"session_id": webhook_resp.session_id}, {"$set": updates})
    return {"received": True, "session_id": webhook_resp.session_id}
