from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import audit, get_current_user, require_role
from app.models import User, utcnow
from app.schemas import LoginIn, PasswordChangeIn, UserCreate, UserUpdate
from app.security import create_access_token, hash_password, validate_password_strength, verify_password
from app.serializers import user_out

router = APIRouter(tags=["auth"])

# Basit, süreç içi kaba kuvvet koruması (çoklu süreçte Redis tabanlı limit önerilir)
_failed: dict = {}


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = (body.email.lower(), request.client.host if request.client else "")
    attempts = [t for t in _failed.get(key, []) if (utcnow() - t).total_seconds() < 900]
    if len(attempts) >= 8:
        raise HTTPException(429, "Çok fazla hatalı deneme. 15 dakika sonra tekrar deneyin.")
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        attempts.append(utcnow())
        _failed[key] = attempts
        raise HTTPException(401, "E-posta veya parola hatalı")
    _failed.pop(key, None)
    user.last_login_at = utcnow()
    audit(db, user, "login", "user", user.id, request=request)
    db.commit()
    return {"access_token": create_access_token(user.id, user.role), "token_type": "bearer", "user": user_out(user)}


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.post("/auth/change-password")
def change_password(body: PasswordChangeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Mevcut parola hatalı")
    err = validate_password_strength(body.new_password)
    if err:
        raise HTTPException(400, err)
    user.password_hash = hash_password(body.new_password)
    audit(db, user, "password_change", "user", user.id)
    db.commit()
    return {"ok": True}


@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_role("sales"))) -> List[dict]:
    return [user_out(u) for u in db.scalars(select(User).order_by(User.full_name)).all()]


@router.post("/users")
def create_user(body: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(400, "Bu e-posta ile kullanıcı var")
    err = validate_password_strength(body.password)
    if err:
        raise HTTPException(400, err)
    u = User(email=body.email, full_name=body.full_name, role=body.role, password_hash=hash_password(body.password))
    db.add(u)
    db.flush()
    audit(db, admin, "user_create", "user", u.id, {"role": u.role})
    db.commit()
    return user_out(u)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Kullanıcı bulunamadı")
    if body.full_name is not None:
        u.full_name = body.full_name
    if body.role is not None:
        if u.id == admin.id and body.role != "admin":
            raise HTTPException(400, "Kendi yönetici yetkinizi kaldıramazsınız")
        u.role = body.role
    if body.is_active is not None:
        if u.id == admin.id and not body.is_active:
            raise HTTPException(400, "Kendinizi pasifleştiremezsiniz")
        u.is_active = body.is_active
    if body.password:
        err = validate_password_strength(body.password)
        if err:
            raise HTTPException(400, err)
        u.password_hash = hash_password(body.password)
    audit(db, admin, "user_update", "user", u.id, body.model_dump(exclude={"password"}, exclude_none=True))
    db.commit()
    return user_out(u)
