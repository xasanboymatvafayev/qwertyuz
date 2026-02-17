from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from routers.auth import get_current_user
import models
from datetime import datetime

router = APIRouter()

class DepositReq(BaseModel):
    amount: float
    payment_method: str = "card"
    payment_proof: Optional[str] = None

class WithdrawReq(BaseModel):
    amount: float
    payment_method: str = "card"
    payment_details: str

class PromoReq(BaseModel):
    code: str
    deposit_amount: Optional[float] = None

@router.post("/deposit")
def deposit(req: DepositReq, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if req.amount <= 0: raise HTTPException(400, "Summa noto'g'ri")
    txn = models.Transaction(
        user_id=u.id, type=models.TransactionType.deposit,
        amount=req.amount, status=models.TransactionStatus.pending,
        description=f"Depozit: {req.payment_method} | {req.payment_proof or ''}"
    )
    db.add(txn); db.commit(); db.refresh(txn)
    return {"transaction_id": txn.id, "amount": req.amount, "status": "pending",
            "message": "So'rovingiz admin tomonidan ko'rib chiqiladi"}

@router.post("/withdraw")
def withdraw(req: WithdrawReq, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if req.amount <= 0: raise HTTPException(400, "Summa noto'g'ri")
    if u.balance < req.amount: raise HTTPException(400, "Balans yetarli emas")
    if u.status == models.UserStatus.frozen: raise HTTPException(403, "Balans muzlatilgan")

    u.balance -= req.amount
    txn = models.Transaction(
        user_id=u.id, type=models.TransactionType.withdrawal,
        amount=req.amount, status=models.TransactionStatus.pending,
        description=f"Yechish: {req.payment_details}"
    )
    db.add(txn); db.commit(); db.refresh(txn)
    return {"transaction_id": txn.id, "amount": req.amount, "status": "pending",
            "balance": u.balance, "message": "Yechish so'rovi qabul qilindi"}

@router.post("/promo/apply")
def apply_promo(req: PromoReq, db: Session = Depends(get_db), u=Depends(get_current_user)):
    promo = db.query(models.PromoCode).filter(
        models.PromoCode.code == req.code.upper(),
        models.PromoCode.is_active == True
    ).first()
    if not promo: raise HTTPException(404, "Promokod topilmadi")
    if promo.expires_at and promo.expires_at < datetime.utcnow(): raise HTTPException(400, "Muddati tugagan")
    if promo.max_uses and promo.current_uses >= promo.max_uses: raise HTTPException(400, "Limit to'ldi")

    used = db.query(models.PromoCodeUse).filter(
        models.PromoCodeUse.promo_id == promo.id,
        models.PromoCodeUse.user_id == u.id
    ).first()
    if used: raise HTTPException(400, "Allaqachon ishlatilgan")

    if promo.bonus_type == "percentage":
        dep = req.deposit_amount or 0
        if dep < promo.min_deposit: raise HTTPException(400, f"Minimal depozit: {promo.min_deposit}")
        bonus = round(dep * promo.bonus_value / 100, 2)
    else:
        bonus = promo.bonus_value

    u.balance += bonus; promo.current_uses += 1
    db.add(models.PromoCodeUse(promo_id=promo.id, user_id=u.id))
    db.add(models.Transaction(user_id=u.id, type=models.TransactionType.promo,
                               amount=bonus, status=models.TransactionStatus.approved,
                               description=f"Promo: {req.code}"))
    db.commit()
    return {"bonus": bonus, "balance": u.balance, "message": f"+{bonus} UZS bonus!"}

@router.get("/transactions")
def transactions(limit: int = 20, db: Session = Depends(get_db), u=Depends(get_current_user)):
    txns = db.query(models.Transaction).filter(
        models.Transaction.user_id == u.id
    ).order_by(models.Transaction.created_at.desc()).limit(limit).all()
    return [{"id": t.id, "type": t.type, "amount": t.amount,
             "status": t.status, "description": t.description,
             "created_at": t.created_at} for t in txns]
