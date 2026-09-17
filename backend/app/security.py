import os
import base64
import hashlib
import hmac
import json
import time
from threading import Lock
from fastapi import Header, HTTPException, Request
from app.database import SessionLocal
from app.models.security_event import SecurityEvent

_login_failures = {}
_login_lock = Lock()
_MAX_LOGIN_FAILURES = 5
_LOCKOUT_SECONDS = 300
_alert_deliveries = {}

def login_allowed(identity: str):
    now = time.time()
    with _login_lock:
        entry = _login_failures.get(identity)
        if entry and entry[0] >= _MAX_LOGIN_FAILURES and now - entry[1] < _LOCKOUT_SECONDS:
            return False
        if entry and now - entry[1] >= _LOCKOUT_SECONDS:
            _login_failures.pop(identity, None)
        return True

def record_login_failure(identity: str):
    with _login_lock:
        count = _login_failures.get(identity, (0, 0))[0] + 1
        _login_failures[identity] = (count, time.time())

def clear_login_failures(identity: str):
    with _login_lock:
        _login_failures.pop(identity, None)

def alert_delivery_allowed(signature: str, cooldown: int = 600):
    now = time.time()
    previous = _alert_deliveries.get(signature)
    if previous and now - previous < cooldown:
        return False, max(0, int(cooldown - (now - previous)))
    return True, 0

def mark_alert_delivered(signature: str):
    _alert_deliveries[signature] = time.time()

def record_security_event(event: str, request: Request | None = None, detail: str = ""):
    db = SessionLocal()
    try:
        db.add(SecurityEvent(event=event, ip_address=request.client.host if request and request.client else None,
                             path=str(request.url.path) if request else None, detail=detail))
        db.commit()
    finally:
        db.close()

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

def require_admin(request: Request, x_admin_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    configured = os.getenv("MATH_AGENT_ADMIN_KEY", "").strip()
    bearer = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if configured and x_admin_key != configured and not _valid_token(bearer, configured):
        record_security_event("admin_denied", request, "invalid credentials")
        raise HTTPException(status_code=403, detail="需要有效的管理员密钥。")
    return True
