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

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN")
GH_TOKEN = os.getenv("GH_TOKEN")
REPO_NAME = "UPL-ANIME/annn"
FILE_PATH = "anim.json"
ANIMEID_PATH = "animeid.json"
CHANNELS_PATH = "channels.json"
ADMINS_PATH = "admins.json" # Adminlar ro'yxati uchun fayl
ADMIN_ID = 5297746319
MINI_APP_URL = "https://upl-anime.github.io/TGteganime/"
IMGBB_API_KEY = "4370f5ebb3ad2302e03c1638b2ccb8c2"
POST_CHANNEL_ID = "@uzbekchaanimelarafna"

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

def find_original_name(image_url):
    try:
        res = requests.get(f"https://api.trace.moe/search?url={image_url}")
        data = res.json()
        if data['result']:
            filename = data['result'][0]['filename']
            clean_name = re.sub(r'\[.*?\]|\.mp4|\.mkv|\d+|\(.*?\)|_', ' ', filename).strip()
            return clean_name
    except:
        return None
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
        file_id = random_map.get(text[1])
        if file_id:
            try: bot.send_video(message.chat.id, file_id)
            except: bot.send_document(message.chat.id, file_id)
        return
    bot.send_message(message.chat.id, "Xush kelibsiz!", reply_markup=main_menu())

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Admin panelga xush kelibsiz:", reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, "Siz admin emassiz!")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    global last_sticker_link
    
    # --- Antiflood (Tugmani ko'p bosishdan himoya) ---
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
                bot.send_message(call.message.chat.id, "Xush kelibsiz!", reply_markup=main_menu())
            else:
                bot.send_message(call.message.chat.id, "Obuna tasdiqlandi!", reply_markup=main_menu())
        else:
            bot.answer_callback_query(call.id, "Hali hamma kanallarga a'zo emassiz!", show_alert=True)
        return

    if not is_admin(call.from_user.id): return
    
    data_list, contents = get_github_content(FILE_PATH)
    if not isinstance(data_list, list): data_list = []
    
    if call.data == "back_to_admin":
        bot.edit_message_text("Admin panel", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

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

    elif call.data.startswith("del_adm_"):
        target_adm = int(call.data.replace("del_adm_", ""))
        admins, adm_contents = get_github_content(ADMINS_PATH)
        if target_adm in admins:
            admins.remove(target_adm)
            save_github(repo, adm_contents, ADMINS_PATH, admins)
            bot.answer_callback_query(call.id, "Admin o'chirildi")
            bot.edit_message_text("Admin o'chirildi. Panelni yangilang.", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

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

    elif call.data == "manage_sub_channels":
        sub_data, _ = get_github_content(CHANNELS_PATH)
        markup = types.InlineKeyboardMarkup(row_width=1)
        for ch in sub_data.get("tg", []):
            markup.add(types.InlineKeyboardButton(f"❌ {ch}", callback_data=f"remove_tg_{ch}"))
        markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="sub_settings"))
        bot.edit_message_text("O'chirish uchun kanalni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("remove_tg_"):
        target = call.data.replace("remove_tg_", "")
        sub_data, sub_contents = get_github_content(CHANNELS_PATH)
        if target in sub_data["tg"]:
            sub_data["tg"].remove(target)
            save_github(repo, sub_contents, CHANNELS_PATH, sub_data)
            bot.answer_callback_query(call.id, f"{target} o'chirildi")
            bot.edit_message_text("Kanal o'chirildi.", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

    elif call.data == "add_tg":
        msg = bot.send_message(call.message.chat.id, "Kanal userneymini yuboring (masalan: @afnacodercpy):")
        bot.register_next_step_handler(msg, save_new_tg)

    elif call.data == "set_insta":
        msg = bot.send_message(call.message.chat.id, "Instagram profil linkini yuboring:")
        bot.register_next_step_handler(msg, save_insta_link)

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
            types.InlineKeyboardButton("❌ Animeni o'chirish", callback_data="del_anime"),
            types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin")
        )
        bot.edit_message_text("Taxrir bo'limi", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "del_anime":
        new_data = [a for a in data_list if str(a["id"]) != str(user_data["edit_id"])]
        save_github(repo, contents, FILE_PATH, new_data)
        bot.send_message(call.message.chat.id, "✅ Muvaffaqiyatli o'chirildi.", reply_markup=admin_menu())

    elif call.data == "manage_eps":
        anime = next(a for a in data_list if str(a["id"]) == str(user_data["edit_id"]))
        markup = types.InlineKeyboardMarkup(row_width=1)
        for i, ep in enumerate(anime["qismlar"]):
            markup.add(types.InlineKeyboardButton(f"🗑 {ep['nom']}", callback_data=f"delep_{i}"))
        markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data=f"edit_{user_data['edit_id']}"))
        bot.edit_message_text("O'chirish uchun qismni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("delep_"):
        ep_idx = int(call.data.split("_")[1])
        for anime in data_list:
            if str(anime["id"]) == str(user_data["edit_id"]): 
                anime["qismlar"].pop(ep_idx)
                break
        save_github(repo, contents, FILE_PATH, data_list)
        bot.send_message(call.message.chat.id, "✅ Qism o'chirildi", reply_markup=admin_menu())

    elif call.data == "new_anime":
        user_data["exists"] = False
        user_data["genre"] = []
        msg = bot.send_message(call.message.chat.id, "Anime nomini kiriting:")
        bot.register_next_step_handler(msg, get_new_title)

    elif call.data.startswith("select_genre_"):
        g_name = call.data.replace("select_genre_", "")
        if "genre" not in user_data: user_data["genre"] = []
        if g_name in user_data["genre"]: user_data["genre"].remove(g_name)
        else: user_data["genre"].append(g_name)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=genre_keyboard(user_data["genre"]))

    elif call.data == "confirm_genres":
        if not user_data.get("genre"): return bot.answer_callback_query(call.id, "Janr tanlang!")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔍 qidirish", callback_data="ai_search_start"),
                   types.InlineKeyboardButton("⏭", callback_data="ai_search_skip"))
        bot.send_message(call.message.chat.id, "Ai uchun rasm kiriting ?", reply_markup=markup)

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

    elif call.data == "use_sticker_link":
        if last_sticker_link:
            user_data["title"] = f"{user_data['title']} ,{{{last_sticker_link}}}"
            bot.send_message(call.message.chat.id, "✅ Saqlangan rasm/link titlega qo'shildi.")
            user_data["temp_videos"] = []
            bot.send_message(call.message.chat.id, "Videolarni yuboring va /boldi deb yozing.")
            bot.register_next_step_handler(call.message, collect_multi_videos)

    elif call.data == "editname":
        msg = bot.send_message(call.message.chat.id, "Yangi nomni kiriting:")
        bot.register_next_step_handler(msg, update_anime_field, "title", data_list, repo, contents)

    elif call.data == "editthumb":
        msg = bot.send_message(call.message.chat.id, "Yangi poster yuboring:")
        bot.register_next_step_handler(msg, update_anime_field, "thumb", data_list, repo, contents)

    elif call.data == "edittitlerasmi":
        msg = bot.send_message(call.message.chat.id, "Yangi Title rasmini yuboring (linkga aylantiriladi):")
        bot.register_next_step_handler(msg, update_title_sticker, data_list, repo, contents)

