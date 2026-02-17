from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from typing import Optional
from database import get_db
from routers.auth import get_current_user
import models
from datetime import datetime, timedelta

router = APIRouter()

def require_admin(u=Depends(get_current_user)):
    if not u.is_admin: raise HTTPException(403, "Admin huquqi yo'q")
    return u

# ===== TRANSACTIONS =====
class ApproveReq(BaseModel):
    note: Optional[str] = None

@router.get("/transactions/pending")
def pending_txns(db: Session = Depends(get_db), admin=Depends(require_admin)):
    rows = db.query(models.Transaction, models.User).join(
        models.User, models.Transaction.user_id == models.User.id
    ).filter(models.Transaction.status == models.TransactionStatus.pending).all()
    return [{"id": t.id, "user_id": t.user_id, "user_login": u.login, "telegram_id": u.telegram_id,
             "type": t.type, "amount": t.amount, "description": t.description,
             "created_at": t.created_at} for t, u in rows]

@router.post("/transactions/{txn_id}/approve")
def approve_txn(txn_id: int, req: ApproveReq, db: Session = Depends(get_db), admin=Depends(require_admin)):
    t = db.query(models.Transaction).filter(models.Transaction.id == txn_id).first()
    if not t: raise HTTPException(404, "Topilmadi")
    if t.status != models.TransactionStatus.pending: raise HTTPException(400, "Allaqachon ko'rib chiqilgan")
    u = db.query(models.User).filter(models.User.id == t.user_id).first()
    t.status = models.TransactionStatus.approved
    t.processed_at = datetime.utcnow()
    t.admin_note = req.note
    if t.type == models.TransactionType.deposit: u.balance += t.amount
    db.commit()
    return {"success": True, "user_balance": u.balance}

@router.post("/transactions/{txn_id}/reject")
def reject_txn(txn_id: int, req: ApproveReq, db: Session = Depends(get_db), admin=Depends(require_admin)):
    t = db.query(models.Transaction).filter(models.Transaction.id == txn_id).first()
    if not t: raise HTTPException(404, "Topilmadi")
    if t.status != models.TransactionStatus.pending: raise HTTPException(400, "Allaqachon ko'rib chiqilgan")
    u = db.query(models.User).filter(models.User.id == t.user_id).first()
    t.status = models.TransactionStatus.rejected
    t.processed_at = datetime.utcnow()
    t.admin_note = req.note
    if t.type == models.TransactionType.withdrawal: u.balance += t.amount
    db.commit()
    return {"success": True}

# ===== STATS =====
@router.get("/stats")
def stats(db: Session = Depends(get_db), admin=Depends(require_admin)):
    today = datetime.utcnow().date()
    total_users = db.query(func.count(models.User.id)).scalar()
    total_bal = db.query(func.sum(models.User.balance)).scalar() or 0
    today_games = db.query(models.GameSession).filter(func.date(models.GameSession.created_at) == today).all()
    daily_bets = sum(g.bet_amount for g in today_games)
    daily_wins = sum(g.win_amount for g in today_games)
    active = db.query(func.count(func.distinct(models.GameSession.user_id))).filter(
        func.date(models.GameSession.created_at) == today).scalar()
    top_w = db.query(models.User).order_by(desc(models.User.total_wins)).limit(10).all()
    top_l = db.query(models.User).order_by(desc(models.User.total_losses)).limit(10).all()
    return {
        "total_users": total_users, "total_balance": total_bal,
        "daily_profit": daily_bets - daily_wins, "daily_bets": daily_bets,
        "active_users_today": active,
        "top_winners": [{"login": u.login, "wins": u.total_wins} for u in top_w],
        "top_losers": [{"login": u.login, "losses": u.total_losses} for u in top_l]
    }

# ===== USERS =====
class UserCtrl(BaseModel):
    user_id: int
    reason: Optional[str] = None
    ban_hours: Optional[int] = None

@router.post("/users/block")
def block(req: UserCtrl, db: Session = Depends(get_db), admin=Depends(require_admin)):
    u = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not u: raise HTTPException(404, "Topilmadi")
    u.status = models.UserStatus.blocked; db.commit()
    return {"success": True}

@router.post("/users/unblock")
def unblock(req: UserCtrl, db: Session = Depends(get_db), admin=Depends(require_admin)):
    u = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not u: raise HTTPException(404, "Topilmadi")
    u.status = models.UserStatus.active; db.commit()
    return {"success": True}

@router.post("/users/freeze")
def freeze(req: UserCtrl, db: Session = Depends(get_db), admin=Depends(require_admin)):
    u = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not u: raise HTTPException(404, "Topilmadi")
    u.status = models.UserStatus.frozen; db.commit()
    return {"success": True}

@router.post("/users/game-ban")
def game_ban(req: UserCtrl, db: Session = Depends(get_db), admin=Depends(require_admin)):
    u = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not u: raise HTTPException(404, "Topilmadi")
    u.games_banned_until = datetime.utcnow() + timedelta(hours=req.ban_hours or 24)
    db.commit()
    return {"success": True, "banned_until": u.games_banned_until}

@router.post("/users/add-balance")
def add_bal(user_id: int, amount: float, db: Session = Depends(get_db), admin=Depends(require_admin)):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u: raise HTTPException(404, "Topilmadi")
    u.balance += amount; db.commit()
    return {"balance": u.balance}

