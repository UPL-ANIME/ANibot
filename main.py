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

# Multi-user support uchun user_data'ni lug'at ko'rinishida saqlaymiz
user_data = {}
random_map = {}
last_sticker_link = None

# Tugmani qayta-qayta bosishdan himoya (Antiflood)
last_click = {}

# Har bir user uchun data ob'ektini yaratish yordamchisi
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
        types.InlineKeyboardButton("📤 Direkt qismlar qo'shish", callback_data="add_direct_main"),
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
    user_id = call.from_user.id
    udata = get_user_step_data(user_id)

    if user_id in last_click and now - last_click[user_id] < 1:
        bot.answer_callback_query(call.id, "Iltimos, biroz kuting...")
        return
    last_click[user_id] = now
    repo = g.get_repo(REPO_NAME)

    if call.data.startswith("check_sub"):
        if check_subscription(user_id):
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

    if not is_admin(user_id): return
    data_list, contents = get_github_content(FILE_PATH)
    
    if call.data == "back_to_admin":
        bot.edit_message_text("Admin panel", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

    elif call.data == "add_direct_main":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📥 Oddiy yuklash (Anime tanlash)", callback_data="add_direct_simple"),
            types.InlineKeyboardButton("📄 JSON formatda yuklash", callback_data="add_direct_json"),
            types.InlineKeyboardButton("⚙️ Linklarni boshqarish", callback_data="manage_direct_links"),
            types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")
        )
        bot.edit_message_text("Direkt linklarni qo'shish uslubini tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "add_direct_simple":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for anime in data_list[-15:]:
            markup.add(types.InlineKeyboardButton(anime["title"], callback_data=f"direkt_{anime['id']}"))
        markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="add_direct_main"))
        bot.edit_message_text("Qism qo'shish uchun ona animeni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "add_direct_json":
        msg = bot.send_message(call.message.chat.id, "JSON formatni tashlang:\n\n`{\"nom\":[son]}`")
        bot.register_next_step_handler(msg, process_direct_json_input)

    elif call.data == "manage_direct_links":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for anime in data_list:
            direct_count = sum(1 for q in anime.get("qismlar", []) if "linkvideo" in q)
            if direct_count > 0:
                markup.add(types.InlineKeyboardButton(f"{anime['title']} ({direct_count} ta)", callback_data=f"man_dir_{anime['id']}"))
        markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="add_direct_main"))
        bot.edit_message_text("Linklarni boshqarish uchun animeni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("man_dir_"):
        udata["anime_id"] = call.data.split("_")[2]
        target = next((a for a in data_list if str(a["id"]) == str(udata["anime_id"])), None)
        if target:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for i, q in enumerate(target["qismlar"]):
                if "linkvideo" in q:
                    markup.add(types.InlineKeyboardButton(f"❌ {q['nom']}", callback_data=f"del_dir_{udata['anime_id']}_{i}"))
            markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="manage_direct_links"))
            bot.edit_message_text(f"{target['title']} qismlari:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("del_dir_"):
        _, _, a_id, idx = call.data.split("_")
        idx = int(idx)
        for a in data_list:
            if str(a["id"]) == str(a_id):
                a["qismlar"].pop(idx)
                break
        save_github(repo, contents, FILE_PATH, data_list)
        bot.answer_callback_query(call.id, "O'chirildi!")
        # Menuni yangilash uchun qayta chaqiramiz
        call.data = f"man_dir_{a_id}"
        callback_query(call)

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

    elif call.data.startswith("direkt_"):
        udata["exists"] = True
        udata["anime_id"] = call.data.split("_")[1]
        udata["temp_links"] = []
        target = next((a for a in data_list if str(a["id"]) == str(udata["anime_id"])), None)
        current_count = len(target["qismlar"]) if target else 0
        msg = bot.send_message(call.message.chat.id, f"Bu animeda {current_count} ta qism bor.\n\nYangi qismlar nechanchidan boshlab raqamlansin? (Masalan: {current_count + 1})")
        bot.register_next_step_handler(msg, set_start_direct_index)

    elif call.data.startswith("shortona_"):
        udata["short_ona_id"] = call.data.split("_")[1]
        for a in data_list:
            if str(a["id"]) == str(udata["short_ona_id"]):
                udata["short_ona_name"] = re.sub(r",\{.*?\}", "", a["title"]).split("📽")[0].strip()
                break
        udata["short_list"] = []
        msg = bot.send_message(call.message.chat.id, f"🎬 {udata['short_ona_name']} uchun shorts yuboring (Fayl yoki Insta/YT link).\n\nTugatgach /boldi deb yozing:")
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
        udata["edit_id"] = call.data.split("_")[1]
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

    elif call.data == "new_anime":
        udata["exists"] = False
        udata["genre"] = []
        udata["fullnews"] = ""
        msg = bot.send_message(call.message.chat.id, "Anime nomini kiriting:")
        bot.register_next_step_handler(msg, get_new_title)

    elif call.data.startswith("select_genre_"):
        g_name = call.data.replace("select_genre_", "")
        if g_name in udata["genre"]: udata["genre"].remove(g_name)
        else: udata["genre"].append(g_name)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=genre_keyboard(udata["genre"]))

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
        udata["exists"] = True
        udata["anime_id"] = call.data.split("_")[1]
        udata["temp_videos"] = []
        target = next((a for a in data_list if str(a["id"]) == str(udata["anime_id"])), None)
        current_count = len(target["qismlar"]) if target else 0
        msg = bot.send_message(call.message.chat.id, f"Bu animeda {current_count} ta qism bor.\n\nYangi qismlar nechanchidan boshlab raqamlansin? (Masalan: {current_count + 1})")
        bot.register_next_step_handler(msg, set_start_episode_index)

