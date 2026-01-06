import sqlite3
import random
from datetime import datetime

def init_db():
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            daily_vocab_count INTEGER DEFAULT 0,
            daily_grammar_count INTEGER DEFAULT 0,
            last_activity TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            question_text TEXT,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct_option TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, last_activity) VALUES (?, ?, ?)", (user_id, username, today))
    conn.commit()
    conn.close()

def get_random_question(subject):
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE type=? ORDER BY RANDOM() LIMIT 1", (subject,))
    question = cursor.fetchone()
    conn.close()
    return question

def update_points(user_id, points):
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points, user_id))
    conn.commit()
    conn.close()

def check_and_update_limit(user_id):
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT is_premium, daily_vocab_count, daily_grammar_count, last_activity FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if user:
        is_premium, v_count, g_count, last_date = user
        if last_date != today:
            cursor.execute("UPDATE users SET daily_vocab_count=0, daily_grammar_count=0, last_activity=? WHERE user_id=?", (today, user_id))
            conn.commit()
            v_count, g_count = 0, 0
        conn.close()
        return is_premium, v_count, g_count
    conn.close()
    return 0, 0, 0

def increment_usage(user_id, subject):
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    if subject == "vocab":
        cursor.execute("UPDATE users SET daily_vocab_count = daily_vocab_count + 1 WHERE user_id=?", (user_id,))
    elif subject == "grammar":
        cursor.execute("UPDATE users SET daily_grammar_count = daily_grammar_count + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def set_premium(user_id, status=1):
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_premium = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

def get_admin_stats():
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
    premium_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM questions")
    total_questions = cursor.fetchone()[0]
    conn.close()
    return total_users, premium_users, total_questions