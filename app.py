from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
import requests
import threading
import asyncio
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ============ CONFIG ============
BOT_TOKEN = "8924432232:AAFLyaI-3CozY3oxfBeGVZ9hu-bhsuGWlVY"  # ← REPLACE WITH YOUR REAL TOKEN
ADMIN_CHAT_ID = "7715442708"
TELEBIRR_NUMBER = "251990066832"
TELEBIRR_NAME = "Biruk"
WEB_APP_URL = "https://primesador-maker.github.io/gemcart/"

def send_telegram(text):
    if BOT_TOKEN == "8924432232:AAFLyaI-3CozY3oxfBeGVZ9hu-bhsuGWlVY": return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": ADMIN_CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        print(f"Notification error: {e}")

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
        customer_username TEXT, items TEXT, total INTEGER,
        status TEXT DEFAULT "pending"
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

# ============ API ROUTES ============
@app.route('/')
def home():
    return jsonify({"status":"GEM CART API"})

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
         data.get('stock',1),data.get('discount',0),1 if data.get('featured') else 0,
         1 if data.get('visible')!=False else 0,1 if data.get('sold') else 0,id])
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
        "customerUsername":r["customer_username"],
        "items":eval(r["items"]) if r["items"] else [],
        "total":r["total"],"status":r["status"]
    } for r in rows])

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    oid = "GEM-" + datetime.now().strftime("%Y%m%d%H%M%S")
    conn = get_db()
    items = data.get('items',[])
    for item in items:
        item_name = item.get('name','')
        item_qty = item.get('qty',1)
        current = conn.execute('SELECT stock FROM products WHERE name=?',[item_name]).fetchone()
        if current:
            new_stock = max(0, current['stock'] - item_qty)
            sold_flag = 1 if new_stock <= 0 else 0
            conn.execute('UPDATE products SET stock=?, sold=? WHERE name=?',[new_stock, sold_flag, item_name])
    conn.execute('INSERT INTO orders (id,date,customer_name,customer_username,items,total,status) VALUES (?,?,?,?,?,?,?)',
        [oid,datetime.now().isoformat(),data.get('customerName',''),data.get('customerUsername',''),str(items),data.get('total',0),'pending'])
    conn.commit()
    conn.close()
    
    customer = data.get('customerName','Unknown')
    username = data.get('customerUsername','@unknown')
    total = data.get('total',0)
    items_text = "\n".join([f"• {i.get('name','?')} × {i.get('qty',1)}" for i in items])
    msg = f"💎 NEW ORDER!\n\n🆔 {oid}\n👤 {customer}\n📧 {username}\n💰 {total:,} Birr\n\n📋 Items:\n{items_text}\n\n💳 Telebirr: {TELEBIRR_NUMBER} ({TELEBIRR_NAME})"
    threading.Thread(target=send_telegram, args=(msg,)).start()
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

@app.route('/health')
def health():
    return jsonify({"status":"healthy"})

# ============ TELEGRAM BOT ============
def run_bot():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Bot token not set. Bot not starting.")
        return
    
    import time as time_module
    
    def send_message(chat_id, text, reply_markup=None):
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = reply_markup
        try:
            requests.post(url, json=data, timeout=10)
        except:
            pass
    
    def handle_update(update):
        if "message" not in update: return
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")
        first_name = msg.get("from", {}).get("first_name", "Customer")
        
        if text == "/start":
            keyboard = {
                "inline_keyboard": [[
                    {"text": "💎 Open GEM CART", "web_app": {"url": WEB_APP_URL}}
                ]]
            }
            greeting = f"✨ <b>Welcome to GEM CART, {first_name}!</b>\n\n💎 Discover our luxury collection of premium accessories.\n\n🛍️ Tap the button below to start shopping:"
            send_message(chat_id, greeting, str(keyboard).replace("'", '"'))
        
        elif text == "/help":
            send_message(chat_id, "💎 <b>GEM CART Help</b>\n\n/start - Open the shop\n/help - This message\n\n📱 For orders, pay via Telebirr:\n📞 {TELEBIRR_NUMBER} ({TELEBIRR_NAME})")
        
        elif text == "/admin":
            if str(chat_id) == ADMIN_CHAT_ID:
                send_message(chat_id, "🔐 <b>Admin Panel</b>\n\nOpen the Mini App and click ⚙️ to manage:\n📦 Products\n📋 Orders\n📣 Broadcasts\n⚙️ Settings")
            else:
                send_message(chat_id, "❌ Admin access only.")
    
    last_update_id = 0
    print("🤖 Bot started! Waiting for messages...")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
            response = requests.get(url, timeout=35)
            data = response.json()
            
            if data.get("ok") and data.get("result"):
                for update in data["result"]:
                    last_update_id = update["update_id"]
                    threading.Thread(target=handle_update, args=(update,)).start()
        except Exception as e:
            print(f"Bot error: {e}")
        time_module.sleep(2)

# Start bot in background
if BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
    threading.Thread(target=run_bot, daemon=True).start()
    print("🤖 Bot thread started!")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
