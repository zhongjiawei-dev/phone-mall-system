from pathlib import Path

import pytest
import yaml

from pages.home_page import HomePage
from pages.product_page import ProductPage

SEARCH_CASES = yaml.safe_load(
    (Path(__file__).resolve().parent.parent / "data" / "search_cases.yaml").read_text(encoding="utf-8")
)


@pytest.mark.smoke
def test_search_exact_model(logged_in, shop):
    home = HomePage(logged_in, shop).open_page().search("iPhone 17 Pro")
    assert home.card_names() == ["iPhone 17 Pro"]


@pytest.mark.parametrize("case", SEARCH_CASES, ids=[c["id"] for c in SEARCH_CASES])
def test_search_filters(logged_in, shop, case):
    home = HomePage(logged_in, shop).open_page().search(case["keyword"])
    if case.get("expect_empty"):
        assert home.card_count() == 0
        assert "没有找到" in home.empty_hint()
        return
    if "expect_count" in case:
        assert home.card_count() == case["expect_count"]
    for name in case.get("expect_names", []):
        assert name in home.card_names()


def test_open_product_detail(logged_in, shop):
    home = HomePage(logged_in, shop).open_page()
    home.open_product("小米 15")
    detail = ProductPage(logged_in, shop)
    assert detail.name() == "小米 15"
    assert "4299.00" in detail.price()


def test_product_stock_text(logged_in, shop):
    detail = ProductPage(logged_in, shop).open_page(1)
    assert "12" in detail.stock()
