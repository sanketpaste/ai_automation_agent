from pathlib import Path
from typing import Dict, Any, Tuple
from flask import Flask, request, jsonify, session, redirect, send_from_directory
from flask.typing import ResponseReturnValue

PUBLIC_DIR: Path = Path(__file__).resolve().parent / "public"

app: Flask = Flask(__name__, static_folder=str(PUBLIC_DIR))
app.secret_key = "dummy-app-super-secret-key-12345"

# In-memory user database: keyed by username
users_db: Dict[str, Dict[str, str]] = {}

def seed_database() -> None:
    """Seeds the initial demo user if not already present."""
    users_db["demo"] = {
        "username": "demo",
        "email": "demo@test.com",
        "password": "Demo@1234",
        "name": "Demo User",
        "phone": "1234567890"
    }

seed_database()

@app.route("/")
def index() -> ResponseReturnValue:
    return redirect("/login")

@app.route("/register")
def register_page() -> ResponseReturnValue:
    return send_from_directory(str(PUBLIC_DIR), "register.html")

@app.route("/login")
def login_page() -> ResponseReturnValue:
    return send_from_directory(str(PUBLIC_DIR), "login.html")

@app.route("/profile")
def profile_page() -> ResponseReturnValue:
    if "username" not in session:
        return redirect("/login")
    return send_from_directory(str(PUBLIC_DIR), "profile.html")

@app.route("/api/register", methods=["POST"])
def api_register() -> ResponseReturnValue:
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    name: str = str(data.get("name", "")).strip()
    email: str = str(data.get("email", "")).strip()
    phone: str = str(data.get("phone", "")).strip()
    password: str = str(data.get("password", ""))
    confirm: str = str(data.get("confirm", ""))

    if not name or not email or not phone or not password or not confirm:
        return jsonify({"success": False, "error": "All fields are required"}), 400

    if "@" not in email or "." not in email:
        return jsonify({"success": False, "error": "Invalid email address format"}), 400

    if len(password) < 8:
        return jsonify({"success": False, "error": "Password must be at least 8 characters"}), 400

    if password != confirm:
        return jsonify({"success": False, "error": "Passwords do not match"}), 400

    # Derive username from email prefix
    username: str = email.split("@")[0]
    for u in users_db.values():
        if u["email"].lower() == email.lower():
            return jsonify({"success": False, "error": "Email address already registered"}), 400
        if u["username"].lower() == username.lower():
            username = f"{username}_{len(users_db)}"

    users_db[username] = {
        "username": username,
        "email": email,
        "password": password,
        "name": name,
        "phone": phone
    }

    return jsonify({"success": True, "message": "Registration successful"}), 200

@app.route("/api/login", methods=["POST"])
def api_login() -> ResponseReturnValue:
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    identifier: str = str(data.get("username", "")).strip()
    password: str = str(data.get("password", ""))

    if not identifier or not password:
        return jsonify({"success": False, "error": "Username and password are required"}), 400

    matched_user: Dict[str, str] | None = None
    for u in users_db.values():
        if u["username"].lower() == identifier.lower() or u["email"].lower() == identifier.lower():
            matched_user = u
            break

    if not matched_user or matched_user["password"] != password:
        return jsonify({"success": False, "error": "Invalid username or password"}), 401

    session["username"] = matched_user["username"]
    return jsonify({"success": True, "redirect": "/profile"}), 200

@app.route("/api/profile", methods=["GET", "PUT"])
def api_profile() -> ResponseReturnValue:
    curr_user: str | None = session.get("username")
    if not curr_user or curr_user not in users_db:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    user_info = users_db[curr_user]

    if request.method == "PUT":
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        new_name: str = str(data.get("name", "")).strip()
        new_phone: str = str(data.get("phone", "")).strip()
        if new_name:
            user_info["name"] = new_name
        if new_phone:
            user_info["phone"] = new_phone

    return jsonify({
        "success": True,
        "user": {
            "name": user_info["name"],
            "email": user_info["email"],
            "phone": user_info["phone"],
            "username": user_info["username"]
        }
    }), 200

@app.route("/api/logout", methods=["POST"])
def api_logout() -> ResponseReturnValue:
    session.clear()
    return jsonify({"success": True, "redirect": "/login"}), 200

def start_dummy_app(host: str = "127.0.0.1", port: int = 4000) -> None:
    """Run the Flask dummy app server without reloader."""
    app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    start_dummy_app()
