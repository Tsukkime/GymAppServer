from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import psycopg2
import random
import os
import requests
import secrets
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "re_ZkoX79sG_3EyeCkkMGihPJti87SsPXyBT")
RESEND_FROM = "GymApp <noreply@webcheating.xyz>"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

def send_email(to_email, subject, body):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={"from": RESEND_FROM, "to": [to_email], "subject": subject, "text": body}
    )
    return response.status_code == 200

pending_registrations = {}

def get_connection():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        parsed = urlparse(database_url)
        return psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path.lstrip("/"),
            user=parsed.username,
            password=parsed.password
        )
    return psycopg2.connect(
        host="localhost",
        database="Gym",
        user="postgres",
        password="postgres"
    )

conn = get_connection()
cursor = conn.cursor()

def get_cursor():
    global conn, cursor
    try:
        cursor.execute("SELECT 1")
    except Exception:
        conn = get_connection()
        cursor = conn.cursor()
    return conn, cursor

def get_user_from_token(token):
    c, cur = get_cursor()
    cur.execute(
        "SELECT u.id FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.token = %s",
        (token,)
    )
    row = cur.fetchone()
    return row[0] if row else None

@app.route('/send_code', methods=['POST'])
def send_code():
    data = request.get_json(force=True, silent=True) or {}
    print(f"send_code data: {data}")
    email = data.get('email')
    if not email:
        return jsonify({"status": "error", "message": "Email не указан"}), 400
    code = str(random.randint(1000, 9999))
    pending_registrations[email] = {"code": code, "data": data}
    print(f"Код: {code} для {email}")
    ok = send_email(email, "Код подтверждения GymApp", f"Ваш код подтверждения: {code}")
    if ok:
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "error", "message": "Ошибка отправки email"}), 400

@app.route('/verify_code', methods=['POST'])
def verify_code():
    data = request.get_json(force=True, silent=True) or {}
    email = data.get('email')
    code = data.get('code')
    if email not in pending_registrations:
        return jsonify({"status": "error", "message": "Код не найден"}), 400
    saved = pending_registrations[email]
    if saved["code"] != code:
        return jsonify({"status": "error", "message": "Неверный код"}), 400
    reg = saved["data"]
    first_name = reg.get('first_name')
    last_name = reg.get('last_name')
    password = reg.get('password')
    height = reg.get('height') or 0
    weight = reg.get('weight') or 0
    try:
        c, cur = get_cursor()
        cur.execute(
            "INSERT INTO users (first_name,last_name,email,password,height,weight) VALUES (%s,%s,%s,%s,%s,%s)",
            (first_name, last_name, email, password, height, weight)
        )
        c.commit()
        del pending_registrations[email]
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(force=True, silent=True) or {}
    email = data.get('email')
    password = data.get('password')
    c, cur = get_cursor()
    cur.execute(
        "SELECT id, first_name, last_name, height, weight FROM users WHERE email=%s AND password=%s",
        (email, password)
    )
    user = cur.fetchone()
    if user:
        token = secrets.token_hex(32)
        cur.execute("INSERT INTO sessions (user_id, token) VALUES (%s, %s)", (user[0], token))
        c.commit()
        return jsonify({
            "status": "success",
            "token": token,
            "id": user[0],
            "first_name": user[1],
            "last_name": user[2],
            "height": user[3],
            "weight": user[4]
        }), 200
    else:
        return jsonify({"status": "error", "message": "Неверный email или пароль"}), 401

@app.route('/me', methods=['GET'])
def me():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return jsonify({"status": "error", "message": "Нет токена"}), 401
    c, cur = get_cursor()
    cur.execute(
        """SELECT u.id, u.first_name, u.last_name, u.height, u.weight
           FROM sessions s JOIN users u ON s.user_id = u.id
           WHERE s.token = %s""",
        (token,)
    )
    user = cur.fetchone()
    if user:
        return jsonify({
            "status": "success",
            "id": user[0],
            "first_name": user[1],
            "last_name": user[2],
            "height": user[3],
            "weight": user[4]
        }), 200
    else:
        return jsonify({"status": "error", "message": "Неверный токен"}), 401

@app.route('/update_profile', methods=['POST'])
def update_profile():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get('id')
    height = data.get('height')
    weight = data.get('weight')
    c, cur = get_cursor()
    cur.execute("UPDATE users SET height=%s, weight=%s WHERE id=%s", (height, weight, user_id))
    c.commit()
    return jsonify({"status": "success"}), 200

@app.route('/workouts', methods=['GET'])
def get_workouts():
    workout_type = request.args.get('type', 'home')
    c, cur = get_cursor()
    cur.execute(
        "SELECT id, title, subtitle FROM workout_plans WHERE type=%s",
        (workout_type,)
    )
    rows = cur.fetchall()
    result = [{"id": row[0], "title": row[1], "subtitle": row[2]} for row in rows]
    return jsonify({"status": "success", "workouts": result}), 200

@app.route('/exercises', methods=['GET'])
def get_exercises():
    workout_plan_id = request.args.get('workout_id')
    c, cur = get_cursor()
    cur.execute(
        """SELECT e.name, e.sets, e.tip
           FROM exercises e
           JOIN workout_exercises we ON e.id = we.exercise_id
           WHERE we.workout_plan_id = %s""",
        (workout_plan_id,)
    )
    rows = cur.fetchall()
    result = [{"name": row[0], "sets": row[1], "tip": row[2]} for row in rows]
    return jsonify({"status": "success", "exercises": result}), 200

