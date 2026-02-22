"""
NASA Space Bot — Enhanced Edition
Webhook mode for Render.com

NEW FEATURES:
- 🔔 Notifications: Asteroid Alerts, Meteor Showers, Space Weather, Lunar Calendar, NASA News
- 🪐 Age & Weight on Other Planets
- 🎓 Space Quiz Game (10 questions, scoring)
- 🌌 Cosmic Name Generator
- 🔮 Sci-Fi Horoscope
- ⏳ Space Time Capsule
- 📊 Daily Space Polls
- 🛰 Mars Rover Live Tracker
- 📺 NASA TV & Streams
"""
import os, logging, random, re, requests, asyncio, threading, json, math
from flask import Flask, request
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, ConversationHandler, filters
)

# ── CONFIG ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
NASA_API_KEY   = os.environ.get("NASA_API_KEY", "UXsg0T63ukdHkImo2VAejU46MHdnZdGgtgrlcQmE")
WEBHOOK_URL    = os.environ.get("WEBHOOK_URL", "").rstrip("/")
NASA_BASE      = "https://api.nasa.gov"
PORT           = int(os.environ.get("PORT", 10000))
SUBSCRIBERS_FILE = "subscribers.json"
CAPSULE_FILE     = "capsules.json"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)
tg_app    = None
bot_loop  = None

# ── CONVERSATION STATES ───────────────────────────────────────────────────────
PLANET_DATE, PLANET_WEIGHT = 10, 11
CAPSULE_MSG, CAPSULE_DATE  = 12, 13
HOROSCOPE_BDAY             = 14

# ── SUBSCRIBER STORAGE ────────────────────────────────────────────────────────
def load_subscribers() -> dict:
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"asteroids": [], "meteors": [], "space_weather": [],
            "lunar": [], "nasa_news": [], "nasa_tv": []}

def save_subscribers(data: dict):
    try:
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.error(f"save_subscribers: {e}")