# --- DIREKT LINK FUNKSIYALARI ---
def set_start_direct_index(message):
    udata = get_user_step_data(message.from_user.id)
    try:
        udata["manual_start_index"] = int(message.text)
        bot.send_message(message.chat.id, "Xabarlarni tashlang. 'WATCH :' yonidagi linklar olinadi. /boldi deb yakunlang.")
        bot.register_next_step_handler(message, collect_direct_links_multi)
    except:
        bot.send_message(message.chat.id, "Faqat son kiriting!")
        bot.register_next_step_handler(message, set_start_direct_index)

def collect_direct_links_multi(message):
    udata = get_user_step_data(message.from_user.id)
    if message.text == "/boldi":
        if not udata.get("temp_links"):
            bot.send_message(message.chat.id, "Link topilmadi!")
            return
        finalize_direct_upload(message)
        return
    if message.text:
        found = re.findall(r"WATCH\s*:\s*(https?://[^\s\n]+)", message.text)
        if found:
            udata.setdefault("temp_links", []).extend(found)
            bot.send_message(message.chat.id, f"✅ {len(found)} ta link qo'shildi.")
    bot.register_next_step_handler(message, collect_direct_links_multi)

def finalize_direct_upload(message):
    user_id = message.from_user.id
    udata = get_user_step_data(user_id)
    repo = g.get_repo(REPO_NAME)
    anim_data, anim_contents = get_github_content(FILE_PATH)
    
    start_ep = udata.get("manual_start_index", 1)
    new_qismlar = []

    for i, link in enumerate(udata["temp_links"]):
        ep_nom = f"{start_ep + i}-qism"
        r_key = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        new_qismlar.append({
            "nom": ep_nom, 
            "linkvideo": link.strip(),
            "link": f"https://t.me/{bot.get_me().username}?start={r_key}"
        })

    for a in anim_data:
        if str(a["id"]) == str(udata["anime_id"]):
            a["qismlar"].extend(new_qismlar)
            break
    
    save_github(repo, anim_contents, FILE_PATH, anim_data)
    bot.send_message(message.chat.id, "✅ Direkt qismlar yangi formatda saqlandi!", reply_markup=admin_menu())

