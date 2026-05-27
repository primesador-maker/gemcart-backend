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
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # ← REPLACE WITH YOUR REAL TOKEN FROM BOTFATHER
ADMIN_CHAT_ID = "7715442708"
TELEBIRR_NUMBER = "251990066832"
TELEBIRR_NAME = "Biruk"
ADMIN_PASSWORD = "sadmin"
WEB_APP_URL = "https://primesador-maker.github.io/gemcart/"

# Store pending broadcast states for admin
pending_broadcasts = {}
# Track last processed update to avoid duplicates
last_update_id = 0


def telegram_request(method, data):
    """Make a request to Telegram Bot API"""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Bot token not set")
        return None
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
        response = requests.post(url, data=data, timeout=15)
        return response.json()
    except Exception as e:
        print(f"Telegram API error: {e}")
        return None


def send_message(chat_id, text, reply_markup=None):
    """Send a message to a specific Telegram chat"""
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    
    result = telegram_request("sendMessage", data)
    if result:
        if result.get("ok"):
            print(f"✅ Message sent to {chat_id}")
        else:
            print(f"❌ Failed to send to {chat_id}: {result.get('description')}")
    return result


def get_all_chat_ids():
    """Get all unique chat IDs from Telegram updates"""
    chat_ids = set()
    # Always include admin
    chat_ids.add(str(ADMIN_CHAT_ID))
    
    try:
        result = telegram_request("getUpdates", {"limit": 200})
        if result and result.get("ok") and result.get("result"):
            for update in result["result"]:
                chat_id = None
                if "message" in update:
                    chat_id = str(update["message"]["chat"]["id"])
                elif "callback_query" in update:
                    chat_id = str(update["callback_query"]["message"]["chat"]["id"])
                if chat_id:
                    chat_ids.add(chat_id)
        print(f"📊 Found {len(chat_ids)} unique chat IDs")
    except Exception as e:
        print(f"Error getting chat IDs: {e}")
    
    return chat_ids


