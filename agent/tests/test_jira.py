import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import requests

from agent.integrations.jira_config import JiraConfig
from agent.integrations.jira_client import JiraClient
from agent.orchestrator.prompt_parser import PromptParser
from agent.agent import AutomationAgent
from agent.models import PromptParseResult

@pytest.fixture
def mock_config() -> JiraConfig:
    return JiraConfig(
        base_url="https://mockcompany.atlassian.net",
        email="qa-tester@example.com",
        api_token="mock_token_12345",
        project_key="QA",
        default_issue_type="Bug",
        auto_create_on_failure=False
    )

@pytest.fixture
def jira_client(mock_config: JiraConfig) -> JiraClient:
    return JiraClient(config=mock_config)

# 1. Config validation tests
def test_jira_config_missing_fields() -> None:
    empty_cfg = JiraConfig(base_url="", email="", api_token="", project_key="")
    assert not empty_cfg.is_configured()
    missing = empty_cfg.get_missing_fields()
    assert "JIRA_BASE_URL" in missing
    assert "JIRA_API_TOKEN" in missing
    assert "JIRA_PROJECT_KEY" in missing

def test_jira_config_url_normalization() -> None:
    with patch.dict("os.environ", {
        "JIRA_BASE_URL": "https://myteam.atlassian.net/jira/software/projects/KAN/boards/1",
        "JIRA_EMAIL": "test@example.com",
        "JIRA_API_TOKEN": "secret",
        "JIRA_PROJECT_KEY": "kan"
    }):
        cfg = JiraConfig.from_env()
        assert cfg.base_url == "https://myteam.atlassian.net"
        assert cfg.project_key == "KAN"
        assert cfg.is_configured()

# 2. Connection validation tests
def test_validate_connection_success(jira_client: JiraClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "displayName": "QA Engineer",
        "emailAddress": "qa-tester@example.com"
    }

    with patch.object(jira_client._session, "get", return_value=mock_resp):
        res = jira_client.validate_connection()
        assert res["success"] is True
        assert res["display_name"] == "QA Engineer"
        assert res["email"] == "qa-tester@example.com"

