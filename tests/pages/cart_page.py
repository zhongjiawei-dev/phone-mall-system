from selenium.webdriver.common.by import By
from tests.pages.base_page import BasePage


class CartPage(BasePage):
    ROWS = (By.CSS_SELECTOR, ".cart-row")
    TOTAL = (By.ID, "cart-total")
    CHECKOUT = (By.ID, "checkout-btn")
    EMPTY = (By.ID, "empty-cart")

    def open_page(self):
        self.open("/cart")
        self.wait_loaded()
        return self

    def wait_loaded(self):
        self.wait_url_contains("/cart")
        self.wait.until(lambda d: d.find_elements(*self.ROWS) or d.find_elements(By.ID, "empty-cart"))

    def row_count(self):
        self.wait_loaded()
        return len(self.driver.find_elements(*self.ROWS))

    def total(self):
        self.wait_loaded()
        return self.text_of(self.TOTAL)

    def is_empty(self):
        self.wait_loaded()
        return self.exists(self.EMPTY)

    def qty_of(self, pid):
        self.wait_loaded()
        el = self.find((By.ID, f"qty-{pid}"))
        return int(el.get_attribute("value"))

    def set_qty(self, pid, qty):
        self.type((By.ID, f"qty-{pid}"), str(qty))
        self.click((By.CSS_SELECTOR, f".cart-row[data-pid='{pid}'] .update-btn"))
        # 表单提交后强制重新加载购物车，避免在导航过程中复用旧 DOM 节点。
        self.open("/cart")
        self.wait_loaded()
        return self

    def remove(self, pid):
        self.click((By.CSS_SELECTOR, f".cart-row[data-pid='{pid}'] .remove-btn"))
        self.open("/cart")
        self.wait_loaded()
        return self

    def go_checkout(self):
        self.click(self.CHECKOUT)
        self.wait_url_contains("/checkout")
        self.wait.until(lambda d: d.find_elements(By.ID, "receiver"))
        return self