# --- ADMIN QO'SHIMCHA FUNKSIYALAR ---
def save_admin_id(message):
    try:
        new_id = int(message.text)
        repo = g.get_repo(REPO_NAME)
        admins, adm_contents = get_github_content(ADMINS_PATH)
        if new_id not in admins:
            admins.append(new_id)
            save_github(repo, adm_contents, ADMINS_PATH, admins)
            bot.send_message(message.chat.id, f"✅ {new_id} admin etib tayinlandi!", reply_markup=admin_menu())
        else:
            bot.send_message(message.chat.id, "Ushbu ID allaqachon admin!")
    except:
        bot.send_message(message.chat.id, "ID faqat raqamlardan iborat bo'lishi kerak!")

def save_new_tg(message):
    if not message.text.startswith("@"):
        bot.send_message(message.chat.id, "❌ Xato! @ bilan boshlang.")
        return
    repo = g.get_repo(REPO_NAME)
    sub_data, sub_contents = get_github_content(CHANNELS_PATH)
    if message.text not in sub_data["tg"]:
        sub_data["tg"].append(message.text)
        save_github(repo, sub_contents, CHANNELS_PATH, sub_data)
        bot.send_message(message.chat.id, "✅ Kanal qo'shildi!", reply_markup=admin_menu())

