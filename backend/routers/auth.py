from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
import models
from auth_utils import (generate_login, generate_password, hash_password,
                        verify_password, create_access_token, decode_token)

router = APIRouter()
security = HTTPBearer()

class LoginRequest(BaseModel):
    login: str
    password: str

class TelegramAuthRequest(BaseModel):
    telegram_id: str
    username: str = None

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(models.User).filter(models.User.id == payload.get("user_id")).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.status == models.UserStatus.blocked:
        raise HTTPException(status_code=403, detail="Account blocked")
    return user

@router.post("/telegram-register")
def telegram_register(req: TelegramAuthRequest, db: Session = Depends(get_db)):
    """Called by bot when user presses /start"""
    existing = db.query(models.User).filter(models.User.telegram_id == req.telegram_id).first()
    if existing:
        return {
            "already_exists": True,
            "login": existing.login,
            "message": "Siz allaqachon ro'yxatdan o'tgansiz"
        }
    
    login = generate_login(req.telegram_id)
    # Ensure unique login
    while db.query(models.User).filter(models.User.login == login).first():
        login = generate_login(req.telegram_id)
    
    password = generate_password()
    
    user = models.User(
        telegram_id=req.telegram_id,
        username=req.username,
        login=login,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return {
        "already_exists": False,
        "login": login,
        "password": password,
        "user_id": user.id,
        "message": "Ro'yxatdan o'tdingiz!"
    }

@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.login == req.login).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Login yoki parol noto'g'ri")
    
    if user.status == models.UserStatus.blocked:
        raise HTTPException(status_code=403, detail="Akkauntingiz bloklangan")
    
    token = create_access_token({"user_id": user.id, "telegram_id": user.telegram_id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "login": user.login,
            "balance": user.balance,
            "telegram_id": user.telegram_id
        }
    }

@router.get("/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "login": current_user.login,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "balance": current_user.balance,
        "total_wins": current_user.total_wins,
        "total_losses": current_user.total_losses,
        "status": current_user.status,
        "created_at": current_user.created_at,
        "is_admin": current_user.is_admin
    }
