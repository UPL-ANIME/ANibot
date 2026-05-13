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
WISTIA_API_KEY = "d8618bedf2489db649126aae9d9e83093d24b25830dd965ce791ec1a29a1c9ff"

GENRES = ["Sarguzasht", "Fantaziya", "Romantika", "Drama", "Komediya", "Isekai", "Psixologik", "Horror", "Hayotiy", "Sport", "Magik"]

auth = Auth.Token(GH_TOKEN)
g = Github(auth=auth)
bot = telebot.TeleBot(TOKEN)

user_data = {}
random_map = {}
last_sticker_link = None
last_click = {}

def get_user_step_data(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            "genre": [],
            "temp_videos": [],
            "short_list": [],
            "fullnews": "",
            "exists": False
        }
    return user_data[user_id]

def get_github_content(path):
    try:
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(path)
        data = json.loads(base64.b64decode(contents.content).decode("utf-8"))
        return data, contents
    except Exception as e:
        if path == FILE_PATH: return [], None
        if path == SHORT_PATH: return [], None
        if path == WEB_SETTINGS_PATH: return {"name": "AFNA", "logo": ""}, None
        if path == CHANNELS_PATH: return {"tg": [], "insta": ""}, None
        if path == ADMINS_PATH: return [ADMIN_ID, 6448946979], None
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
    except: return None
    return None

def get_full_anime_info(image_url):
    try:
        res = requests.get(f"https://api.trace.moe/search?url={image_url}")
        data = res.json()
        if data['result']:
            anilist_id = data['result'][0]['anilist']
            query = '''query ($id: Int) { Media (id: $id, type: ANIME) { title { english romaji } description seasonYear countryOfOrigin genres } }'''
            variables = {'id': anilist_id}
            response = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': variables})
            info = response.json()['data']['Media']
            clean_desc = re.sub('<[^<]+?>', '', info['description'])[:250] + "..."
            country = "Yaponiya" if info['countryOfOrigin'] == "JP" else info['countryOfOrigin']
            uz_desc = translate_text(clean_desc, 'en', 'uz')
            uz_genres = [translate_text(g, 'en', 'uz') for g in info['genres']]
            full_text = f"➤🌍 Davlati: {country}\n➤📆 Chiqqan yili: {info['seasonYear']}\n➤🎞 Janrlar: {', '.join(uz_genres)}\n➤📝 Voqealar: {uz_desc}"
            return info['title']['romaji'] or info['title']['english'], full_text
    except: return None, "Ma'lumot topilmadi."
    return None, "Ma'lumot topilmadi."

def save_github(repo, contents, path, data):
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    try:
        current_file = repo.get_contents(path)
        repo.update_file(path, "update", json_str, current_file.sha)
    except: repo.create_file(path, "create", json_str)

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

# --- ASOSIY HANDLERLAR ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    udata = get_user_step_data(user_id)
    repo = g.get_repo(REPO_NAME)
    data_list, contents = get_github_content(FILE_PATH)

    if call.data == "add_direct_main":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📥 Oddiy yuklash (Anime tanlash)", callback_data="add_direct_simple"),
            types.InlineKeyboardButton("📄 JSON formatda yuklash", callback_data="add_direct_json"),
            types.InlineKeyboardButton("⚙️ Linklarni boshqarish", callback_data="manage_direct_links"),
            types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")
        )
        bot.edit_message_text("Direkt linklarni qo'shish uslubini tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "add_direct_json":
        msg = bot.send_message(call.message.chat.id, "JSON formatni tashlang:\n\n`{\"nom\":[son]}`")
        bot.register_next_step_handler(msg, process_direct_json_input)

# --- DIREKT VA JSON LINKLARNI QAYTA ISHLASH (YANGI LOGIKA) ---
def process_direct_json_input(message):
    try:
        udata = get_user_step_data(message.from_user.id)
        udata["bulk_json"] = json.loads(message.text)
        udata["bulk_links"] = []
        bot.send_message(message.chat.id, "JSON qabul qilindi. Endi linklar bor xabarlarni tashlang (hamma linklarni birdaniga topaman). Tugatgach /boldi deb yozing.")
        bot.register_next_step_handler(message, collect_bulk_links)
    except:
        bot.send_message(message.chat.id, "Xato! JSON formatini tekshiring.")

def collect_bulk_links(message):
    udata = get_user_step_data(message.from_user.id)
    if message.text == "/boldi":
        finalize_bulk_direct(message)
        return
    if message.text:
        # Xabardagi BARCHA 'WATCH :' linklarini topish
        found = re.findall(r"WATCH\s*:\s*(https?://[^\s\n]+)", message.text)
        if found:
            udata.setdefault("bulk_links", []).extend(found)
            bot.send_message(message.chat.id, f"✅ Ushbu xabardan {len(found)} ta link olindi. Jami: {len(udata['bulk_links'])}")
    bot.register_next_step_handler(message, collect_bulk_links)

def finalize_bulk_direct(message):
    udata = get_user_step_data(message.from_user.id)
    repo = g.get_repo(REPO_NAME)
    anim_data, anim_contents = get_github_content(FILE_PATH)
    
    all_links = udata.get("bulk_links", [])
    link_ptr = 0 # Linklar ro'yxati uchun ko'rsatkich
    
    for anime_key, val in udata["bulk_json"].items():
        count = val[0]
        # Kerakli miqdordagi linklarni ketma-ketlikda kesib olish
        current_set = all_links[link_ptr : link_ptr + count]
        link_ptr += count
        
        # Animeni topish (nomi bo'yicha)
        target = None
        for a in anim_data:
            if anime_key.lower() in a["title"].lower():
                target = a
                break
        
        if target and current_set:
            for i, link in enumerate(current_set):
                ep_nom = f"{len(target['qismlar']) + 1}-qism"
                r_key = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
                
                # Yangi linkvideo biriktirish
                target["qismlar"].append({
                    "nom": ep_nom,
                    "linkvideo": link.strip(),
                    "link": f"https://t.me/{bot.get_me().username}?start={r_key}"
                })
    
    save_github(repo, anim_contents, FILE_PATH, anim_data)
    bot.send_message(message.chat.id, "✅ Barcha linklar ketma-ketlik asosida animelarga biriktirildi!", reply_markup=admin_menu())

# --- QOLGAN STANDART FUNKSIYALAR ---
def admin_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("📤 Direkt linklar", callback_data="add_direct_main"), types.InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_to_admin"))
    return markup

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Admin panel:", reply_markup=admin_menu())

load_all_ids()
bot.infinity_polling()
