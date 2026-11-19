from selenium.webdriver.common.by import By
from tests.pages.base_page import BasePage


class CheckoutPage(BasePage):
    RECEIVER = (By.ID, "receiver")
    PHONE = (By.ID, "phone")
    ADDRESS = (By.ID, "address")
    SUBMIT = (By.ID, "submit-order")
    TOTAL = (By.ID, "payable-total")
    DISCOUNT = (By.ID, "discount-row")
    FLASH = (By.ID, "flash")

    def open_page(self):
        self.open("/checkout")
        self.wait_loaded()
        return self

    def wait_loaded(self):
        self.wait.until(lambda d: d.find_elements(*self.RECEIVER))
        return self

    def fill(self, receiver="钟同学", phone="13800000001", address="3 栋 201"):
        self.type(self.RECEIVER, receiver)
        self.type(self.PHONE, phone)
        self.type(self.ADDRESS, address)
        return self

    def submit(self):
        self.click(self.SUBMIT)
        return self

    def total(self):
        return self.text_of(self.TOTAL)

    def has_discount(self):
        return self.exists(self.DISCOUNT)

    def flash_text(self):
        return self.text_of(self.FLASH) if self.exists(self.FLASH) else ""
