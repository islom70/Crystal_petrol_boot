# full bot.py
import logging
import os
import asyncio
import re
import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv

from db import init_db, save_user, save_rating  # <-- DB functions
from db import get_average_rating
from export_to_exel import export_all_tables


# Загрузка .env
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_ENV = os.getenv("ADMIN_ID")

if not API_TOKEN or not ADMIN_ID_ENV:
    raise ValueError("❌ BOT_TOKEN и/или ADMIN_ID не указаны в .env файле!")

try:
    ADMIN_ID = int(ADMIN_ID_ENV)
except ValueError:
    raise ValueError("❌ ADMIN_ID должен быть числом!")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния
class Form(StatesGroup):
    language = State()
    name = State()
    phone = State()
    region = State()
    support = State()
    user_list_page = State()

languages = {
    "🇺🇿 O‘zbekcha": "uz",
    "🇷🇺 Русский": "ru",
    "🇬🇧 English": "en"
}

back_button = KeyboardButton(text="🔙 Orqaga")

rating_buttons = [
    [KeyboardButton(text="⭐️")],
    [KeyboardButton(text="⭐️⭐️")],
    [KeyboardButton(text="⭐️⭐️⭐️")],
    [KeyboardButton(text="⭐️⭐️⭐️⭐️")],
    [KeyboardButton(text="⭐️⭐️⭐️⭐️⭐️")]
]
rating_markup = ReplyKeyboardMarkup(keyboard=rating_buttons, resize_keyboard=True)