@app.route('/all_exercises', methods=['GET'])
def get_all_exercises():
    c, cur = get_cursor()
    cur.execute("SELECT id, name, difficulty, equipment FROM exercises")
    rows = cur.fetchall()
    result = [{"id": row[0], "name": row[1], "difficulty": row[2], "equipment": row[3]} for row in rows]
    return jsonify({"status": "success", "exercises": result}), 200

@app.route('/save_custom_workout', methods=['POST'])
def save_custom_workout():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get('user_id')
    title = data.get('title')
    exercises = data.get('exercises')
    try:
        c, cur = get_cursor()
        cur.execute(
            "INSERT INTO custom_workouts (user_id, title) VALUES (%s, %s) RETURNING id",
            (user_id, title)
        )
        custom_workout_id = cur.fetchone()[0]
        for ex in exercises:
            cur.execute(
                "INSERT INTO custom_workout_exercises (custom_workout_id, exercise_id, sets, reps) VALUES (%s, %s, %s, %s)",
                (custom_workout_id, ex['exercise_id'], ex['sets'], ex['reps'])
            )
        c.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/custom_workouts', methods=['GET'])
def get_custom_workouts():
    user_id = request.args.get('user_id')
    c, cur = get_cursor()
    cur.execute(
        """SELECT cw.id, cw.title, COUNT(cwe.id) as exercise_count
           FROM custom_workouts cw
           LEFT JOIN custom_workout_exercises cwe ON cw.id = cwe.custom_workout_id
           WHERE cw.user_id = %s
           GROUP BY cw.id, cw.title
           ORDER BY cw.id DESC""",
        (user_id,)
    )
    rows = cur.fetchall()
    result = [{"id": row[0], "title": row[1], "exercise_count": row[2]} for row in rows]
    return jsonify({"status": "success", "workouts": result}), 200

@app.route('/custom_workout_exercises', methods=['GET'])
def get_custom_workout_exercises():
    custom_workout_id = request.args.get('custom_workout_id')
    c, cur = get_cursor()
    cur.execute(
        """SELECT e.name, cwe.sets, cwe.reps, e.tip
           FROM custom_workout_exercises cwe
           JOIN exercises e ON e.id = cwe.exercise_id
           WHERE cwe.custom_workout_id = %s""",
        (custom_workout_id,)
    )
    rows = cur.fetchall()
    result = [{
        "name": row[0],
        "sets": str(row[1]) + " подходов",
        "tip": row[3],
        "reps": str(row[2]) + " повторений"
    } for row in rows]
    return jsonify({"status": "success", "exercises": result}), 200

@app.route('/chat', methods=['POST'])
def chat():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = get_user_from_token(token)
    if not user_id:
        return jsonify({"status": "error", "message": "Нет доступа"}), 401

    data = request.get_json(force=True, silent=True) or {}
    user_message = data.get('message', '')
    if not user_message:
        return jsonify({"status": "error", "message": "Нет сообщения"}), 400

    c, cur = get_cursor()
    cur.execute(
        "INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)",
        (user_id, 'user', user_message)
    )
    c.commit()

    cur.execute(
        "SELECT role, content FROM messages WHERE user_id = %s ORDER BY created_at ASC",
        (user_id,)
    )
    history = [{"role": row[0], "content": row[1]} for row in cur.fetchall()]
    messages = [{"role": "system", "content": "Ты фитнес-тренер и диетолог. Отвечай на русском языке. Давай советы по питанию, упражнениям и здоровому образу жизни. Отвечай кратко и по делу."}] + history

    if not OPENROUTER_API_KEY:
        return jsonify({"status": "error", "message": "API ключ не настроен на сервере"}), 500

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={"model": "openrouter/auto", "messages": messages},
            timeout=30
        )
        resp_json = resp.json()
        if "choices" not in resp_json:
            return jsonify({"status": "error", "message": str(resp_json)}), 500
        ai_message = resp_json["choices"][0]["message"]["content"]
        cur.execute(
            "INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)",
            (user_id, 'assistant', ai_message)
        )
        c.commit()
        return jsonify({"status": "success", "message": ai_message}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/chat/history', methods=['GET'])
def chat_history():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = get_user_from_token(token)
    if not user_id:
        return jsonify({"status": "error", "message": "Нет доступа"}), 401
    c, cur = get_cursor()
    cur.execute(
        "SELECT role, content FROM messages WHERE user_id = %s ORDER BY created_at ASC",
        (user_id,)
    )
    history = [{"role": row[0], "content": row[1]} for row in cur.fetchall()]
    return jsonify({"status": "success", "messages": history}), 200

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download')
def download_apk():
    apk_dir = os.path.join(os.path.dirname(__file__), 'static')
    response = send_from_directory(apk_dir, 'app-debug.apk', as_attachment=True, mimetype='application/vnd.android.package-archive')
    response.headers['Content-Disposition'] = 'attachment; filename="GymApp.apk"'
    return response

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 1234))
    app.run(host="0.0.0.0", port=port, debug=False)
