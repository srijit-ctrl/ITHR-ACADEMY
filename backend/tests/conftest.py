"""Shared pytest fixtures + test-only credentials.

Test passwords are read from environment variables so they are never hardcoded
in source. Defaults are used when the env-var is unset — these are strictly test
fixtures (never a real account) and are documented as such.
"""
import os
import secrets

# Read from env-var; fall back to a fresh random per-run password. This keeps
# the test suite hermetic while satisfying static security scanners that flag
# hardcoded credentials in test files.
TEST_USER_PASSWORD: str = os.environ.get(
    "EAIA_TEST_USER_PASSWORD",
    f"E2E-{secrets.token_urlsafe(16)}!Test1",
)
