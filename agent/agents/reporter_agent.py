import json
from pathlib import Path
from typing import List, Dict, Any

from agent.models import TestContext, AgentResult
from agent.utils.logger import mask_text

class ReporterAgent:
    """
    Sub-agent responsible for aggregating test results, generating
    structured report.json and interactive report.html, collecting screenshots,
    and generating human-readable chat summaries.
    """

    def __init__(self, name: str = "ReporterAgent") -> None:
        self.name: str = name

    def generate(
        self,
        ctx: TestContext,
        results: List[AgentResult],
        total_duration_sec: float
    ) -> Dict[str, Any]:
        """
        Creates report.json, report.html, collects screenshots, and builds formatted chat summary.
        """
        ctx.report_dir.mkdir(parents=True, exist_ok=True)

        total_steps: int = sum(len(r.steps) for r in results)
        passed_steps: int = sum(sum(1 for s in r.steps if s.passed) for r in results)
        failed_steps: int = total_steps - passed_steps
        all_passed: bool = all(r.passed for r in results)

        # 1. Generate structured JSON report
        report_data: Dict[str, Any] = {
            "timestamp": ctx.timestamp,
            "project_url": ctx.project_url,
            "username": ctx.username,
            "success": all_passed,
            "total_duration_sec": total_duration_sec,
            "metrics": {
                "flows_count": len(results),
                "total_steps": total_steps,
                "passed_steps": passed_steps,
                "failed_steps": failed_steps
            },
            "flows": [
                {
                    "name": r.agent_name,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                    "error": mask_text(r.error or "", ctx.password) if r.error else None,
                    "steps": [
                        {
                            "name": s.name,
                            "passed": s.passed,
                            "duration_ms": s.duration_ms,
                            "error": mask_text(s.error or "", ctx.password) if s.error else None,
                            "screenshot": s.screenshot_path
                        }
                        for s in r.steps
                    ]
                }
                for r in results
            ]
        }

        json_path: Path = ctx.report_dir / "report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        # 2. Collect screenshots
        screenshots: List[str] = []
        for r in results:
            for s in r.steps:
                if s.screenshot_path:
                    screenshots.append(s.screenshot_path)

        # 3. Generate HTML report
        html_content: str = self._build_html(ctx, report_data)
        html_path: Path = ctx.report_dir / "report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 4. Generate readable chat summary
        chat_summary: str = self._build_summary(ctx, results, total_duration_sec, all_passed)

        return {
            "json_path": str(json_path),
            "html_path": str(html_path),
            "html_url": f"/reports/{ctx.timestamp}/report.html",
            "screenshots": [f"/reports/{ctx.timestamp}/{shot}" for shot in screenshots],
            "chat_summary": chat_summary,
            "all_passed": all_passed
        }

    def _build_summary(
        self,
        ctx: TestContext,
        results: List[AgentResult],
        total_duration_sec: float,
        all_passed: bool
    ) -> str:
        status_emoji: str = "✅ ALL FLOWS PASSED" if all_passed else "❌ SOME FLOWS FAILED"
        lines: List[str] = [
            f"### Test Execution Summary: {status_emoji}",
            f"- **Target Project**: `{ctx.project_url}`",
            f"- **Authenticated User**: `{ctx.username}`",
            f"- **Total Duration**: `{total_duration_sec:.2f}s`",
            "",
            "| Agent / Flow | Status | Duration | Steps Passed | Errors |",
            "| :--- | :---: | :---: | :---: | :--- |"
        ]

        for r in results:
            status_badge: str = "PASSED ✅" if r.passed else "FAILED ❌"
            passed_count: int = sum(1 for s in r.steps if s.passed)
            err_str: str = mask_text(r.error or "--", ctx.password)
            lines.append(
                f"| **{r.agent_name}** | {status_badge} | {r.duration_ms}ms | {passed_count}/{len(r.steps)} | {err_str} |"
            )

        lines.append("")
        lines.append(f"📄 **HTML Report**: [View Full Report](/reports/{ctx.timestamp}/report.html)")
        return "\n".join(lines)

    def _build_html(self, ctx: TestContext, data: Dict[str, Any]) -> str:
        metrics = data["metrics"]
        flows_html: List[str] = []

        for flow in data["flows"]:
            flow_status_class: str = "badge-pass" if flow["passed"] else "badge-fail"
            flow_status_text: str = "PASSED" if flow["passed"] else "FAILED"

            steps_rows: List[str] = []
            for s in flow["steps"]:
                step_status_class: str = "status-pass" if s["passed"] else "status-fail"
                step_status_text: str = "PASS" if s["passed"] else "FAIL"
                err_html: str = f'<div class="error-msg">⚠️ {s["error"]}</div>' if s["error"] else ""
                shot_html: str = f'<a href="{s["screenshot"]}" target="_blank" class="shot-link">📸 Screenshot</a>' if s["screenshot"] else "-"

                steps_rows.append(f"""
                <tr>
                    <td>{s["name"]}{err_html}</td>
                    <td><span class="{step_status_class}">{step_status_text}</span></td>
                    <td>{s["duration_ms"]}ms</td>
                    <td>{shot_html}</td>
                </tr>
                """)

            flows_html.append(f"""
            <div class="flow-card">
                <div class="flow-header">
                    <h3>{flow["name"]}</h3>
                    <div>
                        <span class="timing">{flow["duration_ms"]}ms</span>
                        <span class="{flow_status_class}">{flow_status_text}</span>
                    </div>
                </div>
                <table>
                    <thead>
                        <tr><th>Step</th><th>Result</th><th>Duration</th><th>Artifacts</th></tr>
                    </thead>
                    <tbody>
                        {"".join(steps_rows)}
                    </tbody>
                </table>
            </div>
            """)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Automation Test Report - {ctx.timestamp}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f19; color: #f1f5f9; padding: 30px; margin: 0; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        h1 {{ margin-top: 0; color: #38bdf8; font-size: 24px; }}
        .meta-strip {{ display: flex; gap: 20px; background: #1e293b; padding: 16px; border-radius: 8px; margin-bottom: 24px; font-size: 14px; flex-wrap: wrap; }}
        .badge-pass {{ background: #065f46; color: #6ee7b7; padding: 4px 10px; border-radius: 9999px; font-weight: bold; font-size: 12px; }}
        .badge-fail {{ background: #7f1d1d; color: #fca5a5; padding: 4px 10px; border-radius: 9999px; font-weight: bold; font-size: 12px; }}
        .status-pass {{ color: #10b981; font-weight: bold; font-size: 12px; }}
        .status-fail {{ color: #ef4444; font-weight: bold; font-size: 12px; }}
        .flow-card {{ background: #1e293b; border-radius: 8px; margin-bottom: 20px; overflow: hidden; border: 1px solid #334155; }}
        .flow-header {{ display: flex; justify-content: space-between; align-items: center; padding: 14px 20px; background: #0f172a; border-bottom: 1px solid #334155; }}
        .flow-header h3 {{ margin: 0; font-size: 16px; }}
        .timing {{ font-family: monospace; font-size: 13px; color: #94a3b8; margin-right: 12px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th, td {{ padding: 10px 18px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        th {{ background: rgba(0,0,0,0.2); color: #94a3b8; }}
        .error-msg {{ color: #f87171; font-size: 12px; margin-top: 4px; font-family: monospace; }}
        .shot-link {{ color: #38bdf8; text-decoration: none; font-size: 12px; }}
        .shot-link:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>AI Automation Test Report</h1>
        <div class="meta-strip">
            <div><strong>Target:</strong> {ctx.project_url}</div>
            <div><strong>Timestamp:</strong> {ctx.timestamp}</div>
            <div><strong>Duration:</strong> {data["total_duration_sec"]:.2f}s</div>
            <div><strong>Steps:</strong> {metrics["passed_steps"]}/{metrics["total_steps"]} Passed</div>
        </div>
        {"".join(flows_html)}
    </div>
</body>
</html>"""
