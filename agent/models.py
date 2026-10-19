from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

class TestContext(BaseModel):
    """Execution context passed to the automation agent."""
    project_url: str = Field(..., description="Target base URL of the project")
    username: str = Field(..., description="Username or email for testing")
    password: str = Field(..., description="Password for authentication")
    headless: bool = Field(default=True, description="Run browser headlessly")
    timestamp: str = Field(..., description="Run timestamp identifier")
    report_dir: Path = Field(..., description="Output directory for reports and screenshots")
    flows: List[str] = Field(default_factory=lambda: ["registration", "login", "profile"], description="Test flows to execute")

    model_config = {"arbitrary_types_allowed": True}

class StepResult(BaseModel):
    """Result of an individual test action or assertion."""
    name: str = Field(..., description="Description of the test step")
    passed: bool = Field(..., description="Whether the step succeeded")
    duration_ms: int = Field(..., description="Execution duration in milliseconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    screenshot_path: Optional[str] = Field(default=None, description="Path to screenshot artifact")

class AgentResult(BaseModel):
    """Result of an entire agent execution flow."""
    agent_name: str = Field(..., description="Name of the flow or agent")
    passed: bool = Field(..., description="Whether all steps in the flow passed")
    duration_ms: int = Field(..., description="Total execution time in milliseconds")
    steps: List[StepResult] = Field(default_factory=list, description="List of step results")
    error: Optional[str] = Field(default=None, description="Top-level error message if the flow crashed")

class JiraTicketResult(BaseModel):
    """Result of Jira issue creation or search."""
    success: bool
    key: Optional[str] = None
    url: Optional[str] = None
    summary: Optional[str] = None
    issue_type: Optional[str] = None
    is_duplicate: bool = False
    error: Optional[str] = None
    message: Optional[str] = None
    attachments: List[str] = Field(default_factory=list)

class PromptParseResult(BaseModel):
    """Result of extracting URL, credentials, target flows, or Jira operations from user prompt."""
    success: bool
    intent: str = Field(default="test_execution", description="'test_execution', 'jira_create', or 'jira_status'")
    project_url: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    flows: List[str] = Field(default_factory=lambda: ["registration", "login", "profile"], description="Target test flows")
    jira_issue_type: Optional[str] = Field(default=None, description="Requested Jira issue type, e.g. Bug or Task")
    jira_target_flow: Optional[str] = Field(default=None, description="Target test flow for ticket creation")
    jira_include_screenshots: bool = Field(default=True, description="Whether to attach failure screenshots")
    missing_fields: List[str] = Field(default_factory=list)
    error_message: Optional[str] = Field(default=None)

class OrchestratorResult(BaseModel):
    """Final aggregated test suite result returned to chat UI."""
    success: bool
    summary: str
    flows_executed: List[str] = Field(default_factory=list)
    agent_results: List[AgentResult] = Field(default_factory=list)
    report_json_path: str
    report_html_path: str
    screenshots: List[str] = Field(default_factory=list)
    duration_sec: float
