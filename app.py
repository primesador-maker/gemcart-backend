import os
import json
import uuid
import threading
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from werkzeug.utils import secure_filename
import logging
import subprocess
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8924432232:AAEl9AvRZ9o6tII-YYW5waQoIcvg3wH4qXI"
ADMIN_ID = 7715442708
PASSWORD = "sadmin"

app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ==================== DATABASE ====================
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('gemcart.db')
        g.db.row_factory = sqlite3.Row
    return g.db

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                chat_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                category TEXT DEFAULT 'Uncategorized',
                gender TEXT DEFAULT 'Unisex',
                images TEXT DEFAULT '[]',
                video TEXT,
                stock INTEGER DEFAULT 1,
                is_sold INTEGER DEFAULT 0,
                is_hidden INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                customer_name TEXT,
                customer_username TEXT,
                items TEXT,
                total_amount REAL,
                payment_method TEXT DEFAULT 'Telebirr',
                status TEXT DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS admin_tokens (
                token TEXT PRIMARY KEY
            );
        ''')
        db.commit()

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def admin_required(f):
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization')
        if not auth or not auth.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        token = auth.split(' ')[1]
        db = get_db()
        if not db.execute('SELECT token FROM admin_tokens WHERE token=?', (token,)).fetchone():
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ==================== ROUTES ====================
@app.route('/')
def home():
    return jsonify({'status': 'GEM CART API is running'})

@app.route('/api/categories', methods=['GET'])
def get_categories():
    db = get_db()
    cats = [row['name'] for row in db.execute('SELECT name FROM categories').fetchall()]
    return jsonify({'categories': cats})

@app.route('/api/categories', methods=['POST'])
@admin_required
def add_category():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    db = get_db()
    try:
        db.execute('INSERT INTO categories (name) VALUES (?)', (name,))
        db.commit()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Category exists'}), 400

@app.route('/api/categories/<name>', methods=['DELETE'])
@admin_required
def delete_category(name):
    db = get_db()
    db.execute('DELETE FROM categories WHERE name=?', (name,))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/products', methods=['GET'])
def get_products():
    db = get_db()
    rows = db.execute('SELECT * FROM products').fetchall()
    products = []
    for r in rows:
        products.append({
            'id': r['id'], 'name': r['name'], 'description': r['description'],
            'price': r['price'], 'category': r['category'], 'gender': r['gender'],
            'images': json.loads(r['images']), 'video': r['video'],
            'stock': r['stock'], 'is_sold': bool(r['is_sold']), 'is_hidden': bool(r['is_hidden'])
        })
    return jsonify({'products': products})

@app.route('/api/products', methods=['POST'])
@admin_required
def add_product():
    name = request.form.get('name')
    price = request.form.get('price')
    if not name or not price:
        return jsonify({'error': 'Name and price required'}), 400
    images = []
    video = None
    for file in request.files.getlist('files')[:5]:
        filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        if file.mimetype.startswith('video'):
            video = filename
        else:
            images.append(filename)
    db = get_db()
    db.execute('INSERT INTO products (name,description,price,category,gender,images,video,stock) VALUES (?,?,?,?,?,?,?,?)',
               (name, request.form.get('description',''), float(price),
                request.form.get('category','Uncategorized'), request.form.get('gender','Unisex'),
                json.dumps(images), video, int(request.form.get('stock',1))))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/products/<int:pid>', methods=['PUT'])
@admin_required
def update_product(pid):
    data = request.get_json()
    db = get_db()
    p = db.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    if not p:
        return jsonify({'error': 'Not found'}), 404
    if 'stock_increment' in data:
        db.execute('UPDATE products SET stock=? WHERE id=?', (p['stock']+data['stock_increment'], pid))
    if 'is_sold' in data:
        db.execute('UPDATE products SET is_sold=? WHERE id=?', (int(data['is_sold']), pid))
    if 'is_hidden' in data:
        db.execute('UPDATE products SET is_hidden=? WHERE id=?', (int(data['is_hidden']), pid))
    db.commit()
    updated = db.execute('SELECT stock FROM products WHERE id=?', (pid,)).fetchone()
    if updated['stock'] <= 0:
        db.execute('UPDATE products SET is_sold=1 WHERE id=?', (pid,))
        db.commit()
    return jsonify({'success': True})

@app.route('/api/products/<int:pid>', methods=['DELETE'])
@admin_required
def delete_product(pid):
    db = get_db()
    db.execute('DELETE FROM products WHERE id=?', (pid,))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    db = get_db()
    items = data.get('items', [])
    order_items = []
    total = 0.0
    for item in items:
        pid = item['product_id']
        qty = item['quantity']
        p = db.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
        if not p or p['stock'] < qty or p['is_sold']:
            return jsonify({'error': f'Product {pid} unavailable'}), 400
        db.execute('UPDATE products SET stock=stock-? WHERE id=?', (qty, pid))
        order_items.append({'product_id': pid, 'name': p['name'], 'price': p['price'], 'quantity': qty})
        total += p['price'] * qty
        if p['stock'] - qty <= 0:
            db.execute('UPDATE products SET is_sold=1 WHERE id=?', (pid,))
    db.execute('INSERT INTO orders (customer_id,customer_name,customer_username,items,total_amount,payment_method) VALUES (?,?,?,?,?,?)',
               (data.get('customer_id'), data.get('customer_name',''), data.get('customer_username',''),
                json.dumps(order_items), total, data.get('payment_method','Telebirr')))
    db.commit()
    return jsonify({'order_id': db.execute('SELECT last_insert_rowid()').fetchone()[0]})

@app.route('/api/orders', methods=['GET'])
def get_orders():
    customer_id = request.args.get('customer_id')
    db = get_db()
    if request.args.get('all'):
        auth = request.headers.get('Authorization')
        if not auth or not auth.startswith('Bearer '):
            return jsonify({'error':'Unauthorized'}), 401
        if not db.execute('SELECT token FROM admin_tokens WHERE token=?', (auth.split(' ')[1],)).fetchone():
            return jsonify({'error':'Unauthorized'}), 401
        rows = db.execute('SELECT * FROM orders ORDER BY id DESC').fetchall()
    elif customer_id:
        rows = db.execute('SELECT * FROM orders WHERE customer_id=? ORDER BY id DESC', (customer_id,)).fetchall()
    else:
        return jsonify([])
    return jsonify([{ 'id': r['id'], 'customer_id': r['customer_id'], 'customer_name': r['customer_name'],
                     'customer_username': r['customer_username'], 'items': json.loads(r['items']),
                     'total': r['total_amount'], 'status': r['status'] } for r in rows])

@app.route('/api/orders/<int:oid>/status', methods=['PUT'])
@admin_required
def update_order_status(oid):
    db = get_db()
    db.execute('UPDATE orders SET status=? WHERE id=?', (request.get_json()['status'], oid))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    if request.get_json().get('password') == PASSWORD:
        token = str(uuid.uuid4())
        get_db().execute('INSERT INTO admin_tokens (token) VALUES (?)', (token,))
        get_db().commit()
        return jsonify({'token': token})
    return jsonify({'error': 'Wrong password'}), 403

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# Initialize DB
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
