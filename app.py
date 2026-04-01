from flask import Flask, request, jsonify, render_template, redirect, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
import sqlite3, os, requests

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_key_123")

# 🔥 ВАЖНО: фиксы для мобильных (cookies)
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    raise ValueError("BOT_TOKEN и CHANNEL_ID должны быть заданы")

# ===== LOGIN =====
login_manager = LoginManager()
login_manager.init_app(app)

# 🔥 редирект вместо Unauthorized
login_manager.login_view = "login_page"

users = {"admin": {"password": "1234"}}

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# ===== DATABASE =====
persistent_dir = "persistent"
os.makedirs(persistent_dir, exist_ok=True)
DB_FILE = os.path.join(persistent_dir, "gallery.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            file_id TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def insert_photo(name, file_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO photos (name, file_id) VALUES (?, ?)", (name, file_id))
        conn.commit()
    finally:
        conn.close()

def get_all_photos():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name, file_id FROM photos ORDER BY uploaded_at DESC")
    rows = c.fetchall()
    conn.close()
    return [{"name": r[0], "file_id": r[1]} for r in rows]

def get_file_id(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT file_id FROM photos WHERE name=?", (name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

init_db()

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
    try:
        photos = get_all_photos()
        return jsonify([p["name"] for p in photos])
    except Exception:
        return jsonify([])

@app.route("/image")
@login_required
def image():
    name = request.args.get("name")
    file_id = get_file_id(name)

    if not file_id:
        return "Фото не найдено", 404

    try:
        res = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": file_id},
            timeout=10
        ).json()

        file_path = res.get("result", {}).get("file_path")
        if not file_path:
            return "Ошибка Telegram API", 500

        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    except Exception:
        return "Ошибка при получении файла", 500

    def generate():
        try:
            with requests.get(file_url, stream=True) as r:
                for chunk in r.iter_content(4096):
                    yield chunk
        except Exception:
            return

    return Response(generate(), content_type="image/jpeg")

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")

    if not file:
        return redirect("/")

    name = file.filename

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {"photo": file}
        data = {"chat_id": CHANNEL_ID}

        res = requests.post(url, data=data, files=files, timeout=15).json()

        if not res.get("ok"):
            return "Ошибка Telegram API", 500

        file_id = res["result"]["photo"][-1]["file_id"]
        insert_photo(name, file_id)

    except Exception:
        return "Ошибка при загрузке", 500

    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)