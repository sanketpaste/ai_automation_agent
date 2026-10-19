import time
from typing import List
from playwright.sync_api import Page

from agent.agents.base_agent import BaseAgent
from agent.models import TestContext, StepResult
from agent.pages.login_page import LoginPage
from agent.pages.profile_page import ProfilePage

class ProfileAgent(BaseAgent):
    """
    Sub-agent responsible for testing User Profile flows.
    Tests profile data display, inline editing, persistence across reload,
    and secure logout redirection.
    """

    def __init__(self) -> None:
        super().__init__(name="ProfileAgent")

    def execute(self, page: Page, ctx: TestContext, steps: List[StepResult]) -> None:
        login_page: LoginPage = LoginPage(page, ctx.project_url)
        profile_page: ProfilePage = ProfilePage(page, ctx.project_url)

        # 1. Step: Ensure authenticated on profile
        def step_ensure_auth() -> None:
            profile_page.goto()
            # If not authenticated, redirect to /login occurs
            if "/login" in page.url:
                login_page.fill_credentials(username=ctx.username, password=ctx.password)
                login_page.submit()
                page.wait_for_url("**/profile", timeout=10000)

            if not page.url.endswith("/profile"):
                raise AssertionError(f"Expected to be on /profile, but currently on: '{page.url}'")

        self.record_step(page, ctx, steps, "Profile: Session Authentication", step_ensure_auth)

        # 2. Step: Assert profile data is shown
        def step_view_profile() -> None:
            name: str = profile_page.get_displayed_name()
            email: str = profile_page.get_displayed_email()
            if not name:
                raise AssertionError("Expected non-empty profile name display")
            if "@" not in email:
                raise AssertionError(f"Expected valid email in profile display, got: '{email}'")

        self.record_step(page, ctx, steps, "Profile: View Profile Details", step_view_profile)

        # 3. Step: Edit name and phone, then save
        run_suffix: str = str(int(time.time()) % 10000)
        updated_name: str = f"Updated User {run_suffix}"
        updated_phone: str = f"555{int(time.time()) % 10000000:07d}"

        def step_edit_and_save() -> None:
            profile_page.update_profile(new_name=updated_name, new_phone=updated_phone)
            if not profile_page.is_save_success_visible():
                raise AssertionError("Expected profile save success alert to be visible")

        self.record_step(page, ctx, steps, "Profile: Edit & Save Profile Details", step_edit_and_save)

        # 4. Step: Reload page and assert persistence
        def step_reload_and_verify() -> None:
            page.reload(wait_until="domcontentloaded")
            current_name: str = profile_page.get_displayed_name()
            current_phone: str = profile_page.get_displayed_phone()
            if current_name != updated_name:
                raise AssertionError(f"Profile name not persisted after reload! Expected '{updated_name}', got '{current_name}'")
            if current_phone != updated_phone:
                raise AssertionError(f"Profile phone not persisted after reload! Expected '{updated_phone}', got '{current_phone}'")

        self.record_step(page, ctx, steps, "Profile: Reload & Verify Persistence", step_reload_and_verify)

        # 5. Step: Test logout
        def step_logout() -> None:
            profile_page.logout()
            page.wait_for_url("**/login", timeout=10000)
            if not page.url.endswith("/login"):
                raise AssertionError(f"Expected redirect to /login after logout, but got: '{page.url}'")

        self.record_step(page, ctx, steps, "Profile: Logout Flow & Session Termination", step_logout)
