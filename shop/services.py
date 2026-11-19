"""商城业务逻辑：商品、购物车、计价、订单状态机、优惠券与后台统计。

金额在数据库中统一保存为整数分，展示层通过 money() 转成两位小数字符串。
"""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import session
from werkzeug.security import check_password_hash

try:
    from .db import get_db, now_text
except ImportError:  # 兼容 python shop/app.py 的脚本运行方式
    from db import get_db, now_text

STATUS_LABELS = {
    "pending": "待支付",
    "paid": "已支付",
    "shipped": "已发货",
    "completed": "已完成",
    "cancelled": "已取消",
    "refunding": "退款审核中",
    "refunded": "已退款",
}

STATUS_FLOW = {
    "pending": ("待支付", "可以支付；支付前可取消并释放库存"),
    "paid": ("已支付", "仓库可以发货；用户可发起退款申请"),
    "shipped": ("已发货", "用户可确认收货；用户可发起退款申请"),
    "completed": ("已完成", "订单完成，库存不再释放"),
    "cancelled": ("已取消", "订单已取消，库存已释放"),
    "refunding": ("退款审核中", "等待管理员审核退款"),
    "refunded": ("已退款", "退款完成，库存已释放"),
}

ACTION_RULES = {
    "pay": {"from": ("pending",), "to": "paid", "actor": "user", "note": "用户支付"},
    "cancel": {"from": ("pending",), "to": "cancelled", "actor": "user", "note": "用户取消订单"},
    "request_refund": {"from": ("paid", "shipped"), "to": "refunding", "actor": "user", "note": "用户申请退款"},
    "ship": {"from": ("paid",), "to": "shipped", "actor": "admin", "note": "管理员发货"},
    "complete": {"from": ("shipped",), "to": "completed", "actor": "user", "note": "用户确认收货"},
    "refund": {"from": ("refunding", "paid", "shipped"), "to": "refunded", "actor": "admin", "note": "管理员退款"},
    "admin_cancel": {"from": ("pending",), "to": "cancelled", "actor": "admin", "note": "管理员取消订单"},
}


class BusinessError(Exception):
    """可以直接展示给用户的业务错误。"""


