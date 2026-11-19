import pytest

from tests.pages.cart_page import CartPage
from tests.pages.home_page import HomePage
from tests.pages.product_page import ProductPage


@pytest.mark.smoke
def test_add_one_product(logged_in, shop):
    HomePage(logged_in, shop).open_page().add_to_cart("iPhone 17 Pro")
    cart = CartPage(logged_in, shop)
    assert cart.row_count() == 1
    assert "8999.00" in cart.total()


def test_add_same_product_twice(logged_in, shop):
    home = HomePage(logged_in, shop)
    home.open_page().add_to_cart("iPhone 17 Pro")
    home.open_page().add_to_cart("iPhone 17 Pro")
    cart = CartPage(logged_in, shop)
    assert cart.qty_of(1) == 2
    assert "17998.00" in cart.total()


def test_add_two_different_products(logged_in, shop):
    home = HomePage(logged_in, shop)
    home.open_page().add_to_cart("iPhone 17 Pro")
    home.open_page().add_to_cart("小米 15")
    cart = CartPage(logged_in, shop)
    assert cart.row_count() == 2
    assert "13298.00" in cart.total()


def test_update_quantity(logged_in, shop):
    home = HomePage(logged_in, shop)
    home.open_page().add_to_cart("iPhone 17 Pro")
    cart = CartPage(logged_in, shop).open_page()
    cart.set_qty(1, 3)
    assert cart.qty_of(1) == 3
    assert "26997.00" in cart.total()


def test_remove_product(logged_in, shop):
    home = HomePage(logged_in, shop)
    home.open_page().add_to_cart("iPhone 17 Pro")
    cart = CartPage(logged_in, shop).open_page().remove(1)
    assert cart.is_empty()


def test_empty_cart_page(logged_in, shop):
    cart = CartPage(logged_in, shop).open_page()
    assert cart.is_empty()
    assert cart.row_count() == 0


def test_cart_count_in_nav(logged_in, shop):
    home = HomePage(logged_in, shop)
    home.open_page().add_to_cart("小米 15")
    home.open_page()
    assert "1" in home.cart_count_text()


@pytest.mark.smoke
def test_cart_to_checkout(logged_in, shop):
    home = HomePage(logged_in, shop)
    home.open_page().add_to_cart("iPhone 17 Pro")
    CartPage(logged_in, shop).open_page().go_checkout()
    assert "checkout" in logged_in.current_url


def test_add_from_product_page_with_qty(logged_in, shop):
    ProductPage(logged_in, shop).open_page(2).add(2)
    cart = CartPage(logged_in, shop)
    assert cart.qty_of(2) == 2
    assert "8598.00" in cart.total()


@pytest.mark.xfail(reason="SHOP-01：购物车不校验库存，库存 12 台却能加 13 台")
def test_cart_rejects_quantity_above_stock(logged_in, shop):
    ProductPage(logged_in, shop).open_page(1).add(13)
    cart = CartPage(logged_in, shop)
    assert cart.is_empty()
