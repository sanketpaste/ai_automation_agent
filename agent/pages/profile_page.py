from playwright.sync_api import Page, Locator

class ProfilePage:
    """Page Object Model for the User Profile Flow."""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page: Page = page
        self.base_url: str = base_url.rstrip("/")
        self.page.set_default_timeout(30000)

        # Locators via data-testid
        self.name_display: Locator = self.page.get_by_test_id("profile-name")
        self.email_display: Locator = self.page.get_by_test_id("profile-email")
        self.phone_display: Locator = self.page.get_by_test_id("profile-phone")

        self.edit_name_input: Locator = self.page.get_by_test_id("edit-name")
        self.edit_phone_input: Locator = self.page.get_by_test_id("edit-phone")
        self.save_btn: Locator = self.page.get_by_test_id("save-profile")
        self.save_success_alert: Locator = self.page.get_by_test_id("save-success")

        self.logout_btn: Locator = self.page.get_by_test_id("logout-btn")

    def goto(self) -> None:
        """Navigates to the /profile page."""
        self.page.goto(f"{self.base_url}/profile", wait_until="domcontentloaded")

    def get_displayed_name(self) -> str:
        """Returns the profile name currently displayed."""
        self.name_display.wait_for(state="visible", timeout=10000)
        return self.name_display.inner_text().strip()

    def get_displayed_email(self) -> str:
        """Returns the profile email currently displayed."""
        self.email_display.wait_for(state="visible", timeout=10000)
        return self.email_display.inner_text().strip()

    def get_displayed_phone(self) -> str:
        """Returns the profile phone currently displayed."""
        self.phone_display.wait_for(state="visible", timeout=10000)
        return self.phone_display.inner_text().strip()

    def update_profile(self, new_name: str, new_phone: str) -> None:
        """Fills edit name and phone and clicks save."""
        self.edit_name_input.fill(new_name)
        self.edit_phone_input.fill(new_phone)
        self.save_btn.click()

    def is_save_success_visible(self) -> bool:
        """Checks if profile save success alert is visible."""
        self.save_success_alert.wait_for(state="visible", timeout=10000)
        return self.save_success_alert.is_visible()

    def logout(self) -> None:
        """Clicks the logout button."""
        self.logout_btn.click()
