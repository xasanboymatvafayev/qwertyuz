from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from routers.auth import get_current_user
import models, random, json
from datetime import datetime

router = APIRouter()

# ===== RNG =====
def rng_aviator() -> float:
    r = random.random()
    if r < 0.05: return 1.0
    return round(min(0.99 / (1 - r), 1000.0), 2)

def rng_mines_board(size=25, mines=5):
    board = [0] * size
    for p in random.sample(range(size), mines):
        board[p] = 1
    return board

def mines_mult(revealed, mines, total=25):
    if revealed == 0: return 1.0
    safe = total - mines
    m = 1.0
    for i in range(revealed):
        m *= ((safe - i) / (total - i)) ** -1 * 0.97
    return round(m, 2)

def apple_mults(levels=5):
    return [round(1.5 * (1.4 ** i), 2) for i in range(levels)]

def apple_board(apples=3, bad=1):
    b = [0] * apples
    for p in random.sample(range(apples), bad): b[p] = 1
    return b

def check_ban(user):
    if user.games_banned_until and user.games_banned_until > datetime.utcnow():
        raise HTTPException(status_code=403, detail="O'yin taqiqlangan")

# ===== AVIATOR =====
class AviBet(BaseModel):
    bet: float
    auto_cashout: Optional[float] = None

class AviCash(BaseModel):
    session_id: int
    current_multiplier: float