def test_validate_connection_401_unauthorized(jira_client: JiraClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"

    with patch.object(jira_client._session, "get", return_value=mock_resp):
        res = jira_client.validate_connection()
        assert res["success"] is False
        assert "401" in res["error"]
        assert "JIRA_EMAIL" in res["error"]

def test_validate_connection_403_forbidden(jira_client: JiraClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Forbidden"

    with patch.object(jira_client._session, "get", return_value=mock_resp):
        res = jira_client.validate_connection()
        assert res["success"] is False
        assert "403" in res["error"]

def test_validate_connection_network_failure(jira_client: JiraClient) -> None:
    with patch.object(jira_client._session, "get", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        res = jira_client.validate_connection()
        assert res["success"] is False
        assert "Failed to connect" in res["error"]

# 3. Project validation tests
def test_validate_project_success(jira_client: JiraClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "name": "Quality Assurance",
        "key": "QA",
        "issueTypes": [{"name": "Bug"}, {"name": "Task"}, {"name": "Story"}]
    }

    with patch.object(jira_client._session, "get", return_value=mock_resp):
        res = jira_client.validate_project("QA")
        assert res["success"] is True
        assert res["project_name"] == "Quality Assurance"
        assert "Bug" in res["issue_types"]
        assert "Task" in res["issue_types"]

def test_validate_project_404_not_found(jira_client: JiraClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "Project not found"

    with patch.object(jira_client._session, "get", return_value=mock_resp):
        res = jira_client.validate_project("INVALID")
        assert res["success"] is False
        assert "not found" in res["error"].lower()

# 4. Issue creation tests
def test_create_issue_success(jira_client: JiraClient) -> None:
    mock_search = MagicMock()
    mock_search.status_code = 200
    mock_search.json.return_value = {"issues": []}

    mock_create = MagicMock()
    mock_create.status_code = 201
    mock_create.json.return_value = {"key": "QA-42", "id": "10042"}

    def side_effect_fn(url: str, *args, **kwargs):  # type: ignore
        if "search" in url:
            return mock_search
        return mock_create

    with patch.object(jira_client._session, "get", return_value=mock_search), \
         patch.object(jira_client._session, "post", return_value=mock_create):
        res = jira_client.create_issue(
            summary="Login button timeout",
            description="Detailed failure trace",
            issue_type="Bug"
        )
        assert res["success"] is True
        assert res["key"] == "QA-42"
        assert res["is_duplicate"] is False
        assert "https://mockcompany.atlassian.net/browse/QA-42" in res["url"]

def test_create_issue_deduplication(jira_client: JiraClient) -> None:
    mock_search = MagicMock()
    mock_search.status_code = 200
    mock_search.json.return_value = {
        "issues": [
            {
                "key": "QA-10",
                "fields": {
                    "summary": "Login button timeout",
                    "status": {"name": "In Progress"}
                }
            }
        ]
    }

    with patch.object(jira_client._session, "get", return_value=mock_search):
        res = jira_client.create_issue(
            summary="Login button timeout",
            description="Detailed failure trace",
            check_duplicates=True
        )
        assert res["success"] is True
        assert res["is_duplicate"] is True
        assert res["key"] == "QA-10"

def test_create_issue_invalid_issue_type_fallback(jira_client: JiraClient) -> None:
    mock_search = MagicMock()
    mock_search.status_code = 200
    mock_search.json.return_value = {"issues": []}

    mock_fail = MagicMock()
    mock_fail.status_code = 400
    mock_fail.json.return_value = {
        "errors": {"issuetype": "The issue type selected is invalid."},
        "errorMessages": []
    }

    mock_retry_success = MagicMock()
    mock_retry_success.status_code = 201
    mock_retry_success.json.return_value = {"key": "QA-55", "id": "10055"}

    with patch.object(jira_client._session, "get", return_value=mock_search), \
         patch.object(jira_client._session, "post", side_effect=[mock_fail, mock_retry_success]):
        res = jira_client.create_issue(
            summary="Invalid type test",
            description="Desc",
            issue_type="NonExistentType"
        )
        assert res["success"] is True
        assert res["key"] == "QA-55"
        assert res["issue_type"] == "Task"

# 5. Attachment upload tests
def test_upload_attachment(tmp_path: Path, jira_client: JiraClient) -> None:
    dummy_file = tmp_path / "screenshot.png"
    dummy_file.write_bytes(b"dummy_png_data")

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = [{"filename": "screenshot.png"}]

    with patch.object(jira_client._session, "post", return_value=mock_resp) as mock_post:
        res = jira_client.upload_attachment("QA-42", dummy_file)
        assert res["success"] is True
        assert res["filename"] == "screenshot.png"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"]["Content-Type"] is None
        assert call_kwargs["headers"]["X-Atlassian-Token"] == "no-check"

# 6. Prompt Parser Intent Routing tests
def test_prompt_parser_jira_intents() -> None:
    parser = PromptParser()

    # Login failure request
    r1 = parser.parse("Create a Jira ticket for the login test failure.")
    assert r1.intent == "jira_create"
    assert r1.jira_target_flow == "login"

    # Registration bug request
    r2 = parser.parse("Create a bug ticket for the registration failure.")
    assert r2.intent == "jira_create"
    assert r2.jira_issue_type == "Bug"
    assert r2.jira_target_flow == "registration"

    # All failed cases request
    r3 = parser.parse("Create Jira tickets for all failed test cases.")
    assert r3.intent == "jira_create"
    assert r3.jira_target_flow == "all"

    # Profile task request
    r4 = parser.parse("Create a Jira task to test the profile update flow.")
    assert r4.intent == "jira_create"
    assert r4.jira_issue_type == "Task"
    assert r4.jira_target_flow == "profile"

    # Status check
    r5 = parser.parse("Test Jira connection")
    assert r5.intent == "jira_status"

    # Normal test run prompt is NOT intercepted as Jira
    r6 = parser.parse("Test login flow for http://localhost:4000 with login credentials: username demo and password Demo@1234")
    assert r6.intent == "test_execution"
    assert r6.project_url == "http://localhost:4000"

# 7. Agent integration test with mock report and mock Jira client
def test_agent_handle_jira_ticket_with_report(tmp_path: Path, mock_config: JiraConfig) -> None:
    mock_jira = JiraClient(config=mock_config)

    mock_jira.create_issue = MagicMock(return_value={  # type: ignore
        "success": True,
        "key": "QA-88",
        "url": "https://mockcompany.atlassian.net/browse/QA-88",
        "summary": "[Bug] Login Failure: Negative Password Check",
        "is_duplicate": False
    })
    mock_jira.upload_attachment = MagicMock(return_value={"success": True})  # type: ignore

    agent = AutomationAgent(jira_client=mock_jira)

    # Mock report data
    mock_report = {
        "timestamp": "20261020_000000",
        "project_url": "http://localhost:4000",
        "success": False,
        "_dir": str(tmp_path),
        "flows": [
            {
                "name": "Login",
                "passed": False,
                "steps": [
                    {
                        "name": "Negative Password Check",
                        "passed": False,
                        "duration_ms": 350,
                        "error": "AssertionError: Expected error banner not visible",
                        "screenshot": "login_fail.png"
                    }
                ]
            }
        ]
    }

    # Create dummy screenshot in tmp_path
    (tmp_path / "login_fail.png").write_bytes(b"image_content")

    with patch.object(agent, "_get_latest_report", return_value=mock_report):
        parse_res = PromptParseResult(
            success=True,
            intent="jira_create",
            jira_target_flow="login",
            jira_issue_type="Bug",
            jira_include_screenshots=True
        )
        res = agent._handle_jira_ticket(parse_res)
        assert res["success"] is True
        assert "QA-88" in res["reply"]
        assert mock_jira.create_issue.called
        assert mock_jira.upload_attachment.called
