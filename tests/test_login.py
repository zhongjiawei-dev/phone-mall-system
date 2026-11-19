import pytest


def test_login_page_title(login_page):
    assert "登录" in login_page.driver.title


@pytest.mark.smoke
def test_login_success(login_page):
    login_page.login("student@example.com", "Shop@123")
    assert "小钟" in login_page.logged_in_as()


def test_login_wrong_password(login_page):
    login_page.login("student@example.com", "Wrong123")
    assert "邮箱或密码错误" in login_page.flash_text()
    assert login_page.logged_in_as() == ""


def test_login_unknown_email(login_page):
    login_page.login("nobody@example.com", "Shop@123")
    assert "邮箱或密码错误" in login_page.flash_text()


def test_login_empty_email(login_page):
    login_page.login("", "Shop@123")
    assert "请输入邮箱" in login_page.flash_text()


def test_login_empty_password(login_page):
    login_page.login("student@example.com", "")
    assert "请输入密码" in login_page.flash_text()


def test_login_blocked_account(login_page):
    login_page.login("blocked@example.com", "Block@123")
    assert "账号已被停用" in login_page.flash_text()
    assert login_page.logged_in_as() == ""


def test_logout(logged_in, shop):
    from tests.pages.home_page import HomePage
    page = HomePage(logged_in, shop)
    page.open("/logout")
    page.wait.until(lambda d: d.find_elements(*HomePage.LOGIN_LINK))
    assert page.exists(HomePage.LOGIN_LINK)


@pytest.mark.xfail(reason="SHOP-02：登录邮箱区分大小写，大小写混写登不进去")
def test_login_email_case_insensitive(login_page):
    login_page.login("Student@Example.com", "Shop@123")
    assert "小钟" in login_page.logged_in_as()
