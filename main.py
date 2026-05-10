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
last_sticker_link = None

# Tugmani qayta-qayta bosishdan himoya (Antiflood)
last_click = {}

# --- YORDAMCHI FUNKSIYALAR ---
def get_github_content(path):
    try:
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(path)
        data = json.loads(base64.b64decode(contents.content).decode("utf-8"))
        return data, contents
    except Exception as e:
        print(f"({path}): {e}")
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
        print(f"✅ {len(random_map)}.")

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
            return None
        elif message.text and (message.text.startswith("http://") or message.text.startswith("https://")):
            return message.text
    except:
        return None
    return None

def get_full_anime_info(image_url):
    """AI orqali anime haqida to'liq ma'lumot olish"""
    try:
        res = requests.get(f"https://api.trace.moe/search?url={image_url}")
        data = res.json()
        if data['result']:
            anilist_id = data['result'][0]['anilist']
            query = '''
            query ($id: Int) {
              Media (id: $id, type: ANIME) {
                title { english romaji }
                description
                seasonYear
                countryOfOrigin
                genres
              }
            }
            '''
            variables = {'id': anilist_id}
            response = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': variables})
            info = response.json()['data']['Media']
            
            clean_desc = re.sub('<[^<]+?>', '', info['description'])[:250] + "..."
            country = "Yaponiya" if info['countryOfOrigin'] == "JP" else info['countryOfOrigin']
            
            uz_desc = translate_text(clean_desc, 'en', 'uz')
            uz_genres = [translate_text(g, 'en', 'uz') for g in info['genres']]
            
            full_text = (
                f"➤🌍 Davlati: {country}\n"
                f"➤📆 Chiqqan yili: {info['seasonYear']}\n"
                f"➤🎞 Janrlar: {', '.join(uz_genres)}\n"
                f"➤📝 Voqealar: {uz_desc}"
            )
            return info['title']['romaji'] or info['title']['english'], full_text
    except:
        return None, "Ma'lumot topilmadi."
    return None, "Ma'lumot topilmadi."

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
            if member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            print(f"Error checking {channel}: {e}")
            continue
    return True

# --- MENULAR ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📺 Anime ko'rish")
    return markup

def admin_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Yangi qism qo'shish", callback_data="add_anime"),
        types.InlineKeyboardButton("🎥 Shorts yuklash", callback_data="add_shorts"),
        types.InlineKeyboardButton("🌐 Web App sozlamalari", callback_data="web_settings"),
        types.InlineKeyboardButton("⚙️ Animelarni tahrirlash", callback_data="manage_anime"),
        types.InlineKeyboardButton("📢 Majburiy obuna sozalamalari", callback_data="sub_settings"),
        types.InlineKeyboardButton("👑 Adminlarni boshqarish", callback_data="manage_admins"),
        types.InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_to_admin")
    )
    return markup

def genre_keyboard(selected_genres=[]):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(f"{'✅ ' if g in selected_genres else ''}{g}", callback_data=f"select_genre_{g}") for g in GENRES]
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_genres"))
    markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="add_anime"))
    return markup

