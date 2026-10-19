from pathlib import Path
from playwright.sync_api import Page

def capture_screenshot(page: Page, destination_dir: Path, filename_prefix: str) -> str:
    """
    Captures a full page screenshot and saves it in the destination directory.
    Returns the relative path from the reports directory for clean links.
    """
    destination_dir.mkdir(parents=True, exist_ok=True)
    filename: str = f"{filename_prefix}.png"
    filepath: Path = destination_dir / filename
    page.screenshot(path=str(filepath), full_page=False)
    return filename
