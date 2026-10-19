import os
import sys
from pathlib import Path

# Ensure root directory is on python path and remove agent/ from sys.path[0] to avoid shadowing
ROOT_DIR: Path = Path(__file__).resolve().parent.parent
AGENT_DIR: Path = Path(__file__).resolve().parent

if sys.path and Path(sys.path[0]).resolve() == AGENT_DIR:
    sys.path.pop(0)

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from typing import Dict, Any
from flask import Flask, request, jsonify, send_from_directory, redirect
from flask.typing import ResponseReturnValue
from dotenv import load_dotenv

from agent.orchestrator.orchestrator_agent import OrchestratorAgent

# Load environment configuration
load_dotenv(ROOT_DIR / ".env")

CHAT_DIR: Path = Path(__file__).resolve().parent / "chat"
REPORTS_DIR: Path = Path(__file__).resolve().parent / "reports"

app: Flask = Flask(__name__)
orchestrator: OrchestratorAgent = OrchestratorAgent()

@app.route("/")
def index() -> ResponseReturnValue:
    return redirect("/chat")

@app.route("/chat")
def chat_page() -> ResponseReturnValue:
    """Serves the chat UI."""
    return send_from_directory(str(CHAT_DIR), "chat.html")

@app.route("/api/chat", methods=["POST"])
def api_chat() -> ResponseReturnValue:
    """
    Receives user prompt, invokes OrchestratorAgent,
    and returns test results and report links.
    """
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    prompt: str = str(data.get("prompt", "")).strip()

    result = orchestrator.process_prompt(prompt)
    return jsonify(result), 200

@app.route("/reports/<path:filename>")
def serve_report(filename: str) -> ResponseReturnValue:
    """Serves generated report JSON, HTML, and screenshot artifacts."""
    return send_from_directory(str(REPORTS_DIR), filename)

def start_agent_server(host: str = "127.0.0.1", port: int = 3000) -> None:
    """Run Flask agent server without reloader."""
    port_env: int = int(os.getenv("PORT", str(port)))
    app.run(host=host, port=port_env, debug=False, use_reloader=False)

if __name__ == "__main__":
    start_agent_server()
