# auth_service.py — сервис аутентификации с SQLite и таблицей ролей
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Table, MetaData, ForeignKey, select
from sqlalchemy.orm import sessionmaker
import hashlib
import os
from pathlib import Path
import logging

# ----------------------- НАСТРОЙКА ЛОГИРОВАНИЯ -----------------------
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "authorization.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info("Сервис authorization запущен!")

# ----------------------- КОНФИГУРАЦИЯ -----------------------
app = FastAPI()

# Настройка базы SQLite
DATABASE_URL = "sqlite:////app/data_base/authorization.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
metadata = MetaData()

roles_table = Table(
    "roles",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, unique=True)
)

users_table = Table(
    "users",
    metadata,
    Column("login", String, primary_key=True),
    Column("password_hash", String),
    Column("role_id", Integer, ForeignKey("roles.id"))
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------------- ЭНДПОИНТЫ -----------------------
class AuthRequest(BaseModel):
    login: str
    password: str

@app.post("/verify")
def verify_user(auth: AuthRequest, db=Depends(get_db)):
    logger.info(f"🔐 Запрос на авторизацию: {auth.login}")

    query = select(users_table.c.login, users_table.c.password_hash, roles_table.c.name.label("role"))\
        .join(roles_table, users_table.c.role_id == roles_table.c.id)\
        .where(users_table.c.login == auth.login)

    user = db.execute(query).fetchone()
    if not user:
        logger.warning(f"⚠️ Пользователь не найден: {auth.login}")
        raise HTTPException(status_code=401, detail="User not found")

    hashed_input = hashlib.sha256(auth.password.encode()).hexdigest()
    if hashed_input != user.password_hash:
        logger.warning(f"❌ Неверный пароль: {auth.login}")
        raise HTTPException(status_code=403, detail="Invalid credentials")

    logger.info(f"✅ Авторизация успешна: {auth.login}, роль: {user.role}")
    return {"token": f"demo-token-{auth.login}", "role": user.role}