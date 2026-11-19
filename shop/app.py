"""青禾手机商城 · Flask Web 应用（V1.5）。

启动：
    python shop/app.py --port 9500
"""

import argparse
import os
import re
import secrets
import sys
import time
from pathlib import Path

from flask import (
    Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for,
)

try:  # 以 python shop/app.py 启动时使用同目录导入
    from .db import get_db, init_app as init_db_app, reset_db
    from .services import (
        BusinessError, admin_stats, authenticate, calculate_total, cart_count, cart_items,
        cart_stock_problems, coupon_error, create_coupon, create_order, current_user,
        get_coupon, get_order, get_product, list_coupons, list_orders, list_products,
        list_products_admin, list_users, money, pay_order, toggle_user_active,
        transition_order, update_product_stock,
    )
except ImportError:  # pragma: no cover - 脚本运行的兼容分支
    from db import get_db, init_app as init_db_app, reset_db
    from services import (
        BusinessError, admin_stats, authenticate, calculate_total, cart_count, cart_items,
        cart_stock_problems, coupon_error, create_coupon, create_order, current_user,
        get_coupon, get_order, get_product, list_coupons, list_orders, list_products,
        list_products_admin, list_users, money, pay_order, toggle_user_active,
        transition_order, update_product_stock,
    )

LOGIN_FAILS = {}
LOGIN_WINDOW_SECONDS = 600
LOGIN_MAX_FAILS = 10


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SHOP_SECRET_KEY", "phone-mall-practice-secret-v15"),
        DATABASE=os.environ.get("SHOP_DB", str(Path(__file__).parent / "data" / "shop.db")),
        DEMO_MODE=os.environ.get("SHOP_DEMO", "1") == "1",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SHOP_COOKIE_SECURE", "0") == "1",
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    init_db_app(app)

    def csrf_token():
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token

    def login_key(email):
        return (request.remote_addr or "", (email or "").strip().casefold())

    def login_is_blocked(key):
        record = LOGIN_FAILS.get(key)
        if not record:
            return False
        first_at, count = record
        if time.monotonic() - first_at > LOGIN_WINDOW_SECONDS:
            LOGIN_FAILS.pop(key, None)
            return False
        return count >= LOGIN_MAX_FAILS

    def login_record_fail(key):
        first_at, count = LOGIN_FAILS.get(key, (time.monotonic(), 0))
        LOGIN_FAILS[key] = (first_at, count + 1)

    def safe_next(target):
        if target and target.startswith("/") and not target.startswith("//"):
            return target
        return url_for("index")

    def admin_required():
        user = current_user()
        if not user:
            return None, redirect(url_for("login", next=request.path))
        if user["role"] != "admin":
            abort(403, "无权访问管理后台")
        return user, None

    @app.before_request
    def csrf_protect():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            expected = session.get("csrf_token")
            supplied = request.form.get("csrf_token")
            if not expected or not supplied or not secrets.compare_digest(expected, supplied):
                abort(400, "CSRF 校验失败，请返回页面刷新后重试")

    @app.context_processor
    def inject_globals():
        return {
            "csrf_token": csrf_token,
            "current_user": current_user,
            "cart_count": cart_count,
        }

    @app.errorhandler(400)
    def bad_request(error):
        message = getattr(error, "description", "请求参数不正确")
        return render_template("error.html", code=400, message=message), 400

    @app.errorhandler(403)
    def forbidden(error):
        message = getattr(error, "description", "无权访问")
        return render_template("error.html", code=403, message=message), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, message="页面或商品不存在"), 404

    @app.errorhandler(500)
    def server_error(error):  # pragma: no cover - 线上兜底
        return render_template("error.html", code=500, message="服务暂时不可用，请稍后再试"), 500

    @app.route("/api/health")
    def health():
        db = get_db()
        return jsonify({
            "status": "up",
            "products": db.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"],
            "orders": db.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"],
            "version": "1.5",
        })

    @app.route("/dev/reset")
    def test_reset():
        remote = request.remote_addr or ""
        if remote not in ("127.0.0.1", "::1", "localhost"):
            abort(403, "演示重置接口只允许本机访问")
        reset_db()
        LOGIN_FAILS.clear()
        session.clear()
        return {"status": "reset"}

    @app.route("/")
    def index():
        keyword = request.args.get("q", "").strip()
        products = list_products(keyword)
        return render_template("index.html", products=products, keyword=keyword)

    @app.route("/search")
    def search():
        return redirect(url_for("index", q=request.args.get("q", "")))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().casefold()
            password = request.form.get("password", "").strip()
            if not email:
                flash("请输入邮箱")
                return render_template("login.html"), 200
            if not password:
                flash("请输入密码")
                return render_template("login.html"), 200
            key = login_key(email)
            if login_is_blocked(key):
                flash("登录尝试过于频繁，请 10 分钟后再试")
                return render_template("login.html"), 429
            user, error = authenticate(email, password)
            if error:
                if error == "邮箱或密码错误":
                    login_record_fail(key)
                flash(error)
                return render_template("login.html"), 200
            cart = session.get("cart")
            session.clear()
            if cart:
                session["cart"] = cart
            session["email"] = user["email"]
            session.permanent = True
            LOGIN_FAILS.pop(key, None)
            flash(f"欢迎回来，{user['name']}")
            return redirect(safe_next(request.args.get("next") or request.form.get("next")))
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("已退出登录")
        return redirect(url_for("index"))

    @app.route("/product/<int:pid>")
    def product_detail(pid):
        product = get_product(pid)
        if not product:
            abort(404, "商品不存在")
        return render_template("product.html", product=product)

    @app.route("/cart")
    def cart():
        items, subtotal = cart_items()
        return render_template("cart.html", items=items, subtotal=money(subtotal))

    @app.route("/cart/add/<int:pid>", methods=["POST"])
    def cart_add(pid):
        product = get_product(pid)
        if not product:
            abort(404, "商品不存在")
        try:
            qty = int(request.form.get("qty", 1))
        except (TypeError, ValueError):
            qty = 1
        qty = max(1, qty)
        cart_data = session.setdefault("cart", {})
        current_qty = int(cart_data.get(str(pid), 0))
        if current_qty + qty > product["stock"]:
            flash(f"库存不足：{product['name']} 最多还能加 {max(0, product['stock'] - current_qty)} 台")
            return redirect(url_for("cart"))
        cart_data[str(pid)] = current_qty + qty
        session["cart"] = cart_data
        flash(f"已加入购物车：{product['name']} × {qty}")
        return redirect(url_for("cart"))

    @app.route("/cart/update/<int:pid>", methods=["POST"])
    def cart_update(pid):
        try:
            qty = int(request.form.get("qty", 1))
        except (TypeError, ValueError):
            flash("数量必须是整数")
            return redirect(url_for("cart"))
        cart_data = session.setdefault("cart", {})
        if qty <= 0:
            cart_data.pop(str(pid), None)
            session["cart"] = cart_data
            return redirect(url_for("cart"))
        product = get_product(pid)
        if not product:
            cart_data.pop(str(pid), None)
            session["cart"] = cart_data
            flash("商品已下架，已从购物车移除")
            return redirect(url_for("cart"))
        if qty > product["stock"]:
            flash(f"库存不足：{product['name']} 只剩 {product['stock']} 台")
            return redirect(url_for("cart"))
        cart_data[str(pid)] = qty
        session["cart"] = cart_data
        return redirect(url_for("cart"))

    @app.route("/cart/remove/<int:pid>", methods=["POST"])
    def cart_remove(pid):
        cart_data = session.get("cart", {})
        cart_data.pop(str(pid), None)
        session["cart"] = cart_data
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
        problems = cart_stock_problems(items)
        if problems:
            flash("；".join(problems) + "，请先调整购物车")
            return redirect(url_for("cart"))
        coupon_code = session.get("coupon")
        coupon = get_coupon(coupon_code)
        if coupon:
            error = coupon_error(coupon, subtotal)
            if error:
                session.pop("coupon", None)
                flash(error)
                coupon = None
        amounts = calculate_total(user, subtotal, coupon)
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
                for error in errors:
                    flash(error)
                return render_template(
                    "checkout.html", items=items, subtotal=amounts["subtotal"],
                    discount=amounts["discount"], coupon_discount=amounts["coupon_discount"],
                    total=amounts["total"], user=user, coupon=coupon,
                )
            try:
                order_no = create_order(
                    user, items, receiver, phone, address, coupon["code"] if coupon else None
                )
            except BusinessError as error:
                flash(str(error))
                return render_template(
                    "checkout.html", items=items, subtotal=amounts["subtotal"],
                    discount=amounts["discount"], coupon_discount=amounts["coupon_discount"],
                    total=amounts["total"], user=user, coupon=coupon,
                )
            session["cart"] = {}
            session.pop("coupon", None)
            flash("下单成功，库存已为你锁定")
            return redirect(url_for("order_detail", order_no=order_no))
        return render_template(
            "checkout.html", items=items, subtotal=amounts["subtotal"],
            discount=amounts["discount"], coupon_discount=amounts["coupon_discount"],
            total=amounts["total"], user=user, coupon=coupon,
        )

    @app.route("/checkout/coupon", methods=["POST"])
    def apply_coupon():
        user = current_user()
        if not user:
            return redirect(url_for("login", next="/checkout"))
        code = request.form.get("code", "").strip().upper()
        if not code:
            session.pop("coupon", None)
            flash("已清除优惠券")
            return redirect(url_for("checkout"))
        items, subtotal = cart_items()
        coupon = get_coupon(code)
        error = coupon_error(coupon, subtotal)
        if error:
            flash(error)
        else:
            session["coupon"] = coupon["code"]
            flash(f"已应用优惠券 {coupon['code']}")
        return redirect(url_for("checkout"))

    @app.route("/checkout/coupon/clear", methods=["POST"])
    def clear_coupon():
        session.pop("coupon", None)
        flash("已清除优惠券")
        return redirect(url_for("checkout"))

    def own_order(order_no, user):
        order = get_order(order_no)
        if not order:
            abort(404, "订单不存在")
        if order["user_id"] != user["id"] and user["role"] != "admin":
            abort(403, "无权查看该订单")
        return order

    @app.route("/order/<order_no>")
    def order_detail(order_no):
        user = current_user()
        if not user:
            return redirect(url_for("login", next=request.path))
        order = own_order(order_no, user)
        return render_template("order.html", order=order)

    @app.route("/order/<order_no>/cancel", methods=["POST"])
    def order_cancel(order_no):
        user = current_user()
        if not user:
            return redirect(url_for("login", next=request.path))
        own_order(order_no, user)
        try:
            transition_order(order_no, "cancel", "user")
            flash("订单已取消，库存已释放")
        except BusinessError as error:
            flash(str(error))
        return redirect(url_for("order_detail", order_no=order_no))

    @app.route("/order/<order_no>/refund", methods=["POST"])
    def order_refund(order_no):
        user = current_user()
        if not user:
            return redirect(url_for("login", next=request.path))
        own_order(order_no, user)
        try:
            transition_order(order_no, "request_refund", "user")
            flash("退款申请已提交，等待管理员审核")
        except BusinessError as error:
            flash(str(error))
        return redirect(url_for("order_detail", order_no=order_no))

    @app.route("/order/<order_no>/complete", methods=["POST"])
    def order_complete(order_no):
        user = current_user()
        if not user:
            return redirect(url_for("login", next=request.path))
        own_order(order_no, user)
        try:
            transition_order(order_no, "complete", "user")
            flash("已确认收货，感谢购买")
        except BusinessError as error:
            flash(str(error))
        return redirect(url_for("order_detail", order_no=order_no))

    @app.route("/pay/<order_no>", methods=["GET", "POST"])
    def pay(order_no):
        user = current_user()
        if not user:
            return redirect(url_for("login", next=request.path))
        order = own_order(order_no, user)
        if order["status"] == "paid":
            flash("订单已支付，不用重复付款")
            return render_template("pay.html", order=order), 200
        if order["status"] != "pending":
            flash(f"订单当前状态为「{order['status_label']}」，不能支付")
            return render_template("pay.html", order=order), 200
        if request.method == "POST":
            method = request.form.get("method", "")
            try:
                pay_order(order_no, method)
            except BusinessError as error:
                flash(str(error))
                return render_template("pay.html", order=get_order(order_no)), 200
            flash("支付成功")
            return redirect(url_for("order_detail", order_no=order_no))
        return render_template("pay.html", order=order)

    @app.route("/admin")
    def admin_dashboard():
        user, response = admin_required()
        if response:
            return response
        status = request.args.get("status", "").strip() or None
        return render_template(
            "admin.html",
            stats=admin_stats(),
            orders=list_orders(status),
            products=list_products_admin(),
            coupons=list_coupons(),
            users=list_users(),
            current_status=status or "",
            admin=user,
        )

    @app.route("/admin/orders/<order_no>/<action>", methods=["POST"])
    def admin_order_action(order_no, action):
        _user, response = admin_required()
        if response:
            return response
        action_map = {
            "ship": "ship",
            "complete": "complete",
            "refund": "refund",
            "cancel": "admin_cancel",
        }
        if action not in action_map:
            abort(400, "不支持的后台操作")
        try:
            transition_order(order_no, action_map[action], "admin")
            flash("订单状态已更新")
        except BusinessError as error:
            flash(str(error))
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/products/<int:pid>/stock", methods=["POST"])
    def admin_product_stock(pid):
        _user, response = admin_required()
        if response:
            return response
        try:
            update_product_stock(pid, request.form.get("stock", ""))
            flash("库存已更新")
        except BusinessError as error:
            flash(str(error))
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/coupons", methods=["POST"])
    def admin_coupon_create():
        _user, response = admin_required()
        if response:
            return response
        try:
            create_coupon(
                request.form.get("code", ""),
                request.form.get("kind", "fixed"),
                request.form.get("value", ""),
                request.form.get("min_spend", "0"),
                request.form.get("max_discount") or None,
                request.form.get("max_uses") or None,
                request.form.get("expires_at") or None,
            )
            flash("优惠券已创建")
        except BusinessError as error:
            flash(str(error))
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
    def admin_user_toggle(user_id):
        _user, response = admin_required()
        if response:
            return response
        try:
            active = toggle_user_active(user_id)
            flash("用户已启用" if active else "用户已停用")
        except BusinessError as error:
            flash(str(error))
        return redirect(url_for("admin_dashboard"))

    return app


app = create_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9500)
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port, debug=False)
