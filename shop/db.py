"""SQLite 数据层：建表、种子数据、连接管理。

V1.5 把 V1 中放在内存里的商品、用户、订单迁移到 SQLite。
数据库文件默认位于 shop/data/shop.db，可用 SHOP_DB 环境变量覆盖。
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DB_PATH = Path(__file__).parent / "data" / "shop.db"

PRODUCT_SEED = [
    {"name": "iPhone 17 Pro", "brand": "Apple", "price_cents": 899900, "stock": 12,
     "description": "A19 Pro 芯片，6.3 英寸屏幕，256GB。"},
    {"name": "小米 15", "brand": "Xiaomi", "price_cents": 429900, "stock": 20,
     "description": "骁龙 8 至尊版，徕卡三摄，12GB+256GB。"},
    {"name": "华为 Mate 70", "brand": "Huawei", "price_cents": 549900, "stock": 8,
     "description": "麒麟芯片，鸿蒙系统，12GB+256GB。"},
    {"name": "OPPO Find X8", "brand": "OPPO", "price_cents": 399900, "stock": 15,
     "description": "天玑 9400，哈苏影像，12GB+256GB。"},
    {"name": "vivo X200", "brand": "vivo", "price_cents": 429900, "stock": 10,
     "description": "天玑 9400，蔡司长焦，12GB+256GB。"},
    {"name": "荣耀 Magic7", "brand": "Honor", "price_cents": 449900, "stock": 9,
     "description": "骁龙 8 至尊版，AI 鹰眼相机。"},
    {"name": "三星 Galaxy S25", "brand": "Samsung", "price_cents": 599900, "stock": 6,
     "description": "骁龙 8 至尊版，6.2 英寸直屏。"},
    {"name": "一加 13", "brand": "OnePlus", "price_cents": 429900, "stock": 14,
     "description": "骁龙 8 至尊版，2K 东方屏。"},
]

USER_SEED = [
    {"email": "student@example.com", "password": "Shop@123", "name": "小钟",
     "level": "normal", "role": "user", "active": 1},
    {"email": "vip@example.com", "password": "Vip@123", "name": "会员小钟",
     "level": "vip", "role": "user", "active": 1},
    {"email": "blocked@example.com", "password": "Block@123", "name": "停用账号",
     "level": "normal", "role": "user", "active": 0},
    {"email": "admin@example.com", "password": "Admin@123", "name": "商城管理员",
     "level": "normal", "role": "admin", "active": 1},
]

COUPON_SEED = [
    {"code": "WELCOME10", "kind": "fixed", "value": 1000, "min_spend_cents": 0,
     "max_discount_cents": 1000, "max_uses": 100, "expires_at": None},
    {"code": "SAVE5", "kind": "percent", "value": 5, "min_spend_cents": 300000,
     "max_discount_cents": 50000, "max_uses": 100, "expires_at": None},
    {"code": "VIP20", "kind": "fixed", "value": 2000, "min_spend_cents": 300000,
     "max_discount_cents": 2000, "max_uses": 100, "expires_at": None},
]

_PASSWORD_HASH_CACHE = {}


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _password_hash(password):
    """缓存演示账号的哈希，避免每次 /dev/reset 都重复做密码学计算。"""
    if password not in _PASSWORD_HASH_CACHE:
        _PASSWORD_HASH_CACHE[password] = generate_password_hash(
            password, method="pbkdf2:sha256:120000"
        )
    return _PASSWORD_HASH_CACHE[password]


def get_db():
    if "db" not in g:
        path = current_app.config["DATABASE"]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        g.db = connection
    return g.db


def close_db(_exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _seed(db):
    created_at = now_text()
    for product in PRODUCT_SEED:
        db.execute(
            "INSERT INTO products (name, brand, price_cents, stock, description, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (product["name"], product["brand"], product["price_cents"],
             product["stock"], product["description"], created_at),
        )
    for user in USER_SEED:
        db.execute(
            "INSERT INTO users (email, password_hash, name, level, role, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user["email"], _password_hash(user["password"]), user["name"],
             user["level"], user["role"], user["active"], created_at),
        )
    for coupon in COUPON_SEED:
        db.execute(
            "INSERT INTO coupons (code, kind, value, min_spend_cents, max_discount_cents, "
            "active, used_count, max_uses, expires_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?, ?)",
            (coupon["code"], coupon["kind"], coupon["value"], coupon["min_spend_cents"],
             coupon["max_discount_cents"], coupon["max_uses"], coupon["expires_at"], created_at),
        )


def reset_db():
    """清空业务表并恢复演示数据；保留表结构。"""
    db = get_db()
    for table in (
        "coupon_redemptions", "order_status_logs", "order_items", "orders",
        "coupons", "products", "users",
    ):
        db.execute(f"DELETE FROM {table}")
    try:
        db.execute("DELETE FROM sqlite_sequence")
    except sqlite3.OperationalError:
        pass
    _seed(db)


def init_db():
    db = get_db()
    db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    count = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if count == 0:
        _seed(db)


def init_app(app):
    app.config.setdefault("DATABASE", os.environ.get("SHOP_DB", str(DEFAULT_DB_PATH)))
    app.config.setdefault("DEMO_MODE", True)
    app.teardown_appcontext(close_db)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        init_db()
