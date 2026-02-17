from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class UserStatus(str, enum.Enum):
    active = "active"
    blocked = "blocked"
    frozen = "frozen"

class TransactionType(str, enum.Enum):
    deposit = "deposit"
    withdrawal = "withdrawal"
    win = "win"
    loss = "loss"
    promo = "promo"

class TransactionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class GameType(str, enum.Enum):
    aviator = "aviator"
    apple_fortune = "apple_fortune"
    mines = "mines"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    login = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    balance = Column(Float, default=0.0)
    total_wins = Column(Float, default=0.0)
    total_losses = Column(Float, default=0.0)
    status = Column(Enum(UserStatus), default=UserStatus.active)
    games_banned_until = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    transactions = relationship("Transaction", back_populates="user")
    game_sessions = relationship("GameSession", back_populates="user")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(Enum(TransactionType))
    amount = Column(Float)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.pending)
    description = Column(String, nullable=True)
    admin_note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    user = relationship("User", back_populates="transactions")

class GameSession(Base):
    __tablename__ = "game_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    game_type = Column(Enum(GameType))
    bet_amount = Column(Float)
    win_amount = Column(Float, default=0.0)
    multiplier = Column(Float, default=1.0)
    result = Column(String)
    game_data = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="game_sessions")

class PromoCode(Base):
    __tablename__ = "promo_codes"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False)
    bonus_type = Column(String)
    bonus_value = Column(Float)
    max_uses = Column(Integer, nullable=True)
    current_uses = Column(Integer, default=0)
    min_deposit = Column(Float, default=0.0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    require_subscription = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    uses = relationship("PromoCodeUse", back_populates="promo")

class PromoCodeUse(Base):
    __tablename__ = "promo_code_uses"
    id = Column(Integer, primary_key=True, index=True)
    promo_id = Column(Integer, ForeignKey("promo_codes.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    used_at = Column(DateTime(timezone=True), server_default=func.now())
    promo = relationship("PromoCode", back_populates="uses")

class RequiredChannel(Base):
    __tablename__ = "required_channels"
    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(String, nullable=False)
    channel_name = Column(String)
    channel_url = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Advertisement(Base):
    __tablename__ = "advertisements"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String)
    title = Column(String)
    content = Column(Text)
    image_url = Column(String, nullable=True)
    link = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    show_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
