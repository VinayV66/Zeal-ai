from flask import Flask, render_template, request, jsonify
import json
import os
import sqlite3

from models.vqa_model import get_answer

app = Flask(__name__)

# ---------------- LOAD PRODUCTS ----------------
def load_products():
    with open('data/products.json', 'r') as file:
        return json.load(file)

# ---------------- SMART FILTER ----------------
def is_relevant(question):
    question = question.lower()

    relevant_keywords = [
        "what", "color", "brand", "model", "price",
        "design", "look", "type", "product", "material",
        "size", "feature", "spec", "quality", "durability",
        "battery", "camera", "screen", "this"
    ]

    irrelevant_keywords = [
        "joke", "modi", "prime minister", "weather",
        "news", "cricket", "movie"
    ]

    if any(word in question for word in irrelevant_keywords):
        return False

    if any(word in question for word in relevant_keywords):
        return True

    return True

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            question TEXT,
            answer TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS pending_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            question TEXT,
            answer TEXT DEFAULT NULL
        )
    ''')

    conn.commit()
    conn.close()

# ---------------- HOME ----------------
@app.route('/')
def home():
    products = load_products()
    return render_template('index.html', products=products)

# ---------------- PRODUCT ----------------
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    products = load_products()
    product = next((p for p in products if p["id"] == product_id), None)
    return render_template('product.html', product=product)

# ---------------- CHAT ----------------
@app.route('/chat/<int:product_id>')
def chat(product_id):
    products = load_products()
    product = next((p for p in products if p["id"] == product_id), None)
    return render_template('chat.html', product=product)

# ---------------- ADMIN ----------------
@app.route('/admin')
def admin():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("SELECT * FROM pending_questions WHERE answer IS NULL")
    questions = c.fetchall()

    conn.close()
    return render_template('admin.html', questions=questions)

# ---------------- SAVE ADMIN ANSWER ----------------
@app.route('/answer', methods=['POST'])
def answer():
    data = request.json
    q_id = data.get("id")
    ans = data.get("answer")

    # ❌ reject bad answers
    if len(ans.strip()) < 3:
        return jsonify({"status": "error", "message": "Answer too short"})

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''
        UPDATE pending_questions
        SET answer = ?
        WHERE id = ?
    ''', (ans, q_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "success"})

# ---------------- GET ADMIN ANSWERS (FILTERED) ----------------
@app.route('/get-answers/<int:product_id>')
def get_answers(product_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''
        SELECT question, answer FROM pending_questions
        WHERE product_id = ? AND answer IS NOT NULL
    ''', (product_id,))

    data = c.fetchall()
    conn.close()

    # 🔥 FILTER BAD ANSWERS
    bad_words = ["ok", "modi", "test", "yes"]

    filtered = []
    for q, a in data:
        if a.lower() in bad_words:
            continue

        filtered.append({
            "question": q,
            "answer": a
        })

    return jsonify(filtered)

# ---------------- GET CHAT HISTORY ----------------
@app.route('/get-history/<int:product_id>')
def get_history(product_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''
        SELECT question, answer FROM chat_history
        WHERE product_id = ?
        ORDER BY id ASC
    ''', (product_id,))

    data = c.fetchall()
    conn.close()

    return jsonify([
        {"question": row[0], "answer": row[1]}
        for row in data
    ])

# ---------------- ASK AI ----------------
@app.route('/ask', methods=['POST'])
def ask():
    data = request.json
    question = data.get("question")
    image = data.get("image")
    product_id = data.get("product_id", 1)

    image_path = os.path.join("static", "images", image)

    # ❌ IRRELEVANT → SAVE FOR ADMIN
    if not is_relevant(question):
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        c.execute('''
            INSERT INTO pending_questions (user_id, product_id, question)
            VALUES (?, ?, ?)
        ''', (1, product_id, question))

        conn.commit()
        conn.close()

        return jsonify({
            "answer": "This question was sent for admin review."
        })

    # 🤖 AI ANSWER
    answer = get_answer(image_path, question)

    # 💾 SAVE CHAT
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''
        INSERT INTO chat_history (user_id, product_id, question, answer)
        VALUES (?, ?, ?, ?)
    ''', (1, product_id, question, answer))

    conn.commit()
    conn.close()

    return jsonify({"answer": answer})

# ---------------- RUN ----------------
if __name__ == '__main__':
    init_db()
    app.run(debug=True)