# --- HANDLERS ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    if not check_subscription(message.from_user.id):
        data, _ = get_github_content(CHANNELS_PATH)
        markup = types.InlineKeyboardMarkup(row_width=1)
        if data and data.get("tg"):
            for ch in data["tg"]:
                markup.add(types.InlineKeyboardButton("Kanal 📦", url=f"https://t.me/{ch.replace('@', '')}"))
        if data and data.get("insta"):
            markup.add(types.InlineKeyboardButton("Instagram", url=data["insta"]))
        
        start_param = ""
        text = message.text.split()
        if len(text) > 1:
            start_param = f"_{text[1]}"
            
        markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_sub{start_param}"))
        bot.send_message(message.chat.id, "Botdan foydalanish uchun kanallarga a'zo bo'ling📜:", reply_markup=markup)
        return

    text = message.text.split()
    if len(text) > 1:
        anime_key = text[1]
        file_id = random_map.get(anime_key)
        if file_id:
            data_list, _ = get_github_content(FILE_PATH)
            caption_text = "✨ Anime qismi"
            for anime in data_list:
                for ep in anime.get("qismlar", []):
                    if anime_key in ep.get("link", ""):
                        clean_t = re.sub(r",\{.*?\}", "", anime["title"]).split("📽")[0].strip()
                        caption_text = f"🎬 {clean_t}\n🎞 {ep['nom']}"
                        break
            try: bot.send_video(message.chat.id, file_id, caption=caption_text)
            except: bot.send_document(message.chat.id, file_id, caption=caption_text)
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚀 Ilovani ochish", web_app=types.WebAppInfo(MINI_APP_URL)))
    bot.send_message(message.chat.id, "Xush kelibsiz! Anime ko'rish uchun quyidagi tugmani bosing:", reply_markup=markup)

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Admin panelga xush kelibsiz:", reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, "Siz admin emassiz!")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    global last_sticker_link
    now = time.time()
    if call.from_user.id in last_click and now - last_click[call.from_user.id] < 1:
        bot.answer_callback_query(call.id, "Iltimos, biroz kuting...")
        return
    last_click[call.from_user.id] = now
    repo = g.get_repo(REPO_NAME)

    if call.data.startswith("check_sub"):
        if check_subscription(call.from_user.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            param = call.data.replace("check_sub", "")
            if param.startswith("_"):
                anime_key = param[1:]
                file_id = random_map.get(anime_key)
                if file_id:
                    try: bot.send_video(call.message.chat.id, file_id)
                    except: bot.send_document(call.message.chat.id, file_id)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🚀 Ilovani ochish", web_app=types.WebAppInfo(MINI_APP_URL)))
            bot.send_message(call.message.chat.id, "Xush kelibsiz!", reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "Hali hamma kanallarga a'zo emassiz!", show_alert=True)
        return

    if not is_admin(call.from_user.id): return
    data_list, contents = get_github_content(FILE_PATH)
    
    if call.data == "back_to_admin":
        bot.edit_message_text("Admin panel", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

    elif call.data == "web_settings":
        web_data, _ = get_github_content(WEB_SETTINGS_PATH)
        text = f"🌐 Web App Sozlamalari:\n\nNomi: {web_data['name']}\nLogo: {web_data['logo']}"
        msg = bot.send_message(call.message.chat.id, f"{text}\n\nYangi nom kiriting yoki yangi rasm yuboring:")
        bot.register_next_step_handler(msg, update_web_settings)

    elif call.data == "add_shorts":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for anime in data_list[-15:]:
            markup.add(types.InlineKeyboardButton(anime["title"], callback_data=f"shortona_{anime['id']}"))
        markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin"))
        bot.edit_message_text("Shorts uchun ona animeni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("shortona_"):
        user_data["short_ona_id"] = call.data.split("_")[1]
        for a in data_list:
            if str(a["id"]) == str(user_data["short_ona_id"]):
                user_data["short_ona_name"] = re.sub(r",\{.*?\}", "", a["title"]).split("📽")[0].strip()
                break
        user_data["short_list"] = []
        msg = bot.send_message(call.message.chat.id, f"🎬 {user_data['short_ona_name']} uchun shorts yuboring (Fayl, Link yoki JSON ro'yxat).\n\nTugatgach /boldi deb yozing:")
        bot.register_next_step_handler(msg, collect_shorts_multi)

    elif call.data == "manage_admins":
        admins, _ = get_github_content(ADMINS_PATH)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ Yangi admin qo'shish", callback_data="add_new_admin"))
        for adm in admins:
            if adm != ADMIN_ID:
                markup.add(types.InlineKeyboardButton(f"❌ O'chirish: {adm}", callback_data=f"del_adm_{adm}"))
        markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin"))
        bot.edit_message_text("Adminlar boshqaruvi:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "add_new_admin":
        msg = bot.send_message(call.message.chat.id, "Yangi admin ID raqamini yuboring:")
        bot.register_next_step_handler(msg, save_admin_id)

    elif call.data == "sub_settings":
        sub_data, _ = get_github_content(CHANNELS_PATH)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_tg"),
            types.InlineKeyboardButton("❌ Kanal o'chirish", callback_data="manage_sub_channels"),
            types.InlineKeyboardButton("📸 Insta Link", callback_data="set_insta"),
            types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")
        )
        text = f"📢 TG: {', '.join(sub_data.get('tg', []))}\n📸 Insta: {sub_data.get('insta', 'Yoqilmagan')}"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "add_anime":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for anime in data_list[-15:]:
            markup.add(types.InlineKeyboardButton(anime["title"], callback_data=f"anime_{anime['id']}"))
        markup.add(types.InlineKeyboardButton("🆕 Yangi anime", callback_data="new_anime"))
        markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin"))
        bot.edit_message_text("Anime tanlang (oxirgi qo'shilganlar):", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "manage_anime":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for anime in data_list:
            markup.add(types.InlineKeyboardButton(f"📝 {anime['title']}", callback_data=f"edit_{anime['id']}"))
        markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin"))
        bot.edit_message_text("Tahrirlash uchun animeni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("edit_"):
        user_data["edit_id"] = call.data.split("_")[1]
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("Nomini tahrirlash", callback_data="editname"),
            types.InlineKeyboardButton("Posterni tahrirlash", callback_data="editthumb"),
            types.InlineKeyboardButton("Title rasmini tahrirlash", callback_data="edittitlerasmi"),
            types.InlineKeyboardButton("Qismlarni boshqarish", callback_data="manage_eps"),
            types.InlineKeyboardButton("📝 So'zlar tayinlash (ko'p)", callback_data="assign_keyword"),
            types.InlineKeyboardButton("❌ Animeni o'chirish", callback_data="del_anime"),
            types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")
        )
        bot.edit_message_text("Taxrir bo'limi", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "assign_keyword":
        msg = bot.send_message(call.message.chat.id, "Kalit so'zlarni vergul bilan ajratib yuboring (masalan: naruto, boruto, kishi):")
        bot.register_next_step_handler(msg, update_anime_field, "keyword", data_list, repo, contents)

    elif call.data == "new_anime":
        user_data["exists"] = False
        user_data["genre"] = []
        user_data["fullnews"] = ""
        msg = bot.send_message(call.message.chat.id, "Anime nomini kiriting:")
        bot.register_next_step_handler(msg, get_new_title)

    elif call.data.startswith("select_genre_"):
        g_name = call.data.replace("select_genre_", "")
        if "genre" not in user_data: user_data["genre"] = []
        if g_name in user_data["genre"]: user_data["genre"].remove(g_name)
        else: user_data["genre"].append(g_name)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=genre_keyboard(user_data["genre"]))

    elif call.data == "confirm_genres":
        markup = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🔍 AI Qidiruv", callback_data="ai_search_start"),
            types.InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="ai_search_skip")
        )
        bot.send_message(call.message.chat.id, "AI orqali ma'lumot qidiramizmi?", reply_markup=markup)

    elif call.data == "ai_search_start":
        msg = bot.send_message(call.message.chat.id, "AI topishi uchun rasm yuboring:")
        bot.register_next_step_handler(msg, get_ai_result)

    elif call.data == "ai_search_skip":
        ask_title_sticker(call.message)

    elif call.data.startswith("anime_"):
        user_data["exists"] = True
        user_data["anime_id"] = call.data.split("_")[1]
        user_data["temp_videos"] = []
        bot.send_message(call.message.chat.id, "Videolarni yuboring. Tugatgach /boldi deb yozing.")
        bot.register_next_step_handler(call.message, collect_multi_videos)

# --- WEB SETTINGS ---
def update_web_settings(message):
    repo = g.get_repo(REPO_NAME)
    web_data, web_contents = get_github_content(WEB_SETTINGS_PATH)
    
    if message.photo:
        link = upload_to_imgbb(message)
        if link:
            web_data["logo"] = link
            bot.send_message(message.chat.id, "✅ Logo o'zgartirildi!")
    elif message.text:
        web_data["name"] = message.text
        bot.send_message(message.chat.id, "✅ Nom o'zgartirildi!")
    
    save_github(repo, web_contents, WEB_SETTINGS_PATH, web_data)
    bot.send_message(message.chat.id, "Admin panel", reply_markup=admin_menu())

# --- SHORTS MULTI UPLOAD MANTIQI ---
def collect_shorts_multi(message):
    if message.text == "/boldi":
        if not user_data.get("short_list"):
            bot.send_message(message.chat.id, "Hech narsa yubormadingiz!")
            return
        finalize_shorts_upload(message)
        return

    # 1. Video yoki Hujjat (Fayl) bo'lsa
    if message.video or message.document:
        process_short_file(message)

    # 2. Matn bo'lsa (JSON list yoki Oddiy Link)
    elif message.text:
        raw_text = message.text.strip()
        
        # JSON formatdagi linklar ro'yxati ekanligini tekshirish
        if raw_text.startswith("[") and raw_text.endswith("]"):
            try:
                links = json.loads(raw_text)
                if isinstance(links, list):
                    bot.send_message(message.chat.id, f"📦 JSON formatda {len(links)} ta link topildi. Navbat bilan yuklanmoqda...")
                    for single_link in links:
                        process_short_link(message, single_link.strip())
                else:
                    bot.send_message(message.chat.id, "❌ JSON list formatida emas.")
            except:
                bot.send_message(message.chat.id, "❌ JSON tahlilida xatolik yuz berdi.")
        
        # Bitta oddiy link bo'lsa
        elif raw_text.startswith("http"):
            process_short_link(message, raw_text)

    bot.register_next_step_handler(message, collect_shorts_multi)

def process_short_file(message):
    file_id = message.video.file_id if message.video else message.document.file_id
    bot.send_message(message.chat.id, "⏳ Fayl Wistiaga yuborilmoqda...")
    file_info = bot.get_file(file_id)
    file_bytes = bot.download_file(file_info.file_path)
    hashed_id = upload_video_to_wistia(file_bytes)
    if hashed_id:
        user_data["short_list"].append(hashed_id)
        bot.send_message(message.chat.id, f"✅ Fayl yuklandi. Jami: {len(user_data['short_list'])}")
    else:
        bot.send_message(message.chat.id, "❌ Wistia yuklashda xato.")

def process_short_link(message, link):
    bot.send_message(message.chat.id, f"⏳ Yuklanmoqda: {link}")
    video_bytes = download_from_link(link)
    if video_bytes:
        hashed_id = upload_video_to_wistia(video_bytes)
        if hashed_id:
            user_data["short_list"].append(hashed_id)
            bot.send_message(message.chat.id, f"✅ Tayyor: {link}")
        else:
            bot.send_message(message.chat.id, f"❌ Wistia xatosi (link): {link}")
    else:
        bot.send_message(message.chat.id, f"❌ Linkdan videoni olib bo'lmadi: {link}")

def download_from_link(link):
    """Linkdan video yuklab olish (YouTube cookies bilan)"""
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': 'temp_video.mp4',
            'quiet': True,
            'no_warnings': True,
            'cookiefile': 'cookies.txt',  # Papkadagi cookies fayli
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])
        
        if os.path.exists('temp_video.mp4'):
            with open('temp_video.mp4', 'rb') as f:
                data = f.read()
            os.remove('temp_video.mp4')
            return data
    except Exception as e:
        print(f"DL Error: {e}")
    return None

