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

def send_telegram(text, chat_id=None, reply_markup=None):
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE": return
    target = chat_id or ADMIN_CHAT_ID
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": target, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"Send error: {e}")

def send_to_all_users(message, photo_url=None, video_url=None):
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return 0
    
    chat_ids = set()
    
    # Get IDs from orders
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT customer_id FROM orders WHERE customer_id IS NOT NULL AND customer_id != '' AND customer_id != 'None'").fetchall()
    conn.close()
    for row in rows:
        cid = str(row['customer_id']).strip()
        if cid and cid != 'None' and cid != '':
            chat_ids.add(cid)
    
    # Always include admin
    chat_ids.add(str(ADMIN_CHAT_ID))
    
    # Get recent Telegram users
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?limit=100"
        resp = requests.get(url, timeout=10).json()
        if resp.get('ok') and resp.get('result'):
            for update in resp['result']:
                cid = None
                if 'message' in update:
                    cid = str(update['message']['chat']['id'])
                elif 'callback_query' in update:
                    cid = str(update['callback_query']['message']['chat']['id'])
                if cid:
                    chat_ids.add(cid)
    except:
        pass
    
    print(f"📣 Broadcasting to {len(chat_ids)} users")
    
    keyboard = {"inline_keyboard": [[{"text": "💎 Open GEM CART", "web_app": {"url": WEB_APP_URL}}]]}
    sent_count = 0
    
    for chat_id in chat_ids:
        try:
            if video_url:
                r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
                    data={"chat_id": chat_id, "video": video_url, "caption": message or "", "reply_markup": json.dumps(keyboard)}, timeout=15)
            elif photo_url:
                r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    data={"chat_id": chat_id, "photo": photo_url, "caption": message or "", "reply_markup": json.dumps(keyboard)}, timeout=15)
            else:
                r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": message, "parse_mode": "HTML", "reply_markup": keyboard}, timeout=10)
            if r.json().get('ok'):
                sent_count += 1
            time_module.sleep(0.3)
        except Exception as e:
            print(f"Failed {chat_id}: {e}")
    
    print(f"✅ Sent to {sent_count}/{len(chat_ids)}")
    
    # Save to DB
    conn = get_db()
    conn.execute('INSERT INTO broadcasts (time, message, photo) VALUES (?, ?, ?)',
        [datetime.now().isoformat(), message, photo_url or video_url or ''])
    conn.commit()
    conn.close()
    
    return sent_count

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
    conn.execute('INSERT INTO orders (id,date,customer_name,customer_username,customer_id,items,total,status) VALUES (?,?,?,?,?,?,?,?)',
        [oid,datetime.now().isoformat(),data.get('customerName',''),data.get('customerUsername',''),
         str(data.get('customerId','')),str(items),data.get('total',0),'pending'])
    conn.commit()
    conn.close()
    
    customer = data.get('customerName','Unknown')
    username = data.get('customerUsername','@unknown')
    total = data.get('total',0)
    items_text = "\n".join([f"• {i.get('name','?')} × {i.get('qty',1)}" for i in items])
    msg = f"💎 <b>NEW ORDER!</b>\n\n🆔 {oid}\n👤 {customer}\n📧 {username}\n💰 {total:,} Birr\n\n📋 <b>Items:</b>\n{items_text}\n\n💳 Telebirr: {TELEBIRR_NUMBER} ({TELEBIRR_NAME})"
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
    message = data.get('message','')
    photo = data.get('photo','')
    
    # Save to DB
    conn = get_db()
    conn.execute('INSERT INTO broadcasts (time,message,photo) VALUES (?,?,?)',
        [datetime.now().isoformat(), message, photo])
    conn.commit()
    conn.close()
    
    # Send to all Telegram users
    if message or photo:
        count = send_to_all_users(message, photo_url=photo if photo else None)
        return jsonify({"success":True,"sent":count})
    
    return jsonify({"success":True})

@app.route('/health')
def health():
    return jsonify({"status":"healthy"})

# ============ TELEGRAM BOT ============
processed_updates = set()

