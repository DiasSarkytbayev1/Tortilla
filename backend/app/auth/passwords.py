"""Bcrypt password hashing + verification."""

from __future__ import annotations

import bcrypt


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """
    Returns False on any mismatch.

    bcrypt.checkpw raises ValueError on a malformed hash; treat that as a
    failed verification rather than a 500. Any other exception is a real bug
    and should propagate.
    """
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False
