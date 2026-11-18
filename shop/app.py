#!/usr/bin/env python3
"""手机商城练习站，给 Selenium 页面测试用。

启动：
    python shop/app.py --port 9500
"""

import argparse
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from flask import Flask, redirect, render_template, request, session, url_for, flash

app = Flask(__name__)
app.secret_key = "phone-mall-practice-secret"

PRODUCTS_SEED = [
    {"id": 1, "name": "iPhone 17 Pro", "brand": "Apple", "price": "8999.00", "stock": 12,
     "desc": "A19 Pro 芯片，6.3 英寸屏幕，256GB。"},
    {"id": 2, "name": "小米 15", "brand": "Xiaomi", "price": "4299.00", "stock": 20,
     "desc": "骁龙 8 至尊版，徕卡三摄，12GB+256GB。"},
    {"id": 3, "name": "华为 Mate 70", "brand": "Huawei", "price": "5499.00", "stock": 8,
     "desc": "麒麟芯片，鸿蒙系统，12GB+256GB。"},
    {"id": 4, "name": "OPPO Find X8", "brand": "OPPO", "price": "3999.00", "stock": 15,
     "desc": "天玑 9400，哈苏影像，12GB+256GB。"},
    {"id": 5, "name": "vivo X200", "brand": "vivo", "price": "4299.00", "stock": 10,
     "desc": "天玑 9400，蔡司长焦，12GB+256GB。"},
    {"id": 6, "name": "荣耀 Magic7", "brand": "Honor", "price": "4499.00", "stock": 9,
     "desc": "骁龙 8 至尊版，AI 鹰眼相机。"},
    {"id": 7, "name": "三星 Galaxy S25", "brand": "Samsung", "price": "5999.00", "stock": 6,
     "desc": "骁龙 8 至尊版，6.2 英寸直屏。"},
    {"id": 8, "name": "一加 13", "brand": "OnePlus", "price": "4299.00", "stock": 14,
     "desc": "骁龙 8 至尊版，2K 东方屏。"},
]

USERS = {
    "student@example.com": {"password": "Shop@123", "name": "小钟", "level": "normal", "active": True},
    "vip@example.com": {"password": "Vip@123", "name": "会员小钟", "level": "vip", "active": True},
    "blocked@example.com": {"password": "Block@123", "name": "停用账号", "level": "normal", "active": False},
}

PRODUCTS = []
ORDERS = []
SEQ = {"n": 0}


def reset_data():
    PRODUCTS.clear()
    for p in PRODUCTS_SEED:
        PRODUCTS.append(dict(p))
    ORDERS.clear()
    SEQ["n"] = 0


reset_data()


