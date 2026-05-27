from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
import requests
import threading
import time as time_module
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ============ CONFIGURATION ============
BOT_TOKEN = "8924432232:AAFLyaI-3CozY3oxfBeGVZ9hu-bhsuGWlVY"  # ← REPLACE WITH YOUR REAL TOKEN
ADMIN_CHAT_ID = "7715442708"
TELEBIRR_NUMBER = "251990066832"
TELEBIRR_NAME = "Biruk"
ADMIN_PASSWORD = "sadmin"
WEB_APP_URL = "https://primesador-maker.github.io/gemcart/"

pending_broadcasts = {}
processed_updates = set()

def telegram_request(method, data):
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return None
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
        response = requests.post(url, data=data, timeout=15)
        return response.json()
    except Exception as e:
        print(f"API error: {e}")
        return None

def send_message(chat_id, text, reply_markup=None):
    """Send message with proper error logging"""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Bot token not set")
        return None
    
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        response = requests.post(url, data=data, timeout=15)
        result = response.json()
        
        if result.get("ok"):
            print(f"✅ Message sent to {chat_id}")
        else:
            print(f"❌ FAILED {chat_id}: Error {result.get('error_code')} - {result.get('description')}")
        
        return result
    except Exception as e:
        print(f"❌ Exception for {chat_id}: {e}")
        return None

def get_all_chat_ids():
    chat_ids = set()
    chat_ids.add(str(ADMIN_CHAT_ID))
    try:
        result = telegram_request("getUpdates", {"limit": 200})
        if result and result.get("ok") and result.get("result"):
            for update in result["result"]:
                cid = None
                if "message" in update:
                    cid = str(update["message"]["chat"]["id"])
                elif "callback_query" in update:
                    cid = str(update["callback_query"]["message"]["chat"]["id"])
                if cid:
                    chat_ids.add(cid)
    except:
        pass
    print(f"📊 Found {len(chat_ids)} chat IDs: {chat_ids}")
    return chat_ids

def broadcast_to_all(message, photo_url=None, video_url=None):
    chat_ids = get_all_chat_ids()
    
    if len(chat_ids) == 0:
        print("⚠️ No users found")
        return 0
    
    print(f"📣 Broadcasting to {len(chat_ids)} users...")
    
    keyboard = {"inline_keyboard": [[{"text": "💎 Open GEM CART", "web_app": {"url": WEB_APP_URL}}]]}
    sent = 0
    failed = 0
    
    for cid in chat_ids:
        try:
            if video_url:
                r = telegram_request("sendVideo", {"chat_id": cid, "video": video_url, "caption": message or "", "reply_markup": json.dumps(keyboard)})
            elif photo_url:
                r = telegram_request("sendPhoto", {"chat_id": cid, "photo": photo_url, "caption": message or "", "reply_markup": json.dumps(keyboard)})
            else:
                r = send_message(cid, message, keyboard)
            
            if r and r.get("ok"):
                sent += 1
            else:
                failed += 1
            
            time_module.sleep(0.5)
        except Exception as e:
            failed += 1
            print(f"  ❌ Error for {cid}: {e}")
    
    print(f"✅ Broadcast: {sent} sent, {failed} failed")
    
    try:
        conn = get_db()
        conn.execute('INSERT INTO broadcasts (time, message, photo) VALUES (?, ?, ?)',
            [datetime.now().isoformat(), message, photo_url or video_url or ''])
        conn.commit()
        conn.close()
    except:
        pass
    
    return sent

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

# ============ API ROUTES ============
@app.route('/')
def home():
    return jsonify({"status":"GEM CART API"})

@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_db()
    rows = conn.execute('SELECT * FROM products WHERE visible=1').fetchall()
    conn.close()
    return jsonify([{"id":r["id"],"name":r["name"],"category":r["category"],"gender":r["gender"],"price":r["price"],"description":r["description"],"size":r["size"],"photos":r["photos"].split(",") if r["photos"] else [],"stock":r["stock"],"discount":r["discount"],"featured":bool(r["featured"]),"visible":bool(r["visible"]),"sold":bool(r["sold"])} for r in rows])

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    conn = get_db()
    conn.execute('INSERT INTO products (name,category,gender,price,description,size,photos,stock,discount,featured,visible,sold) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',[data.get('name'),data.get('category'),data.get('gender'),data.get('price'),data.get('description'),data.get('size'),','.join(data.get('photos',[])),data.get('stock',1),data.get('discount',0),1 if data.get('featured') else 0,1 if data.get('visible')!=False else 0,1 if data.get('sold') else 0])
    conn.commit();conn.close()
    return jsonify({"success":True})

