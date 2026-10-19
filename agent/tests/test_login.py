from playwright.sync_api import Page
from agent.pages.login_page import LoginPage

def test_login_empty_form_validation(page: Page, base_url: str) -> None:
    """Verifies that empty login credentials trigger validation error."""
    login = LoginPage(page, base_url)
    login.goto()
    login.submit()
    assert "required" in login.get_error_text().lower()

def test_login_invalid_password(page: Page, base_url: str) -> None:
    """Verifies that invalid password displays error."""
    login = LoginPage(page, base_url)
    login.goto()
    login.fill_credentials(username="demo", password="WrongPassword999!")
    login.submit()
    assert "invalid" in login.get_error_text().lower()

def test_login_success_and_redirect(page: Page, base_url: str) -> None:
    """Verifies that valid credentials authenticate and redirect to /profile."""
    login = LoginPage(page, base_url)
    login.goto()
    login.fill_credentials(username="demo", password="Demo@1234")
    login.submit()
    page.wait_for_url("**/profile", timeout=10000)
    assert page.url.endswith("/profile")
