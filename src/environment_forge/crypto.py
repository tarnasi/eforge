"""
Fernet-based encryption engine.

Uses AES-128-CBC + HMAC-SHA256 via the ``cryptography`` library.
The master key is derived from a secret using SHA-256.
"""

import base64
import hashlib
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def generate_secret_key() -> str:
    """Generate a cryptographically secure secret key."""
    return secrets.token_urlsafe(50)


def derive_fernet_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet key from an arbitrary secret string."""
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt(plaintext: str, secret: str) -> str:
    """Encrypt a plaintext string, returning the Fernet token as UTF-8."""
    f = Fernet(derive_fernet_key(secret))
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str, secret: str) -> str:
    """Decrypt a Fernet token back to plaintext. Raises on failure."""
    f = Fernet(derive_fernet_key(secret))
    return f.decrypt(ciphertext.encode()).decode()


def get_or_create_secret(keyfile: Path) -> str:
    """
    Resolve the master secret in priority order:

    1. Read from *keyfile* on disk
    2. ``EFORGE_SECRET`` environment variable
    3. Auto-generate and save to *keyfile*
    """
    import os

    # 1. File on disk
    if keyfile.is_file():
        key = keyfile.read_text(encoding="utf-8").strip()
        if key:
            return key

    # 2. Environment variable
    key = os.environ.get("EFORGE_SECRET", "").strip()
    if key:
        return key

    # 3. Auto-generate
    key = generate_secret_key()
    keyfile.parent.mkdir(parents=True, exist_ok=True)
    keyfile.write_text(key, encoding="utf-8")
    # Restrict permissions (owner-only)
    keyfile.chmod(0o600)
    return key
