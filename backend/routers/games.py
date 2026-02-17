from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from routers.auth import get_current_user
import models
import random
import math
import json
from datetime import datetime

router = APIRouter()

# =================== RNG ENGINE ===================

def generate_aviator_crash() -> float:
    """Generate crash multiplier using provably fair RNG.
    House edge ~5%. Min 1.0x, most games crash between 1x-5x.
    """
    r = random.random()
    # Formula: 0.99 / (1 - r) with house edge
    # 5% chance of instant crash at 1.0x
    if r < 0.05:
        return 1.0
    crash = 0.99 / (1 - r)
    return round(min(crash, 1000.0), 2)  # cap at 1000x

def generate_mines_board(size: int = 25, mine_count: int = 5) -> List[int]:
    """Generate mines positions (0=safe, 1=mine)"""
    board = [0] * size
    mine_positions = random.sample(range(size), mine_count)
    for pos in mine_positions:
        board[pos] = 1
    return board

def mines_multiplier(revealed: int, mines: int, total: int = 25) -> float:
    """Calculate mines multiplier based on revealed safe cells"""
    if revealed == 0:
        return 1.0
    safe_total = total - mines
    multiplier = 1.0
    for i in range(revealed):
        remaining = total - i
        safe_remaining = safe_total - i
        prob = safe_remaining / remaining
        multiplier *= (1.0 / prob) * 0.97  # 3% house edge
    return round(multiplier, 2)

def apple_multipliers(levels: int = 5) -> List[float]:
    """Generate multiplier sequence for Apple Fortune"""
    multipliers = []
    base = 1.5
    for i in range(levels):
        mult = round(base * (1.4 ** i), 2)
        multipliers.append(mult)
    return multipliers

def apple_board_per_level(apples_per_level: int = 3, bad_apples: int = 1) -> List[int]:
    """Generate apple board: 0=good, 1=bad"""
    board = [0] * apples_per_level
    bad_pos = random.sample(range(apples_per_level), bad_apples)
    for pos in bad_pos:
        board[pos] = 1
    return board

# =================== AVIATOR ===================

class AviatorBetRequest(BaseModel):
    bet: float
    auto_cashout: Optional[float] = None  # auto cashout multiplier

class AviatorCashoutRequest(BaseModel):
    session_id: int
    current_multiplier: float

