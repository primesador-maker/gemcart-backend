import sqlite3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8924432232:AAEl9AvRZ9o6tII-YYW5waQoIcvg3wH4qXI"
ADMIN_ID = 7715442708

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    db = sqlite3.connect('gemcart.db')
    db.execute('INSERT OR REPLACE INTO users (telegram_id, first_name, last_name, username, chat_id) VALUES (?,?,?,?,?)',
               (user.id, user.first_name or '', user.last_name or '', user.username or '', chat_id))
    db.commit()
    db.close()
    
    first_name = user.first_name or "Valued Customer"
    
    await update.message.reply_text(
        f"✨ *Welcome, {first_name}!* ✨\n\n"
        f"🛒 Step into the world of *GEM CART* – where luxury meets elegance.\n\n"
        f"💎 Discover handpicked jewelry & accessories\n"
        f"🌟 Exclusive designs for every style\n"
        f"🚚 Fast & secure ordering with Telebirr\n\n"
        f"_Your personal shopping experience awaits._",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Open GEM CART 💎", web_app=WebAppInfo(url="https://primesador-maker.github.io/gemcart"))]
        ])
    )
    logger.info(f"User {user.id} ({first_name}) started bot")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use /start to open GEM CART. Admin: /broadcast <message>")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return
    text = update.message.text.split(' ', 1)
    if len(text) < 2:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    db = sqlite3.connect('gemcart.db')
    users = db.execute('SELECT chat_id FROM users').fetchall()
    db.close()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Open GEM CART", web_app=WebAppInfo(url="https://primesador-maker.github.io/gemcart"))]
    ])
    
    count = 0
    for (chat_id,) in users:
        try:
            await context.bot.send_message(chat_id, text[1], reply_markup=keyboard)
            count += 1
        except:
            pass
    
    await update.message.reply_text(f"✅ Broadcast sent to {count} users")

def main():
    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("help", help_cmd))
    app_bot.add_handler(CommandHandler("broadcast", broadcast))
    
    logger.info("🤖 Bot started! Send /start to @GemCart_bot")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
