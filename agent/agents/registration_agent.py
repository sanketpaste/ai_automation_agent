from typing import List, Dict
from playwright.sync_api import Page

from agent.agents.base_agent import BaseAgent
from agent.models import TestContext, StepResult
from agent.pages.registration_page import RegistrationPage
from agent.utils.data_generator import generate_user

class RegistrationAgent(BaseAgent):
    """
    Sub-agent responsible for testing User Registration flows.
    Tests negative validation (empty fields, invalid email, password mismatch)
    and valid registration with unique generated user data.
    """

    def __init__(self) -> None:
        super().__init__(name="RegistrationAgent")

    def execute(self, page: Page, ctx: TestContext, steps: List[StepResult]) -> None:
        reg_page: RegistrationPage = RegistrationPage(page, ctx.project_url)

        # 1. Negative case: Empty form validation
        def step_empty_form() -> None:
            reg_page.goto()
            reg_page.fill_form(name="", email="", phone="", password="", confirm="")
            reg_page.submit()
            err: str = reg_page.get_error_text()
            if "required" not in err.lower():
                raise AssertionError(f"Expected empty form error, but got: '{err}'")

        self.record_step(page, ctx, steps, "Negative: Empty Form Validation", step_empty_form)

        # 2. Negative case: Invalid email format validation
        def step_invalid_email() -> None:
            reg_page.goto()
            reg_page.fill_form(
                name="Bad Email User",
                email="not-an-email",
                phone="1234567890",
                password="Password123",
                confirm="Password123"
            )
            reg_page.submit()
            err: str = reg_page.get_error_text()
            if "email" not in err.lower() and "format" not in err.lower():
                raise AssertionError(f"Expected invalid email error, but got: '{err}'")

        self.record_step(page, ctx, steps, "Negative: Invalid Email Format Validation", step_invalid_email)

        # 3. Negative case: Password mismatch validation
        def step_password_mismatch() -> None:
            reg_page.goto()
            reg_page.fill_form(
                name="Mismatch User",
                email="mismatch@test.com",
                phone="1234567890",
                password="Password123",
                confirm="PasswordDifferent!"
            )
            reg_page.submit()
            err: str = reg_page.get_error_text()
            if "match" not in err.lower():
                raise AssertionError(f"Expected password mismatch error, but got: '{err}'")

        self.record_step(page, ctx, steps, "Negative: Password Mismatch Validation", step_password_mismatch)

        # 4. Positive case: Valid registration with unique randomly generated user
        user_data: Dict[str, str] = generate_user()

        def step_valid_registration() -> None:
            reg_page.goto()
            reg_page.fill_form(
                name=user_data["name"],
                email=user_data["email"],
                phone=user_data["phone"],
                password=user_data["password"],
                confirm=user_data["password"]
            )
            reg_page.submit()
            msg: str = reg_page.get_success_text()
            if "successful" not in msg.lower():
                raise AssertionError(f"Expected registration success message, but got: '{msg}'")

        self.record_step(page, ctx, steps, "Positive: Successful Registration Flow", step_valid_registration)