def load_capsules() -> list:
    if os.path.exists(CAPSULE_FILE):
        try:
            with open(CAPSULE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_capsules(data: list):
    try:
        with open(CAPSULE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.error(f"save_capsules: {e}")

# ── TRANSLATIONS ──────────────────────────────────────────────────────────────
CHANNELS_TEXT = {
    "ru": "📢 *Наши каналы*\n\n📡 @your\\_channel\n💬 @your\\_group",
    "en": "📢 *Our Channels*\n\n📡 @your\\_channel\n💬 @your\\_group",
    "he": "📢 *הערוצים שלנו*\n\n📡 @your\\_channel\n💬 @your\\_group",
    "ar": "📢 *قنواتنا*\n\n📡 @your\\_channel\n💬 @your\\_group",
}

T = {
"ru": {
    "choose_lang":"🌍 *Выберите язык / Choose language / בחרו שפה / اختر اللغة*",
    "lang_set":"🇷🇺 Язык: *Русский*",
    "start_msg":"🚀 *NASA Space Bot* — твой проводник во Вселенную, {name}!\n\n*7 категорий, 60+ разделов* 👇",
    "main_menu":"🌠 *Главное меню:*", "choose_sec":"\n\nВыбери раздел 👇",
    "cat_photo":"📸 ФОТО И ГАЛЕРЕЯ", "cat_solarsys":"🪐 СОЛНЕЧНАЯ СИСТЕМА",
    "cat_deepspace":"🌌 ГЛУБОКИЙ КОСМОС", "cat_earth":"🌍 ЗЕМЛЯ И АТМОСФЕРА",
    "cat_science":"🔬 НАУКА И ИСТОРИЯ", "cat_live":"🔴 LIVE — РЕАЛЬНОЕ ВРЕМЯ",
    "cat_interactive":"🎮 ИНТЕРАКТИВ",
    "btn_spacefact":"⭐ Факт о космосе", "btn_channels":"📢 Каналы", "btn_lang":"🌍 Язык",
    "back_menu":"◀️ Главное меню", "back_cat":"◀️ Назад",
    "btn_refresh":"🔄 Обновить", "btn_more_rnd":"🎲 Ещё", "btn_another":"🔄 Ещё снимок", "btn_other_rv":"🔄 Другой",
    "title_photo":"📸 *Фото и галерея*", "title_solarsys":"🪐 *Солнечная система*",
    "title_deepspace":"🌌 *Глубокий космос*", "title_earth":"🌍 *Земля и атмосфера*",
    "title_science":"🔬 *Наука и история*", "title_live":"🔴 *LIVE*",
    "title_interactive":"🎮 *Интерактив*",
    "err":"❌ Ошибка", "no_data":"📭 Нет данных", "no_img":"📭 Снимки недоступны",
    "unknown":"🤔 Используй /start", "hazard_yes":"🔴 ОПАСЕН", "hazard_no":"🟢 Безопасен",
    "iss_map":"🗺 Карта", "iss_no_crew":"Нет данных", "live_nodata":"Нет данных.",
    "moon_phases":["Новолуние","Растущий серп","Первая четверть","Растущая Луна","Полнолуние","Убывающая Луна","Последняя четверть","Убывающий серп"],
    # Existing buttons
    "btn_apod":"🌌 Фото дня","btn_apod_rnd":"🎲 Случайное","btn_gallery":"🖼 Галерея","btn_hubble":"🔬 Хаббл",
    "btn_mars":"🤖 Марс","btn_mars_rv":"🤖 Марсоходы","btn_epic":"🌍 Земля из космоса","btn_earth_night":"🌃 Земля ночью",
    "btn_nebulae":"💫 Туманности","btn_clusters":"✨ Скопления","btn_eclipse":"🌑 Затмения","btn_jwst":"🔭 Джеймс Уэбб",
    "btn_moon_gal":"🖼 Луна","btn_blue_marble":"🌐 Голубой мрамор","btn_spacewalks":"🛸 Выходы",
    "btn_planets":"🪐 Планеты","btn_giants":"🪐 Гиганты","btn_dwarfs":"🪨 Карликовые","btn_moons":"🌙 Спутники",
    "btn_asteroids":"☄️ Астероиды","btn_comets":"☄️ Кометы","btn_moon":"🌑 Фаза Луны","btn_meteors":"🌠 Метеоры",
    "btn_sun":"☀️ Солнце","btn_spaceweather":"🌞 Косм. погода","btn_ceres":"🪨 Церера","btn_pluto":"🔷 Плутон",
    "btn_kuiper":"📦 Пояс Койпера","btn_alignment":"🪐 Парад планет","btn_solar_ecl":"☀️ Затмения","btn_scale":"📏 Масштаб","btn_lunar_miss":"🌙 Лунные миссии",
    "btn_deepspace":"🌌 Глубокий космос","btn_milkyway":"🌌 Млечный Путь","btn_blackholes":"⚫ Чёрные дыры","btn_supernovae":"💥 Сверхновые",
    "btn_pulsars":"💎 Пульсары","btn_nearstars":"⭐ Ближайшие звёзды","btn_exoplanets":"🔭 Экзопланеты","btn_seti":"👽 SETI",
    "btn_gravwaves":"🌊 Гравит. волны","btn_darkmatter":"🌑 Тёмная материя","btn_future":"🔮 Будущее",
    "btn_radioastro":"🔭 Радиоастрономия","btn_quasars":"📡 Квазары","btn_grb":"💥 Гамма-всплески",
    "btn_cmb":"📻 Реликт. излучение","btn_gal_coll":"🌀 Столкн. галактик","btn_starform":"⭐ Рождение звёзд",
    "btn_dark_en":"⚡ Тёмная энергия","btn_cosm_web":"🕸 Косм. паутина","btn_red_giants":"🔴 Красные гиганты",
    "btn_climate":"🌍 Климат","btn_volcanoes":"🌋 Вулканы","btn_hurricanes":"🌀 Ураганы","btn_aurora":"🌈 Сияние",
    "btn_magneto":"🧲 Магнитосфера","btn_satellites":"📡 Спутники","btn_debris":"🛰 Косм. мусор",
    "btn_wildfires":"🔥 Пожары","btn_ice":"🧊 Ледники","btn_deforest":"🌲 Вырубка","btn_nightlights":"🌃 Города ночью",
    "btn_ozone":"🛡 Озон","btn_ocean_temp":"🌡 Океан","btn_ocean_cur":"🌊 Течения","btn_tornadoes":"🌪 Торнадо",
    "btn_launches":"🚀 Запуски","btn_missions":"🛸 Миссии","btn_history":"🚀 История","btn_iss":"🛸 МКС",
    "btn_telescopes":"🔬 Телескопы","btn_sp_stations":"🛸 Станции","btn_moon_sites":"🌙 Места высадки",
    "btn_women":"👩‍🚀 Женщины","btn_mars_col":"🔴 Марс-колонизация","btn_sp_med":"🩺 Медицина",
    "btn_rockets":"🚀 Двигатели","btn_training":"🎓 Подготовка","btn_records":"🏆 Рекорды","btn_food":"🍽 Еда",
    "btn_solar_wind":"🔴 Солнечный ветер","btn_kp":"🔴 Kp-индекс","btn_flares":"🔴 Вспышки",
    "btn_live_iss":"🔴 МКС сейчас","btn_radiation":"🔴 Радиация","btn_aurora_f":"🔴 Прогноз сияний",
    "btn_geomag":"🔴 Геомагн. бури","btn_sunspot":"🔴 Пятна Солнца","btn_live_epic":"🔴 Земля EPIC","btn_sat_count":"🔴 Спутники",
    # NEW buttons
    "btn_notifications":"🔔 Уведомления","btn_planet_calc":"🪐 Возраст на планетах",
    "btn_space_name":"✨ Космическое имя","btn_horoscope":"🔮 Sci-Fi Гороскоп",
    "btn_quiz":"🧠 Космический квиз","btn_capsule":"⏳ Капсула времени",
    "btn_poll":"📊 Опрос дня","btn_mars_live":"🛰 Ровер сейчас",
    "btn_nasa_tv":"📺 NASA TV","btn_lunar_cal":"📆 Лунный календарь",
    # Notifications
    "notif_title":"🔔 *Уведомления*\n\nПодпишись на космические события:",
    "notif_sub_ast":"☄️ Астероидная опасность","notif_sub_meteor":"🌠 Метеорные потоки",
    "notif_sub_sw":"🌞 Косм. погода","notif_sub_lunar":"🌙 Лунный календарь",
    "notif_sub_news":"🔭 Webb/Hubble новости","notif_sub_tv":"📺 NASA TV трансляции",
    "notif_subscribed":"✅ Подписан","notif_unsubscribed":"🔕 Отписан",
    # Planet calculator
    "planet_calc_ask_date":"🪐 *Калькулятор планет*\n\nВведи дату рождения в формате ДД.ММ.ГГГГ\n(например: 15.03.1990):",
    "planet_calc_ask_weight":"⚖️ Отлично! Теперь введи свой вес в кг\n(например: 70):",
    "planet_calc_error_date":"❌ Неверный формат даты. Используй ДД.ММ.ГГГГ",
    "planet_calc_error_weight":"❌ Неверный вес. Введи число от 1 до 500",
    # Quiz
    "quiz_start":"🧠 *Космический квиз*\n\n10 вопросов о Вселенной!\nНажми «Начать» когда будешь готов.",
    "quiz_btn_start":"▶️ Начать квиз","quiz_correct":"✅ Верно!","quiz_wrong":"❌ Неверно!",
    "quiz_result":"🏆 *Результат квиза*\n\nПравильных ответов: *{score}/10*\n\n{grade}",
    "quiz_next":"➡️ Следующий","quiz_finish":"🏁 Завершить",
    # Capsule
    "capsule_ask":"⏳ *Капсула времени*\n\nНапиши сообщение себе в будущее. Мы пришлём его через 1 год!\n\nПросто отправь свой текст:",
    "capsule_saved":"✅ *Капсула времени сохранена!*\n\nМы пришлём твоё сообщение: *{date}*\n\n🚀 Пусть будущее тебя удивит!",
    "capsule_cancel":"❌ Капсула отменена",
    # Name generator
    "name_gen_title":"✨ *Твоё космическое имя*\n\n",
    # Horoscope
    "horoscope_ask":"🔮 Введи дату рождения (ДД.ММ) для Sci-Fi гороскопа:",
    "horoscope_error":"❌ Неверный формат. Используй ДД.ММ",
    # Lunar calendar
    "lunar_cal_title":"📆 *Лунный календарь для фотографов*\n\n",
    # Mars rover
    "mars_rover_title":"🛰 *Ровер сейчас*\n\n",
    # NASA TV
    "nasa_tv_title":"📺 *NASA TV — Трансляции*\n\n🔴 *Прямой эфир:*\n[📡 NASA TV Live](https://www.nasa.gov/nasatv)\n[▶️ YouTube](https://www.youtube.com/nasagov)\n\n🎬 *Каналы:*\n• NASA TV Public — новости, миссии\n• NASA TV Media — пресс-конференции\n\n📅 *Расписание:* [schedule](https://www.nasa.gov/live)",
},
"en": {
    "choose_lang":"🌍 *Choose language / Выберите язык / בחרו שפה / اختر اللغة*",
    "lang_set":"🇬🇧 Language: *English*",
    "start_msg":"🚀 *NASA Space Bot* — your guide to the Universe, {name}!\n\n*7 categories, 60+ sections* 👇",
    "main_menu":"🌠 *Main Menu:*", "choose_sec":"\n\nChoose section 👇",
    "cat_photo":"📸 PHOTO & GALLERY", "cat_solarsys":"🪐 SOLAR SYSTEM",
    "cat_deepspace":"🌌 DEEP SPACE", "cat_earth":"🌍 EARTH & ATMOSPHERE",
    "cat_science":"🔬 SCIENCE & HISTORY", "cat_live":"🔴 LIVE — REAL TIME",
    "cat_interactive":"🎮 INTERACTIVE",
    "btn_spacefact":"⭐ Space Fact", "btn_channels":"📢 Channels", "btn_lang":"🌍 Language",
    "back_menu":"◀️ Main Menu", "back_cat":"◀️ Back",
    "btn_refresh":"🔄 Refresh", "btn_more_rnd":"🎲 More", "btn_another":"🔄 Another", "btn_other_rv":"🔄 Other Rover",
    "title_photo":"📸 *Photo & Gallery*", "title_solarsys":"🪐 *Solar System*",
    "title_deepspace":"🌌 *Deep Space*", "title_earth":"🌍 *Earth & Atmosphere*",
    "title_science":"🔬 *Science & History*", "title_live":"🔴 *LIVE*",
    "title_interactive":"🎮 *Interactive*",
    "err":"❌ Error", "no_data":"📭 No data", "no_img":"📭 Images unavailable",
    "unknown":"🤔 Use /start", "hazard_yes":"🔴 HAZARDOUS", "hazard_no":"🟢 Safe",
    "iss_map":"🗺 Map", "iss_no_crew":"No data", "live_nodata":"No data.",
    "moon_phases":["New Moon","Waxing Crescent","First Quarter","Waxing Gibbous","Full Moon","Waning Gibbous","Last Quarter","Waning Crescent"],
    "btn_apod":"🌌 Photo of Day","btn_apod_rnd":"🎲 Random","btn_gallery":"🖼 Gallery","btn_hubble":"🔬 Hubble",
    "btn_mars":"🤖 Mars","btn_mars_rv":"🤖 Rovers","btn_epic":"🌍 Earth from Space","btn_earth_night":"🌃 Earth at Night",
    "btn_nebulae":"💫 Nebulae","btn_clusters":"✨ Clusters","btn_eclipse":"🌑 Eclipses","btn_jwst":"🔭 James Webb",
    "btn_moon_gal":"🖼 Moon","btn_blue_marble":"🌐 Blue Marble","btn_spacewalks":"🛸 Spacewalks",
    "btn_planets":"🪐 Planets","btn_giants":"🪐 Giants","btn_dwarfs":"🪨 Dwarfs","btn_moons":"🌙 Moons",
    "btn_asteroids":"☄️ Asteroids","btn_comets":"☄️ Comets","btn_moon":"🌑 Moon Phase","btn_meteors":"🌠 Meteors",
    "btn_sun":"☀️ Sun","btn_spaceweather":"🌞 Space Weather","btn_ceres":"🪨 Ceres","btn_pluto":"🔷 Pluto",
    "btn_kuiper":"📦 Kuiper Belt","btn_alignment":"🪐 Planet Parade","btn_solar_ecl":"☀️ Eclipses","btn_scale":"📏 Scale","btn_lunar_miss":"🌙 Lunar Missions",
    "btn_deepspace":"🌌 Deep Space","btn_milkyway":"🌌 Milky Way","btn_blackholes":"⚫ Black Holes","btn_supernovae":"💥 Supernovae",
    "btn_pulsars":"💎 Pulsars","btn_nearstars":"⭐ Nearest Stars","btn_exoplanets":"🔭 Exoplanets","btn_seti":"👽 SETI",
    "btn_gravwaves":"🌊 Grav. Waves","btn_darkmatter":"🌑 Dark Matter","btn_future":"🔮 Future",
    "btn_radioastro":"🔭 Radio Astro","btn_quasars":"📡 Quasars","btn_grb":"💥 Gamma Bursts",
    "btn_cmb":"📻 CMB","btn_gal_coll":"🌀 Galaxy Collisions","btn_starform":"⭐ Star Formation",
    "btn_dark_en":"⚡ Dark Energy","btn_cosm_web":"🕸 Cosmic Web","btn_red_giants":"🔴 Red Giants",
    "btn_climate":"🌍 Climate","btn_volcanoes":"🌋 Volcanoes","btn_hurricanes":"🌀 Hurricanes","btn_aurora":"🌈 Aurora",
    "btn_magneto":"🧲 Magnetosphere","btn_satellites":"📡 Satellites","btn_debris":"🛰 Debris",
    "btn_wildfires":"🔥 Wildfires","btn_ice":"🧊 Glaciers","btn_deforest":"🌲 Deforestation","btn_nightlights":"🌃 City Lights",
    "btn_ozone":"🛡 Ozone","btn_ocean_temp":"🌡 Ocean Temp","btn_ocean_cur":"🌊 Currents","btn_tornadoes":"🌪 Tornadoes",
    "btn_launches":"🚀 Launches","btn_missions":"🛸 Missions","btn_history":"🚀 History","btn_iss":"🛸 ISS",
    "btn_telescopes":"🔬 Telescopes","btn_sp_stations":"🛸 Stations","btn_moon_sites":"🌙 Landing Sites",
    "btn_women":"👩‍🚀 Women","btn_mars_col":"🔴 Mars Colonization","btn_sp_med":"🩺 Medicine",
    "btn_rockets":"🚀 Engines","btn_training":"🎓 Training","btn_records":"🏆 Records","btn_food":"🍽 Food",
    "btn_solar_wind":"🔴 Solar Wind","btn_kp":"🔴 Kp-index","btn_flares":"🔴 Flares",
    "btn_live_iss":"🔴 ISS Now","btn_radiation":"🔴 Radiation","btn_aurora_f":"🔴 Aurora Forecast",
    "btn_geomag":"🔴 Geomag. Storms","btn_sunspot":"🔴 Sunspots","btn_live_epic":"🔴 Earth EPIC","btn_sat_count":"🔴 Satellites",
    # NEW
    "btn_notifications":"🔔 Notifications","btn_planet_calc":"🪐 Age on Planets",
    "btn_space_name":"✨ Cosmic Name","btn_horoscope":"🔮 Sci-Fi Horoscope",
    "btn_quiz":"🧠 Space Quiz","btn_capsule":"⏳ Time Capsule",
    "btn_poll":"📊 Daily Poll","btn_mars_live":"🛰 Rover Now",
    "btn_nasa_tv":"📺 NASA TV","btn_lunar_cal":"📆 Lunar Calendar",
    "notif_title":"🔔 *Notifications*\n\nSubscribe to space events:",
    "notif_sub_ast":"☄️ Asteroid Alerts","notif_sub_meteor":"🌠 Meteor Showers",
    "notif_sub_sw":"🌞 Space Weather","notif_sub_lunar":"🌙 Lunar Calendar",
    "notif_sub_news":"🔭 Webb/Hubble News","notif_sub_tv":"📺 NASA TV Streams",
    "notif_subscribed":"✅ Subscribed","notif_unsubscribed":"🔕 Unsubscribed",
    "planet_calc_ask_date":"🪐 *Planet Calculator*\n\nEnter your birth date as DD.MM.YYYY\n(e.g. 15.03.1990):",
    "planet_calc_ask_weight":"⚖️ Great! Now enter your weight in kg\n(e.g. 70):",
    "planet_calc_error_date":"❌ Invalid date format. Use DD.MM.YYYY",
    "planet_calc_error_weight":"❌ Invalid weight. Enter a number 1–500",
    "quiz_start":"🧠 *Space Quiz*\n\n10 questions about the Universe!\nPress Start when you're ready.",
    "quiz_btn_start":"▶️ Start Quiz","quiz_correct":"✅ Correct!","quiz_wrong":"❌ Wrong!",
    "quiz_result":"🏆 *Quiz Result*\n\nCorrect answers: *{score}/10*\n\n{grade}",
    "quiz_next":"➡️ Next","quiz_finish":"🏁 Finish",
    "capsule_ask":"⏳ *Time Capsule*\n\nWrite a message to your future self. We'll send it in 1 year!\n\nJust send your text:",
    "capsule_saved":"✅ *Time Capsule saved!*\n\nWe'll send your message on: *{date}*\n\n🚀 May the future surprise you!",
    "capsule_cancel":"❌ Capsule cancelled",
    "name_gen_title":"✨ *Your Cosmic Name*\n\n",
    "horoscope_ask":"🔮 Enter your birth date (DD.MM) for your Sci-Fi horoscope:",
    "horoscope_error":"❌ Invalid format. Use DD.MM",
    "lunar_cal_title":"📆 *Lunar Photographer's Calendar*\n\n",
    "mars_rover_title":"🛰 *Rover Now*\n\n",
    "nasa_tv_title":"📺 *NASA TV — Streams*\n\n🔴 *Live:*\n[📡 NASA TV](https://www.nasa.gov/nasatv)\n[▶️ YouTube](https://www.youtube.com/nasagov)\n\n📅 *Schedule:* [schedule](https://www.nasa.gov/live)",
},
"he": {
    "choose_lang":"🌍 *Выберите язык / Choose language / בחרו שפה / اختر اللغة*",
    "lang_set":"🇮🇱 שפה: *עברית*",
    "start_msg":"🚀 *NASA Space Bot* — המדריך שלך ליקום, {name}!\n\n*7 קטגוריות, 60+ מדורים* 👇",
    "main_menu":"🌠 *תפריט ראשי:*","choose_sec":"\n\nבחר מדור 👇",
    "cat_photo":"📸 תמונות","cat_solarsys":"🪐 מערכת השמש",
    "cat_deepspace":"🌌 חלל עמוק","cat_earth":"🌍 כדור הארץ",
    "cat_science":"🔬 מדע","cat_live":"🔴 LIVE","cat_interactive":"🎮 אינטראקטיב",
    "btn_spacefact":"⭐ עובדה","btn_channels":"📢 ערוצים","btn_lang":"🌍 שפה",
    "back_menu":"◀️ תפריט","back_cat":"◀️ חזרה",
    "btn_refresh":"🔄 רענון","btn_more_rnd":"🎲 עוד","btn_another":"🔄 עוד","btn_other_rv":"🔄 אחר",
    "title_photo":"📸 *תמונות*","title_solarsys":"🪐 *מערכת השמש*",
    "title_deepspace":"🌌 *חלל עמוק*","title_earth":"🌍 *כדור הארץ*",
    "title_science":"🔬 *מדע*","title_live":"🔴 *LIVE*","title_interactive":"🎮 *אינטראקטיב*",
    "err":"❌ שגיאה","no_data":"📭 אין נתונים","no_img":"📭 אין תמונות",
    "unknown":"🤔 /start","hazard_yes":"🔴 מסוכן","hazard_no":"🟢 בטוח",
    "iss_map":"🗺 מפה","iss_no_crew":"אין","live_nodata":"אין נתונים.",
    "moon_phases":["ירח חדש","סהר עולה","רבע ראשון","ירח עולה","ירח מלא","ירח יורד","רבע אחרון","סהר יורד"],
    "btn_apod":"🌌 תמונת יום","btn_apod_rnd":"🎲 אקראית","btn_gallery":"🖼 גלריה","btn_hubble":"🔬 האבל",
    "btn_mars":"🤖 מאדים","btn_mars_rv":"🤖 רובר","btn_epic":"🌍 כדור הארץ","btn_earth_night":"🌃 לילה",
    "btn_nebulae":"💫 ערפיליות","btn_clusters":"✨ אשכולות","btn_eclipse":"🌑 ליקויים","btn_jwst":"🔭 ווב",
    "btn_moon_gal":"🖼 ירח","btn_blue_marble":"🌐 כדור שיש","btn_spacewalks":"🛸 הליכות",
    "btn_planets":"🪐 כוכבים","btn_giants":"🪐 ענקים","btn_dwarfs":"🪨 ננסיים","btn_moons":"🌙 ירחים",
    "btn_asteroids":"☄️ אסטרואידים","btn_comets":"☄️ שביטים","btn_moon":"🌑 ירח","btn_meteors":"🌠 מטאורים",
    "btn_sun":"☀️ שמש","btn_spaceweather":"🌞 מזג","btn_ceres":"🪨 סרס","btn_pluto":"🔷 פלוטו",
    "btn_kuiper":"📦 קויפר","btn_alignment":"🪐 מצעד","btn_solar_ecl":"☀️ ליקוי","btn_scale":"📏 קנה מידה","btn_lunar_miss":"🌙 ירח",
    "btn_deepspace":"🌌 חלל","btn_milkyway":"🌌 שביל החלב","btn_blackholes":"⚫ חורים","btn_supernovae":"💥 סופרנובות",
    "btn_pulsars":"💎 פולסרים","btn_nearstars":"⭐ קרובים","btn_exoplanets":"🔭 אקסופלנטות","btn_seti":"👽 SETI",
    "btn_gravwaves":"🌊 גלי כבידה","btn_darkmatter":"🌑 חומר אפל","btn_future":"🔮 עתיד",
    "btn_radioastro":"🔭 רדיו","btn_quasars":"📡 קווזרים","btn_grb":"💥 גמא",
    "btn_cmb":"📻 רקע","btn_gal_coll":"🌀 התנגשות","btn_starform":"⭐ לידה",
    "btn_dark_en":"⚡ אנרגיה","btn_cosm_web":"🕸 רשת","btn_red_giants":"🔴 ענקים",
    "btn_climate":"🌍 אקלים","btn_volcanoes":"🌋 וולקנים","btn_hurricanes":"🌀 הוריקנים","btn_aurora":"🌈 זוהר",
    "btn_magneto":"🧲 מגנטוספירה","btn_satellites":"📡 לוויינים","btn_debris":"🛰 פסולת",
    "btn_wildfires":"🔥 שרפות","btn_ice":"🧊 קרחונים","btn_deforest":"🌲 כריתה","btn_nightlights":"🌃 אורות",
    "btn_ozone":"🛡 אוזון","btn_ocean_temp":"🌡 אוקיינוס","btn_ocean_cur":"🌊 זרמים","btn_tornadoes":"🌪 טורנדו",
    "btn_launches":"🚀 שיגורים","btn_missions":"🛸 משימות","btn_history":"🚀 היסטוריה","btn_iss":"🛸 ISS",
    "btn_telescopes":"🔬 טלסקופים","btn_sp_stations":"🛸 תחנות","btn_moon_sites":"🌙 נחיתה",
    "btn_women":"👩‍🚀 נשים","btn_mars_col":"🔴 מאדים","btn_sp_med":"🩺 רפואה",
    "btn_rockets":"🚀 מנועים","btn_training":"🎓 אימון","btn_records":"🏆 שיאים","btn_food":"🍽 אוכל",
    "btn_solar_wind":"🔴 רוח","btn_kp":"🔴 Kp","btn_flares":"🔴 להבות",
    "btn_live_iss":"🔴 ISS","btn_radiation":"🔴 קרינה","btn_aurora_f":"🔴 זוהר",
    "btn_geomag":"🔴 סערות","btn_sunspot":"🔴 כתמים","btn_live_epic":"🔴 EPIC","btn_sat_count":"🔴 לוויינים",
    "btn_notifications":"🔔 התראות","btn_planet_calc":"🪐 גיל בכוכבים","btn_space_name":"✨ שם קוסמי",
    "btn_horoscope":"🔮 גורל Sci-Fi","btn_quiz":"🧠 חידון","btn_capsule":"⏳ קפסולת זמן",
    "btn_poll":"📊 סקר","btn_mars_live":"🛰 רובר עכשיו","btn_nasa_tv":"📺 NASA TV","btn_lunar_cal":"📆 לוח ירח",
    "notif_title":"🔔 *התראות*\n\nהירשם לאירועים קוסמיים:",
    "notif_sub_ast":"☄️ אסטרואידים","notif_sub_meteor":"🌠 מטאורים","notif_sub_sw":"🌞 מזג אוויר",
    "notif_sub_lunar":"🌙 לוח ירח","notif_sub_news":"🔭 Webb/Hubble","notif_sub_tv":"📺 NASA TV",
    "notif_subscribed":"✅ רשום","notif_unsubscribed":"🔕 בוטל",
    "planet_calc_ask_date":"🪐 הכנס תאריך לידה DD.MM.YYYY:","planet_calc_ask_weight":"⚖️ הכנס משקל בק\"ג:",
    "planet_calc_error_date":"❌ פורמט שגוי","planet_calc_error_weight":"❌ משקל שגוי",
    "quiz_start":"🧠 *חידון קוסמי*\n\n10 שאלות! לחץ התחל.","quiz_btn_start":"▶️ התחל",
    "quiz_correct":"✅ נכון!","quiz_wrong":"❌ שגוי!",
    "quiz_result":"🏆 *תוצאה*\n\n{score}/10\n\n{grade}","quiz_next":"➡️ הבא","quiz_finish":"🏁 סיום",
    "capsule_ask":"⏳ כתוב הודעה לעצמך בעתיד:","capsule_saved":"✅ נשמר! נשלח: *{date}*","capsule_cancel":"❌ בוטל",
    "name_gen_title":"✨ *השם הקוסמי שלך*\n\n","horoscope_ask":"🔮 הכנס תאריך לידה (DD.MM):",
    "horoscope_error":"❌ פורמט שגוי","lunar_cal_title":"📆 *לוח ירח לצלמים*\n\n",
    "mars_rover_title":"🛰 *רובר עכשיו*\n\n",
    "nasa_tv_title":"📺 *NASA TV*\n\n[📡 Live](https://www.nasa.gov/nasatv)\n[▶️ YouTube](https://www.youtube.com/nasagov)",
},
"ar": {
    "choose_lang":"🌍 *Выберите язык / Choose language / בחרו שפה / اختر اللغة*",
    "lang_set":"🇦🇪 اللغة: *العربية*",
    "start_msg":"🚀 *NASA Space Bot* — دليلك إلى الكون، {name}!\n\n*7 فئات، 60+ قسماً* 👇",
    "main_menu":"🌠 *القائمة الرئيسية:*","choose_sec":"\n\nاختر قسماً 👇",
    "cat_photo":"📸 الصور","cat_solarsys":"🪐 المجموعة الشمسية",
    "cat_deepspace":"🌌 الفضاء العميق","cat_earth":"🌍 الأرض",
    "cat_science":"🔬 العلوم","cat_live":"🔴 مباشر","cat_interactive":"🎮 تفاعلي",
    "btn_spacefact":"⭐ حقيقة","btn_channels":"📢 قنواتنا","btn_lang":"🌍 اللغة",
    "back_menu":"◀️ القائمة","back_cat":"◀️ العودة",
    "btn_refresh":"🔄 تحديث","btn_more_rnd":"🎲 المزيد","btn_another":"🔄 أخرى","btn_other_rv":"🔄 مركبة",
    "title_photo":"📸 *الصور*","title_solarsys":"🪐 *المجموعة الشمسية*",
    "title_deepspace":"🌌 *الفضاء العميق*","title_earth":"🌍 *الأرض*",
    "title_science":"🔬 *العلوم*","title_live":"🔴 *مباشر*","title_interactive":"🎮 *تفاعلي*",
    "err":"❌ خطأ","no_data":"📭 لا بيانات","no_img":"📭 لا صور",
    "unknown":"🤔 /start","hazard_yes":"🔴 خطير","hazard_no":"🟢 آمن",
    "iss_map":"🗺 خريطة","iss_no_crew":"لا بيانات","live_nodata":"لا بيانات.",
    "moon_phases":["محاق","هلال متزايد","تربيع أول","بدر متزايد","بدر","بدر متناقص","تربيع أخير","هلال متناقص"],
    "btn_apod":"🌌 صورة اليوم","btn_apod_rnd":"🎲 عشوائية","btn_gallery":"🖼 صالة","btn_hubble":"🔬 هابل",
    "btn_mars":"🤖 المريخ","btn_mars_rv":"🤖 مركبة","btn_epic":"🌍 الأرض","btn_earth_night":"🌃 ليلاً",
    "btn_nebulae":"💫 سدم","btn_clusters":"✨ مجموعات","btn_eclipse":"🌑 كسوف","btn_jwst":"🔭 ويب",
    "btn_moon_gal":"🖼 القمر","btn_blue_marble":"🌐 كرة المرمر","btn_spacewalks":"🛸 تمشية",
    "btn_planets":"🪐 كواكب","btn_giants":"🪐 عمالقة","btn_dwarfs":"🪨 قزمة","btn_moons":"🌙 أقمار",
    "btn_asteroids":"☄️ كويكبات","btn_comets":"☄️ مذنبات","btn_moon":"🌑 القمر","btn_meteors":"🌠 شهب",
    "btn_sun":"☀️ الشمس","btn_spaceweather":"🌞 طقس","btn_ceres":"🪨 سيريس","btn_pluto":"🔷 بلوتو",
    "btn_kuiper":"📦 كويبر","btn_alignment":"🪐 استعراض","btn_solar_ecl":"☀️ كسوف","btn_scale":"📏 مقياس","btn_lunar_miss":"🌙 مهمات",
    "btn_deepspace":"🌌 فضاء","btn_milkyway":"🌌 درب التبانة","btn_blackholes":"⚫ ثقوب","btn_supernovae":"💥 مستعرات",
    "btn_pulsars":"💎 نابضة","btn_nearstars":"⭐ نجوم","btn_exoplanets":"🔭 خارجية","btn_seti":"👽 SETI",
    "btn_gravwaves":"🌊 جاذبية","btn_darkmatter":"🌑 مظلمة","btn_future":"🔮 مستقبل",
    "btn_radioastro":"🔭 راديو","btn_quasars":"📡 كوازارات","btn_grb":"💥 غاما",
    "btn_cmb":"📻 خلفية","btn_gal_coll":"🌀 تصادم","btn_starform":"⭐ تشكّل",
    "btn_dark_en":"⚡ طاقة","btn_cosm_web":"🕸 شبكة","btn_red_giants":"🔴 عمالقة",
    "btn_climate":"🌍 مناخ","btn_volcanoes":"🌋 براكين","btn_hurricanes":"🌀 أعاصير","btn_aurora":"🌈 شفق",
    "btn_magneto":"🧲 مغناطيسي","btn_satellites":"📡 أقمار","btn_debris":"🛰 حطام",
    "btn_wildfires":"🔥 حرائق","btn_ice":"🧊 جليد","btn_deforest":"🌲 غابات","btn_nightlights":"🌃 أضواء",
    "btn_ozone":"🛡 أوزون","btn_ocean_temp":"🌡 محيط","btn_ocean_cur":"🌊 تيارات","btn_tornadoes":"🌪 أعاصير",
    "btn_launches":"🚀 إطلاقات","btn_missions":"🛸 مهمات","btn_history":"🚀 تاريخ","btn_iss":"🛸 محطة",
    "btn_telescopes":"🔬 تلسكوبات","btn_sp_stations":"🛸 محطات","btn_moon_sites":"🌙 هبوط",
    "btn_women":"👩‍🚀 نساء","btn_mars_col":"🔴 استعمار","btn_sp_med":"🩺 طب",
    "btn_rockets":"🚀 محركات","btn_training":"🎓 تدريب","btn_records":"🏆 أرقام","btn_food":"🍽 طعام",
    "btn_solar_wind":"🔴 رياح","btn_kp":"🔴 Kp","btn_flares":"🔴 توهجات",
    "btn_live_iss":"🔴 محطة","btn_radiation":"🔴 إشعاع","btn_aurora_f":"🔴 شفق",
    "btn_geomag":"🔴 عواصف","btn_sunspot":"🔴 بقع","btn_live_epic":"🔴 EPIC","btn_sat_count":"🔴 أقمار",
    "btn_notifications":"🔔 إشعارات","btn_planet_calc":"🪐 عمرك على الكواكب","btn_space_name":"✨ اسمك الكوني",
    "btn_horoscope":"🔮 توقعات Sci-Fi","btn_quiz":"🧠 مسابقة","btn_capsule":"⏳ كبسولة الزمن",
    "btn_poll":"📊 استطلاع","btn_mars_live":"🛰 المركبة الآن","btn_nasa_tv":"📺 NASA TV","btn_lunar_cal":"📆 تقويم القمر",
    "notif_title":"🔔 *الإشعارات*\n\nاشترك في أحداث الفضاء:","notif_sub_ast":"☄️ تحذيرات الكويكبات",
    "notif_sub_meteor":"🌠 الشهب","notif_sub_sw":"🌞 الطقس الفضائي","notif_sub_lunar":"🌙 تقويم القمر",
    "notif_sub_news":"🔭 أخبار Webb/Hubble","notif_sub_tv":"📺 NASA TV",
    "notif_subscribed":"✅ تم الاشتراك","notif_unsubscribed":"🔕 تم الإلغاء",
    "planet_calc_ask_date":"🪐 أدخل تاريخ ميلادك DD.MM.YYYY:","planet_calc_ask_weight":"⚖️ أدخل وزنك بالكيلوغرام:",
    "planet_calc_error_date":"❌ تنسيق خاطئ","planet_calc_error_weight":"❌ وزن خاطئ",
    "quiz_start":"🧠 *مسابقة الفضاء*\n\n10 أسئلة! اضغط ابدأ.","quiz_btn_start":"▶️ ابدأ",
    "quiz_correct":"✅ صحيح!","quiz_wrong":"❌ خطأ!",
    "quiz_result":"🏆 *النتيجة*\n\n{score}/10\n\n{grade}","quiz_next":"➡️ التالي","quiz_finish":"🏁 إنهاء",
    "capsule_ask":"⏳ اكتب رسالة لنفسك في المستقبل:","capsule_saved":"✅ تم الحفظ! سيُرسل: *{date}*","capsule_cancel":"❌ ملغى",
    "name_gen_title":"✨ *اسمك الكوني*\n\n","horoscope_ask":"🔮 أدخل تاريخ ميلادك (DD.MM):",
    "horoscope_error":"❌ تنسيق خاطئ","lunar_cal_title":"📆 *تقويم القمر للمصورين*\n\n",
    "mars_rover_title":"🛰 *المركبة الآن*\n\n",
    "nasa_tv_title":"📺 *NASA TV*\n\n[📡 Live](https://www.nasa.gov/nasatv)\n[▶️ YouTube](https://www.youtube.com/nasagov)",
},
}

def tx(lang, key, **kw):
    val = T.get(lang, T["en"]).get(key) or T["en"].get(key) or key
    return val.format(**kw) if kw else val

def get_lang(ctx): return ctx.user_data.get("lang", "ru")
def strip_html(t): return re.sub(r'<[^>]+>', '', t or '')

# ── NASA API HELPERS ──────────────────────────────────────────────────────────
def nasa_req(path, params=None):
    p = {"api_key": NASA_API_KEY}
    if params: p.update(params)
    r = requests.get(f"{NASA_BASE}{path}", params=p, timeout=15)
    r.raise_for_status()
    return r.json()

def get_json(url, params=None, timeout=12):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

# ── TELEGRAM HELPERS ──────────────────────────────────────────────────────────
async def safe_answer(q):
    try: await q.answer()
    except Exception: pass

async def safe_edit(q, text, reply_markup=None):
    try:
        await q.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception:
        try: await q.message.delete()
        except Exception: pass
        try:
            await q.message.chat.send_message(text, parse_mode="Markdown",
                                              reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception: pass

async def del_msg(q):
    try: await q.message.delete()
    except Exception: pass

# ── DATA ──────────────────────────────────────────────────────────────────────
PLANETS = [
    {"name":"☿ Mercury","dist":"57.9M km","period":"88d","day":"58.6d","temp":"-180/+430°C","moons":0,"radius":"2440km","fact":{"ru":"Самый большой перепад температур.","en":"Largest temperature range.","he":"הפרש הטמפרטורות הגדול ביותר.","ar":"أكبر مدى حراري."}},
    {"name":"♀ Venus","dist":"108M km","period":"225d","day":"243d","temp":"+465°C","moons":0,"radius":"6051km","fact":{"ru":"Горячее Меркурия. Вращается обратно.","en":"Hotter than Mercury. Spins backwards.","he":"חמה ממרקורי. מסתובבת הפוך.","ar":"أحر من عطارد. تدور عكسياً."}},
    {"name":"🌍 Earth","dist":"150M km","period":"365d","day":"24h","temp":"-88/+58°C","moons":1,"radius":"6371km","fact":{"ru":"Единственная планета с жизнью.","en":"Only known planet with life.","he":"הכוכב היחיד עם חיים.","ar":"الكوكب الوحيد بالحياة."}},
    {"name":"♂ Mars","dist":"228M km","period":"687d","day":"24h37m","temp":"-125/+20°C","moons":2,"radius":"3390km","fact":{"ru":"Гора Олимп — 21 км.","en":"Olympus Mons — 21km tall.","he":"הר אולימפוס — 21 ק\"מ.","ar":"جبل أوليمبوس — 21 كم."}},
    {"name":"♃ Jupiter","dist":"778M km","period":"11.9y","day":"9h56m","temp":"-108°C","moons":95,"radius":"71492km","fact":{"ru":"Шторм БКП — 350+ лет.","en":"GRS storm — 350+ years old.","he":"סערת הכתם האדום — 350+ שנה.","ar":"العاصفة الحمراء — 350+ سنة."}},
    {"name":"♄ Saturn","dist":"1.43B km","period":"29.5y","day":"10h33m","temp":"-139°C","moons":146,"radius":"60268km","fact":{"ru":"Плавал бы в воде!","en":"Would float in water!","he":"היה צף על מים!","ar":"سيطفو على الماء!"}},
    {"name":"⛢ Uranus","dist":"2.87B km","period":"84y","day":"17h14m","temp":"-197°C","moons":28,"radius":"25559km","fact":{"ru":"Ось наклонена на 98°.","en":"Axis tilted 98°.","he":"ציר מוטה ב-98°.","ar":"محوره مائل 98°."}},
    {"name":"♆ Neptune","dist":"4.5B km","period":"165y","day":"16h6m","temp":"-201°C","moons":16,"radius":"24622km","fact":{"ru":"Ветер до 2100 км/ч.","en":"Winds up to 2100 km/h.","he":"רוחות עד 2100 קמ\"ש.","ar":"رياح 2100 كم/ساعة."}},
]

# Planet data for age/weight calculator
PLANET_GRAVITY = {
    "☿ Mercury": 0.376, "♀ Venus": 0.904, "🌍 Earth": 1.0, "♂ Mars": 0.379,
    "♃ Jupiter": 2.528, "♄ Saturn": 1.065, "⛢ Uranus": 0.886, "♆ Neptune": 1.137
}
PLANET_YEAR_DAYS = {
    "☿ Mercury": 87.97, "♀ Venus": 224.70, "🌍 Earth": 365.25, "♂ Mars": 686.97,
    "♃ Jupiter": 4332.59, "♄ Saturn": 10759.22, "⛢ Uranus": 30688.50, "♆ Neptune": 60182.0
}

SPACE_FACTS = {
    "ru":["🌌 Вселенной ~13.8 млрд лет.","⭐ Звёзд больше, чем песчинок на всех пляжах.","🌑 Следы Армстронга на Луне сохранятся миллионы лет.","☀️ Свет от Солнца летит 8 мин 20 сек.","🪐 День на Венере длиннее года.","🌊 На Энцеладе — гейзеры воды.","⚫ Если сжать Землю до горошины — чёрная дыра.","🚀 Вояджер-1 покинул Солнечную систему в 2012 году.","🌌 В Млечном Пути ~400 млрд звёзд.","♄ Кольца Сатурна тоньше, чем бумага относительно своей ширины."],
    "en":["🌌 Universe is ~13.8 billion years old.","⭐ More stars than grains of sand on all beaches.","🌑 Armstrong's footprints last millions of years.","☀️ Sunlight takes 8 min 20 sec to reach Earth.","🪐 A day on Venus is longer than its year.","🌊 Enceladus has water geysers.","⚫ Earth compressed to marble = black hole.","🚀 Voyager 1 entered interstellar space in 2012.","🌌 Milky Way has ~400 billion stars.","♄ Saturn's rings are thinner than paper relative to their width."],
    "he":["🌌 היקום בן ~13.8 מיליארד שנה.","⭐ יותר כוכבים מגרגרי חול.","🌑 עקבות ארמסטרונג ישמרו מיליוני שנים.","☀️ אור השמש מגיע תוך 8 דקות ו-20 שניות.","🪐 יום על נוגה ארוך מהשנה.","🌊 לאנקלדוס יש גייזרים.","⚫ כדור הארץ לגולה = חור שחור.","🚀 ווֹיאַג'ר 1 — 2012."],
    "ar":["🌌 عمر الكون ~13.8 مليار سنة.","⭐ نجوم أكثر من حبات الرمل.","🌑 آثار أرمسترونغ ملايين السنين.","☀️ ضوء الشمس 8 دقائق و20 ثانية.","🪐 يوم الزهرة أطول من سنتها.","🌊 إنسيلادوس لديه ينابيع.","⚫ الأرض بحجم رخامة = ثقب أسود.","🚀 فوياجر 1 — 2012."],
}

METEOR_SHOWERS = [
    {"name":{"ru":"Персеиды","en":"Perseids","he":"פרסאידים","ar":"البرشاويات"},"peak":"12-13 Aug","rate":"100+/h","parent":"Comet Swift-Tuttle","speed":"59km/s","best":"After midnight, dark skies"},
    {"name":{"ru":"Геминиды","en":"Geminids","he":"גמינידים","ar":"الجوزائيات"},"peak":"13-14 Dec","rate":"120+/h","parent":"3200 Phaethon","speed":"35km/s","best":"Late evening onwards"},
    {"name":{"ru":"Леониды","en":"Leonids","he":"ליאונידים","ar":"الأسديات"},"peak":"17-18 Nov","rate":"10-15/h","parent":"Comet Tempel-Tuttle","speed":"71km/s","best":"After 1am"},
    {"name":{"ru":"Оринидиды","en":"Orionids","he":"אוריונידים","ar":"الجباريات"},"peak":"21-22 Oct","rate":"20/h","parent":"Comet Halley","speed":"66km/s","best":"After midnight"},
    {"name":{"ru":"Лириды","en":"Lyrids","he":"לירידים","ar":"الشلياقيات"},"peak":"22-23 Apr","rate":"18/h","parent":"Comet Thatcher","speed":"49km/s","best":"Pre-dawn hours"},
    {"name":{"ru":"Дракониды","en":"Draconids","he":"דרקונידים","ar":"التنينيات"},"peak":"8-9 Oct","rate":"10/h","parent":"Comet Giacobini-Zinner","speed":"20km/s","best":"Evening hours"},
]

KNOWN_EXOPLANETS = [
    {"name":"Kepler-452b","star":"Kepler-452","year":2015,"radius":1.63,"period":384.8,"dist_ly":1400,"note":{"ru":"Двойник Земли","en":"Earth twin","he":"כפיל כדור הארץ","ar":"توأم الأرض"}},
    {"name":"TRAPPIST-1e","star":"TRAPPIST-1","year":2017,"radius":0.92,"period":6.1,"dist_ly":39,"note":{"ru":"Возможна жидкая вода","en":"Possible liquid water","he":"מים נוזליים אפשריים","ar":"ماء سائل محتمل"}},
    {"name":"Proxima Centauri b","star":"Proxima Cen","year":2016,"radius":1.3,"period":11.2,"dist_ly":4.2,"note":{"ru":"Ближайшая экзопланета!","en":"Nearest exoplanet!","he":"הקרובה ביותר!","ar":"الأقرب!"}},
    {"name":"TOI 700 d","star":"TOI 700","year":2020,"radius":1.19,"period":37.4,"dist_ly":101,"note":{"ru":"Земного размера","en":"Earth-sized","he":"בגודל כדור הארץ","ar":"بحجم الأرض"}},
]

# ── QUIZ DATA ─────────────────────────────────────────────────────────────────
QUIZ_QUESTIONS = [
    {
        "q":{"ru":"Сколько планет в Солнечной системе?","en":"How many planets are in the Solar System?","he":"כמה כוכבים יש במערכת השמש?","ar":"كم عدد الكواكب في المجموعة الشمسية؟"},
        "options":["7","8","9","10"],"answer":1,
        "exp":{"ru":"С 2006 г. — 8 (Плутон стал карликовой планетой).","en":"Since 2006 — 8 (Pluto became a dwarf planet).","he":"מ-2006 — 8 (פלוטו הפך לכוכב לכת ננסי).","ar":"منذ 2006 — 8 (بلوتو أصبح كوكباً قزماً)."}
    },
    {
        "q":{"ru":"Какая планета самая горячая?","en":"Which planet is the hottest?","he":"איזה כוכב חם ביותר?","ar":"أي الكواكب الأكثر سخونة؟"},
        "options":["Mercury","Venus","Mars","Jupiter"],"answer":1,
        "exp":{"ru":"Венера (465°C) — парниковый эффект!","en":"Venus (465°C) — greenhouse effect!","he":"נוגה (465°C) — אפקט חממה!","ar":"الزهرة (465°C) — ظاهرة الاحتباس الحراري!"}
    },
    {
        "q":{"ru":"Как называется галактика, в которой мы живём?","en":"What is the name of our galaxy?","he":"מה שם הגלקסיה שלנו?","ar":"ما اسم مجرتنا؟"},
        "options":["Andromeda","Triangulum","Milky Way","Sombrero"],"answer":2,
        "exp":{"ru":"Млечный Путь содержит ~400 млрд звёзд.","en":"The Milky Way contains ~400 billion stars.","he":"שביל החלב מכיל ~400 מיליארד כוכבים.","ar":"درب التبانة يحتوي على ~400 مليار نجم."}
    },
    {
        "q":{"ru":"Что такое световой год?","en":"What is a light-year?","he":"מהי שנת אור?","ar":"ما هو السنة الضوئية؟"},
        "options":["Unit of time","Unit of distance","Speed of light","Unit of mass"],"answer":1,
        "exp":{"ru":"Расстояние, которое свет проходит за год (~9.46 трлн км).","en":"Distance light travels in one year (~9.46 trillion km).","he":"המרחק שאור עובר בשנה (~9.46 טריליון ק\"מ).","ar":"المسافة التي يقطعها الضوء في سنة واحدة (~9.46 تريليون كم)."}
    },
    {
        "q":{"ru":"На какой планете самый длинный день?","en":"Which planet has the longest day?","he":"לאיזה כוכב יש היום הארוך ביותר?","ar":"أي الكواكب لديه أطول يوم؟"},
        "options":["Mars","Saturn","Venus","Neptune"],"answer":2,
        "exp":{"ru":"День на Венере длиннее её года (243 земных дня).","en":"Venus's day is longer than its year (243 Earth days).","he":"יום על נוגה ארוך משנתה (243 ימי כדור הארץ).","ar":"يوم الزهرة أطول من سنتها (243 يوم أرضي)."}
    },
    {
        "q":{"ru":"Кто первым вышел в открытый космос?","en":"Who was the first person to walk in space?","he":"מי יצא לחלל הפתוח ראשון?","ar":"من كان أول شخص يسير في الفضاء؟"},
        "options":["Neil Armstrong","Yuri Gagarin","Alexei Leonov","Buzz Aldrin"],"answer":2,
        "exp":{"ru":"Алексей Леонов, 18 марта 1965 года.","en":"Alexei Leonov, March 18, 1965.","he":"אלכסיי לאונוב, 18 במרץ 1965.","ar":"أليكسي ليونوف، 18 مارس 1965."}
    },
    {
        "q":{"ru":"Какой телескоп был запущен в 2021 году?","en":"Which telescope was launched in 2021?","he":"איזה טלסקופ הושק ב-2021?","ar":"أي تلسكوب أُطلق في 2021؟"},
        "options":["Hubble","Spitzer","James Webb","Chandra"],"answer":2,
        "exp":{"ru":"JWST запущен 25 декабря 2021 года, зеркало 6.5 м.","en":"JWST launched Dec 25, 2021, 6.5m mirror.","he":"JWST הושק ב-25 בדצמבר 2021, מראה 6.5מ'.","ar":"JWST أُطلق في 25 ديسمبر 2021، مرآة 6.5 م."}
    },
    {
        "q":{"ru":"Сколько времени нужно свету, чтобы добраться от Солнца до Земли?","en":"How long does sunlight take to reach Earth?","he":"כמה זמן לוקח לאור השמש להגיע לכדור הארץ?","ar":"كم يستغرق ضوء الشمس للوصول إلى الأرض؟"},
        "options":["3 minutes","8 minutes 20 seconds","1 hour","24 hours"],"answer":1,
        "exp":{"ru":"~8 минут 20 секунд (150 млн км / 300 000 км/с).","en":"~8 min 20 sec (150M km ÷ 300,000 km/s).","he":"~8 דקות ו-20 שניות.","ar":"~8 دقائق و20 ثانية."}
    },
    {
        "q":{"ru":"Что находится в центре нашей галактики?","en":"What is at the center of our galaxy?","he":"מה נמצא במרכז הגלקסיה שלנו?","ar":"ما الذي يوجد في مركز مجرتنا؟"},
        "options":["White dwarf","Pulsar","Supermassive black hole","Neutron star"],"answer":2,
        "exp":{"ru":"Стрелец A* — чёрная дыра массой 4 млн солнц.","en":"Sagittarius A* — black hole with mass of 4M suns.","he":"קשת A* — חור שחור במסת 4 מיליון שמשות.","ar":"القوس A* — ثقب أسود بكتلة 4 ملايين شمس."}
    },
    {
        "q":{"ru":"Какая самая маленькая планета Солнечной системы?","en":"What is the smallest planet in the Solar System?","he":"מהו כוכב הלכת הקטן ביותר?","ar":"ما أصغر كوكب في المجموعة الشمسية؟"},
        "options":["Mars","Venus","Mercury","Pluto"],"answer":2,
        "exp":{"ru":"Меркурий — радиус 2440 км (чуть больше Луны).","en":"Mercury — radius 2,440 km (slightly bigger than Moon).","he":"מרקורי — רדיוס 2,440 ק\"מ.","ar":"عطارد — نصف قطره 2,440 كم."}
    },
]

# ── SCI-FI HOROSCOPE DATA ─────────────────────────────────────────────────────
ZODIAC_RANGES = [
    ((3,21),(4,19),"Aries"),((4,20),(5,20),"Taurus"),((5,21),(6,20),"Gemini"),
    ((6,21),(7,22),"Cancer"),((7,23),(8,22),"Leo"),((8,23),(9,22),"Virgo"),
    ((9,23),(10,22),"Libra"),((10,23),(11,21),"Scorpio"),((11,22),(12,21),"Sagittarius"),
    ((12,22),(12,31),"Capricorn"),((1,1),(1,19),"Capricorn"),((1,20),(2,18),"Aquarius"),
    ((2,19),(3,20),"Pisces"),
]

HOROSCOPES = {
    "ru": {
        "Aries":   "♈ *Овен*\n\nСолнечный ветер умеренный — Марс в благоприятном положении для ваших проектов. Сегодня хороший день для запуска нового маршрута исследования!\n\n🔬 *Наука дня:* Кп-индекс стабилен. Магнитосфера защищена.\n⚡ Энергия: ████████░░ 80%",
        "Taurus":  "♉ *Телец*\n\nВенера в перигелии — хороший день для долгосрочных проектов. Гравитация на вашей стороне, стройте фундамент!\n\n🔬 *Наука дня:* Солнечная активность низкая. Время планировать миссии.\n⚡ Энергия: ██████░░░░ 60%",
        "Gemini":  "♊ *Близнецы*\n\nДва магнитных полюса Урана символизируют ваш дух — будьте гибки! Межпланетная связь сегодня особенно чёткая.\n\n🔬 *Наука дня:* Активность суперновых в вашем секторе.\n⚡ Энергия: █████████░ 90%",
        "Cancer":  "♋ *Рак*\n\nЛуна в апогее — лучшее время для рефлексии и планирования. Приливные силы помогут скорректировать курс.\n\n🔬 *Наука дня:* Лунные фазы влияют на ионосферу Земли.\n⚡ Энергия: ████░░░░░░ 40%",
        "Leo":     "♌ *Лев*\n\nСолнечные вспышки класса M — ваша энергия зашкаливает! Космический ветер несёт вас к новым горизонтам.\n\n🔬 *Наука дня:* Возможны полярные сияния — смотрите на небо!\n⚡ Энергия: ██████████ 100%",
        "Virgo":   "♍ *Дева*\n\nАнализ данных с JWST указывает: детали важны. Сегодня займитесь точной настройкой своих систем.\n\n🔬 *Наука дня:* Телескоп Джеймс Уэбб фиксирует новые экзопланеты.\n⚡ Энергия: ███████░░░ 70%",
        "Libra":   "♎ *Весы*\n\nЦентр масс между Землёй и Луной в равновесии — идеальное время для принятия взвешенных решений.\n\n🔬 *Наука дня:* Гравитационные волны обнаружены LIGO.\n⚡ Энергия: ███████░░░ 70%",
        "Scorpio": "♏ *Скорпион*\n\nТёмная материя напоминает о скрытых силах. Изучайте то, что другие игнорируют — там ваша сила.\n\n🔬 *Наука дня:* 27% вселенной — тёмная материя. Обнаружена только косвенно.\n⚡ Энергия: ████████░░ 80%",
        "Sagittarius":"♐ *Стрелец*\n\nСтрела летит к центру галактики Стрелец A*! Ваши амбиции масштабны как Млечный Путь.\n\n🔬 *Наука дня:* Центр нашей галактики скрыт за газопылевыми облаками.\n⚡ Энергия: █████████░ 90%",
        "Capricorn":"♑ *Козерог*\n\nСатурн с его кольцами — ваш покровитель. Структура и порядок — ключи к успеху.\n\n🔬 *Наука дня:* Кольца Сатурна состоят из льда и пыли, толщиной всего ~100м.\n⚡ Энергия: ██████░░░░ 60%",
        "Aquarius": "♒ *Водолей*\n\nУран перевернулся на 98° — и вы готовы к нестандартным решениям! Время для революций в науке.\n\n🔬 *Наука дня:* Уран вращается «на боку» — уникальная ось вращения.\n⚡ Энергия: ████████░░ 80%",
        "Pisces":   "♓ *Рыбы*\n\nВодяные гейзеры Энцелада намекают: интуиция ведёт к источникам жизни. Доверяйте своим инстинктам.\n\n🔬 *Наука дня:* Подо льдом Энцелада возможен жидкий океан с жизнью.\n⚡ Энергия: █████░░░░░ 50%",
    },
    "en": {
        "Aries":   "♈ *Aries*\n\nSolar wind is moderate — Mars is in a favorable position for your projects. Great day to launch a new exploration mission!\n\n🔬 *Science today:* Kp-index stable. Magnetosphere protected.\n⚡ Energy: ████████░░ 80%",
        "Taurus":  "♉ *Taurus*\n\nVenus at perihelion — ideal for long-term projects. Gravity is on your side, build your foundation!\n\n🔬 *Science today:* Low solar activity. Time to plan missions.\n⚡ Energy: ██████░░░░ 60%",
        "Gemini":  "♊ *Gemini*\n\nUranus's dual magnetic poles mirror your spirit — stay flexible! Interplanetary communication is especially clear today.\n\n🔬 *Science today:* Supernova activity detected in your sector.\n⚡ Energy: █████████░ 90%",
        "Cancer":  "♋ *Cancer*\n\nMoon at apogee — best time for reflection and planning. Tidal forces help you correct your course.\n\n🔬 *Science today:* Moon phases affect Earth's ionosphere.\n⚡ Energy: ████░░░░░░ 40%",
        "Leo":     "♌ *Leo*\n\nClass M solar flares — your energy is off the charts! Cosmic wind carries you to new horizons.\n\n🔬 *Science today:* Aurora borealis possible — look to the skies!\n⚡ Energy: ██████████ 100%",
        "Virgo":   "♍ *Virgo*\n\nJWST data analysis says: details matter. Today is the day for fine-tuning your systems.\n\n🔬 *Science today:* James Webb Telescope imaging new exoplanets.\n⚡ Energy: ███████░░░ 70%",
        "Libra":   "♎ *Libra*\n\nEarth-Moon center of mass in equilibrium — perfect for balanced decision-making.\n\n🔬 *Science today:* Gravitational waves detected by LIGO.\n⚡ Energy: ███████░░░ 70%",
        "Scorpio": "♏ *Scorpio*\n\nDark matter reminds you of hidden forces. Study what others ignore — therein lies your power.\n\n🔬 *Science today:* 27% of the universe is dark matter, detected only indirectly.\n⚡ Energy: ████████░░ 80%",
        "Sagittarius":"♐ *Sagittarius*\n\nThe arrow flies toward Sagittarius A*! Your ambitions are as vast as the Milky Way.\n\n🔬 *Science today:* Our galactic center is hidden behind dust clouds.\n⚡ Energy: █████████░ 90%",
        "Capricorn":"♑ *Capricorn*\n\nSaturn with its rings is your patron. Structure and order are your keys to success.\n\n🔬 *Science today:* Saturn's rings are ice and dust, only ~100m thick.\n⚡ Energy: ██████░░░░ 60%",
        "Aquarius": "♒ *Aquarius*\n\nUranus tilted 98° — and you're ready for unconventional solutions! Time for scientific revolutions.\n\n🔬 *Science today:* Uranus rotates 'on its side' — unique axial tilt.\n⚡ Energy: ████████░░ 80%",
        "Pisces":   "♓ *Pisces*\n\nEnceladus water geysers hint: intuition leads to life's sources. Trust your instincts.\n\n🔬 *Science today:* Beneath Enceladus's ice there may be a liquid ocean with life.\n⚡ Energy: █████░░░░░ 50%",
    },
}

# ── COSMIC NAME GENERATOR DATA ────────────────────────────────────────────────
NAME_PREFIXES = ["Alpha","Beta","Gamma","Delta","Zeta","Omega","Nova","Astro","Cosmo","Stellar","Nebula","Quasar","Pulsar","Photon","Proton","Electron","Ion","Plasma","Corona","Aurora","Vega","Lyra","Orion","Sirius","Arcturus"]
NAME_SUFFIXES = ["Prime","Major","Minor","Centauri","Nexus","Proxima","Maxima","Ultima","Eternis","Infiniti","Vortex","Apex","Zenith","Nadir","Polaris","Astra","Solara","Lunara","Gaia","Helios"]
STAR_CODES    = ["2026","X","VII","Omega","Mk2","Alpha","3C","HD"]

# ── DAILY POLL DATA ───────────────────────────────────────────────────────────
DAILY_POLLS = [
    {
        "q":{"ru":"Где бы вы предпочли жить?","en":"Where would you prefer to live?"},
        "opts":{"ru":["В облаках Венеры ☁️","В пещерах Марса 🪐","На Луне 🌙","На станции у Юпитера ♃"],
                "en":["In Venus clouds ☁️","In Mars caves 🪐","On the Moon 🌙","On Jupiter station ♃"]}
    },
    {
        "q":{"ru":"Что важнее для человечества?","en":"What matters more for humanity?"},
        "opts":{"ru":["Колонизация Марса 🔴","Поиск экзопланет 🔭","Изучение тёмной материи ⚫","Добыча ресурсов астероидов ☄️"],
                "en":["Mars colonization 🔴","Finding exoplanets 🔭","Dark matter research ⚫","Asteroid mining ☄️"]}
    },
    {
        "q":{"ru":"Ваша любимая миссия NASA?","en":"Your favorite NASA mission?"},
        "opts":{"ru":["Аполлон 🌙","Вояджер 🚀","Хаббл 🔭","Перспектива 🤖"],
                "en":["Apollo 🌙","Voyager 🚀","Hubble 🔭","Perseverance 🤖"]}
    },
    {
        "q":{"ru":"Что вы бы взяли на МКС?","en":"What would you bring to the ISS?"},
        "opts":{"ru":["Гитару 🎸","Книги 📚","Спортивный зал 🏋️","Телескоп 🔭"],
                "en":["A guitar 🎸","Books 📚","Gym equipment 🏋️","A telescope 🔭"]}
    },
]

# ── STATIC TEXT DATA ──────────────────────────────────────────────────────────
STATIC_TEXTS = {
    "kuiper_belt":    {"ru":"📦 *Пояс Койпера*\n\nОбласть за Нептуном. Плутон, Эрида, Макемаке.\nNew Horizons посетил Плутон (2015) и Аррокот (2019).","en":"📦 *Kuiper Belt*\n\nBeyond Neptune. Pluto, Eris, Makemake.\nNew Horizons visited Pluto (2015) & Arrokoth (2019).","he":"📦 *חגורת קויפר*\n\nמעבר לנפטון. פלוטו, אריס, מאקמאקה.","ar":"📦 *حزام كويبر*\n\nوراء نبتون. بلوتو، إيريس، ماكيماكي."},
    "planet_alignment":{"ru":"🪐 *Парад планет*\n\nМарс, Юпитер, Сатурн видны без телескопа. Полный парад (все 8) — раз в сотни лет.","en":"🪐 *Planet Parade*\n\nMars, Jupiter, Saturn — naked eye. Full parade (all 8) every few hundred years.","he":"🪐 *מצעד כוכבים*\n\nמאדים, צדק, שבתאי — ללא טלסקופ.","ar":"🪐 *استعراض الكواكب*\n\nالمريخ، المشتري، زحل — بالعين."},
    "solar_eclipse":  {"ru":"☀️ *Затмения*\n\n• 2026 — Испания\n• 2027 — Сев. Африка\n• 2028 — Австралия","en":"☀️ *Solar Eclipses*\n\n• 2026 — Spain\n• 2027 — North Africa\n• 2028 — Australia","he":"☀️ *ליקויי חמה*\n\n• 2026 ספרד\n• 2027 צפון אפריקה","ar":"☀️ *كسوف الشمس*\n\n• 2026 إسبانيا\n• 2027 شمال أفريقيا"},
    "orbital_scale":  {"ru":"📏 *Масштаб*\n\nЕсли Солнце = 1 м:\n• Земля — 1 см / 117 м\n• Нептун — 3 см / 3.5 км\n• Проксима — 2800 км!","en":"📏 *Scale*\n\nIf Sun = 1m:\n• Earth — 1cm at 117m\n• Neptune — 3cm at 3.5km\n• Proxima — 2,800 km!","he":"📏 *קנה מידה*\n\nאם השמש = 1מ': כדור הארץ 1ס\"מ.","ar":"📏 *مقياس*\n\nإذا الشمس = 1م: الأرض 1سم."},
    "darkmatter":     {"ru":"🌑 *Тёмная материя*\n\n5% обычная, 27% тёмная, 68% тёмная энергия.\nОбнаружена по гравитационным эффектам.","en":"🌑 *Dark Matter*\n\n5% ordinary, 27% dark matter, 68% dark energy.\nDetected via gravitational lensing.","he":"🌑 *חומר אפל*\n\n5% רגיל, 27% חומר אפל, 68% אנרגיה אפלה.","ar":"🌑 *المادة المظلمة*\n\n5% عادية، 27% مظلمة، 68% طاقة مظلمة."},
    "seti":           {"ru":"👽 *SETI*\n\nУравнение Дрейка. Послание Аресибо (1974).\nСигнал Wow! (1977). Парадокс Ферми.","en":"👽 *SETI*\n\nDrake Equation. Arecibo Message (1974).\nWow! Signal (1977). Fermi Paradox.","he":"👽 *SETI*\n\nמשוואת דרייק. מסר אריסיבו (1974). אות Wow!","ar":"👽 *SETI*\n\nمعادلة دريك. رسالة أريسيبو 1974. إشارة Wow!"},
    "gravwaves":      {"ru":"🌊 *Гравитационные волны*\n\nGW150914 (2015) — слияние ЧД. LIGO. Нобель 2017.","en":"🌊 *Gravitational Waves*\n\nGW150914 (2015) — BH merger. LIGO. Nobel 2017.","he":"🌊 *גלי כבידה*\n\nGW150914 (2015). LIGO. נובל 2017.","ar":"🌊 *موجات الجاذبية*\n\nGW150914 (2015). LIGO. نوبل 2017."},
    "future":         {"ru":"🔮 *Будущее*\n\n+5 млрд лет — Солнце → красный гигант.\n+4.5 млрд — столкновение с Андромедой.\n+100 трлн — тепловая смерть.","en":"🔮 *Future*\n\n+5B yrs — Sun → red giant.\n+4.5B — Andromeda collision.\n+100T — heat death.","he":"🔮 *עתיד*\n\n+5 מיליארד שנה — השמש ענק אדום.","ar":"🔮 *المستقبل*\n\n+5 مليار سنة — الشمس عملاق أحمر."},
    "radioastro":     {"ru":"🔭 *Радиоастрономия*\n\nПульсары, квазары, FRB. FAST (500м) — крупнейший. Wow! (1977) не объяснён.","en":"🔭 *Radio Astronomy*\n\nPulsars, quasars, FRBs. FAST (500m) world's largest. Wow! signal unexplained.","he":"🔭 *רדיו אסטרונומיה*\n\nפולסרים, קווזרים. FAST 500מ'.","ar":"🔭 *الفلك الراديوي*\n\nنجوم نابضة، كوازارات. FAST 500م."},
    "grb":            {"ru":"💥 *Гамма-всплески*\n\nМощнейшие взрывы во Вселенной.\nДлинные — коллапс звезды. Короткие — слияние НЗ.","en":"💥 *Gamma-Ray Bursts*\n\nMost powerful explosions. Long — stellar collapse. Short — neutron star merger.","he":"💥 *פרצי גמא*\n\nהפיצוצים החזקים ביותר.","ar":"💥 *انفجارات غاما*\n\nأقوى الانفجارات في الكون."},
    "dark_energy":    {"ru":"⚡ *Тёмная энергия*\n\n68% Вселенной. Открыта 1998. Нобель 2011.\nУскоряет расширение — природа неизвестна.","en":"⚡ *Dark Energy*\n\n68% of Universe. Discovered 1998. Nobel 2011.\nAccelerates expansion — nature unknown.","he":"⚡ *אנרגיה אפלה*\n\n68% מהיקום. נובל 2011.","ar":"⚡ *الطاقة المظلمة*\n\n68% من الكون. نوبل 2011."},
    "ozone":          {"ru":"🛡 *Озон*\n\nЗащищает от УФ. Монреальский протокол (1987). Дыра восстанавливается.","en":"🛡 *Ozone*\n\nBlocks UV. Montreal Protocol (1987). Antarctic hole recovering.","he":"🛡 *אוזון*\n\nפרוטוקול מונטריאול 1987.","ar":"🛡 *الأوزون*\n\nبروتوكول مونتريال 1987."},
    "ocean_currents": {"ru":"🌊 *Течения*\n\nГольфстрим, Куросио — переносят тепло, влияют на климат.","en":"🌊 *Ocean Currents*\n\nGulf Stream, Kuroshio — transport heat, affect climate.","he":"🌊 *זרמים*\n\nזרם המפרץ, קורושיו.","ar":"🌊 *التيارات*\n\nتيار الخليج، كوروشيو."},
    "space_stations": {"ru":"🛸 *Станции*\n\n• *МКС* (с 1998) — 420 т, 408 км\n• *Тяньгун (Китай)* — НОО\n• *Gateway* (~2028) — у Луны","en":"🛸 *Space Stations*\n\n• *ISS* (1998) — 420t, 408km\n• *Tiangong (China)* — LEO\n• *Gateway* (~2028) — Moon orbit","he":"🛸 *תחנות*\n\n• ISS (1998). • Tiangong. • Gateway (~2028).","ar":"🛸 *محطات*\n\n• ISS (1998). • Tiangong. • Gateway (~2028)."},
    "women_in_space": {"ru":"👩‍🚀 *Женщины*\n\n• Терешкова (1963)\n• Салли Райд (1983)\n• Савицкая (1984) — первый выход\n• Пегги Уитсон — рекорд","en":"👩‍🚀 *Women in Space*\n\n• Tereshkova (1963)\n• Sally Ride (1983)\n• Savitskaya (1984) — first EVA\n• Peggy Whitson — duration record","he":"👩‍🚀 *נשים*\n\n• טרשקובה (1963). • סאלי רייד (1983).","ar":"👩‍🚀 *نساء*\n\n• تيريشكوفا (1963). • سالي رايد (1983)."},
    "mars_colonization":{"ru":"🔴 *Марс*\n\nSpaceX, NASA, Китай — планы 2030–2040.\nПроблемы: радиация, гравитация, ресурсы.","en":"🔴 *Mars Colonization*\n\nSpaceX, NASA, China — plans 2030–2040.\nChallenges: radiation, gravity, resources.","he":"🔴 *מאדים*\n\nSpaceX, NASA, סין — 2030–2040.","ar":"🔴 *المريخ*\n\nSpaceX، ناسا، الصين — 2030–2040."},
    "space_medicine":  {"ru":"🩺 *Медицина*\n\nНевесомость — потеря костной массы.\nЛимит NASA — 600 мЗв.","en":"🩺 *Space Medicine*\n\nMicrogravity — bone loss.\nNASA limit — 600 mSv.","he":"🩺 *רפואה*\n\nאובדן עצם. 600 mSv.","ar":"🩺 *طب*\n\nفقدان العظام. 600 mSv."},
    "astronaut_training":{"ru":"🎓 *Подготовка*\n\nНейтральная плавучесть, центрифуги, тренажёры. Русский/английский для МКС.","en":"🎓 *Training*\n\nNeutral buoyancy, centrifuges, simulators. Russian/English for ISS.","he":"🎓 *אימון*\n\nציפה ניטרלית, צנטריפוגות.","ar":"🎓 *التدريب*\n\nالطفو المحايد، أجهزة الطرد."},
    "debris":          {"ru":"🛰 *Мусор*\n\n~50 000 объектов. Скорость ~7.5 км/с. МКС маневрирует ~3 раза/год.","en":"🛰 *Space Debris*\n\n~50,000 objects. Speed ~7.5 km/s. ISS maneuvers ~3×/year.","he":"🛰 *פסולת*\n\n~50,000 עצמים. 7.5 ק\"מ/ש'.","ar":"🛰 *الحطام*\n\n~50,000 جسم. 7.5 كم/ث."},
    "space_records":   {"ru":"🏆 *Рекорды*\n\n• Поляков — 437 суток (Мир)\n• Кононенко — 1000+ суток (2024)\n• Вояджер-1 — >24 млрд км","en":"🏆 *Records*\n\n• Polyakov — 437 days (Mir)\n• Kononenko — 1000+ days (2024)\n• Voyager-1 — >24B km","he":"🏆 *שיאים*\n\n• פוליאקוב 437 ימים. • Voyager-1 >24 מיליארד ק\"מ.","ar":"🏆 *أرقام*\n\n• بوليكوف 437 يوماً. • Voyager-1 >24 مليار كم."},
    "red_giants":      {"ru":"🔴 *Красные гиганты*\n\nСолнце → гигант через ~5 млрд лет.\nЗвёзды >8 M☉ — сверхновая → нейтронная звезда или ЧД.","en":"🔴 *Red Giants*\n\nSun → red giant in ~5B years.\nStars >8 M☉ → supernova → neutron star or BH.","he":"🔴 *ענקים אדומים*\n\nהשמש → ענק אדום בעוד ~5 מיליארד שנה.","ar":"🔴 *العمالقة الحمراء*\n\nالشمس → عملاق أحمر بعد ~5 مليار سنة."},
}

# ── IMAGE SEARCH QUERIES ──────────────────────────────────────────────────────
EARTH_Q  = ["earth from space","earth orbit nasa","earth blue marble","earth ISS view"]
GALLERY_Q= ["nebula","galaxy","supernova","aurora","saturn rings","jupiter","andromeda galaxy"]
MARS_Q   = ["mars surface curiosity","mars landscape nasa","mars perseverance"]
ROVER_NAMES = ["curiosity","perseverance"]
MARS_FACTS = {
    "ru":["Олимп — 21 км!","Curiosity проехал >33 км.","Сутки — 24 ч 37 мин.","Гравитация 38%."],
    "en":["Olympus Mons 21km!","Curiosity >33km.","Day — 24h 37min.","Gravity 38%."],
    "he":["הר אולימפוס 21 ק\"מ.","קיוריוסיטי >33 ק\"מ.","יום — 24:37."],
    "ar":["أوليمبوس 21 كم.","كيوريوسيتي >33 كم.","اليوم 24:37."]
}

IMG_MAP = {
    "epic": EARTH_Q, "gallery": GALLERY_Q,
    "earth_night": ["earth at night city lights nasa","night lights satellite"],
    "eclipse": ["solar eclipse nasa","lunar eclipse nasa","total eclipse"],
    "jwst_gallery": ["James Webb telescope JWST","Webb deep field nebula"],
    "moon_gallery": ["moon surface nasa","lunar crater apollo"],
    "blue_marble": ["blue marble earth nasa","whole earth nasa"],
    "ceres": ["Ceres Dawn nasa","Ceres bright spots"],
    "pluto_close": ["Pluto New Horizons nasa"],
    "nebulae": ["nebula hubble","eagle nebula","orion nebula"],
    "deepspace": ["hubble deep field galaxy","james webb deep field"],
    "sun": ["solar flare nasa SDO","sun corona"],
    "aurora": ["aurora borealis ISS","northern lights nasa"],
    "blackholes": ["black hole accretion disk nasa"],
    "supernovae": ["supernova remnant hubble","crab nebula"],
    "clusters": ["star cluster hubble","globular cluster"],
    "comets": ["comet nasa hubble","comet NEOWISE"],
    "history": ["apollo moon landing nasa","space shuttle launch"],
    "giants": ["jupiter great red spot nasa","saturn rings cassini"],
    "moons": ["europa moon jupiter nasa","titan saturn cassini","enceladus geysers"],
    "missions": ["voyager spacecraft nasa","cassini saturn","perseverance rover"],
    "nearstars": ["alpha centauri star","red dwarf star nasa"],
    "pulsars": ["pulsar neutron star nasa","crab pulsar"],
    "milkyway": ["milky way galaxy nasa","galactic center"],
    "magnetosphere": ["earth magnetosphere nasa","Van Allen belts"],
    "dwarfplanets": ["pluto new horizons nasa","ceres dawn nasa"],
    "climate": ["arctic ice melt nasa","sea level rise satellite"],
    "quasars": ["quasar nasa hubble","active galaxy nucleus"],
    "cmb": ["cosmic microwave background Planck"],
    "galaxy_collision": ["galaxy collision hubble","antennae galaxies"],
    "star_formation": ["star formation nebula","pillars of creation"],
    "cosmic_web": ["cosmic web filament simulation"],
    "wildfires": ["wildfire satellite nasa","forest fire space"],
    "ice_sheets": ["ice sheet antarctica nasa","arctic sea ice"],
    "deforestation": ["deforestation amazon satellite"],
    "night_lights": ["earth at night city lights nasa"],
    "ocean_temp": ["sea surface temperature nasa"],
    "volcanoes": ["volcano eruption space satellite"],
    "hurricanes": ["hurricane from space satellite","tropical storm ISS"],
    "spacewalks": ["spacewalk EVA astronaut ISS nasa"],
    "lunar_missions": ["apollo moon mission","artemis moon nasa"],
    "moon_landing_sites": ["apollo landing site moon","tranquility base"],
    "rocket_engines": ["rocket engine nasa RS-25"],
    "tornadoes": ["tornado from space satellite"],
    "space_food": ["space food astronaut nasa ISS"],
}

# ── KEYBOARDS ──────────────────────────────────────────────────────────────────
def lang_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_ru"),
        InlineKeyboardButton("🇬🇧 English",  callback_data="setlang_en"),
    ],[
        InlineKeyboardButton("🇮🇱 עברית",   callback_data="setlang_he"),
        InlineKeyboardButton("🇦🇪 العربية", callback_data="setlang_ar"),
    ]])

