from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
import models

router = APIRouter()

@router.get("/profile")
def profile(u=Depends(get_current_user)):
    return {
        "id": u.id, "login": u.login, "telegram_id": u.telegram_id,
        "username": u.username, "balance": u.balance,
        "total_wins": u.total_wins, "total_losses": u.total_losses,
        "status": u.status, "created_at": u.created_at
    }

@router.get("/profile-by-telegram/{telegram_id}")
def profile_by_tg(telegram_id: str, db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not u: raise HTTPException(404, "Topilmadi")
    return {"login": u.login, "balance": u.balance, "total_wins": u.total_wins,
            "total_losses": u.total_losses, "created_at": str(u.created_at)}

@router.get("/history-by-telegram/{telegram_id}")
def history_by_tg(telegram_id: str, db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not u: raise HTTPException(404, "Topilmadi")
    sessions = db.query(models.GameSession).filter(
        models.GameSession.user_id == u.id
    ).order_by(models.GameSession.created_at.desc()).limit(10).all()
    return [{"game_type": s.game_type, "bet": s.bet_amount, "win": s.win_amount,
             "multiplier": s.multiplier, "result": s.result} for s in sessions]