def upload_video_to_wistia(file_bytes):
    """Wistiaga yuklash"""
    try:
        url = "https://upload.wistia.com/"
        params = {"api_password": WISTIA_API_KEY}
        files = {"file": (f"short_{int(time.time())}.mp4", file_bytes, "video/mp4")}
        res = requests.post(url, params=params, files=files)
        if res.status_code == 200:
            return res.json()["hashed_id"]
    except:
        pass
    return None

def finalize_shorts_upload(message):
    repo = g.get_repo(REPO_NAME)
    shorts_data, shorts_contents = get_github_content(SHORT_PATH)
    
    for item in user_data["short_list"]:
        new_short = {
            "nom": user_data["short_ona_name"],
            "link": item,
            "ona": user_data["short_ona_id"]
        }
        shorts_data.append(new_short)
    
    save_github(repo, shorts_contents, SHORT_PATH, shorts_data)
    bot.send_message(message.chat.id, f"✅ {len(user_data['short_list'])} ta shorts muvaffaqiyatli saqlandi!", reply_markup=admin_menu())

# --- QADAMMA-QADAM MANTIQ ---
def get_new_title(message):
    user_data["title"] = message.text
    msg = bot.send_message(message.chat.id, "Anime bosh posterini yuboring:")
    bot.register_next_step_handler(msg, get_poster_initial)

