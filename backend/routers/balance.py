from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from routers.auth import get_current_user
import models
from datetime import datetime

router = APIRouter()

class DepositRequest(BaseModel):
    amount: float
    payment_method: str = "card"
    payment_proof: Optional[str] = None  # screenshot/txid

class WithdrawRequest(BaseModel):
    amount: float
    payment_method: str
    payment_details: str  # card number, wallet address etc.

class PromoRequest(BaseModel):
    code: str
    deposit_amount: Optional[float] = None

@router.post("/deposit")
def request_deposit(req: DepositRequest, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Summa noto'g'ri")
    
    transaction = models.Transaction(
        user_id=current_user.id,
        type=models.TransactionType.deposit,
        amount=req.amount,
        status=models.TransactionStatus.pending,
        description=f"Depozit so'rovi: {req.payment_method}"
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    return {
        "transaction_id": transaction.id,
        "amount": req.amount,
        "status": "pending",
        "message": "So'rovingiz admin tomonidan ko'rib chiqiladi"
    }

@router.post("/withdraw")
def request_withdraw(req: WithdrawRequest, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Summa noto'g'ri")
    if current_user.balance < req.amount:
        raise HTTPException(status_code=400, detail="Balans yetarli emas")
    if current_user.status == models.UserStatus.frozen:
        raise HTTPException(status_code=403, detail="Balans muzlatilgan")
    
    # Reserve funds
    current_user.balance -= req.amount
    
    transaction = models.Transaction(
        user_id=current_user.id,
        type=models.TransactionType.withdrawal,
        amount=req.amount,
        status=models.TransactionStatus.pending,
        description=f"Yechish: {req.payment_method} - {req.payment_details}"
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    return {
        "transaction_id": transaction.id,
        "amount": req.amount,
        "status": "pending",
        "message": "Yechish so'rovi qabul qilindi",
        "balance": current_user.balance
    }

@router.post("/promo/apply")
def apply_promo(req: PromoRequest, db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    promo = db.query(models.PromoCode).filter(
        models.PromoCode.code == req.code.upper(),
        models.PromoCode.is_active == True
    ).first()
    
    if not promo:
        raise HTTPException(status_code=404, detail="Promokod topilmadi")
    
    # Check expiry
    if promo.expires_at and promo.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Promokod muddati tugagan")
    
    # Check max uses
    if promo.max_uses and promo.current_uses >= promo.max_uses:
        raise HTTPException(status_code=400, detail="Promokod foydalanish limiti to'ldi")
    
    # Check user already used
    existing = db.query(models.PromoCodeUse).filter(
        models.PromoCodeUse.promo_id == promo.id,
        models.PromoCodeUse.user_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu promokodni allaqachon ishlatgansiz")
    
    # Check subscription requirement
    if promo.require_subscription:
        channels = db.query(models.RequiredChannel).filter(
            models.RequiredChannel.is_active == True
        ).all()
        for channel in channels:
            sub = db.query(models.ChannelSubscription).filter(
                models.ChannelSubscription.user_id == current_user.id,
                models.ChannelSubscription.channel_id == channel.channel_id
            ).first()
            if not sub:
                raise HTTPException(
                    status_code=403,
                    detail=f"Promokod uchun kanalga obuna bo'ling: {channel.channel_url}"
                )
    
    # Calculate bonus
    if promo.bonus_type == "percentage":
        deposit = req.deposit_amount or 0
        if deposit < promo.min_deposit:
            raise HTTPException(status_code=400, detail=f"Minimal depozit: {promo.min_deposit}")
        bonus = round(deposit * promo.bonus_value / 100, 2)
    else:  # fixed
        bonus = promo.bonus_value
    
    # Apply bonus
    current_user.balance += bonus
    promo.current_uses += 1
    
    use = models.PromoCodeUse(promo_id=promo.id, user_id=current_user.id)
    db.add(use)
    
    transaction = models.Transaction(
        user_id=current_user.id,
        type=models.TransactionType.promo,
        amount=bonus,
        status=models.TransactionStatus.approved,
        description=f"Promokod bonus: {req.code}"
    )
    db.add(transaction)
    db.commit()
    
    return {"bonus": bonus, "balance": current_user.balance, "message": f"+{bonus} UZS bonus!"}

@router.get("/transactions")
def get_transactions(limit: int = 20, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    txns = db.query(models.Transaction).filter(
        models.Transaction.user_id == current_user.id
    ).order_by(models.Transaction.created_at.desc()).limit(limit).all()
    
    return [{
        "id": t.id,
        "type": t.type,
        "amount": t.amount,
        "status": t.status,
        "description": t.description,
        "created_at": t.created_at
    } for t in txns]
