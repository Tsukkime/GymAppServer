from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app)

conn = psycopg2.connect(
    host="localhost",
    database="Gym",
    user="postgres",
    password="postgres"
)
cursor = conn.cursor()

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    password = data.get('password')
    height = data.get('height') or 0
    weight = data.get('weight') or 0
    try:
        cursor.execute(
            "INSERT INTO users (first_name,last_name,email,password,height,weight) VALUES (%s,%s,%s,%s,%s,%s)",
            (first_name, last_name, email, password, height, weight)
        )
        conn.commit()
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
            cursor.execute("INSERT INTO custom_workout_exercises (custom_workout_id, exercise_id, sets, reps) VALUES (%s, %s, %s, %s)",
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
        "SELECT id, title, created_at FROM custom_workouts WHERE user_id=%s ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cursor.fetchall()
    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "title": row[1],
            "created_at": str(row[2])
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

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)