def money(cents):
    cents = int(cents or 0)
    return str((Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_cents(text):
    try:
        value = Decimal(str(text)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception as exc:
        raise BusinessError("金额格式不正确") from exc
    if value < 0:
        raise BusinessError("金额不能为负数")
    return int(value * 100)


def now_text_value():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def product_view(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "brand": row["brand"],
        "price": money(row["price_cents"]),
        "price_cents": row["price_cents"],
        "stock": row["stock"],
        "desc": row["description"],
        "active": bool(row["active"]),
    }


def user_view(row):
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "level": row["level"],
        "role": row["role"],
        "active": bool(row["active"]),
    }


def get_product(pid):
    row = get_db().execute(
        "SELECT * FROM products WHERE id = ? AND active = 1", (pid,)
    ).fetchone()
    return product_view(row) if row else None


def list_products(keyword=""):
    db = get_db()
    keyword = (keyword or "").strip()
    if keyword:
        pattern = f"%{keyword}%"
        rows = db.execute(
            "SELECT * FROM products WHERE active = 1 AND (name LIKE ? OR brand LIKE ?) "
            "ORDER BY id", (pattern, pattern)
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM products WHERE active = 1 ORDER BY id").fetchall()
    return [product_view(row) for row in rows]


def get_user_by_email(email):
    if not email:
        return None
    row = get_db().execute(
        "SELECT * FROM users WHERE email = ?", (email.strip().casefold(),)
    ).fetchone()
    return user_view(row) if row else None


def get_user_row_by_email(email):
    if not email:
        return None
    return get_db().execute(
        "SELECT * FROM users WHERE email = ?", (email.strip().casefold(),)
    ).fetchone()


def authenticate(email, password):
    row = get_user_row_by_email(email)
    if not row or not check_password_hash(row["password_hash"], password):
        return None, "邮箱或密码错误"
    if not row["active"]:
        return None, "账号已被停用"
    return user_view(row), None


def current_user():
    email = session.get("email")
    if not email:
        return None
    user = get_user_by_email(email)
    if not user or not user["active"]:
        return None
    return user


def cart_items():
    db = get_db()
    cart = session.get("cart", {})
    items = []
    subtotal = 0
    for pid_text, qty in cart.items():
        try:
            pid = int(pid_text)
            qty = int(qty)
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        row = db.execute(
            "SELECT * FROM products WHERE id = ? AND active = 1", (pid,)
        ).fetchone()
        if not row:
            continue
        product = product_view(row)
        line_total = product["price_cents"] * qty
        subtotal += line_total
        items.append({
            "product": product,
            "qty": qty,
            "line_total": money(line_total),
            "line_total_cents": line_total,
            "stock_short": qty > product["stock"],
        })
    return items, subtotal


def cart_count():
    return sum(int(qty) for qty in session.get("cart", {}).values() if str(qty).isdigit())


def cart_stock_problems(items):
    return [
        f"{item['product']['name']} 库存只剩 {item['product']['stock']} 台"
        for item in items if item["stock_short"]
    ]


def vip_discount_for(user, subtotal_cents):
    if user and user["level"] == "vip":
        return int((Decimal(subtotal_cents) * Decimal("0.05")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        ))
    return 0


def get_coupon(code):
    if not code:
        return None
    row = get_db().execute(
        "SELECT * FROM coupons WHERE code = ?", (str(code).strip().upper(),)
    ).fetchone()
    return dict(row) if row else None


def coupon_error(coupon, subtotal_cents):
    if not coupon:
        return "优惠券不存在"
    if not coupon["active"]:
        return "优惠券已停用"
    if coupon["expires_at"] and coupon["expires_at"] <= now_text_value():
        return "优惠券已过期"
    if coupon["used_count"] >= (coupon["max_uses"] if coupon["max_uses"] is not None else 10**9):
        return "优惠券已领完"
    if subtotal_cents < coupon["min_spend_cents"]:
        return f"订单满 {money(coupon['min_spend_cents'])} 元才可使用"
    return None


def coupon_discount(coupon, amount_cents):
    if not coupon:
        return 0
    if coupon["kind"] == "fixed":
        discount = int(coupon["value"])
    else:
        discount = int((Decimal(amount_cents) * Decimal(coupon["value"]) / Decimal(100)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        ))
    if coupon["max_discount_cents"]:
        discount = min(discount, int(coupon["max_discount_cents"]))
    return max(0, min(discount, amount_cents))


def calculate_total(user, subtotal_cents, coupon=None):
    vip_discount = vip_discount_for(user, subtotal_cents)
    after_vip = subtotal_cents - vip_discount
    coupon_discount_value = coupon_discount(coupon, after_vip) if coupon else 0
    total = max(0, after_vip - coupon_discount_value)
    return {
        "subtotal_cents": subtotal_cents,
        "vip_discount_cents": vip_discount,
        "coupon_discount_cents": coupon_discount_value,
        "total_cents": total,
        "subtotal": money(subtotal_cents),
        "discount": money(vip_discount),
        "coupon_discount": money(coupon_discount_value),
        "total": money(total),
    }


def _new_order_no(db, timestamp):
    next_id = db.execute("SELECT COALESCE(MAX(id), 0) + 1 AS n FROM orders").fetchone()["n"]
    return f"ORD{timestamp}{int(next_id):04d}"


def create_order(user, items, receiver, phone, address, coupon_code=None):
    """下单即锁定库存，订单取消/退款时释放库存，避免并发超卖。"""
    if not items:
        raise BusinessError("购物车是空的")
    db = get_db()
    subtotal_cents = sum(item["line_total_cents"] for item in items)
    coupon = get_coupon(coupon_code)
    if coupon_code and not coupon:
        raise BusinessError("优惠券不存在")
    if coupon:
        error = coupon_error(coupon, subtotal_cents)
        if error:
            raise BusinessError(error)
    amounts = calculate_total(user, subtotal_cents, coupon)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    try:
        db.execute("BEGIN IMMEDIATE")
        for item in items:
            row = db.execute(
                "SELECT stock, name FROM products WHERE id = ? AND active = 1",
                (item["product"]["id"],),
            ).fetchone()
            if not row:
                raise BusinessError(f"商品已下架：{item['product']['name']}")
            if row["stock"] < item["qty"]:
                raise BusinessError(f"库存不足：{row['name']} 只剩 {row['stock']} 台")
        for item in items:
            updated = db.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                (item["qty"], item["product"]["id"], item["qty"]),
            )
            if updated.rowcount != 1:
                raise BusinessError(f"库存不足：{item['product']['name']}")
        order_no = _new_order_no(db, timestamp)
        cursor = db.execute(
            "INSERT INTO orders (order_no, user_id, subtotal_cents, vip_discount_cents, "
            "coupon_discount_cents, total_cents, receiver, phone, address, status, "
            "coupon_code, stock_restored, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, 0, ?)",
            (order_no, user["id"], amounts["subtotal_cents"], amounts["vip_discount_cents"],
             amounts["coupon_discount_cents"], amounts["total_cents"], receiver, phone,
             address, coupon["code"] if coupon else None, now_text()),
        )
        order_id = cursor.lastrowid
        for item in items:
            product = item["product"]
            db.execute(
                "INSERT INTO order_items (order_id, product_id, product_name, price_cents, qty, line_total_cents) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (order_id, product["id"], product["name"], product["price_cents"],
                 item["qty"], item["line_total_cents"]),
            )
        db.execute(
            "INSERT INTO order_status_logs (order_id, from_status, to_status, actor, note, created_at) "
            "VALUES (?, NULL, 'pending', 'user', '用户提交订单', ?)",
            (order_id, now_text()),
        )
        if coupon:
            updated = db.execute(
                "UPDATE coupons SET used_count = used_count + 1 WHERE id = ? "
                "AND (max_uses IS NULL OR used_count < max_uses)",
                (coupon["id"],),
            )
            if updated.rowcount != 1:
                raise BusinessError("优惠券已领完")
            db.execute(
                "INSERT INTO coupon_redemptions (coupon_id, order_id, user_id, discount_cents, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (coupon["id"], order_id, user["id"], amounts["coupon_discount_cents"], now_text()),
            )
        db.execute("COMMIT")
        return order_no
    except Exception:
        db.execute("ROLLBACK")
        raise


def _order_row(order_no):
    return get_db().execute(
        "SELECT o.*, u.email AS user_email, u.name AS user_name "
        "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.order_no = ?",
        (order_no,),
    ).fetchone()


def order_view(row):
    db = get_db()
    items = db.execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (row["id"],)
    ).fetchall()
    logs = db.execute(
        "SELECT * FROM order_status_logs WHERE order_id = ? ORDER BY id", (row["id"],)
    ).fetchall()
    order = {
        "order_no": row["order_no"],
        "user_id": row["user_id"],
        "email": row["user_email"],
        "user_name": row["user_name"],
        "subtotal": money(row["subtotal_cents"]),
        "discount": money(row["vip_discount_cents"]),
        "coupon_discount": money(row["coupon_discount_cents"]),
        "total": money(row["total_cents"]),
        "receiver": row["receiver"],
        "phone": row["phone"],
        "address": row["address"],
        "status": row["status"],
        "status_label": STATUS_LABELS.get(row["status"], row["status"]),
        "payment_method": row["payment_method"],
        "coupon_code": row["coupon_code"],
        "created_at": row["created_at"],
        "paid_at": row["paid_at"],
        "shipped_at": row["shipped_at"],
        "completed_at": row["completed_at"],
        "cancelled_at": row["cancelled_at"],
        "refunded_at": row["refunded_at"],
        "stock_restored": bool(row["stock_restored"]),
        "lines": [{
            "pid": item["product_id"],
            "name": item["product_name"],
            "price": money(item["price_cents"]),
            "qty": item["qty"],
            "line_total": money(item["line_total_cents"]),
        } for item in items],
        "logs": [{
            "from_status": log["from_status"],
            "from_label": STATUS_LABELS.get(log["from_status"], log["from_status"] or ""),
            "to_status": log["to_status"],
            "to_label": STATUS_LABELS.get(log["to_status"], log["to_status"]),
            "actor": log["actor"],
            "note": log["note"],
            "created_at": log["created_at"],
        } for log in logs],
    }
    return order


