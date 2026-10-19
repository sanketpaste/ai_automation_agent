import abc
import time
from typing import List, Optional, Callable, Tuple
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

from agent.models import TestContext, StepResult, AgentResult
from agent.utils.logger import log_info, log_error
from agent.utils.screenshot import capture_screenshot

class BaseAgent(abc.ABC):
    """
    Abstract Base Agent defining lifecycle, step recording, timing,
    and automatic screenshot-on-failure capture.
    """

    def __init__(self, name: str) -> None:
        self.name: str = name

    @abc.abstractmethod
    def execute(self, page: Page, ctx: TestContext, steps: List[StepResult]) -> None:
        """Subclasses implement concrete step actions here."""
        pass

    def run(self, ctx: TestContext, page: Optional[Page] = None) -> AgentResult:
        """
        Executes the agent flow. Reuses active Page if supplied by orchestrator;
        otherwise launches a dedicated Playwright instance.
        """
        start_time: float = time.time()
        steps: List[StepResult] = []

        log_info(f"[{self.name}] Starting flow execution...", ctx.password)

        if page is not None:
            passed, flow_error = self._run_on_page(page, ctx, steps, start_time)
        else:
            with sync_playwright() as pw:
                browser: Browser = pw.chromium.launch(
                    headless=ctx.headless,
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
                context: BrowserContext = browser.new_context(viewport={"width": 1280, "height": 800})
                pg: Page = context.new_page()
                pg.set_default_timeout(30000)
                try:
                    passed, flow_error = self._run_on_page(pg, ctx, steps, start_time)
                finally:
                    context.close()
                    browser.close()

        duration_ms: int = int((time.time() - start_time) * 1000)
        status_str: str = "PASSED" if passed else "FAILED"
        log_info(f"[{self.name}] Completed in {duration_ms}ms ({status_str}).", ctx.password)

        return AgentResult(
            agent_name=self.name,
            passed=passed,
            duration_ms=duration_ms,
            steps=steps,
            error=flow_error
        )

    def _run_on_page(
        self,
        page: Page,
        ctx: TestContext,
        steps: List[StepResult],
        start_time: float
    ) -> Tuple[bool, Optional[str]]:
        flow_error: Optional[str] = None
        passed: bool = True
        try:
            self.execute(page, ctx, steps)
        except Exception as e:
            flow_error = str(e)
            passed = False
            log_error(f"[{self.name}] Encountered unhandled exception: {flow_error}", ctx.password)
            try:
                shot_name = capture_screenshot(
                    page,
                    ctx.report_dir,
                    f"{self.name.lower()}_unhandled_fail"
                )
                steps.append(StepResult(
                    name=f"{self.name} Unhandled Error",
                    passed=False,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error=flow_error,
                    screenshot_path=shot_name
                ))
            except Exception as shot_err:
                log_error(f"[{self.name}] Failed to capture error screenshot: {shot_err}")

        if any(not s.passed for s in steps):
            passed = False

        return passed, flow_error

    def record_step(
        self,
        page: Page,
        ctx: TestContext,
        steps: List[StepResult],
        step_name: str,
        action: Callable[[], None]
    ) -> None:
        """Executes a single test step, timing it and capturing a screenshot on failure."""
        step_start: float = time.time()
        try:
            action()
            step_duration: int = int((time.time() - step_start) * 1000)
            log_info(f"[{self.name}] Step '{step_name}' PASSED ({step_duration}ms)", ctx.password)
            steps.append(StepResult(
                name=step_name,
                passed=True,
                duration_ms=step_duration
            ))
        except Exception as err:
            step_duration = int((time.time() - step_start) * 1000)
            err_msg: str = str(err)
            log_error(f"[{self.name}] Step '{step_name}' FAILED ({step_duration}ms): {err_msg}", ctx.password)

            safe_name: str = "".join(c if c.isalnum() else "_" for c in step_name).strip("_")
            shot_file: Optional[str] = None
            try:
                shot_file = capture_screenshot(
                    page,
                    ctx.report_dir,
                    f"{self.name.lower()}_{safe_name}_fail"
                )
            except Exception:
                pass

            steps.append(StepResult(
                name=step_name,
                passed=False,
                duration_ms=step_duration,
                error=err_msg,
                screenshot_path=shot_file
            ))
