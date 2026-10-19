from typing import List
from playwright.sync_api import Page

from agent.agents.base_agent import BaseAgent
from agent.models import TestContext, StepResult
from agent.pages.login_page import LoginPage

class LoginAgent(BaseAgent):
    """
    Sub-agent responsible for testing User Authentication flows.
    Tests empty form validation, wrong password error messaging,
    and valid credentials redirecting to /profile.
    """

    def __init__(self) -> None:
        super().__init__(name="LoginAgent")

    def execute(self, page: Page, ctx: TestContext, steps: List[StepResult]) -> None:
        login_page: LoginPage = LoginPage(page, ctx.project_url)

        # 1. Negative case: Empty login form validation
        def step_empty_form() -> None:
            login_page.goto()
            login_page.fill_credentials(username="", password="")
            login_page.submit()
            err: str = login_page.get_error_text()
            if "required" not in err.lower():
                raise AssertionError(f"Expected empty form error, but got: '{err}'")

        self.record_step(page, ctx, steps, "Negative: Empty Form Validation", step_empty_form)

        # 2. Negative case: Wrong password validation
        def step_wrong_password() -> None:
            login_page.goto()
            login_page.fill_credentials(
                username=ctx.username,
                password=f"{ctx.password}_invalid_suffix_999"
            )
            login_page.submit()
            err: str = login_page.get_error_text()
            if "invalid" not in err.lower():
                raise AssertionError(f"Expected invalid credentials error, but got: '{err}'")

        self.record_step(page, ctx, steps, "Negative: Invalid Password Validation", step_wrong_password)

        # 3. Positive case: Valid login with user credentials
        def step_valid_login() -> None:
            login_page.goto()
            login_page.fill_credentials(username=ctx.username, password=ctx.password)
            login_page.submit()
            page.wait_for_url("**/profile", timeout=10000)
            if not page.url.endswith("/profile"):
                raise AssertionError(f"Expected URL to end with '/profile', but got: '{page.url}'")

        self.record_step(page, ctx, steps, "Positive: Successful Login & Redirect to /profile", step_valid_login)