# --- JSON BULK UPLOAD ---
def process_direct_json_input(message):
    try:
        udata = get_user_step_data(message.from_user.id)
        udata["bulk_json"] = json.loads(message.text)
        udata["bulk_links"] = []
        bot.send_message(message.chat.id, "JSON qabul qilindi. Endi barcha linklarni ketma-ket yuboring va /boldi deb yozing.")
        bot.register_next_step_handler(message, collect_bulk_links)
    except:
        bot.send_message(message.chat.id, "Xato! JSON formatini tekshiring.")

def collect_bulk_links(message):
    udata = get_user_step_data(message.from_user.id)
    if message.text == "/boldi":
        finalize_bulk_direct(message)
        return
    if message.text:
        found = re.findall(r"WATCH\s*:\s*(https?://[^\s\n]+)", message.text)
        if found:
            udata["bulk_links"].extend(found)
            bot.send_message(message.chat.id, f"✅ {len(found)} ta qo'shildi. Jami: {len(udata['bulk_links'])}")
    bot.register_next_step_handler(message, collect_bulk_links)

def finalize_bulk_direct(message):
    udata = get_user_step_data(message.from_user.id)
    repo = g.get_repo(REPO_NAME)
    anim_data, anim_contents = get_github_content(FILE_PATH)
    
    links = udata["bulk_links"]
    link_idx = 0
    
    for anime_name, count_list in udata["bulk_json"].items():
        count = count_list[0]
        current_links = links[link_idx:link_idx + count]
        link_idx += count
        
        target = None
        for a in anim_data:
            if anime_name.lower() in a["title"].lower():
                target = a
                break
        
        if target:
            # Mavjud bo'lsa qismlarni linkvideo bilan yangilaydi yoki qo'shadi
            for i, l in enumerate(current_links):
                ep_nom = f"{len(target['qismlar']) + 1}-qism"
                r_key = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
                target["qismlar"].append({
                    "nom": ep_nom,
                    "linkvideo": l,
                    "link": f"https://t.me/{bot.get_me().username}?start={r_key}"
                })
    
    save_github(repo, anim_contents, FILE_PATH, anim_data)
    bot.send_message(message.chat.id, "✅ Ommaviy yuklash yakunlandi!", reply_markup=admin_menu())

# --- QOLGAN FUNKSIYALAR ---
def set_start_episode_index(message):
    udata = get_user_step_data(message.from_user.id)
    try:
        udata["manual_start_index"] = int(message.text)
        bot.send_message(message.chat.id, f"Tushunarli! Qismlar {udata['manual_start_index']}-qismdan boshlab raqamlanadi. Videolarni yuboring va /boldi deb yozing.")
        bot.register_next_step_handler(message, collect_multi_videos)
    except:
        bot.send_message(message.chat.id, "Faqat son kiriting!")
        bot.register_next_step_handler(message, set_start_episode_index)

def update_web_settings(message):
    repo = g.get_repo(REPO_NAME)
    web_data, web_contents = get_github_content(WEB_SETTINGS_PATH)
    if message.photo:
        link = upload_to_imgbb(message)
        if link: web_data["logo"] = link
    elif message.text:
        web_data["name"] = message.text
    save_github(repo, web_contents, WEB_SETTINGS_PATH, web_data)
    bot.send_message(message.chat.id, "✅ Sozlamalar yangilandi!", reply_markup=admin_menu())

