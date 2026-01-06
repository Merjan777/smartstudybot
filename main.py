import asyncio
import logging
import sqlite3
import os
from groq import Groq 
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from datetime import datetime

# database.py faylidan funksiyalarni chaqiramiz
from database import (
    init_db, add_user, get_random_question, update_points, 
    set_premium, check_and_update_limit, increment_usage,
    get_admin_stats
)

# 1. Bot sozlamalari
TOKEN = "8563326166:AAHrCE4EKwL_knjkz4Roo-C3AGPD_UiqY8I"
ADMIN_ID = 5153879168  
GROQ_API_KEY = "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"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- GROQ AI SOZLAMALARI ---
client = Groq(api_key=GROQ_API_KEY)

system_prompt = (
    "Siz aqlli, do'stona va erkin muloqot qiladigan yordamchisiz. "
    "Foydalanuvchining har qanday savoliga cheklovsiz javob bering. "
    "Javoblaringiz samimiy va tushunarli bo'lsin."
)

# 2. Holatlar (FSM)
class UserStates(StatesGroup):
    waiting_for_ai_question = State()

class AdminStates(StatesGroup):
    waiting_for_ad_content = State()
    waiting_for_premium_id = State()

# --- KLAVIATURALAR ---

def main_menu():
    kb = [
        [KeyboardButton(text="📝 Testni boshlash"), KeyboardButton(text="🇬🇧 Til o'rganish")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🤖 AI Yordamchi")],
        [KeyboardButton(text="🏆 Reyting"), KeyboardButton(text="💎 Premium")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def language_panel():
    kb = [
        [KeyboardButton(text="📝 Lug'at (3 ta/kun)"), KeyboardButton(text="📖 Grammatika (1 ta/kun)")],
        [KeyboardButton(text="🏠 Asosiy menyuga qaytish")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_panel():
    kb = [
        [KeyboardButton(text="📊 Umumiy statistika")],
        [KeyboardButton(text="📢 Reklama tarqatish")],
        [KeyboardButton(text="💎 Premium berish"), KeyboardButton(text="👥 Foydalanuvchilar")],
        [KeyboardButton(text="🏠 Asosiy menyuga qaytish")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def subject_menu():
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧮 Matematika", callback_data="subject_math")],
        [InlineKeyboardButton(text="🇬🇧 English Grammar", callback_data="subject_grammar")],
        [InlineKeyboardButton(text="📝 Vocabulary (Lug'at)", callback_data="subject_vocab")]
    ])
    return ikb

# --- FOYDALANUVCHI HANDLERLARI ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username or "User")
    await message.answer(f"Salom {message.from_user.full_name}!\nSmartStudy botiga xush kelibsiz.", reply_markup=main_menu())

@dp.message(Command("id"))
async def get_my_id(message: types.Message):
    await message.answer(f"🆔 Sizning Telegram ID raqamingiz: {message.from_user.id}\n\n(Nusxalash uchun ustiga bosing)")

@dp.message(F.text == "🇬🇧 Til o'rganish")
async def open_language_panel(message: types.Message):
    await message.answer("Til o'rganish bo'limini tanlang:", reply_markup=language_panel())

@dp.message(F.text == "📝 Testni boshlash")
async def start_quiz(message: types.Message):
    await message.answer("Qaysi fandan test topshirmoqchisiz?", reply_markup=subject_menu())

@dp.message(F.text == "🏠 Asosiy menyuga qaytish")
async def back_home(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy menyudasiz.", reply_markup=main_menu())

# --- GROQ AI HANDLERLARI (OVOZLI VA MATNLI) ---

@dp.message(F.text == "🤖 AI Yordamchi")
async def ai_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    is_premium, _, _ = check_and_update_limit(user_id)

    if is_premium == 1:
        await message.answer(
            "🚀 Erkin AI Yordamchi ishga tushdi.\n\n"
            "Menga matnli xabar bering yoki 🎤 ovozli xabar yuboring:", 
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🏠 Asosiy menyuga qaytish")]], resize_keyboard=True)
        )
        await state.set_state(UserStates.waiting_for_ai_question)
    else:
        await message.answer(
            "❌ Ushbu funksiya faqat Premium foydalanuvchilar uchun!\n\n"
            "AI yordamchidan foydalanish uchun Premium obunani faollashtiring.", 
            reply_markup=main_menu()
        )

# Ovozli xabarni qayta ishlash
@dp.message(UserStates.waiting_for_ai_question, F.voice)
async def ai_voice_answer(message: types.Message, state: FSMContext):
    await bot.send_chat_action(message.chat.id, "record_voice")
    
    # Faylni yuklab olish
    voice = message.voice
    file_info = await bot.get_file(voice.file_id)
    file_name = f"voice_{message.from_user.id}.ogg"
    await bot.download_file(file_info.file_path, file_name)
    
    try:
        # 1. Groq Whisper orqali matnga o'girish
        with open(file_name, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(file_name, file.read()),
                model="whisper-large-v3",
                response_format="text",
            )
        
        user_text = transcription
        if not user_text:
            return await message.answer("🎤 Ovozni aniqlab bo'lmadi. Iltimos, qaytadan yozing.")
            
        await message.answer(f"🎤 Siz dedingiz: {user_text}")

        # 2. AI-dan javob olish
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            model="llama-3.3-70b-versatile"
        )
        await message.reply(chat_completion.choices[0].message.content)

    except Exception as e:
        logging.error(f"Ovozli AI xatosi: {e}")
        await message.answer("⚠️ Ovozni qayta ishlashda xatolik yuz berdi. (Serverda ffmpeg o'rnatilganligini tekshiring)")
    finally:
        if os.path.exists(file_name):
            os.remove(file_name)

# Matnli xabarni qayta ishlash
@dp.message(UserStates.waiting_for_ai_question, F.text)
async def ai_text_answer(message: types.Message, state: FSMContext):
    if message.text == "🏠 Asosiy menyuga qaytish":
        await state.clear()
        return await message.answer("Asosiy menyu", reply_markup=main_menu())

    await bot.send_chat_action(message.chat.id, "typing")
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message.text}
            ],
            model="llama-3.3-70b-versatile"
        )
        await message.reply(chat_completion.choices[0].message.content)
    except Exception as e:
        logging.error(f"Groq xatosi: {e}")
        await message.answer("⚠️ Kechirasiz, texnik nosozlik yuz berdi.")

# --- TEST VA TIL O'RGANISH ---

async def send_new_lang_question(user_id, subject, message_obj):
    is_premium, v_count, g_count = check_and_update_limit(user_id)
    if is_premium == 0:
        if subject == "vocab" and v_count >= 3:
            return await (message_obj.answer if isinstance(message_obj, types.Message) else message_obj.message.answer)("❌ Bugungi lug'at limiti tugadi (3/3).")
        elif subject == "grammar" and g_count >= 1:
            return await (message_obj.answer if isinstance(message_obj, types.Message) else message_obj.message.answer)("❌ Bugungi grammatika limiti tugadi (1/1).")

    q = get_random_question(subject)
    if q:
        increment_usage(user_id, subject)
        text = f"📚 Bo'lim: {subject.capitalize()}\n\n❓ Savol: {q[2]}"
        buttons = [
            [InlineKeyboardButton(text=f"A) {q[3]}", callback_data=f"ans_A_{q[6]}_{subject}")],
            [InlineKeyboardButton(text=f"B) {q[4]}", callback_data=f"ans_B_{q[6]}_{subject}")],
            [InlineKeyboardButton(text=f"C) {q[5]}", callback_data=f"ans_C_{q[6]}_{subject}")]
        ]
        msg = message_obj if isinstance(message_obj, types.Message) else message_obj.message
        await msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.message(lambda message: message.text and ("Lug'at" in message.text or "Grammatika" in message.text))
async def start_language_test(message: types.Message):
    subject = "vocab" if "Lug'at" in message.text else "grammar"
    await send_new_lang_question(message.from_user.id, subject, message)

@dp.callback_query(F.data.startswith("ans_"))
async def check_answer(callback: CallbackQuery):
    data = callback.data.split("_")
    user_choice, correct_choice, subject = data[1], data[2], data[3]
    user_id = callback.from_user.id
    
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT is_premium FROM users WHERE user_id=?", (user_id,))
    res = cursor.fetchone()
    is_premium = res[0] if res else 0
    conn.close()

    if user_choice == correct_choice:
        ball = 10 if is_premium == 1 else 5
        update_points(user_id, ball)
        await callback.answer(f"✅ To'g'ri! +{ball} ball")
    else:
        await callback.answer(f"❌ Noto'g'ri! To'g'ri: {correct_choice}", show_alert=True)
    
    await callback.message.delete()
    if subject in ["vocab", "grammar"]:
        await send_new_lang_question(user_id, subject, callback)

@dp.callback_query(F.data.startswith("subject_"))
async def send_callback_question(callback: CallbackQuery):
    subject = callback.data.split("_")[1]
    q = get_random_question(subject)
    if q:
        text = f"📚 Fan: {subject.capitalize()}\n\n❓ Savol: {q[2]}"
        buttons = [[InlineKeyboardButton(text=f"A) {q[3]}", callback_data=f"ans_A_{q[6]}_{subject}")],
                   [InlineKeyboardButton(text=f"B) {q[4]}", callback_data=f"ans_B_{q[6]}_{subject}")],
                   [InlineKeyboardButton(text=f"C) {q[5]}", callback_data=f"ans_C_{q[6]}_{subject}")]]
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# --- STATISTIKA VA REYTING ---

@dp.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    is_premium, v_count, g_count = check_and_update_limit(message.from_user.id)
    conn = sqlite3.connect('quiz_bot.db'); cursor = conn.cursor()
    cursor.execute("SELECT points FROM users WHERE user_id=?", (message.from_user.id,))
    points_res = cursor.fetchone()
    points = points_res[0] if points_res else 0
    conn.close()
    
    status = "💎 Premium" if is_premium == 1 else "Bepul"
    text = (f"📊 Natijalar:\n👤 {message.from_user.full_name}\n✨ Ballar: {points}\n🛡 Status: {status}")
    await message.answer(text)

@dp.message(F.text == "🏆 Reyting")
async def show_leaderboard(message: types.Message):
    conn = sqlite3.connect('quiz_bot.db'); cursor = conn.cursor()
    cursor.execute("SELECT username, points, is_premium FROM users ORDER BY points DESC LIMIT 10")
    leaders = cursor.fetchall(); conn.close()
    text = "🏆 TOP 10:\n\n"
    for i, user in enumerate(leaders, 1):
        p = "💎" if user[2] == 1 else ""
        text += f"{i}. {user[0]} {p} — {user[1]} ball\n"
    await message.answer(text)

@dp.message(F.text == "💎 Premium")
async def premium_info(message: types.Message):
    await message.answer("💎 Premium Obuna:\n✅ Ovozli AI muloqot!\n✅ Cheksiz testlar!\n💳 Karta: 9860 2466 0200 6594")

# --- ADMIN PANEL ---

@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def open_admin(message: types.Message):
    await message.answer("🛠 Admin panel:", reply_markup=admin_panel())

@dp.message(F.text == "📊 Umumiy statistika", F.from_user.id == ADMIN_ID)
async def admin_stats_msg(message: types.Message):
    t, p, q = get_admin_stats()
    await message.answer(f"👥 Jami: {t}\n💎 Prem: {p}\n📚 Savollar: {q}")

@dp.message(F.text == "📢 Reklama tarqatish", F.from_user.id == ADMIN_ID)
async def ad_start(message: types.Message, state: FSMContext):
    await message.answer("Xabarni yuboring:"); await state.set_state(AdminStates.waiting_for_ad_content)

@dp.message(AdminStates.waiting_for_ad_content)
async def ad_broadcast(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('quiz_bot.db'); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users"); users = cursor.fetchall(); conn.close()
    for u in users:
        try: await message.copy_to(u[0]); await asyncio.sleep(0.05)
        except: continue
    await message.answer("📢 Yuborildi."); await state.clear()

@dp.message(F.text == "💎 Premium berish", F.from_user.id == ADMIN_ID)
async def prem_give_start(message: types.Message, state: FSMContext):
    await message.answer("ID yuboring:"); await state.set_state(AdminStates.waiting_for_premium_id)

@dp.message(AdminStates.waiting_for_premium_id)
async def prem_give_done(message: types.Message, state: FSMContext):
    try:
        set_premium(int(message.text), 1)
        await message.answer("✅ Tayyor!"); await state.clear()
    except: await message.answer("❌ Xato.")

async def main():
    init_db()
    await dp.start_polling(bot, skip_updates=True, request_timeout=60)

if __name__ == "__main__":
    asyncio.run(main())