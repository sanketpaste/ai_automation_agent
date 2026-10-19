import os
import time
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, cast
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from agent.models import TestContext, AgentResult, PromptParseResult
from agent.orchestrator.prompt_parser import PromptParser
from agent.agents.base_agent import BaseAgent
from agent.agents.registration_agent import RegistrationAgent
from agent.agents.login_agent import LoginAgent
from agent.agents.profile_agent import ProfileAgent
from agent.agents.reporter_agent import ReporterAgent
from agent.utils.logger import log_info, log_error, mask_text
from agent.integrations.jira_client import JiraClient

REPORTS_BASE_DIR: Path = Path(__file__).resolve().parent.parent / "reports"

class OrchestratorAgent:
    """
    Main Orchestrator Agent.
    
    1. Parses user testing instructions via PromptParser (LLM / Regex).
    2. Validates parameters with Pydantic.
    3. Handles Jira status checks and natural language ticket creation.
    4. Runs sub-agents in sequence: RegistrationAgent -> LoginAgent -> ProfileAgent.
    5. Dispatches results to ReporterAgent for report.json and interactive HTML generation.
    6. Automatically attaches screenshots and reproduction details to Jira bug tickets on test failures.
    """

    def __init__(self, name: str = "OrchestratorAgent", jira_client: Optional[JiraClient] = None) -> None:
        self.name: str = name
        self.parser: PromptParser = PromptParser()
        self.jira_client: JiraClient = jira_client or JiraClient()
        self.reporter: ReporterAgent = ReporterAgent()
        self.last_results: Optional[List[AgentResult]] = None
        self.last_ctx: Optional[TestContext] = None
        self.last_report_info: Optional[Dict[str, Any]] = None

    def process_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Processes prompt, runs target sub-agents in sequence, and generates reports.
        """
        # 1. Parse prompt
        parse_result: PromptParseResult = self.parser.parse(prompt)

        # 2. Handle Jira Status / Verification
        if parse_result.intent == "jira_status":
            return self._handle_jira_status()

        # 3. Handle Jira Ticket Creation
        if parse_result.intent == "jira_create":
            return self._handle_jira_ticket(parse_result)

        # 4. Validate required test parameters
        if not parse_result.success or not parse_result.project_url or not parse_result.username or not parse_result.password:
            missing_text = ""
            if parse_result.missing_fields:
                missing_text = f" Missing fields: {', '.join(parse_result.missing_fields)}."
            return {
                "success": False,
                "reply": parse_result.error_message or (
                    f"Please provide the project URL, username, and password.{missing_text}\n"
                    f"Example: `Test the project: http://localhost:4000 with login credentials: username demo and password Demo@1234`"
                ),
                "report_url": None,
                "screenshots": [],
                "agent_results": []
            }

        # 5. Setup test execution context
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir: Path = REPORTS_BASE_DIR / timestamp
        headless_env: str = os.getenv("HEADLESS", "true").lower()
        headless: bool = headless_env not in ("false", "0", "no")

        ctx: TestContext = TestContext(
            project_url=parse_result.project_url,
            username=parse_result.username,
            password=parse_result.password,
            headless=headless,
            timestamp=timestamp,
            report_dir=report_dir,
            flows=parse_result.flows
        )

        flow_names = ", ".join(ctx.flows)
        log_info(
            f"[{self.name}] Starting execution for flows [{flow_names}] on {ctx.project_url} with user '{ctx.username}'",
            ctx.password
        )

        overall_start: float = time.time()
        agent_results: List[AgentResult] = []

        # 6. Execute sub-agents in sequence using Playwright
        with sync_playwright() as pw:
            browser: Browser = pw.chromium.launch(
                headless=ctx.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context: BrowserContext = browser.new_context(
                viewport={"width": 1280, "height": 800}
            )
            page: Page = context.new_page()
            page.set_default_timeout(30000)

            try:
                agent_results = self._run_subagents(page, ctx)
            finally:
                context.close()
                browser.close()

        total_duration_sec: float = round(time.time() - overall_start, 2)

        # 7. Generate reports via ReporterAgent
        report_info: Dict[str, Any] = self.reporter.generate(
            ctx=ctx,
            results=agent_results,
            total_duration_sec=total_duration_sec
        )

        self.last_results = agent_results
        self.last_ctx = ctx
        self.last_report_info = report_info

        # 8. Check for Jira ticket creation on failure or suggestions
        reply_message: str = str(report_info.get("chat_summary", ""))
        jira_note: Optional[str] = self._generate_jira_prompt_recommendation(agent_results, report_info)
        if jira_note:
            reply_message = f"{reply_message}\n\n{jira_note}"

        return {
            "success": bool(report_info.get("all_passed", False)),
            "reply": reply_message,
            "report_url": report_info.get("html_url"),
            "screenshots": report_info.get("screenshots", []),
            "agent_results": [r.model_dump() for r in agent_results]
        }

    def _run_subagents(self, page: Page, ctx: TestContext) -> List[AgentResult]:
        """Runs the configured sub-agents in order: Registration -> Login -> Profile."""
        results: List[AgentResult] = []
        flow_set = set(ctx.flows)

        subagent_map: List[tuple[str, BaseAgent]] = [
            ("registration", RegistrationAgent()),
            ("login", LoginAgent()),
            ("profile", ProfileAgent()),
        ]

        for flow_key, subagent in subagent_map:
            if flow_key in flow_set:
                log_info(f"[{self.name}] Running sub-agent: {subagent.name}", ctx.password)
                flow_result: AgentResult = subagent.run(ctx, page=page)
                results.append(flow_result)

        return results

    def _handle_jira_status(self) -> Dict[str, Any]:
        """Tests Jira connection and returns status."""
        if not self.jira_client.config.is_configured():
            missing = self.jira_client.config.get_missing_fields()
            return {
                "success": False,
                "reply": (
                    f"### ⚙️ Jira Integration Not Configured\n\n"
                    f"Please configure your `.env` file with Jira Cloud credentials:\n"
                    + "\n".join(f"- `{m}`" for m in missing)
                ),
                "report_url": None,
                "screenshots": [],
                "agent_results": []
            }

        conn_res = self.jira_client.validate_connection()
        if not conn_res.get("success", False):
            return {
                "success": False,
                "reply": f"### ❌ Jira Authentication Failed\n\nError: `{conn_res.get('error')}`\nPlease verify your Jira credentials.",
                "report_url": None,
                "screenshots": [],
                "agent_results": []
            }

        user_name = conn_res.get("display_name", self.jira_client.config.email)
        proj_res = self.jira_client.validate_project()
        proj_ok = proj_res.get("success", False)
        proj_name = proj_res.get("project_name", self.jira_client.config.project_key)
        proj_err = proj_res.get("error", "Invalid project")
        proj_status = f"✅ Project `{self.jira_client.config.project_key}` ({proj_name})" if proj_ok else f"⚠️ Project `{self.jira_client.config.project_key}` invalid: {proj_err}"

        return {
            "success": True,
            "reply": (
                f"### 🔗 Jira Cloud Connection Verified\n\n"
                f"- **Jira Instance**: [{self.jira_client.config.base_url}]({self.jira_client.config.base_url})\n"
                f"- **Authenticated User**: `{user_name}`\n"
                f"- **Project**: {proj_status}\n"
                f"- **Default Issue Type**: `{self.jira_client.config.default_issue_type}`\n\n"
                f"You can create bug tickets by typing: `Create Jira ticket for the failed login flow`."
            ),
            "report_url": None,
            "screenshots": [],
            "agent_results": []
        }

    def _handle_jira_ticket(self, parse_result: PromptParseResult) -> Dict[str, Any]:
        """Processes request to create Jira ticket from recent execution results."""
        if not self.jira_client.config.is_configured():
            return {
                "success": False,
                "reply": "### ⚙️ Jira is not configured in your `.env`. Please add `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, and `JIRA_PROJECT_KEY`.",
                "report_url": None,
                "screenshots": [],
                "agent_results": []
            }

        target_flow_name = parse_result.jira_target_flow
        issue_type = parse_result.jira_issue_type or self.jira_client.config.default_issue_type or "Task"
        include_screenshots = parse_result.jira_include_screenshots

        # Retrieve flow data
        results = self.last_results
        report_data = self.last_report_info
        ctx = self.last_ctx

        flow_name: str = ""
        project_url: str = ""
        username: str = ""
        error_message: str = ""
        failed_steps: List[Dict[str, Any]] = []
        report_dir: Optional[Path] = None
        report_url_path: str = ""

        # Check if in-memory results have a matching failure
        has_in_memory_failure = False
        target_agent_res: Optional[AgentResult] = None
        if results and ctx and report_data:
            target_agent_res = self._find_target_agent_result(results, target_flow_name)
            if target_agent_res and any(not s.passed for s in target_agent_res.steps):
                has_in_memory_failure = True

        if not has_in_memory_failure:
            latest = self._get_latest_report(target_flow=target_flow_name, require_failure=True)
            if not latest:
                return {
                    "success": False,
                    "reply": "No test runs found to create a Jira ticket from. Please run a test first!",
                    "report_url": None,
                    "screenshots": [],
                    "agent_results": []
                }
            report_dir = Path(str(latest["_dir"]))
            report_url_path = f"/reports/{latest['timestamp']}/report.html"
            target_flow_data = self._find_flow_in_dict(latest, target_flow_name)
            if not target_flow_data:
                return {
                    "success": False,
                    "reply": f"Could not find matching flow '{target_flow_name}' in latest report.",
                    "report_url": report_url_path,
                    "screenshots": [],
                    "agent_results": []
                }
            flow_name = str(target_flow_data.get("name", "Test Flow"))
            project_url = str(latest.get("project_url", ""))
            username = str(latest.get("username", ""))
            error_message = str(target_flow_data.get("error", "Flow failed during execution"))
            failed_steps = [s for s in target_flow_data.get("steps", []) if not s.get("passed", False)]
        else:
            assert target_agent_res is not None
            assert ctx is not None
            assert report_data is not None
            flow_name = target_agent_res.agent_name
            project_url = ctx.project_url
            username = ctx.username
            error_message = target_agent_res.error or "Flow encountered assertion failure"
            failed_steps = [
                {
                    "name": s.name,
                    "error": s.error,
                    "duration_ms": s.duration_ms,
                    "screenshot": s.screenshot_path
                }
                for s in target_agent_res.steps if not s.passed
            ]
            report_dir = ctx.report_dir
            report_url_path = str(report_data.get("html_url", ""))

        # Build issue summary and description
        first_step_err = failed_steps[0].get("name", "") if failed_steps else "Failure"
        summary = f"[{issue_type}] {flow_name} Failure: {first_step_err}"

        description_lines = [
            f"h2. AI Automation Test Failure: {flow_name}",
            f"*Target Project*: {project_url}",
            f"*Test Account*: {username}",
            f"*Error*: {error_message}",
            "",
            "h3. Failed Steps & Reproduction:",
        ]
        for idx, step in enumerate(failed_steps, 1):
            s_name = step.get("name", "Step")
            s_err = step.get("error", "Error")
            s_dur = step.get("duration_ms", 0)
            description_lines.append(f"{idx}. *{s_name}* ({s_dur}ms) - {s_err}")

        if report_url_path:
            description_lines.extend(["", "h3. Test Report Artifacts:", f"View full HTML execution report: {report_url_path}"])

        description = "\n".join(description_lines)

        res = self.jira_client.create_issue(
            summary=summary,
            description=description,
            issue_type=issue_type,
            check_duplicates=True
        )

        if not res.get("success", False):
            return {
                "success": False,
                "reply": f"### ❌ Failed to Create Jira Ticket\n\nError: `{res.get('error', 'Unknown Jira API error')}`",
                "report_url": None,
                "screenshots": [],
                "agent_results": []
            }

        ticket_key = str(res.get("key", ""))
        ticket_url = str(res.get("url", f"{self.jira_client.config.base_url}/browse/{ticket_key}"))
        is_duplicate = bool(res.get("is_duplicate", False))
        created_summary = str(res.get("summary", summary))
        created_type = str(res.get("issue_type", issue_type))

        # Upload screenshots and execution report
        uploaded_attachments: List[str] = []
        if include_screenshots and report_dir and ticket_key:
            # 1. Collect candidate screenshot files
            paths_to_upload: List[Path] = []
            for step in failed_steps:
                shot_filename = step.get("screenshot")
                if shot_filename:
                    candidates = [
                        Path(str(shot_filename)),
                        report_dir / Path(str(shot_filename)).name,
                        report_dir / "screenshots" / Path(str(shot_filename)).name
                    ]
                    for cand in candidates:
                        if cand.is_file() and cand not in paths_to_upload:
                            paths_to_upload.append(cand)
                            break

            # Fallback: if no specific step screenshot resolved, collect any png in report_dir
            if not paths_to_upload and report_dir.is_dir():
                for p in sorted(report_dir.glob("*.png")):
                    if p.is_file() and p not in paths_to_upload:
                        paths_to_upload.append(p)

            # Upload screenshots
            for shot_path in paths_to_upload:
                up_res = self.jira_client.upload_attachment(ticket_key, shot_path)
                if up_res.get("success"):
                    uploaded_attachments.append(str(up_res.get("filename", shot_path.name)))
                else:
                    log_error(f"[{self.name}] Failed to upload screenshot '{shot_path.name}': {up_res.get('error')}")

            # Also upload report.html if present
            html_report = report_dir / "report.html"
            if html_report.is_file():
                html_res = self.jira_client.upload_attachment(ticket_key, html_report)
                if html_res.get("success"):
                    uploaded_attachments.append(html_report.name)
                else:
                    log_error(f"[{self.name}] Failed to upload report HTML '{html_report.name}': {html_res.get('error')}")

        dup_badge = " *(Existing Issue)*" if is_duplicate else " *(Created)*"
        attach_msg = f"\n- **Attachments**: {', '.join(uploaded_attachments)}" if uploaded_attachments else "\n- **Attachments**: None"

        return {
            "success": True,
            "reply": (
                f"### 🎫 Jira {created_type} Logged{dup_badge}\n\n"
                f"- **Ticket Key**: [{ticket_key}]({ticket_url})\n"
                f"- **Summary**: `{created_summary}`\n"
                f"- **Status**: Successfully synced to project `{self.jira_client.config.project_key}`\n"
                f"{attach_msg}\n\n"
                f"Click the ticket key above to open the issue in Jira Cloud."
            ),
            "report_url": None,
            "screenshots": [],
            "agent_results": []
        }

    def _generate_jira_prompt_recommendation(
        self,
        results: List[AgentResult],
        report_info: Dict[str, Any]
    ) -> Optional[str]:
        """Produces a suggestion card if tests failed and Jira is configured."""
        failed_flows = [r for r in results if not r.passed]
        if not failed_flows or not self.jira_client.config.is_configured():
            return None

        flow_names = ", ".join(f"`{f.agent_name}`" for f in failed_flows)
        return (
            f"> 💡 **Jira Integration Ready**: One or more flows failed ({flow_names}).\n"
            f"> Type `Create Jira bug for {failed_flows[0].agent_name}` to automatically file an issue with logs & screenshots!"
        )

    def _find_target_agent_result(
        self,
        results: List[AgentResult],
        target_flow: Optional[str]
    ) -> Optional[AgentResult]:
        """Finds matching failed AgentResult."""
        failed = [r for r in results if not r.passed]
        if not failed:
            if results:
                return results[0]
            return None

        if not target_flow or target_flow == "all":
            return failed[0]

        target_lower = target_flow.lower()
        for r in failed:
            if target_lower in r.agent_name.lower():
                return r

        return failed[0]

    def _find_flow_in_dict(
        self,
        report_data: Dict[str, Any],
        target_flow: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        flows = cast(List[Dict[str, Any]], report_data.get("flows", []))
        failed = [f for f in flows if not f.get("passed", False)]
        if not failed:
            return flows[0] if flows else None

        if not target_flow or target_flow == "all":
            return failed[0]

        target_lower = target_flow.lower()
        for f in failed:
            if target_lower in str(f.get("name", "")).lower():
                return f

        return failed[0]

    def _get_latest_report(
        self,
        target_flow: Optional[str] = None,
        require_failure: bool = False
    ) -> Optional[Dict[str, Any]]:
        if not REPORTS_BASE_DIR.exists():
            return None
        dirs = sorted([d for d in REPORTS_BASE_DIR.iterdir() if d.is_dir()], key=lambda p: p.name, reverse=True)
        fallback: Optional[Dict[str, Any]] = None

        for d in dirs:
            report_file = d / "report.json"
            if report_file.is_file():
                try:
                    with open(report_file, "r", encoding="utf-8") as f:
                        data = cast(Dict[str, Any], json.load(f))
                        data["_dir"] = str(d)
                        if fallback is None:
                            fallback = data

                        if require_failure:
                            flows = cast(List[Dict[str, Any]], data.get("flows", []))
                            for flow in flows:
                                flow_name = str(flow.get("name", "")).lower()
                                if target_flow and target_flow != "all":
                                    if target_flow.lower() in flow_name and not flow.get("passed", True):
                                        return data
                                else:
                                    if not flow.get("passed", True):
                                        return data
                        else:
                            return data
                except Exception:
                    continue
        return fallback
