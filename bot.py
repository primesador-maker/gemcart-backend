import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import os

# ============ CONFIGURATION ============
TOKEN = os.getenv("BOT_TOKEN")  # Set this on Render
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "sadmin")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://primesador-maker.github.io/gemcart/")

# ============ BOT SETUP ============
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ============ COMMANDS ============
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Open GEM CART", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    await message.answer(
        f"✦ *Welcome to GEM CART* ✦\n\n"
        f"👤 Hello, {message.from_user.first_name}!\n\n"
        f"Tap the button below to browse our luxury collection.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    await message.answer(
        "🔐 Admin Panel\n\n"
        "Open the Mini App and click ⚙️ to access the admin panel.\n"
        f"Password: `{ADMIN_PASSWORD}`",
        parse_mode="Markdown"
    )

@dp.message(Command("help"))
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
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
