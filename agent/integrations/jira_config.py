import os
from urllib.parse import urlsplit, urlunsplit
from typing import Optional
from pydantic import BaseModel, Field

class JiraConfig(BaseModel):
    """Configuration settings for Jira integration."""
    base_url: str = Field(default="", description="Base Jira URL, e.g. https://company.atlassian.net")
    email: str = Field(default="", description="Atlassian account email")
    api_token: str = Field(default="", description="Atlassian API token or personal access token")
    project_key: str = Field(default="", description="Jira project key, e.g. QA or KAN")
    default_issue_type: str = Field(default="Bug", description="Default issue type, e.g. Bug or Task")
    auto_create_on_failure: bool = Field(default=False, description="Whether to auto-create tickets on test failure")

    @classmethod
    def from_env(cls) -> "JiraConfig":
        """Instantiates JiraConfig from environment variables, sanitizing inputs."""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass

        raw_url = os.getenv("JIRA_BASE_URL", "").strip()
        clean_url = ""
        if raw_url:
            parsed = urlsplit(raw_url)
            # If scheme missing, default to https
            scheme = parsed.scheme if parsed.scheme else "https"
            netloc = parsed.netloc if parsed.netloc else parsed.path.split("/")[0]
            clean_url = urlunsplit((scheme, netloc, "", "", "")).rstrip("/")

        email = os.getenv("JIRA_EMAIL", "").strip()
        token = os.getenv("JIRA_API_TOKEN", "").strip()
        project_key = os.getenv("JIRA_PROJECT_KEY", "").strip().upper()
        default_issue_type = os.getenv("JIRA_DEFAULT_ISSUE_TYPE", "Bug").strip() or "Bug"
        auto_create = os.getenv("JIRA_AUTO_CREATE_ON_FAILURE", "false").strip().lower() in ("true", "1", "yes")

        return cls(
            base_url=clean_url,
            email=email,
            api_token=token,
            project_key=project_key,
            default_issue_type=default_issue_type,
            auto_create_on_failure=auto_create
        )

    def is_configured(self) -> bool:
        """Returns True if essential credentials and endpoints are present."""
        return bool(self.base_url and self.api_token and self.project_key and (self.email or "atlassian.net" not in self.base_url))

    def get_missing_fields(self) -> list[str]:
        """Returns list of missing configuration parameters."""
        missing = []
        if not self.base_url:
            missing.append("JIRA_BASE_URL")
        if not self.api_token:
            missing.append("JIRA_API_TOKEN")
        if not self.project_key:
            missing.append("JIRA_PROJECT_KEY")
        if not self.email and "atlassian.net" in self.base_url:
            missing.append("JIRA_EMAIL")
        return missing
