from playwright.sync_api import Page, Locator

class RegistrationPage:
    """Page Object Model for the Registration Flow."""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page: Page = page
        self.base_url: str = base_url.rstrip("/")
        self.page.set_default_timeout(30000)

        # Locators via data-testid
        self.name_input: Locator = self.page.get_by_test_id("reg-name")
        self.email_input: Locator = self.page.get_by_test_id("reg-email")
        self.phone_input: Locator = self.page.get_by_test_id("reg-phone")
        self.password_input: Locator = self.page.get_by_test_id("reg-password")
        self.confirm_input: Locator = self.page.get_by_test_id("reg-confirm")
        self.submit_btn: Locator = self.page.get_by_test_id("reg-submit")
        self.error_alert: Locator = self.page.get_by_test_id("reg-error")
        self.success_alert: Locator = self.page.get_by_test_id("reg-success")

    def goto(self) -> None:
        """Navigates to the /register page."""
        self.page.goto(f"{self.base_url}/register", wait_until="domcontentloaded")

    def fill_form(
        self,
        name: str = "",
        email: str = "",
        phone: str = "",
        password: str = "",
        confirm: str = ""
    ) -> None:
        """Fills registration input fields."""
        self.name_input.fill(name)
        self.email_input.fill(email)
        self.phone_input.fill(phone)
        self.password_input.fill(password)
        self.confirm_input.fill(confirm)

    def submit(self) -> None:
        """Submits the registration form."""
        self.submit_btn.click()

    def get_error_text(self) -> str:
        """Returns the visible registration error message."""
        self.error_alert.wait_for(state="visible", timeout=10000)
        return self.error_alert.inner_text().strip()

    def get_success_text(self) -> str:
        """Returns the visible registration success message."""
        self.success_alert.wait_for(state="visible", timeout=10000)
        return self.success_alert.inner_text().strip()

    def is_error_visible(self) -> bool:
        """Checks if the error alert is currently visible."""
        return self.error_alert.is_visible()

    def is_success_visible(self) -> bool:
        """Checks if the success alert is currently visible."""
        return self.success_alert.is_visible()
