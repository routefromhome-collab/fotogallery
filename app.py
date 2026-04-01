from flask import Flask, request, jsonify, render_template, redirect, Response
import requests
import json
import os

from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_key_123")

# 🔑 Настройки
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # токен бота
CHANNEL_ID = os.environ.get("CHANNEL_ID")  # ID канала -100XXXXXXXXXX

if not BOT_TOKEN or not CHANNEL_ID:
    raise ValueError("BOT_TOKEN и CHANNEL_ID должны быть заданы в environment variables")

# ===== LOGIN =====
login_manager = LoginManager()
login_manager.login_view = "/login_page"
login_manager.init_app(app)

users = {"admin": {"password": "1234"}}

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# ===== DB =====
DB_FILE = "db.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ===== ROUTES =====

@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/login_page")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    if username in users and users[username]["password"] == password:
        login_user(User(username))
        return redirect("/")
    return render_template("login.html", error="Неверный логин или пароль")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login_page")

@app.route("/images")
@login_required
def images():
    db = load_db()
    return jsonify(list(db.keys()))

@app.route("/image")
@login_required
def image():
    name = request.args.get("name")
    db = load_db()
    if not name or name not in db:
        return "Not found", 404

    file_id = db[name]
    try:
        res = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": file_id},
            timeout=10
        ).json()
    except Exception as e:
        return f"Ошибка Telegram API: {e}", 500

    if not res.get("ok"):
        return f"Ошибка Telegram API: {res}", 500

    file_path = res["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    def generate():
        try:
            with requests.get(file_url, stream=True, timeout=10) as r:
                r.raise_for_status()
                for chunk in r.iter_content(4096):
                    if chunk:
                        yield chunk
        except Exception:
            yield b''

    return Response(generate(), content_type="image/jpeg")

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")
    if not file:
        return redirect("/")

    name = file.filename
    if not name.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
        return f"Неверный формат файла: {name}", 400

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    files = {"photo": file}
    data = {"chat_id": CHANNEL_ID}

    try:
        res = requests.post(url, data=data, files=files, timeout=10).json()
    except Exception as e:
        return f"Ошибка при загрузке в Telegram: {e}", 500

    if not res.get("ok"):
        return f"Ошибка Telegram API: {res}", 500

    file_id = res["result"]["photo"][-1]["file_id"]

    db = load_db()
    db[name] = file_id
    save_db(db)

    return redirect("/")

# ===== START =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)