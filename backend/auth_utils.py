from datetime import datetime, timedelta
from typing import Optional
import jwt, bcrypt, random, string, os

SECRET_KEY = os.getenv("SECRET_KEY", "95951223sabriya-95951223sabriya")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

def generate_login(telegram_id: str) -> str:
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"user{str(telegram_id)[-4:]}{suffix}"

def generate_password(length: int = 10) -> str:
    chars = string.ascii_letters + string.digits + "!@#"
    return ''.join(random.choices(chars, k=length))

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None
