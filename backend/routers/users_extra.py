# Add these endpoints to users.py router

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models

# Additional endpoints needed by bot (no auth required - internal use)

def get_user_by_telegram(telegram_id: str, db: Session):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    return user

# Add to users router:
# GET /users/profile-by-telegram/{telegram_id}
# GET /users/history-by-telegram/{telegram_id}

# Add to admin router:
# POST /admin/deposit-approve-telegram  
# POST /admin/withdraw-request-telegram

"""
@router.get("/profile-by-telegram/{telegram_id}")
def profile_by_telegram(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {
        "login": user.login,
        "balance": user.balance,
        "total_wins": user.total_wins,
        "total_losses": user.total_losses,
        "created_at": str(user.created_at)
    }

@router.get("/history-by-telegram/{telegram_id}")  
def history_by_telegram(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")
    sessions = db.query(models.GameSession).filter(
        models.GameSession.user_id == user.id
    ).order_by(models.GameSession.created_at.desc()).limit(10).all()
    return [{
        "game_type": s.game_type,
        "bet": s.bet_amount,
        "win": s.win_amount,
        "multiplier": s.multiplier,
        "result": s.result
    } for s in sessions]
"""