def main_menu_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("cat_photo"),       callback_data="cat_photo")],
        [InlineKeyboardButton(L("cat_solarsys"),    callback_data="cat_solarsys")],
        [InlineKeyboardButton(L("cat_deepspace"),   callback_data="cat_deepspace")],
        [InlineKeyboardButton(L("cat_earth"),       callback_data="cat_earth")],
        [InlineKeyboardButton(L("cat_science"),     callback_data="cat_science")],
        [InlineKeyboardButton(L("cat_live"),        callback_data="cat_live")],
        [InlineKeyboardButton(L("cat_interactive"), callback_data="cat_interactive")],
        [InlineKeyboardButton(L("btn_spacefact"),   callback_data="spacefact"),
         InlineKeyboardButton(L("btn_channels"),    callback_data="channels")],
        [InlineKeyboardButton(L("btn_lang"),        callback_data="choose_lang")],
    ])

def back_kb(lang, refresh=None, ctx=None):
    rows = []
    if refresh:
        rows.append([InlineKeyboardButton(tx(lang, "btn_refresh"), callback_data=refresh)])
    row = []
    if ctx and ctx.user_data.get("last_cat"):
        row.append(InlineKeyboardButton(tx(lang, "back_cat"), callback_data=ctx.user_data["last_cat"]))
    row.append(InlineKeyboardButton(tx(lang, "back_menu"), callback_data="back"))
    rows.append(row)
    return InlineKeyboardMarkup(rows)

