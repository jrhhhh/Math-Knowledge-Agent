import os
import base64
import hashlib
import hmac
import json
import time
from fastapi import Header, HTTPException

def issue_admin_token(key: str):
    payload = {"sub": "admin", "exp": int(time.time()) + 3600}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"

def _valid_token(token: str, key: str):
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return hmac.compare_digest(signature, expected) and payload.get("exp", 0) > time.time()
    except (ValueError, json.JSONDecodeError, TypeError):
        return False

def require_admin(x_admin_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    configured = os.getenv("MATH_AGENT_ADMIN_KEY", "").strip()
    bearer = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if configured and x_admin_key != configured and not _valid_token(bearer, configured):
        raise HTTPException(status_code=403, detail="需要有效的管理员密钥。")
    return True
