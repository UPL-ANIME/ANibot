import telebot
from telebot import types
import random
import string
import json
import re
import time
from github import Github

# --- KONFIGURATSIYA ---
TOKEN = "YOUR_BOT_TOKEN"
GITHUB_TOKEN = "YOUR_GITHUB_TOKEN"
REPO_NAME = "YOUR_REPO_NAME"
FILE_PATH = "anim.json"
ANIMEID_PATH = "animeid.json"
POST_CHANNEL_ID = -1001234567890 # Kanal ID

bot = telebot.TeleBot(TOKEN)
g = Github(GITHUB_TOKEN)

user_data = {}
random_map = {}

def get_user_step_data(user_id):
    if user_id not in user_data:
        user_data[user_id] = {"temp_videos": []}
    return user_data[user_id]

def get_github_content(path):
    repo = g.get_repo(REPO_NAME)
    contents = repo.get_contents(path)
    return json.loads(contents.decoded_content.decode()), contents

def save_github(repo, contents, path, data):
    repo.update_file(path, f"Update {path}", json.dumps(data, indent=2), contents.sha)

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Anime qo'shish", "Mavjudga qism qo'shish")
    return markup

@bot.message_count_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Salom! Admin panelga xush kelibsiz.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "Anime qo'shish")
def add_anime_start(message):
    uid = message.from_user.id
    user_data[uid] = {"temp_videos": [], "exists": False}
    bot.send_message(uid, "Anime nomini kiriting:")
    bot.register_next_step_handler(message, get_title)

def get_title(message):
    uid = message.from_user.id
    user_data[uid]["title"] = message.text
    bot.send_message(uid, "Poster (thumb) uchun rasm silkasini yuboring:")
    bot.register_next_step_handler(message, get_thumb)

def get_thumb(message):
    uid = message.from_user.id
    user_data[uid]["thumb"] = message.text
    bot.send_message(uid, "Janrlarni kiriting (vergul bilan):")
    bot.register_next_step_handler(message, get_genre)

def get_genre(message):
    uid = message.from_user.id
    user_data[uid]["genre"] = [i.strip() for i in message.text.split(",")]
    bot.send_message(uid, "Anime haqida ma'lumot (fullnews) kiriting:")
    bot.register_next_step_handler(message, get_fullnews)

def get_fullnews(message):
    uid = message.from_user.id
    user_data[uid]["fullnews"] = message.text
    bot.send_message(uid, "Endi videolarni birma-bir yuboring. Tugatish uchun /done buyrug'ini bosing.")
    bot.register_next_step_handler(message, get_videos)

def get_videos(message):
    uid = message.from_user.id
    if message.text == "/done":
        finalize_multi_upload(message)
        return
    if message.text:
        user_data[uid]["temp_videos"].append(message.text)
        bot.send_message(uid, f"{len(user_data[uid]['temp_videos'])} ta video qabul qilindi. Yana yuboring yoki /done bosing.")
        bot.register_next_step_handler(message, get_videos)

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
        # --- ID GENERATSIYA TIZIMI (OXIRGISI + 1) ---
        last_num = 0
        for anime in anim_data:
            a_id = str(anime.get("id", ""))
            if a_id.startswith("a"):
                try:
                    num_part = a_id[1:]
                    if num_part.isdigit():
                        num = int(num_part)
                        if num > last_num and num < 1000000:
                            last_num = num
                except:
                    continue
        
        new_id = f"a{last_num + 1}"
        # --------------------------------------------

        current_anime = {
            "id": new_id, 
            "title": udata["title"], 
            "thumb": udata["thumb"], 
            "turkum": udata["genre"], 
            "fullnews": udata.get("fullnews", ""),
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
    
    bot.send_message(message.chat.id, f"✅ Bajarildi! Yangi anime ID: {current_anime['id']}", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "Mavjudga qism qo'shish")
def update_anime_start(message):
    bot.send_message(message.chat.id, "Anime ID sini kiriting (masalan: a7):")
    bot.register_next_step_handler(message, check_anime_id)

def check_anime_id(message):
    uid = message.from_user.id
    anime_id = message.text
    anim_data, _ = get_github_content(FILE_PATH)
    
    found = False
    for a in anim_data:
        if str(a["id"]) == anime_id:
            user_data[uid] = {
                "anime_id": anime_id, 
                "exists": True, 
                "temp_videos": [], 
                "manual_start_index": len(a["qismlar"]) + 1
            }
            found = True
            break
    
    if found:
        bot.send_message(uid, "Anime topildi. Yangi qismlar videolarini yuboring. Tugatish uchun /done bosing.")
        bot.register_next_step_handler(message, get_videos)
    else:
        bot.send_message(uid, "Bunday ID li anime topilmadi.", reply_markup=main_menu())

bot.polling(none_stop=True)
