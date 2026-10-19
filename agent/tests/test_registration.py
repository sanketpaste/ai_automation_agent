from playwright.sync_api import Page
from agent.pages.registration_page import RegistrationPage
from agent.utils.data_generator import generate_user

def test_registration_empty_form_validation(page: Page, base_url: str) -> None:
    """Verifies that submitting an empty registration form displays validation error."""
    reg = RegistrationPage(page, base_url)
    reg.goto()
    reg.submit()
    assert "required" in reg.get_error_text().lower()

def test_registration_invalid_email_validation(page: Page, base_url: str) -> None:
    """Verifies that an invalid email format produces validation error."""
    reg = RegistrationPage(page, base_url)
    reg.goto()
    reg.fill_form(name="John Doe", email="notanemail", phone="1234567890", password="Password123", confirm="Password123")
    reg.submit()
    assert "email" in reg.get_error_text().lower() or "format" in reg.get_error_text().lower()

def test_registration_password_mismatch_validation(page: Page, base_url: str) -> None:
    """Verifies that mismatched passwords produce validation error."""
    reg = RegistrationPage(page, base_url)
    reg.goto()
    reg.fill_form(name="John Doe", email="john@example.com", phone="1234567890", password="Password123", confirm="DiffPassword!")
    reg.submit()
    assert "match" in reg.get_error_text().lower()

def test_registration_success(page: Page, base_url: str) -> None:
    """Verifies successful registration with unique generated user credentials."""
    user = generate_user()
    reg = RegistrationPage(page, base_url)
    reg.goto()
    reg.fill_form(
        name=user["name"],
        email=user["email"],
        phone=user["phone"],
        password=user["password"],
        confirm=user["password"]
    )
    reg.submit()
    assert "successful" in reg.get_success_text().lower()
