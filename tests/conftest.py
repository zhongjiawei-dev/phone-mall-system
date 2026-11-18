import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = os.environ.get("CHROME_BIN", "/usr/local/bin/chromium")
DRIVER = os.environ.get("CHROMEDRIVER", "/usr/local/bin/chromedriver")
SHOT_DIR = os.path.join(ROOT, "reports", "screenshots")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_up(url, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("商城服务没起来")


@pytest.fixture(scope="session")
def shop_server():
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "shop/app.py", "--port", str(port)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        wait_up(base + "/api/health")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def shop(shop_server):
    return shop_server


@pytest.fixture(scope="session")
def driver():
    options = Options()
    if os.path.exists(CHROME):
        options.binary_location = CHROME
    for arg in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--no-proxy-server", "--proxy-bypass-list=*", "--window-size=1280,900"):
        options.add_argument(arg)
    options.page_load_strategy = "eager"
    service = Service(DRIVER) if os.path.exists(DRIVER) else Service()
    d = webdriver.Chrome(service=service, options=options)
    d.set_window_size(1280, 900)
    yield d
    d.quit()


@pytest.fixture(autouse=True)
def reset_shop(shop_server, driver, request):
    requests.get(shop_server + "/test/reset", timeout=5)
    try:
        driver.get(shop_server + "/logout")
    except Exception:
        pass
    yield
    rep = getattr(request.node, "rep_call", None)
    if rep is not None and rep.failed:
        os.makedirs(SHOT_DIR, exist_ok=True)
        name = request.node.nodeid.replace("/", "_").replace("::", "_").replace(".py", "")
        path = os.path.join(SHOT_DIR, f"{name}.png")
        try:
            driver.save_screenshot(path)
            try:
                import allure
                allure.attach.file(path, name="失败截图", attachment_type=allure.attachment_type.PNG)
            except Exception:
                pass
        except Exception:
            pass


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


@pytest.fixture
def login_page(driver, shop):
    from pages.login_page import LoginPage
    return LoginPage(driver, shop).open_page()


@pytest.fixture
def logged_in(driver, shop):
    from pages.login_page import LoginPage
    LoginPage(driver, shop).open_page().login("student@example.com", "Shop@123").wait_url_contains("/")
    return driver


@pytest.fixture
def vip_logged_in(driver, shop):
    from pages.login_page import LoginPage
    LoginPage(driver, shop).open_page().login("vip@example.com", "Vip@123").wait_url_contains("/")
    return driver


@pytest.fixture
def cart_with_iphone(logged_in, shop):
    from pages.home_page import HomePage
    HomePage(logged_in, shop).open_page().add_to_cart("iPhone 17 Pro")
    return logged_in


@pytest.fixture
def checkout_ready(cart_with_iphone, shop):
    from pages.cart_page import CartPage
    CartPage(cart_with_iphone, shop).open_page().go_checkout()
    return cart_with_iphone


@pytest.fixture
def created_order(checkout_ready, shop):
    from pages.checkout_page import CheckoutPage
    from pages.order_page import OrderPage
    page = CheckoutPage(checkout_ready, shop)
    page.fill().submit()
    page.wait_url_contains("/order/")
    order = OrderPage(checkout_ready, shop)
    return {"driver": checkout_ready, "order_no": order.order_no(), "total": order.total(), "page": order}


@pytest.fixture
def pay_ready(created_order, shop):
    from pages.pay_page import PayPage
    created_order["page"].go_pay()
    return PayPage(created_order["driver"], shop)