def money(value):
    return str(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def find_product(pid):
    return next((p for p in PRODUCTS if p["id"] == pid), None)


def cart_items():
    cart = session.get("cart", {})
    items = []
    subtotal = Decimal("0.00")
    for pid_text, qty in cart.items():
        p = find_product(int(pid_text))
        if not p or qty <= 0:
            continue
        line = Decimal(p["price"]) * qty
        subtotal += line
        items.append({"product": p, "qty": qty, "line_total": money(line)})
    return items, subtotal


def current_user():
    email = session.get("email")
    if not email:
        return None
    user = USERS.get(email)
    if not user:
        return None
    return {"email": email, **user}


def discount_for(user, subtotal):
    if user and user["level"] == "vip":
        return (subtotal * Decimal("0.05")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal("0.00")


def cart_count():
    return sum(session.get("cart", {}).values())


app.jinja_env.globals.update(cart_count=cart_count, current_user=current_user)


@app.route("/api/health")
def health():
    return {"status": "up", "products": len(PRODUCTS), "orders": len(ORDERS)}


@app.route("/test/reset")
def test_reset():
    reset_data()
    session.clear()
    return {"status": "reset"}


@app.route("/")
def index():
    keyword = request.args.get("q", "").strip()
    if keyword:
        lowered = keyword.lower()
        items = [p for p in PRODUCTS if lowered in p["name"].lower() or lowered in p["brand"].lower()]
    else:
        items = list(PRODUCTS)
    return render_template("index.html", products=items, keyword=keyword)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        if not email:
            flash("请输入邮箱")
            return render_template("login.html"), 200
        if not password:
            flash("请输入密码")
            return render_template("login.html"), 200
        user = USERS.get(email)
        if not user or user["password"] != password:
            flash("邮箱或密码错误")
            return render_template("login.html"), 200
        if not user["active"]:
            flash("账号已被停用")
            return render_template("login.html"), 200
        session["email"] = email
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("email", None)
    session.pop("cart", None)
    return redirect(url_for("index"))


@app.route("/search")
def search():
    return redirect(url_for("index", q=request.args.get("q", "")))


@app.route("/product/<int:pid>")
def product_detail(pid):
    p = find_product(pid)
    if not p:
        return "商品不存在", 404
    return render_template("product.html", product=p)


@app.route("/cart")
def cart():
    items, subtotal = cart_items()
    return render_template("cart.html", items=items, subtotal=money(subtotal))


@app.route("/cart/add/<int:pid>", methods=["POST"])
def cart_add(pid):
    p = find_product(pid)
    if not p:
        return "商品不存在", 404
    qty = int(request.form.get("qty", 1))
    if qty < 1:
        qty = 1
    cart = session.setdefault("cart", {})
    cart[str(pid)] = cart.get(str(pid), 0) + qty
    session["cart"] = cart
    flash(f"已加入购物车：{p['name']} × {qty}")
    return redirect(request.form.get("next") or url_for("cart"))


@app.route("/cart/update/<int:pid>", methods=["POST"])
def cart_update(pid):
    qty = int(request.form.get("qty", 1))
    cart = session.setdefault("cart", {})
    if qty <= 0:
        cart.pop(str(pid), None)
    else:
        cart[str(pid)] = qty
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:pid>", methods=["POST"])
def cart_remove(pid):
    cart = session.get("cart", {})
    cart.pop(str(pid), None)
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    user = current_user()
    if not user:
        return redirect(url_for("login", next="/checkout"))
    items, subtotal = cart_items()
    if not items:
        flash("购物车是空的，先去挑手机")
        return redirect(url_for("cart"))
    discount = discount_for(user, subtotal)
    total = subtotal - discount
    if request.method == "POST":
        receiver = request.form.get("receiver", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        errors = []
        if len(receiver) < 2:
            errors.append("收货人至少 2 个字")
        if not re.match(r"^1[3-9]\d{9}$", phone):
            errors.append("手机号格式不对")
        if len(address) < 5:
            errors.append("详细地址至少 5 个字")
        if errors:
            for e in errors:
                flash(e)
            return render_template("checkout.html", items=items, subtotal=money(subtotal),
                                   discount=money(discount), total=money(total), user=user)
        SEQ["n"] += 1
        order_no = "ORD" + datetime.now().strftime("%Y%m%d%H%M%S") + f"{SEQ['n']:04d}"
        order = {
            "order_no": order_no,
            "email": user["email"],
            "lines": [{"name": i["product"]["name"], "price": i["product"]["price"],
                      "qty": i["qty"], "line_total": i["line_total"], "pid": i["product"]["id"]} for i in items],
            "subtotal": money(subtotal),
            "discount": money(discount),
            "total": money(total),
            "receiver": receiver,
            "phone": phone,
            "address": address,
            "status": "pending",
            "payment_method": None,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "paid_at": None,
        }
        ORDERS.append(order)
        session["cart"] = {}
        return redirect(url_for("order_detail", order_no=order_no))
    return render_template("checkout.html", items=items, subtotal=money(subtotal),
                           discount=money(discount), total=money(total), user=user)


def get_order(order_no):
    return next((o for o in ORDERS if o["order_no"] == order_no), None)


@app.route("/order/<order_no>")
def order_detail(order_no):
    user = current_user()
    if not user:
        return redirect(url_for("login", next=request.path))
    order = get_order(order_no)
    if not order:
        return "订单不存在", 404
    if order["email"] != user["email"]:
        return "无权查看该订单", 403
    return render_template("order.html", order=order)


@app.route("/pay/<order_no>", methods=["GET", "POST"])
def pay(order_no):
    user = current_user()
    if not user:
        return redirect(url_for("login", next=request.path))
    order = get_order(order_no)
    if not order:
        return "订单不存在", 404
    if order["email"] != user["email"]:
        return "无权支付该订单", 403
    if order["status"] == "paid":
        flash("订单已支付，不用重复付款")
        return render_template("pay.html", order=order)
    if request.method == "POST":
        method = request.form.get("method", "")
        if method not in ("alipay", "wechat", "card"):
            flash("请选择支付方式")
            return render_template("pay.html", order=order)
        order["status"] = "paid"
        order["payment_method"] = method
        order["paid_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in order["lines"]:
            p = find_product(item["pid"])
            if p:
                p["stock"] = max(0, p["stock"] - item["qty"])
        flash("支付成功")
        return redirect(url_for("order_detail", order_no=order_no))
    return render_template("pay.html", order=order)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9500)
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port, debug=False)