def get_order(order_no):
    row = _order_row(order_no)
    return order_view(row) if row else None


def list_orders(status=None, user_id=None):
    sql = (
        "SELECT o.*, u.email AS user_email, u.name AS user_name "
        "FROM orders o JOIN users u ON o.user_id = u.id "
    )
    params = []
    clauses = []
    if status:
        clauses.append("o.status = ?")
        params.append(status)
    if user_id:
        clauses.append("o.user_id = ?")
        params.append(user_id)
    if clauses:
        sql += "WHERE " + " AND ".join(clauses) + " "
    sql += "ORDER BY o.id DESC"
    rows = get_db().execute(sql, params).fetchall()
    orders = []
    for row in rows:
        orders.append({
            "order_no": row["order_no"],
            "email": row["user_email"],
            "user_name": row["user_name"],
            "total": money(row["total_cents"]),
            "status": row["status"],
            "status_label": STATUS_LABELS.get(row["status"], row["status"]),
            "created_at": row["created_at"],
            "item_count": get_db().execute(
                "SELECT COALESCE(SUM(qty), 0) AS n FROM order_items WHERE order_id = ?",
                (row["id"],),
            ).fetchone()["n"],
        })
    return orders


def transition_order(order_no, action, actor=None, note=None):
    rule = ACTION_RULES.get(action)
    if not rule:
        raise BusinessError("不支持的订单操作")
    db = get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        row = _order_row(order_no)
        if not row:
            raise BusinessError("订单不存在")
        if row["status"] not in rule["from"]:
            raise BusinessError(f"订单当前状态为「{STATUS_LABELS.get(row['status'], row['status'])}」，不能执行该操作")
        target = rule["to"]
        timestamp_column = {
            "paid": "paid_at",
            "shipped": "shipped_at",
            "completed": "completed_at",
            "cancelled": "cancelled_at",
            "refunded": "refunded_at",
        }.get(target)
        now = now_text()
        stock_restored = row["stock_restored"]
        if target in ("cancelled", "refunded") and not stock_restored:
            for item in db.execute(
                "SELECT product_id, qty FROM order_items WHERE order_id = ?", (row["id"],)
            ).fetchall():
                db.execute(
                    "UPDATE products SET stock = stock + ? WHERE id = ?",
                    (item["qty"], item["product_id"]),
                )
            stock_restored = 1
        if timestamp_column:
            db.execute(
                f"UPDATE orders SET status = ?, {timestamp_column} = ?, stock_restored = ? WHERE id = ?",
                (target, now, stock_restored, row["id"]),
            )
        else:
            db.execute(
                "UPDATE orders SET status = ?, stock_restored = ? WHERE id = ?",
                (target, stock_restored, row["id"]),
            )
        db.execute(
            "INSERT INTO order_status_logs (order_id, from_status, to_status, actor, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (row["id"], row["status"], target, actor or rule["actor"],
             note or rule["note"], now),
        )
        db.execute("COMMIT")
        return target
    except Exception:
        db.execute("ROLLBACK")
        raise