def get_poster_initial(message):
    user_data["thumb"] = upload_to_imgbb(message) or message.text
    bot.send_message(message.chat.id, "Janrlarni tanlang:", reply_markup=genre_keyboard())

def get_ai_result(message):
    pic = upload_to_imgbb(message)
    if pic:
        bot.send_message(message.chat.id, "AI qidirmoqda...")
        orig_name, full_info = get_full_anime_info(pic)
        if orig_name:
            user_data["title"] = f"{user_data['title']} 📽 | {orig_name}"
            user_data["fullnews"] = full_info
            bot.send_message(message.chat.id, f"✅ Ma'lumotlar olindi va o'zbekchaga o'girildi!")
    ask_title_sticker(message)

def ask_title_sticker(message):
    search_q = user_data["title"].split('📽')[0].strip().replace(" ", "-")
    tenor_url = f"https://tenor.com/search/{search_q}-gifs"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎨 Brauzerda GIF tanlash", url=tenor_url))
    
    msg = bot.send_message(message.chat.id, "Title ichidagi rasm linkini yuboring yoki Chrome orqali GIF topib linkini tashlang:", reply_markup=markup)
    bot.register_next_step_handler(msg, finalize_title_with_sticker)

def finalize_title_with_sticker(message):
    link = None
    if message.text and (message.text.startswith("http://") or message.text.startswith("https://")):
        link = message.text
    else:
        link = upload_to_imgbb(message)
        
    if link: user_data["title"] = f"{user_data['title']} ,{{{link}}}"
    user_data["temp_videos"] = []
    bot.send_message(message.chat.id, "Videolarni yuboring va /boldi deb yozing.")
    bot.register_next_step_handler(message, collect_multi_videos)