def action_kb(lang, cb, label="btn_another", ctx=None):
    row = [InlineKeyboardButton(tx(lang, label), callback_data=cb)]
    if ctx and ctx.user_data.get("last_cat"):
        row.append(InlineKeyboardButton(tx(lang, "back_cat"), callback_data=ctx.user_data["last_cat"]))
    row.append(InlineKeyboardButton(tx(lang, "back_menu"), callback_data="back"))
    return InlineKeyboardMarkup([row])

def cat_photo_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_apod"),callback_data="apod"), InlineKeyboardButton(L("btn_apod_rnd"),callback_data="apod_random")],
        [InlineKeyboardButton(L("btn_gallery"),callback_data="gallery"), InlineKeyboardButton(L("btn_hubble"),callback_data="deepspace")],
        [InlineKeyboardButton(L("btn_mars"),callback_data="mars"), InlineKeyboardButton(L("btn_mars_rv"),callback_data="mars_rovers")],
        [InlineKeyboardButton(L("btn_epic"),callback_data="epic"), InlineKeyboardButton(L("btn_earth_night"),callback_data="earth_night")],
        [InlineKeyboardButton(L("btn_nebulae"),callback_data="nebulae"), InlineKeyboardButton(L("btn_clusters"),callback_data="clusters")],
        [InlineKeyboardButton(L("btn_eclipse"),callback_data="eclipse"), InlineKeyboardButton(L("btn_jwst"),callback_data="jwst_gallery")],
        [InlineKeyboardButton(L("btn_moon_gal"),callback_data="moon_gallery"), InlineKeyboardButton(L("btn_blue_marble"),callback_data="blue_marble")],
        [InlineKeyboardButton(L("btn_spacewalks"),callback_data="spacewalks")],
        [InlineKeyboardButton(L("back_menu"),callback_data="back")],
    ])