def save_insta_link(message):
    repo = g.get_repo(REPO_NAME)
    sub_data, sub_contents = get_github_content(CHANNELS_PATH)
    sub_data["insta"] = message.text
    save_github(repo, sub_contents, CHANNELS_PATH, sub_data)
    bot.send_message(message.chat.id, "✅ Instagram link saqlandi!", reply_markup=admin_menu())

# --- QADAMMA-QADAM MANTIQ ---
def get_new_title(message):
    user_data["title"] = message.text
    msg = bot.send_message(message.chat.id, "Anime bosh posterini (Mini App uchun) yuboring:")
    bot.register_next_step_handler(msg, get_poster_initial)

def get_poster_initial(message):
    pic = upload_to_imgbb(message)
    user_data["thumb"] = pic if pic else message.text
    bot.send_message(message.chat.id, "Janrlarni tanlang:", reply_markup=genre_keyboard())

def get_ai_result(message):
    pic = upload_to_imgbb(message)
    if pic:
        bot.send_message(message.chat.id, "Qidirilmoqda...")
        orig_name = find_original_name(pic)
        if orig_name:
            user_data["title"] = f"{user_data['title']} 📽 | {orig_name}"
            bot.send_message(message.chat.id, f"✅ Topildi: {orig_name}")
    ask_title_sticker(message)

def ask_title_sticker(message):
    global last_sticker_link
    markup = types.InlineKeyboardMarkup()
    if last_sticker_link:
        markup.add(types.InlineKeyboardButton("🖼 Oxirgi link/rasm", callback_data="use_sticker_link"))
    msg = bot.send_message(message.chat.id, "Title ichidagi rasm yuboring yoki link kiriting:", reply_markup=markup)
    bot.register_next_step_handler(msg, finalize_title_with_sticker)

def finalize_title_with_sticker(message):
    global last_sticker_link
    link = upload_to_imgbb(message)
    if link:
        last_sticker_link = link
        user_data["title"] = f"{user_data['title']} ,{{{link}}}"
    user_data["temp_videos"] = []
    bot.send_message(message.chat.id, "Videolarni yuboring va /boldi deb yozing.")
    bot.register_next_step_handler(message, collect_multi_videos)

def collect_multi_videos(message):
    if message.text == "/boldi":
        if not user_data.get("temp_videos") or len(user_data["temp_videos"]) == 0:
            bot.send_message(message.chat.id, "Hech qanday video yubormadingiz! Kamida bitta video yuboring.")
            bot.register_next_step_handler(message, collect_multi_videos)
            return
        user_data["v_idx"] = 0
        user_data["final_eps"] = []
        ask_ep_name_one_by_one(message)
        return
    if message.video or message.document:
        vid = message.video.file_id if message.video else message.document.file_id
        user_data["temp_videos"].append(vid)
        bot.send_message(message.chat.id, f"📥 {len(user_data['temp_videos'])}-video qabul qilindi. Yana yuboring yoki /boldi deng.")
    bot.register_next_step_handler(message, collect_multi_videos)

def ask_ep_name_one_by_one(message):
    idx = user_data["v_idx"]
    bot.send_message(message.chat.id, f"{idx+1}-video uchun qism nomini kiriting:")
    bot.register_next_step_handler(message, save_ep_name_and_next)

def save_ep_name_and_next(message):
    idx = user_data["v_idx"]
    vid = user_data["temp_videos"][idx]
    r_key = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    user_data["final_eps"].append({"nom": message.text, "vid": vid, "key": r_key})
    user_data["v_idx"] += 1
    if user_data["v_idx"] < len(user_data["temp_videos"]):
        ask_ep_name_one_by_one(message)
    else:
        finalize_multi_upload(message)