def pay_order(order_no, method):
    if method not in ("alipay", "wechat", "card"):
        raise BusinessError("请选择支付方式")
    db = get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        row = _order_row(order_no)
        if not row:
            raise BusinessError("订单不存在")
        if row["status"] != "pending":
            raise BusinessError(
                f"订单当前状态为「{STATUS_LABELS.get(row['status'], row['status'])}」，不能支付"
            )
        paid_at = now_text()
        db.execute(
            "UPDATE orders SET status = 'paid', payment_method = ?, paid_at = ? WHERE id = ?",
            (method, paid_at, row["id"]),
        )
        db.execute(
            "INSERT INTO order_status_logs (order_id, from_status, to_status, actor, note, created_at) "
            "VALUES (?, 'pending', 'paid', 'user', '用户完成模拟支付', ?)",
            (row["id"], paid_at),
        )
        db.execute("COMMIT")
        return "paid"
    except Exception:
        db.execute("ROLLBACK")
        raise


def admin_stats():
    db = get_db()
    total_orders = db.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
    revenue = db.execute(
        "SELECT COALESCE(SUM(total_cents), 0) AS n FROM orders "
        "WHERE status IN ('paid', 'shipped', 'completed')"
    ).fetchone()["n"]
    users = db.execute("SELECT COUNT(*) AS n FROM users WHERE active = 1").fetchone()["n"]
    products = db.execute("SELECT COUNT(*) AS n FROM products WHERE active = 1").fetchone()["n"]
    low_stock = db.execute(
        "SELECT COUNT(*) AS n FROM products WHERE active = 1 AND stock <= 3"
    ).fetchone()["n"]
    pending = db.execute(
        "SELECT COUNT(*) AS n FROM orders WHERE status = 'pending'"
    ).fetchone()["n"]
    refunding = db.execute(
        "SELECT COUNT(*) AS n FROM orders WHERE status = 'refunding'"
    ).fetchone()["n"]
    return {
        "total_orders": total_orders,
        "revenue": money(revenue),
        "users": users,
        "products": products,
        "low_stock": low_stock,
        "pending": pending,
        "refunding": refunding,
    }


