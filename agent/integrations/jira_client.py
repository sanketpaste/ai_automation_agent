import os
import re
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
from requests.auth import HTTPBasicAuth

from agent.integrations.jira_config import JiraConfig
from agent.utils.logger import log_info, log_error

class JiraClient:
    """
    Client for interacting with the Jira REST API v2.
    Supports Jira Cloud (API token + email) and Data Center (PAT or Basic Auth).
    """

    def __init__(self, config: Optional[JiraConfig] = None) -> None:
        self.config: JiraConfig = config or JiraConfig.from_env()
        self._session: requests.Session = requests.Session()
        self._setup_auth()

    def _setup_auth(self) -> None:
        """Sets up authentication headers safely."""
        self._session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "AI-Automation-Tester/1.0"
        })
        if self.config.email and self.config.api_token:
            self._session.auth = HTTPBasicAuth(self.config.email, self.config.api_token)
        elif self.config.api_token:
            # Bearer token for Jira Data Center PAT
            self._session.headers["Authorization"] = f"Bearer {self.config.api_token}"

    def validate_connection(self) -> Dict[str, Any]:
        """
        Validates connection to Jira using the current user endpoint.
        Returns user profile info or structured error.
        """
        if not self.config.is_configured():
            missing = self.config.get_missing_fields()
            return {
                "success": False,
                "error": f"Jira configuration incomplete. Missing: {', '.join(missing)}"
            }

        endpoint = f"{self.config.base_url}/rest/api/2/myself"
        try:
            resp = self._session.get(endpoint, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                display_name = data.get("displayName", "User")
                email = data.get("emailAddress", self.config.email)
                log_info(f"[JiraClient] Connected successfully as '{display_name}' ({email})")
                return {
                    "success": True,
                    "display_name": display_name,
                    "email": email,
                    "raw": data
                }
            elif resp.status_code == 401:
                return {
                    "success": False,
                    "error": "Authentication failed (401 Unauthorized). Please check your JIRA_EMAIL and JIRA_API_TOKEN in .env."
                }
            elif resp.status_code == 403:
                return {
                    "success": False,
                    "error": "Access forbidden (403). Your Jira user account may lack API access permissions."
                }
            else:
                return {
                    "success": False,
                    "error": f"Jira responded with status code {resp.status_code}: {resp.text[:200]}"
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Failed to connect to Jira at {self.config.base_url}: {str(e)}"
            }

    def validate_project(self, project_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates that the project key exists and retrieves available issue types.
        """
        key = (project_key or self.config.project_key).upper()
        if not key:
            return {"success": False, "error": "No project key specified."}

        endpoint = f"{self.config.base_url}/rest/api/2/project/{key}"
        try:
            resp = self._session.get(endpoint, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                issue_types = [it.get("name", "") for it in data.get("issueTypes", []) if it.get("name")]
                return {
                    "success": True,
                    "project_name": data.get("name", key),
                    "project_key": key,
                    "issue_types": issue_types
                }
            elif resp.status_code == 404:
                return {
                    "success": False,
                    "error": f"Project key '{key}' not found on Jira instance. Please verify JIRA_PROJECT_KEY."
                }
            elif resp.status_code == 401:
                return {"success": False, "error": "Authentication failed (401 Unauthorized)."}
            elif resp.status_code == 403:
                return {"success": False, "error": f"Access forbidden (403) for project '{key}'."}
            else:
                return {
                    "success": False,
                    "error": f"Project validation failed with status {resp.status_code}: {resp.text[:200]}"
                }
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Network error validating project '{key}': {str(e)}"}

    def find_existing_issue(self, summary: str, project_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Searches for an open issue with an identical or matching summary to prevent duplicate ticket creation.
        Supports both Jira Cloud (/rest/api/3/search/jql) and Jira Server/DC (/rest/api/2/search).
        """
        key = (project_key or self.config.project_key).upper()
        # Clean summary for JQL: escape quotes and special characters
        clean_summary = re.sub(r'["\\]', '', summary).strip()
        # Take first 50 chars for summary search to avoid JQL length issues
        search_term = clean_summary[:50]
        jql = f'project = "{key}" AND summary ~ "{search_term}" AND statusCategory != Done ORDER BY created DESC'

        endpoints = [
            f"{self.config.base_url}/rest/api/3/search/jql",
            f"{self.config.base_url}/rest/api/2/search"
        ]
        params: Dict[str, Any] = {
            "jql": jql,
            "maxResults": 1,
            "fields": "key,summary,status,issuetype,created"
        }
        for endpoint in endpoints:
            try:
                resp = self._session.get(endpoint, params=params, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    issues = data.get("issues", [])
                    if issues:
                        issue = issues[0]
                        issue_key = issue.get("key", "")
                        fields = issue.get("fields", {})
                        return {
                            "key": issue_key,
                            "url": f"{self.config.base_url}/browse/{issue_key}",
                            "summary": fields.get("summary", ""),
                            "status": fields.get("status", {}).get("name", "Open")
                        }
                    return None
            except Exception as e:
                log_error(f"[JiraClient] Deduplication search via {endpoint} error: {e}")
        return None

    def create_issue(
        self,
        summary: str,
        description: str,
        issue_type: Optional[str] = None,
        project_key: Optional[str] = None,
        labels: Optional[List[str]] = None,
        check_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        Creates a new Jira issue using REST API v2.
        """
        if not self.config.is_configured():
            missing = self.config.get_missing_fields()
            return {
                "success": False,
                "error": f"Jira configuration incomplete. Missing: {', '.join(missing)}"
            }

        key = (project_key or self.config.project_key).upper()
        selected_type = issue_type or self.config.default_issue_type or "Task"

        # Resolve issue type against project's allowed types
        proj_val = self.validate_project(key)
        if proj_val.get("success") and proj_val.get("issue_types"):
            avail_types = proj_val["issue_types"]
            matched = next((t for t in avail_types if t.lower() == selected_type.lower()), None)
            if matched:
                selected_type = matched
            elif "Task" in avail_types:
                selected_type = "Task"
            elif avail_types:
                selected_type = avail_types[0]

        # Deduplication check
        if check_duplicates:
            existing = self.find_existing_issue(summary, project_key=key)
            if existing:
                log_info(f"[JiraClient] Duplicate open issue found: {existing['key']}")
                return {
                    "success": True,
                    "key": existing["key"],
                    "url": existing["url"],
                    "is_duplicate": True,
                    "message": f"An open ticket already exists for this issue: {existing['key']} ({existing['url']})"
                }

        # Build payload
        issue_labels = labels or ["ai-automation-test"]
        payload: Dict[str, Any] = {
            "fields": {
                "project": {"key": key},
                "summary": summary[:250],  # Jira max summary is 255
                "description": description,
                "issuetype": {"name": selected_type},
                "labels": issue_labels
            }
        }

        endpoint = f"{self.config.base_url}/rest/api/2/issue"
        try:
            resp = self._session.post(endpoint, json=payload, timeout=15)
            if resp.status_code in (200, 201):
                data = resp.json()
                created_key = data.get("key", "")
                browse_url = f"{self.config.base_url}/browse/{created_key}"
                log_info(f"[JiraClient] Created issue {created_key}: {browse_url}")
                return {
                    "success": True,
                    "key": created_key,
                    "id": data.get("id"),
                    "url": browse_url,
                    "is_duplicate": False,
                    "summary": summary,
                    "issue_type": selected_type
                }
            elif resp.status_code == 400:
                # Validation error, e.g. unknown issue type
                data = resp.json() if resp.text else {}
                errors = data.get("errors", {})
                error_msgs = data.get("errorMessages", [])
                err_detail = "; ".join(error_msgs) if error_msgs else str(errors)

                # If issue type was invalid, try fallback to "Task" or retrieve available types
                if "issuetype" in errors and selected_type != "Task":
                    log_info(f"[JiraClient] Retrying creation with issue type 'Task' due to: {err_detail}")
                    payload["fields"]["issuetype"] = {"name": "Task"}
                    retry_resp = self._session.post(endpoint, json=payload, timeout=15)
                    if retry_resp.status_code in (200, 201):
                        data = retry_resp.json()
                        created_key = data.get("key", "")
                        return {
                            "success": True,
                            "key": created_key,
                            "url": f"{self.config.base_url}/browse/{created_key}",
                            "is_duplicate": False,
                            "summary": summary,
                            "issue_type": "Task"
                        }

                return {
                    "success": False,
                    "error": f"Jira issue validation failed (400 Bad Request): {err_detail}"
                }
            elif resp.status_code == 401:
                return {"success": False, "error": "Authentication failed (401 Unauthorized)."}
            elif resp.status_code == 403:
                return {"success": False, "error": f"Permission denied (403) to create issues in project '{key}'."}
            else:
                return {
                    "success": False,
                    "error": f"Failed to create Jira issue (HTTP {resp.status_code}): {resp.text[:250]}"
                }
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Network failure contacting Jira: {str(e)}"}

    def upload_attachment(self, issue_key: str, file_path: Path | str) -> Dict[str, Any]:
        """
        Uploads an attachment (screenshot, report) to an existing Jira issue.
        """
        path = Path(file_path)
        if not path.is_file():
            return {"success": False, "error": f"Attachment file not found: {file_path}"}

        endpoint = f"{self.config.base_url}/rest/api/2/issue/{issue_key}/attachments"
        # Overwrite session-level Content-Type: application/json with None so requests
        # generates multipart/form-data with the correct boundary
        headers = {"X-Atlassian-Token": "no-check", "Content-Type": None}

        content_type, _ = mimetypes.guess_type(str(path))
        if not content_type:
            content_type = "application/octet-stream"

        try:
            with open(path, "rb") as f:
                files = {"file": (path.name, f, content_type)}
                resp = self._session.post(endpoint, headers=headers, files=files, timeout=20)  # type: ignore[arg-type]
                if resp.status_code in (200, 201):
                    log_info(f"[JiraClient] Uploaded attachment '{path.name}' to {issue_key}")
                    return {"success": True, "filename": path.name}
                else:
                    err_msg = f"Failed to upload attachment (HTTP {resp.status_code}): {resp.text[:200]}"
                    log_error(f"[JiraClient] {err_msg}")
                    return {
                        "success": False,
                        "error": err_msg
                    }
        except Exception as e:
            err_msg = f"Exception uploading attachment: {str(e)}"
            log_error(f"[JiraClient] {err_msg}")
            return {"success": False, "error": err_msg}