def cat_solarsys_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_planets"),callback_data="planets"), InlineKeyboardButton(L("btn_giants"),callback_data="giants")],
        [InlineKeyboardButton(L("btn_dwarfs"),callback_data="dwarfplanets"), InlineKeyboardButton(L("btn_moons"),callback_data="moons")],
        [InlineKeyboardButton(L("btn_asteroids"),callback_data="asteroids"), InlineKeyboardButton(L("btn_comets"),callback_data="comets")],
        [InlineKeyboardButton(L("btn_moon"),callback_data="moon"), InlineKeyboardButton(L("btn_meteors"),callback_data="meteors")],
        [InlineKeyboardButton(L("btn_sun"),callback_data="sun"), InlineKeyboardButton(L("btn_spaceweather"),callback_data="spaceweather")],
        [InlineKeyboardButton(L("btn_ceres"),callback_data="ceres"), InlineKeyboardButton(L("btn_pluto"),callback_data="pluto_close")],
        [InlineKeyboardButton(L("btn_kuiper"),callback_data="kuiper_belt"), InlineKeyboardButton(L("btn_alignment"),callback_data="planet_alignment")],
        [InlineKeyboardButton(L("btn_solar_ecl"),callback_data="solar_eclipse"), InlineKeyboardButton(L("btn_scale"),callback_data="orbital_scale")],
        [InlineKeyboardButton(L("btn_lunar_miss"),callback_data="lunar_missions")],
        [InlineKeyboardButton(L("back_menu"),callback_data="back")],
    ])

def cat_deepspace_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_deepspace"),callback_data="deepspace"), InlineKeyboardButton(L("btn_milkyway"),callback_data="milkyway")],
        [InlineKeyboardButton(L("btn_blackholes"),callback_data="blackholes"), InlineKeyboardButton(L("btn_supernovae"),callback_data="supernovae")],
        [InlineKeyboardButton(L("btn_pulsars"),callback_data="pulsars"), InlineKeyboardButton(L("btn_nearstars"),callback_data="nearstars")],
        [InlineKeyboardButton(L("btn_exoplanets"),callback_data="exoplanets"), InlineKeyboardButton(L("btn_seti"),callback_data="seti")],
        [InlineKeyboardButton(L("btn_gravwaves"),callback_data="gravwaves"), InlineKeyboardButton(L("btn_darkmatter"),callback_data="darkmatter")],
        [InlineKeyboardButton(L("btn_future"),callback_data="future"), InlineKeyboardButton(L("btn_radioastro"),callback_data="radioastro")],
        [InlineKeyboardButton(L("btn_quasars"),callback_data="quasars"), InlineKeyboardButton(L("btn_grb"),callback_data="grb")],
        [InlineKeyboardButton(L("btn_cmb"),callback_data="cmb"), InlineKeyboardButton(L("btn_gal_coll"),callback_data="galaxy_collision")],
        [InlineKeyboardButton(L("btn_starform"),callback_data="star_formation"), InlineKeyboardButton(L("btn_dark_en"),callback_data="dark_energy")],
        [InlineKeyboardButton(L("btn_cosm_web"),callback_data="cosmic_web"), InlineKeyboardButton(L("btn_red_giants"),callback_data="red_giants")],
        [InlineKeyboardButton(L("back_menu"),callback_data="back")],
    ])

def cat_earth_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_epic"),callback_data="epic"), InlineKeyboardButton(L("btn_climate"),callback_data="climate")],
        [InlineKeyboardButton(L("btn_volcanoes"),callback_data="volcanoes"), InlineKeyboardButton(L("btn_hurricanes"),callback_data="hurricanes")],
        [InlineKeyboardButton(L("btn_aurora"),callback_data="aurora"), InlineKeyboardButton(L("btn_magneto"),callback_data="magnetosphere")],
        [InlineKeyboardButton(L("btn_satellites"),callback_data="satellites"), InlineKeyboardButton(L("btn_debris"),callback_data="debris")],
        [InlineKeyboardButton(L("btn_wildfires"),callback_data="wildfires"), InlineKeyboardButton(L("btn_ice"),callback_data="ice_sheets")],
        [InlineKeyboardButton(L("btn_deforest"),callback_data="deforestation"), InlineKeyboardButton(L("btn_nightlights"),callback_data="night_lights")],
        [InlineKeyboardButton(L("btn_ozone"),callback_data="ozone"), InlineKeyboardButton(L("btn_ocean_temp"),callback_data="ocean_temp")],
        [InlineKeyboardButton(L("btn_ocean_cur"),callback_data="ocean_currents"), InlineKeyboardButton(L("btn_tornadoes"),callback_data="tornadoes")],
        [InlineKeyboardButton(L("back_menu"),callback_data="back")],
    ])

def cat_science_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_launches"),callback_data="launches"), InlineKeyboardButton(L("btn_missions"),callback_data="missions")],
        [InlineKeyboardButton(L("btn_history"),callback_data="history"), InlineKeyboardButton(L("btn_iss"),callback_data="iss")],
        [InlineKeyboardButton(L("btn_telescopes"),callback_data="telescopes"), InlineKeyboardButton(L("btn_sp_stations"),callback_data="space_stations")],
        [InlineKeyboardButton(L("btn_moon_sites"),callback_data="moon_landing_sites"), InlineKeyboardButton(L("btn_women"),callback_data="women_in_space")],
        [InlineKeyboardButton(L("btn_mars_col"),callback_data="mars_colonization"), InlineKeyboardButton(L("btn_sp_med"),callback_data="space_medicine")],
        [InlineKeyboardButton(L("btn_rockets"),callback_data="rocket_engines"), InlineKeyboardButton(L("btn_training"),callback_data="astronaut_training")],
        [InlineKeyboardButton(L("btn_records"),callback_data="space_records"), InlineKeyboardButton(L("btn_food"),callback_data="space_food")],
        [InlineKeyboardButton(L("back_menu"),callback_data="back")],
    ])

def cat_live_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_solar_wind"),callback_data="live_solar_wind")],
        [InlineKeyboardButton(L("btn_kp"),callback_data="live_kp"), InlineKeyboardButton(L("btn_flares"),callback_data="live_flares")],
        [InlineKeyboardButton(L("btn_live_iss"),callback_data="live_iss"), InlineKeyboardButton(L("btn_radiation"),callback_data="live_radiation")],
        [InlineKeyboardButton(L("btn_aurora_f"),callback_data="live_aurora_forecast"), InlineKeyboardButton(L("btn_geomag"),callback_data="live_geomagnetic_alert")],
        [InlineKeyboardButton(L("btn_sunspot"),callback_data="live_sunspot"), InlineKeyboardButton(L("btn_live_epic"),callback_data="live_epic_latest")],
        [InlineKeyboardButton(L("btn_sat_count"),callback_data="live_satellite_count")],
        [InlineKeyboardButton(L("back_menu"),callback_data="back")],
    ])

def cat_interactive_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_planet_calc"), callback_data="planet_calc")],
        [InlineKeyboardButton(L("btn_quiz"),        callback_data="quiz_start_menu")],
        [InlineKeyboardButton(L("btn_space_name"),  callback_data="space_name")],
        [InlineKeyboardButton(L("btn_horoscope"),   callback_data="horoscope_menu")],
        [InlineKeyboardButton(L("btn_capsule"),     callback_data="capsule_menu")],
        [InlineKeyboardButton(L("btn_poll"),        callback_data="daily_poll")],
        [InlineKeyboardButton(L("btn_mars_live"),   callback_data="mars_rover_live")],
        [InlineKeyboardButton(L("btn_notifications"),callback_data="notifications_menu")],
        [InlineKeyboardButton(L("btn_nasa_tv"),     callback_data="nasa_tv")],
        [InlineKeyboardButton(L("btn_lunar_cal"),   callback_data="lunar_calendar")],
        [InlineKeyboardButton(L("back_menu"),       callback_data="back")],
    ])

def notifications_kb(lang, subs: dict, chat_id: int):
    def btn(key, cb):
        label = tx(lang, key)
        is_sub = chat_id in subs.get(cb.replace("notif_toggle_",""), [])
        status = "✅" if is_sub else "🔔"
        return InlineKeyboardButton(f"{status} {label}", callback_data=cb)
    return InlineKeyboardMarkup([
        [btn("notif_sub_ast",    "notif_toggle_asteroids")],
        [btn("notif_sub_meteor", "notif_toggle_meteors")],
        [btn("notif_sub_sw",     "notif_toggle_space_weather")],
        [btn("notif_sub_lunar",  "notif_toggle_lunar")],
        [btn("notif_sub_news",   "notif_toggle_nasa_news")],
        [btn("notif_sub_tv",     "notif_toggle_nasa_tv")],
        [InlineKeyboardButton(tx(lang, "back_menu"), callback_data="back")],
    ])

def quiz_kb(lang, q_index: int, answered: bool = False):
    if answered:
        next_cb = "quiz_next" if q_index < 9 else "quiz_finish"
        label   = tx(lang, "quiz_next") if q_index < 9 else tx(lang, "quiz_finish")
        return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=next_cb)]])
    opts = QUIZ_QUESTIONS[q_index]["options"]
    rows = [[InlineKeyboardButton(opt, callback_data=f"quiz_ans_{q_index}_{i}")] for i, opt in enumerate(opts)]
    return InlineKeyboardMarkup(rows)