def broadcast_to_all(message, photo_url=None, video_url=None):
    """Send a message to ALL users who ever interacted with the bot"""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Bot token not set")
        return 0
    
    # Get all users
    chat_ids = get_all_chat_ids()
    
    if len(chat_ids) == 0:
        print("⚠️ No users found to broadcast to")
        return 0
    
    print(f"📣 Starting broadcast to {len(chat_ids)} users...")
    
    # Create the "Open GEM CART" button
    keyboard = {
        "inline_keyboard": [
            [{"text": "💎 Open GEM CART", "web_app": {"url": WEB_APP_URL}}]
        ]
    }
    
    sent_count = 0
    
    for chat_id in chat_ids:
        try:
            if video_url:
                # Send video broadcast
                data = {
                    "chat_id": chat_id,
                    "video": video_url,
                    "caption": message or "",
                    "reply_markup": json.dumps(keyboard)
                }
                result = telegram_request("sendVideo", data)
            elif photo_url:
                # Send photo broadcast
                data = {
                    "chat_id": chat_id,
                    "photo": photo_url,
                    "caption": message or "",
                    "reply_markup": json.dumps(keyboard)
                }
                result = telegram_request("sendPhoto", data)
            else:
                # Send text broadcast
                result = send_message(chat_id, message, keyboard)
            
            if result and result.get("ok"):
                sent_count += 1
            else:
                error_desc = result.get("description", "Unknown error") if result else "No response"
                print(f"❌ Failed for {chat_id}: {error_desc}")
            
            # Wait between sends to avoid rate limiting
            time_module.sleep(0.4)
            
        except Exception as e:
            print(f"❌ Error sending to {chat_id}: {e}")
    
    print(f"✅ Broadcast complete: {sent_count}/{len(chat_ids)} users received it")
    
    # Save broadcast to database for Mini App display
    try:
        conn = get_db()
        conn.execute(
            'INSERT INTO broadcasts (time, message, photo) VALUES (?, ?, ?)',
            [datetime.now().isoformat(), message, photo_url or video_url or '']
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving broadcast: {e}")
    
    return sent_count


def get_db():
    """Get database connection"""
    conn = sqlite3.connect('gemcart.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database with tables and default data"""
    conn = get_db()
    
    # Create tables
    conn.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
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
        customer_id TEXT,
        items TEXT,
        total INTEGER,
        status TEXT DEFAULT "pending"
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT,
        message TEXT,
        photo TEXT
    )''')
    
    # Add default products if empty
    count = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    if count == 0:
        conn.execute(
            "INSERT INTO products (name,category,gender,price,description,size,photos,stock,discount,featured,visible,sold) "
            "VALUES ('Emerald Backpack','Bags','Male',2200,'Handcrafted water-resistant backpack with laptop sleeve.','Large',"
            "'https://placehold.co/400x400/0B2E1E/D4AF37?text=Backpack',5,0,1,1,0)"
        )
        conn.execute(
            "INSERT INTO products (name,category,gender,price,description,size,photos,stock,discount,featured,visible,sold) "
            "VALUES ('Golden Tote','Bags','Female',1200,'Premium canvas tote with gold-plated hardware.','Medium',"
            "'https://placehold.co/400x400/1A533E/F3D673?text=Tote',3,0,0,1,0)"
        )
        conn.execute(
            "INSERT INTO products (name,category,gender,price,description,size,photos,stock,discount,featured,visible,sold) "
            "VALUES ('Diamond Stickers','Stickers','Unisex',350,'50pcs holographic premium stickers.',null,"
            "'https://placehold.co/400x400/0B2E1E/D4AF37?text=Stickers',20,10,1,1,0)"
        )
        conn.execute(
            "INSERT INTO products (name,category,gender,price,description,size,photos,stock,discount,featured,visible,sold) "
            "VALUES ('Crystal Bracelet','Jewelry','Female',450,'Natural crystal beads with gold-plated clasp.','One Size',"
            "'https://placehold.co/400x400/1A533E/F3D673?text=Bracelet',0,0,0,1,1)"
        )
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")


# Initialize database on startup
init_db()


# ============ API ROUTES ============

@app.route('/')
def home():
    return jsonify({"status": "GEM CART API", "version": "2.0"})


@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_db()
    rows = conn.execute('SELECT * FROM products WHERE visible = 1').fetchall()
    conn.close()
    
    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "gender": row["gender"],
            "price": row["price"],
            "description": row["description"],
            "size": row["size"],
            "photos": row["photos"].split(",") if row["photos"] else [],
            "stock": row["stock"],
            "discount": row["discount"],
            "featured": bool(row["featured"]),
            "visible": bool(row["visible"]),
            "sold": bool(row["sold"])
        })
    
    return jsonify(result)


@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    conn = get_db()
    
    conn.execute(
        'INSERT INTO products (name, category, gender, price, description, size, photos, stock, discount, featured, visible, sold) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        [
            data.get('name'),
            data.get('category'),
            data.get('gender'),
            data.get('price'),
            data.get('description'),
            data.get('size'),
            ','.join(data.get('photos', [])),
            data.get('stock', 1),
            data.get('discount', 0),
            1 if data.get('featured') else 0,
            1 if data.get('visible') != False else 0,
            1 if data.get('sold') else 0
        ]
    )
    
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/products/<int:id>', methods=['PUT'])
def update_product(id):
    data = request.json
    conn = get_db()
    
    conn.execute(
        'UPDATE products SET name=?, category=?, gender=?, price=?, description=?, size=?, photos=?, stock=?, discount=?, featured=?, visible=?, sold=? WHERE id=?',
        [
            data.get('name'),
            data.get('category'),
            data.get('gender'),
            data.get('price'),
            data.get('description'),
            data.get('size'),
            ','.join(data.get('photos', [])),
            data.get('stock', 1),
            data.get('discount', 0),
            1 if data.get('featured') else 0,
            1 if data.get('visible') != False else 0,
            1 if data.get('sold') else 0,
            id
        ]
    )
    
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    conn = get_db()
    conn.execute('DELETE FROM products WHERE id = ?', [id])
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/orders', methods=['GET'])
def get_orders():
    conn = get_db()
    rows = conn.execute('SELECT * FROM orders ORDER BY date DESC').fetchall()
    conn.close()
    
    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "date": row["date"],
            "customerName": row["customer_name"],
            "customerUsername": row["customer_username"],
            "items": eval(row["items"]) if row["items"] else [],
            "total": row["total"],
            "status": row["status"]
        })
    
    return jsonify(result)


@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    order_id = "GEM-" + datetime.now().strftime("%Y%m%d%H%M%S")
    conn = get_db()
    
    # Process each item - decrease stock
    items = data.get('items', [])
    for item in items:
        item_name = item.get('name', '')
        item_qty = item.get('qty', 1)
        
        # Get current stock
        current = conn.execute('SELECT stock FROM products WHERE name = ?', [item_name]).fetchone()
        if current:
            new_stock = max(0, current['stock'] - item_qty)
            sold_flag = 1 if new_stock <= 0 else 0
            conn.execute(
                'UPDATE products SET stock = ?, sold = ? WHERE name = ?',
                [new_stock, sold_flag, item_name]
            )
    
    # Save the order
    conn.execute(
        'INSERT INTO orders (id, date, customer_name, customer_username, customer_id, items, total, status) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [
            order_id,
            datetime.now().isoformat(),
            data.get('customerName', ''),
            data.get('customerUsername', ''),
            str(data.get('customerId', '')),
            str(items),
            data.get('total', 0),
            'pending'
        ]
    )
    
    conn.commit()
    conn.close()
    
    # Send notification to admin
    customer_name = data.get('customerName', 'Unknown')
    customer_username = data.get('customerUsername', '@unknown')
    order_total = data.get('total', 0)
    
    items_text = ""
    for item in items:
        items_text += f"• {item.get('name', '?')} × {item.get('qty', 1)}\n"
    
    notification = (
        f"💎 <b>NEW ORDER!</b>\n\n"
        f"🆔 {order_id}\n"
        f"👤 {customer_name}\n"
        f"📧 {customer_username}\n"
        f"💰 {order_total:,} Birr\n\n"
        f"📋 <b>Items:</b>\n{items_text}\n"
        f"💳 Telebirr: {TELEBIRR_NUMBER} ({TELEBIRR_NAME})"
    )
    
    # Send in background thread
    threading.Thread(target=send_message, args=(ADMIN_CHAT_ID, notification)).start()
    
    return jsonify({"success": True, "orderId": order_id})


@app.route('/api/orders/<string:id>', methods=['PUT'])
def update_order(id):
    data = request.json
    conn = get_db()
    conn.execute('UPDATE orders SET status = ? WHERE id = ?', [data.get('status'), id])
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/broadcasts', methods=['GET'])
def get_broadcasts():
    conn = get_db()
    rows = conn.execute('SELECT * FROM broadcasts ORDER BY time DESC').fetchall()
    conn.close()
    
    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "time": row["time"],
            "message": row["message"],
            "photo": row["photo"]
        })
    
    return jsonify(result)


@app.route('/api/broadcasts', methods=['POST'])
def add_broadcast():
    data = request.json
    message = data.get('message', '')
    photo = data.get('photo', '')
    
    # Save to database
    conn = get_db()
    conn.execute(
        'INSERT INTO broadcasts (time, message, photo) VALUES (?, ?, ?)',
        [datetime.now().isoformat(), message, photo]
    )
    conn.commit()
    conn.close()
    
    # Also send to all Telegram users
    sent_count = 0
    if message or photo:
        sent_count = broadcast_to_all(message, photo_url=photo if photo else None)
    
    return jsonify({"success": True, "sent": sent_count})


@app.route('/health')
def health():
    return jsonify({"status": "healthy"})


# ============ TELEGRAM BOT ============

def run_bot():
    """Main bot loop - polls for updates and handles commands"""
    global last_update_id
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Bot token not set. Bot will not start.")
        return
    
    print("🤖 Bot started! Polling for messages...")
    
    while True:
        try:
            # Get updates from Telegram
            result = telegram_request(
                "getUpdates",
                {"offset": last_update_id + 1, "timeout": 30}
            )
            
            if result and result.get("ok") and result.get("result"):
                for update in result["result"]:
                    update_id = update.get("update_id", 0)
                    
                    # Skip already processed updates
                    if update_id <= last_update_id:
                        continue
                    
                    last_update_id = update_id
                    
                    # Handle regular messages
                    if "message" in update:
                        message = update["message"]
                        chat_id = str(message["chat"]["id"])
                        text = message.get("text", "")
                        first_name = message.get("from", {}).get("first_name", "Customer")
                        
                        # Check if this is the admin
                        is_admin = (chat_id == str(ADMIN_CHAT_ID))
                        
                        # ============ COMMANDS ============
                        
                        if text == "/start":
                            # Welcome message with Open GEM CART button
                            keyboard = {
                                "inline_keyboard": [[
                                    {"text": "💎 Open GEM CART", "web_app": {"url": WEB_APP_URL}}
                                ]]
                            }
                            send_message(
                                chat_id,
                                f"✨ <b>Welcome to GEM CART, {first_name}!</b>\n\n"
                                f"💎 Discover our luxury collection of premium accessories.\n\n"
                                f"🛍️ Tap the button below to start shopping:",
                                keyboard
                            )
                        
                        elif text == "/broadcast" and is_admin:
                            # Start text broadcast
                            pending_broadcasts[chat_id] = {"type": "text"}
                            send_message(chat_id, "📣 <b>Send Broadcast</b>\n\nType your message now. It will be sent to ALL users with an 'Open GEM CART' button.")
                        
                        elif text == "/broadcast_photo" and is_admin:
                            # Start photo broadcast
                            pending_broadcasts[chat_id] = {"type": "photo", "caption": ""}
                            send_message(chat_id, "📷 <b>Send Photo Broadcast</b>\n\n1️⃣ First, type your caption text.\n2️⃣ Then send the photo.")
                        
                        elif text == "/broadcast_video" and is_admin:
                            # Start video broadcast
                            pending_broadcasts[chat_id] = {"type": "video", "caption": ""}
                            send_message(chat_id, "🎬 <b>Send Video Broadcast</b>\n\n1️⃣ First, type your caption text.\n2️⃣ Then send the video.")
                        
                        elif text == "/admin" and is_admin:
                            # Admin help menu
                            send_message(
                                chat_id,
                                f"🔐 <b>Admin Commands:</b>\n\n"
                                f"/broadcast - Send text message to all users\n"
                                f"/broadcast_photo - Send photo + caption to all users\n"
                                f"/broadcast_video - Send video + caption to all users\n\n"
                                f"📱 Mini App Admin Password: <code>{ADMIN_PASSWORD}</code>"
                            )
                        
                        elif text == "/help":
                            # Help message
                            keyboard = {
                                "inline_keyboard": [[
                                    {"text": "💎 Open GEM CART", "web_app": {"url": WEB_APP_URL}}
                                ]]
                            }
                            send_message(
                                chat_id,
                                f"💎 <b>GEM CART Help</b>\n\n"
                                f"/start - Open the shop\n"
                                f"/help - This message\n\n"
                                f"📱 Payment via Telebirr:\n"
                                f"📞 {TELEBIRR_NUMBER} ({TELEBIRR_NAME})",
                                keyboard
                            )
                        
                        # ============ HANDLE PENDING BROADCASTS ============
                        elif chat_id in pending_broadcasts and is_admin:
                            pending = pending_broadcasts[chat_id]
                            
                            if pending["type"] in ["photo", "video"] and not pending.get("caption"):
                                # Save the caption, wait for photo/video
                                pending["caption"] = text
                                send_message(chat_id, f"✅ Caption saved!\n\nNow send the {'photo' if pending['type'] == 'photo' else 'video'}.")
                            else:
                                # Send text broadcast
                                count = broadcast_to_all(text)
                                del pending_broadcasts[chat_id]
                                send_message(chat_id, f"✅ Broadcast sent to {count} users!")
                        
                        # ============ HANDLE PHOTO UPLOAD FOR BROADCAST ============
                        elif "photo" in message and chat_id in pending_broadcasts and is_admin:
                            pending = pending_broadcasts[chat_id]
                            if pending["type"] == "photo":
                                # Get the largest photo
                                photos = message["photo"]
                                file_id = photos[-1]["file_id"]
                                
                                try:
                                    # Get file path from Telegram
                                    file_response = requests.get(
                                        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
                                    ).json()
                                    file_path = file_response.get("result", {}).get("file_path", "")
                                    photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                                    
                                    # Broadcast the photo
                                    count = broadcast_to_all(pending.get("caption", ""), photo_url=photo_url)
                                    del pending_broadcasts[chat_id]
                                    send_message(chat_id, f"✅ Photo broadcast sent to {count} users!")
                                except Exception as e:
                                    print(f"Photo broadcast error: {e}")
                                    del pending_broadcasts[chat_id]
                                    send_message(chat_id, "❌ Failed to send photo broadcast.")
                        
                        # ============ HANDLE VIDEO UPLOAD FOR BROADCAST ============
                        elif "video" in message and chat_id in pending_broadcasts and is_admin:
                            pending = pending_broadcasts[chat_id]
                            if pending["type"] == "video":
                                file_id = message["video"]["file_id"]
                                
                                try:
                                    # Get file path from Telegram
                                    file_response = requests.get(
                                        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
                                    ).json()
                                    file_path = file_response.get("result", {}).get("file_path", "")
                                    video_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                                    
                                    # Broadcast the video
                                    count = broadcast_to_all(pending.get("caption", ""), video_url=video_url)
                                    del pending_broadcasts[chat_id]
                                    send_message(chat_id, f"✅ Video broadcast sent to {count} users!")
                                except Exception as e:
                                    print(f"Video broadcast error: {e}")
                                    del pending_broadcasts[chat_id]
                                    send_message(chat_id, "❌ Failed to send video broadcast.")
        
        except Exception as e:
            print(f"Bot loop error: {e}")
        
        # Wait before next poll
        time_module.sleep(1)


# Start the bot in a background thread
if BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("🤖 Bot thread started!")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
