from typing import List
from playwright.sync_api import Page

from agent.test_cases.base_case import BaseTestCase
from agent.models import TestContext, StepResult
from agent.pages.login_page import LoginPage

class LoginTestCases(BaseTestCase):
    """Encapsulates all test cases for User Authentication & Login."""

    def __init__(self) -> None:
        super().__init__(name="Login")

    def execute(self, page: Page, ctx: TestContext, steps: List[StepResult]) -> None:
        login_page: LoginPage = LoginPage(page, ctx.project_url)

        # Case 1: Empty credentials submission
        def case_empty_form() -> None:
            login_page.goto()
            login_page.fill_credentials(username="", password="")
            login_page.submit()
            err: str = login_page.get_error_text()
            if "required" not in err.lower():
                raise AssertionError(f"Expected empty form error, but got: '{err}'")

        self.record_step(page, ctx, steps, "Negative: Empty Form Validation", case_empty_form)

        # Case 2: Invalid password rejection
        def case_wrong_password() -> None:
            login_page.goto()
            login_page.fill_credentials(username=ctx.username, password="WrongPassword999!")
            login_page.submit()
            err: str = login_page.get_error_text()
            if "invalid" not in err.lower():
                raise AssertionError(f"Expected invalid credentials error, but got: '{err}'")

        self.record_step(page, ctx, steps, "Negative: Invalid Password Validation", case_wrong_password)

        # Case 3: Valid authentication with provided credentials and redirection check
        def case_valid_login() -> None:
            login_page.goto()
            login_page.fill_credentials(username=ctx.username, password=ctx.password)
            login_page.submit()
            page.wait_for_url("**/profile", timeout=10000)
            if not page.url.endswith("/profile"):
                raise AssertionError(f"Expected redirect to /profile, but current URL is '{page.url}'")

        self.record_step(page, ctx, steps, "Positive: Valid Login and Redirect to /profile", case_valid_login)
