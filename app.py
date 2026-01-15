from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app)

# Подключение к PostgreSQL
conn = psycopg2.connect(
    host="localhost",
    database="Gym",
    user="postgres",
    password="postgres"
)
cursor = conn.cursor()


# Регистрация
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


# Логин
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    print("Login attempt:", email, password)  # Логируем входные данные

    cursor.execute(
        "SELECT id, first_name, last_name, height, weight FROM users WHERE email=%s AND password=%s",
        (email, password)
    )
    user = cursor.fetchone()
    print("DB result:", user)  # Логируем что вернулось из базы


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


# Обновление профиля (рост и вес)
@app.route('/update_profile', methods=['POST'])
def update_profile():
    data = request.json
    user_id = data.get('id')
    height = data.get('height')
    weight = data.get('weight')

    cursor.execute("UPDATE users SET height=%s, weight=%s WHERE id=%s", (height, weight, user_id))
    conn.commit()
    return jsonify({"status": "success"}), 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