def collect_multi_videos(message):
    if message.text == "/boldi":
        if not user_data.get("temp_videos"):
            bot.send_message(message.chat.id, "Video yubormadingiz!")
            return
        finalize_multi_upload(message)
        return
    if message.video or message.document:
        vid = message.video.file_id if message.video else message.document.file_id
        user_data["temp_videos"].append(vid)
        bot.send_message(message.chat.id, f"📥 {len(user_data['temp_videos'])}-qism qabul qilindi.")
    bot.register_next_step_handler(message, collect_multi_videos)

def finalize_multi_upload(message):
    repo = g.get_repo(REPO_NAME)
    db_data, db_contents = get_github_content(ANIMEID_PATH)
    anim_data, anim_contents = get_github_content(FILE_PATH)
    
    new_qismlar = []
    start_ep = 1
    if user_data.get("exists"):
        curr = next((a for a in anim_data if str(a["id"]) == str(user_data["anime_id"])), None)
        if curr: start_ep = len(curr["qismlar"]) + 1

    for i, vid in enumerate(user_data["temp_videos"]):
        r_key = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        db_data[r_key] = vid
        random_map[r_key] = vid
        ep_nom = f"{start_ep + i}-qism"
        new_qismlar.append({"nom": ep_nom, "link": f"https://t.me/{bot.get_me().username}?start={r_key}"})

    if user_data.get("exists"):
        for a in anim_data:
            if str(a["id"]) == str(user_data["anime_id"]):
                a["qismlar"].extend(new_qismlar)
                current_anime = a
                break
    else:
        a_id = f"a{int(time.time())}"
        current_anime = {
            "id": a_id, 
            "title": user_data["title"], 
            "thumb": user_data["thumb"], 
            "turkum": user_data["genre"], 
            "fullnews": user_data.get("fullnews", ""),
            "qismlar": new_qismlar
        }
        anim_data.append(current_anime)

    save_github(repo, db_contents, ANIMEID_PATH, db_data)
    save_github(repo, anim_contents, FILE_PATH, anim_data)

    clean_title = re.sub(r",\{.*?\}", "", current_anime["title"]).split("📽")[0].strip()
    caption = (
        f"➤🎬 Nomi: {clean_title}\n"
        f"➤🎥 Qismlar: {len(current_anime['qismlar'])}\n"
        f"➤🎞 Janri: {', '.join(current_anime['turkum'])}\n\n"
        f"{current_anime.get('fullnews', '')}\n\n"
        f"Bot orqali ko'rish 👇"
    )
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📺 Tomosha qilish", url=f"https://t.me/{bot.get_me().username}/link?startapp={current_anime['id']}"))
    
    try: bot.send_photo(POST_CHANNEL_ID, current_anime["thumb"], caption=caption, reply_markup=markup)
    except: bot.send_message(POST_CHANNEL_ID, caption, reply_markup=markup)
    
    bot.send_message(message.chat.id, "✅ Jarayon yakunlandi!", reply_markup=main_menu())

