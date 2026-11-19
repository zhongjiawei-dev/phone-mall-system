"""V1.5 业务规则测试：数据库、库存、订单状态机、优惠券与后台。"""

import re

import pytest

from shop.app import create_app
from shop.db import get_db
from shop.services import get_order, get_product


@pytest.fixture
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "shop-test.db"),
        "SECRET_KEY": "test-secret",
    })
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def csrf(client, path):
    response = client.get(path)
    assert response.status_code == 200
    match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
    assert match, f"页面没有 CSRF token: {path}"
    return match.group(1).decode()


def login(client, email="student@example.com", password="Shop@123"):
    token = csrf(client, "/login")
    return client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": token},
        follow_redirects=True,
    )


def add_iphone(client):
    token = csrf(client, "/")
    return client.post(
        "/cart/add/1", data={"qty": "1", "csrf_token": token}, follow_redirects=True
    )


def make_order(client, receiver="钟同学", phone="13800000001", address="3 栋 201"):
    add_iphone(client)
    token = csrf(client, "/checkout")
    response = client.post(
        "/checkout",
        data={"receiver": receiver, "phone": phone, "address": address, "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 302
    return response.headers["Location"].rsplit("/", 1)[-1]


def pay_order(client, order_no):
    token = csrf(client, f"/pay/{order_no}")
    return client.post(
        f"/pay/{order_no}", data={"method": "alipay", "csrf_token": token},
        follow_redirects=True,
    )


def test_password_hash_and_schema(client, app):
    with app.app_context():
        row = get_db().execute(
            "SELECT password_hash FROM users WHERE email = 'student@example.com'"
        ).fetchone()
        assert row and "Shop@123" not in row["password_hash"]
        assert len(row["password_hash"]) > 40
        assert get_product(1)["stock"] == 12


def test_login_case_insensitive(client):
    response = login(client, "Student@Example.com")
    text = response.get_data(as_text=True)
    assert "你好，小钟" in text


def test_csrf_required(client):
    response = client.post("/login", data={"email": "student@example.com", "password": "Shop@123"})
    assert response.status_code == 400
    assert "CSRF" in response.get_data(as_text=True)


def test_cart_rejects_stock_overflow(client, app):
    login(client)
    token = csrf(client, "/product/1")
    response = client.post(
        "/cart/add/1", data={"qty": "13", "csrf_token": token}, follow_redirects=True
    )
    assert "库存不足" in response.get_data(as_text=True)
    with app.app_context():
        assert get_product(1)["stock"] == 12


def test_cancel_pending_restores_stock(client, app):
    login(client)
    order_no = make_order(client)
    with app.app_context():
        assert get_product(1)["stock"] == 11
    token = csrf(client, f"/order/{order_no}")
    response = client.post(
        f"/order/{order_no}/cancel", data={"csrf_token": token}, follow_redirects=True
    )
    assert "订单已取消" in response.get_data(as_text=True)
    with app.app_context():
        assert get_order(order_no)["status"] == "cancelled"
        assert get_product(1)["stock"] == 12


def test_pay_and_admin_refund(client, app):
    login(client)
    order_no = make_order(client)
    response = pay_order(client, order_no)
    assert "支付成功" in response.get_data(as_text=True)
    with app.app_context():
        assert get_order(order_no)["payment_method"] == "alipay"
    token = csrf(client, f"/order/{order_no}")
    client.post(f"/order/{order_no}/refund", data={"csrf_token": token}, follow_redirects=True)
    with app.app_context():
        assert get_order(order_no)["status"] == "refunding"
        assert get_product(1)["stock"] == 11
    client.get("/logout")
    login(client, "admin@example.com", "Admin@123")
    token = csrf(client, "/admin")
    client.post(f"/admin/orders/{order_no}/refund", data={"csrf_token": token}, follow_redirects=True)
    with app.app_context():
        order = get_order(order_no)
        assert order["status"] == "refunded"
        assert order["stock_restored"] is True
        assert get_product(1)["stock"] == 12


def test_coupon_discount(client, app):
    login(client)
    add_iphone(client)
    token = csrf(client, "/checkout")
    response = client.post(
        "/checkout/coupon", data={"code": "WELCOME10", "csrf_token": token},
        follow_redirects=True,
    )
    assert "已应用优惠券" in response.get_data(as_text=True)
    token = csrf(client, "/checkout")
    response = client.post(
        "/checkout",
        data={"receiver": "钟同学", "phone": "13800000001", "address": "3 栋 201",
              "csrf_token": token},
        follow_redirects=False,
    )
    order_no = response.headers["Location"].rsplit("/", 1)[-1]
    with app.app_context():
        order = get_order(order_no)
        assert order["coupon_code"] == "WELCOME10"
        assert order["total"] == "8989.00"


def test_order_lifecycle_ship_and_complete(client, app):
    login(client)
    order_no = make_order(client)
    pay_order(client, order_no)
    client.get("/logout")
    login(client, "admin@example.com", "Admin@123")
    token = csrf(client, "/admin")
    client.post(f"/admin/orders/{order_no}/ship", data={"csrf_token": token}, follow_redirects=True)
    client.get("/logout")
    login(client)
    token = csrf(client, f"/order/{order_no}")
    client.post(f"/order/{order_no}/complete", data={"csrf_token": token}, follow_redirects=True)
    with app.app_context():
        assert get_order(order_no)["status"] == "completed"


def test_admin_stock_update(client, app):
    login(client, "admin@example.com", "Admin@123")
    token = csrf(client, "/admin")
    client.post("/admin/products/1/stock", data={"stock": "30", "csrf_token": token}, follow_redirects=True)
    with app.app_context():
        assert get_product(1)["stock"] == 30