def list_users():
    rows = get_db().execute("SELECT * FROM users ORDER BY id").fetchall()
    return [user_view(row) for row in rows]


def list_products_admin():
    rows = get_db().execute("SELECT * FROM products ORDER BY id").fetchall()
    return [product_view(row) for row in rows]


def list_coupons():
    rows = get_db().execute("SELECT * FROM coupons ORDER BY id").fetchall()
    return [{
        **dict(row),
        "value_label": money(row["value"]) if row["kind"] == "fixed" else f"{row['value']}%",
        "min_spend": money(row["min_spend_cents"]),
    } for row in rows]


def create_coupon(code, kind, value, min_spend, max_discount=None, max_uses=None, expires_at=None):
    code = (code or "").strip().upper()
    if not code:
        raise BusinessError("请输入优惠券编码")
    if kind not in ("fixed", "percent"):
        raise BusinessError("优惠券类型不正确")
    if kind == "fixed":
        value_cents = parse_cents(value)
        if value_cents <= 0:
            raise BusinessError("优惠金额必须大于 0")
    else:
        try:
            percent = int(value)
        except Exception as exc:
            raise BusinessError("折扣百分比必须是整数") from exc
        if not 1 <= percent <= 99:
            raise BusinessError("折扣百分比需在 1 到 99 之间")
        value_cents = percent
    min_spend_cents = parse_cents(min_spend or "0")
    max_discount_cents = parse_cents(max_discount) if max_discount else None
    try:
        max_uses_value = int(max_uses) if max_uses else None
    except Exception as exc:
        raise BusinessError("使用次数必须是整数") from exc
    if get_coupon(code):
        raise BusinessError("优惠券编码已存在")
    db = get_db()
    try:
        db.execute(
            "INSERT INTO coupons (code, kind, value, min_spend_cents, max_discount_cents, "
            "active, used_count, max_uses, expires_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?, ?)",
            (code, kind, value_cents, min_spend_cents, max_discount_cents,
             max_uses_value, expires_at or None, now_text()),
        )
    except Exception as exc:
        raise BusinessError("优惠券创建失败，请检查编码是否重复") from exc


def update_product_stock(pid, stock):
    try:
        stock = int(stock)
    except Exception as exc:
        raise BusinessError("库存必须是整数") from exc
    if stock < 0:
        raise BusinessError("库存不能为负数")
    db = get_db()
    updated = db.execute(
        "UPDATE products SET stock = ? WHERE id = ? AND active = 1", (stock, pid)
    )
    if updated.rowcount != 1:
        raise BusinessError("商品不存在")


def toggle_user_active(user_id):
    db = get_db()
    row = db.execute("SELECT active, email FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise BusinessError("用户不存在")
    if row["email"] == "admin@example.com":
        raise BusinessError("不能停用管理员账号")
    db.execute("UPDATE users SET active = ? WHERE id = ?", (0 if row["active"] else 1, user_id))
    return not bool(row["active"])
