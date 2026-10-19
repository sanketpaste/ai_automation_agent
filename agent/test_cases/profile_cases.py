import time
from typing import List
from playwright.sync_api import Page

from agent.test_cases.base_case import BaseTestCase
from agent.models import TestContext, StepResult
from agent.pages.login_page import LoginPage
from agent.pages.profile_page import ProfilePage

class ProfileTestCases(BaseTestCase):
    """Encapsulates all test cases for User Profile Viewing, Editing, and Session Logout."""

    def __init__(self) -> None:
        super().__init__(name="Profile")

    def execute(self, page: Page, ctx: TestContext, steps: List[StepResult]) -> None:
        login_page: LoginPage = LoginPage(page, ctx.project_url)
        profile_page: ProfilePage = ProfilePage(page, ctx.project_url)

        # Case 1: Authenticate to access profile
        def case_login_for_profile() -> None:
            login_page.goto()
            login_page.fill_credentials(username=ctx.username, password=ctx.password)
            login_page.submit()
            page.wait_for_url("**/profile", timeout=10000)

        self.record_step(page, ctx, steps, "Profile Setup: Authenticate to Access Profile", case_login_for_profile)

        # Case 2: Assert profile user details are rendered correctly
        def case_verify_profile_data() -> None:
            name: str = profile_page.get_displayed_name()
            email: str = profile_page.get_displayed_email()
            phone: str = profile_page.get_displayed_phone()
            if not name or name == "Loading...":
                raise AssertionError(f"Expected valid profile name, got: '{name}'")
            if not email or "@" not in email:
                raise AssertionError(f"Expected valid profile email, got: '{email}'")
            if not phone:
                raise AssertionError(f"Expected valid profile phone, got: '{phone}'")

        self.record_step(page, ctx, steps, "Profile Verification: Assert User Data Displayed", case_verify_profile_data)

        # Case 3: Modify profile name & phone, save, and check success confirmation
        updated_name: str = f"Updated User {int(time.time()) % 1000}"
        updated_phone: str = "9876543210"

        def case_update_profile() -> None:
            profile_page.update_profile(new_name=updated_name, new_phone=updated_phone)
            if not profile_page.is_save_success_visible():
                raise AssertionError("Expected save success confirmation alert")

        self.record_step(page, ctx, steps, "Profile Update: Modify Name & Phone and Save", case_update_profile)

        # Case 4: Reload page and verify persistence of updated fields
        def case_verify_persistence() -> None:
            page.reload(wait_until="domcontentloaded")
            persisted_name: str = profile_page.get_displayed_name()
            persisted_phone: str = profile_page.get_displayed_phone()
            if persisted_name != updated_name:
                raise AssertionError(f"Expected persisted name '{updated_name}', but found '{persisted_name}'")
            if persisted_phone != updated_phone:
                raise AssertionError(f"Expected persisted phone '{updated_phone}', but found '{persisted_phone}'")

        self.record_step(page, ctx, steps, "Profile Persistence: Reload and Verify Saved Data", case_verify_persistence)

        # Case 5: Perform logout and assert redirection to /login
        def case_logout() -> None:
            profile_page.logout()
            page.wait_for_url("**/login", timeout=10000)
            if not page.url.endswith("/login"):
                raise AssertionError(f"Expected redirect to /login after logout, but current URL is '{page.url}'")

        self.record_step(page, ctx, steps, "Profile Logout: Perform Logout and Assert Redirect", case_logout)