def collect_shorts_multi(message):
    user_id = message.from_user.id
    udata = get_user_step_data(user_id)
    if message.text == "/boldi":
        if not udata.get("short_list"):
            bot.send_message(message.chat.id, "Hech narsa yubormadingiz!")
            return
        finalize_shorts_upload(message)
        return

    if message.video or message.document:
        file_id = message.video.file_id if message.video else message.document.file_id
        bot.send_message(message.chat.id, "⏳ Video Wistiaga yuklanmoqda...")
        file_info = bot.get_file(file_id)
        file_bytes = bot.download_file(file_info.file_path)
        hashed_id = upload_video_to_wistia(file_bytes)
        if hashed_id:
            udata["short_list"].append(hashed_id)
            bot.send_message(message.chat.id, f"✅ Fayl yuklandi. Jami: {len(udata['short_list'])}")
        else:
            bot.send_message(message.chat.id, "❌ Wistia yuklashda xato.")

    elif message.text and message.text.startswith("http"):
        links = [l.strip() for l in message.text.split(",")]
        for link in links:
            bot.send_message(message.chat.id, f"⏳ {link} yuklanmoqda...")
            video_bytes = download_from_link(link)
            if video_bytes:
                hashed_id = upload_video_to_wistia(video_bytes)
                if hashed_id:
                    udata["short_list"].append(hashed_id)
                    bot.send_message(message.chat.id, f"✅ Muvaffaqiyatli: {link}")
        bot.send_message(message.chat.id, f"Jami: {len(udata['short_list'])} ta shorts.")

    bot.register_next_step_handler(message, collect_shorts_multi)

def download_from_link(link):
    try:
        ydl_opts = {'format': 'best', 'outtmpl': 'temp_video.mp4', 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])
        with open('temp_video.mp4', 'rb') as f:
            data = f.read()
        os.remove('temp_video.mp4')
        return data
    except: return None

def upload_video_to_wistia(file_bytes):
    try:
        url = "https://upload.wistia.com/"
        params = {"api_password": WISTIA_API_KEY}
        files = {"file": (f"short_{int(time.time())}.mp4", file_bytes, "video/mp4")}
        res = requests.post(url, params=params, files=files)
        if res.status_code == 200: return res.json()["hashed_id"]
    except: pass
    return None

def finalize_shorts_upload(message):
    user_id = message.from_user.id
    udata = get_user_step_data(user_id)
    repo = g.get_repo(REPO_NAME)
    shorts_data, shorts_contents = get_github_content(SHORT_PATH)
    
    for item in udata["short_list"]:
        shorts_data.append({
            "nom": udata["short_ona_name"],
            "link": item,
            "ona": udata["short_ona_id"]
        })
    
    save_github(repo, shorts_contents, SHORT_PATH, shorts_data)
    bot.send_message(message.chat.id, f"✅ {len(udata['short_list'])} ta shorts muvaffaqiyatli saqlandi!", reply_markup=admin_menu())

def get_new_title(message):
    udata = get_user_step_data(message.from_user.id)
    udata["title"] = message.text
    msg = bot.send_message(message.chat.id, "Anime bosh posterini yuboring:")
    bot.register_next_step_handler(msg, get_poster_initial)

def get_poster_initial(message):
    udata = get_user_step_data(message.from_user.id)
    udata["thumb"] = upload_to_imgbb(message) or message.text
    bot.send_message(message.chat.id, "Janrlarni tanlang:", reply_markup=genre_keyboard(udata["genre"]))

def get_ai_result(message):
    udata = get_user_step_data(message.from_user.id)
    pic = upload_to_imgbb(message)
    if pic:
        bot.send_message(message.chat.id, "AI qidirmoqda...")
        orig_name, full_info = get_full_anime_info(pic)
        if orig_name:
            udata["title"] = f"{udata['title']} 📽 | {orig_name}"
            udata["fullnews"] = full_info
            bot.send_message(message.chat.id, f"✅ Ma'lumotlar olindi!")
    ask_title_sticker(message)

def ask_title_sticker(message):
    udata = get_user_step_data(message.from_user.id)
    search_q = udata["title"].split('📽')[0].strip().replace(" ", "-")
    tenor_url = f"https://tenor.com/search/{search_q}-gifs"
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🎨 GIF tanlash", url=tenor_url))
    msg = bot.send_message(message.chat.id, "Title linkini yuboring:", reply_markup=markup)
    bot.register_next_step_handler(msg, finalize_title_with_sticker)

