from selenium.webdriver.common.by import By
from pages.base_page import BasePage


class PayPage(BasePage):
    AMOUNT = (By.ID, "pay-amount")
    ALIPAY = (By.ID, "method-alipay")
    WECHAT = (By.ID, "method-wechat")
    CARD = (By.ID, "method-card")
    CONFIRM = (By.ID, "pay-confirm")
    STATUS = (By.ID, "pay-status")
    FLASH = (By.ID, "flash")

    def amount(self):
        return self.text_of(self.AMOUNT)

    def choose(self, method):
        locator = {"alipay": self.ALIPAY, "wechat": self.WECHAT, "card": self.CARD}[method]
        self.click(locator)
        return self

    def confirm(self):
        self.click(self.CONFIRM)
        self.wait.until(lambda d: "/order/" in d.current_url or d.find_elements(By.ID, "flash"))
        return self

    def pay(self, method):
        self.choose(method)
        self.confirm()
        return self

    def paid_text(self):
        return self.text_of(self.STATUS) if self.exists(self.STATUS) else ""

    def flash_text(self):
        return self.text_of(self.FLASH) if self.exists(self.FLASH) else ""