# ── IMAGE HELPER ──────────────────────────────────────────────────────────────
async def send_nasa_image(q, ctx, queries, cb=""):
    lang = get_lang(ctx)
    try:
        r = requests.get("https://images-api.nasa.gov/search",
            params={"q": random.choice(queries), "media_type":"image","page_size":40}, timeout=12)
        r.raise_for_status()
        items = [it for it in r.json().get("collection",{}).get("items",[]) if it.get("links")]
        if not items:
            await safe_edit(q, tx(lang,"no_img"), reply_markup=back_kb(lang, ctx=ctx)); return
        item   = random.choice(items[:25])
        data   = item.get("data",[{}])[0]
        title  = data.get("title","NASA")
        desc   = strip_html(data.get("description",""))[:400]
        date_c = (data.get("date_created") or "")[:10]
        center = data.get("center","NASA")
        img_url= (item.get("links",[{}])[0]).get("href","")
        caption= f"*{title}*\n📅 {date_c}  |  🏛 {center}\n\n{desc+'…' if desc else ''}"
        kb = action_kb(lang, cb, "btn_another", ctx) if cb else back_kb(lang, ctx=ctx)
        await del_msg(q)
        if img_url:
            try:
                await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                    caption=caption[:1024], parse_mode="Markdown", reply_markup=kb); return
            except Exception: pass
        await ctx.bot.send_message(chat_id=q.message.chat_id, text=caption[:4096],
            parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang, ctx=ctx))

# ── HELPER: moon phase ────────────────────────────────────────────────────────
def get_moon_phase(for_date: date):
    known_new  = date(2024, 1, 11)
    cycle_day  = (for_date - known_new).days % 29.53
    if   cycle_day < 1.85:  emoji, idx = "🌑", 0
    elif cycle_day < 7.38:  emoji, idx = "🌒", 1
    elif cycle_day < 9.22:  emoji, idx = "🌓", 2
    elif cycle_day < 14.77: emoji, idx = "🌔", 3
    elif cycle_day < 16.61: emoji, idx = "🌕", 4
    elif cycle_day < 22.15: emoji, idx = "🌖", 5
    elif cycle_day < 23.99: emoji, idx = "🌗", 6
    else:                   emoji, idx = "🌘", 7
    illum = round((1 - abs(cycle_day - 14.77) / 14.77) * 100)
    return emoji, idx, cycle_day, illum

# ── HELPER: get zodiac ────────────────────────────────────────────────────────
def get_zodiac(month: int, day: int) -> str:
    for (sm, sd), (em, ed), sign in ZODIAC_RANGES:
        if (month == sm and day >= sd) or (month == em and day <= ed):
            return sign
    return "Aries"

# ── CORE HANDLERS ────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(tx("ru","choose_lang"), parse_mode="Markdown", reply_markup=lang_kb())

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await update.message.reply_text(tx(lang,"main_menu"), parse_mode="Markdown", reply_markup=main_menu_kb(lang))

async def choose_lang_h(update, ctx):
    q = update.callback_query; await safe_answer(q)
    await safe_edit(q, tx("ru","choose_lang"), reply_markup=lang_kb())

async def setlang_h(update, ctx):
    q = update.callback_query; await safe_answer(q)
    lang = q.data.split("_")[1]; ctx.user_data["lang"] = lang
    name = q.from_user.first_name or "explorer"
    await safe_edit(q, tx(lang,"lang_set")+"\n\n"+tx(lang,"start_msg",name=name), reply_markup=main_menu_kb(lang))

async def back_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    await safe_edit(q, tx(lang,"main_menu"), reply_markup=main_menu_kb(lang))

async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(ctx)
    await update.message.reply_text(tx(lang,"unknown"), reply_markup=main_menu_kb(lang))

# ── APOD ─────────────────────────────────────────────────────────────────────
async def _send_apod(q, ctx, params=None):
    lang = get_lang(ctx)
    try:
        data  = nasa_req("/planetary/apod", params)
        title = data.get("title",""); expl = strip_html(data.get("explanation",""))[:900]
        url   = data.get("url",""); hdurl = data.get("hdurl", url)
        mtype = data.get("media_type","image"); d = data.get("date","")
        copy_ = data.get("copyright","NASA").strip().replace("\n"," ")
        caption = f"🌌 *{title}*\n📅 {d}  |  © {copy_}\n\n{expl}…\n\n[🔗 HD]({hdurl})"
        kb = action_kb(lang,"apod_random","btn_more_rnd",ctx) if not params else back_kb(lang,ctx=ctx)
        await del_msg(q)
        if mtype == "image":
            await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=url,
                caption=caption[:1024], parse_mode="Markdown", reply_markup=kb)
        else:
            await ctx.bot.send_message(chat_id=q.message.chat_id,
                text=caption[:4096]+f"\n\n[▶️]({url})", parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')} APOD: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

async def apod_h(update, ctx):
    q = update.callback_query; await safe_answer(q); await safe_edit(q,"⏳..."); await _send_apod(q,ctx)

async def apod_random_h(update, ctx):
    q = update.callback_query; await safe_answer(q); await safe_edit(q,"🎲...")
    s = date(1995,6,16); rnd = s + timedelta(days=random.randint(0,(date.today()-s).days))
    await _send_apod(q, ctx, {"date": rnd.isoformat()})

# ── MARS ──────────────────────────────────────────────────────────────────────
async def mars_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🤖...")
    try:
        photos = []
        for sol in random.sample([100,200,300,500,750,1000,1200,1500],4):
            try:
                r = requests.get(f"{NASA_BASE}/mars-photos/api/v1/rovers/curiosity/photos",
                    params={"sol":sol,"api_key":NASA_API_KEY,"page":1}, timeout=10)
                if r.status_code == 200:
                    photos = r.json().get("photos",[])
                    if photos: break
            except Exception: continue
        if photos:
            p    = random.choice(photos[:20])
            fact = random.choice(MARS_FACTS.get(lang, MARS_FACTS["en"]))
            cap  = (f"🤖 *{p['rover']['name']}*\n📅 {p['earth_date']}  |  Sol {p['sol']}\n"
                    f"📷 {p['camera']['full_name']}\n\n💡 {fact}")
            await del_msg(q)
            await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=p["img_src"],
                caption=cap, parse_mode="Markdown", reply_markup=action_kb(lang,"mars","btn_another",ctx))
            return
    except Exception as e:
        logger.error(f"Mars: {e}")
    await send_nasa_image(q, ctx, MARS_Q, "mars")

async def mars_rovers_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🤖...")
    try:
        rover = random.choice(ROVER_NAMES)
        for sol in random.sample(list(range(50,1800)),8):
            try:
                r = requests.get(f"{NASA_BASE}/mars-photos/api/v1/rovers/{rover}/photos",
                    params={"sol":sol,"api_key":NASA_API_KEY,"page":1}, timeout=10)
                if r.status_code != 200: continue
                photos = r.json().get("photos",[])
                if not photos: continue
                p = random.choice(photos[:15]); img = p.get("img_src","")
                if not img: continue
                cap = (f"🤖 *{p.get('rover',{}).get('name',rover.title())}*\n"
                       f"📅 {p.get('earth_date','')}  |  Sol {p.get('sol',sol)}\n"
                       f"📷 {p.get('camera',{}).get('full_name','—')}")
                await del_msg(q)
                await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img, caption=cap,
                    parse_mode="Markdown", reply_markup=action_kb(lang,"mars_rovers","btn_other_rv",ctx))
                return
            except Exception: continue
        await safe_edit(q, tx(lang,"no_img"), reply_markup=back_kb(lang,ctx=ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

# ── ASTEROIDS ─────────────────────────────────────────────────────────────────
async def asteroids_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"☄️...")
    try:
        today = date.today().isoformat()
        data  = nasa_req("/neo/rest/v1/feed",{"start_date":today,"end_date":today})
        neos  = data["near_earth_objects"].get(today,[])
        if not neos:
            await safe_edit(q, tx(lang,"no_data"), reply_markup=back_kb(lang,"asteroids",ctx)); return
        danger = sum(1 for a in neos if a["is_potentially_hazardous_asteroid"])
        neos_s = sorted(neos, key=lambda a: float(a["close_approach_data"][0]["miss_distance"]["kilometers"])
                               if a["close_approach_data"] else 9e99)
        text = f"☄️ *{today}*\n📊 {len(neos)} NEOs  |  ⚠️ {danger}\n\n"
        for i, ast in enumerate(neos_s[:5], 1):
            name   = ast["name"].replace("(","").replace(")","").strip()
            d_min  = ast["estimated_diameter"]["meters"]["estimated_diameter_min"]
            d_max  = ast["estimated_diameter"]["meters"]["estimated_diameter_max"]
            hz     = tx(lang,"hazard_yes") if ast["is_potentially_hazardous_asteroid"] else tx(lang,"hazard_no")
            ap     = ast["close_approach_data"][0] if ast["close_approach_data"] else {}
            speed  = ap.get("relative_velocity",{}).get("kilometers_per_hour","?")
            dist_ld= ap.get("miss_distance",{}).get("lunar","?")
            try: speed = f"{float(speed):,.0f} km/h"
            except Exception: pass
            try: dist_ld = f"{float(dist_ld):.2f} LD"
            except Exception: pass
            text  += f"*{i}. {name}*  {hz}\n📏 {d_min:.0f}–{d_max:.0f}m  🚀 {speed}  📍 {dist_ld}\n\n"
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"asteroids",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

# ── ISS ───────────────────────────────────────────────────────────────────────
async def iss_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🛸...")
    try:
        pos = get_json("http://api.open-notify.org/iss-now.json", timeout=10)
        lat = float(pos["iss_position"]["latitude"]); lon = float(pos["iss_position"]["longitude"])
        ts  = datetime.utcfromtimestamp(pos["timestamp"]).strftime("%H:%M:%S UTC")
        try:
            crew_r = requests.get("http://api.open-notify.org/astros.json", timeout=10)
            people = crew_r.json().get("people",[]) if crew_r.ok else []
        except Exception: people = []
        iss_crew = [p["name"] for p in people if p.get("craft")=="ISS"]
        crew_str = "\n".join(f"   👨‍🚀 {n}" for n in iss_crew) or f"   {tx(lang,'iss_no_crew')}"
        text = (f"🛸 *ISS — {ts}*\n\n🌍 `{lat:.4f}°` | 🌏 `{lon:.4f}°`\n"
                f"⚡ ~27,600 km/h  |  🏔 ~408 km\n\n👨‍🚀 Crew ({len(iss_crew)}):\n{crew_str}\n\n"
                f"[{tx(lang,'iss_map')}](https://www.google.com/maps?q={lat},{lon})")
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"iss",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')} ISS: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

# ── EXOPLANETS ────────────────────────────────────────────────────────────────
async def exoplanets_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    sel  = random.sample(KNOWN_EXOPLANETS, min(4,len(KNOWN_EXOPLANETS)))
    text = "🔭 *Exoplanets*\n\n"
    for p in sel:
        note = p["note"].get(lang, p["note"]["en"])
        text += (f"🪐 *{p['name']}* — {p['star']}\n"
                 f"   📅 {p['year']}  |  📏 {p['radius']}R🌍  |  🔄 {p['period']}d  |  📡 {p['dist_ly']}ly\n"
                 f"   💡 _{note}_\n\n")
    text += "[🔗 NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu)"
    await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"exoplanets",ctx))

# ── SPACE WEATHER ─────────────────────────────────────────────────────────────
async def spaceweather_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🌞...")
    try:
        end   = date.today().isoformat()
        start = (date.today()-timedelta(days=7)).isoformat()
        flares = nasa_req("/DONKI/FLR",{"startDate":start,"endDate":end}) or []
        cmes   = nasa_req("/DONKI/CME",{"startDate":start,"endDate":end}) or []
        storms = nasa_req("/DONKI/GST",{"startDate":start,"endDate":end}) or []
        text = f"🌞 *Space Weather (7d)*\n\n⚡ Flares: *{len(flares)}*\n"
        for f in flares[-3:]:
            text += f"   • {f.get('classType','?')} — {(f.get('peakTime') or '')[:16].replace('T',' ')}\n"
        text += f"\n🌊 CME: *{len(cmes)}*\n"
        for c in cmes[-2:]:
            text += f"   • {(c.get('startTime') or '')[:16].replace('T',' ')}\n"
        text += f"\n🧲 Storms: *{len(storms)}*\n"
        for s in storms[-2:]:
            kp_i = s.get("allKpIndex",[{}]); kp_v = kp_i[-1].get("kpIndex","?") if kp_i else "?"
            text += f"   • {(s.get('startTime') or '')[:16].replace('T',' ')}  Kp: *{kp_v}*\n"
        text += "\n[NOAA](https://www.swpc.noaa.gov)"
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"spaceweather",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

# ── LAUNCHES ──────────────────────────────────────────────────────────────────
async def launches_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🚀...")
    try:
        data    = get_json("https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=7&ordering=net&mode=list",timeout=15)
        launches= data.get("results",[])
        if not launches:
            await safe_edit(q, tx(lang,"no_data"), reply_markup=back_kb(lang,ctx=ctx)); return
        text = "🚀 *Upcoming Launches*\n\n"
        for i, lc in enumerate(launches[:6], 1):
            if not isinstance(lc, dict): continue
            try:
                name   = str(lc.get("name","?"))
                rocket = str((lc.get("rocket") or {}).get("configuration",{}).get("name","?"))
                prov   = str((lc.get("launch_service_provider") or {}).get("name","?"))
                net    = str(lc.get("net","?"))
                stat_a = str((lc.get("status") or {}).get("abbrev","?"))
                emoji  = {"Go":"✅","TBD":"❓","TBC":"🔸","Success":"🎉","Failure":"❌"}.get(stat_a,"🕐")
                try:
                    dt  = datetime.fromisoformat(net.replace("Z","+00:00"))
                    net = dt.strftime("%d.%m.%Y %H:%M UTC")
                except Exception: pass
                text += f"*{i}. {name}*\n   🚀 {rocket}  |  {prov}\n   ⏰ {net}  {emoji}\n\n"
            except Exception: continue
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"launches",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

# ── SATELLITES ────────────────────────────────────────────────────────────────
async def satellites_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"📡...")
    try:
        sl     = get_json("https://api.spacexdata.com/v4/starlink", timeout=10)
        total  = len(sl)
        active = sum(1 for s in sl if isinstance(s,dict) and not (s.get("spaceTrack") or {}).get("DECAY_DATE"))
    except Exception: total = active = "?"
    await safe_edit(q, f"📡 *Satellites*\n\n🌍 In orbit: ~9,000+\n🛸 *Starlink:* {total} total, {active} active\n\n[🔗 n2yo.com](https://www.n2yo.com)",
        reply_markup=back_kb(lang,"satellites",ctx))

# ── METEORS ───────────────────────────────────────────────────────────────────
async def meteors_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    text = "🌠 *Meteor Showers*\n\n"
    for m in METEOR_SHOWERS:
        name  = m["name"].get(lang, m["name"]["en"])
        text += f"✨ *{name}* — {m['peak']}\n   ⚡ {m['speed']}  |  🌠 {m['rate']}  |  _{m['parent']}_\n   📌 {m['best']}\n\n"
    await safe_edit(q, text, reply_markup=back_kb(lang,ctx=ctx))

# ── PLANETS ───────────────────────────────────────────────────────────────────
async def planets_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    p    = random.choice(PLANETS)
    fact = p["fact"].get(lang, p["fact"]["en"])
    text = (f"🪐 *{p['name']}*\n\n📏 {p['radius']}  |  📡 {p['dist']}\n"
            f"🔄 {p['period']}  |  🌅 {p['day']}\n🌡 {p['temp']}  |  🌙 {p['moons']}\n\n💡 *{fact}*")
    await safe_edit(q, text, reply_markup=back_kb(lang,"planets",ctx))

# ── MOON ─────────────────────────────────────────────────────────────────────
async def moon_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    emoji, idx, cycle_day, illum = get_moon_phase(date.today())
    phases     = tx(lang,"moon_phases")
    phase_name = phases[idx] if isinstance(phases,list) else "?"
    text = (f"{emoji} *Moon Phase*\n\n📅 {date.today()}\n🌙 *{phase_name}*\n"
            f"💡 ~{illum}%  |  Day {cycle_day:.1f}/29.5")
    await safe_edit(q, text, reply_markup=back_kb(lang,"moon",ctx))

# ── TELESCOPES ────────────────────────────────────────────────────────────────
async def telescopes_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    await safe_edit(q,
        "🔬 *Telescopes*\n\n🌌 *JWST* — 6.5m, L2\n🔭 *Hubble* — 2.4m, LEO\n📡 *VLT* — 4×8.2m\n"
        "🌐 *FAST* — 500m (radio)\n🔭 *ELT (~2028)* — 39m (largest optical)\n"
        "🛸 *Chandra* — X-ray\n🌊 *LIGO* — gravitational waves",
        reply_markup=back_kb(lang,ctx=ctx))

# ── SPACE FACT ────────────────────────────────────────────────────────────────
async def spacefact_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    fact = random.choice(SPACE_FACTS.get(lang, SPACE_FACTS["en"]))
    await safe_edit(q, f"⭐ *Fact*\n\n{fact}", reply_markup=back_kb(lang,"spacefact",ctx))

# ── CHANNELS ──────────────────────────────────────────────────────────────────
async def channels_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    await safe_edit(q, CHANNELS_TEXT.get(lang, CHANNELS_TEXT["ru"]), reply_markup=back_kb(lang,ctx=ctx))