# Главное меню
async def show_main_menu(message: Message):
    buttons = [
        [KeyboardButton(text="📝 Ro'yxatdan o'tish"), KeyboardButton(text="⭐️ Crystal Petrol servisini baholash")],
        [KeyboardButton(text="📞 Crystal Petrol bilan aloqa"), KeyboardButton(text="⛽ Benzin buyurtma qilish")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("🔙 Bosh menyuga qaytdingiz. Quyidagi menyudan tanlang:", reply_markup=markup)

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await show_main_menu(message)
    await state.clear()


@dp.message(F.text == "📝 Ro'yxatdan o'tish")
async def handle_registration(message: Message, state: FSMContext):
    conn = await asyncpg.connect(os.getenv("PG_URL"))

    # Проверяем, зарегистрирован ли пользователь
    exists = await conn.fetchval(
        "SELECT 1 FROM users WHERE telegram_id = $1",
        message.from_user.id
    )

    await conn.close()

    if exists:
        await message.answer("✅ Siz allaqachon ro'yxatdan o'tgansiz.")
        return

    # Показываем выбор языка
    buttons = [[KeyboardButton(text=lang)] for lang in languages]
    buttons.append([back_button])
    markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("Tilni tanlang / Choose language / Выберите язык", reply_markup=markup)
    await state.set_state(Form.language)



@dp.message(Form.language)
async def choose_language(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await show_main_menu(message)
        await state.clear()
        return

    if message.text not in languages:
        await message.answer("❌ Noto‘g‘ri tanlov. Iltimos, tilni tanlang.")
        return

    lang_code = languages[message.text]
    await state.update_data(language=lang_code)
    await state.set_state(Form.name)

    prompts = {
        "uz": "Ismingizni kiriting:",
        "ru": "Введите ваше имя:",
        "en": "Please enter your name:"
    }

    markup = ReplyKeyboardMarkup(keyboard=[[back_button]], resize_keyboard=True)
    await message.answer(prompts[lang_code], reply_markup=markup)

@dp.message(Form.name)
async def enter_name(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.set_state(Form.language)
        buttons = [[KeyboardButton(text=lang)] for lang in languages]
        buttons.append([back_button])
        markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        await message.answer("Tilni tanlang / Choose language / Выберите язык", reply_markup=markup)
        return

    await state.update_data(name=message.text)
    await state.set_state(Form.phone)

    contact_button = KeyboardButton(text="📱 Kontaktni yuborish", request_contact=True)
    markup = ReplyKeyboardMarkup(keyboard=[[contact_button], [back_button]], resize_keyboard=True)
    await message.answer("Telefon raqamingizni yuboring yoki yozing:", reply_markup=markup)


@dp.message(Form.phone)
async def enter_phone(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.set_state(Form.name)
        await message.answer("Ismingizni kiriting:", reply_markup=ReplyKeyboardMarkup(keyboard=[[back_button]], resize_keyboard=True))
        return

    phone = message.contact.phone_number if message.contact else message.text.strip()
    normalized = re.sub(r"[^\d+]", "", phone)

    if normalized.startswith("998") and len(normalized) == 12:
        normalized = "+{}".format(normalized)
    elif normalized.startswith("9") and len(normalized) == 9:
        normalized = "+998{}".format(normalized)
    elif normalized.startswith("8") and len(normalized) == 9:
        normalized = "+998{}".format(normalized)
    elif normalized.startswith("+998") and len(normalized) == 13:
        pass
    else:
        await message.answer("❌ Telefon raqam noto‘g‘ri formatda. Masalan: +998901234567")
        return

    await state.update_data(phone=normalized)
    await state.set_state(Form.region)

    regions = [
        "Toshkent", "Toshkent viloyati", "Andijon", "Fargʻona",
        "Namangan", "Samarqand", "Buxoro", "Xorazm",
        "Qashqadaryo", "Surxondaryo", "Jizzax", "Navoiy"
    ]
    buttons = [[KeyboardButton(text=region)] for region in regions]
    buttons.append([back_button])
    markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("Qayerdansiz (viloyat/shahar):", reply_markup=markup)


@dp.message(Form.region)
async def enter_region(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.set_state(Form.phone)
        contact_button = KeyboardButton(text="📱 Kontaktni yuborish", request_contact=True)
        markup = ReplyKeyboardMarkup(keyboard=[[contact_button], [back_button]], resize_keyboard=True)
        await message.answer("Telefon raqamingizni yuboring yoki yozing:", reply_markup=markup)
        return

    await state.update_data(region=message.text)
    data = await state.get_data()

    text = (
        f"📥 Yangi foydalanuvchi ro‘yxatdan o‘tdi:\n\n"
        f"👤 Ism: {data['name']}\n"
        f"📞 Telefon: {data['phone']}\n"
        f"📍 Hudud: {data['region']}\n"
        f"🌐 Til: {data['language']}"
    )

    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
        await save_user(data, message.from_user.id, message.from_user.full_name)  # Save to DB
    except TelegramBadRequest as e:
        logging.error(f"❌ Не удалось отправить сообщение админу: {e}")

    # ✅ Показываем кнопку назад в меню
    markup = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 Orqaga")]], resize_keyboard=True)
    await message.answer(
        "✅ Ro‘yxatdan o‘tganingiz uchun rahmat!\n\n⬅️ Bosh menyuga qaytish uchun 'Orqaga' tugmasini bosing.",
        reply_markup=markup
    )
    await state.clear()


@dp.message(F.text == "⭐️ Crystal Petrol servisini baholash")
async def handle_service_rating(message: Message, state: FSMContext):
    conn = await asyncpg.connect(os.getenv("PG_URL"))

    # Проверка: зарегистрирован ли пользователь
    registered = await conn.fetchval("""
        SELECT 1 FROM users
        WHERE telegram_id = $1 AND name IS NOT NULL AND phone IS NOT NULL AND region IS NOT NULL
    """, message.from_user.id)

    # Проверка: оставлял ли он уже отзыв
    rated = await conn.fetchval("""
        SELECT 1 FROM ratings WHERE telegram_id = $1
    """, message.from_user.id)

    await conn.close()

    if not registered:
        await message.answer("❗️ Baholashdan oldin ro‘yxatdan o‘ting.")
        return

    if rated:
        await message.answer("✅ Siz allaqachon baholagansiz. Rahmat!")
        return

    await message.answer(
        "Iltimos, servisimizni qanday baholaysiz? (1–5 yulduz)",
        reply_markup=rating_markup
    )
    await state.set_state(Form.support)



@dp.message(Form.support, F.text.in_(
    ["⭐️", "⭐️⭐️", "⭐️⭐️⭐️", "⭐️⭐️⭐️⭐️", "⭐️⭐️⭐️⭐️⭐️"]
))
async def submit_service_rating(message: Message, state: FSMContext):
    rating_text = message.text
    stars_count = rating_text.count("⭐")

    if stars_count not in range(1, 6):
        await message.answer("❌ Baho noto‘g‘ri. Iltimos, 1 dan 5 gacha yulduz tanlang.")
        return

    try:
        await save_rating(message.from_user.id, message.from_user.full_name, stars_count)
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⭐️ Crystal Petrol servisiga baho: {stars_count} / 5\n👤 {message.from_user.full_name}"
        )
    except TelegramBadRequest as e:
        logging.error(f"❌ Bahoni yuborishda xatolik: {e}")

    markup = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 Orqaga")]], resize_keyboard=True)
    await message.answer("✅ Bahoyingiz uchun rahmat!", reply_markup=markup)
    await state.clear()


@dp.message(F.text == "🔙 Orqaga")
async def back_to_main(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    await show_main_menu(message)


@dp.message(F.text == "📞 Crystal Petrol bilan aloqa")
async def handle_contact(message: Message, state: FSMContext):
    markup = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 Orqaga")]], resize_keyboard=True)
    await message.answer("Biz bilan bog'lanish:\n📞 +998 97 555 25 00", reply_markup=markup)


@dp.message(F.text == "⛽ Benzin buyurtma qilish")
async def handle_order(message: Message, state: FSMContext):
    markup = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 Orqaga")]], resize_keyboard=True)
    await message.answer("Benzin buyurtma qilish xizmati tez orada ishga tushadi. Kuzatib boring!", reply_markup=markup)


@dp.message(Command("support"))
async def support_command(message: Message, state: FSMContext):
    await state.set_state(Form.support)
    await message.answer("Muammo yoki savolingizni yozing. Tez orada javob beramiz.")


@dp.message(Form.support)
async def support_message(message: Message, state: FSMContext):
    text = (
        f"📨 Texnik murojaat:\n\n"
        f"👤 {message.from_user.full_name}\n"
        f"🆔 @{message.from_user.username or 'N/A'}\n\n"
        f"💬 {message.text}"
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
    except TelegramBadRequest as e:
        logging.error(f"❌ Не удалось отправить сообщение админу: {e}")
    await message.answer("Xabaringiz yuborildi. Rahmat!")
    await state.clear()
    await show_main_menu(message)


@dp.message(Command("users"))
async def list_users_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda ruxsat yo'q.")
        return
    await state.set_state(Form.user_list_page)
    await state.update_data(page=0)
    await send_users_page(message, 0)


load_dotenv()
PG_URL = os.getenv("PG_URL")

async def send_users_page(message: Message, page: int):
    LIMIT = 5
    OFFSET = page * LIMIT

    conn = await asyncpg.connect(PG_URL)

    # Получить общее количество пользователей
    total_users = await conn.fetchval("SELECT COUNT(*) FROM users")

    # Получить LIMIT пользователей с OFFSET
    rows = await conn.fetch("""
        SELECT name, phone, region, language
        FROM users
        ORDER BY id DESC
        LIMIT $1 OFFSET $2
    """, LIMIT, OFFSET)

    await conn.close()

    if not rows:
        await message.answer("🛑 Foydalanuvchilar yo‘q.")
        return

    # Формирование текста
    text = f"📋 Foydalanuvchilar ({OFFSET + 1}–{OFFSET + len(rows)}):\n\n"
    for i, row in enumerate(rows, OFFSET + 1):
        text += f"{i}. 👤 {row['name']}\n📞 {row['phone']}\n📍 {row['region']} | 🌐 {row['language']}\n\n"

    # Кнопки пагинации
    pagination_row = []
    if page > 0:
        pagination_row.append(KeyboardButton(text="⬅️ Orqaga"))
    if OFFSET + LIMIT < total_users:
        pagination_row.append(KeyboardButton(text="➡️ Keyingi"))

    # Кнопка меню
    menu_row = [KeyboardButton(text="🏠 Bosh menyu")]

    # Итоговая клавиатура
    keyboard = []
    if pagination_row:
        keyboard.append(pagination_row)
    keyboard.append(menu_row)

    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    await message.answer(text.strip(), reply_markup=markup)



@dp.message(Form.user_list_page, F.text.in_(["⬅️ Orqaga", "➡️ Keyingi", "🏠 Bosh menyu"]))
async def paginate_users(message: Message, state: FSMContext):
    if message.text == "🏠 Bosh menyu":
        await state.clear()
        await show_main_menu(message)
        return

    data = await state.get_data()
    page = data.get("page", 0)

    if message.text == "➡️ Keyingi":
        page += 1
    elif message.text == "⬅️ Orqaga" and page > 0:
        page -= 1

    await state.update_data(page=page)
    await send_users_page(message, page)


@dp.message(Command("ratings"))
async def show_average_rating(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda ruxsat yo‘q.")
        return

    avg = await get_average_rating()
    if avg:
        await message.answer(f"⭐️ O'rtacha baho: {avg} / 5")
    else:
        await message.answer("🚫 Hozircha baholar mavjud emas.")


@dp.message(Command("download_excel"))
async def send_excel_file(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda ruxsat yo'q.")
        return

    await export_all_tables()  # <-- regenerate the Excel before sending

    file_path = "exported_data.xlsx"
    if not os.path.exists(file_path):
        await message.answer("⚠️ Excel fayli topilmadi.")
        return

    file = FSInputFile(file_path)
    await bot.send_document(chat_id=message.chat.id, document=file, caption="📊 Yangilangan Excel fayli!")


async def main():
    await init_db()
    await export_all_tables()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
