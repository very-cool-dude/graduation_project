# init_db.py — инициализация базы authorization.db с таблицами users и roles
import hashlib
from sqlalchemy import create_engine, Column, String, Integer, Table, MetaData
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data_base/authorization.db')}"

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
    Column("role_id", Integer)
)

metadata.create_all(engine)

with engine.connect() as conn:
    # Очистим старые данные (если нужно)
    conn.execute(roles_table.delete())
    conn.execute(users_table.delete())

    # Добавим роли
    conn.execute(roles_table.insert(), [
        {"id": 1, "name": "admin"},
        {"id": 2, "name": "operator"}
    ])

    # Добавим пользователей
    conn.execute(users_table.insert(), [
        {
            "login": "admin",
            "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
            "role_id": 1
        },
        {
            "login": "operator",
            "password_hash": hashlib.sha256("op123".encode()).hexdigest(),
            "role_id": 2
        }
    ])

    conn.commit()

print("База данных инициализирована.")