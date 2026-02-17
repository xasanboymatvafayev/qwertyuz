from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
import models

router = APIRouter()

@router.get("/profile")
def get_profile(current_user: models.User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "login": current_user.login,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "balance": current_user.balance,
        "total_wins": current_user.total_wins,
        "total_losses": current_user.total_losses,
        "net_result": current_user.total_wins - current_user.total_losses,
        "status": current_user.status,
        "created_at": current_user.created_at
    }

@router.get("/check-subscription/{channel_id}")
def check_subscription(channel_id: str, db: Session = Depends(get_db),
                        current_user: models.User = Depends(get_current_user)):
    sub = db.query(models.ChannelSubscription).filter(
        models.ChannelSubscription.user_id == current_user.id,
        models.ChannelSubscription.channel_id == channel_id
    ).first()
    return {"subscribed": sub is not None}
