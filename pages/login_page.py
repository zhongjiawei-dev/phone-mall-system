from selenium.webdriver.common.by import By
from pages.base_page import BasePage


class LoginPage(BasePage):
    EMAIL = (By.ID, "email")
    PASSWORD = (By.ID, "password")
    LOGIN_BTN = (By.ID, "login-btn")
    FLASH = (By.ID, "flash")
    NAV_USER = (By.ID, "nav-user")

    def open_page(self):
        self.open("/login")
        self.wait.until(lambda d: d.find_elements(*self.EMAIL))
        return self

    def login(self, email, password):
        self.type(self.EMAIL, email)
        self.type(self.PASSWORD, password)
        self.click(self.LOGIN_BTN)
        return self

    def flash_text(self):
        return self.text_of(self.FLASH) if self.exists(self.FLASH) else ""

    def logged_in_as(self):
        return self.text_of(self.NAV_USER) if self.exists(self.NAV_USER, timeout=5) else ""
