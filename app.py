from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
import threading
from datetime import datetime
import requests

app = Flask(__name__)
CORS(app)

# ============ CONFIGURATION ============
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # ← Paste your real bot token
ADMIN_CHAT_ID = "7715442708"        # ← Your Telegram ID (already set)
TELEBIRR_NUMBER = "251990066832"
TELEBIRR_NAME = "Biruk"

# ============ DATABASE ============
def get_db():
    conn = sqlite3.connect('gemcart.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, category TEXT,
        gender TEXT, price INTEGER, description TEXT, size TEXT,
        photos TEXT, stock INTEGER DEFAULT 0, discount INTEGER DEFAULT 0,
        featured INTEGER DEFAULT 0, visible INTEGER DEFAULT 1, sold INTEGER DEFAULT 0
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY, date TEXT, customer_name TEXT,
        customer_username TEXT, customer_id TEXT, items TEXT,
        total INTEGER, status TEXT DEFAULT "pending"
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT,
        message TEXT, photo TEXT
    )''')
    count = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    if count == 0:
        conn.execute("INSERT INTO products (name,category,gender,price,description,size,photos,stock,discount,featured,visible,sold) VALUES ('Emerald Backpack','Bags','Male',2200,'Handcrafted backpack.','Large','https://placehold.co/400x400/0B2E1E/D4AF37?text=Backpack',5,0,1,1,0)")
        conn.execute("INSERT INTO products (name,category,gender,price,description,size,photos,stock,discount,featured,visible,sold) VALUES ('Golden Tote','Bags','Female',1200,'Premium canvas tote.','Medium','https://placehold.co/400x400/1A533E/F3D673?text=Tote',3,0,0,1,0)")
        conn.execute("INSERT INTO products (name,category,gender,price,description,size,photos,stock,discount,featured,visible,sold) VALUES ('Diamond Stickers','Stickers','Unisex',350,'50pcs stickers.',null,'https://placehold.co/400x400/0B2E1E/D4AF37?text=Stickers',20,10,1,1,0)")
        conn.execute("INSERT INTO products (name,category,gender,price,description,size,photos,stock,discount,featured,visible,sold) VALUES ('Crystal Bracelet','Jewelry','Female',450,'Natural crystal beads.','One Size','https://placehold.co/400x400/1A533E/F3D673?text=Bracelet',0,0,0,1,1)")
    conn.commit()
    conn.close()

init_db()

# ============ TELEGRAM NOTIFICATION ============
def send_telegram_message(chat_id, text):
    """Send message via Telegram bot"""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Bot token not set. Skipping notification.")
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        response = requests.post(url, json=data, timeout=10)
        print(f"📣 Notification sent: {response.status_code}")
    except Exception as e:
        print(f"❌ Notification failed: {e}")

def notify_new_order(order_id, customer_name, customer_username, items, total):
    """Send order notification to admin"""
    items_text = "\n".join([f"• {item['name']} × {item['qty']}" for item in items])
    message = (
        f"💎 <b>NEW GEM CART ORDER!</b>\n\n"
        f"🆔 <b>Order:</b> {order_id}\n"
        f"👤 <b>Customer:</b> {customer_name}\n"
        f"📧 <b>Username:</b> {customer_username}\n"
        f"💰 <b>Total:</b> {total:,} Birr\n\n"
        f"📋 <b>Items:</b>\n{items_text}\n\n"
        f"💳 <b>Payment:</b> Telebirr\n"
        f"📱 {TELEBIRR_NUMBER}\n"
        f"👤 {TELEBIRR_NAME}\n\n"
        f"<i>Contact the customer for payment confirmation.</i>"
    )
    send_telegram_message(ADMIN_CHAT_ID, message)

# ============ API ROUTES ============
@app.route('/')
def home():
    return jsonify({"status":"GEM CART API","version":"2.0"})

@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_db()
    rows = conn.execute('SELECT * FROM products WHERE visible=1').fetchall()
    conn.close()
    return jsonify([{
        "id":r["id"],"name":r["name"],"category":r["category"],
        "gender":r["gender"],"price":r["price"],"description":r["description"],
        "size":r["size"],"photos":r["photos"].split(",") if r["photos"] else [],
        "stock":r["stock"],"discount":r["discount"],
        "featured":bool(r["featured"]),"visible":bool(r["visible"]),"sold":bool(r["sold"])
    } for r in rows])

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    conn = get_db()
    conn.execute('INSERT INTO products (name,category,gender,price,description,size,photos,stock,discount,featured,visible,sold) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
        [data.get('name'),data.get('category'),data.get('gender'),data.get('price'),
         data.get('description'),data.get('size'),','.join(data.get('photos',[])),
         data.get('stock',1),data.get('discount',0),1 if data.get('featured') else 0,
         1 if data.get('visible')!=False else 0,1 if data.get('sold') else 0])
    conn.commit()
    conn.close()
    return jsonify({"success":True})

@app.route('/api/products/<int:id>', methods=['PUT'])
def update_product(id):
    data = request.json
    conn = get_db()
    conn.execute('UPDATE products SET name=?, category=?, gender=?, price=?, description=?, size=?, photos=?, stock=?, discount=?, featured=?, visible=?, sold=? WHERE id=?',
        [data.get('name'),data.get('category'),data.get('gender'),data.get('price'),
         data.get('description'),data.get('size'),','.join(data.get('photos',[])),
         data.get('stock',1),data.get('discount',0),
         1 if data.get('featured') else 0,1 if data.get('visible')!=False else 0,
         1 if data.get('sold') else 0,id])
    conn.commit()
    conn.close()
    return jsonify({"success":True})

@app.route('/api/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    conn = get_db()
    conn.execute('DELETE FROM products WHERE id=?',[id])
    conn.commit()
    conn.close()
    return jsonify({"success":True})

@app.route('/api/orders', methods=['GET'])
def get_orders():
    conn = get_db()
    rows = conn.execute('SELECT * FROM orders ORDER BY date DESC').fetchall()
    conn.close()
    return jsonify([{
        "id":r["id"],"date":r["date"],"customerName":r["customer_name"],
        "customerUsername":r["customer_username"],"customerId":r["customer_id"],
        "items":eval(r["items"]) if r["items"] else [],
        "total":r["total"],"status":r["status"]
    } for r in rows])

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    oid = "GEM-" + datetime.now().strftime("%Y%m%d%H%M%S")
    conn = get_db()
    
    # Decrease stock
    items = data.get('items',[])
    for item in items:
        conn.execute('UPDATE products SET stock=MAX(0,stock-?), sold=CASE WHEN stock-?<=0 THEN 1 ELSE sold END WHERE name=?',
            [item.get('qty',1),item.get('qty',1),item.get('name')])
    
    # Insert order
    conn.execute('INSERT INTO orders (id,date,customer_name,customer_username,customer_id,items,total,status) VALUES (?,?,?,?,?,?,?,?)',
        [oid,datetime.now().isoformat(),data.get('customerName',''),data.get('customerUsername',''),
         str(data.get('customerId','')),str(items),data.get('total',0),'pending'])
    conn.commit()
    conn.close()
    
    # 🔔 SEND TELEGRAM NOTIFICATION
    customer_name = data.get('customerName','Unknown')
    customer_username = data.get('customerUsername','@unknown')
    total = data.get('total',0)
    threading.Thread(target=notify_new_order, args=(oid, customer_name, customer_username, items, total)).start()
    
    return jsonify({"success":True,"orderId":oid})

@app.route('/api/orders/<string:id>', methods=['PUT'])
def update_order(id):
    data = request.json
    conn = get_db()
    conn.execute('UPDATE orders SET status=? WHERE id=?',[data.get('status'),id])
    conn.commit()
    conn.close()
    return jsonify({"success":True})

@app.route('/api/broadcasts', methods=['GET'])
def get_broadcasts():
    conn = get_db()
    rows = conn.execute('SELECT * FROM broadcasts ORDER BY time DESC').fetchall()
    conn.close()
    return jsonify([{"id":r["id"],"time":r["time"],"message":r["message"],"photo":r["photo"]} for r in rows])

@app.route('/api/broadcasts', methods=['POST'])
def add_broadcast():
    data = request.json
    conn = get_db()
    conn.execute('INSERT INTO broadcasts (time,message,photo) VALUES (?,?,?)',
        [datetime.now().isoformat(),data.get('message'),data.get('photo')])
    conn.commit()
    conn.close()
    return jsonify({"success":True})

@app.route('/api/admin/verify', methods=['POST'])
def verify_admin():
    data = request.json
    ADMIN_IDS = [7715442708, 5960149589]
    user_id = data.get('userId')
    if user_id in ADMIN_IDS:
        return jsonify({"admin":True})
    return jsonify({"admin":False})

@app.route('/health')
def health():
    return jsonify({"status":"healthy"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0',port=port)
