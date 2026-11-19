import pytest

from tests.pages.cart_page import CartPage
from tests.pages.checkout_page import CheckoutPage
from tests.pages.home_page import HomePage
from tests.pages.login_page import LoginPage
from tests.pages.order_page import OrderPage
from tests.pages.pay_page import PayPage
from tests.pages.product_page import ProductPage


def test_pay_page_amount(pay_ready):
    assert "8999.00" in pay_ready.amount()


@pytest.mark.smoke
def test_pay_with_alipay(created_order, shop):
    created_order["page"].go_pay()
    PayPage(created_order["driver"], shop).pay("alipay")
    assert OrderPage(created_order["driver"], shop).status() == "已支付"


@pytest.mark.smoke
def test_pay_with_wechat(created_order, shop):
    created_order["page"].go_pay()
    PayPage(created_order["driver"], shop).pay("wechat")
    assert OrderPage(created_order["driver"], shop).status() == "已支付"


@pytest.mark.smoke
def test_pay_with_card(created_order, shop):
    created_order["page"].go_pay()
    PayPage(created_order["driver"], shop).pay("card")
    assert OrderPage(created_order["driver"], shop).status() == "已支付"


def test_pay_without_method(pay_ready):
    pay_ready.confirm()
    assert "请选择支付方式" in pay_ready.flash_text()


def test_paid_order_cannot_pay_again(created_order, shop):
    created_order["page"].go_pay()
    PayPage(created_order["driver"], shop).pay("alipay")
    created_order["driver"].get(shop + f"/pay/{created_order['order_no']}")
    assert "已支付" in PayPage(created_order["driver"], shop).paid_text()


def test_stock_decreased_after_pay(created_order, shop):
    created_order["page"].go_pay()
    PayPage(created_order["driver"], shop).pay("alipay")
    HomePage(created_order["driver"], shop).open_page()
    assert "11" in ProductPage(created_order["driver"], shop).open_page(1).stock()


def test_total_not_changed_after_pay(created_order, shop):
    created_order["page"].go_pay()
    PayPage(created_order["driver"], shop).pay("alipay")
    assert "8999.00" in OrderPage(created_order["driver"], shop).total()


def test_other_user_cannot_view_order(created_order, shop):
    created_order["driver"].get(shop + "/logout")
    LoginPage(created_order["driver"], shop).open_page().login("vip@example.com", "Vip@123")
    created_order["driver"].get(shop + f"/order/{created_order['order_no']}")
    assert "无权查看该订单" in created_order["driver"].page_source


def test_pay_requires_login(created_order, shop):
    no = created_order["order_no"]
    created_order["driver"].get(shop + "/logout")
    created_order["driver"].get(shop + f"/pay/{no}")
    assert "/login" in created_order["driver"].current_url