@app.route('/api/products/<int:id>', methods=['PUT'])
def update_product(id):
    data = request.json
    conn = get_db()
    conn.execute('UPDATE products SET name=?, category=?, gender=?, price=?, description=?, size=?, photos=?, stock=?, discount=?, featured=?, visible=?, sold=? WHERE id=?',[data.get('name'),data.get('category'),data.get('gender'),data.get('price'),data.get('description'),data.get('size'),','.join(data.get('photos',[])),data.get('stock',1),data.get('discount',0),1 if data.get('featured') else 0,1 if data.get('visible')!=False else 0,1 if data.get('sold') else 0,id])
    conn.commit();conn.close()
    return jsonify({"success":True})

@app.route('/api/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    conn = get_db();conn.execute('DELETE FROM products WHERE id=?',[id]);conn.commit();conn.close()
    return jsonify({"success":True})

@app.route('/api/orders', methods=['GET'])
def get_orders():
    conn = get_db()
    rows = conn.execute('SELECT * FROM orders ORDER BY date DESC').fetchall()
    conn.close()
    return jsonify([{"id":r["id"],"date":r["date"],"customerName":r["customer_name"],"customerUsername":r["customer_username"],"items":eval(r["items"]) if r["items"] else [],"total":r["total"],"status":r["status"]} for r in rows])

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    oid = "GEM-" + datetime.now().strftime("%Y%m%d%H%M%S")
    conn = get_db()
    items = data.get('items',[])
    for item in items:
        item_name = item.get('name','');item_qty = item.get('qty',1)
        current = conn.execute('SELECT stock FROM products WHERE name=?',[item_name]).fetchone()
        if current:
            new_stock = max(0, current['stock'] - item_qty)
            conn.execute('UPDATE products SET stock=?, sold=? WHERE name=?',[new_stock, 1 if new_stock<=0 else 0, item_name])
    conn.execute('INSERT INTO orders (id,date,customer_name,customer_username,customer_id,items,total,status) VALUES (?,?,?,?,?,?,?,?)',[oid,datetime.now().isoformat(),data.get('customerName',''),data.get('customerUsername',''),str(data.get('customerId','')),str(items),data.get('total',0),'pending'])
    conn.commit();conn.close()
    customer = data.get('customerName','Unknown');username = data.get('customerUsername','@unknown');total = data.get('total',0)
    items_text = "\n".join([f"• {i.get('name','?')} × {i.get('qty',1)}" for i in items])
    msg = f"💎 <b>NEW ORDER!</b>\n\n🆔 {oid}\n👤 {customer}\n📧 {username}\n💰 {total:,} Birr\n\n📋 <b>Items:</b>\n{items_text}\n\n💳 Telebirr: {TELEBIRR_NUMBER} ({TELEBIRR_NAME})"
    threading.Thread(target=send_message, args=(ADMIN_CHAT_ID, msg)).start()
    return jsonify({"success":True,"orderId":oid})

@app.route('/api/orders/<string:id>', methods=['PUT'])
def update_order(id):
    data = request.json;conn = get_db()
    conn.execute('UPDATE orders SET status=? WHERE id=?',[data.get('status'),id]);conn.commit();conn.close()
    return jsonify({"success":True})

@app.route('/api/broadcasts', methods=['GET'])
def get_broadcasts():
    conn = get_db();rows = conn.execute('SELECT * FROM broadcasts ORDER BY time DESC').fetchall();conn.close()
    return jsonify([{"id":r["id"],"time":r["time"],"message":r["message"],"photo":r["photo"]} for r in rows])

@app.route('/api/broadcasts', methods=['POST'])
def add_broadcast():
    data = request.json;message = data.get('message','');photo = data.get('photo','')
    conn = get_db();conn.execute('INSERT INTO broadcasts (time,message,photo) VALUES (?,?,?)',[datetime.now().isoformat(),message,photo]);conn.commit();conn.close()
    count = broadcast_to_all(message, photo_url=photo if photo else None)
    return jsonify({"success":True,"sent":count})

@app.route('/health')
def health():
    return jsonify({"status":"healthy"})

# ============ TELEGRAM BOT ============
def handle_bot_message(msg):
    chat_id = str(msg["chat"]["id"])
    text = msg.get("text", "")
    first_name = msg.get("from", {}).get("first_name", "Customer")
    is_admin = (chat_id == str(ADMIN_CHAT_ID))
    
    print(f"📩 [{first_name}] {text}")
    
    if text == "/start":
        keyboard = {"inline_keyboard": [[{"text": "💎 Open GEM CART", "web_app": {"url": WEB_APP_URL}}]]}
        send_message(chat_id, f"✨ <b>Welcome to GEM CART, {first_name}!</b>\n\n💎 Discover our luxury collection.\n🛍️ Tap below to start shopping:", keyboard)
        return
    
    if text == "/help":
        keyboard = {"inline_keyboard": [[{"text": "💎 Open GEM CART", "web_app": {"url": WEB_APP_URL}}]]}
        send_message(chat_id, f"💎 <b>GEM CART Help</b>\n\n/start - Open shop\n/help - Help\n\n📱 Telebirr: {TELEBIRR_NUMBER}", keyboard)
        return
    
    if text == "/admin" and is_admin:
        send_message(chat_id, f"🔐 <b>Admin:</b>\n\n/broadcast - Text to all\n/broadcast_photo - Photo to all\n/broadcast_video - Video to all")
        return
    
    if text == "/broadcast" and is_admin:
        pending_broadcasts[chat_id] = {"type": "text"}
        send_message(chat_id, "📣 Type your broadcast message:")
        return
    
    if text == "/broadcast_photo" and is_admin:
        pending_broadcasts[chat_id] = {"type": "photo", "caption": ""}
        send_message(chat_id, "📷 Type caption first, then send photo:")
        return
    
    if text == "/broadcast_video" and is_admin:
        pending_broadcasts[chat_id] = {"type": "video", "caption": ""}
        send_message(chat_id, "🎬 Type caption first, then send video:")
        return
    
    if chat_id in pending_broadcasts and is_admin:
        pending = pending_broadcasts[chat_id]
        if pending["type"] in ["photo", "video"] and not pending.get("caption"):
            pending["caption"] = text
            send_message(chat_id, f"✅ Caption saved! Send the {'photo' if pending['type']=='photo' else 'video'} now.")
        else:
            count = broadcast_to_all(text)
            del pending_broadcasts[chat_id]
            send_message(chat_id, f"✅ Sent to {count} users!")
        return
    
    if "photo" in msg and chat_id in pending_broadcasts and is_admin:
        pending = pending_broadcasts[chat_id]
        if pending["type"] == "photo":
            file_id = msg["photo"][-1]["file_id"]
            try:
                fr = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
                fp = fr.get("result",{}).get("file_path","")
                photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{fp}"
                count = broadcast_to_all(pending.get("caption",""), photo_url=photo_url)
                del pending_broadcasts[chat_id]
                send_message(chat_id, f"✅ Photo sent to {count} users!")
            except:
                del pending_broadcasts[chat_id]
                send_message(chat_id, "❌ Failed")
        return
    
    if "video" in msg and chat_id in pending_broadcasts and is_admin:
        file_id = msg["video"]["file_id"]
        try:
            fr = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
            fp = fr.get("result",{}).get("file_path","")
            video_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{fp}"
            count = broadcast_to_all(pending_broadcasts[chat_id].get("caption",""), video_url=video_url)
            del pending_broadcasts[chat_id]
            send_message(chat_id, f"✅ Video sent to {count} users!")
        except:
            del pending_broadcasts[chat_id]
            send_message(chat_id, "❌ Failed")
        return

def run_bot():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Bot token not set")
        return
    
    print("🤖 Bot started!")
    offset = 0
    
    while True:
        try:
            result = telegram_request("getUpdates", {"offset": offset, "timeout": 30})
            
            if result and result.get("ok") and result.get("result"):
                for update in result["result"]:
                    uid = update.get("update_id", 0)
                    offset = max(offset, uid + 1)
                    
                    if uid in processed_updates:
                        continue
                    processed_updates.add(uid)
                    
                    if len(processed_updates) > 500:
                        processed_updates.clear()
                    
                    if "message" in update:
                        handle_bot_message(update["message"])
        
        except Exception as e:
            print(f"Bot error: {e}")
        
        time_module.sleep(1)

if BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
    threading.Thread(target=run_bot, daemon=True).start()
    print("🤖 Bot started!")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
