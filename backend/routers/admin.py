from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from routers.auth import get_current_user
import models
from datetime import datetime, timedelta

router = APIRouter()

def require_admin(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin huquqi yo'q")
    return current_user

# =================== TRANSACTIONS ===================

class ApproveTransactionRequest(BaseModel):
    note: Optional[str] = None

@router.get("/transactions/pending")
def get_pending_transactions(db: Session = Depends(get_db), admin=Depends(require_admin)):
    txns = db.query(models.Transaction, models.User).join(
        models.User, models.Transaction.user_id == models.User.id
    ).filter(
        models.Transaction.status == models.TransactionStatus.pending
    ).order_by(models.Transaction.created_at.asc()).all()
    
    return [{
        "id": t.id,
        "user_id": t.user_id,
        "user_login": u.login,
        "telegram_id": u.telegram_id,
        "type": t.type,
        "amount": t.amount,
        "description": t.description,
        "created_at": t.created_at
    } for t, u in txns]

@router.post("/transactions/{txn_id}/approve")
def approve_transaction(txn_id: int, req: ApproveTransactionRequest,
                        db: Session = Depends(get_db), admin=Depends(require_admin)):
    txn = db.query(models.Transaction).filter(models.Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Topilmadi")
    if txn.status != models.TransactionStatus.pending:
        raise HTTPException(status_code=400, detail="Allaqachon ko'rib chiqilgan")
    
    user = db.query(models.User).filter(models.User.id == txn.user_id).first()
    txn.status = models.TransactionStatus.approved
    txn.processed_at = datetime.utcnow()
    txn.admin_note = req.note
    
    if txn.type == models.TransactionType.deposit:
        user.balance += txn.amount
    
    db.commit()
    return {"success": True, "user_balance": user.balance}

@router.post("/transactions/{txn_id}/reject")
def reject_transaction(txn_id: int, req: ApproveTransactionRequest,
                       db: Session = Depends(get_db), admin=Depends(require_admin)):
    txn = db.query(models.Transaction).filter(models.Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Topilmadi")
    if txn.status != models.TransactionStatus.pending:
        raise HTTPException(status_code=400, detail="Allaqachon ko'rib chiqilgan")
    
    user = db.query(models.User).filter(models.User.id == txn.user_id).first()
    txn.status = models.TransactionStatus.rejected
    txn.processed_at = datetime.utcnow()
    txn.admin_note = req.note
    
    # Refund if withdrawal
    if txn.type == models.TransactionType.withdrawal:
        user.balance += txn.amount
    
    db.commit()
    return {"success": True}

# =================== STATISTICS ===================

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), admin=Depends(require_admin)):
    today = datetime.utcnow().date()
    
    total_users = db.query(func.count(models.User.id)).scalar()
    total_balance = db.query(func.sum(models.User.balance)).scalar() or 0
    
    # Daily profit = total losses - total wins today
    today_games = db.query(models.GameSession).filter(
        func.date(models.GameSession.created_at) == today
    ).all()
    
    daily_bets = sum(g.bet_amount for g in today_games)
    daily_wins = sum(g.win_amount for g in today_games)
    daily_profit = daily_bets - daily_wins
    
    # Top winners
    top_winners = db.query(models.User).order_by(
        desc(models.User.total_wins)
    ).limit(10).all()
    
    # Top losers
    top_losers = db.query(models.User).order_by(
        desc(models.User.total_losses)
    ).limit(10).all()
    
    # Active users today
    active_today = db.query(func.count(func.distinct(models.GameSession.user_id))).filter(
        func.date(models.GameSession.created_at) == today
    ).scalar()
    
    return {
        "total_users": total_users,
        "total_balance": total_balance,
        "daily_profit": daily_profit,
        "daily_bets": daily_bets,
        "active_users_today": active_today,
        "top_winners": [{"login": u.login, "wins": u.total_wins} for u in top_winners],
        "top_losers": [{"login": u.login, "losses": u.total_losses} for u in top_losers]
    }

# =================== USER MANAGEMENT ===================

class UserControlRequest(BaseModel):
    user_id: int
    reason: Optional[str] = None
    ban_hours: Optional[int] = None  # for game ban

@router.post("/users/block")
def block_user(req: UserControlRequest, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    user.status = models.UserStatus.blocked
    db.commit()
    return {"success": True}

@router.post("/users/unblock")
def unblock_user(req: UserControlRequest, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")
    user.status = models.UserStatus.active
    db.commit()
    return {"success": True}

@router.post("/users/freeze")
def freeze_balance(req: UserControlRequest, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")
    user.status = models.UserStatus.frozen
    db.commit()
    return {"success": True}

@router.post("/users/game-ban")
def game_ban(req: UserControlRequest, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")
    hours = req.ban_hours or 24
    user.games_banned_until = datetime.utcnow() + timedelta(hours=hours)
    db.commit()
    return {"success": True, "banned_until": user.games_banned_until}

@router.post("/users/add-balance")
def add_balance(user_id: int, amount: float, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")
    user.balance += amount
    db.commit()
    return {"balance": user.balance}

@router.get("/users")
def list_users(skip: int = 0, limit: int = 50, search: str = None,
               db: Session = Depends(get_db), admin=Depends(require_admin)):
    q = db.query(models.User)
    if search:
        q = q.filter(
            (models.User.login.ilike(f"%{search}%")) |
            (models.User.telegram_id.ilike(f"%{search}%"))
        )
    users = q.offset(skip).limit(limit).all()
    return [{
        "id": u.id,
        "login": u.login,
        "telegram_id": u.telegram_id,
        "balance": u.balance,
        "total_wins": u.total_wins,
        "total_losses": u.total_losses,
        "status": u.status,
        "created_at": u.created_at
    } for u in users]

# =================== PROMO CODES ===================

class PromoCreateRequest(BaseModel):
    code: str
    bonus_type: str  # percentage / fixed
    bonus_value: float
    max_uses: Optional[int] = None
    min_deposit: float = 0.0
    expires_days: Optional[int] = None
    require_subscription: bool = False

@router.post("/promo/create")
def create_promo(req: PromoCreateRequest, db: Session = Depends(get_db), admin=Depends(require_admin)):
    existing = db.query(models.PromoCode).filter(
        models.PromoCode.code == req.code.upper()
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu kod allaqachon mavjud")
    
    expires_at = None
    if req.expires_days:
        expires_at = datetime.utcnow() + timedelta(days=req.expires_days)
    
    promo = models.PromoCode(
        code=req.code.upper(),
        bonus_type=req.bonus_type,
        bonus_value=req.bonus_value,
        max_uses=req.max_uses,
        min_deposit=req.min_deposit,
        expires_at=expires_at,
        require_subscription=req.require_subscription
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return {"id": promo.id, "code": promo.code}

@router.get("/promo/list")
def list_promos(db: Session = Depends(get_db), admin=Depends(require_admin)):
    promos = db.query(models.PromoCode).order_by(models.PromoCode.created_at.desc()).all()
    return [{
        "id": p.id,
        "code": p.code,
        "bonus_type": p.bonus_type,
        "bonus_value": p.bonus_value,
        "max_uses": p.max_uses,
        "current_uses": p.current_uses,
        "is_active": p.is_active,
        "expires_at": p.expires_at
    } for p in promos]

# =================== CHANNELS ===================

class ChannelRequest(BaseModel):
    channel_id: str
    channel_name: str
    channel_url: str

@router.post("/channels/add")
def add_channel(req: ChannelRequest, db: Session = Depends(get_db), admin=Depends(require_admin)):
    channel = models.RequiredChannel(
        channel_id=req.channel_id,
        channel_name=req.channel_name,
        channel_url=req.channel_url
    )
    db.add(channel)
    db.commit()
    return {"success": True}

@router.get("/channels")
def list_channels(db: Session = Depends(get_db), admin=Depends(require_admin)):
    channels = db.query(models.RequiredChannel).filter(
        models.RequiredChannel.is_active == True
    ).all()
    return [{"id": c.id, "channel_id": c.channel_id, "name": c.channel_name, "url": c.channel_url} 
            for c in channels]

@router.delete("/channels/{channel_id}")
def remove_channel(channel_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    channel = db.query(models.RequiredChannel).filter(models.RequiredChannel.id == channel_id).first()
    if channel:
        channel.is_active = False
        db.commit()
    return {"success": True}

# =================== ADS ===================

class AdRequest(BaseModel):
    type: str  # banner / popup / bot_message
    title: str
    content: str
    image_url: Optional[str] = None
    link: Optional[str] = None

@router.post("/ads/create")
def create_ad(req: AdRequest, db: Session = Depends(get_db), admin=Depends(require_admin)):
    ad = models.Advertisement(**req.dict())
    db.add(ad)
    db.commit()
    db.refresh(ad)
    return {"id": ad.id}

@router.get("/ads")
def list_ads(db: Session = Depends(get_db), admin=Depends(require_admin)):
    ads = db.query(models.Advertisement).order_by(models.Advertisement.created_at.desc()).all()
    return ads

@router.get("/ads/active")
def get_active_ads(ad_type: str = None, db: Session = Depends(get_db)):
    """Public endpoint for frontend to get ads"""
    q = db.query(models.Advertisement).filter(models.Advertisement.is_active == True)
    if ad_type:
        q = q.filter(models.Advertisement.type == ad_type)
    ads = q.all()
    for ad in ads:
        ad.show_count += 1
    db.commit()
    return ads
