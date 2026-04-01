from flask import Flask, request, jsonify, render_template, redirect, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, requests

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_key_123")

# 🔥 фиксы для мобильных
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
login_manager.login_view = "login_page"

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()

    if row:
        return User(row[0], row[1])
    return None

# ===== DATABASE =====
persistent_dir = "persistent"
os.makedirs(persistent_dir, exist_ok=True)
DB_FILE = os.path.join(persistent_dir, "gallery.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # пользователи
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')

    # фото
    c.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            file_id TEXT,
            user_id INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

init_db()

# ===== DB FUNCTIONS =====
def create_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    hashed = generate_password_hash(password)
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
        conn.commit()
    except:
        return False
    finally:
        conn.close()
    return True

def get_user(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, username, password FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row

def insert_photo(name, file_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO photos (name, file_id, user_id) VALUES (?, ?, ?)",
        (name, file_id, user_id)
    )
    conn.commit()
    conn.close()

def get_all_photos(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT name, file_id FROM photos WHERE user_id=? ORDER BY uploaded_at DESC",
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [{"name": r[0], "file_id": r[1]} for r in rows]

def get_file_id(name, user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT file_id FROM photos WHERE name=? AND user_id=?",
        (name, user_id)
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# ===== ROUTES =====

@app.route("/")
@login_required
def index():
    return render_template("index.html", username=current_user.username)

@app.route("/login_page")
def login_page():
    return render_template("login.html")

@app.route("/register", methods=["POST"])
def register():
    username = request.form.get("username")
    password = request.form.get("password")

    if create_user(username, password):
        return redirect("/login_page")
    return "Пользователь уже существует"

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    user = get_user(username)
    if user and check_password_hash(user[2], password):
        login_user(User(user[0], user[1]))
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
    photos = get_all_photos(current_user.id)
    return jsonify([p["name"] for p in photos])

@app.route("/image")
@login_required
def image():
    name = request.args.get("name")
    file_id = get_file_id(name, current_user.id)

    if not file_id:
        return "Нет доступа или файл не найден", 404

    try:
        res = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": file_id},
            timeout=10
        ).json()

        file_path = res.get("result", {}).get("file_path")
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    except:
        return "Ошибка Telegram", 500

    def generate():
        with requests.get(file_url, stream=True) as r:
            for chunk in r.iter_content(4096):
                yield chunk

    return Response(generate(), content_type="image/jpeg")

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")

    if not file:
        return redirect("/")

    name = file.filename

    try:
        res = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": CHANNEL_ID},
            files={"photo": file},
            timeout=15
        ).json()

        if not res.get("ok"):
            return "Ошибка Telegram API", 500

        file_id = res["result"]["photo"][-1]["file_id"]

        insert_photo(name, file_id, current_user.id)

    except:
        return "Ошибка загрузки", 500

    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)