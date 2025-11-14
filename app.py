import os
import uuid
import base64
import sqlite3
from datetime import datetime

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
    flash,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from flask_bcrypt import Bcrypt

# Optional: backend Gemini integration (stubbed by default)
try:
    import google.generativeai as genai
except ImportError:
    genai = None

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")

login_manager = LoginManager(app)
login_manager.login_view = "login"

bcrypt = Bcrypt(app)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if genai and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
else:
    gemini_model = None


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_teacher INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            input_image TEXT,
            output_image TEXT,
            model_response_text TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    conn.commit()
    conn.close()


class User(UserMixin):
    def __init__(self, id, username, password_hash, is_teacher=False):
        self.id = str(id)
        self.username = username
        self.password_hash = password_hash
        self.is_teacher = bool(is_teacher)

    @property
    def is_teacher_bool(self):
        return self.is_teacher


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return User(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            is_teacher=row["is_teacher"],
        )
    return None


# Initialize DB at startup
with app.app_context():
    init_db()


def get_user_count():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM users")
    count = cur.fetchone()["c"]
    conn.close()
    return count


def generate_image_from_sketch(image_bytes: bytes, mime_type: str, prompt: str) -> dict:
    """
    Plug your real Gemini logic here.

    The function should return:
        {
            "image_base64": "<base64 of output image>",
            "image_mime_type": "image/png",
            "text": "optional model text response",
        }

    Currently this is a stub that just echoes the input image.
    """
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return {
        "image_base64": encoded,
        "image_mime_type": mime_type,
        "text": f"(Stub) Model response for prompt: {prompt}",
    }


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, go to dashboard
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM users")
    user_count = cur.fetchone()["c"]
    conn.close()

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            flash("Please enter both username and password.", "error")
            return render_template("login.html", user_count=user_count)

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        conn.close()

        if not row or not bcrypt.check_password_hash(row["password_hash"], password):
            flash("Invalid username or password.", "error")
            return render_template("login.html", user_count=user_count)

        user = User(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            is_teacher=row["is_teacher"],
        )
        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("login.html", user_count=user_count)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Registration logic:
    - If there are NO users yet, the first registered user becomes the teacher.
    - After that, only a logged-in teacher can create more users (students or other teachers).
    """
    user_count = get_user_count()
    first_user = user_count == 0

    if not first_user:
        if not current_user.is_authenticated or not current_user.is_teacher:
            flash("Only a teacher can create new accounts.", "error")
            return redirect(url_for("login"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        is_teacher = request.form.get("is_teacher") == "on"

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("register.html", first_user=first_user)

        if first_user:
            is_teacher = True  # first user is always teacher

        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, password_hash, is_teacher) VALUES (?, ?, ?)",
                (username, password_hash, 1 if is_teacher else 0),
            )
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError:
            flash("Username already exists. Choose another one.", "error")
            return render_template("register.html", first_user=first_user)

        flash(
            "Account created successfully. You can now log in."
            if first_user
            else "Student account created successfully.",
            "success",
        )

        if first_user:
            return redirect(url_for("login"))
        else:
            return redirect(url_for("teacher_panel"))

    return render_template("register.html", first_user=first_user)


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)


@app.route("/teacher")
@login_required
def teacher_panel():
    if not current_user.is_teacher:
        flash("Teacher access required.", "error")
        return redirect(url_for("dashboard"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT u.id, u.username, u.is_teacher,
               COUNT(c.id) AS convo_count
        FROM users u
        LEFT JOIN conversations c ON u.id = c.user_id
        GROUP BY u.id, u.username, u.is_teacher
        ORDER BY u.is_teacher DESC, u.username ASC
        """
    )
    users = cur.fetchall()
    conn.close()

    return render_template("teacher.html", users=users)


@app.route("/teacher/user/<int:user_id>")
@login_required
def teacher_user_view(user_id):
    if not current_user.is_teacher:
        flash("Teacher access required.", "error")
        return redirect(url_for("dashboard"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        flash("User not found.", "error")
        return redirect(url_for("teacher_panel"))

    cur.execute(
        """
        SELECT * FROM conversations
        WHERE user_id = ?
        ORDER BY datetime(created_at) ASC
        """,
        (user_id,),
    )
    convos = cur.fetchall()
    conn.close()

    return render_template(
        "teacher_user.html",
        student=user,
        conversations=convos,
    )


@app.route("/api/my_history")
@login_required
def api_my_history():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, prompt, input_image, output_image, model_response_text, created_at
        FROM conversations
        WHERE user_id = ?
        ORDER BY datetime(created_at) ASC
        """,
        (int(current_user.id),),
    )
    rows = cur.fetchall()
    conn.close()

    history = []
    for r in rows:
        history.append(
            {
                "id": r["id"],
                "prompt": r["prompt"],
                "inputImage": r["input_image"],
                "outputImage": r["output_image"],
                "modelResponseText": r["model_response_text"],
                "createdAt": r["created_at"],
            }
        )
    return jsonify(history)


@app.route("/api/initial", methods=["POST"])
@login_required
def api_initial():
    sketch_file = request.files.get("sketch")
    prompt = (request.form.get("prompt") or "").strip()

    if not sketch_file:
        return jsonify({"error": "Missing sketch file"}), 400
    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    image_bytes = sketch_file.read()
    mime_type = sketch_file.mimetype or "image/png"

    result = generate_image_from_sketch(image_bytes, mime_type, prompt)

    input_data_url = (
        f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"
    )
    output_data_url = (
        f"data:{result['image_mime_type']};base64,{result['image_base64']}"
    )

    created_at = datetime.utcnow().isoformat()

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO conversations
        (user_id, prompt, input_image, output_image, model_response_text, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            int(current_user.id),
            prompt,
            input_data_url,
            output_data_url,
            result.get("text"),
            created_at,
        ),
    )
    convo_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify(
        {
            "id": convo_id,
            "prompt": prompt,
            "inputImage": input_data_url,
            "outputImage": output_data_url,
            "modelResponseText": result.get("text"),
            "createdAt": created_at,
        }
    )


@app.route("/api/continue", methods=["POST"])
@login_required
def api_continue():
    data = request.get_json(force=True) or {}
    prompt = (data.get("prompt") or "").strip()
    last_image_data_url = data.get("lastImage")

    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400
    if not last_image_data_url:
        return jsonify({"error": "Missing lastImage (data URL)"}), 400

    try:
        header, b64data = last_image_data_url.split(",", 1)
        mime_type = header.split(";")[0].split(":")[1]
    except Exception:
        return jsonify({"error": "Invalid lastImage data URL"}), 400

    image_bytes = base64.b64decode(b64data)

    result = generate_image_from_sketch(image_bytes, mime_type, prompt)

    output_data_url = (
        f"data:{result['image_mime_type']};base64,{result['image_base64']}"
    )

    created_at = datetime.utcnow().isoformat()

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO conversations
        (user_id, prompt, input_image, output_image, model_response_text, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            int(current_user.id),
            prompt,
            last_image_data_url,
            output_data_url,
            result.get("text"),
            created_at,
        ),
    )
    convo_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify(
        {
            "id": convo_id,
            "prompt": prompt,
            "inputImage": last_image_data_url,
            "outputImage": output_data_url,
            "modelResponseText": result.get("text"),
            "createdAt": created_at,
        }
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