@router.post("/aviator/start")
def aviator_start(req: AviBet, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if req.bet <= 0: raise HTTPException(400, "Bet noto'g'ri")
    if u.balance < req.bet: raise HTTPException(400, "Balans yetarli emas")
    check_ban(u)

    crash = rng_aviator()
    u.balance -= req.bet

    sess = models.GameSession(
        user_id=u.id, game_type=models.GameType.aviator,
        bet_amount=req.bet, result="pending",
        game_data=json.dumps({"crash_at": crash, "auto_cashout": req.auto_cashout})
    )
    db.add(sess); db.commit(); db.refresh(sess)

    auto_result = None
    if req.auto_cashout:
        if req.auto_cashout <= crash:
            win = round(req.bet * req.auto_cashout, 2)
            u.balance += win; u.total_wins += win - req.bet
            sess.win_amount = win; sess.multiplier = req.auto_cashout; sess.result = "win"
            auto_result = {"cashed_out": True, "multiplier": req.auto_cashout, "win": win}
        else:
            u.total_losses += req.bet; sess.result = "loss"
            auto_result = {"cashed_out": False, "crashed_at": crash}

    db.commit()
    resp = {"session_id": sess.id, "crash_at": crash, "balance": u.balance}
    if auto_result: resp["auto_result"] = auto_result
    return resp

@router.post("/aviator/cashout")
def aviator_cashout(req: AviCash, db: Session = Depends(get_db), u=Depends(get_current_user)):
    sess = db.query(models.GameSession).filter(
        models.GameSession.id == req.session_id,
        models.GameSession.user_id == u.id
    ).first()
    if not sess: raise HTTPException(404, "Session topilmadi")
    if sess.result != "pending": raise HTTPException(400, "O'yin tugagan")

    crash = json.loads(sess.game_data)["crash_at"]
    if req.current_multiplier > crash:
        u.total_losses += sess.bet_amount; sess.result = "loss"; sess.multiplier = crash
        db.commit()
        return {"success": False, "crashed_at": crash, "message": "Qulab tushdi!"}

    win = round(sess.bet_amount * req.current_multiplier, 2)
    u.balance += win; u.total_wins += win - sess.bet_amount
    sess.win_amount = win; sess.multiplier = req.current_multiplier; sess.result = "win"
    db.commit()
    return {"success": True, "multiplier": req.current_multiplier, "win": win, "balance": u.balance}

# ===== MINES =====
class MinesBet(BaseModel):
    bet: float
    mines_count: int = 5

class MinesReveal(BaseModel):
    session_id: int
    cell_index: int

class MinesCash(BaseModel):
    session_id: int

@router.post("/mines/start")
def mines_start(req: MinesBet, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if req.bet <= 0: raise HTTPException(400, "Bet noto'g'ri")
    if u.balance < req.bet: raise HTTPException(400, "Balans yetarli emas")
    if not (1 <= req.mines_count <= 24): raise HTTPException(400, "Minalar 1-24 bo'lsin")
    check_ban(u)

    board = rng_mines_board(25, req.mines_count)
    u.balance -= req.bet
    sess = models.GameSession(
        user_id=u.id, game_type=models.GameType.mines,
        bet_amount=req.bet, result="pending",
        game_data=json.dumps({"board": board, "mines_count": req.mines_count, "revealed": [], "current_multiplier": 1.0})
    )
    db.add(sess); db.commit(); db.refresh(sess)
    return {"session_id": sess.id, "mines_count": req.mines_count, "balance": u.balance}

@router.post("/mines/reveal")
def mines_reveal(req: MinesReveal, db: Session = Depends(get_db), u=Depends(get_current_user)):
    sess = db.query(models.GameSession).filter(
        models.GameSession.id == req.session_id, models.GameSession.user_id == u.id
    ).first()
    if not sess or sess.result != "pending": raise HTTPException(400, "Session yo'q yoki tugagan")

    gd = json.loads(sess.game_data)
    if req.cell_index in gd["revealed"]: raise HTTPException(400, "Allaqachon ochilgan")
    if not (0 <= req.cell_index < 25): raise HTTPException(400, "Noto'g'ri katak")

    gd["revealed"].append(req.cell_index)
    if gd["board"][req.cell_index] == 1:
        u.total_losses += sess.bet_amount; sess.result = "loss"
        sess.game_data = json.dumps(gd); db.commit()
        return {"hit_mine": True, "cell": req.cell_index, "board": gd["board"], "balance": u.balance}

    new_mult = mines_mult(len(gd["revealed"]), gd["mines_count"])
    gd["current_multiplier"] = new_mult
    sess.game_data = json.dumps(gd); sess.multiplier = new_mult
    db.commit()
    return {"hit_mine": False, "cell": req.cell_index, "revealed_count": len(gd["revealed"]), "current_multiplier": new_mult, "balance": u.balance}

@router.post("/mines/cashout")
def mines_cashout(req: MinesCash, db: Session = Depends(get_db), u=Depends(get_current_user)):
    sess = db.query(models.GameSession).filter(
        models.GameSession.id == req.session_id, models.GameSession.user_id == u.id
    ).first()
    if not sess or sess.result != "pending": raise HTTPException(400, "Session yo'q yoki tugagan")
    gd = json.loads(sess.game_data)
    if not gd["revealed"]: raise HTTPException(400, "Hech bo'lmasa 1 katak oching")

    mult = gd["current_multiplier"]
    win = round(sess.bet_amount * mult, 2)
    u.balance += win; u.total_wins += win - sess.bet_amount
    sess.win_amount = win; sess.multiplier = mult; sess.result = "win"
    gd["game_over"] = True; sess.game_data = json.dumps(gd)
    db.commit()
    return {"multiplier": mult, "win": win, "balance": u.balance, "board": gd["board"]}

# ===== APPLE =====
class AppleBet(BaseModel):
    bet: float
    levels: int = 5

class ApplePick(BaseModel):
    session_id: int
    apple_index: int

class AppleCash(BaseModel):
    session_id: int

@router.post("/apple/start")
def apple_start(req: AppleBet, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if req.bet <= 0 or u.balance < req.bet: raise HTTPException(400, "Bet noto'g'ri yoki balans yetarli emas")
    check_ban(u)

    lvs = min(max(req.levels, 3), 8)
    mults = apple_mults(lvs)
    boards = [apple_board(3, 1) for _ in range(lvs)]

    u.balance -= req.bet
    sess = models.GameSession(
        user_id=u.id, game_type=models.GameType.apple_fortune,
        bet_amount=req.bet, result="pending",
        game_data=json.dumps({"levels": lvs, "apples_per_level": 3, "multipliers": mults, "level_boards": boards, "current_level": 0, "current_multiplier": 1.0})
    )
    db.add(sess); db.commit(); db.refresh(sess)
    return {"session_id": sess.id, "levels": lvs, "apples_per_level": 3, "multipliers": mults, "current_level": 0, "balance": u.balance}

@router.post("/apple/pick")
def apple_pick(req: ApplePick, db: Session = Depends(get_db), u=Depends(get_current_user)):
    sess = db.query(models.GameSession).filter(
        models.GameSession.id == req.session_id, models.GameSession.user_id == u.id
    ).first()
    if not sess or sess.result != "pending": raise HTTPException(400, "Session yo'q yoki tugagan")

    gd = json.loads(sess.game_data)
    lv = gd["current_level"]
    if not (0 <= req.apple_index < gd["apples_per_level"]): raise HTTPException(400, "Noto'g'ri olma")

    if gd["level_boards"][lv][req.apple_index] == 1:
        u.total_losses += sess.bet_amount; sess.result = "loss"
        sess.game_data = json.dumps(gd); db.commit()
        return {"bad_apple": True, "apple_index": req.apple_index, "level_board": gd["level_boards"][lv]}

    new_lv = lv + 1
    new_mult = gd["multipliers"][lv]
    gd["current_level"] = new_lv; gd["current_multiplier"] = new_mult
    sess.multiplier = new_mult; sess.game_data = json.dumps(gd)

    if new_lv >= gd["levels"]:
        win = round(sess.bet_amount * new_mult, 2)
        u.balance += win; u.total_wins += win - sess.bet_amount
        sess.win_amount = win; sess.result = "win"; db.commit()
        return {"bad_apple": False, "completed": True, "multiplier": new_mult, "win": win, "balance": u.balance}

    db.commit()
    return {"bad_apple": False, "completed": False, "current_level": new_lv, "current_multiplier": new_mult,
            "next_multiplier": gd["multipliers"][new_lv]}

@router.post("/apple/cashout")
def apple_cashout(req: AppleCash, db: Session = Depends(get_db), u=Depends(get_current_user)):
    sess = db.query(models.GameSession).filter(
        models.GameSession.id == req.session_id, models.GameSession.user_id == u.id
    ).first()
    if not sess or sess.result != "pending": raise HTTPException(400, "Session yo'q yoki tugagan")
    gd = json.loads(sess.game_data)
    if gd["current_level"] == 0: raise HTTPException(400, "Hech bo'lmasa 1 qavatdan o'ting")

    mult = gd["current_multiplier"]
    win = round(sess.bet_amount * mult, 2)
    u.balance += win; u.total_wins += win - sess.bet_amount
    sess.win_amount = win; sess.multiplier = mult; sess.result = "win"
    db.commit()
    return {"multiplier": mult, "win": win, "balance": u.balance}

@router.get("/history")
def history(limit: int = 20, db: Session = Depends(get_db), u=Depends(get_current_user)):
    sessions = db.query(models.GameSession).filter(
        models.GameSession.user_id == u.id
    ).order_by(models.GameSession.created_at.desc()).limit(limit).all()
    return [{"id": s.id, "game_type": s.game_type, "bet": s.bet_amount,
             "win": s.win_amount, "multiplier": s.multiplier, "result": s.result,
             "created_at": s.created_at} for s in sessions]
