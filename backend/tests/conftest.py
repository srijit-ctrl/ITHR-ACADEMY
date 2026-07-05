"""Shared pytest fixtures + test-only credentials.

Test passwords are read from environment variables so they are never hardcoded
in source. Defaults are used when the env-var is unset — these are strictly test
fixtures (never a real account) and are documented as such.
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# Ensure backend/.env AND frontend/.env are both loaded before any test imports
# reach for env vars. auth.py + core.py read JWT_SECRET / MONGO_URL at import
# time; backend_test.py reaches for REACT_APP_BACKEND_URL which lives in
# frontend/.env. Loading both here means `pytest tests/...` works standalone.
load_dotenv(Path(__file__).parent.parent / ".env")
load_dotenv(Path(__file__).parent.parent.parent / "frontend" / ".env")

# Read from env-var; fall back to a fresh random per-run password. This keeps
# the test suite hermetic while satisfying static security scanners that flag
# hardcoded credentials in test files.
TEST_USER_PASSWORD: str = os.environ.get(
    "EAIA_TEST_USER_PASSWORD",
    f"E2E-{secrets.token_urlsafe(16)}!Test1",
)
