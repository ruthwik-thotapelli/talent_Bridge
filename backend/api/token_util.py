import jwt
from datetime import datetime, timedelta, timezone
from django.conf import settings

def sign_token(payload: dict) -> str:
    # 7 days expiry
    exp = datetime.now(timezone.utc) + timedelta(days=7)
    data = {**payload, "exp": exp}
    return jwt.encode(data, settings.JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
