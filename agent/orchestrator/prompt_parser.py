import os
import re
import json
from typing import Optional, List
from pydantic import BaseModel, Field

from agent.models import PromptParseResult

class ParsedPromptData(BaseModel):
    """Pydantic validation for extracted prompt parameters."""
    project_url: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    flows: List[str] = Field(default_factory=lambda: ["registration", "login", "profile"])

class PromptParser:
    """
    Parses user testing instructions into structured URL, credentials, and target flows.
    Uses Google Gemini when GEMINI_API_KEY is configured, or regex parsing with flow detection.
    """

    def __init__(self) -> None:
        self.gemini_key: str = (
            os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
        )
        self.anthropic_key: str = os.getenv("ANTHROPIC_API_KEY", "").strip()

    def parse(self, prompt: str) -> PromptParseResult:
        """Parses the prompt and returns a validated PromptParseResult."""
        if not prompt or not prompt.strip():
            return PromptParseResult(
                success=False,
                error_message="Prompt is empty. Please enter instructions in the format: "
                              "Test the project: <project_link> with login credentials: username <username> and password <password>"
            )

        # 1. Quick check for Jira specific intent (offline/deterministic fast path)
        jira_intent = self._detect_jira_intent(prompt)
        if jira_intent:
            return jira_intent

        # 2. Attempt LLM parsing if ANTHROPIC_API_KEY is available
        if self.anthropic_key:
            llm_res: Optional[PromptParseResult] = self._parse_with_anthropic(prompt)
            if llm_res and llm_res.success:
                return llm_res

        # 3. Attempt LLM parsing if Gemini API key is available
        if self.gemini_key:
            llm_res = self._parse_with_gemini(prompt)
            if llm_res and llm_res.success:
                return llm_res

        # 4. Fallback to Regex parser with flow detection
        return self._parse_with_regex(prompt)

    def _detect_jira_intent(self, prompt: str) -> Optional[PromptParseResult]:
        """Detects whether prompt requests Jira operations (status/connection or ticket creation)."""
        p = prompt.strip().lower()

        # Jira Status / Connection check
        if any(kw in p for kw in [
            "test jira connection", "check jira connection", "validate jira", 
            "jira status", "ping jira", "verify jira"
        ]):
            return PromptParseResult(
                success=True,
                intent="jira_status"
            )

        # Jira Ticket Creation
        is_jira_req = "jira" in p or "ticket" in p or ("bug" in p and any(action in p for action in ["create", "file", "raise", "log", "submit", "open"]))
        has_action = any(action in p for action in ["create", "file", "raise", "log", "submit", "open", "make", "generate", "post"])

        if is_jira_req and has_action:
            # Issue type detection
            issue_type: Optional[str] = None
            if "bug" in p:
                issue_type = "Bug"
            elif "task" in p:
                issue_type = "Task"
            elif "story" in p:
                issue_type = "Story"

            # Target flow detection
            target_flow: Optional[str] = None
            if "login" in p:
                target_flow = "login"
            elif "registration" in p or "register" in p:
                target_flow = "registration"
            elif "profile" in p:
                target_flow = "profile"
            elif "all" in p or "failed test" in p or "failures" in p or "failure" in p:
                target_flow = "all"

            include_screenshots = "without screenshot" not in p and "no screenshot" not in p

            return PromptParseResult(
                success=True,
                intent="jira_create",
                jira_issue_type=issue_type,
                jira_target_flow=target_flow,
                jira_include_screenshots=include_screenshots
            )

        return None

    def _detect_flows(self, prompt: str) -> List[str]:
        """Detects whether the prompt asks for specific flows or the entire test suite."""
        p = prompt.lower()

        # Check explicit "all" requests
        if any(k in p for k in ["all case", "all test", "all flows", "entire project", "whole project", "full suite", "every test"]):
            return ["registration", "login", "profile"]

        wants_login = any(k in p for k in ["test login", "login test", "login flow", "only login", "just login"])
        wants_reg = any(k in p for k in ["test registration", "test register", "registration flow", "register flow", "registration test", "only register", "only registration"])
        wants_profile = any(k in p for k in ["test profile", "profile flow", "profile test", "only profile", "just profile"])

        # Also loose keyword check if specific flow asked
        if not (wants_login or wants_reg or wants_profile):
            if "login" in p and not any(k in p for k in ["register", "profile", "test the project"]):
                wants_login = True
            elif ("register" in p or "registration" in p) and not any(k in p for k in ["login", "profile", "test the project"]):
                wants_reg = True
            elif "profile" in p and not any(k in p for k in ["login", "register", "test the project"]):
                wants_profile = True

        detected: List[str] = []
        if wants_reg:
            detected.append("registration")
        if wants_login:
            detected.append("login")
        if wants_profile:
            detected.append("profile")

        if detected:
            return detected

        # Default: execute all test cases
        return ["registration", "login", "profile"]

    def _parse_with_regex(self, prompt: str) -> PromptParseResult:
        """Extracts project_url, username, password, and flows using regex patterns."""
        url_match = re.search(
            r'(?:project:?|link:?|at:?)\s*(https?://[^\s,;]+|http://localhost:\d+|localhost:\d+)',
            prompt,
            re.IGNORECASE
        )
        if not url_match:
            url_match = re.search(r'(https?://[^\s,;]+)', prompt, re.IGNORECASE)

        user_match = re.search(r'(?:username|user):\s*([^\s,;]+)|username\s+([^\s,;]+)', prompt, re.IGNORECASE)
        pass_match = re.search(r'(?:password|pass):\s*([^\s,;]+)|password\s+([^\s,;]+)', prompt, re.IGNORECASE)

        project_url: Optional[str] = None
        if url_match:
            project_url = url_match.group(1).rstrip("/")
            if not project_url.startswith("http://") and not project_url.startswith("https://"):
                project_url = "http://" + project_url

        username: Optional[str] = None
        if user_match:
            username = (user_match.group(1) or user_match.group(2)).strip()

        password: Optional[str] = None
        if pass_match:
            password = (pass_match.group(1) or pass_match.group(2)).strip()

        flows = self._detect_flows(prompt)

        missing: List[str] = []
        if not project_url:
            missing.append("project link / URL")
        if not username:
            missing.append("username")
        if not password:
            missing.append("password")

        if missing:
            missing_text: str = ", ".join(missing)
            return PromptParseResult(
                success=False,
                project_url=project_url,
                username=username,
                password=password,
                flows=flows,
                missing_fields=missing,
                error_message=(
                    f"Missing required parameters: **{missing_text}**.\n\n"
                    "Please provide your prompt in the format:\n"
                    "`Test the project: <project_link> with login credentials: username <username> and password <password>`"
                )
            )

        try:
            validated = ParsedPromptData(
                project_url=project_url or "",
                username=username or "",
                password=password or "",
                flows=flows
            )
            return PromptParseResult(
                success=True,
                project_url=validated.project_url,
                username=validated.username,
                password=validated.password,
                flows=validated.flows
            )
        except Exception as e:
            return PromptParseResult(
                success=False,
                flows=flows,
                error_message=f"Validation failed: {e}"
            )

    def _parse_with_anthropic(self, prompt: str) -> Optional[PromptParseResult]:
        """Extracts parameters using the Anthropic Claude API."""
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.anthropic_key)
            system_instruction = (
                "You are an automated QA prompt parser.\n"
                "Extract 'project_url', 'username', 'password', and 'flows' (subset of ['registration', 'login', 'profile']).\n"
                "Respond ONLY with a valid JSON object in this format:\n"
                '{"project_url": "...", "username": "...", "password": "...", "flows": ["..."]}\n'
                "If a field cannot be found, set its value to null."
            )
            response = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
                max_tokens=256,
                system=system_instruction,
                messages=[{"role": "user", "content": prompt}]
            )
            content_block = response.content[0]
            text_output = getattr(content_block, "text", "")
            json_match = re.search(r'\{.*\}', text_output, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                p_url = data.get("project_url")
                u_name = data.get("username")
                p_word = data.get("password")
                flows = data.get("flows")
                if not isinstance(flows, list) or not flows:
                    flows = self._detect_flows(prompt)

                missing: List[str] = []
                if not p_url:
                    missing.append("project link / URL")
                if not u_name:
                    missing.append("username")
                if not p_word:
                    missing.append("password")

                if missing:
                    return PromptParseResult(
                        success=False,
                        flows=flows,
                        missing_fields=missing,
                        error_message=f"Missing required parameters: {', '.join(missing)}"
                    )

                return PromptParseResult(
                    success=True,
                    intent="test_execution",
                    project_url=str(p_url).rstrip("/"),
                    username=str(u_name),
                    password=str(p_word),
                    flows=[str(f).lower() for f in flows]
                )
        except Exception:
            return None
        return None

    def _parse_with_gemini(self, prompt: str) -> Optional[PromptParseResult]:
        """Extracts parameters, target flows, or Jira operations using the Google Gemini model."""
        try:
            from google import genai

            client = genai.Client(api_key=self.gemini_key)
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
            system_instruction = (
                "You are an automated QA prompt parser and Jira ticket dispatcher.\n"
                "Determine the user's intent: 'test_execution', 'jira_create', or 'jira_status'.\n"
                "1. If intent is 'jira_status': user wants to test, check, or validate Jira connection/status.\n"
                "2. If intent is 'jira_create': user wants to create a Jira ticket/bug/task for a test failure or test task.\n"
                "   Extract 'jira_issue_type' ('Bug', 'Task', or 'Story') and 'jira_target_flow' ('login', 'registration', 'profile', or 'all').\n"
                "3. If intent is 'test_execution': extract 'project_url', 'username', 'password', and 'flows' (subset of ['registration', 'login', 'profile']).\n\n"
                "Respond ONLY with a JSON object in this format:\n"
                '{"intent": "...", "project_url": "...", "username": "...", "password": "...", "flows": ["..."], "jira_issue_type": "...", "jira_target_flow": "..."}\n'
                "If a field cannot be found or is not applicable, set its value to null."
            )

            response = client.models.generate_content(
                model=model_name,
                contents=f"{system_instruction}\n\nUser prompt: {prompt}"
            )

            text_output = response.text or ""
            json_match = re.search(r'\{.*\}', text_output, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                intent = data.get("intent") or "test_execution"

                if intent == "jira_status":
                    return PromptParseResult(success=True, intent="jira_status")

                if intent == "jira_create":
                    return PromptParseResult(
                        success=True,
                        intent="jira_create",
                        jira_issue_type=data.get("jira_issue_type") or "Bug",
                        jira_target_flow=data.get("jira_target_flow") or "all",
                        jira_include_screenshots=True
                    )

                p_url = data.get("project_url")
                u_name = data.get("username")
                p_word = data.get("password")
                flows = data.get("flows")

                if not isinstance(flows, list) or not flows:
                    flows = self._detect_flows(prompt)

                missing: List[str] = []
                if not p_url:
                    missing.append("project link / URL")
                if not u_name:
                    missing.append("username")
                if not p_word:
                    missing.append("password")

                if missing:
                    return PromptParseResult(
                        success=False,
                        flows=flows,
                        missing_fields=missing,
                        error_message=f"Missing required parameters: {', '.join(missing)}"
                    )

                return PromptParseResult(
                    success=True,
                    intent="test_execution",
                    project_url=str(p_url).rstrip("/"),
                    username=str(u_name),
                    password=str(p_word),
                    flows=[str(f).lower() for f in flows]
                )
        except Exception:
            return None
        return None

