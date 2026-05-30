import os, json, uuid, threading, sqlite3
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from werkzeug.utils import secure_filename
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

PASSWORD = 'sadmin'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('gemcart.db')
        g.db.row_factory = sqlite3.Row
    return g.db

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, username TEXT, chat_id INTEGER);
            CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, price REAL NOT NULL, category TEXT DEFAULT 'Uncategorized', gender TEXT DEFAULT 'Unisex', images TEXT DEFAULT '[]', video TEXT, stock INTEGER DEFAULT 1, is_sold INTEGER DEFAULT 0, is_hidden INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL, customer_name TEXT, customer_username TEXT, items TEXT, total_amount REAL, payment_method TEXT DEFAULT 'Telebirr', status TEXT DEFAULT 'pending');
            CREATE TABLE IF NOT EXISTS admin_tokens (token TEXT PRIMARY KEY);
        ''')
        db.commit()

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None: db.close()

def admin_required(f):
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization')
        if not auth or not auth.startswith('Bearer '): return jsonify({'error':'Unauthorized'}), 401
        token = auth.split(' ')[1]
        if not get_db().execute('SELECT token FROM admin_tokens WHERE token=?',(token,)).fetchone():
            return jsonify({'error':'Invalid token'}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@app.route('/')
def home(): return jsonify({'status':'GEM CART API is running'})

@app.route('/api/categories', methods=['GET'])
def get_categories():
    return jsonify({'categories': [r['name'] for r in get_db().execute('SELECT name FROM categories').fetchall()]})

@app.route('/api/categories', methods=['POST'])
@admin_required
def add_category():
    n = request.get_json().get('name','').strip()
    if not n: return jsonify({'error':'Name required'}), 400
    try:
        get_db().execute('INSERT INTO categories (name) VALUES (?)',(n,)); get_db().commit()
        return jsonify({'success':True})
    except: return jsonify({'error':'Exists'}), 400

@app.route('/api/categories/<name>', methods=['DELETE'])
@admin_required
def delete_category(name):
    get_db().execute('DELETE FROM categories WHERE name=?',(name,)); get_db().commit()
    return jsonify({'success':True})

@app.route('/api/products', methods=['GET'])
def get_products():
    rows = get_db().execute('SELECT * FROM products').fetchall()
    return jsonify({'products':[{ 'id':r['id'],'name':r['name'],'description':r['description'],'price':r['price'],'category':r['category'],'gender':r['gender'],'images':json.loads(r['images']),'video':r['video'],'stock':r['stock'],'is_sold':bool(r['is_sold']),'is_hidden':bool(r['is_hidden'])} for r in rows]})

@app.route('/api/products', methods=['POST'])
@admin_required
def add_product():
    n,p = request.form.get('name'), request.form.get('price')
    if not n or not p: return jsonify({'error':'Name and price required'}), 400
    imgs,v = [], None
    for f in request.files.getlist('files')[:5]:
        fn = secure_filename(f"{uuid.uuid4()}_{f.filename}")
        f.save(os.path.join(app.config['UPLOAD_FOLDER'],fn))
        if f.mimetype.startswith('video'): v = fn
        else: imgs.append(fn)
    get_db().execute('INSERT INTO products (name,description,price,category,gender,images,video,stock) VALUES (?,?,?,?,?,?,?,?)',
        (n,request.form.get('description',''),float(p),request.form.get('category','Uncategorized'),request.form.get('gender','Unisex'),json.dumps(imgs),v,int(request.form.get('stock',1))))
    get_db().commit()
    return jsonify({'success':True})

@app.route('/api/products/<int:pid>', methods=['PUT'])
@admin_required
def update_product(pid):
    d = request.get_json(); db = get_db(); p = db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
    if not p: return jsonify({'error':'Not found'}), 404
    if 'stock_increment' in d: db.execute('UPDATE products SET stock=? WHERE id=?',(p['stock']+d['stock_increment'],pid))
    if 'is_sold' in d: db.execute('UPDATE products SET is_sold=? WHERE id=?',(int(d['is_sold']),pid))
    if 'is_hidden' in d: db.execute('UPDATE products SET is_hidden=? WHERE id=?',(int(d['is_hidden']),pid))
    db.commit()
    if db.execute('SELECT stock FROM products WHERE id=?',(pid,)).fetchone()['stock'] <= 0:
        db.execute('UPDATE products SET is_sold=1 WHERE id=?',(pid,)); db.commit()
    return jsonify({'success':True})

@app.route('/api/products/<int:pid>', methods=['DELETE'])
@admin_required
def delete_product(pid):
    get_db().execute('DELETE FROM products WHERE id=?',(pid,)); get_db().commit()
    return jsonify({'success':True})

@app.route('/api/orders', methods=['POST'])
def create_order():
    d = request.get_json(); db = get_db(); items, total = [], 0.0
    for i in d.get('items',[]):
        p = db.execute('SELECT * FROM products WHERE id=?',(i['product_id'],)).fetchone()
        if not p or p['stock']<i['quantity'] or p['is_sold']: return jsonify({'error':f'Product {i["product_id"]} unavailable'}), 400
        db.execute('UPDATE products SET stock=stock-? WHERE id=?',(i['quantity'],i['product_id']))
        items.append({'product_id':i['product_id'],'name':p['name'],'price':p['price'],'quantity':i['quantity']})
        total += p['price']*i['quantity']
        if p['stock']-i['quantity'] <= 0: db.execute('UPDATE products SET is_sold=1 WHERE id=?',(i['product_id'],))
    db.execute('INSERT INTO orders (customer_id,customer_name,customer_username,items,total_amount,payment_method) VALUES (?,?,?,?,?,?)',
        (d.get('customer_id'),d.get('customer_name',''),d.get('customer_username',''),json.dumps(items),total,d.get('payment_method','Telebirr')))
    db.commit()
    return jsonify({'order_id': db.execute('SELECT last_insert_rowid()').fetchone()[0]})

@app.route('/api/orders', methods=['GET'])
def get_orders():
    cid = request.args.get('customer_id'); db = get_db()
    if request.args.get('all'):
        auth = request.headers.get('Authorization')
        if not auth or not auth.startswith('Bearer '): return jsonify({'error':'Unauthorized'}), 401
        if not db.execute('SELECT token FROM admin_tokens WHERE token=?',(auth.split(' ')[1],)).fetchone(): return jsonify({'error':'Unauthorized'}), 401
        rows = db.execute('SELECT * FROM orders ORDER BY id DESC').fetchall()
    elif cid: rows = db.execute('SELECT * FROM orders WHERE customer_id=? ORDER BY id DESC',(cid,)).fetchall()
    else: return jsonify([])
    return jsonify([{'id':r['id'],'customer_id':r['customer_id'],'customer_name':r['customer_name'],'customer_username':r['customer_username'],'items':json.loads(r['items']),'total':r['total_amount'],'status':r['status']} for r in rows])

@app.route('/api/orders/<int:oid>/status', methods=['PUT'])
@admin_required
def update_order_status(oid):
    get_db().execute('UPDATE orders SET status=? WHERE id=?',(request.get_json()['status'],oid)); get_db().commit()
    return jsonify({'success':True})

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    if request.get_json().get('password') == PASSWORD:
        t = str(uuid.uuid4()); get_db().execute('INSERT INTO admin_tokens (token) VALUES (?)',(t,)); get_db().commit()
        return jsonify({'token':t})
    return jsonify({'error':'Wrong password'}), 403

@app.route('/api/broadcast', methods=['POST'])
@admin_required
def broadcast():
    return jsonify({'success':True,'message':'Use bot /broadcast command instead'})

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)))
