import os
from fastapi import Header, HTTPException

def require_admin(x_admin_key: str | None = Header(default=None)):
    configured = os.getenv("MATH_AGENT_ADMIN_KEY", "").strip()
    if configured and x_admin_key != configured:
        raise HTTPException(status_code=403, detail="需要有效的管理员密钥。")
    return True