def finalize_title_with_sticker(message):
    udata = get_user_step_data(message.from_user.id)
    link = upload_to_imgbb(message)
    if link: udata["title"] = f"{udata['title']} ,{{{link}}}"
    udata["temp_videos"] = []
    udata["manual_start_index"] = 1
    bot.send_message(message.chat.id, "Videolarni yuboring va /boldi deb yozing.")
    bot.register_next_step_handler(message, collect_multi_videos)

def collect_multi_videos(message):
    udata = get_user_step_data(message.from_user.id)
    if message.text == "/boldi":
        if not udata.get("temp_videos"):
            bot.send_message(message.chat.id, "Video yubormadingiz!")
            return
        finalize_multi_upload(message)
        return
    if message.video or message.document:
        vid = message.video.file_id if message.video else message.document.file_id
        udata["temp_videos"].append(vid)
        bot.send_message(message.chat.id, f"📥 {len(udata['temp_videos'])}-qabul qilindi.")
    bot.register_next_step_handler(message, collect_multi_videos)

def finalize_multi_upload(message):
    user_id = message.from_user.id
    udata = get_user_step_data(user_id)
    repo = g.get_repo(REPO_NAME)
    db_data, db_contents = get_github_content(ANIMEID_PATH)
    anim_data, anim_contents = get_github_content(FILE_PATH)
    
    new_qismlar = []
    start_ep = udata.get("manual_start_index", 1)

    for i, vid in enumerate(udata["temp_videos"]):
        r_key = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        db_data[r_key] = vid
        random_map[r_key] = vid
        ep_nom = f"{start_ep + i}-qism"
        new_qismlar.append({"nom": ep_nom, "link": f"https://t.me/{bot.get_me().username}?start={r_key}"})

    if udata.get("exists"):
        for a in anim_data:
            if str(a["id"]) == str(udata["anime_id"]):
                a["qismlar"].extend(new_qismlar)
                current_anime = a
                break
    else:
        a_id = f"a{int(time.time())}"
        current_anime = {
            "id": a_id, "title": udata["title"], "thumb": udata["thumb"], 
            "turkum": udata["genre"], "fullnews": udata.get("fullnews", ""),
            "qismlar": new_qismlar
        }
        anim_data.append(current_anime)

    save_github(repo, db_contents, ANIMEID_PATH, db_data)
    save_github(repo, anim_contents, FILE_PATH, anim_data)

    clean_title = re.sub(r",\{.*?\}", "", current_anime["title"]).split("📽")[0].strip()
    caption = f"➤🎬 Nomi: {clean_title}\n➤🎥 Qismlar: {len(current_anime['qismlar'])}\n➤🎞 Janri: {', '.join(current_anime['turkum'])}\n\n{current_anime.get('fullnews', '')}"
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📺 Tomosha qilish", url=f"https://t.me/{bot.get_me().username}/link?startapp={current_anime['id']}"))
    
    try: bot.send_photo(POST_CHANNEL_ID, current_anime["thumb"], caption=caption, reply_markup=markup)
    except: bot.send_message(POST_CHANNEL_ID, caption, reply_markup=markup)
    
    bot.send_message(message.chat.id, "✅ Bajarildi!", reply_markup=main_menu())

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
                if anime["thumb"].startswith("http"): bot.send_photo(message.chat.id, anime["thumb"], caption=caption, reply_markup=markup)
                else: bot.send_message(message.chat.id, caption, reply_markup=markup)
                return

    if message.text == "📺 Anime ko'rish": 
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🚀 Ilovani ochish", web_app=types.WebAppInfo(MINI_APP_URL)))
        bot.send_message(message.chat.id, "Mini Appni ochish:", reply_markup=markup)

load_all_ids()
bot.infinity_polling()
