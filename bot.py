import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# ============ CONFIGURATION ============
# !! IMPORTANT: Paste your new bot token from BotFather here !!
TOKEN = "8924432232:AAFLyaI-3CozY3oxfBeGVZ9hu-bhsuGWlVY" 

ADMIN_PASSWORD = "sadmin"
WEB_APP_URL = "https://primesador-maker.github.io/gemcart/"

# ============ BOT SETUP ============
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# ============ COMMANDS ============
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text="💎 Open GEM CART", web_app=WebAppInfo(url=WEB_APP_URL)))
    await message.answer(
        f"✦ *Welcome to GEM CART* ✦\n\n"
        f"👤 Hello, {message.from_user.first_name}!\n\n"
        f"Tap the button below to browse our luxury collection.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message_handler(commands=["admin"])
async def cmd_admin(message: types.Message):
    await message.answer(
        "🔐 Admin Panel\n\n"
        "Open the Mini App and click ⚙️ to access the admin panel.\n"
        f"Password: `{ADMIN_PASSWORD}`",
        parse_mode="Markdown"
    )

@dp.message_handler(commands=["help"])
async def cmd_help(message: types.Message):
    await message.answer(
        "💎 *GEM CART — Help*\n\n"
        "/start — Open the shop\n"
        "/admin — Admin info\n"
        "/help — This message\n\n"
        "✦ For orders, we will DM you for Telebirr payment.",
        parse_mode="Markdown"
    )

# ============ START BOT ============
if __name__ == "__main__":
    print("GEM CART Bot is starting...")
    executor.start_polling(dp, skip_updates=True)
