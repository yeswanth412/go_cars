"""Security and cryptographic utilities for GoCars.

Provides:
- Password hashing and verification using Argon2 via pwdlib
- JWT access token generation and decoding using python-jose
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from jose import jwt, JWTError
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from app.core.config import settings

# Initialize password hasher with Argon2
password_hasher = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """Hash a plaintext password using the Argon2 algorithm."""
    return password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2 hash.

    Returns True if the password matches, False otherwise.
    """
    try:
        return password_hasher.verify(password, hashed_password)
    except Exception:
        return False


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a signed JWT access token.

    Contains standard claims:
    - sub: subject (user UUID)
    - exp: expiration timestamp (UTC)
    - iat: issued-at timestamp (UTC)
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }

    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(
        to_encode,
        settings.effective_jwt_secret_key,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a signed JWT access token.

    Raises:
        JWTError: If signature is invalid, token is expired, or malformed.
    """
    return jwt.decode(
        token,
        settings.effective_jwt_secret_key,
        algorithms=[settings.JWT_ALGORITHM],
    )
