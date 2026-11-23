from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, User
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)

ROLE_RANK = {"viewer": 0, "sales": 1, "manager": 2, "admin": 3}


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Giriş yapmanız gerekiyor")
    payload = decode_token(creds.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Oturum süresi doldu veya geçersiz")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Kullanıcı bulunamadı veya pasif")
    return user


def require_role(min_role: str) -> Callable[..., User]:
    def checker(user: User = Depends(get_current_user)) -> User:
        if ROLE_RANK.get(user.role, -1) < ROLE_RANK[min_role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu işlem için yetkiniz yok")
        return user
    return checker


def audit(db: Session, user: Optional[User], action: str, entity_type: Optional[str] = None,
          entity_id=None, details: Optional[dict] = None, request: Optional[Request] = None) -> None:
    db.add(AuditLog(user_id=user.id if user else None, action=action, entity_type=entity_type,
                    entity_id=str(entity_id) if entity_id is not None else None, details=details or {},
                    ip=request.client.host if request and request.client else None))