# ── LIVE HANDLERS ─────────────────────────────────────────────────────────────
async def live_solar_wind_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        r = requests.get("https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json",timeout=12)
        r.raise_for_status()
        data   = r.json(); latest = data[-1] if data else {}
        speed  = latest[2] if len(latest)>2 else "?"
        density= latest[1] if len(latest)>1 else "?"
        time_str = str(latest[0])[:16].replace("T"," ") if latest else "?"
        try:
            spd_f  = float(speed)
            status = "🟢 Calm" if spd_f<400 else "🟡 Moderate" if spd_f<600 else "🟠 Strong" if spd_f<800 else "🔴 STORM"
        except Exception: status = "?"
        try: speed   = f"{float(speed):,.0f} km/s"
        except Exception: pass
        try: density = f"{float(density):.2f} p/cm³"
        except Exception: pass
        await safe_edit(q, f"🔴 *LIVE: Solar Wind*\n⏱ {time_str} UTC\n\n{status}\n🚀 {speed}  |  🔵 {density}\n\n[NOAA](https://www.swpc.noaa.gov)",
            reply_markup=back_kb(lang,"live_solar_wind",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

async def live_kp_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",timeout=12)
        r.raise_for_status()
        data    = r.json(); current = data[-1] if data else {}
        kp_now  = current.get("kp_index", current.get("Kp","?"))
        time_   = current.get("time_tag","")[:16].replace("T"," ")
        try:
            kp_val = float(kp_now)
            state  = "🟢 Quiet" if kp_val<4 else "🟡 Minor" if kp_val<5 else "🟠 Moderate" if kp_val<6 else "🔴 Strong" if kp_val<8 else "🚨 G5"
            aurora = "Polar only" if kp_val<4 else "Scandinavia/Canada" if kp_val<6 else "Mid-latitudes" if kp_val<8 else "Equatorial"
        except Exception: state = aurora = "?"
        await safe_edit(q, f"🔴 *LIVE: Kp-index*\n⏱ {time_} UTC\n\nKp: *{kp_now}*  |  {state}\n🌈 Aurora: {aurora}",
            reply_markup=back_kb(lang,"live_kp",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

async def live_flares_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json",timeout=12)
        r.raise_for_status()
        xray   = r.json(); latest = xray[-1] if xray else {}
        flux   = latest.get("flux","?"); time_ = latest.get("time_tag","")[:16].replace("T"," ")
        try:
            fv   = float(flux)
            cls_ = "🔴 X" if fv>=1e-4 else "🟠 M" if fv>=1e-5 else "🟡 C" if fv>=1e-6 else "🟢 B" if fv>=1e-7 else "⚪ A"
            fs   = f"{fv:.2e} W/m²"
        except Exception: cls_ = "?"; fs = str(flux)
        await safe_edit(q, f"🔴 *LIVE: Solar Flares*\n⏱ {time_} UTC\n\n⚡ *{cls_}* — `{fs}`",
            reply_markup=back_kb(lang,"live_flares",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

async def live_iss_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        pos = requests.get("http://api.open-notify.org/iss-now.json", timeout=10).json()
        lat = float(pos["iss_position"]["latitude"]); lon = float(pos["iss_position"]["longitude"])
        ts  = datetime.utcfromtimestamp(pos["timestamp"]).strftime("%H:%M:%S UTC")
        try:
            cr     = requests.get("http://api.open-notify.org/astros.json", timeout=8)
            people = cr.json().get("people",[]) if cr.ok else []
            iss_c  = [p["name"] for p in people if p.get("craft")=="ISS"]
        except Exception: iss_c = []
        text = (f"🔴 *LIVE: ISS*\n⏱ {ts}\n\n🌍 `{lat:+.4f}°` | 🌏 `{lon:+.4f}°`\n"
                f"⚡ ~27,576 km/h  |  ~408 km\n👨‍🚀 {', '.join(iss_c) or tx(lang,'iss_no_crew')}\n\n"
                f"[{tx(lang,'iss_map')}](https://www.google.com/maps?q={lat},{lon})")
        await safe_edit(q, text, reply_markup=back_kb(lang,"live_iss",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

async def live_radiation_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/goes/primary/integral-protons-6-hour.json",timeout=12)
        r.raise_for_status()
        protons = r.json(); latest = protons[-1] if protons else {}
        flux_p  = latest.get("flux","?"); time_p = latest.get("time_tag","")[:16].replace("T"," ")
        try:
            fp = float(flux_p)
            rl = "🚨 S5" if fp>=1e4 else "🔴 S4" if fp>=1e3 else "🟠 S3" if fp>=1e2 else "🟡 S2" if fp>=10 else "🟢 S1" if fp>=1 else "⚪ BG"
            fs = f"{fp:.2e} p/(cm²·s·sr)"
        except Exception: rl = "?"; fs = str(flux_p)
        await safe_edit(q, f"🔴 *LIVE: Radiation*\n⏱ {time_p} UTC\n\n☢️ `{fs}`\n🌡 *{rl}*",
            reply_markup=back_kb(lang,"live_radiation",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

async def live_aurora_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",timeout=12)
        r.raise_for_status()
        data    = r.json(); current = data[-1] if data else {}
        kp      = current.get("kp_index", current.get("Kp","?"))
        time_   = current.get("time_tag","")[:16].replace("T"," ")
        try:
            kp_val  = float(kp)
            forecast = ("🌈 Mid-latitudes (Moscow, Kyiv)" if kp_val>=7 else
                       "🌈 Scandinavia, Canada, Alaska" if kp_val>=5 else
                       "🌈 Near polar circle" if kp_val>=4 else "🌈 Polar regions only")
        except Exception: forecast = "?"
        await safe_edit(q, f"🔴 *Aurora Forecast*\n⏱ {time_} UTC\n\nKp: *{kp}*\n{forecast}",
            reply_markup=back_kb(lang,"live_aurora_forecast",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

async def live_geomag_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        end    = date.today().isoformat()
        start  = (date.today()-timedelta(days=2)).isoformat()
        storms = nasa_req("/DONKI/GST",{"startDate":start,"endDate":end}) or []
        text   = f"🔴 *Geomagnetic Storms (2d)*\n\nEvents: *{len(storms)}*\n\n"
        for s in (storms[-5:] if storms else []):
            t    = (s.get("startTime") or "?")[:16].replace("T"," ")
            kp_i = s.get("allKpIndex",[{}]); kp_v = kp_i[-1].get("kpIndex","?") if kp_i else "?"
            text+= f"• {t} UTC  Kp *{kp_v}*\n"
        if not storms: text += tx(lang,"live_nodata")
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"live_geomagnetic_alert",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

async def live_sunspot_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json",timeout=12)
        r.raise_for_status()
        data = r.json(); latest = data[-1] if data else {}
        ssn  = latest.get("smoothed_ssn", latest.get("ssn","?"))
        await safe_edit(q, f"🔴 *Sunspots (Cycle 25)*\n\nWolf number: *{ssn}*\n\nCycle 25 near maximum — more flares expected.",
            reply_markup=back_kb(lang,"live_sunspot",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

async def live_epic_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        data = nasa_req("/EPIC/api/natural")
        if not data:
            await safe_edit(q, tx(lang,"no_img"), reply_markup=back_kb(lang,ctx=ctx)); return
        item     = data[0]; date_str = item.get("date","")[:10].replace("-","/")
        img      = item.get("image","")
        url      = f"https://epic.gsfc.nasa.gov/archive/natural/{date_str}/png/{img}.png"
        caption  = f"🌍 *EPIC Live — Earth*\n📅 {date_str}\n\nDSCOVR satellite (L1)."
        await del_msg(q)
        try:
            await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=url, caption=caption,
                parse_mode="Markdown", reply_markup=back_kb(lang,"live_epic_latest",ctx))
        except Exception:
            await ctx.bot.send_message(chat_id=q.message.chat_id, text=caption+f"\n\n[Open]({url})",
                parse_mode="Markdown", reply_markup=back_kb(lang,ctx=ctx), disable_web_page_preview=True)
    except Exception:
        await safe_edit(q, tx(lang,"no_img"), reply_markup=back_kb(lang,ctx=ctx))

async def live_sat_count_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        sl     = get_json("https://api.spacexdata.com/v4/starlink", timeout=10)
        total  = len(sl)
        active = sum(1 for s in sl if isinstance(s,dict) and not (s.get("spaceTrack") or {}).get("DECAY_DATE"))
    except Exception: total = active = "?"
    await safe_edit(q, f"🔴 *Starlink*\n\nTotal: *{total}*  |  Active: *{active}*\n\nAll satellites: ~9,000+ in orbit.",
        reply_markup=back_kb(lang,"live_satellite_count",ctx))

# ══════════════════════════════════════════════════════════════════════════════
# NEW INTERACTIVE FEATURES
# ══════════════════════════════════════════════════════════════════════════════

# ── NOTIFICATIONS MENU ────────────────────────────────────────────────────────
async def notifications_menu_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    subs    = load_subscribers()
    chat_id = q.message.chat_id
    await safe_edit(q, tx(lang,"notif_title"), reply_markup=notifications_kb(lang, subs, chat_id))

async def notif_toggle_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    topic   = q.data.replace("notif_toggle_","")
    chat_id = q.message.chat_id
    subs    = load_subscribers()
    if topic not in subs: subs[topic] = []
    if chat_id in subs[topic]:
        subs[topic].remove(chat_id)
        msg = tx(lang,"notif_unsubscribed")
    else:
        subs[topic].append(chat_id)
        msg = tx(lang,"notif_subscribed")
    save_subscribers(subs)
    try: await q.answer(msg, show_alert=False)
    except Exception: pass
    await safe_edit(q, tx(lang,"notif_title"), reply_markup=notifications_kb(lang, subs, chat_id))

# ── NOTIFICATIONS SCHEDULER JOBS ──────────────────────────────────────────────
async def job_asteroid_alert(context: ContextTypes.DEFAULT_TYPE):
    """Daily asteroid danger check — sends to subscribers."""
    subs = load_subscribers()
    chat_ids = subs.get("asteroids", [])
    if not chat_ids: return
    try:
        today   = date.today().isoformat()
        data    = nasa_req("/neo/rest/v1/feed",{"start_date":today,"end_date":today})
        neos    = data["near_earth_objects"].get(today,[])
        danger  = [a for a in neos if a["is_potentially_hazardous_asteroid"]]
        if not danger: return
        msg = f"☄️ *Asteroid Flyby Alert!*\n📅 {today}\n\n⚠️ *{len(danger)} potentially hazardous NEO(s) today!*\n\n"
        for ast in danger[:3]:
            name   = ast["name"].replace("(","").replace(")","").strip()
            ap     = ast["close_approach_data"][0] if ast["close_approach_data"] else {}
            dist   = ap.get("miss_distance",{}).get("lunar","?")
            speed  = ap.get("relative_velocity",{}).get("kilometers_per_hour","?")
            d_max  = ast["estimated_diameter"]["meters"]["estimated_diameter_max"]
            try: dist  = f"{float(dist):.1f} LD"
            except Exception: pass
            try: speed = f"{float(speed):,.0f} km/h"
            except Exception: pass
            msg += f"🔴 *{name}*\n   📏 ~{d_max:.0f}m  📍 {dist}  🚀 {speed}\n\n"
        msg += "[🔗 NASA NEO](https://cneos.jpl.nasa.gov)"
        for chat_id in chat_ids:
            try:
                await context.bot.send_message(chat_id=chat_id, text=msg[:4096],
                    parse_mode="Markdown", disable_web_page_preview=True)
            except Exception as e:
                logger.warning(f"Alert send fail {chat_id}: {e}")
    except Exception as e:
        logger.error(f"job_asteroid_alert: {e}")

async def job_meteor_alert(context: ContextTypes.DEFAULT_TYPE):
    """Weekly meteor shower reminder."""
    subs     = load_subscribers()
    chat_ids = subs.get("meteors", [])
    if not chat_ids: return
    today    = date.today()
    msg_parts = []
    for shower in METEOR_SHOWERS:
        try:
            peak_str = shower["peak"]
            parts    = peak_str.split("-")[0].strip()
            peak_dt  = datetime.strptime(f"{parts} {today.year}", "%d %b %Y").date()
            days_to  = (peak_dt - today).days
            if 0 <= days_to <= 7:
                name = shower["name"].get("ru", shower["name"]["en"])
                msg_parts.append(f"🌠 *{name}*\n   📅 Пик: {peak_str}\n   🌠 {shower['rate']}  ⚡ {shower['speed']}\n   📌 {shower['best']}")
        except Exception: continue
    if not msg_parts: return
    msg = "🌠 *Метеорный поток на этой неделе!*\n\n" + "\n\n".join(msg_parts)
    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=msg[:4096], parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Meteor alert fail {chat_id}: {e}")

async def job_space_weather_alert(context: ContextTypes.DEFAULT_TYPE):
    """Alert when Kp >= 5 (moderate geomagnetic storm)."""
    subs     = load_subscribers()
    chat_ids = subs.get("space_weather", [])
    if not chat_ids: return
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",timeout=12)
        r.raise_for_status()
        data   = r.json()
        recent = [float(d.get("kp_index", d.get("Kp",0))) for d in data[-5:] if d]
        kp_max = max(recent) if recent else 0
        if kp_max < 5: return
        state  = "🟠 G2" if kp_max<6 else "🔴 G3" if kp_max<7 else "🚨 G4+" 
        aurora = "Scandinavia, Canada" if kp_max<6 else "Central Europe, Northern US" if kp_max<7 else "Mid-latitudes"
        msg    = (f"🌞 *Space Weather Alert!*\n\nKp-index: *{kp_max:.1f}* {state}\n"
                  f"🌈 Aurora visible: {aurora}\n\n[NOAA](https://www.swpc.noaa.gov)")
        for chat_id in chat_ids:
            try:
                await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown",
                    disable_web_page_preview=True)
            except Exception as e:
                logger.warning(f"SW alert fail {chat_id}: {e}")
    except Exception as e:
        logger.error(f"job_space_weather_alert: {e}")

async def job_lunar_alert(context: ContextTypes.DEFAULT_TYPE):
    """Notify on New Moon and Full Moon — good for photographers."""
    subs     = load_subscribers()
    chat_ids = subs.get("lunar", [])
    if not chat_ids: return
    emoji, idx, cycle_day, illum = get_moon_phase(date.today())
    if idx not in (0, 4): return  # Only alert on New/Full Moon
    phase_names = {"ru": ["Новолуние","Полнолуние"], "en": ["New Moon","Full Moon"]}
    is_full     = (idx == 4)
    photo_tip   = ("📸 Лучший момент для фото ночного пейзажа — полнолуние!" if is_full
                   else "📸 Идеальное время для фото звёздного неба — новолуние! Небо темнее.")
    msg = (f"{emoji} *Лунный Календарь*\n\n"
           f"Сегодня: *{'Полнолуние' if is_full else 'Новолуние'}*\n"
           f"Освещённость: ~{illum}%\n\n{photo_tip}\n\n"
           f"🔭 Рекомендуемое оборудование: ISO 800-3200, f/2.8, 30 сек выдержка")
    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Lunar alert fail {chat_id}: {e}")

async def job_check_capsules(context: ContextTypes.DEFAULT_TYPE):
    """Send time capsule messages when their delivery date arrives."""
    capsules     = load_capsules()
    today_str    = date.today().isoformat()
    remaining    = []
    for cap in capsules:
        if cap.get("deliver_on","") <= today_str:
            try:
                text = (f"⏳ *Капсула времени*\n\n"
                        f"Привет! Ровно год назад ты написал себе:\n\n"
                        f"_{cap['message']}_\n\n"
                        f"🚀 Как дела? Сбылось ли что-то из задуманного?")
                await context.bot.send_message(chat_id=cap["chat_id"], text=text[:4096],
                    parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Capsule delivery fail: {e}")
        else:
            remaining.append(cap)
    if len(remaining) != len(capsules):
        save_capsules(remaining)

# ── PLANET CALCULATOR — ConversationHandler ────────────────────────────────────
async def planet_calc_start(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    ctx.user_data["planet_calc_lang"] = lang
    await del_msg(q)
    await ctx.bot.send_message(chat_id=q.message.chat_id,
        text=tx(lang,"planet_calc_ask_date"), parse_mode="Markdown")
    return PLANET_DATE

async def planet_date_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = ctx.user_data.get("planet_calc_lang","ru")
    text = update.message.text.strip()
    try:
        bday = datetime.strptime(text, "%d.%m.%Y").date()
        if bday > date.today() or bday.year < 1900:
            raise ValueError("Invalid date")
        ctx.user_data["planet_bday"] = bday
        await update.message.reply_text(tx(lang,"planet_calc_ask_weight"), parse_mode="Markdown")
        return PLANET_WEIGHT
    except Exception:
        await update.message.reply_text(tx(lang,"planet_calc_error_date"), parse_mode="Markdown")
        return PLANET_DATE

async def planet_weight_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = ctx.user_data.get("planet_calc_lang","ru")
    try:
        weight = float(update.message.text.strip().replace(",","."))
        if not (1 <= weight <= 500): raise ValueError("Out of range")
    except Exception:
        await update.message.reply_text(tx(lang,"planet_calc_error_weight"), parse_mode="Markdown")
        return PLANET_WEIGHT

    bday    = ctx.user_data.get("planet_bday")
    today   = date.today()
    age_earth_days = (today - bday).days
    age_earth_years = age_earth_days / 365.25

    lines = [f"🪐 *Ваш возраст и вес на других планетах*\n"]
    lines.append(f"🌍 *Земля:* {age_earth_years:.1f} лет  |  {weight:.1f} кг\n")

    for pname, gravity in PLANET_GRAVITY.items():
        if pname == "🌍 Earth": continue
        year_days = PLANET_YEAR_DAYS[pname]
        age_planet = age_earth_days / year_days
        w_planet   = weight * gravity
        age_str    = f"{age_planet:.1f}"
        w_str      = f"{w_planet:.1f}"
        emoji_age  = "👶" if age_planet < 3 else "🧑" if age_planet < 20 else "🧓" if age_planet < 80 else "🏆"
        lines.append(f"{pname}: {emoji_age} *{age_str} лет*  |  ⚖️ *{w_str} кг*")

    lines.append(f"\n🌙 *Луна:* ⚖️ {weight*0.165:.1f} кг (gravity 16.5%)")
    lines.append(f"\n💡 Ты прожил *{age_earth_days:,}* земных дней — это *{age_earth_days*24:,}* часов!")

    result = "\n".join(lines)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ Интерактив", callback_data="cat_interactive"),
        InlineKeyboardButton("◀️ Меню", callback_data="back")
    ]])
    await update.message.reply_text(result[:4096], parse_mode="Markdown", reply_markup=kb)
    return ConversationHandler.END

async def planet_calc_cancel(update, ctx):
    lang = ctx.user_data.get("planet_calc_lang","ru")
    await update.message.reply_text("❌ Отменено", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ Меню", callback_data="back")]]))
    return ConversationHandler.END

# ── SPACE NAME GENERATOR ──────────────────────────────────────────────────────
async def space_name_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    user    = q.from_user
    name    = (user.first_name or "Explorer").upper()
    seed    = sum(ord(c) for c in name) + date.today().toordinal()
    random.seed(seed)
    prefix  = random.choice(NAME_PREFIXES)
    suffix  = random.choice(NAME_SUFFIXES)
    code    = random.choice(STAR_CODES)
    year    = date.today().year
    callsign    = f"{prefix}-{name[:3]}-{suffix}"
    star_name   = f"{prefix} {name[:4].title()} {code}-{year}"
    constellation = random.choice(["Orion","Lyra","Cygnus","Perseus","Aquila","Centaurus","Vela","Puppis"])
    spec_type = random.choice(["G2V ☀️","K5V 🟠","M4V 🔴","F8V 🟡","A1V 🔵"])
    random.seed()  # reset seed

    text = (tx(lang,"name_gen_title") +
            f"👨‍🚀 *Позывной астронавта:*\n`{callsign}`\n\n"
            f"⭐ *Твоя звезда открыта:*\n`{star_name}`\n"
            f"📡 Созвездие: {constellation}\n"
            f"🔬 Спектральный тип: {spec_type}\n"
            f"📍 Расстояние: {random.randint(10,9999)} световых лет\n\n"
            f"🏷 *Поделись своим именем с миром!*")
    await safe_edit(q, text, reply_markup=back_kb(lang,"space_name",ctx))

# ── SCI-FI HOROSCOPE MENU ─────────────────────────────────────────────────────
async def horoscope_menu_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    ctx.user_data["horoscope_lang"] = lang
    await del_msg(q)
    await ctx.bot.send_message(chat_id=q.message.chat_id,
        text=tx(lang,"horoscope_ask"), parse_mode="Markdown")
    return HOROSCOPE_BDAY

async def horoscope_date_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = ctx.user_data.get("horoscope_lang","ru")
    text = update.message.text.strip()
    try:
        parts = text.split(".")
        if len(parts) < 2: raise ValueError
        day, month = int(parts[0]), int(parts[1])
        if not (1<=day<=31 and 1<=month<=12): raise ValueError
    except Exception:
        await update.message.reply_text(tx(lang,"horoscope_error"), parse_mode="Markdown")
        return HOROSCOPE_BDAY

    sign  = get_zodiac(month, day)
    horoscopes = HOROSCOPES.get(lang, HOROSCOPES["en"])
    horoscope  = horoscopes.get(sign, horoscopes.get("Aries",""))

    # Add today's space weather flavour
    try:
        r     = requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",timeout=5)
        data  = r.json()
        kp    = float(data[-1].get("kp_index", data[-1].get("Kp",2))) if data else 2
        sw_tip = (f"\n\n🌞 *Сегодняшний Kp-индекс:* {kp:.1f} — " +
                  ("мощные энергии! 🔴" if kp>=5 else "умеренная активность 🟡" if kp>=3 else "спокойно, время планировать 🟢"))
    except Exception: sw_tip = ""

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Ещё раз", callback_data="horoscope_menu"),
        InlineKeyboardButton("◀️ Меню", callback_data="back")
    ]])
    await update.message.reply_text(horoscope + sw_tip, parse_mode="Markdown", reply_markup=kb)
    return ConversationHandler.END

async def horoscope_cancel(update, ctx):
    await update.message.reply_text("❌ Отменено")
    return ConversationHandler.END

# ── QUIZ ──────────────────────────────────────────────────────────────────────
async def quiz_start_menu_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    ctx.user_data["quiz_score"] = 0
    ctx.user_data["quiz_q"]     = 0
    ctx.user_data["quiz_answered"] = False
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"quiz_btn_start"), callback_data="quiz_next")]])
    await safe_edit(q, tx(lang,"quiz_start"), reply_markup=kb)

async def quiz_show_question(q, ctx, q_index: int):
    lang      = get_lang(ctx)
    question  = QUIZ_QUESTIONS[q_index]
    q_text    = question["q"].get(lang, question["q"]["en"])
    opts_text = "\n".join(f"{chr(65+i)}. {opt}" for i, opt in enumerate(question["options"]))
    text      = f"🧠 *Вопрос {q_index+1}/10*\n\n{q_text}\n\n{opts_text}"
    ctx.user_data["quiz_answered"] = False
    await safe_edit(q, text, reply_markup=quiz_kb(lang, q_index))

async def quiz_next_h(update, ctx):
    q    = update.callback_query; await safe_answer(q)
    qi   = ctx.user_data.get("quiz_q", 0)
    await quiz_show_question(q, ctx, qi)

async def quiz_answer_h(update, ctx):
    q    = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    if ctx.user_data.get("quiz_answered", False): return  # ignore double-tap
    ctx.user_data["quiz_answered"] = True
    parts   = q.data.split("_")  # quiz_ans_{q_index}_{answer_index}
    q_index = int(parts[2]); ans_idx = int(parts[3])
    question= QUIZ_QUESTIONS[q_index]
    correct = question["answer"]
    is_right= (ans_idx == correct)
    if is_right:
        ctx.user_data["quiz_score"] = ctx.user_data.get("quiz_score",0) + 1

    result_emoji = tx(lang,"quiz_correct") if is_right else tx(lang,"quiz_wrong")
    exp = question["exp"].get(lang, question["exp"]["en"])
    correct_opt = question["options"][correct]
    text = (f"🧠 *Вопрос {q_index+1}/10*\n\n"
            f"{'✅' if is_right else '❌'} {result_emoji}\n"
            f"{'✔️' if is_right else f'Правильный ответ: *{correct_opt}*'}\n\n"
            f"💡 _{exp}_\n\n"
            f"Счёт: {ctx.user_data['quiz_score']}/{q_index+1}")
    ctx.user_data["quiz_q"] = q_index + 1
    await safe_edit(q, text, reply_markup=quiz_kb(lang, q_index, answered=True))

async def quiz_finish_h(update, ctx):
    q    = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    score = ctx.user_data.get("quiz_score", 0)
    grades = {
        range(0,4):  "🌑 Новичок — но космос бесконечен, продолжай учиться!",
        range(4,7):  "🌓 Исследователь — хорошее знание космоса!",
        range(7,9):  "🌕 Астронавт — впечатляющий результат!",
        range(9,11): "🚀 Легенда NASA — ты настоящий эксперт!",
    }
    grade = next((v for k,v in grades.items() if score in k), "Отличный результат!")
    text  = tx(lang,"quiz_result",score=score,grade=grade)
    kb    = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Ещё раз", callback_data="quiz_start_menu"),
        InlineKeyboardButton("◀️ Меню",    callback_data="back")
    ]])
    await safe_edit(q, text, reply_markup=kb)

# ── TIME CAPSULE — ConversationHandler ────────────────────────────────────────
async def capsule_menu_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    ctx.user_data["capsule_lang"] = lang
    await del_msg(q)
    await ctx.bot.send_message(chat_id=q.message.chat_id,
        text=tx(lang,"capsule_ask"), parse_mode="Markdown")
    return CAPSULE_MSG

async def capsule_msg_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang      = ctx.user_data.get("capsule_lang","ru")
    user_msg  = update.message.text.strip()
    if len(user_msg) < 5 or len(user_msg) > 2000:
        await update.message.reply_text("❌ Сообщение слишком короткое или длинное (5–2000 символов)")
        return CAPSULE_MSG

    deliver_on = (date.today() + timedelta(days=365)).isoformat()
    capsules   = load_capsules()
    capsules.append({
        "chat_id":    update.effective_chat.id,
        "message":    user_msg,
        "deliver_on": deliver_on,
        "created_at": date.today().isoformat()
    })
    save_capsules(capsules)

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Меню", callback_data="back")]])
    await update.message.reply_text(
        tx(lang,"capsule_saved", date=deliver_on), parse_mode="Markdown", reply_markup=kb)
    return ConversationHandler.END

async def capsule_cancel(update, ctx):
    lang = ctx.user_data.get("capsule_lang","ru")
    await update.message.reply_text(tx(lang,"capsule_cancel"))
    return ConversationHandler.END

# ── DAILY POLL ────────────────────────────────────────────────────────────────
async def daily_poll_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    poll_data = DAILY_POLLS[date.today().toordinal() % len(DAILY_POLLS)]
    question  = poll_data["q"].get(lang, poll_data["q"]["en"])
    options   = poll_data["opts"].get(lang, poll_data["opts"]["en"])
    await del_msg(q)
    try:
        await ctx.bot.send_poll(
            chat_id=q.message.chat_id,
            question=f"🌌 {question}",
            options=options,
            is_anonymous=True,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Интерактив", callback_data="cat_interactive")]])
        )
    except Exception as e:
        await ctx.bot.send_message(chat_id=q.message.chat_id,
            text=f"📊 *{question}*\n\n" + "\n".join(f"• {o}" for o in options),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Интерактив", callback_data="cat_interactive")]]))

# ── MARS ROVER LIVE ───────────────────────────────────────────────────────────
async def mars_rover_live_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q,"🛰...")
    try:
        # Get latest manifest for both rovers
        rovers_data = []
        for rover in ["perseverance","curiosity"]:
            try:
                r = requests.get(f"{NASA_BASE}/mars-photos/api/v1/manifests/{rover}",
                    params={"api_key": NASA_API_KEY}, timeout=10)
                if r.status_code == 200:
                    m = r.json().get("photo_manifest",{})
                    rovers_data.append({
                        "name": m.get("name","?"),
                        "status": m.get("status","?"),
                        "landing_date": m.get("landing_date","?"),
                        "max_sol": m.get("max_sol",0),
                        "max_date": m.get("max_date","?"),
                        "total_photos": m.get("total_photos",0),
                    })
            except Exception: continue

        text = tx(lang,"mars_rover_title")
        for rv in rovers_data:
            status_emoji = "🟢" if rv["status"]=="active" else "⚪"
            text += (f"🤖 *{rv['name']}* {status_emoji}\n"
                     f"   🛬 Посадка: {rv['landing_date']}\n"
                     f"   ☀️ Текущий Sol: {rv['max_sol']}\n"
                     f"   📅 Последнее фото: {rv['max_date']}\n"
                     f"   📷 Всего снимков: {rv['total_photos']:,}\n\n")

        text += "📍 [Mars Trek Map](https://trek.nasa.gov/mars/)"
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"mars_rover_live",ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,ctx=ctx))

