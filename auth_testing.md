# Auth Testing Playbook — Enterprise Agentic AI Academy

## Auth Model
- Backend issues its own JWT for BOTH email/password and Google OAuth flows.
- Token is stored in localStorage as `eaia_token` (NOT cookies).
- All protected endpoints require `Authorization: Bearer <token>` header.

## Email/Password Flow (native)
### Register
```bash
curl -X POST "$BACKEND_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"qa@test.com","password":"pass123!","full_name":"QA User"}'
# → { token, user }
```

### Login
```bash
curl -X POST "$BACKEND_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"qa@test.com","password":"pass123!"}'
```

### Me
```bash
curl -X GET "$BACKEND_URL/api/auth/me" \
  -H "Authorization: Bearer $TOKEN"
```

## Google OAuth Flow (Emergent-managed)
1. Frontend clicks "Continue with Google" → redirects to `https://auth.emergentagent.com/?redirect=<origin>/dashboard`.
2. Emergent completes Google OAuth, returns to `<origin>/dashboard#session_id=<id>`.
3. `AppShell` detects `session_id` in URL hash synchronously (before routing), renders `AuthCallback`.
4. `AuthCallback` calls `POST /api/auth/google/callback` with `{session_id}`.
5. Backend calls `GET https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data` with `X-Session-ID` header, receives `{id, email, name, picture, session_token}`.
6. Backend upserts user by email, returns our JWT token.
7. Frontend stores JWT and navigates to `/dashboard`.

### Simulating Google flow in tests
Since we cannot programmatically complete Google OAuth in an automated test, simulate by:
1. Register a normal user via `/api/auth/register` (that user represents what a Google user would look like).
2. Test that the resulting JWT works on protected endpoints.

## Protected Endpoint Checklist
- `/api/auth/me` — returns current user
- `/api/dashboard/stats` — user's XP, enrollments, certs, streak
- `/api/enrollments` — user's enrollments
- `/api/courses/{slug}/enroll` — enroll
- `/api/lessons/complete` — mark lesson complete
- `/api/courses/{slug}/quiz/submit` — submit quiz
- `/api/certificates` — user's certificates
- `/api/ai/tutor` — SSE streaming AI tutor chat
- `/api/ai/sessions` — list chat sessions

## Public Endpoints (no auth)
- `/api/health`
- `/api/courses` and `/api/courses/{slug}`
- `/api/catalog/*`
- `/api/certificates/verify/{cert_id}`
