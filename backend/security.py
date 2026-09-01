import base64, hashlib, hmac, os, secrets, time
from fastapi import Header, HTTPException

SECRET = os.getenv("DRS_SECRET", "demo-only-change-before-deployment")
def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 240000).hex()
    return f"{salt}${digest}"
def verify_password(password: str, stored: str) -> bool:
    salt, digest = stored.split("$", 1); return hmac.compare_digest(hash_password(password, salt), stored)
def make_token(username: str) -> str:
    payload = f"{username}|{int(time.time()) + 28800}"; sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest(); return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode()
def current_user(authorization: str | None = Header(default=None)) -> str:
    try:
        raw = base64.urlsafe_b64decode(authorization.removeprefix("Bearer ").encode()).decode(); username, expiry, sig = raw.rsplit("|", 2); valid = hmac.compare_digest(sig, hmac.new(SECRET.encode(), f"{username}|{expiry}".encode(), hashlib.sha256).hexdigest())
        if not valid or int(expiry) < time.time(): raise ValueError
        return username
    except Exception: raise HTTPException(401, "Session invalide ou expirée")
