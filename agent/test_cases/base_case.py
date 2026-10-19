import abc
import time
from typing import List, Optional, Callable
from playwright.sync_api import Page

from agent.models import TestContext, StepResult, AgentResult
from agent.utils.logger import log_info, log_error
from agent.utils.screenshot import capture_screenshot

class BaseTestCase(abc.ABC):
    """
    Base test case runner providing step recording, timing,
    and automatic screenshot capture on failure.
    """

    def __init__(self, name: str = "TestCase") -> None:
        self.name: str = name

    @abc.abstractmethod
    def execute(self, page: Page, ctx: TestContext, steps: List[StepResult]) -> None:
        """Subclasses implement the concrete step actions here."""
        pass

    def run(self, page: Page, ctx: TestContext) -> AgentResult:
        """Executes all steps in this test case and returns an AgentResult."""
        start_time: float = time.time()
        steps: List[StepResult] = []
        flow_error: Optional[str] = None
        passed: bool = True

        log_info(f"[{self.name}] Starting test case execution...", ctx.password)

        try:
            self.execute(page, ctx, steps)
        except Exception as e:
            flow_error = str(e)
            passed = False
            log_error(f"[{self.name}] Encountered exception: {flow_error}", ctx.password)
            try:
                shot_name = capture_screenshot(
                    page,
                    ctx.report_dir,
                    f"{self.name.lower()}_exception"
                )
                steps.append(StepResult(
                    name=f"{self.name} Unhandled Exception",
                    passed=False,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error=flow_error,
                    screenshot_path=shot_name
                ))
            except Exception as shot_err:
                log_error(f"[{self.name}] Could not capture screenshot: {shot_err}")

        if any(not s.passed for s in steps):
            passed = False

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
            # Continue so subsequent independent checks or screenshot inspection can happen
