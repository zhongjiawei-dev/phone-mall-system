import pytest

from tests.pages.cart_page import CartPage
from tests.pages.checkout_page import CheckoutPage
from tests.pages.home_page import HomePage
from tests.pages.login_page import LoginPage
from tests.pages.order_page import OrderPage


def test_checkout_requires_login(driver, shop):
    driver.get(shop + "/checkout")
    assert "/login" in driver.current_url


def test_checkout_page_shows_total(checkout_ready, shop):
    page = CheckoutPage(checkout_ready, shop)
    assert "8999.00" in page.total()
    assert page.exists(page.SUBMIT)


@pytest.mark.smoke
def test_submit_order_success(created_order):
    assert created_order["order_no"].startswith("ORD")
    assert created_order["page"].status() == "待支付"


def test_order_receiver(checkout_ready, shop):
    page = CheckoutPage(checkout_ready, shop)
    page.fill(receiver="钟同学").submit()
    assert OrderPage(checkout_ready, shop).receiver() == "钟同学"


def test_empty_receiver_rejected(checkout_ready, shop):
    page = CheckoutPage(checkout_ready, shop)
    page.fill(receiver="").submit()
    assert "收货人至少 2 个字" in page.flash_text()
    assert "/checkout" in checkout_ready.current_url


def test_bad_phone_rejected(checkout_ready, shop):
    page = CheckoutPage(checkout_ready, shop)
    page.fill(phone="12345").submit()
    assert "手机号格式不对" in page.flash_text()


def test_short_address_rejected(checkout_ready, shop):
    page = CheckoutPage(checkout_ready, shop)
    page.fill(address="3栋").submit()
    assert "详细地址至少 5 个字" in page.flash_text()


def test_order_total_matches_cart(checkout_ready, shop):
    cart_total = CartPage(checkout_ready, shop).open_page().total()
    CheckoutPage(checkout_ready, shop).open_page().fill().submit()
    assert OrderPage(checkout_ready, shop).total() == cart_total


@pytest.mark.smoke
def test_vip_discount(vip_logged_in, shop):
    HomePage(vip_logged_in, shop).open_page().add_to_cart("iPhone 17 Pro")
    CartPage(vip_logged_in, shop).open_page().go_checkout()
    page = CheckoutPage(vip_logged_in, shop)
    assert page.has_discount()
    assert "8549.05" in page.total()
