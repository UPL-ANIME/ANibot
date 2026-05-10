import os
import telebot
import base64
import json
import requests
from github import Github, Auth
from telebot import types
import random
import string
import time
import re 
import yt_dlp

# --- TRANSLATE FUNKSIYASI ---
def translate_text(text, src='en', dest='uz'):
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={src}&tl={dest}&dt=t&q={requests.utils.quote(text)}"
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            return data[0][0][0]
        return text
    except:
        return text

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN")
GH_TOKEN = os.getenv("GH_TOKEN")
REPO_NAME = "UPL-ANIME/annn"
FILE_PATH = "anim.json"
SHORT_PATH = "short.json"
WEB_SETTINGS_PATH = "wepset.json"
ANIMEID_PATH = "animeid.json"
CHANNELS_PATH = "channels.json"
ADMINS_PATH = "admins.json" 
ADMIN_ID = 5297746319
MINI_APP_URL = "https://upl-anime.github.io/TGteganime/"
IMGBB_API_KEY = "4370f5ebb3ad2302e03c1638b2ccb8c2"
POST_CHANNEL_ID = "@uzbekchaanimelarafna"
WISTIA_API_KEY = "93fce19521210fa554aa4ac475a39e55066b539df4a44490d39d6a118b7c4f8b"

GENRES = ["Sarguzasht", "Fantaziya", "Romantika", "Drama", "Komediya", "Isekai", "Psixologik", "Horror", "Hayotiy", "Sport", "Magik"]

auth = Auth.Token(GH_TOKEN)
g = Github(auth=auth)
bot = telebot.TeleBot(TOKEN)
user_data = {}
random_map = {}
last_click = {}

# --- YORDAMCHI FUNKSIYALAR ---
def get_github_content(path):
    try:
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(path)
        data = json.loads(base64.b64decode(contents.content).decode("utf-8"))
        return data, contents
    except Exception:
        if path == FILE_PATH: return [], None
        if path == SHORT_PATH: return [], None
        if path == WEB_SETTINGS_PATH: return {"name": "AFNA", "logo": ""}, None
        if path == CHANNELS_PATH: return {"tg": [], "insta": ""}, None
        if path == ADMINS_PATH: return [ADMIN_ID], None
        return {}, None

def is_admin(user_id):
    admins, _ = get_github_content(ADMINS_PATH)
    return user_id in admins

def load_all_ids():
    global random_map
    data, _ = get_github_content(ANIMEID_PATH)
    if data and isinstance(data, dict):
        random_map = data

def upload_to_imgbb(message):
    try:
        if message.photo:
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            url = "https://api.imgbb.com/1/upload"
            payload = {"key": IMGBB_API_KEY}
            files = {"image": downloaded_file}
            res_raw = requests.post(url, payload, files=files)
            if res_raw.status_code == 200:
                res = res_raw.json()
                return res['data']['url'] if res.get('success') else None
    except:
        return None
    return None

def download_from_link(link):
    """Linkdan video yuklab olish (Maksimal himoya bilan)"""
    file_name = f"video_{int(time.time())}.mp4"
    try:
        cookie_path = 'cookies.txt'
        ydl_opts = {
            # Faqat tayyor MP4 formatini yuklaymiz (FFmpeg talab qilmasligi uchun)
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': file_name,
            'quiet': True,
            'no_warnings': True,
            # YouTube-ga biz brauzermiz deb aytamiz
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'referer': 'https://www.google.com/',
            'nocheckcertificate': True,
            'geo_bypass': True,
        }
        
        # Agar cookies bo'lsa, ulash
        if os.path.exists(cookie_path):
            ydl_opts['cookiefile'] = cookie_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])
        
        if os.path.exists(file_name):
            with open(file_name, 'rb') as f:
                data = f.read()
            os.remove(file_name)
            return data
    except Exception as e:
        print(f"DL Error: {e}")
        if os.path.exists(file_name): os.remove(file_name)
    return None

def upload_video_to_wistia(file_bytes):
    try:
        url = "https://upload.wistia.com/"
        params = {"api_password": WISTIA_API_KEY}
        files = {"file": (f"v_{int(time.time())}.mp4", file_bytes, "video/mp4")}
        res = requests.post(url, params=params, files=files)
        if res.status_code == 200:
            return res.json()["hashed_id"]
    except:
        return None

def save_github(repo, contents, path, data):
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    try:
        current_file = repo.get_contents(path)
        repo.update_file(path, "update", json_str, current_file.sha)
    except:
        repo.create_file(path, "create", json_str)

