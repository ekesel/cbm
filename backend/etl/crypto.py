import base64, os
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

def _get_fernet() -> Fernet:
    key = getattr(settings, "CREDENTIALS_FERNET_KEY", None)
    if not key:
        # For dev only: derive from SECRET_KEY (do NOT do this in prod)
        raw = (settings.SECRET_KEY + "sldp-fernet").encode()[:32]
        key = base64.urlsafe_b64encode(raw.ljust(32, b"0"))
    elif len(key) != 44:  # Fernet expects 32 bytes base64 urlsafe => 44 chars
        key = base64.urlsafe_b64encode(key.encode()[:32].ljust(32, b"0"))
    return Fernet(key)

def encrypt_value(plain: str) -> bytes:
    if plain is None:
        return b""
    return _get_fernet().encrypt(plain.encode())

def decrypt_value(cipher: bytes) -> str:
    if not cipher:
        return ""
    try:
        return _get_fernet().decrypt(cipher).decode()
    except InvalidToken:
        return ""
