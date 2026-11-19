from selenium.webdriver.common.by import By
from tests.pages.base_page import BasePage


class OrderPage(BasePage):
    ORDER_NO = (By.ID, "order-no")
    STATUS = (By.ID, "order-status")
    TOTAL = (By.ID, "order-total")
    PAY_BTN = (By.ID, "pay-btn")
    RECEIVER = (By.ID, "order-receiver")

    def order_no(self):
        return self.text_of(self.ORDER_NO)

    def status(self):
        return self.text_of(self.STATUS)

    def total(self):
        return self.text_of(self.TOTAL)

    def receiver(self):
        return self.text_of(self.RECEIVER)

    def go_pay(self):
        self.click(self.PAY_BTN)
        self.wait_url_contains("/pay/")
        return self