def check_subscription(user_id):
    if is_admin(user_id): return True
    data, _ = get_github_content(CHANNELS_PATH)
    if not data or not data.get("tg"): return True
    for channel in data["tg"]:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked']: return False
        except: continue
    return True

# --- ADMIN FUNKSIYALARI ---
def admin_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Yangi qism qo'shish", callback_data="add_anime"),
        types.InlineKeyboardButton("🎥 Shorts yuklash", callback_data="add_shorts"),
        types.InlineKeyboardButton("⚙️ Animelarni tahrirlash", callback_data="manage_anime"),
        types.InlineKeyboardButton("👑 Adminlarni boshqarish", callback_data="manage_admins"),
        types.InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_to_admin")
    )
    return markup

def genre_keyboard(selected_genres=[]):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(f"{'✅ ' if g in selected_genres else ''}{g}", callback_data=f"select_genre_{g}") for g in GENRES]
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_genres"))
    return markup

# --- HANDLERS ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    if not check_subscription(message.from_user.id):
        data, _ = get_github_content(CHANNELS_PATH)
        markup = types.InlineKeyboardMarkup(row_width=1)
        for ch in data.get("tg", []):
            markup.add(types.InlineKeyboardButton("Kanalga a'zo bo'lish", url=f"https://t.me/{ch.replace('@', '')}"))
        markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
        bot.send_message(message.chat.id, "Botdan foydalanish uchun kanallarga a'zo bo'ling:", reply_markup=markup)
        return

    text = message.text.split()
    if len(text) > 1:
        file_id = random_map.get(text[1])
        if file_id:
            bot.send_video(message.chat.id, file_id)
            return

    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🚀 Ilovani ochish", web_app=types.WebAppInfo(MINI_APP_URL)))
    bot.send_message(message.chat.id, "Xush kelibsiz!", reply_markup=markup)

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Admin panel:", reply_markup=admin_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    repo = g.get_repo(REPO_NAME)
    data_list, contents = get_github_content(FILE_PATH)

    if call.data == "add_shorts":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for anime in data_list[-15:]:
            markup.add(types.InlineKeyboardButton(anime["title"][:30], callback_data=f"shortona_{anime['id']}"))
        bot.edit_message_text("Shorts uchun ona animeni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("shortona_"):
        user_data["short_ona_id"] = call.data.split("_")[1]
        for a in data_list:
            if str(a["id"]) == str(user_data["short_ona_id"]):
                user_data["short_ona_name"] = a["title"].split(",{")[0].strip()
                break
        user_data["short_list"] = []
        msg = bot.send_message(call.message.chat.id, "YouTube Shorts linkini yuboring. Tugatgach /boldi deb yozing:")
        bot.register_next_step_handler(msg, collect_shorts)

def collect_shorts(message):
    if message.text == "/boldi":
        finalize_shorts(message)
        return

    if message.video or message.document:
        bot.send_message(message.chat.id, "⏳ Fayl yuborilmoqda...")
        f_id = message.video.file_id if message.video else message.document.file_id
        f_bytes = bot.download_file(bot.get_file(f_id).file_path)
        h_id = upload_video_to_wistia(f_bytes)
        if h_id: 
            user_data["short_list"].append(h_id)
            bot.send_message(message.chat.id, "✅ Fayl qabul qilindi.")
    
    elif message.text and "http" in message.text:
        bot.send_message(message.chat.id, "⏳ Linkdan yuklanmoqda (cookies bilan)...")
        v_bytes = download_from_link(message.text)
        if v_bytes:
            h_id = upload_video_to_wistia(v_bytes)
            if h_id: 
                user_data["short_list"].append(h_id)
                bot.send_message(message.chat.id, "✅ Muvaffaqiyatli yuklandi.")
            else:
                bot.send_message(message.chat.id, "❌ Wistia-ga yuklashda xato.")
        else:
            bot.send_message(message.chat.id, "❌ Link xatosi yoki YouTube blokladi. Cookies-ni yangilab ko'ring.")

    bot.register_next_step_handler(message, collect_shorts)

def finalize_shorts(message):
    if not user_data.get("short_list"):
        bot.send_message(message.chat.id, "Hech narsa saqlanmadi.")
        return
    repo = g.get_repo(REPO_NAME)
    shorts, s_cont = get_github_content(SHORT_PATH)
    for item in user_data["short_list"]:
        shorts.append({"nom": user_data["short_ona_name"], "link": item, "ona": user_data["short_ona_id"]})
    save_github(repo, s_cont, SHORT_PATH, shorts)
    bot.send_message(message.chat.id, f"✅ {len(user_data['short_list'])} ta shorts saqlandi!", reply_markup=admin_menu())

load_all_ids()
bot.infinity_polling()