# ── LUNAR CALENDAR ────────────────────────────────────────────────────────────
async def lunar_calendar_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    today = date.today()
    text  = tx(lang,"lunar_cal_title")
    text += f"📅 *{today.strftime('%B %Y')}*\n\n"

    # Show next 30 days
    moon_events = []
    for i in range(30):
        d = today + timedelta(days=i)
        emoji, idx, cycle_day, illum = get_moon_phase(d)
        if idx in (0,2,4,6):  # New, First Q, Full, Last Q
            phases = ["Новолуние 🌑","Первая четверть 🌓","Полнолуние 🌕","Последняя четверть 🌗"]
            moon_events.append((d, phases[idx//2]))

    seen_phases = set()
    for d, phase in moon_events:
        if phase not in seen_phases:
            seen_phases.add(phase)
            text += f"• {d.strftime('%d.%m')} — *{phase}*\n"

    text += "\n📸 *Советы фотографу:*\n"
    text += "🌕 Полнолуние: длинная выдержка, f/11, ISO 100\n"
    text += "🌑 Новолуние: лучшее время для звёзд!\n"
    text += "🌓 Четверти: красивые тени на лунной поверхности\n"
    text += "\n🔭 Лучшее время: 2-3 часа после заката / до рассвета"

    await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"lunar_calendar",ctx))

# ── NASA TV ───────────────────────────────────────────────────────────────────
async def nasa_tv_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    await safe_edit(q, tx(lang,"nasa_tv_title"), reply_markup=back_kb(lang,ctx=ctx))

# ══════════════════════════════════════════════════════════════════════════════
# CALLBACK ROUTER
# ══════════════════════════════════════════════════════════════════════════════
DIRECT_MAP = {
    "apod": apod_h, "apod_random": apod_random_h,
    "mars": mars_h, "mars_rovers": mars_rovers_h,
    "asteroids": asteroids_h, "iss": iss_h,
    "exoplanets": exoplanets_h, "spaceweather": spaceweather_h,
    "launches": launches_h, "spacefact": spacefact_h,
    "channels": channels_h, "planets": planets_h,
    "moon": moon_h, "satellites": satellites_h,
    "meteors": meteors_h, "telescopes": telescopes_h,
    "live_solar_wind": live_solar_wind_h, "live_kp": live_kp_h,
    "live_flares": live_flares_h, "live_iss": live_iss_h,
    "live_radiation": live_radiation_h, "live_aurora_forecast": live_aurora_h,
    "live_geomagnetic_alert": live_geomag_h, "live_sunspot": live_sunspot_h,
    "live_epic_latest": live_epic_h, "live_satellite_count": live_sat_count_h,
    # NEW
    "notifications_menu": notifications_menu_h,
    "space_name":    space_name_h,
    "quiz_start_menu": quiz_start_menu_h,
    "quiz_next":     quiz_next_h,
    "quiz_finish":   quiz_finish_h,
    "daily_poll":    daily_poll_h,
    "mars_rover_live": mars_rover_live_h,
    "nasa_tv":       nasa_tv_h,
    "lunar_calendar":lunar_calendar_h,
}

CAT_MAP = {
    "cat_photo":       (cat_photo_kb,       "title_photo"),
    "cat_solarsys":    (cat_solarsys_kb,    "title_solarsys"),
    "cat_deepspace":   (cat_deepspace_kb,   "title_deepspace"),
    "cat_earth":       (cat_earth_kb,       "title_earth"),
    "cat_science":     (cat_science_kb,     "title_science"),
    "cat_live":        (cat_live_kb,        "title_live"),
    "cat_interactive": (cat_interactive_kb, "title_interactive"),
}

async def callback_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q  = update.callback_query
    cb = q.data
    lang = get_lang(ctx)

    if cb == "choose_lang":        await choose_lang_h(update, ctx); return
    if cb.startswith("setlang_"):  await setlang_h(update, ctx); return
    if cb == "back":               await back_h(update, ctx); return
    if cb == "noop":               await safe_answer(q); return

    if cb in CAT_MAP:
        kb_fn, title_key = CAT_MAP[cb]; await safe_answer(q)
        ctx.user_data["last_cat"] = cb
        await safe_edit(q, tx(lang,title_key)+tx(lang,"choose_sec"), reply_markup=kb_fn(lang)); return

    if cb in DIRECT_MAP:
        await DIRECT_MAP[cb](update, ctx); return

    # Notification toggles
    if cb.startswith("notif_toggle_"):
        await notif_toggle_h(update, ctx); return

    # Quiz answers
    if cb.startswith("quiz_ans_"):
        await quiz_answer_h(update, ctx); return

    if cb in STATIC_TEXTS:
        await safe_answer(q)
        texts = STATIC_TEXTS[cb]
        text  = texts.get(lang, texts.get("en",""))
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang,cb,ctx)); return

    if cb in IMG_MAP:
        await safe_answer(q); await safe_edit(q,"⏳...")
        await send_nasa_image(q, ctx, IMG_MAP[cb], cb); return

    await safe_answer(q)

# ── FLASK ROUTES ──────────────────────────────────────────────────────────────
@flask_app.route("/")
def index():
    return "🚀 NASA Space Bot Enhanced is alive!", 200

@flask_app.route("/health")
def health():
    return "OK", 200

@flask_app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    if tg_app is None:
        return "Bot not ready", 503
    data   = request.get_json(force=True)
    future = asyncio.run_coroutine_threadsafe(process_update(data), bot_loop)
    try:
        future.result(timeout=30)
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
    return "ok", 200

async def process_update(data):
    upd = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(upd)

# ── STARTUP ───────────────────────────────────────────────────────────────────
def _run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

async def set_bot_descriptions(bot):
    descriptions = {
        "ru": "🚀 Твой проводник во Вселенную! Фото NASA, Марс, МКС, астероиды, квизы, калькулятор планет и живые данные. 7 категорий, 60+ разделов.",
        "en": "🚀 Your guide to the Universe! NASA photos, Mars, ISS, asteroids, quizzes, planet calculator and live data. 7 categories, 60+ sections.",
        "he": "🚀 המדריך שלך ליקום! NASA, מאדים, ISS, אסטרואידים, חידונים. 7 קטגוריות, 60+ מדורים.",
        "ar": "🚀 دليلك إلى الكون! صور NASA، المريخ، محطة الفضاء، ألعاب وبيانات مباشرة. 7 فئات، 60+ قسماً.",
    }
    short_descriptions = {
        "ru": "NASA фото, квизы, МКС, астероиды и живые данные о космосе 🚀",
        "en": "NASA photos, quiz, ISS, asteroids and live space data 🚀",
        "he": "תמונות NASA, חידון, ISS ונתוני חלל חיים 🚀",
        "ar": "صور NASA، مسابقات، محطة الفضاء وبيانات الفضاء المباشرة 🚀",
    }
    try:
        for lang_code, desc in descriptions.items():
            await bot.set_my_description(description=desc, language_code=lang_code)
        for lang_code, desc in short_descriptions.items():
            await bot.set_my_short_description(short_description=desc, language_code=lang_code)
        logger.info("✅ Bot descriptions updated")
    except Exception as e:
        logger.error(f"Failed to set descriptions: {e}")

async def setup_bot():
    global tg_app
    builder = Application.builder().token(TELEGRAM_TOKEN)
    tg_app  = builder.build()

    # ── ConversationHandlers (must be registered BEFORE the general CallbackQueryHandler)
    planet_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(planet_calc_start, pattern="^planet_calc$")],
        states={
            PLANET_DATE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, planet_date_received)],
            PLANET_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, planet_weight_received)],
        },
        fallbacks=[CommandHandler("cancel", planet_calc_cancel)],
        allow_reentry=True,
    )
    capsule_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(capsule_menu_h, pattern="^capsule_menu$")],
        states={
            CAPSULE_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, capsule_msg_received)],
        },
        fallbacks=[CommandHandler("cancel", capsule_cancel)],
        allow_reentry=True,
    )
    horoscope_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(horoscope_menu_h, pattern="^horoscope_menu$")],
        states={
            HOROSCOPE_BDAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, horoscope_date_received)],
        },
        fallbacks=[CommandHandler("cancel", horoscope_cancel)],
        allow_reentry=True,
    )

    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("menu",  menu_cmd))
    tg_app.add_handler(planet_conv)
    tg_app.add_handler(capsule_conv)
    tg_app.add_handler(horoscope_conv)
    tg_app.add_handler(CallbackQueryHandler(callback_router))
    tg_app.add_handler(MessageHandler(filters.ALL, unknown))

    # ── Scheduled Jobs ──────────────────────────────────────────────────────
    jq = tg_app.job_queue
    if jq:
        jq.run_daily(job_asteroid_alert,   time=datetime.strptime("09:00","%H:%M").time())
        jq.run_daily(job_lunar_alert,      time=datetime.strptime("07:00","%H:%M").time())
        jq.run_daily(job_check_capsules,   time=datetime.strptime("10:00","%H:%M").time())
        jq.run_repeating(job_space_weather_alert, interval=3600, first=60)  # every hour
        jq.run_weekly(job_meteor_alert,    day=0, time=datetime.strptime("08:00","%H:%M").time())  # Mondays
        logger.info("✅ Scheduled jobs registered")
    else:
        logger.warning("⚠️ JobQueue not available — install python-telegram-bot[job-queue]")

    await tg_app.initialize()
    if WEBHOOK_URL:
        wh = f"{WEBHOOK_URL}/webhook/{TELEGRAM_TOKEN}"
        await tg_app.bot.set_webhook(url=wh, drop_pending_updates=True)
        logger.info(f"✅ Webhook set: {wh}")
    else:
        logger.warning("⚠️  WEBHOOK_URL not set — webhook NOT registered!")

    await set_bot_descriptions(tg_app.bot)

def init_worker():
    """Start async event loop in daemon thread and set up the bot."""
    global bot_loop
    bot_loop = asyncio.new_event_loop()
    t = threading.Thread(target=_run_loop, args=(bot_loop,), daemon=True)
    t.start()
    future = asyncio.run_coroutine_threadsafe(setup_bot(), bot_loop)
    future.result(timeout=30)
    logger.info("✅ Worker initialized — bot loop running")

# ── Direct run ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_worker()
    flask_app.run(host="0.0.0.0", port=PORT)
