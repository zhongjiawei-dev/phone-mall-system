from selenium.webdriver.common.by import By
from tests.pages.base_page import BasePage


class ProductPage(BasePage):
    NAME = (By.ID, "product-name")
    PRICE = (By.ID, "price")
    STOCK = (By.ID, "stock")
    QTY = (By.ID, "qty")
    ADD_BTN = (By.ID, "add-cart")

    def open_page(self, pid):
        path = f"/product/{pid}"
        for _ in range(2):
            self.driver.get(self.base_url + path)
            try:
                self.wait.until(lambda d: path in d.current_url and d.find_elements(*self.NAME))
                return self
            except Exception:
                continue
        return self

    def name(self):
        return self.text_of(self.NAME)

    def price(self):
        return self.text_of(self.PRICE)

    def stock(self):
        self.wait.until(lambda d: d.find_elements(*self.STOCK))
        return self.text_of(self.STOCK)

    def add(self, qty=1):
        self.type(self.QTY, str(qty))
        self.click(self.ADD_BTN)
        self.wait_url_contains("/cart")
        return self