def finalize_multi_upload(message):
    repo = g.get_repo(REPO_NAME)
    db_data, db_contents = get_github_content(ANIMEID_PATH)
    anim_data, anim_contents = get_github_content(FILE_PATH)
    if db_data is None: db_data = {}
    if anim_data is None: anim_data = []
    new_qismlar = []
    for item in user_data["final_eps"]:
        db_data[item["key"]] = item["vid"]
        link = f"https://t.me/{bot.get_me().username}?start={item['key']}"
        new_qismlar.append({"nom": item["nom"], "link": link})
        random_map[item["key"]] = item["vid"]
    
    if user_data.get("exists"):
        current_anime = None
        for a in anim_data:
            if str(a["id"]) == str(user_data["anime_id"]):
                a["qismlar"].extend(new_qismlar)
                current_anime = a
                break
    else:
        a_id = f"a{int(time.time())}"
        current_anime = {"id": a_id, "title": user_data["title"], "thumb": user_data["thumb"], "turkum": user_data["genre"], "qismlar": new_qismlar}
        anim_data.append(current_anime)

    save_github(repo, db_contents, ANIMEID_PATH, db_data)
    save_github(repo, anim_contents, FILE_PATH, anim_data)

    # --- KANALGA POST YUBORISH ---
    clean_title = re.sub(r",\{.*?\}", "", current_anime["title"]).split("📽")[0].strip()
    genre_str = ", ".join(current_anime["turkum"])
    
    caption = (
        f"➤🎬Nomi: {clean_title}\n\n"
        f"➤🎥 Qismlar soni: {len(current_anime['qismlar'])}\n"
        f"➤🌍 Davlati: Yaponiya\n"
        f"➤🇺🇿 Tili: O'zbek tilida\n"
        f"➤📆 Yili: 2026\n"
        f"➤🎞 Janri: {genre_str}\n\n"
        f"Bot orqali ko'rish uchun pastdagi tugmani bosing 👇"
    )
    
    post_markup = types.InlineKeyboardMarkup()
    app_link = f"https://t.me/animeuzbektilida_afna_robot/link?startapp={current_anime['id']}"
    post_markup.add(types.InlineKeyboardButton("📺 Tomosha qilish (Mini App)", url=app_link))
    
    try:
        if current_anime["thumb"].startswith("http"):
            bot.send_photo(POST_CHANNEL_ID, current_anime["thumb"], caption=caption, reply_markup=post_markup)
        else:
            bot.send_message(POST_CHANNEL_ID, caption, reply_markup=post_markup)
    except Exception as e:
        print(f"Channel Post Error: {e}")

    bot.send_message(message.chat.id, "✅ Jarayon muvaffaqiyatli yakunlandi va kanalga post joylandi!", reply_markup=main_menu())

def update_anime_field(message, field, data_list, repo, contents):
    val = upload_to_imgbb(message) if field == "thumb" else message.text
    for anime in data_list:
        if str(anime["id"]) == str(user_data["edit_id"]): 
            anime[field] = val
            break
    save_github(repo, contents, FILE_PATH, data_list)
    bot.send_message(message.chat.id, "✅ Yangilandi!", reply_markup=admin_menu())

def update_title_sticker(message, data_list, repo, contents):
    link = upload_to_imgbb(message)
    if not link:
        return bot.send_message(message.chat.id, "❌ Rasm yuklanmadi.")
    for anime in data_list:
        if str(anime["id"]) == str(user_data["edit_id"]):
            title = anime["title"]
            if ",{" in title:
                new_title = re.sub(r",\{.*?\}", f",{{{link}}}", title)
            else:
                new_title = f"{title} ,{{{link}}}"
            anime["title"] = new_title
            break
    save_github(repo, contents, FILE_PATH, data_list)
    bot.send_message(message.chat.id, "✅ Title rasmi yangilandi!", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: True)
def text_h(message):
    if not check_subscription(message.from_user.id):
        handle_start(message)
        return

    if message.text == "📺 Anime ko'rish": 
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Ilova", web_app=types.WebAppInfo(MINI_APP_URL)))
        bot.send_message(message.chat.id, "Mini App:", reply_markup=markup)

load_all_ids()
bot.infinity_polling()
