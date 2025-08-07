import os
import requests
import psycopg2
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import sys
print(f"🔧 Python version: {sys.version}")

# Загружаем переменные окружения
load_dotenv()

DB_USER = os.getenv("user")
DB_PASSWORD = os.getenv("password")
DB_HOST = os.getenv("host")
DB_PORT = os.getenv("port")
DB_NAME = os.getenv("dbname")
BOT_TOKEN = os.getenv("BOT_TOKEN")


def save_user_info(user, chat_id):
    try:
        connection = psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME
        )
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT,
                is_premium BOOLEAN,
                chat_id BIGINT
            );
        """)
        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, language_code, is_premium, chat_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING;
        """, (
            user.id,
            user.username,
            user.first_name,
            user.last_name,
            user.language_code,
            getattr(user, 'is_premium', False),
            chat_id
        ))
        connection.commit()
        cursor.close()
        connection.close()
        print("✅ Пользователь сохранён в базе.")
    except Exception as e:
        print(f"❌ Ошибка сохранения пользователя: {e}")

def save_location(user_id, latitude, longitude, address):
    try:
        connection = psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME
        )
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                address TEXT
            );
        """)
        cursor.execute("""
            INSERT INTO locations (user_id, latitude, longitude, address)
            VALUES (%s, %s, %s, %s);
        """, (user_id, latitude, longitude, address))
        connection.commit()
        cursor.close()
        connection.close()
        print("📍 Геолокация сохранена.")
    except Exception as e:
        print(f"❌ Ошибка сохранения геолокации: {e}")

def save_echo(user_id, text):
    try:
        connection = psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME
        )
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                message TEXT
            );
        """)
        cursor.execute("""
            INSERT INTO messages (user_id, message)
            VALUES (%s, %s);
        """, (user_id, text))
        connection.commit()
        cursor.close()
        connection.close()
        print("💬 Сообщение сохранено.")
    except Exception as e:
        print(f"❌ Ошибка сохранения сообщения: {e}")

# Получение адреса по координатам
def get_address_from_coords(lat, lon):
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "format": "json",
            "lat": lat,
            "lon": lon,
            "zoom": 18,
            "addressdetails": 1
        }
        headers = {
            "User-Agent": "telegram-bot-demo"
        }
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get("display_name", "Адрес не найден")
        else:
            return "Ошибка геокодирования"
    except Exception as e:
        return f"Ошибка: {e}"

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    save_user_info(user, chat.id)

    photos = await context.bot.get_user_profile_photos(user.id, limit=1)
    photo_id = photos.photos[0][0].file_id if photos.total_count > 0 else None

    location_button = KeyboardButton("📍 Отправить геолокацию", request_location=True)
    location_keyboard = ReplyKeyboardMarkup([[location_button]], resize_keyboard=True, one_time_keyboard=True)

    text = (
        f"👤 <b>Информация о вас:</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📛 Имя: {user.first_name or '-'}\n"
        f"👪 Фамилия: {user.last_name or '-'}\n"
        f"🔗 Username: @{user.username or '-'}\n"
        f"🌐 Язык: {user.language_code or '-'}\n"
        f"💎 Premium: {'Да' if getattr(user, 'is_premium', False) else 'Нет'}\n"
        f"💬 Chat ID: {chat.id}\n\n"
        f"📍 Пожалуйста, отправьте свою геолокацию 👇"
    )

    if photo_id:
        await update.message.reply_photo(
            photo=photo_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=location_keyboard
        )
    else:
        await update.message.reply_text(
            text=text,
            parse_mode="HTML",
            reply_markup=location_keyboard
        )

# Обработка геолокации
async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    user = update.effective_user

    latitude = location.latitude
    longitude = location.longitude

    address = get_address_from_coords(latitude, longitude)

    save_location(user.id, latitude, longitude, address)

    await update.message.reply_text(
        f"📍 Спасибо, {user.first_name}!\n"
        f"<b>Ваша геолокация:</b>\n"
        f"🧭 Широта: <code>{latitude}</code>\n"
        f"🧭 Долгота: <code>{longitude}</code>\n"
        f"🏠 Адрес: <i>{address}</i>",
        parse_mode="HTML"
    )

# Обработка текста
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message.text
    save_echo(user.id, message)
    await update.message.reply_text(f"Вы сказали: {message}")

# Запуск
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("✅ Бот запущен...")
    app.run_polling()
