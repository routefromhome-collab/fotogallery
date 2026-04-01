from flask import Flask, request, jsonify, render_template, redirect, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, requests, threading, time

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_key_123")

app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

BASE_URL = os.environ.get("BASE_URL")  # ВАЖНО

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
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return User(row[0], row[1]) if row else None

# ===== DATABASE =====
DB_FILE = os.path.join("persistent", "gallery.db")
os.makedirs("persistent", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')

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

# ===== DB =====
def create_user(username, password):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, generate_password_hash(password))
        )
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def get_user(username):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    c.execute("SELECT id, username, password FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row

def insert_photo(name, file_id, user_id):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    c.execute("INSERT INTO photos (name, file_id, user_id) VALUES (?, ?, ?)",
              (name, file_id, user_id))
    conn.commit()
    conn.close()

def get_all_photos(user_id):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    c.execute("SELECT name FROM photos WHERE user_id=? ORDER BY uploaded_at DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_file_id(name, user_id):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    c.execute("SELECT file_id FROM photos WHERE name=? AND user_id=?", (name, user_id))
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
    if create_user(request.form.get("username"), request.form.get("password")):
        return redirect("/login_page")
    return render_template("login.html", error="Пользователь уже существует")

@app.route("/login", methods=["POST"])
def login():
    user = get_user(request.form.get("username"))
    if user and check_password_hash(user[2], request.form.get("password")):
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
    return jsonify(get_all_photos(current_user.id))

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

        if not file_path:
            return "Файл не найден", 404

        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        # 🔥 определяем тип файла
        if file_path.endswith(".png"):
            content_type = "image/png"
        elif file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif file_path.endswith(".webp"):
            content_type = "image/webp"
        else:
            content_type = "application/octet-stream"

    except Exception as e:
        print("Telegram error:", e)
        return "Ошибка Telegram", 500

    def generate():
        try:
            with requests.get(file_url, stream=True) as r:
                for chunk in r.iter_content(4096):
                    yield chunk
        except Exception as e:
            print("Stream error:", e)

    return Response(generate(), content_type=content_type)

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")

    if not file:
        return jsonify({"error": "no file"}), 400

    try:
        res = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
            data={"chat_id": CHANNEL_ID},
            files={"document": file},
            timeout=15
        ).json()

        if not res.get("ok"):
            return jsonify({"error": res.get("description")}), 500

        file_id = res["result"]["document"]["file_id"]

        insert_photo(file.filename, file_id, current_user.id)

        return jsonify({
            "status": "ok",
            "name": file.filename
        })

    except Exception as e:
        print(e)
        return jsonify({"error": "upload failed"}), 500

# ===== KEEP ALIVE =====
@app.route("/ping")
def ping():
    return "ok"

def self_ping():
    if not BASE_URL:
        return
    while True:
        try:
            requests.get(BASE_URL + "/ping", timeout=5)
        except:
            pass
        time.sleep(300)

threading.Thread(target=self_ping, daemon=True).start()

if __name__ == "__main__":
    app.run(debug=True)