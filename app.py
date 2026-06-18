from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_mail import Mail, Message
import psycopg2
import random
import os
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nektslider@gmail.com'
app.config['MAIL_PASSWORD'] = 'eatz ktre ypzi ahlr'
app.config['MAIL_DEFAULT_SENDER'] = 'nektslider@gmail.com'

mail = Mail(app)

pending_registrations = {}

database_url = os.environ.get("DATABASE_URL")
if database_url:
    parsed = urlparse(database_url)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        database=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password
    )
else:
    conn = psycopg2.connect(
        host="localhost",
        database="Gym",
        user="postgres",
        password="postgres"
    )
cursor = conn.cursor()

@app.route('/send_code', methods=['POST'])
def send_code():
    data = request.json
    email = data.get('email')
    if not email:
        return jsonify({"status": "error", "message": "Email не указан"}), 400
    code = str(random.randint(1000, 9999))
    pending_registrations[email] = {"code": code, "data": data}
    print(f"Код: {code} для {email}")
    try:
        msg = Message(
            subject="Код подтверждения GymApp",
            recipients=[email],
            body=f"Ваш код подтверждения: {code}"
        )
        mail.send(msg)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/verify_code', methods=['POST'])
def verify_code():
    data = request.json
    print(f"Получили данные: {data}")
    email = data.get('email')
    code = data.get('code')
    print(f"Проверяем: email={email}, code={code}")
    print(f"Сохранённые коды: {pending_registrations}")
    if email not in pending_registrations:
        return jsonify({"status": "error", "message": "Код не найден"}), 400
    saved = pending_registrations[email]
    print(f"Сохранённый код: {saved['code']}")
    if saved["code"] != code:
        return jsonify({"status": "error", "message": "Неверный код"}), 400
    reg = saved["data"]
    first_name = reg.get('first_name')
    last_name = reg.get('last_name')
    password = reg.get('password')
    height = reg.get('height') or 0
    weight = reg.get('weight') or 0
    try:
        cursor.execute(
            "INSERT INTO users (first_name,last_name,email,password,height,weight) VALUES (%s,%s,%s,%s,%s,%s)",
            (first_name, last_name, email, password, height, weight)
        )
        conn.commit()
        del pending_registrations[email]
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    cursor.execute(
        "SELECT id, first_name, last_name, height, weight FROM users WHERE email=%s AND password=%s",
        (email, password)
    )
    user = cursor.fetchone()
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
        return jsonify({"status": "error", "message": "Неверный email или пароль"}), 401

@app.route('/update_profile', methods=['POST'])
def update_profile():
    data = request.json
    user_id = data.get('id')
    height = data.get('height')
    weight = data.get('weight')
    cursor.execute("UPDATE users SET height=%s, weight=%s WHERE id=%s", (height, weight, user_id))
    conn.commit()
    return jsonify({"status": "success"}), 200

@app.route('/workouts', methods=['GET'])
def get_workouts():
    workout_type = request.args.get('type', 'home')
    cursor.execute(
        "SELECT id, title, subtitle FROM workout_plans WHERE type=%s",
        (workout_type,)
    )
    rows = cursor.fetchall()
    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "title": row[1],
            "subtitle": row[2]
        })
    return jsonify({"status": "success", "workouts": result}), 200

@app.route('/exercises', methods=['GET'])
def get_exercises():
    workout_plan_id = request.args.get('workout_id')
    cursor.execute(
        """
        SELECT e.name, e.sets, e.tip
        FROM exercises e
        JOIN workout_exercises we ON e.id = we.exercise_id
        WHERE we.workout_plan_id = %s
        """,
        (workout_plan_id,)
    )
    rows = cursor.fetchall()
    result = []
    for row in rows:
        result.append({
            "name": row[0],
            "sets": row[1],
            "tip": row[2]
        })
    return jsonify({"status": "success", "exercises": result}), 200

@app.route('/all_exercises', methods=['GET'])
def get_all_exercises():
    cursor.execute("SELECT id, name, difficulty, equipment FROM exercises")
    rows = cursor.fetchall()
    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "name": row[1],
            "difficulty": row[2],
            "equipment": row[3]
        })
    return jsonify({"status": "success", "exercises": result}), 200

@app.route('/save_custom_workout', methods=['POST'])
def save_custom_workout():
    data = request.json
    user_id = data.get('user_id')
    title = data.get('title')
    exercises = data.get('exercises')
    try:
        cursor.execute(
            "INSERT INTO custom_workouts (user_id, title) VALUES (%s, %s) RETURNING id",
            (user_id, title)
        )
        custom_workout_id = cursor.fetchone()[0]
        for ex in exercises:
            cursor.execute(
                "INSERT INTO custom_workout_exercises (custom_workout_id, exercise_id, sets, reps) VALUES (%s, %s, %s, %s)",
                (custom_workout_id, ex['exercise_id'], ex['sets'], ex['reps'])
            )
        conn.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/custom_workouts', methods=['GET'])
def get_custom_workouts():
    user_id = request.args.get('user_id')
    cursor.execute(
        """
        SELECT cw.id, cw.title, COUNT(cwe.id) as exercise_count
        FROM custom_workouts cw
        LEFT JOIN custom_workout_exercises cwe ON cw.id = cwe.custom_workout_id
        WHERE cw.user_id = %s
        GROUP BY cw.id, cw.title
        ORDER BY cw.id DESC
        """,
        (user_id,)
    )
    rows = cursor.fetchall()
    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "title": row[1],
            "exercise_count": row[2]
        })
    return jsonify({"status": "success", "workouts": result}), 200

@app.route('/custom_workout_exercises', methods=['GET'])
def get_custom_workout_exercises():
    custom_workout_id = request.args.get('custom_workout_id')
    cursor.execute(
        """
        SELECT e.name, cwe.sets, cwe.reps, e.tip
        FROM custom_workout_exercises cwe
        JOIN exercises e ON e.id = cwe.exercise_id
        WHERE cwe.custom_workout_id = %s
        """,
        (custom_workout_id,)
    )
    rows = cursor.fetchall()
    result = []
    for row in rows:
        result.append({
            "name": row[0],
            "sets": str(row[1]) + " подходов",
            "tip": row[3],
            "reps": str(row[2]) + " повторений"
        })
    return jsonify({"status": "success", "exercises": result}), 200

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download')
def download_apk():
    apk_dir = os.path.join(os.path.dirname(__file__), 'static')
    return send_from_directory(apk_dir, 'app-debug.apk', as_attachment=True)

if __name__ == '__main__':
    app.run(host="localhost", port=1234, debug=True)