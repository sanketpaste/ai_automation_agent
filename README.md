# AI Automation Tester

A multi-agent AI automation testing system built with **Playwright for Python**, **Flask**, and **pydantic**, featuring an interactive chat interface and a full test dummy application.

> 📖 **Documentation Links**:
> - [Project Architecture Guide (Technical Documentation)](PROJECT_ARCHITECTURE.md)
> - [Complete Hinglish Learning Guide](AI_AUTOMATION_TESTER_HINGLISH_GUIDE.md)

---
## 🛠️ Tech Stack

- **Python 3.11+** with strict type hints (`mypy --strict`)
- **Playwright for Python** (sync API)
- **pytest** + **pytest-playwright** for standalone flow tests
- **Flask** for the agent orchestrator and dummy web app
- **pydantic v2** for prompt and result validation
- **python-dotenv** for configuration
- `run.py` task runner

---

## 🚀 Setup & Installation


### 1. Create and Activate Virtual Environment

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
```

### 2. Install Dependencies & Playwright Browsers

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Environment Configuration

```bash
# Windows:
copy .env.example .env
# Linux/macOS:
cp .env.example .env
```

Optional settings inside `.env`:
```env
PORT=3000
HEADLESS=true
GEMINI_API_KEY=
```

---

## 🕹️ Task Runner (`run.py`)

```bash
python run.py dummy     # Start dummy web app on http://127.0.0.1:4000
python run.py agent     # Start agent server on http://127.0.0.1:3000
python run.py dev       # Start both servers together
python run.py test      # Run all pytest flow specifications
```

---

## 💬 Triggering Tests from `/chat`

1. Run both servers:
   ```bash
   python run.py dev
   ```
2. Open your browser at:
   👉 **`http://localhost:3000/chat`**
3. Enter your prompt in the required format:
   ```text
   Test the project: http://localhost:4000 with login credentials: username demo and password Demo@1234
   ```
4. The **Orchestrator Agent** validates parameters and executes:
   - **RegistrationAgent**: tests negative validations (empty form, invalid email, password mismatch) and registers a random unique user.
   - **LoginAgent**: tests negative validations (empty form, invalid password) and authenticates with the provided credentials.
   - **ProfileAgent**: verifies loaded user info, updates name/phone, verifies persistence across page reload, and tests logout.
   - **ReporterAgent**: produces `report.json` and `report.html` inside `agent/reports/<timestamp>/`.

---

## ➕ How to Add a New Agent (e.g. "Checkout")

Adding new test scenarios to the multi-agent system is modular:

### 1. Create the Page Object Model (`agent/pages/checkout_page.py`)
```python
from playwright.sync_api import Page, Locator

class CheckoutPage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.checkout_btn: Locator = self.page.get_by_test_id("checkout-submit")
        self.order_success: Locator = self.page.get_by_test_id("order-success")

    def goto(self) -> None:
        self.page.goto(f"{self.base_url}/checkout")

    def place_order(self) -> None:
        self.checkout_btn.click()
```

### 2. Create the Sub-Agent (`agent/agents/checkout_agent.py`)
```python
from typing import List
from playwright.sync_api import Page
from agent.agents.base_agent import BaseAgent
from agent.models import TestContext, StepResult
from agent.pages.checkout_page import CheckoutPage

class CheckoutAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="CheckoutAgent")

    def execute(self, page: Page, ctx: TestContext, steps: List[StepResult]) -> None:
        checkout = CheckoutPage(page, ctx.project_url)

        def step_place_order() -> None:
            checkout.goto()
            checkout.place_order()
            checkout.order_success.wait_for(state="visible", timeout=10000)

        self.record_step(page, ctx, steps, "Checkout: Place Order and Assert Confirmation", step_place_order)
```

### 3. Register in `OrchestratorAgent` (`agent/orchestrator/orchestrator_agent.py`)
Add `("checkout", CheckoutAgent())` to `subagent_map` inside `_run_subagents`. The orchestrator will now execute `CheckoutAgent` whenever `checkout` is specified or as part of full test runs!

---

## 🎫 Jira Integration Guide

The agent seamlessly integrates with **Jira Cloud** (and Data Center) to validate connections, file bugs for test failures (with logs and screenshots), and create QA tasks directly through conversational prompts.

### 1. Prerequisites & Finding Your Settings

1. **Jira Base URL**:
   - The base root of your Jira instance (e.g., `https://your-company.atlassian.net`).
2. **Jira Project Key**:
   - In Jira, open your project. The key is the uppercase prefix (e.g., in `KAN-1` or `QA-42`, the key is `KAN` or `QA`).
   - Also visible under **Project settings** > **Details** > **Key**.
3. **Atlassian API Token**:
   - Go to: [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
   - Click **Create API token**, name it (e.g., `ai-tester`), and copy the generated token.
   - *Security Note*: Never share or commit your token into Git.

### 2. Configure `.env`

Add the following block to your `.env` file:

```env
# Jira Integration Configuration
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token
JIRA_PROJECT_KEY=KAN
JIRA_DEFAULT_ISSUE_TYPE=Bug
JIRA_AUTO_CREATE_ON_FAILURE=false
```

### 3. Validating the Jira Connection

You can test connectivity without creating any tickets:

1. **Via Chat Interface**:
   - Type: `"Test Jira connection"` or click the **🔌 Test Jira Connection** button in `/chat`.
   - The agent calls `/rest/api/2/myself` and `/rest/api/2/project/{KEY}` to confirm credentials and available issue types.
2. **Via Automated Test**:
   ```bash
   python -m pytest agent/tests/test_jira.py
   ```

### 4. Creating Tickets from the Chat UI

The agent understands natural language Jira requests:

- **Create a ticket for a failure**:
  > *"Create a Jira ticket for the login test failure."*
- **Create a specific issue type**:
  > *"Create a bug ticket for the registration failure."*
- **Create tickets for all failed steps**:
  > *"Create Jira tickets for all failed test cases."*
- **Create a QA planning task**:
  > *"Create a Jira task to test the profile update flow."*

When creating a bug ticket, the agent automatically:
- Pulls actual error traces and step names from the latest execution report.
- Formats structured reproduction steps.
- Uploads failure screenshots (`.png`) and `report.html` as issue attachments.
- Checks for duplicate open tickets with the same summary to prevent duplicate filings.
- Returns a clickable link in the chat: `[KAN-123](https://your-domain.atlassian.net/browse/KAN-123)`.

### 5. Troubleshooting Common Errors

| Error | Cause | Resolution |
| :--- | :--- | :--- |
| **401 Unauthorized** | Invalid email or API token | Verify `JIRA_EMAIL` matches your Atlassian account and generate a new token. |
| **403 Forbidden** | User account lacks permission | Ensure the Jira user has "Create Issues" and "Add Attachments" permissions in the project. |
| **404 Not Found** | Project key or URL is incorrect | Verify `JIRA_PROJECT_KEY` matches an existing project and `JIRA_BASE_URL` is the root URL. |
| **400 Bad Request** | Unsupported Issue Type | The agent automatically falls back to `Task` if `Bug` is not permitted in your project schema. |

### 6. Token Rotation & Revocation

- If an API token is ever exposed, immediately revoke it at [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
- Generate a replacement token and update `JIRA_API_TOKEN` in your local `.env`. No code changes or server restart is required.