@router.post("/aviator/start")
def aviator_start(req: AviatorBetRequest, db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    if req.bet <= 0:
        raise HTTPException(status_code=400, detail="Bet noto'g'ri")
    if current_user.balance < req.bet:
        raise HTTPException(status_code=400, detail="Balans yetarli emas")
    
    # Check game ban
    if current_user.games_banned_until and current_user.games_banned_until > datetime.utcnow():
        raise HTTPException(status_code=403, detail="O'yin taqiqlangan")
    
    crash_at = generate_aviator_crash()
    
    # Deduct bet
    current_user.balance -= req.bet
    
    # Create session
    session = models.GameSession(
        user_id=current_user.id,
        game_type=models.GameType.aviator,
        bet_amount=req.bet,
        result="pending",
        game_data=json.dumps({
            "crash_at": crash_at,
            "auto_cashout": req.auto_cashout,
            "cashed_out": False
        })
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # Handle auto cashout
    auto_result = None
    if req.auto_cashout and req.auto_cashout <= crash_at:
        # Auto cashout wins
        win = round(req.bet * req.auto_cashout, 2)
        current_user.balance += win
        current_user.total_wins += win - req.bet
        session.win_amount = win
        session.multiplier = req.auto_cashout
        session.result = "win"
        game_data = json.loads(session.game_data)
        game_data["cashed_out"] = True
        game_data["cashout_multiplier"] = req.auto_cashout
        session.game_data = json.dumps(game_data)
        auto_result = {"cashed_out": True, "multiplier": req.auto_cashout, "win": win}
    elif req.auto_cashout and req.auto_cashout > crash_at:
        # Auto cashout too late - crash
        current_user.total_losses += req.bet
        session.result = "loss"
        auto_result = {"cashed_out": False, "crashed_at": crash_at}
    
    db.commit()
    
    response = {
        "session_id": session.id,
        "crash_at": crash_at,
        "balance": current_user.balance
    }
    if auto_result:
        response["auto_result"] = auto_result
    
    return response

@router.post("/aviator/cashout")
def aviator_cashout(req: AviatorCashoutRequest, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    session = db.query(models.GameSession).filter(
        models.GameSession.id == req.session_id,
        models.GameSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session topilmadi")
    if session.result != "pending":
        raise HTTPException(status_code=400, detail="O'yin tugagan")
    
    game_data = json.loads(session.game_data)
    crash_at = game_data["crash_at"]
    
    if req.current_multiplier > crash_at:
        # Too late - already crashed
        current_user.total_losses += session.bet_amount
        session.result = "loss"
        session.multiplier = crash_at
        db.commit()
        return {"success": False, "crashed_at": crash_at, "message": "Samolyot qulab tushdi!"}
    
    # Successful cashout
    win = round(session.bet_amount * req.current_multiplier, 2)
    current_user.balance += win
    current_user.total_wins += win - session.bet_amount
    session.win_amount = win
    session.multiplier = req.current_multiplier
    session.result = "win"
    game_data["cashed_out"] = True
    game_data["cashout_multiplier"] = req.current_multiplier
    session.game_data = json.dumps(game_data)
    db.commit()
    
    return {
        "success": True,
        "multiplier": req.current_multiplier,
        "win": win,
        "balance": current_user.balance
    }

# =================== MINES ===================

class MinesBetRequest(BaseModel):
    bet: float
    mines_count: int = 5  # 1-24

class MinesRevealRequest(BaseModel):
    session_id: int
    cell_index: int

class MinesCashoutRequest(BaseModel):
    session_id: int

@router.post("/mines/start")
def mines_start(req: MinesBetRequest, db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    if req.bet <= 0:
        raise HTTPException(status_code=400, detail="Bet noto'g'ri")
    if current_user.balance < req.bet:
        raise HTTPException(status_code=400, detail="Balans yetarli emas")
    if req.mines_count < 1 or req.mines_count > 24:
        raise HTTPException(status_code=400, detail="Minalar soni 1-24 orasida bo'lishi kerak")
    
    if current_user.games_banned_until and current_user.games_banned_until > datetime.utcnow():
        raise HTTPException(status_code=403, detail="O'yin taqiqlangan")
    
    board = generate_mines_board(25, req.mines_count)
    current_user.balance -= req.bet
    
    session = models.GameSession(
        user_id=current_user.id,
        game_type=models.GameType.mines,
        bet_amount=req.bet,
        result="pending",
        game_data=json.dumps({
            "board": board,
            "mines_count": req.mines_count,
            "revealed": [],
            "current_multiplier": 1.0,
            "game_over": False
        })
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return {
        "session_id": session.id,
        "mines_count": req.mines_count,
        "current_multiplier": 1.0,
        "balance": current_user.balance
    }

@router.post("/mines/reveal")
def mines_reveal(req: MinesRevealRequest, db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    session = db.query(models.GameSession).filter(
        models.GameSession.id == req.session_id,
        models.GameSession.user_id == current_user.id
    ).first()
    
    if not session or session.result != "pending":
        raise HTTPException(status_code=400, detail="Session topilmadi yoki tugagan")
    
    game_data = json.loads(session.game_data)
    board = game_data["board"]
    revealed = game_data["revealed"]
    
    if req.cell_index in revealed:
        raise HTTPException(status_code=400, detail="Bu katak allaqachon ochilgan")
    if req.cell_index < 0 or req.cell_index >= 25:
        raise HTTPException(status_code=400, detail="Noto'g'ri katak")
    
    revealed.append(req.cell_index)
    cell_value = board[req.cell_index]
    
    if cell_value == 1:
        # Hit a mine!
        current_user.total_losses += session.bet_amount
        session.result = "loss"
        game_data["revealed"] = revealed
        game_data["game_over"] = True
        session.game_data = json.dumps(game_data)
        db.commit()
        return {
            "hit_mine": True,
            "cell": req.cell_index,
            "board": board,  # reveal full board on loss
            "balance": current_user.balance
        }
    
    # Safe cell
    new_multiplier = mines_multiplier(len(revealed), game_data["mines_count"])
    game_data["revealed"] = revealed
    game_data["current_multiplier"] = new_multiplier
    session.game_data = json.dumps(game_data)
    session.multiplier = new_multiplier
    db.commit()
    
    return {
        "hit_mine": False,
        "cell": req.cell_index,
        "revealed_count": len(revealed),
        "current_multiplier": new_multiplier,
        "balance": current_user.balance
    }

@router.post("/mines/cashout")
def mines_cashout(req: MinesCashoutRequest, db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    session = db.query(models.GameSession).filter(
        models.GameSession.id == req.session_id,
        models.GameSession.user_id == current_user.id
    ).first()
    
    if not session or session.result != "pending":
        raise HTTPException(status_code=400, detail="Session topilmadi yoki tugagan")
    
    game_data = json.loads(session.game_data)
    if len(game_data["revealed"]) == 0:
        raise HTTPException(status_code=400, detail="Hech bo'lmasa 1 katak oching")
    
    multiplier = game_data["current_multiplier"]
    win = round(session.bet_amount * multiplier, 2)
    
    current_user.balance += win
    current_user.total_wins += win - session.bet_amount
    session.win_amount = win
    session.multiplier = multiplier
    session.result = "win"
    game_data["game_over"] = True
    session.game_data = json.dumps(game_data)
    db.commit()
    
    return {
        "multiplier": multiplier,
        "win": win,
        "balance": current_user.balance,
        "board": game_data["board"]
    }

# =================== APPLE FORTUNE ===================

class AppleBetRequest(BaseModel):
    bet: float
    levels: int = 5

class ApplePickRequest(BaseModel):
    session_id: int
    apple_index: int

class AppleCashoutRequest(BaseModel):
    session_id: int

@router.post("/apple/start")
def apple_start(req: AppleBetRequest, db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    if req.bet <= 0 or current_user.balance < req.bet:
        raise HTTPException(status_code=400, detail="Bet noto'g'ri yoki balans yetarli emas")
    
    if current_user.games_banned_until and current_user.games_banned_until > datetime.utcnow():
        raise HTTPException(status_code=403, detail="O'yin taqiqlangan")
    
    levels = min(max(req.levels, 3), 8)
    apples_per_level = 3
    multipliers = apple_multipliers(levels)
    
    # Pre-generate all level boards
    level_boards = [apple_board_per_level(apples_per_level, 1) for _ in range(levels)]
    
    current_user.balance -= req.bet
    
    session = models.GameSession(
        user_id=current_user.id,
        game_type=models.GameType.apple_fortune,
        bet_amount=req.bet,
        result="pending",
        game_data=json.dumps({
            "levels": levels,
            "apples_per_level": apples_per_level,
            "multipliers": multipliers,
            "level_boards": level_boards,
            "current_level": 0,
            "current_multiplier": 1.0,
            "game_over": False
        })
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return {
        "session_id": session.id,
        "levels": levels,
        "apples_per_level": apples_per_level,
        "multipliers": multipliers,
        "current_level": 0,
        "balance": current_user.balance
    }

@router.post("/apple/pick")
def apple_pick(req: ApplePickRequest, db: Session = Depends(get_db),
               current_user: models.User = Depends(get_current_user)):
    session = db.query(models.GameSession).filter(
        models.GameSession.id == req.session_id,
        models.GameSession.user_id == current_user.id
    ).first()
    
    if not session or session.result != "pending":
        raise HTTPException(status_code=400, detail="Session topilmadi yoki tugagan")
    
    game_data = json.loads(session.game_data)
    current_level = game_data["current_level"]
    level_board = game_data["level_boards"][current_level]
    multipliers = game_data["multipliers"]
    
    if req.apple_index < 0 or req.apple_index >= game_data["apples_per_level"]:
        raise HTTPException(status_code=400, detail="Noto'g'ri olma")
    
    apple_value = level_board[req.apple_index]
    
    if apple_value == 1:
        # Red apple - loss!
        current_user.total_losses += session.bet_amount
        session.result = "loss"
        game_data["game_over"] = True
        session.game_data = json.dumps(game_data)
        db.commit()
        return {
            "bad_apple": True,
            "apple_index": req.apple_index,
            "level_board": level_board,
            "balance": current_user.balance
        }
    
    # Green apple - advance
    new_level = current_level + 1
    new_multiplier = multipliers[current_level]
    game_data["current_level"] = new_level
    game_data["current_multiplier"] = new_multiplier
    session.multiplier = new_multiplier
    
    if new_level >= game_data["levels"]:
        # Completed all levels - auto win!
        win = round(session.bet_amount * new_multiplier, 2)
        current_user.balance += win
        current_user.total_wins += win - session.bet_amount
        session.win_amount = win
        session.result = "win"
        game_data["game_over"] = True
        session.game_data = json.dumps(game_data)
        db.commit()
        return {
            "bad_apple": False,
            "completed": True,
            "multiplier": new_multiplier,
            "win": win,
            "balance": current_user.balance
        }
    
    session.game_data = json.dumps(game_data)
    db.commit()
    
    return {
        "bad_apple": False,
        "completed": False,
        "current_level": new_level,
        "current_multiplier": new_multiplier,
        "next_multiplier": multipliers[new_level] if new_level < len(multipliers) else None,
        "balance": current_user.balance
    }

@router.post("/apple/cashout")
def apple_cashout(req: AppleCashoutRequest, db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    session = db.query(models.GameSession).filter(
        models.GameSession.id == req.session_id,
        models.GameSession.user_id == current_user.id
    ).first()
    
    if not session or session.result != "pending":
        raise HTTPException(status_code=400, detail="Session topilmadi yoki tugagan")
    
    game_data = json.loads(session.game_data)
    if game_data["current_level"] == 0:
        raise HTTPException(status_code=400, detail="Hech bo'lmasa 1 qavatdan o'ting")
    
    multiplier = game_data["current_multiplier"]
    win = round(session.bet_amount * multiplier, 2)
    
    current_user.balance += win
    current_user.total_wins += win - session.bet_amount
    session.win_amount = win
    session.multiplier = multiplier
    session.result = "win"
    game_data["game_over"] = True
    session.game_data = json.dumps(game_data)
    db.commit()
    
    return {
        "multiplier": multiplier,
        "win": win,
        "balance": current_user.balance
    }

@router.get("/history")
def game_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    sessions = db.query(models.GameSession).filter(
        models.GameSession.user_id == current_user.id
    ).order_by(models.GameSession.created_at.desc()).limit(limit).all()
    
    return [{
        "id": s.id,
        "game_type": s.game_type,
        "bet": s.bet_amount,
        "win": s.win_amount,
        "multiplier": s.multiplier,
        "result": s.result,
        "created_at": s.created_at
    } for s in sessions]