def update_anime_field(message, field, data_list, repo, contents):
    val = upload_to_imgbb(message) if field == "thumb" else message.text
    for anime in data_list:
        if str(anime["id"]) == str(user_data["edit_id"]):
            anime[field] = val
            break
    save_github(repo, contents, FILE_PATH, data_list)
    bot.send_message(message.chat.id, "✅ Yangilandi!", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: True)
def text_h(message):
    if not check_subscription(message.from_user.id):
        handle_start(message)
        return

    data_list, _ = get_github_content(FILE_PATH)
    for anime in data_list:
        if "keyword" in anime:
            keywords = [k.strip().lower() for k in anime["keyword"].split(",")]
            if message.text.lower() in keywords:
                clean_title = re.sub(r",\{.*?\}", "", anime["title"]).split("📽")[0].strip()
                caption = f"➤🎬 Nomi: {clean_title}\n➤🎥 Qismlar: {len(anime['qismlar'])}\n\n{anime.get('fullnews', '')}"
                markup = types.InlineKeyboardMarkup(row_width=2)
                btns = [types.InlineKeyboardButton(ep["nom"], url=ep["link"]) for ep in anime["qismlar"]]
                markup.add(*btns)
                markup.add(types.InlineKeyboardButton("📺 Mini App", url=f"https://t.me/{bot.get_me().username}/link?startapp={anime['id']}"))
                if anime["thumb"].startswith("http"):
                    bot.send_photo(message.chat.id, anime["thumb"], caption=caption, reply_markup=markup)
                else:
                    bot.send_message(message.chat.id, caption, reply_markup=markup)
                return

    if message.text == "📺 Anime ko'rish": 
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🚀 Ilovani ochish", web_app=types.WebAppInfo(MINI_APP_URL)))
        bot.send_message(message.chat.id, "Mini Appni ochish:", reply_markup=markup)

load_all_ids()
bot.infinity_polling()
