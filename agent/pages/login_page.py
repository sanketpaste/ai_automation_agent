from playwright.sync_api import Page, Locator

class LoginPage:
    """Page Object Model for the Login Flow."""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page: Page = page
        self.base_url: str = base_url.rstrip("/")
        self.page.set_default_timeout(30000)

        # Locators via data-testid
        self.username_input: Locator = self.page.get_by_test_id("login-username")
        self.password_input: Locator = self.page.get_by_test_id("login-password")
        self.submit_btn: Locator = self.page.get_by_test_id("login-submit")
        self.error_alert: Locator = self.page.get_by_test_id("login-error")

    def goto(self) -> None:
        """Navigates to the /login page."""
        self.page.goto(f"{self.base_url}/login", wait_until="domcontentloaded")

    def fill_credentials(self, username: str = "", password: str = "") -> None:
        """Fills the login credentials."""
        self.username_input.fill(username)
        self.password_input.fill(password)

    def submit(self) -> None:
        """Clicks the login submit button."""
        self.submit_btn.click()

    def get_error_text(self) -> str:
        """Returns the visible login error message."""
        self.error_alert.wait_for(state="visible", timeout=10000)
        return self.error_alert.inner_text().strip()

    def is_error_visible(self) -> bool:
        """Checks if login error is visible."""
        return self.error_alert.is_visible()
