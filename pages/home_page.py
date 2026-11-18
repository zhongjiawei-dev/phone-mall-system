from selenium.webdriver.common.by import By
from pages.base_page import BasePage


class HomePage(BasePage):
    SEARCH_INPUT = (By.ID, "search-input")
    SEARCH_BTN = (By.ID, "search-btn")
    CARDS = (By.CSS_SELECTOR, ".product-card")
    EMPTY = (By.ID, "empty-result")
    CART_LINK = (By.ID, "nav-cart")
    LOGIN_LINK = (By.ID, "nav-login")

    def open_page(self):
        self.open("/")
        self.wait.until(lambda d: d.find_elements(*self.CARDS) or d.find_elements(*self.EMPTY))
        return self

    def search(self, keyword):
        if keyword:
            self.type(self.SEARCH_INPUT, keyword)
        self.click(self.SEARCH_BTN)
        self.wait.until(lambda d: d.find_elements(*self.CARDS) or d.find_elements(*self.EMPTY))
        return self

    def card_names(self):
        return [c.get_attribute("data-name") for c in self.driver.find_elements(*self.CARDS)]

    def card_count(self):
        return len(self.driver.find_elements(*self.CARDS))

    def add_to_cart(self, product_name):
        by_name = (By.XPATH, f"//div[@data-name='{product_name}']//button[contains(@class,'add-cart')]")
        self.click(by_name)
        self.wait_url_contains("/cart")
        return self

    def open_product(self, product_name):
        by_name = (By.XPATH, f"//div[@data-name='{product_name}']//a[contains(@class,'product-link')]")
        self.click(by_name)
        self.wait_url_contains("/product/")
        return self

    def cart_count_text(self):
        return self.text_of(self.CART_LINK)

    def empty_hint(self):
        return self.text_of(self.EMPTY) if self.exists(self.EMPTY) else ""
