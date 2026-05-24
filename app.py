from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ============ DATABASE SETUP ============
def get_db():
    conn = sqlite3.connect('gemcart.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        gender TEXT,
        price INTEGER,
        description TEXT,
        size TEXT,
        photos TEXT,
        stock INTEGER DEFAULT 0,
        discount INTEGER DEFAULT 0,
        featured INTEGER DEFAULT 0,
        visible INTEGER DEFAULT 1,
        sold INTEGER DEFAULT 0
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        date TEXT,
        customer_name TEXT,
        customer_username TEXT,
        items TEXT,
        total INTEGER,
        status TEXT DEFAULT 'pending'
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT,
        message TEXT,
        photo TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# ============ API ROUTES ============
@app.route('/')
def home():
    return jsonify({"status": "GEM CART API is running", "version": "1.0"})

@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_db()
    products = conn.execute('SELECT * FROM products WHERE visible=1').fetchall()
    conn.close()
    result = []
    for p in products:
        result.append({
            "id": p["id"],
            "name": p["name"],
            "category": p["category"],
            "gender": p["gender"],
            "price": p["price"],
            "description": p["description"],
            "size": p["size"],
            "photos": p["photos"].split(",") if p["photos"] else [],
            "stock": p["stock"],
            "discount": p["discount"],
            "featured": bool(p["featured"]),
            "visible": bool(p["visible"]),
            "sold": bool(p["sold"])
        })
    return jsonify(result)

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    order_id = "GEM-" + datetime.now().strftime("%Y%m%d%H%M%S")
    conn = get_db()
    conn.execute('INSERT INTO orders (id, date, customer_name, customer_username, items, total, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
                 [order_id, datetime.now().isoformat(), data.get('customerName'), data.get('customerUsername'), str(data.get('items')), data.get('total'), 'pending'])
    conn.commit()
    conn.close()
    return jsonify({"success": True, "orderId": order_id})

@app.route('/api/orders', methods=['GET'])
def get_orders():
    conn = get_db()
    orders = conn.execute('SELECT * FROM orders ORDER BY date DESC').fetchall()
    conn.close()
    result = []
    for o in orders:
        result.append({
            "id": o["id"],
            "date": o["date"],
            "customerName": o["customer_name"],
            "customerUsername": o["customer_username"],
            "items": eval(o["items"]) if o["items"] else [],
            "total": o["total"],
            "status": o["status"]
        })
    return jsonify(result)

@app.route('/api/broadcasts', methods=['GET'])
def get_broadcasts():
    conn = get_db()
    broadcasts = conn.execute('SELECT * FROM broadcasts ORDER BY time DESC').fetchall()
    conn.close()
    result = []
    for b in broadcasts:
        result.append({
            "id": b["id"],
            "time": b["time"],
            "message": b["message"],
            "photo": b["photo"]
        })
    return jsonify(result)

# ============ HEALTH CHECK ============
@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