@router.get("/users")
def list_users(skip: int = 0, limit: int = 50, search: str = None,
               db: Session = Depends(get_db), admin=Depends(require_admin)):
    q = db.query(models.User)
    if search:
        q = q.filter((models.User.login.ilike(f"%{search}%")) | (models.User.telegram_id.ilike(f"%{search}%")))
    users = q.offset(skip).limit(limit).all()
    return [{"id": u.id, "login": u.login, "telegram_id": u.telegram_id, "balance": u.balance,
             "total_wins": u.total_wins, "total_losses": u.total_losses,
             "status": u.status, "created_at": u.created_at} for u in users]

# ===== BOT ENDPOINTS =====
class DepApprove(BaseModel):
    telegram_id: str
    amount: float

@router.post("/deposit-approve-telegram")
def dep_approve_tg(req: DepApprove, db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.telegram_id == req.telegram_id).first()
    if not u: raise HTTPException(404, "Topilmadi")
    u.balance += req.amount
    db.add(models.Transaction(user_id=u.id, type=models.TransactionType.deposit,
                               amount=req.amount, status=models.TransactionStatus.approved,
                               description="Bot orqali admin tasdiqladi"))
    db.commit()
    return {"success": True, "balance": u.balance}

class WdRequest(BaseModel):
    telegram_id: str
    amount: float
    payment_details: str

@router.post("/withdraw-request-telegram")
def wd_req_tg(req: WdRequest, db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.telegram_id == req.telegram_id).first()
    if not u: raise HTTPException(404, "Topilmadi")
    if u.balance < req.amount: raise HTTPException(400, "Balans yetarli emas")
    u.balance -= req.amount
    db.add(models.Transaction(user_id=u.id, type=models.TransactionType.withdrawal,
                               amount=req.amount, status=models.TransactionStatus.pending,
                               description=f"Bot orqali yechish: {req.payment_details}"))
    db.commit()
    return {"success": True, "balance": u.balance}

# ===== PROMO =====
class PromoCreate(BaseModel):
    code: str
    bonus_type: str
    bonus_value: float
    max_uses: Optional[int] = None
    min_deposit: float = 0.0
    expires_days: Optional[int] = None
    require_subscription: bool = False

@router.post("/promo/create")
def create_promo(req: PromoCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    if db.query(models.PromoCode).filter(models.PromoCode.code == req.code.upper()).first():
        raise HTTPException(400, "Bu kod mavjud")
    expires = None
    if req.expires_days:
        from datetime import timedelta
        expires = datetime.utcnow() + timedelta(days=req.expires_days)
    p = models.PromoCode(code=req.code.upper(), bonus_type=req.bonus_type,
                          bonus_value=req.bonus_value, max_uses=req.max_uses,
                          min_deposit=req.min_deposit, expires_at=expires,
                          require_subscription=req.require_subscription)
    db.add(p); db.commit(); db.refresh(p)
    return {"id": p.id, "code": p.code}

@router.get("/promo/list")
def promo_list(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return [{"id": p.id, "code": p.code, "bonus_type": p.bonus_type, "bonus_value": p.bonus_value,
             "max_uses": p.max_uses, "current_uses": p.current_uses,
             "is_active": p.is_active, "expires_at": p.expires_at}
            for p in db.query(models.PromoCode).order_by(models.PromoCode.created_at.desc()).all()]

# ===== CHANNELS =====
class ChannelReq(BaseModel):
    channel_id: str
    channel_name: str
    channel_url: str

@router.post("/channels/add")
def add_ch(req: ChannelReq, db: Session = Depends(get_db), admin=Depends(require_admin)):
    db.add(models.RequiredChannel(channel_id=req.channel_id, channel_name=req.channel_name, channel_url=req.channel_url))
    db.commit()
    return {"success": True}

@router.get("/channels")
def list_ch(db: Session = Depends(get_db)):
    chs = db.query(models.RequiredChannel).filter(models.RequiredChannel.is_active == True).all()
    return [{"id": c.id, "channel_id": c.channel_id, "name": c.channel_name, "url": c.channel_url} for c in chs]

@router.delete("/channels/{ch_id}")
def del_ch(ch_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    c = db.query(models.RequiredChannel).filter(models.RequiredChannel.id == ch_id).first()
    if c: c.is_active = False; db.commit()
    return {"success": True}

# ===== ADS =====
class AdReq(BaseModel):
    type: str
    title: str
    content: str
    image_url: Optional[str] = None
    link: Optional[str] = None

@router.post("/ads/create")
def create_ad(req: AdReq, db: Session = Depends(get_db), admin=Depends(require_admin)):
    ad = models.Advertisement(**req.dict())
    db.add(ad); db.commit(); db.refresh(ad)
    return {"id": ad.id}

@router.get("/ads")
def list_ads(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return db.query(models.Advertisement).order_by(models.Advertisement.created_at.desc()).all()

@router.get("/ads/active")
def active_ads(ad_type: str = None, db: Session = Depends(get_db)):
    q = db.query(models.Advertisement).filter(models.Advertisement.is_active == True)
    if ad_type: q = q.filter(models.Advertisement.type == ad_type)
    ads = q.all()
    for a in ads: a.show_count += 1
    db.commit()
    return ads
