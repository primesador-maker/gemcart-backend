import os, json, uuid, threading, asyncio, sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from werkzeug.utils import secure_filename
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB

ADMIN_ID = 7715442708  # Only you get order notifications
PASSWORD = 'sadmin'

# Get token from environment - CRASH if missing
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN environment variable not set!")
    raise ValueError("BOT_TOKEN environment variable is required!")

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
                chat_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                category TEXT,
                gender TEXT DEFAULT 'Unisex',
                images TEXT DEFAULT '[]',
                video TEXT,
                stock INTEGER DEFAULT 1,
                is_sold INTEGER DEFAULT 0,
                is_hidden INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                customer_name TEXT,
                customer_username TEXT,
                items TEXT,
                total_amount REAL,
                payment_method TEXT DEFAULT 'Telebirr',
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS admin_tokens (
                token TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        db.commit()

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# ==================== AUTH ====================
def admin_required(f):
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization')
        if not auth or not auth.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        token = auth.split(' ')[1]
        db = get_db()
        row = db.execute('SELECT token FROM admin_tokens WHERE token=?', (token,)).fetchone()
        if not row:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ==================== ROUTES ====================
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
    except sqlite3.IntegrityError:
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
    files = request.files.getlist('files')
    for file in files[:5]:
        filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
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
    db = get_db()
    data = request.get_json()
    product = db.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    if not product:
        return jsonify({'error':'Not found'}), 404
    if 'stock_increment' in data:
        new_stock = product['stock'] + data['stock_increment']
        db.execute('UPDATE products SET stock=? WHERE id=?', (new_stock, pid))
    if 'is_sold' in data:
        db.execute('UPDATE products SET is_sold=? WHERE id=?', (int(data['is_sold']), pid))
    if 'is_hidden' in data:
        db.execute('UPDATE products SET is_hidden=? WHERE id=?', (int(data['is_hidden']), pid))
    db.commit()
    # auto-mark sold if stock zero
    updated = db.execute('SELECT stock, is_sold FROM products WHERE id=?', (pid,)).fetchone()
    if updated['stock'] <= 0 and not updated['is_sold']:
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
    customer_id = data.get('customer_id')
    if not customer_id:
        return jsonify({'error': 'customer_id required'}), 400
    db = get_db()
    items = data.get('items', [])
    order_items = []
    total = 0.0
    for item in items:
        pid = item['product_id']
        qty = item['quantity']
        product = db.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
        if not product or product['stock'] < qty or product['is_sold']:
            return jsonify({'error': f'Product {pid} not available'}), 400
        db.execute('UPDATE products SET stock=stock-? WHERE id=?', (qty, pid))
        order_items.append({
            'product_id': pid, 'name': product['name'], 'price': product['price'], 'quantity': qty
        })
        total += product['price'] * qty
        # check sold
        new_stock = product['stock'] - qty
        if new_stock <= 0:
            db.execute('UPDATE products SET is_sold=1 WHERE id=?', (pid,))
    db.execute('INSERT INTO orders (customer_id,customer_name,customer_username,items,total_amount,payment_method) VALUES (?,?,?,?,?,?)',
               (customer_id, data.get('customer_name',''), data.get('customer_username',''),
                json.dumps(order_items), total, data.get('payment_method','Telebirr')))
    db.commit()
    order_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    # Notify ONLY admin
    threading.Thread(target=notify_admin_order, args=(order_id,)).start()
    return jsonify({'order_id': order_id})

@app.route('/api/orders', methods=['GET'])
def get_orders():
    customer_id = request.args.get('customer_id')
    all_orders = request.args.get('all')
    db = get_db()
    if all_orders:
        # admin check token
        auth = request.headers.get('Authorization')
        if not auth or not auth.startswith('Bearer '):
            return jsonify({'error':'Unauthorized'}), 401
        token = auth.split(' ')[1]
        if not db.execute('SELECT token FROM admin_tokens WHERE token=?', (token,)).fetchone():
            return jsonify({'error':'Unauthorized'}), 401
        rows = db.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    elif customer_id:
        rows = db.execute('SELECT * FROM orders WHERE customer_id=? ORDER BY created_at DESC', (customer_id,)).fetchall()
    else:
        return jsonify([])
    orders = []
    for r in rows:
        orders.append({
            'id': r['id'], 'customer_id': r['customer_id'], 'customer_name': r['customer_name'],
            'customer_username': r['customer_username'], 'items': json.loads(r['items']),
            'total': r['total_amount'], 'status': r['status'], 'created_at': r['created_at']
        })
    return jsonify(orders)

@app.route('/api/orders/<int:oid>/status', methods=['PUT'])
@admin_required
def update_order_status(oid):
    data = request.get_json()
    db = get_db()
    db.execute('UPDATE orders SET status=? WHERE id=?', (data['status'], oid))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    if data.get('password') == PASSWORD:
        token = str(uuid.uuid4())
        db = get_db()
        db.execute('INSERT INTO admin_tokens (token) VALUES (?)', (token,))
        db.commit()
        return jsonify({'token': token})
    return jsonify({'error': 'Wrong password'}), 403

@app.route('/api/broadcast', methods=['POST'])
@admin_required
def broadcast():
    message = request.form.get('message', '')
    photo = request.files.get('photo')
    threading.Thread(target=send_broadcast, args=(message, photo)).start()
    return jsonify({'success': True})

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# ==================== BOT ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Save user to database for broadcasts
    db = sqlite3.connect('gemcart.db')
    db.execute(
        'INSERT OR REPLACE INTO users (telegram_id, first_name, last_name, username, chat_id) VALUES (?,?,?,?,?)',
        (user.id, user.first_name, user.last_name, user.username, chat_id)
    )
    db.commit()
    db.close()
    
    # Personalized welcome
    first_name = user.first_name or "Valued Customer"
    
    welcome_text = f"""✨ *Welcome, {first_name}!* ✨

🛒 Step into the world of *GEM CART* – where luxury meets elegance.

💎 Discover handpicked jewelry & accessories
🌟 Exclusive designs for every style
🚚 Fast & secure ordering with Telebirr

_Your personal shopping experience awaits._"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "💎 Open GEM CART 💎", 
            web_app=WebAppInfo(url="https://primesador-maker.github.io/gemcart")
        )]
    ])
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use /start to open the app. Admins can broadcast with /broadcast, /broadcast_photo, /broadcast_video.")

async def handle_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        logger.warning(f"Unauthorized broadcast attempt from user {update.effective_user.id}")
        return
    text = update.message.text.split(' ', 1)
    if len(text) < 2:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    await broadcast_to_all(text[1], photo=None, video=None)

async def handle_broadcast_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        logger.warning(f"Unauthorized broadcast_photo attempt from user {update.effective_user.id}")
        return
    photo = update.message.photo[-1].file_id
    caption = update.message.caption or ''
    if caption.startswith('/broadcast_photo'):
        msg_text = caption.replace('/broadcast_photo', '').strip()
    else:
        msg_text = caption
    await broadcast_to_all(msg_text, photo=photo, video=None)

async def handle_broadcast_video(update: Update, context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        logger.warning(f"Unauthorized broadcast_video attempt from user {update.effective_user.id}")
        return
    video = update.message.video.file_id
    caption = update.message.caption or ''
    if caption.startswith('/broadcast_video'):
        msg_text = caption.replace('/broadcast_video', '').strip()
    else:
        msg_text = caption
    await broadcast_to_all(msg_text, photo=None, video=video)

async def broadcast_to_all(text, photo=None, video=None):
    db = sqlite3.connect('gemcart.db')
    users = db.execute('SELECT chat_id FROM users').fetchall()
    db.close()
    
    bot_app = Application.builder().token(BOT_TOKEN).build().bot
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Open GEM CART", web_app=WebAppInfo(url="https://primesador-maker.github.io/gemcart"))]
    ])
    
    success_count = 0
    fail_count = 0
    
    for (chat_id,) in users:
        try:
            if photo:
                await bot_app.send_photo(chat_id, photo, caption=text, reply_markup=keyboard)
            elif video:
                await bot_app.send_video(chat_id, video, caption=text, reply_markup=keyboard)
            else:
                await bot_app.send_message(chat_id, text, reply_markup=keyboard)
            success_count += 1
        except Exception as e:
            logger.error(f"Broadcast to {chat_id} failed: {e}")
            fail_count += 1
    
    logger.info(f"Broadcast complete: {success_count} sent, {fail_count} failed")

def send_broadcast(message, photo_file=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(broadcast_to_all(message))
    except Exception as e:
        logger.error(f"Send broadcast error: {e}")
    finally:
        loop.close()

def notify_admin_order(order_id):
    """Notify ONLY the admin (you) when a new order is placed"""
    try:
        db = sqlite3.connect('gemcart.db')
        order = db.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
        admin_user = db.execute('SELECT chat_id FROM users WHERE telegram_id=?', (ADMIN_ID,)).fetchone()
        db.close()
        
        if not order:
            logger.error(f"Order {order_id} not found for notification")
            return
            
        if not admin_user:
            logger.warning(f"Admin {ADMIN_ID} not found in users table. Have you sent /start to the bot?")
            return
            
        chat_id = admin_user[0]
        items = json.loads(order['items'])
        
        text = f"""🛒 *New Order #{order['id']}*

👤 *Customer:* {order['customer_name']}
📱 *Username:* @{order['customer_username']}

📦 *Items:*
"""
        for i in items:
            text += f"  • {i['name']} x{i['quantity']} = ETB {i['price']*i['quantity']}\n"
        
        text += f"""
💰 *Total:* ETB {order['total_amount']}
📌 *Status:* {order['status']}
💳 *Payment:* {order['payment_method']}
🕐 *Date:* {order['created_at']}
"""
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot_app = Application.builder().token(BOT_TOKEN).build()
        loop.run_until_complete(
            bot_app.bot.send_message(chat_id, text, parse_mode='Markdown')
        )
        loop.close()
        logger.info(f"Order notification sent to admin for order #{order_id}")
        
    except Exception as e:
        logger.error(f"Failed to notify admin about order #{order_id}: {e}")

def run_bot():
    """Run the Telegram bot with error handling"""
    try:
        logger.info("Starting Telegram bot...")
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_cmd))
        application.add_handler(CommandHandler("broadcast", handle_broadcast_text))
        application.add_handler(MessageHandler(filters.PHOTO & filters.CaptionRegex(r'^/broadcast_photo'), handle_broadcast_photo))
        application.add_handler(MessageHandler(filters.VIDEO & filters.CaptionRegex(r'^/broadcast_video'), handle_broadcast_video))
        
        logger.info("✅ Bot polling started successfully!")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")

# ==================== STARTUP ====================
logger.info("Initializing database...")
init_db()

logger.info("Starting bot in background thread...")
threading.Thread(target=run_bot, daemon=True).start()

if __name__ == '__main__':
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
