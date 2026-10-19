import time
from playwright.sync_api import Page
from agent.pages.login_page import LoginPage
from agent.pages.profile_page import ProfilePage

def test_profile_view_edit_and_persist(page: Page, base_url: str) -> None:
    """Verifies profile data view, edit, persistence on reload, and logout."""
    login = LoginPage(page, base_url)
    profile = ProfilePage(page, base_url)

    # 1. Login
    login.goto()
    login.fill_credentials(username="demo", password="Demo@1234")
    login.submit()
    page.wait_for_url("**/profile", timeout=10000)

    # 2. Assert initial profile displayed
    assert profile.get_displayed_name() != ""
    assert "@" in profile.get_displayed_email()

    # 3. Edit profile
    new_name: str = f"Demo User {int(time.time()) % 1000}"
    new_phone: str = "5551234567"
    profile.update_profile(new_name=new_name, new_phone=new_phone)
    assert profile.is_save_success_visible()

    # 4. Reload and assert persistence
    page.reload(wait_until="domcontentloaded")
    assert profile.get_displayed_name() == new_name
    assert profile.get_displayed_phone() == new_phone

    # 5. Logout
    profile.logout()
    page.wait_for_url("**/login", timeout=10000)
    assert page.url.endswith("/login")