def run_bot():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Bot token not set.")
        return
    
    def send_msg(chat_id, text, reply_markup=None):
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        try:
            requests.post(url, json=data, timeout=10)
        except:
            pass
    
    def is_admin(chat_id):
        return str(chat_id) == str(ADMIN_CHAT_ID)
    
    def handle_update(update):
        update_id = update.get("update_id", 0)
        if update_id in processed_updates:
            return
        processed_updates.add(update_id)
        if len(processed_updates) > 1000:
            processed_updates.clear()
        
        if "message" in update:
            msg = update["message"]
            chat_id = str(msg["chat"]["id"])
            text = msg.get("text", "")
            first_name = msg.get("from", {}).get("first_name", "Customer")
            
            # Save customer ID
            if not is_admin(chat_id):
                conn = get_db()
                conn.execute('UPDATE orders SET customer_id=? WHERE customer_username=? AND customer_id=""',
                    [chat_id, msg.get("from", {}).get("username", "")])
                conn.commit()
                conn.close()
            
            if text == "/start":
                # WELCOME MESSAGE WITH OPEN GEM CART BUTTON
                keyboard = {
                    "inline_keyboard": [[
                        {"text": "💎 Open GEM CART", "web_app": {"url": WEB_APP_URL}}
                    ]]
                }
                if is_admin(chat_id):
                    send_msg(chat_id, f"✨ <b>Welcome Admin!</b>\n\n💎 GEM CART is ready for you.\n\n🛍️ Tap below to open the shop:\n📣 Use /broadcast to send messages to customers.", keyboard)
                else:
                    send_msg(chat_id, f"✨ <b>Welcome to GEM CART, {first_name}!</b>\n\n💎 Discover our luxury collection of premium accessories.\n\n🛍️ Tap the button below to start shopping:", keyboard)
            
            elif text == "/admin" and is_admin(chat_id):
                send_msg(chat_id, f"🔐 <b>Admin Commands:</b>\n\n/broadcast - Send text to all users\n/broadcast_photo - Send photo + caption\n/broadcast_video - Send video + caption\n\nPassword: <code>{ADMIN_PASSWORD}</code>")
            
            elif text == "/broadcast" and is_admin(chat_id):
                pending_broadcasts[chat_id] = {"type": "text"}
                send_msg(chat_id, "📣 <b>Send Broadcast</b>\n\nType your message now. It will be sent to ALL users.")
            
            elif text == "/broadcast_photo" and is_admin(chat_id):
                pending_broadcasts[chat_id] = {"type": "photo", "caption": ""}
                send_msg(chat_id, "📷 <b>Send Photo Broadcast</b>\n\n1. First, type your caption.\n2. Then send the photo.")
            
            elif text == "/broadcast_video" and is_admin(chat_id):
                pending_broadcasts[chat_id] = {"type": "video", "caption": ""}
                send_msg(chat_id, "🎬 <b>Send Video Broadcast</b>\n\n1. First, type your caption.\n2. Then send the video.")
            
            elif text == "/help":
                keyboard = {"inline_keyboard": [[{"text": "💎 Open GEM CART", "web_app": {"url": WEB_APP_URL}}]]}
                send_msg(chat_id, "💎 <b>GEM CART Help</b>\n\n/start - Open the shop\n/help - This message\n\n📱 Payment via Telebirr:\n📞 {TELEBIRR_NUMBER} ({TELEBIRR_NAME})", keyboard)
            
            # Handle pending broadcast
            elif chat_id in pending_broadcasts and is_admin(chat_id):
                pending = pending_broadcasts[chat_id]
                if pending["type"] in ["photo", "video"] and not pending.get("caption"):
                    pending["caption"] = text
                    send_msg(chat_id, f"✅ Caption saved!\n\nNow send the {'photo' if pending['type']=='photo' else 'video'}.")
                else:
                    count = send_to_all_users(text)
                    del pending_broadcasts[chat_id]
                    send_msg(chat_id, f"✅ Broadcast sent to {count} users!")
            
            # Handle photo upload
            elif "photo" in msg and chat_id in pending_broadcasts and is_admin(chat_id):
                pending = pending_broadcasts[chat_id]
                if pending["type"] == "photo":
                    photos = msg["photo"]
                    file_id = photos[-1]["file_id"]
                    try:
                        file_resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
                        file_path = file_resp.get("result", {}).get("file_path", "")
                        photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                        count = send_to_all_users(pending.get("caption",""), photo_url=photo_url)
                        del pending_broadcasts[chat_id]
                        send_msg(chat_id, f"✅ Photo broadcast sent to {count} users!")
                    except:
                        del pending_broadcasts[chat_id]
                        send_msg(chat_id, "❌ Failed.")
            
            # Handle video upload
            elif "video" in msg and chat_id in pending_broadcasts and is_admin(chat_id):
                pending = pending_broadcasts[chat_id]
                if pending["type"] == "video":
                    file_id = msg["video"]["file_id"]
                    try:
                        file_resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
                        file_path = file_resp.get("result", {}).get("file_path", "")
                        video_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                        count = send_to_all_users(pending.get("caption",""), video_url=video_url)
                        del pending_broadcasts[chat_id]
                        send_msg(chat_id, f"✅ Video broadcast sent to {count} users!")
                    except:
                        del pending_broadcasts[chat_id]
                        send_msg(chat_id, "❌ Failed.")
        
        elif "callback_query" in update:
            cb = update["callback_query"]
            chat_id = str(cb["message"]["chat"]["id"])
            data = cb.get("data", "")
            if data == "broadcast" and is_admin(chat_id):
                send_msg(chat_id, "📣 <b>Broadcast:</b>\n\n/broadcast - Text\n/broadcast_photo - Photo\n/broadcast_video - Video")
    
    last_update_id = 0
    print("🤖 Bot started!")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
            response = requests.get(url, timeout=35)
            data = response.json()
            if data.get("ok") and data.get("result"):
                for update in data["result"]:
                    update_id = update.get("update_id", 0)
                    if update_id > last_update_id:
                        last_update_id = update_id
                    handle_update(update)
        except Exception as e:
            print(f"Bot error: {e}")
        time_module.sleep(1)

if BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
    threading.Thread(target=run_bot, daemon=True).start()
    print("🤖 Bot started!")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
