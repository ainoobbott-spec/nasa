"""
🚀 NASA Space Bot — Multilingual (RU/EN/HE/AR)
Fixed APIs, 4 languages, channels button, language switcher
"""

import os
import logging, random, re, requests, threading
from flask import Flask
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
)

# ── KEEP ALIVE (Настройка для Render) ────────────────────────────────────────
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "🚀 NASA Bot is alive!"

def run_flask():
    # Render требует слушать порт из переменной окружения
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# ── CONFIG ───────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = "8503684628:AAFQltwb59V8ZmkUPZ2pFkCuWh-C0s7ID04"
NASA_API_KEY   = "UXsg0T63ukdHkImo2VAejU46MHdnZdGgtgrlcQmE"
NASA_BASE      = "https://api.nasa.gov"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── CHANNELS (replace with your real links) ──────────────────────────────────
CHANNELS_TEXT = {
    "ru": "📢 *Наши группы и каналы*\n\n🚀 Подписывайся — первым узнавай о космосе!\n\n📡 *Канал:* @your\\_channel\n💬 *Группа:* @your\\_group\n\n_(Замени ссылки на реальные в коде)_",
    "en": "📢 *Our Groups & Channels*\n\n🚀 Subscribe for space news!\n\n📡 *Channel:* @your\\_channel\n💬 *Group:* @your\\_group\n\n_(Replace links in the code)_",
    "he": "📢 *הערוצים שלנו*\n\n🚀 הירשם לחדשות חלל!\n\n📡 *ערוץ:* @your\\_channel\n💬 *קבוצה:* @your\\_group\n\n_(החלף את הקישורים בקוד)_",
    "ar": "📢 *قنواتنا ومجموعاتنا*\n\n🚀 اشترك لأخبار الفضاء!\n\n📡 *القناة:* @your\\_channel\n💬 *المجموعة:* @your\\_group\n\n_(استبدل الروابط في الكود)_",
}


# ── TRANSLATIONS ─────────────────────────────────────────────────────────────
T = {
"ru": {
    "choose_lang":"🌍 *Выберите язык / Choose language / בחרו שפה / اختر اللغة*",
    "lang_btn_ru":"🇷🇺 Русский","lang_btn_en":"🇬🇧 English","lang_btn_he":"🇮🇱 עברית","lang_btn_ar":"🇦🇪 العربية",
    "lang_set":"🇷🇺 Язык установлен: *Русский*",
    "start_msg":"🚀 *NASA Space Bot* — твой проводник во Вселенную, {name}!\n\nЖивые данные NASA, NOAA и ведущих космических агентств.\n\n*6 категорий, 50+ разделов* 👇",
    "main_menu":"🌠 *Главное меню* — выбери категорию:",
    "choose_sec":"\n\nВыбери раздел 👇",
    "cat_photo":"📸  ФОТО И ГАЛЕРЕЯ NASA","cat_solarsys":"🪐  СОЛНЕЧНАЯ СИСТЕМА",
    "cat_deepspace":"🌌  ГЛУБОКИЙ КОСМОС","cat_earth":"🌍  ЗЕМЛЯ И АТМОСФЕРА",
    "cat_science":"🔬  НАУКА И ИСТОРИЯ","cat_live":"🔴  LIVE — РЕАЛЬНОЕ ВРЕМЯ",
    "btn_spacefact":"⭐ Факт о космосе","btn_channels":"📢 Наши каналы","btn_lang":"🌍 Сменить язык",
    "back_menu":"◀️ Главное меню","back_cat":"◀️ Назад в категорию",
    "btn_refresh":"🔄 Обновить","btn_more_rnd":"🎲 Ещё случайное","btn_another":"🔄 Ещё снимок","btn_other_rv":"🔄 Другой марсоход",
    "title_photo":"📸 *Фото и галерея NASA*","title_solarsys":"🪐 *Солнечная система*",
    "title_deepspace":"🌌 *Глубокий космос*","title_earth":"🌍 *Земля и атмосфера*",
    "title_science":"🔬 *Наука и история*","title_live":"🔴 *LIVE — реальное время*",
    "err":"❌ Ошибка","no_data":"📭 Нет данных","no_img":"📭 Снимки временно недоступны",
    "unknown":"🤔 Используй /start или /menu",
    "hazard_yes":"🔴 ОПАСЕН","hazard_no":"🟢 Безопасен",
    "iss_map":"🗺 Открыть на карте","iss_no_crew":"Нет данных","live_nodata":"Нет данных за период.",
    "moon_phases":["Новолуние","Растущий серп","Первая четверть","Растущая Луна","Полнолуние","Убывающая Луна","Последняя четверть","Убывающий серп"],
    # Buttons photo
    "btn_apod":"🌌 Фото дня (APOD)","btn_apod_rnd":"🎲 Случайное фото","btn_gallery":"🖼 Галерея NASA","btn_hubble":"🔬 Телескоп Хаббл",
    "btn_mars":"🤖 Марс: снимки","btn_mars_rv":"🤖 Фото марсоходов","btn_epic":"🌍 Земля из космоса","btn_earth_night":"🌃 Земля ночью",
    "btn_nebulae":"💫 Туманности","btn_clusters":"✨ Звёздные скопления","btn_eclipse":"🌑 Затмения","btn_jwst":"🔭 Джеймс Уэбб",
    "btn_moon_gal":"🖼 Луна в объективе","btn_blue_marble":"🌐 Голубой мрамор","btn_spacewalks":"🛸 Выходы в космос",
    # Buttons solar
    "btn_planets":"🪐 Планеты","btn_giants":"🪐 Планеты-гиганты","btn_dwarfs":"🪨 Карликовые","btn_moons":"🌙 Спутники",
    "btn_asteroids":"☄️ Астероиды","btn_comets":"☄️ Кометы","btn_moon":"🌑 Фаза Луны","btn_meteors":"🌠 Метеоры",
    "btn_sun":"☀️ Солнце","btn_spaceweather":"🌞 Косм. погода","btn_ceres":"🪨 Церера","btn_pluto":"🔷 Плутон",
    "btn_kuiper":"📦 Пояс Койпера","btn_alignment":"🪐 Парад планет","btn_solar_ecl":"☀️ Солн. затмения","btn_scale":"📏 Масштаб","btn_lunar_miss":"🌙 Лунные миссии",
    # Buttons deep
    "btn_deepspace":"🌌 Глубокий космос","btn_milkyway":"🌌 Млечный Путь","btn_blackholes":"⚫ Чёрные дыры","btn_supernovae":"💥 Сверхновые",
    "btn_pulsars":"💎 Пульсары","btn_nearstars":"⭐ Ближ. звёзды","btn_exoplanets":"🔭 Экзопланеты","btn_seti":"👽 SETI",
    "btn_gravwaves":"🌊 Гравит. волны","btn_darkmatter":"🌑 Тёмная материя","btn_future":"🔮 Будущее Вселенной",
    "btn_radioastro":"🔭 Радиоастрономия","btn_quasars":"📡 Квазары","btn_grb":"💥 Гамма-всплески",
    "btn_cmb":"📻 Реликт. излучение","btn_gal_coll":"🌀 Столкн. галактик","btn_starform":"⭐ Рождение звёзд",
    "btn_dark_en":"⚡ Тёмная энергия","btn_cosm_web":"🕸 Косм. паутина","btn_red_giants":"🔴 Красные гиганты",
    # Buttons earth
    "btn_climate":"🌍 Климат","btn_volcanoes":"🌋 Вулканы","btn_hurricanes":"🌀 Ураганы","btn_aurora":"🌈 Сияние",
    "btn_magneto":"🧲 Магнитосфера","btn_satellites":"📡 Спутники","btn_debris":"🛰 Косм. мусор",
    "btn_wildfires":"🔥 Пожары","btn_ice":"🧊 Ледники","btn_deforest":"🌲 Вырубка лесов",
    "btn_nightlights":"🌃 Города ночью","btn_ozone":"🛡 Озон","btn_ocean_temp":"🌡 Темп. океана",
    "btn_ocean_cur":"🌊 Океан. течения","btn_tornadoes":"🌪 Торнадо",
    # Buttons science
    "btn_launches":"🚀 Запуски","btn_missions":"🛸 Миссии","btn_history":"🚀 История","btn_iss":"🛸 МКС + экипаж",
    "btn_telescopes":"🔬 Телескопы","btn_sp_stations":"🛸 Косм. станции","btn_moon_sites":"🌙 Места высадки",
    "btn_women":"👩‍🚀 Женщины в космосе","btn_mars_col":"🔴 Марс колонизация",
    "btn_sp_med":"🩺 Косм. медицина","btn_rockets":"🚀 Двигатели","btn_training":"🎓 Подготовка астрон.",
    "btn_records":"🏆 Рекорды","btn_food":"🍽 Еда в космосе",
    # Buttons live
    "btn_solar_wind":"🔴 Солнечный ветер","btn_kp":"🔴 Kp-индекс","btn_flares":"🔴 Вспышки Солнца",
    "btn_live_iss":"🔴 МКС сейчас","btn_radiation":"🔴 Радиация","btn_aurora_f":"🔴 Прогноз сияний",
    "btn_geomag":"🔴 Геомагн. бури","btn_sunspot":"🔴 Пятна Солнца","btn_live_epic":"🔴 Земля EPIC","btn_sat_count":"🔴 Кол-во спутников",
},
"en": {
    "choose_lang":"🌍 *Choose language / Выберите язык / בחרו שפה / اختر اللغة*",
    "lang_btn_ru":"🇷🇺 Русский","lang_btn_en":"🇬🇧 English","lang_btn_he":"🇮🇱 עברית","lang_btn_ar":"🇦🇪 العربية",
    "lang_set":"🇬🇧 Language set: *English*",
    "start_msg":"🚀 *NASA Space Bot* — your guide to the Universe, {name}!\n\nLive data from NASA, NOAA and leading space agencies.\n\n*6 categories, 50+ sections* 👇",
    "main_menu":"🌠 *Main Menu* — choose a category:","choose_sec":"\n\nChoose a section 👇",
    "cat_photo":"📸  PHOTO & NASA GALLERY","cat_solarsys":"🪐  SOLAR SYSTEM",
    "cat_deepspace":"🌌  DEEP SPACE","cat_earth":"🌍  EARTH & ATMOSPHERE",
    "cat_science":"🔬  SCIENCE & HISTORY","cat_live":"🔴  LIVE — REAL TIME",
    "btn_spacefact":"⭐ Space Fact","btn_channels":"📢 Our Channels","btn_lang":"🌍 Change Language",
    "back_menu":"◀️ Main Menu","back_cat":"◀️ Back to Category",
    "btn_refresh":"🔄 Refresh","btn_more_rnd":"🎲 Another Random","btn_another":"🔄 Another Photo","btn_other_rv":"🔄 Other Rover",
    "title_photo":"📸 *Photo & NASA Gallery*","title_solarsys":"🪐 *Solar System*",
    "title_deepspace":"🌌 *Deep Space*","title_earth":"🌍 *Earth & Atmosphere*",
    "title_science":"🔬 *Science & History*","title_live":"🔴 *LIVE — Real Time*",
    "err":"❌ Error","no_data":"📭 No data available","no_img":"📭 Images temporarily unavailable",
    "unknown":"🤔 Use /start or /menu",
    "hazard_yes":"🔴 HAZARDOUS","hazard_no":"🟢 Safe",
    "iss_map":"🗺 Open on Map","iss_no_crew":"No data","live_nodata":"No data for the period.",
    "moon_phases":["New Moon","Waxing Crescent","First Quarter","Waxing Gibbous","Full Moon","Waning Gibbous","Last Quarter","Waning Crescent"],
    "btn_apod":"🌌 Photo of the Day","btn_apod_rnd":"🎲 Random Photo","btn_gallery":"🖼 NASA Gallery","btn_hubble":"🔬 Hubble",
    "btn_mars":"🤖 Mars: Photos","btn_mars_rv":"🤖 Rover Photos","btn_epic":"🌍 Earth from Space","btn_earth_night":"🌃 Earth at Night",
    "btn_nebulae":"💫 Nebulae","btn_clusters":"✨ Star Clusters","btn_eclipse":"🌑 Eclipses","btn_jwst":"🔭 James Webb",
    "btn_moon_gal":"🖼 Moon Gallery","btn_blue_marble":"🌐 Blue Marble","btn_spacewalks":"🛸 Spacewalks",
    "btn_planets":"🪐 Planets","btn_giants":"🪐 Giant Planets","btn_dwarfs":"🪨 Dwarf Planets","btn_moons":"🌙 Planet Moons",
    "btn_asteroids":"☄️ Asteroids","btn_comets":"☄️ Comets","btn_moon":"🌑 Moon Phase","btn_meteors":"🌠 Meteors",
    "btn_sun":"☀️ The Sun","btn_spaceweather":"🌞 Space Weather","btn_ceres":"🪨 Ceres","btn_pluto":"🔷 Pluto",
    "btn_kuiper":"📦 Kuiper Belt","btn_alignment":"🪐 Planet Parade","btn_solar_ecl":"☀️ Solar Eclipses","btn_scale":"📏 Scale","btn_lunar_miss":"🌙 Lunar Missions",
    "btn_deepspace":"🌌 Deep Space","btn_milkyway":"🌌 Milky Way","btn_blackholes":"⚫ Black Holes","btn_supernovae":"💥 Supernovae",
    "btn_pulsars":"💎 Pulsars","btn_nearstars":"⭐ Nearest Stars","btn_exoplanets":"🔭 Exoplanets","btn_seti":"👽 SETI",
    "btn_gravwaves":"🌊 Grav. Waves","btn_darkmatter":"🌑 Dark Matter","btn_future":"🔮 Future of Universe",
    "btn_radioastro":"🔭 Radio Astronomy","btn_quasars":"📡 Quasars","btn_grb":"💥 Gamma Bursts",
    "btn_cmb":"📻 CMB","btn_gal_coll":"🌀 Galaxy Collisions","btn_starform":"⭐ Star Formation",
    "btn_dark_en":"⚡ Dark Energy","btn_cosm_web":"🕸 Cosmic Web","btn_red_giants":"🔴 Red Giants",
    "btn_climate":"🌍 Climate","btn_volcanoes":"🌋 Volcanoes","btn_hurricanes":"🌀 Hurricanes","btn_aurora":"🌈 Aurora",
    "btn_magneto":"🧲 Magnetosphere","btn_satellites":"📡 Satellites","btn_debris":"🛰 Space Debris",
    "btn_wildfires":"🔥 Wildfires","btn_ice":"🧊 Glaciers","btn_deforest":"🌲 Deforestation",
    "btn_nightlights":"🌃 City Lights","btn_ozone":"🛡 Ozone","btn_ocean_temp":"🌡 Ocean Temp",
    "btn_ocean_cur":"🌊 Ocean Currents","btn_tornadoes":"🌪 Tornadoes",
    "btn_launches":"🚀 Launches","btn_missions":"🛸 Missions","btn_history":"🚀 History","btn_iss":"🛸 ISS + Crew",
    "btn_telescopes":"🔬 Telescopes","btn_sp_stations":"🛸 Space Stations","btn_moon_sites":"🌙 Landing Sites",
    "btn_women":"👩‍🚀 Women in Space","btn_mars_col":"🔴 Mars Colonization",
    "btn_sp_med":"🩺 Space Medicine","btn_rockets":"🚀 Engines","btn_training":"🎓 Training","btn_records":"🏆 Records","btn_food":"🍽 Space Food",
    "btn_solar_wind":"🔴 Solar Wind","btn_kp":"🔴 Kp-index","btn_flares":"🔴 Solar Flares",
    "btn_live_iss":"🔴 ISS Now","btn_radiation":"🔴 Radiation","btn_aurora_f":"🔴 Aurora Forecast",
    "btn_geomag":"🔴 Geomag. Storms","btn_sunspot":"🔴 Sunspots","btn_live_epic":"🔴 Earth EPIC","btn_sat_count":"🔴 Satellite Count",
},
"he": {
    "choose_lang":"🌍 *Выберите язык / Choose language / בחרו שפה / اختر اللغة*",
    "lang_btn_ru":"🇷🇺 Русский","lang_btn_en":"🇬🇧 English","lang_btn_he":"🇮🇱 עברית","lang_btn_ar":"🇦🇪 العربية",
    "lang_set":"🇮🇱 שפה נקבעה: *עברית*",
    "start_msg":"🚀 *NASA Space Bot* — המדריך שלך ליקום, {name}!\n\nנתונים חיים מ-NASA ו-NOAA — ישירות בטלגרם.\n\n*6 קטגוריות, 50+ מדורים* 👇",
    "main_menu":"🌠 *תפריט ראשי* — בחר קטגוריה:","choose_sec":"\n\nבחר מדור 👇",
    "cat_photo":"📸  תמונות וגלריית NASA","cat_solarsys":"🪐  מערכת השמש",
    "cat_deepspace":"🌌  חלל עמוק","cat_earth":"🌍  כדור הארץ ואטמוספירה",
    "cat_science":"🔬  מדע והיסטוריה","cat_live":"🔴  LIVE — זמן אמת",
    "btn_spacefact":"⭐ עובדת חלל","btn_channels":"📢 הערוצים שלנו","btn_lang":"🌍 שינוי שפה",
    "back_menu":"◀️ תפריט ראשי","back_cat":"◀️ חזרה לקטגוריה",
    "btn_refresh":"🔄 רענון","btn_more_rnd":"🎲 עוד אקראי","btn_another":"🔄 תמונה נוספת","btn_other_rv":"🔄 רובר אחר",
    "title_photo":"📸 *תמונות וגלריית NASA*","title_solarsys":"🪐 *מערכת השמש*",
    "title_deepspace":"🌌 *חלל עמוק*","title_earth":"🌍 *כדור הארץ ואטמוספירה*",
    "title_science":"🔬 *מדע והיסטוריה*","title_live":"🔴 *LIVE — זמן אמת*",
    "err":"❌ שגיאה","no_data":"📭 אין נתונים","no_img":"📭 תמונות אינן זמינות כרגע",
    "unknown":"🤔 השתמש ב-/start או ב-/menu",
    "hazard_yes":"🔴 מסוכן","hazard_no":"🟢 בטוח",
    "iss_map":"🗺 פתח במפה","iss_no_crew":"אין נתונים","live_nodata":"אין נתונים לתקופה.",
    "moon_phases":["ירח חדש","סהר עולה","רבע ראשון","ירח עולה","ירח מלא","ירח יורד","רבע אחרון","סהר יורד"],
    "btn_apod":"🌌 תמונת יום (APOD)","btn_apod_rnd":"🎲 תמונה אקראית","btn_gallery":"🖼 גלריית NASA","btn_hubble":"🔬 האבל",
    "btn_mars":"🤖 מאדים: תמונות","btn_mars_rv":"🤖 תמונות רובר","btn_epic":"🌍 כדור הארץ מהחלל","btn_earth_night":"🌃 כדור הארץ בלילה",
    "btn_nebulae":"💫 ערפיליות","btn_clusters":"✨ אשכולות כוכבים","btn_eclipse":"🌑 ליקויים","btn_jwst":"🔭 ג'יימס ווב",
    "btn_moon_gal":"🖼 גלריית ירח","btn_blue_marble":"🌐 כדור שיש כחול","btn_spacewalks":"🛸 הליכות חלל",
    "btn_planets":"🪐 כוכבי לכת","btn_giants":"🪐 כוכבי ענק","btn_dwarfs":"🪨 ננסיים","btn_moons":"🌙 ירחים",
    "btn_asteroids":"☄️ אסטרואידים","btn_comets":"☄️ שביטים","btn_moon":"🌑 שלב הירח","btn_meteors":"🌠 גשמי מטאורים",
    "btn_sun":"☀️ השמש","btn_spaceweather":"🌞 מזג אוויר בחלל","btn_ceres":"🪨 סרס","btn_pluto":"🔷 פלוטו",
    "btn_kuiper":"📦 חגורת קויפר","btn_alignment":"🪐 מצעד כוכבים","btn_solar_ecl":"☀️ ליקויי חמה","btn_scale":"📏 קנה מידה","btn_lunar_miss":"🌙 משימות ירח",
    "btn_deepspace":"🌌 חלל עמוק","btn_milkyway":"🌌 שביל החלב","btn_blackholes":"⚫ חורים שחורים","btn_supernovae":"💥 סופרנובות",
    "btn_pulsars":"💎 פולסרים","btn_nearstars":"⭐ כוכבים קרובים","btn_exoplanets":"🔭 אקסופלנטות","btn_seti":"👽 SETI",
    "btn_gravwaves":"🌊 גלי כבידה","btn_darkmatter":"🌑 חומר אפל","btn_future":"🔮 עתיד היקום",
    "btn_radioastro":"🔭 רדיו אסטרונומיה","btn_quasars":"📡 קווזרים","btn_grb":"💥 פרצי גמא",
    "btn_cmb":"📻 קרינת רקע","btn_gal_coll":"🌀 התנגשות גלקסיות","btn_starform":"⭐ לידת כוכבים",
    "btn_dark_en":"⚡ אנרגיה אפלה","btn_cosm_web":"🕸 רשת קוסמית","btn_red_giants":"🔴 ענקים אדומים",
    "btn_climate":"🌍 אקלים","btn_volcanoes":"🌋 וולקנים","btn_hurricanes":"🌀 הוריקנים","btn_aurora":"🌈 זוהר צפוני",
    "btn_magneto":"🧲 מגנטוספירה","btn_satellites":"📡 לוויינים","btn_debris":"🛰 פסולת חלל",
    "btn_wildfires":"🔥 שרפות","btn_ice":"🧊 קרחונים","btn_deforest":"🌲 כריתת יערות",
    "btn_nightlights":"🌃 אורות ערים","btn_ozone":"🛡 אוזון","btn_ocean_temp":"🌡 טמפ' אוקיינוס",
    "btn_ocean_cur":"🌊 זרמי האוקיינוס","btn_tornadoes":"🌪 טורנדו",
    "btn_launches":"🚀 שיגורים","btn_missions":"🛸 משימות","btn_history":"🚀 היסטוריה","btn_iss":"🛸 ISS + צוות",
    "btn_telescopes":"🔬 טלסקופים","btn_sp_stations":"🛸 תחנות חלל","btn_moon_sites":"🌙 אתרי נחיתה",
    "btn_women":"👩‍🚀 נשים בחלל","btn_mars_col":"🔴 קולוניזציה מאדים",
    "btn_sp_med":"🩺 רפואת חלל","btn_rockets":"🚀 מנועים","btn_training":"🎓 אימון","btn_records":"🏆 שיאים","btn_food":"🍽 אוכל בחלל",
    "btn_solar_wind":"🔴 רוח שמש","btn_kp":"🔴 מדד Kp","btn_flares":"🔴 להבות שמש",
    "btn_live_iss":"🔴 ISS עכשיו","btn_radiation":"🔴 קרינה","btn_aurora_f":"🔴 תחזית זוהר",
    "btn_geomag":"🔴 סערות מגנטיות","btn_sunspot":"🔴 כתמי שמש","btn_live_epic":"🔴 כדור הארץ EPIC","btn_sat_count":"🔴 ספירת לוויינים",
},
"ar": {
    "choose_lang":"🌍 *Выберите язык / Choose language / בחרו שפה / اختر اللغة*",
    "lang_btn_ru":"🇷🇺 Русский","lang_btn_en":"🇬🇧 English","lang_btn_he":"🇮🇱 עברית","lang_btn_ar":"🇦🇪 العربية",
    "lang_set":"🇦🇪 تم تعيين اللغة: *العربية*",
    "start_msg":"🚀 *NASA Space Bot* — دليلك إلى الكون، {name}!\n\nبيانات حية من ناسا ووكالات الفضاء الرائدة.\n\n*6 فئات، أكثر من 50 قسماً* 👇",
    "main_menu":"🌠 *القائمة الرئيسية* — اختر فئة:","choose_sec":"\n\nاختر قسماً 👇",
    "cat_photo":"📸  الصور وصالة ناسا","cat_solarsys":"🪐  المجموعة الشمسية",
    "cat_deepspace":"🌌  الفضاء العميق","cat_earth":"🌍  الأرض والغلاف الجوي",
    "cat_science":"🔬  العلوم والتاريخ","cat_live":"🔴  مباشر — الوقت الفعلي",
    "btn_spacefact":"⭐ حقيقة فضائية","btn_channels":"📢 قنواتنا","btn_lang":"🌍 تغيير اللغة",
    "back_menu":"◀️ القائمة الرئيسية","back_cat":"◀️ العودة للفئة",
    "btn_refresh":"🔄 تحديث","btn_more_rnd":"🎲 عشوائي آخر","btn_another":"🔄 صورة أخرى","btn_other_rv":"🔄 مركبة أخرى",
    "title_photo":"📸 *الصور وصالة ناسا*","title_solarsys":"🪐 *المجموعة الشمسية*",
    "title_deepspace":"🌌 *الفضاء العميق*","title_earth":"🌍 *الأرض والغلاف الجوي*",
    "title_science":"🔬 *العلوم والتاريخ*","title_live":"🔴 *مباشر — الوقت الفعلي*",
    "err":"❌ خطأ","no_data":"📭 لا توجد بيانات","no_img":"📭 الصور غير متاحة مؤقتاً",
    "unknown":"🤔 استخدم /start أو /menu",
    "hazard_yes":"🔴 خطير","hazard_no":"🟢 آمن",
    "iss_map":"🗺 فتح على الخريطة","iss_no_crew":"لا توجد بيانات","live_nodata":"لا توجد بيانات للفترة.",
    "moon_phases":["محاق","هلال متزايد","تربيع أول","بدر متزايد","بدر","بدر متناقص","تربيع أخير","هلال متناقص"],
    "btn_apod":"🌌 صورة اليوم (APOD)","btn_apod_rnd":"🎲 صورة عشوائية","btn_gallery":"🖼 صالة ناسا","btn_hubble":"🔬 هابل",
    "btn_mars":"🤖 المريخ: صور","btn_mars_rv":"🤖 صور المركبات","btn_epic":"🌍 الأرض من الفضاء","btn_earth_night":"🌃 الأرض ليلاً",
    "btn_nebulae":"💫 السدم","btn_clusters":"✨ مجموعات النجوم","btn_eclipse":"🌑 الكسوف","btn_jwst":"🔭 جيمس ويب",
    "btn_moon_gal":"🖼 صور القمر","btn_blue_marble":"🌐 كرة المرمر","btn_spacewalks":"🛸 المشي الفضائي",
    "btn_planets":"🪐 الكواكب","btn_giants":"🪐 الكواكب العملاقة","btn_dwarfs":"🪨 الكواكب القزمة","btn_moons":"🌙 أقمار الكواكب",
    "btn_asteroids":"☄️ الكويكبات","btn_comets":"☄️ المذنبات","btn_moon":"🌑 طور القمر","btn_meteors":"🌠 أمطار الشهب",
    "btn_sun":"☀️ الشمس","btn_spaceweather":"🌞 الطقس الفضائي","btn_ceres":"🪨 سيريس","btn_pluto":"🔷 بلوتو",
    "btn_kuiper":"📦 حزام كويبر","btn_alignment":"🪐 استعراض الكواكب","btn_solar_ecl":"☀️ كسوف الشمس","btn_scale":"📏 المقياس","btn_lunar_miss":"🌙 مهمات القمر",
    "btn_deepspace":"🌌 الفضاء العميق","btn_milkyway":"🌌 درب التبانة","btn_blackholes":"⚫ الثقوب السوداء","btn_supernovae":"💥 المستعرات الأعظم",
    "btn_pulsars":"💎 النجوم النابضة","btn_nearstars":"⭐ النجوم الأقرب","btn_exoplanets":"🔭 الكواكب الخارجية","btn_seti":"👽 SETI",
    "btn_gravwaves":"🌊 موجات الجاذبية","btn_darkmatter":"🌑 المادة المظلمة","btn_future":"🔮 مستقبل الكون",
    "btn_radioastro":"🔭 الفلك الراديوي","btn_quasars":"📡 الكوازارات","btn_grb":"💥 انفجارات غاما",
    "btn_cmb":"📻 إشعاع الخلفية","btn_gal_coll":"🌀 تصادم المجرات","btn_starform":"⭐ تشكّل النجوم",
    "btn_dark_en":"⚡ الطاقة المظلمة","btn_cosm_web":"🕸 الشبكة الكونية","btn_red_giants":"🔴 العمالقة الحمراء",
    "btn_climate":"🌍 المناخ","btn_volcanoes":"🌋 البراكين","btn_hurricanes":"🌀 الأعاصير","btn_aurora":"🌈 الشفق القطبي",
    "btn_magneto":"🧲 الغلاف المغناطيسي","btn_satellites":"📡 الأقمار الاصطناعية","btn_debris":"🛰 حطام الفضاء",
    "btn_wildfires":"🔥 حرائق الغابات","btn_ice":"🧊 الجليد","btn_deforest":"🌲 إزالة الغابات",
    "btn_nightlights":"🌃 أضواء المدن","btn_ozone":"🛡 الأوزون","btn_ocean_temp":"🌡 حرارة المحيط",
    "btn_ocean_cur":"🌊 تيارات المحيط","btn_tornadoes":"🌪 الأعاصير الرياحية",
    "btn_launches":"🚀 الإطلاقات","btn_missions":"🛸 المهمات","btn_history":"🚀 التاريخ","btn_iss":"🛸 محطة الفضاء + الطاقم",
    "btn_telescopes":"🔬 التلسكوبات","btn_sp_stations":"🛸 محطات الفضاء","btn_moon_sites":"🌙 مواقع الهبوط",
    "btn_women":"👩‍🚀 المرأة في الفضاء","btn_mars_col":"🔴 استعمار المريخ",
    "btn_sp_med":"🩺 الطب الفضائي","btn_rockets":"🚀 المحركات","btn_training":"🎓 التدريب","btn_records":"🏆 الأرقام القياسية","btn_food":"🍽 الطعام الفضائي",
    "btn_solar_wind":"🔴 الرياح الشمسية","btn_kp":"🔴 مؤشر Kp","btn_flares":"🔴 التوهجات الشمسية",
    "btn_live_iss":"🔴 المحطة الآن","btn_radiation":"🔴 الإشعاع","btn_aurora_f":"🔴 توقعات الشفق",
    "btn_geomag":"🔴 العواصف المغناطيسية","btn_sunspot":"🔴 البقع الشمسية","btn_live_epic":"🔴 الأرض EPIC","btn_sat_count":"🔴 عدد الأقمار",
},
}

def tx(lang, key, **kw):
    """Get translation, fallback to 'en' then key itself."""
    val = T.get(lang, T["en"]).get(key) or T["en"].get(key) or key
    return val.format(**kw) if kw else val

def get_lang(context):
    return context.user_data.get("lang", "ru")


# ── HELPERS ──────────────────────────────────────────────────────────────────
def strip_html(text): return re.sub(r'<[^>]+>', '', text or '')

def nasa(path, params=None):
    p = {"api_key": NASA_API_KEY}
    if params: p.update(params)
    r = requests.get(f"{NASA_BASE}{path}", params=p, timeout=15)
    r.raise_for_status(); return r.json()

def get_json(url, params=None, timeout=12):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status(); return r.json()

async def safe_answer(query):
    try: await query.answer()
    except: pass

async def safe_edit(query, text, reply_markup=None):
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup, disable_web_page_preview=True)
    except:
        try: await query.message.delete()
        except: pass
        try:
            await query.message.chat.send_message(text, parse_mode="Markdown", reply_markup=reply_markup, disable_web_page_preview=True)
        except: pass

async def del_msg(query):
    try: await query.message.delete()
    except: pass

# ── KEYBOARDS ────────────────────────────────────────────────────────────────
def lang_keyboard():
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
        [InlineKeyboardButton(L("cat_photo"),    callback_data="cat_photo")],
        [InlineKeyboardButton(L("cat_solarsys"), callback_data="cat_solarsys")],
        [InlineKeyboardButton(L("cat_deepspace"),callback_data="cat_deepspace")],
        [InlineKeyboardButton(L("cat_earth"),    callback_data="cat_earth")],
        [InlineKeyboardButton(L("cat_science"),  callback_data="cat_science")],
        [InlineKeyboardButton(L("cat_live"),     callback_data="cat_live")],
        [InlineKeyboardButton(L("btn_spacefact"),callback_data="spacefact"),
         InlineKeyboardButton(L("btn_channels"), callback_data="channels")],
        [InlineKeyboardButton(L("btn_lang"),     callback_data="choose_lang")],
    ])

def cat_photo_kb(lang):
    L = lambda k: tx(lang, k)
    rows = [
        [InlineKeyboardButton(L("cat_photo"), callback_data="noop")],
        [InlineKeyboardButton(L("btn_apod"), callback_data="apod"), InlineKeyboardButton(L("btn_apod_rnd"), callback_data="apod_random")],
        [InlineKeyboardButton(L("btn_gallery"), callback_data="gallery"), InlineKeyboardButton(L("btn_hubble"), callback_data="deepspace")],
        [InlineKeyboardButton(L("btn_mars"), callback_data="mars"), InlineKeyboardButton(L("btn_mars_rv"), callback_data="mars_rovers")],
        [InlineKeyboardButton(L("btn_epic"), callback_data="epic"), InlineKeyboardButton(L("btn_earth_night"), callback_data="earth_night")],
        [InlineKeyboardButton(L("btn_nebulae"), callback_data="nebulae"), InlineKeyboardButton(L("btn_clusters"), callback_data="clusters")],
        [InlineKeyboardButton(L("btn_eclipse"), callback_data="eclipse"), InlineKeyboardButton(L("btn_jwst"), callback_data="jwst_gallery")],
        [InlineKeyboardButton(L("btn_moon_gal"), callback_data="moon_gallery"), InlineKeyboardButton(L("btn_blue_marble"), callback_data="blue_marble")],
        [InlineKeyboardButton(L("btn_spacewalks"), callback_data="spacewalks")],
        [InlineKeyboardButton(L("back_menu"), callback_data="back")],
    ]
    return InlineKeyboardMarkup(rows)

def cat_solarsys_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("cat_solarsys"), callback_data="noop")],
        [InlineKeyboardButton(L("btn_planets"), callback_data="planets"), InlineKeyboardButton(L("btn_giants"), callback_data="giants")],
        [InlineKeyboardButton(L("btn_dwarfs"), callback_data="dwarfplanets"), InlineKeyboardButton(L("btn_moons"), callback_data="moons")],
        [InlineKeyboardButton(L("btn_asteroids"), callback_data="asteroids"), InlineKeyboardButton(L("btn_comets"), callback_data="comets")],
        [InlineKeyboardButton(L("btn_moon"), callback_data="moon"), InlineKeyboardButton(L("btn_meteors"), callback_data="meteors")],
        [InlineKeyboardButton(L("btn_sun"), callback_data="sun"), InlineKeyboardButton(L("btn_spaceweather"), callback_data="spaceweather")],
        [InlineKeyboardButton(L("btn_ceres"), callback_data="ceres"), InlineKeyboardButton(L("btn_pluto"), callback_data="pluto_close")],
        [InlineKeyboardButton(L("btn_kuiper"), callback_data="kuiper_belt"), InlineKeyboardButton(L("btn_alignment"), callback_data="planet_alignment")],
        [InlineKeyboardButton(L("btn_solar_ecl"), callback_data="solar_eclipse"), InlineKeyboardButton(L("btn_scale"), callback_data="orbital_scale")],
        [InlineKeyboardButton(L("btn_lunar_miss"), callback_data="lunar_missions")],
        [InlineKeyboardButton(L("back_menu"), callback_data="back")],
    ])

def cat_deepspace_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("cat_deepspace"), callback_data="noop")],
        [InlineKeyboardButton(L("btn_deepspace"), callback_data="deepspace"), InlineKeyboardButton(L("btn_milkyway"), callback_data="milkyway")],
        [InlineKeyboardButton(L("btn_blackholes"), callback_data="blackholes"), InlineKeyboardButton(L("btn_supernovae"), callback_data="supernovae")],
        [InlineKeyboardButton(L("btn_pulsars"), callback_data="pulsars"), InlineKeyboardButton(L("btn_nearstars"), callback_data="nearstars")],
        [InlineKeyboardButton(L("btn_exoplanets"), callback_data="exoplanets"), InlineKeyboardButton(L("btn_seti"), callback_data="seti")],
        [InlineKeyboardButton(L("btn_gravwaves"), callback_data="gravwaves"), InlineKeyboardButton(L("btn_darkmatter"), callback_data="darkmatter")],
        [InlineKeyboardButton(L("btn_future"), callback_data="future"), InlineKeyboardButton(L("btn_radioastro"), callback_data="radioastro")],
        [InlineKeyboardButton(L("btn_quasars"), callback_data="quasars"), InlineKeyboardButton(L("btn_grb"), callback_data="grb")],
        [InlineKeyboardButton(L("btn_cmb"), callback_data="cmb"), InlineKeyboardButton(L("btn_gal_coll"), callback_data="galaxy_collision")],
        [InlineKeyboardButton(L("btn_starform"), callback_data="star_formation"), InlineKeyboardButton(L("btn_dark_en"), callback_data="dark_energy")],
        [InlineKeyboardButton(L("btn_cosm_web"), callback_data="cosmic_web")],
        [InlineKeyboardButton(L("btn_red_giants"), callback_data="red_giants")],
        [InlineKeyboardButton(L("back_menu"), callback_data="back")],
    ])

def cat_earth_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("cat_earth"), callback_data="noop")],
        [InlineKeyboardButton(L("btn_epic"), callback_data="epic"), InlineKeyboardButton(L("btn_climate"), callback_data="climate")],
        [InlineKeyboardButton(L("btn_volcanoes"), callback_data="volcanoes"), InlineKeyboardButton(L("btn_hurricanes"), callback_data="hurricanes")],
        [InlineKeyboardButton(L("btn_aurora"), callback_data="aurora"), InlineKeyboardButton(L("btn_magneto"), callback_data="magnetosphere")],
        [InlineKeyboardButton(L("btn_satellites"), callback_data="satellites"), InlineKeyboardButton(L("btn_debris"), callback_data="debris")],
        [InlineKeyboardButton(L("btn_wildfires"), callback_data="wildfires"), InlineKeyboardButton(L("btn_ice"), callback_data="ice_sheets")],
        [InlineKeyboardButton(L("btn_deforest"), callback_data="deforestation"), InlineKeyboardButton(L("btn_nightlights"), callback_data="night_lights")],
        [InlineKeyboardButton(L("btn_ozone"), callback_data="ozone"), InlineKeyboardButton(L("btn_ocean_temp"), callback_data="ocean_temp")],
        [InlineKeyboardButton(L("btn_ocean_cur"), callback_data="ocean_currents")],
        [InlineKeyboardButton(L("btn_tornadoes"), callback_data="tornadoes")],
        [InlineKeyboardButton(L("back_menu"), callback_data="back")],
    ])

def cat_science_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("cat_science"), callback_data="noop")],
        [InlineKeyboardButton(L("btn_launches"), callback_data="launches"), InlineKeyboardButton(L("btn_missions"), callback_data="missions")],
        [InlineKeyboardButton(L("btn_history"), callback_data="history"), InlineKeyboardButton(L("btn_iss"), callback_data="iss")],
        [InlineKeyboardButton(L("btn_telescopes"), callback_data="telescopes"), InlineKeyboardButton(L("btn_radioastro"), callback_data="radioastro")],
        [InlineKeyboardButton(L("btn_sp_stations"), callback_data="space_stations"), InlineKeyboardButton(L("btn_moon_sites"), callback_data="moon_landing_sites")],
        [InlineKeyboardButton(L("btn_women"), callback_data="women_in_space"), InlineKeyboardButton(L("btn_mars_col"), callback_data="mars_colonization")],
        [InlineKeyboardButton(L("btn_sp_med"), callback_data="space_medicine"), InlineKeyboardButton(L("btn_rockets"), callback_data="rocket_engines")],
        [InlineKeyboardButton(L("btn_training"), callback_data="astronaut_training")],
        [InlineKeyboardButton(L("btn_records"), callback_data="space_records"), InlineKeyboardButton(L("btn_food"), callback_data="space_food")],
        [InlineKeyboardButton(L("back_menu"), callback_data="back")],
    ])

def cat_live_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("cat_live"), callback_data="noop")],
        [InlineKeyboardButton(L("btn_solar_wind"), callback_data="live_solar_wind")],
        [InlineKeyboardButton(L("btn_kp"), callback_data="live_kp"), InlineKeyboardButton(L("btn_flares"), callback_data="live_flares")],
        [InlineKeyboardButton(L("btn_live_iss"), callback_data="live_iss"), InlineKeyboardButton(L("btn_radiation"), callback_data="live_radiation")],
        [InlineKeyboardButton(L("btn_aurora_f"), callback_data="live_aurora_forecast"), InlineKeyboardButton(L("btn_geomag"), callback_data="live_geomagnetic_alert")],
        [InlineKeyboardButton(L("btn_sunspot"), callback_data="live_sunspot"), InlineKeyboardButton(L("btn_live_epic"), callback_data="live_epic_latest")],
        [InlineKeyboardButton(L("btn_sat_count"), callback_data="live_satellite_count")],
        [InlineKeyboardButton(L("back_menu"), callback_data="back")],
    ])

def back_kb(lang, refresh_data=None, context=None):
    rows = []
    if refresh_data:
        rows.append([InlineKeyboardButton(tx(lang, "btn_refresh"), callback_data=refresh_data)])
    row = []
    if context and context.user_data.get("last_category"):
        row.append(InlineKeyboardButton(tx(lang, "back_cat"), callback_data=context.user_data["last_category"]))
    row.append(InlineKeyboardButton(tx(lang, "back_menu"), callback_data="back"))
    rows.append(row)
    return InlineKeyboardMarkup(rows)

def action_kb(lang, refresh_cb, refresh_label_key="btn_refresh", context=None):
    row = [InlineKeyboardButton(tx(lang, refresh_label_key), callback_data=refresh_cb)]
    if context and context.user_data.get("last_category"):
        row.append(InlineKeyboardButton(tx(lang, "back_cat"), callback_data=context.user_data["last_category"]))
    row.append(InlineKeyboardButton(tx(lang, "back_menu"), callback_data="back"))
    return InlineKeyboardMarkup([row])


# ── STATIC CONTENT ───────────────────────────────────────────────────────────
PLANETS = [
    {"name":"☿ Меркурий / Mercury / כוכב חמה / عطارد","dist":"57.9M km","period":"88d","day":"58.6d","temp":"-180/+430°C","moons":0,"radius":"2440km","fact":{"ru":"Самый большой перепад температур.","en":"Largest temperature range.","he":"הפרש הטמפרטורות הגדול ביותר.","ar":"أكبر مدى حراري."}},
    {"name":"♀ Венера / Venus / נוגה / الزهرة","dist":"108M km","period":"225d","day":"243d","temp":"+465°C","moons":0,"radius":"6051km","fact":{"ru":"Горячее Меркурия. Вращается обратно.","en":"Hotter than Mercury. Spins backwards.","he":"חמה ממרקורי. מסתובבת הפוך.","ar":"أحر من عطارد. تدور عكسياً."}},
    {"name":"🌍 Земля / Earth / כדור הארץ / الأرض","dist":"150M km","period":"365.25d","day":"24h","temp":"-88/+58°C","moons":1,"radius":"6371km","fact":{"ru":"Единственная известная планета с жизнью.","en":"Only known planet with life.","he":"כוכב הלכת היחיד הידוע עם חיים.","ar":"الكوكب الوحيد المعروف بالحياة."}},
    {"name":"♂ Марс / Mars / מאדים / المريخ","dist":"228M km","period":"687d","day":"24h37m","temp":"-125/+20°C","moons":2,"radius":"3390km","fact":{"ru":"Гора Олимп — 21 км высотой.","en":"Olympus Mons — 21km tall.","he":"הר אולימפוס — 21 ק\"מ גובה.","ar":"جبل أوليمبوس — 21 كم ارتفاعاً."}},
    {"name":"♃ Юпитер / Jupiter / צדק / المشتري","dist":"778M km","period":"11.9y","day":"9h56m","temp":"-108°C","moons":95,"radius":"71492km","fact":{"ru":"БКП — шторм более 350 лет.","en":"GRS storm — 350+ years old.","he":"סערת הכתם האדום — 350+ שנה.","ar":"العاصفة الحمراء الكبرى — أكثر من 350 سنة."}},
    {"name":"♄ Сатурн / Saturn / שבתאי / زحل","dist":"1.43B km","period":"29.5y","day":"10h33m","temp":"-139°C","moons":146,"radius":"60268km","fact":{"ru":"Плавал бы в воде!","en":"Would float in water!","he":"היה צף על מים!","ar":"سيطفو على الماء!"}},
    {"name":"⛢ Уран / Uranus / אורנוס / أورانوس","dist":"2.87B km","period":"84y","day":"17h14m","temp":"-197°C","moons":28,"radius":"25559km","fact":{"ru":"Ось наклонена на 98°.","en":"Axis tilted 98°.","he":"ציר מוטה ב-98°.","ar":"محوره مائل بزاوية 98°."}},
    {"name":"♆ Нептун / Neptune / נפטון / نبتون","dist":"4.5B km","period":"165y","day":"16h6m","temp":"-201°C","moons":16,"radius":"24622km","fact":{"ru":"Ветер до 2100 км/ч.","en":"Winds up to 2100 km/h.","he":"רוחות עד 2100 קמ\"ש.","ar":"رياح تصل إلى 2100 كم/ساعة."}},
]

SPACE_FACTS = {
    "ru":[
        "🌌 Вселенной ~13.8 млрд лет. Земля появилась спустя 9 млрд.",
        "⭐ Звёзд во Вселенной больше, чем песчинок на всех пляжах Земли — ~10²⁴.",
        "🌑 Следы Армстронга на Луне сохранятся миллионы лет — там нет ветра.",
        "☀️ Свет от Солнца летит 8 мин 20 сек. От Альфы Центавра — 4.2 года.",
        "🪐 День на Венере длиннее её года.",
        "🌊 На Энцеладе Сатурна бьют гейзеры воды — возможна жизнь.",
        "⚫ Если сжать Землю до горошины — она станет чёрной дырой.",
        "🚀 Вояджер-1 вышел за пределы Солнечной системы в 2012 году.",
    ],
    "en":[
        "🌌 The Universe is ~13.8 billion years old. Earth appeared 9 billion years later.",
        "⭐ There are more stars in the Universe than grains of sand on all Earth's beaches.",
        "🌑 Armstrong's footprints on the Moon will last millions of years — no wind there.",
        "☀️ Sunlight takes 8 min 20 sec to reach Earth. Proxima: 4.2 years.",
        "🪐 A day on Venus is longer than its year.",
        "🌊 Saturn's Enceladus has water geysers — life may exist there.",
        "⚫ If Earth were compressed to a marble size, it would become a black hole.",
        "🚀 Voyager 1 entered interstellar space in 2012.",
    ],
    "he":[
        "🌌 היקום בן ~13.8 מיליארד שנה. כדור הארץ הופיע 9 מיליארד שנה אחר כך.",
        "⭐ מספר הכוכבים ביקום גדול ממספר גרגרי החול בכל חופי העולם.",
        "🌑 עקבות ארמסטרונג על הירח ישמרו מיליוני שנים — אין שם רוח.",
        "☀️ האור מהשמש מגיע לכדור הארץ תוך 8 דקות ו-20 שניות.",
        "🪐 יום על נוגה ארוך מהשנה שלה.",
        "🌊 לאנקלדוס של שבתאי יש גייזרים של מים — ייתכן שיש שם חיים.",
        "⚫ אם כדור הארץ היה מתכווץ לגודל גולה — הוא היה הופך לחור שחור.",
        "🚀 ווֹיאַג'ר 1 נכנס למרחב הבין-כוכבי ב-2012.",
    ],
    "ar":[
        "🌌 عمر الكون ~13.8 مليار سنة. ظهرت الأرض بعد 9 مليارات سنة.",
        "⭐ عدد النجوم في الكون أكثر من حبات الرمل في جميع شواطئ الأرض.",
        "🌑 آثار أقدام أرمسترونغ على القمر ستبقى ملايين السنين — لا توجد هناك رياح.",
        "☀️ ضوء الشمس يصل إلى الأرض في 8 دقائق و20 ثانية.",
        "🪐 يوم على كوكب الزهرة أطول من سنته.",
        "🌊 لقمر إنسيلادوس التابع لزحل ينابيع مياه — قد توجد حياة هناك.",
        "⚫ لو ضُغطت الأرض إلى حجم كرة رخام، ستصبح ثقباً أسود.",
        "🚀 دخل فوياجر 1 الفضاء النجمي البيني عام 2012.",
    ],
}

METEOR_SHOWERS = [
    {"name":{"ru":"Персеиды","en":"Perseids","he":"פרסאידים","ar":"البرشاويات"},"peak":"12-13 Aug","rate":"100+/h","parent":"Swift-Tuttle","speed":"59km/s"},
    {"name":{"ru":"Геминиды","en":"Geminids","he":"גמינידים","ar":"الجوزائيات"},"peak":"13-14 Dec","rate":"120+/h","parent":"3200 Phaethon","speed":"35km/s"},
    {"name":{"ru":"Леониды","en":"Leonids","he":"ליאונידים","ar":"الأسديات"},"peak":"17-18 Nov","rate":"10-15/h","parent":"Tempel-Tuttle","speed":"71km/s"},
]

KNOWN_EXOPLANETS = [
    {"name":"Kepler-452b","star":"Kepler-452","year":2015,"radius":1.63,"period":384.8,"dist_ly":1400,"note":{"ru":"Двойник Земли в обитаемой зоне","en":"Earth twin in habitable zone","he":"כפיל כדור הארץ באזור הניתן למגורים","ar":"توأم الأرض في المنطقة الصالحة للحياة"}},
    {"name":"TRAPPIST-1e","star":"TRAPPIST-1","year":2017,"radius":0.92,"period":6.1,"dist_ly":39,"note":{"ru":"Возможна жидкая вода","en":"Possible liquid water","he":"מים נוזליים אפשריים","ar":"يُحتمل وجود ماء سائل"}},
    {"name":"Proxima Centauri b","star":"Proxima Cen","year":2016,"radius":1.3,"period":11.2,"dist_ly":4.2,"note":{"ru":"Ближайшая к Солнцу экзопланета!","en":"Nearest exoplanet to the Sun!","he":"האקסופלנטה הקרובה ביותר לשמש!","ar":"أقرب كوكب خارج المجموعة الشمسية!"}},
    {"name":"Kepler-22b","star":"Kepler-22","year":2011,"radius":2.4,"period":289.9,"dist_ly":638,"note":{"ru":"В обитаемой зоне","en":"In habitable zone","he":"באזור הניתן למגורים","ar":"في المنطقة الصالحة للحياة"}},
    {"name":"TOI 700 d","star":"TOI 700","year":2020,"radius":1.19,"period":37.4,"dist_ly":101,"note":{"ru":"Земного размера, открыта TESS","en":"Earth-sized, found by TESS","he":"בגודל כדור הארץ, התגלתה על ידי TESS","ar":"بحجم الأرض، اكتُشفت بواسطة TESS"}},
]


# ── NASA IMAGE HELPER ────────────────────────────────────────────────────────
async def send_nasa_image(q, context, queries, cb_data=""):
    lang = get_lang(context)
    query_word = random.choice(queries)
    try:
        r = requests.get("https://images-api.nasa.gov/search",
            params={"q": query_word, "media_type": "image", "page_size": 40}, timeout=12)
        r.raise_for_status()
        items = [it for it in r.json().get("collection", {}).get("items", []) if it.get("links")]
        if not items:
            await safe_edit(q, tx(lang, "no_img"), reply_markup=back_kb(lang, context=context))
            return
        item   = random.choice(items[:25])
        data   = item.get("data", [{}])[0]
        links  = item.get("links", [])
        title  = data.get("title", "NASA")
        desc   = strip_html(data.get("description", ""))[:400]
        date_c = (data.get("date_created") or "")[:10]
        center = data.get("center", "NASA")
        img_url = links[0].get("href", "") if links else ""
        caption = f"*{title}*\n📅 {date_c}  |  🏛 {center}\n\n{desc + '…' if desc else ''}"
        kb = action_kb(lang, cb_data, "btn_another", context) if cb_data else back_kb(lang, context=context)
        await del_msg(q)
        if img_url:
            try:
                await context.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                    caption=caption[:1024], parse_mode="Markdown", reply_markup=kb)
                return
            except: pass
        await context.bot.send_message(chat_id=q.message.chat_id, text=caption[:4096],
            parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"NASA image {e}")
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang, context=context))

# ── START & MENU ─────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    name = update.effective_user.first_name or "космонавт"
    await update.message.reply_text(
        tx(lang, "choose_lang"), parse_mode="Markdown", reply_markup=lang_keyboard())

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await update.message.reply_text(tx(lang, "main_menu"), parse_mode="Markdown", reply_markup=main_menu_kb(lang))

async def choose_lang_handler(update, context):
    q = update.callback_query
    await safe_answer(q)
    await safe_edit(q, tx("ru", "choose_lang"), reply_markup=lang_keyboard())

async def setlang_handler(update, context):
    q = update.callback_query
    await safe_answer(q)
    new_lang = q.data.split("_")[1]
    context.user_data["lang"] = new_lang
    lang = new_lang
    name = q.from_user.first_name or "космонавт"
    await safe_edit(q,
        tx(lang, "lang_set") + "\n\n" + tx(lang, "start_msg", name=name),
        reply_markup=main_menu_kb(lang))

# ── APOD ─────────────────────────────────────────────────────────────────────
async def _send_apod(q, context, params=None):
    lang = get_lang(context)
    try:
        data  = nasa("/planetary/apod", params)
        title = data.get("title","")
        expl  = strip_html(data.get("explanation",""))[:900]
        url   = data.get("url","")
        hdurl = data.get("hdurl", url)
        mtype = data.get("media_type","image")
        d     = data.get("date","")
        copy_ = data.get("copyright","NASA").strip().replace("\n"," ")
        caption = f"🌌 *{title}*\n📅 {d}  |  © {copy_}\n\n{expl}…\n\n[🔗 HD]({hdurl})"
        kb = (action_kb(lang, "apod_random", "btn_more_rnd", context) if params
              else back_kb(lang, context=context))
        await del_msg(q)
        if mtype == "image":
            await context.bot.send_photo(chat_id=q.message.chat_id, photo=url,
                caption=caption, parse_mode="Markdown", reply_markup=kb)
        else:
            await context.bot.send_message(chat_id=q.message.chat_id,
                text=caption + f"\n\n[▶️]({url})", parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        logger.error(f"APOD: {e}")
        await safe_edit(q, f"{tx(lang,'err')} APOD: `{e}`", reply_markup=back_kb(lang, context=context))

async def apod_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "⏳ APOD...")
    await _send_apod(q, context)

async def apod_random_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    await safe_edit(q, "🎲...")
    s = date(1995, 6, 16)
    rnd = s + timedelta(days=random.randint(0, (date.today()-s).days))
    await _send_apod(q, context, {"date": rnd.isoformat()})

# ── EARTH / EPIC ─────────────────────────────────────────────────────────────
EARTH_Q = ["earth from space","earth orbit astronaut","earth blue marble","earth ISS view","earth nasa satellite"]

async def epic_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🌍...")
    await send_nasa_image(q, context, EARTH_Q, "epic")

# ── MARS ─────────────────────────────────────────────────────────────────────
MARS_FACTS = {
    "ru":["Олимп — 21 км. Эверест — лишь 8.8 км.","Curiosity проехал >33 км по Марсу.","Марсианские сутки — 24 ч 37 мин.","Гравитация 38% от земной.","Пылевые бури размером с континент."],
    "en":["Olympus Mons — 21km. Everest — only 8.8km.","Curiosity traveled >33km on Mars.","Martian day — 24h 37min.","Gravity is 38% of Earth's.","Dust storms the size of a continent."],
    "he":["הר אולימפוס — 21 ק\"מ. אוורסט — רק 8.8 ק\"מ.","קיוריוסיטי נסעה >33 ק\"מ על מאדים.","יום מאדימי — 24 שעות ו-37 דקות.","כוח משיכה 38% מכדור הארץ.","סופות אבק בגודל יבשת."],
    "ar":["أوليمبوس مونس — 21 كم. إيفرست — 8.8 كم فقط.","كيوريوسيتي قطعت >33 كم على المريخ.","اليوم المريخي — 24 ساعة و37 دقيقة.","الجاذبية 38% من جاذبية الأرض.","عواصف ترابية بحجم قارة."],
}
MARS_Q = ["mars surface curiosity rover","mars landscape nasa","mars crater rover","mars perseverance rover","mars olympus mons"]
ROVER_NAMES = ["curiosity","perseverance"]

async def mars_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🤖...")
    try:
        photos = []
        for sol in random.sample([100,200,300,500,750,1000,1200,1500],4):
            try:
                r = requests.get(f"{NASA_BASE}/mars-photos/api/v1/rovers/curiosity/photos",
                    params={"sol":sol,"api_key":NASA_API_KEY,"page":1}, timeout=10)
                if r.status_code==200:
                    photos = r.json().get("photos",[])
                    if photos: break
            except: continue
        if photos:
            p = random.choice(photos[:20])
            fact = random.choice(MARS_FACTS.get(lang, MARS_FACTS["en"]))
            caption = (f"🤖 *{p['rover']['name']}*\n📅 {p['earth_date']}  |  Sol: {p['sol']}\n"
                       f"📷 {p['camera']['full_name']}\n\n💡 *{fact}*")
            await del_msg(q)
            await context.bot.send_photo(chat_id=q.message.chat_id, photo=p["img_src"],
                caption=caption, parse_mode="Markdown",
                reply_markup=action_kb(lang,"mars","btn_another",context))
            return
    except Exception as e:
        logger.error(f"Mars rover API: {e}")
    await send_nasa_image(q, context, MARS_Q, "mars")

async def mars_rovers_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🤖...")
    try:
        rover = random.choice(ROVER_NAMES)
        for sol in random.sample(list(range(50,1800)),8):
            try:
                r = requests.get(f"{NASA_BASE}/mars-photos/api/v1/rovers/{rover}/photos",
                    params={"sol":sol,"api_key":NASA_API_KEY,"page":1}, timeout=10)
                if r.status_code!=200: continue
                photos = r.json().get("photos",[])
                if not photos: continue
                p = random.choice(photos[:15])
                img = p.get("img_src","")
                if not img: continue
                caption = (f"🤖 *{p.get('rover',{}).get('name',rover.title())}*\n"
                           f"📅 {p.get('earth_date','')}  |  Sol: {p.get('sol',sol)}\n"
                           f"📷 {p.get('camera',{}).get('full_name','—')}")
                await del_msg(q)
                await context.bot.send_photo(chat_id=q.message.chat_id, photo=img,
                    caption=caption, parse_mode="Markdown",
                    reply_markup=action_kb(lang,"mars_rovers","btn_other_rv",context))
                return
            except: continue
        await safe_edit(q, tx(lang,"no_img"), reply_markup=back_kb(lang,context=context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,context=context))

# ── ASTEROIDS ────────────────────────────────────────────────────────────────
async def asteroids_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "☄️...")
    try:
        today = date.today().isoformat()
        data  = nasa("/neo/rest/v1/feed", {"start_date":today,"end_date":today})
        neos  = data["near_earth_objects"].get(today,[])
        if not neos:
            await safe_edit(q, tx(lang,"no_data"), reply_markup=back_kb(lang,"asteroids",context))
            return
        danger = sum(1 for a in neos if a["is_potentially_hazardous_asteroid"])
        neos_s = sorted(neos, key=lambda a: float(a["close_approach_data"][0]["miss_distance"]["kilometers"]) if a["close_approach_data"] else 9e99)
        text = f"☄️ *{today}*\n📊 {len(neos)}  |  ⚠️ {danger}\n\n"
        for i, ast in enumerate(neos_s[:6], 1):
            name  = ast["name"].replace("(","").replace(")","").strip()
            d_min = ast["estimated_diameter"]["meters"]["estimated_diameter_min"]
            d_max = ast["estimated_diameter"]["meters"]["estimated_diameter_max"]
            hz    = tx(lang,"hazard_yes") if ast["is_potentially_hazardous_asteroid"] else tx(lang,"hazard_no")
            ap    = ast["close_approach_data"][0] if ast["close_approach_data"] else {}
            speed = ap.get("relative_velocity",{}).get("kilometers_per_hour","?")
            dist_km = ap.get("miss_distance",{}).get("kilometers","?")
            dist_ld = ap.get("miss_distance",{}).get("lunar","?")
            close_t = ap.get("close_approach_date_full","?")
            try: speed=f"{float(speed):,.0f} km/h"
            except: pass
            try: dist_km=f"{float(dist_km):,.0f} km"
            except: pass
            try: dist_ld=f"{float(dist_ld):.2f} LD"
            except: pass
            text += f"*{i}. {name}*  {hz}\n⏰ {close_t}\n📏 {d_min:.0f}–{d_max:.0f}m  🚀 {speed}\n📍 {dist_km} ({dist_ld})\n\n"
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"asteroids",context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,context=context))

# ── ISS ──────────────────────────────────────────────────────────────────────
async def iss_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🛸...")
    try:
        pos  = get_json("http://api.open-notify.org/iss-now.json", timeout=10)
        lat  = float(pos["iss_position"]["latitude"])
        lon  = float(pos["iss_position"]["longitude"])
        ts   = datetime.utcfromtimestamp(pos["timestamp"]).strftime("%H:%M:%S UTC")
        try:
            crew_r = requests.get("http://api.open-notify.org/astros.json", timeout=10)
            people = crew_r.json().get("people",[]) if crew_r.ok else []
        except: people = []
        iss_crew = [p["name"] for p in people if p.get("craft")=="ISS"]
        crew_str = "\n".join(f"   👨‍🚀 {n}" for n in iss_crew) or f"   {tx(lang,'iss_no_crew')}"
        map_link = tx(lang,"iss_map")
        text = (f"🛸 *ISS — {ts}*\n\n"
                f"🌍 `{lat:.4f}°` | 🌏 `{lon:.4f}°`\n"
                f"⚡ ~27,600 km/h  |  🏔 ~408 km\n\n"
                f"👨‍🚀 Crew ({len(iss_crew)}):\n{crew_str}\n\n"
                f"[🗺 {map_link}](https://www.google.com/maps?q={lat},{lon})")
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"iss",context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')} ISS: `{e}`", reply_markup=back_kb(lang,context=context))

# ── EXOPLANETS ───────────────────────────────────────────────────────────────
async def exoplanets_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🔭...")
    selection = random.sample(KNOWN_EXOPLANETS, min(4, len(KNOWN_EXOPLANETS)))
    text = "🔭 *Exoplanets / Экзопланеты*\n\n"
    for p in selection:
        note = p["note"].get(lang, p["note"]["en"])
        text += (f"🪐 *{p['name']}* — {p['star']}\n"
                 f"   📅 {p['year']}  |  📏 {p['radius']} R🌍  |  🔄 {p['period']}d  |  📡 {p['dist_ly']} ly\n"
                 f"   💡 _{note}_\n\n")
    text += "[🔗 NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu)"
    await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"exoplanets",context))

# ── SPACE WEATHER ────────────────────────────────────────────────────────────
async def spaceweather_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🌞...")
    try:
        end   = date.today().isoformat()
        start = (date.today()-timedelta(days=7)).isoformat()
        flares = nasa("/DONKI/FLR",{"startDate":start,"endDate":end}) or []
        cmes   = nasa("/DONKI/CME",{"startDate":start,"endDate":end}) or []
        storms = nasa("/DONKI/GST",{"startDate":start,"endDate":end}) or []
        text = f"🌞 *Space Weather — 7 days*\n\n⚡ Flares: *{len(flares)}*\n"
        for f in flares[-3:]:
            text += f"   • {f.get('classType','?')} — {(f.get('peakTime') or '')[:16].replace('T',' ')}\n"
        text += f"\n🌊 CME: *{len(cmes)}*\n"
        for c in cmes[-2:]:
            text += f"   • {(c.get('startTime') or '')[:16].replace('T',' ')}\n"
        text += f"\n🧲 Storms: *{len(storms)}*\n"
        for s in storms[-2:]:
            kp_idx = s.get("allKpIndex",[{}])
            kp_val = kp_idx[-1].get("kpIndex","?") if kp_idx else "?"
            text  += f"   • {(s.get('startTime') or '')[:16].replace('T',' ')}  Kp: *{kp_val}*\n"
        text += "\n📊 Kp: 0–3 🟢  4–5 🟡  6–7 🟠  8–9 🔴\n\n[NOAA](https://www.swpc.noaa.gov)"
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"spaceweather",context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,context=context))

# ── LAUNCHES ─────────────────────────────────────────────────────────────────
async def launches_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🚀...")
    try:
        data = get_json("https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=7&ordering=net&mode=list", timeout=15)
        launches = data.get("results",[])
        if not launches:
            await safe_edit(q, tx(lang,"no_data"), reply_markup=back_kb(lang,context=context)); return
        text = "🚀 *Upcoming Launches*\n\n"
        for i, lc in enumerate(launches[:6], 1):
            if not isinstance(lc, dict): continue
            try:
                name   = str(lc.get("name","?"))
                rocket = str((lc.get("rocket") or {}).get("configuration",{}).get("name","?"))
                prov   = str((lc.get("launch_service_provider") or {}).get("name","?"))
                net    = str(lc.get("net","?"))
                stat_a = str((lc.get("status") or {}).get("abbrev","?"))
                orbit  = str(((lc.get("mission") or {}).get("orbit") or {}).get("name","LEO"))
                loc    = str(((lc.get("pad") or {}).get("location") or {}).get("name","?"))
                try:
                    dt = datetime.fromisoformat(net.replace("Z","+00:00"))
                    net = dt.strftime("%d.%m.%Y %H:%M UTC")
                except: pass
                emoji = {"Go":"✅","TBD":"❓","TBC":"🔸","Success":"🎉","Failure":"❌"}.get(stat_a,"🕐")
                text += f"*{i}. {name}*\n   🚀 {rocket}  |  {prov}\n   🛰 {orbit}  |  📍 {loc}\n   ⏰ {net}  {emoji}\n\n"
            except: continue
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"launches",context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,context=context))

# ── GALLERY ──────────────────────────────────────────────────────────────────
GALLERY_Q = ["nebula","galaxy","black hole","supernova","aurora","saturn rings","jupiter storm","andromeda","solar flare","moon surface"]

async def gallery_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    await safe_edit(q, "🖼...")
    await send_nasa_image(q, context, GALLERY_Q, "gallery")

# ── SPACE FACT ───────────────────────────────────────────────────────────────
async def spacefact_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    fact = random.choice(SPACE_FACTS.get(lang, SPACE_FACTS["en"]))
    await safe_edit(q, f"⭐ *Fact*\n\n{fact}", reply_markup=back_kb(lang,"spacefact",context))

# ── CHANNELS ─────────────────────────────────────────────────────────────────
async def channels_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, CHANNELS_TEXT.get(lang, CHANNELS_TEXT["ru"]),
                    reply_markup=back_kb(lang, context=context))

# ── PLANETS ──────────────────────────────────────────────────────────────────
async def planets_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    p = random.choice(PLANETS)
    fact = p["fact"].get(lang, p["fact"]["en"])
    text = (f"🪐 *{p['name']}*\n\n📏 {p['radius']}  |  📡 {p['dist']}\n"
            f"🔄 {p['period']}  |  🌅 {p['day']}\n🌡 {p['temp']}  |  🌙 {p['moons']}\n\n💡 *{fact}*")
    await safe_edit(q, text, reply_markup=back_kb(lang,"planets",context))

# ── MOON PHASE ───────────────────────────────────────────────────────────────
async def moon_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    known_new = date(2024,1,11)
    cycle_day = (date.today()-known_new).days % 29.53
    phases = tx(lang,"moon_phases")
    if   cycle_day < 1.85:  emoji,idx = "🌑",0
    elif cycle_day < 7.38:  emoji,idx = "🌒",1
    elif cycle_day < 9.22:  emoji,idx = "🌓",2
    elif cycle_day < 14.77: emoji,idx = "🌔",3
    elif cycle_day < 16.61: emoji,idx = "🌕",4
    elif cycle_day < 22.15: emoji,idx = "🌖",5
    elif cycle_day < 23.99: emoji,idx = "🌗",6
    else:                   emoji,idx = "🌘",7
    phase_name = phases[idx] if isinstance(phases, list) else "?"
    illum = round((1 - abs(cycle_day-14.77)/14.77)*100)
    next_full = round(15-cycle_day if cycle_day<15 else 29.53-cycle_day+15)
    next_new  = round(29.53-cycle_day)
    text = (f"{emoji} *Moon Phase / Фаза Луны*\n\n📅 {date.today()}\n"
            f"🌙 *{phase_name}*\n💡 ~{illum}%  |  Day {cycle_day:.1f}/29.5\n\n"
            f"⏳ Full: ~{next_full}d  |  New: ~{next_new}d\n"
            f"• 384,400 km  • Ø 3,474 km")
    await safe_edit(q, text, reply_markup=back_kb(lang,"moon",context))

# ── SATELLITES ───────────────────────────────────────────────────────────────
async def satellites_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "📡...")
    try:
        sl = get_json("https://api.spacexdata.com/v4/starlink", timeout=10)
        total  = len(sl)
        active = sum(1 for s in sl if isinstance(s,dict) and not (s.get("spaceTrack") or {}).get("DECAY_DATE"))
    except: total=active="?"
    text = (f"📡 *Satellites*\n\n🌍 In orbit: ~9,000+  |  Active: ~7,500+\n"
            f"🛸 *Starlink:* {total} total, {active} active\n\n[🔗 n2yo.com](https://www.n2yo.com)")
    await safe_edit(q, text, reply_markup=back_kb(lang,"satellites",context))

# ── METEORS ──────────────────────────────────────────────────────────────────
async def meteors_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    text = "🌠 *Meteor Showers*\n\n"
    for m in METEOR_SHOWERS:
        name = m["name"].get(lang, m["name"]["en"])
        text += f"✨ *{name}* — {m['peak']}\n   ⚡ {m['speed']}  |  🌠 {m['rate']}  |  {m['parent']}\n\n"
    text += "💡 Best: 00:00–04:00, dark sky, 20 min adaptation."
    await safe_edit(q, text[:4096], reply_markup=back_kb(lang,context=context))

# ── TELESCOPES ───────────────────────────────────────────────────────────────
async def telescopes_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    text = ("🔬 *Greatest Telescopes*\n\n"
            "🌌 *JWST* — 6.5m, L2, IR, 13.5 Gly\n"
            "🔭 *Hubble* — 2.4m, 547km, >1.6M obs\n"
            "📡 *VLT* — 4×8.2m  |  *ALMA* — 66 antennas\n"
            "🌐 *FAST* — 500m (world's largest)\n"
            "🔭 *ELT (~2028)* — 39m mirror")
    await safe_edit(q, text, reply_markup=back_kb(lang,context=context))


# ── IMAGE HANDLERS (using send_nasa_image) ───────────────────────────────────
async def _img(cb, queries, msg="⏳..."):
    async def handler(update, context):
        q = update.callback_query; await safe_answer(q)
        await safe_edit(q, msg)
        await send_nasa_image(q, context, queries, cb)
    return handler

# ── STATIC TEXT HANDLERS ─────────────────────────────────────────────────────
def _static(text_key_or_fn):
    async def handler(update, context):
        q = update.callback_query; await safe_answer(q)
        lang = get_lang(context)
        text = text_key_or_fn(lang) if callable(text_key_or_fn) else text_key_or_fn
        cb = q.data
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang, cb, context))
    return handler

def kuiper_text(lang):
    texts = {
        "ru":"📦 *Пояс Койпера*\n\nОбласть за Нептуном (30–55 а.е.), тысячи ледяных тел.\n• Плутон, Эрида, Макемаке, Хаумеа\n• New Horizons посетил Плутон (2015) и Аррокот (2019)\n\n💡 Хранит древнее вещество Солнечной системы.",
        "en":"📦 *Kuiper Belt*\n\nRegion beyond Neptune (30–55 AU), thousands of icy bodies.\n• Pluto, Eris, Makemake, Haumea — dwarf planets\n• New Horizons visited Pluto (2015) and Arrokoth (2019)\n\n💡 Preserves primordial Solar System material.",
        "he":"📦 *חגורת קויפר*\n\nאזור מעבר לנפטון (30–55 AU), אלפי גופים קפואים.\n• פלוטו, אריס, מאקמאקה, האומאה\n• New Horizons ביקר בפלוטו (2015) ובארוקות' (2019)\n\n💡 שומרת חומר קדמוני של מערכת השמש.",
        "ar":"📦 *حزام كويبر*\n\nمنطقة ما وراء نبتون (30–55 AU)، آلاف الأجسام الجليدية.\n• بلوتو، إيريس، ماكيماكي، هاوميا\n• New Horizons زار بلوتو (2015) وأروكوث (2019)\n\n💡 يحفظ مواد بدائية للمجموعة الشمسية.",
    }
    return texts.get(lang, texts["en"])

def alignment_text(lang):
    texts = {
        "ru":"🪐 *Парад планет*\n\nРедко все планеты выстраиваются в ряд.\n• Марс, Юпитер, Сатурн видны невооружённым глазом\n• Полный парад (все 8) — раз в сотни лет\n\n💡 Декабрь 2022 — парад всех видимых планет.",
        "en":"🪐 *Planet Parade*\n\nRarely do all planets align.\n• Mars, Jupiter, Saturn visible to the naked eye when close\n• Full parade (all 8) — once every few hundred years\n\n💡 December 2022 had a parade of all visible planets.",
        "he":"🪐 *מצעד כוכבים*\n\n• מאדים, צדק, שבתאי — נראים בעין בלתי מזוינת\n• מצעד מלא (כל 8) — פעם בכמה מאות שנים\n\n💡 דצמבר 2022 — מצעד של כל הכוכבים הנראים.",
        "ar":"🪐 *استعراض الكواكب*\n\n• المريخ، المشتري، زحل — مرئية بالعين المجردة\n• استعراض كامل (جميع 8) — مرة كل مئات السنين\n\n💡 ديسمبر 2022 — استعراض جميع الكواكب المرئية.",
    }
    return texts.get(lang, texts["en"])

def solar_ecl_text(lang):
    texts = {
        "ru":"☀️ *Солнечные затмения*\n\n• 2026 — Испания  • 2027 — Сев. Африка  • 2028 — Австралия\n• В полной фазе видна корона и звёзды днём\n\n💡 Полное затмение в одном месте — раз в ~375 лет.",
        "en":"☀️ *Solar Eclipses*\n\n• 2026 — Spain  • 2027 — North Africa  • 2028 — Australia\n• During totality: corona & stars visible by day\n\n💡 Total eclipse at same location — once in ~375 years.",
        "he":"☀️ *ליקויי חמה*\n\n• 2026 — ספרד  • 2027 — צפון אפריקה  • 2028 — אוסטרליה\n• בשלב מלא: הקורונה וכוכבים נראים ביום\n\n💡 ליקוי מלא באותו מקום — פעם ב-375~ שנים.",
        "ar":"☀️ *كسوف الشمس*\n\n• 2026 — إسبانيا  • 2027 — شمال أفريقيا  • 2028 — أستراليا\n• في الكسوف الكلي: الهالة والنجوم مرئية نهاراً\n\n💡 كسوف كلي في نفس المكان — مرة كل ~375 سنة.",
    }
    return texts.get(lang, texts["en"])

def scale_text(lang):
    texts = {
        "ru":"📏 *Масштаб Солнечной системы*\n\nЕсли Солнце = мяч 1 м:\n• Меркурий — 4 мм, 43 м\n• Земля — 1 см, 117 м\n• Юпитер — 11 см, 600 м\n• Нептун — 3 см, 3.5 км\n• Проксима — 2 800 км!\n\n💡 Космос в основном пуст.",
        "en":"📏 *Solar System Scale*\n\nIf Sun = 1m ball:\n• Mercury — 4mm, 43m\n• Earth — 1cm, 117m\n• Jupiter — 11cm, 600m\n• Neptune — 3cm, 3.5km\n• Proxima — 2,800 km!\n\n💡 Space is mostly empty.",
        "he":"📏 *קנה מידה של מערכת השמש*\n\nאם השמש = כדור של 1 מ':\n• כוכב חמה — 4מ\"מ, 43מ'\n• כדור הארץ — 1ס\"מ, 117מ'\n• נפטון — 3ס\"מ, 3.5ק\"מ\n• פרוקסימה — 2,800 ק\"מ!\n\n💡 החלל בעיקרו ריק.",
        "ar":"📏 *مقياس المجموعة الشمسية*\n\nإذا كانت الشمس = كرة 1م:\n• عطارد — 4مم، 43م\n• الأرض — 1سم، 117م\n• نبتون — 3سم، 3.5كم\n• بروكسيما — 2,800 كم!\n\n💡 الفضاء في معظمه فراغ.",
    }
    return texts.get(lang, texts["en"])

def darkmatter_text(lang):
    texts = {
        "ru":"🌑 *Тёмная материя и тёмная энергия*\n\n📊 5% обычная, 27% тёмная материя, 68% тёмная энергия.\n⚫ Тёмная материя обнаружена по гравитации.\n⚡ Тёмная энергия ускоряет расширение (Нобель 2011).\n\n🔭 Телескопы Евклид и Nancy Roman изучают.",
        "en":"🌑 *Dark Matter & Dark Energy*\n\n📊 5% ordinary, 27% dark matter, 68% dark energy.\n⚫ Dark matter detected via gravity — emits no light.\n⚡ Dark energy accelerates expansion (Nobel 2011).\n\n🔭 Euclid & Nancy Roman are studying it.",
        "he":"🌑 *חומר אפל ואנרגיה אפלה*\n\n📊 5% חומר רגיל, 27% חומר אפל, 68% אנרגיה אפלה.\n⚫ חומר אפל נגלה דרך כבידה — אינו פולט אור.\n⚡ אנרגיה אפלה מאיצה את ההתפשטות (נובל 2011).",
        "ar":"🌑 *المادة المظلمة والطاقة المظلمة*\n\n📊 5% عادية، 27% مظلمة، 68% طاقة مظلمة.\n⚫ المادة المظلمة مكتشفة بالجاذبية.\n⚡ الطاقة المظلمة تسرّع التمدد (نوبل 2011).",
    }
    return texts.get(lang, texts["en"])

def seti_text(lang):
    texts = {
        "ru":"👽 *SETI — поиск жизни*\n\nУравнение Дрейка. Послание Аресибо (1974). Сигнал Wow! (1977).\n🌱 Кандидаты: Европа, Энцелад, Марс, Титан.\n💡 Парадокс Ферми: если жизнь обычна — где все?",
        "en":"👽 *SETI — Search for Extraterrestrial Intelligence*\n\nDrake Equation. Arecibo Message (1974). Wow! Signal (1977).\n🌱 Candidates: Europa, Enceladus, Mars, Titan.\n💡 Fermi Paradox: if life is common — where is everyone?",
        "he":"👽 *SETI — חיפוש חיים בחלל*\n\nמשוואת דרייק. מסר אריסיבו (1974). אות Wow! (1977).\n🌱 מועמדים: אירופה, אנקלדוס, מאדים, טיטאן.\n💡 פרדוקס פרמי: אם חיים שכיחים — היכן כולם?",
        "ar":"👽 *SETI — البحث عن ذكاء خارج الأرض*\n\nمعادلة دريك. رسالة أريسيبو (1974). إشارة Wow! (1977).\n🌱 مرشحون: أوروبا، إنسيلادوس، المريخ، تيتان.\n💡 مفارقة فيرمي: إذا كانت الحياة شائعة — أين الجميع؟",
    }
    return texts.get(lang, texts["en"])

def gravwaves_text(lang):
    return {"ru":"🌊 *Гравитационные волны*\n\nGW150914 (2015) — слияние ЧД, 62 M☉. LIGO/Virgo.\nGW170817 (2017) — нейтронные звёзды. Нобель 2017.\nК 2024 — >90 событий.",
            "en":"🌊 *Gravitational Waves*\n\nGW150914 (2015) — BH merger, 62 M☉. LIGO/Virgo.\nGW170817 (2017) — neutron star merger. Nobel 2017.\nBy 2024 — >90 registered events.",
            "he":"🌊 *גלי כבידה*\n\nGW150914 (2015) — התמזגות חורים שחורים. LIGO/Virgo.\nGW170817 (2017) — כוכבי נייטרונים. נובל 2017.\nעד 2024 — >90 אירועים.",
            "ar":"🌊 *موجات الجاذبية*\n\nGW150914 (2015) — اندماج ثقبين أسودين. LIGO/Virgo.\nGW170817 (2017) — نجوم نيوترونية. نوبل 2017.\nحتى 2024 — >90 حدثاً."}.get(lang,"")

def future_text(lang):
    return {"ru":"🔮 *Будущее Вселенной*\n\n+5 млрд лет — Солнце → красный гигант → белый карлик.\n+4.5 млрд — столкновение с Андромедой.\n+100 трлн лет — эра вырождения.\nТепловая смерть или Большой Разрыв.",
            "en":"🔮 *Future of the Universe*\n\n+5B yrs — Sun → red giant → white dwarf.\n+4.5B — Milky Way collides with Andromeda.\n+100T yrs — degenerate era.\nHeat death or Big Rip.",
            "he":"🔮 *עתיד היקום*\n\n+5 מיליארד שנה — השמש תהיה ענק אדום → ננס לבן.\n+4.5 מיליארד — התנגשות עם אנדרומדה.\n+100 טריליון — עידן ניוון.",
            "ar":"🔮 *مستقبل الكون*\n\n+5 مليار سنة — الشمس → عملاق أحمر → قزم أبيض.\n+4.5 مليار — اصطدام مع أندروميدا.\n+100 تريليون — عصر التحلل."}.get(lang,"")

def grb_text(lang):
    return {"ru":"💥 *Гамма-всплески (GRB)*\n\nСамые мощные взрывы во Вселенной.\nДлинные — коллапс звезды. Короткие — слияние нейтронных звёзд.\nSwift, Fermi, INTEGRAL следят в реальном времени.",
            "en":"💥 *Gamma-Ray Bursts (GRB)*\n\nMost powerful explosions in the Universe.\nLong — stellar collapse. Short — neutron star merger.\nSwift, Fermi, INTEGRAL monitor in real time.",
            "he":"💥 *פרצי קרינת גמא (GRB)*\n\nהפיצוצים החזקים ביותר ביקום.\nארוכים — קריסת כוכב. קצרים — התמזגות כוכבי נייטרונים.",
            "ar":"💥 *انفجارات أشعة غاما (GRB)*\n\nأقوى الانفجارات في الكون.\nطويلة — انهيار نجم. قصيرة — اندماج نجوم نيوترونية."}.get(lang,"")

def radioastro_text(lang):
    return {"ru":"🔭 *Радиоастрономия*\n\nПульсары, реликтовое излучение, нейтральный водород 21 см, квазары, FRB.\nFAST (Китай) 500 м — крупнейший. Сигнал Wow! (1977) не объяснён.",
            "en":"🔭 *Radio Astronomy*\n\nPulsars, CMB, 21cm H, quasars, FRBs.\nFAST (China) 500m — world's largest. Wow! signal (1977) unexplained.",
            "he":"🔭 *רדיו אסטרונומיה*\n\nפולסרים, CMB, מימן 21ס\"מ, קווזרים, FRB.\nFAST (סין) 500מ' — הגדול בעולם. אות Wow! (1977) לא הוסבר.",
            "ar":"🔭 *الفلك الراديوي*\n\nنجوم نابضة، CMB، هيدروجين 21سم، كوازارات، FRBs.\nFAST (الصين) 500م — الأكبر في العالم."}.get(lang,"")

def dark_energy_text(lang):
    return {"ru":"⚡ *Тёмная энергия*\n\n68% Вселенной. Открыта 1998 — расширение ускоряется. Нобель 2011.\nПрирода неизвестна — главная загадка космологии.",
            "en":"⚡ *Dark Energy*\n\n68% of the Universe. Discovered 1998 — expansion accelerating. Nobel 2011.\nNature unknown — cosmology's greatest mystery.",
            "he":"⚡ *אנרגיה אפלה*\n\n68% מהיקום. התגלתה 1998 — ההתפשטות מואצת. נובל 2011.\nהטבע לא ידוע.",
            "ar":"⚡ *الطاقة المظلمة*\n\n68% من الكون. اكتُشفت 1998. نوبل 2011.\nطبيعتها مجهولة — اللغز الأكبر في الكونيات."}.get(lang,"")

def ozone_text(lang):
    return {"ru":"🛡 *Озоновый слой*\n\nЗащищает от УФ. Монреальский протокол (1987) — запрет CFC.\nДыра над Антарктидой медленно затягивается.",
            "en":"🛡 *Ozone Layer*\n\nProtects from UV. Montreal Protocol (1987) — CFC ban.\nAntarctic hole slowly recovering.",
            "he":"🛡 *שכבת האוזון*\n\nמגנה מUV. פרוטוקול מונטריאול (1987).\nחור האוזון מתאושש לאט.",
            "ar":"🛡 *طبقة الأوزون*\n\nتحمي من الأشعة فوق البنفسجية. بروتوكول مونتريال (1987).\nثقب الأوزون يتعافى تدريجياً."}.get(lang,"")

def ocean_cur_text(lang):
    return {"ru":"🌊 *Океанские течения*\n\nГольфстрим, Куросио — переносят тепло, влияют на климат.\nNASA JPL измеряет течения со спутников.",
            "en":"🌊 *Ocean Currents*\n\nGulf Stream, Kuroshio — transport heat, affect climate.\nNASA JPL measures from satellites.",
            "he":"🌊 *זרמי האוקיינוס*\n\nזרם המפרץ, קורושיו — מעבירים חום, משפיעים על האקלים.",
            "ar":"🌊 *تيارات المحيط*\n\nتيار الخليج، كوروشيو — ينقلان الحرارة، يؤثران على المناخ."}.get(lang,"")

def sp_stations_text(lang):
    return {"ru":"🛸 *Космические станции*\n\n• *МКС* (с 1998) — 420 т, ~408 км. Экипаж с 2000.\n• *Тяньгун (Китай)* — модульная на НОО.\n• *Gateway* (NASA, ~2028) — у Луны, для Artemis.",
            "en":"🛸 *Space Stations*\n\n• *ISS* (since 1998) — 420t, ~408km. Crew since 2000.\n• *Tiangong (China)* — modular LEO station.\n• *Gateway* (NASA, ~2028) — near Moon, for Artemis.",
            "he":"🛸 *תחנות חלל*\n\n• *ISS* (מ-1998) — 420 טון, ~408ק\"מ. צוות מ-2000.\n• *Tiangong (סין)* — תחנה מודולרית.\n• *Gateway* (NASA, ~2028) — ליד הירח.",
            "ar":"🛸 *محطات الفضاء*\n\n• *ISS* (منذ 1998) — 420 طن، ~408كم. طاقم منذ 2000.\n• *Tiangong (الصين)* — محطة معيارية.\n• *Gateway* (ناسا، ~2028) — قرب القمر."}.get(lang,"")

def women_text(lang):
    return {"ru":"👩‍🚀 *Женщины в космосе*\n\n• Терешкова (1963) — первая.\n• Салли Райд (1983) — первая американка.\n• Савицкая (1984) — первая в открытом космосе.\n• Пегги Уитсон — рекорд по времени.",
            "en":"👩‍🚀 *Women in Space*\n\n• Tereshkova (1963) — first woman.\n• Sally Ride (1983) — first American woman.\n• Savitskaya (1984) — first EVA.\n• Peggy Whitson — longest duration record.",
            "he":"👩‍🚀 *נשים בחלל*\n\n• טרשקובה (1963) — הראשונה.\n• סאלי רייד (1983) — האמריקאית הראשונה.\n• סביצקאיה (1984) — הראשונה בחלל פתוח.",
            "ar":"👩‍🚀 *المرأة في الفضاء*\n\n• تيريشكوفا (1963) — الأولى.\n• سالي رايد (1983) — أول أمريكية.\n• سافيتسكايا (1984) — أول تمشية فضائية."}.get(lang,"")

def mars_col_text(lang):
    return {"ru":"🔴 *Колонизация Марса*\n\nSpaceX (Starship), NASA, Китай — планы 2030–2040.\nПроблемы: радиация, гравитация, ресурсы.\nPerseverance тестирует производство кислорода.",
            "en":"🔴 *Mars Colonization*\n\nSpaceX (Starship), NASA, China — plans for 2030–2040.\nChallenges: radiation, gravity, resources.\nPerseverance tests oxygen production.",
            "he":"🔴 *קולוניזציה של מאדים*\n\nSpaceX (Starship), NASA, סין — תוכניות ל-2030–2040.\nאתגרים: קרינה, כבידה, משאבים.",
            "ar":"🔴 *استعمار المريخ*\n\nSpaceX (Starship)، ناسا، الصين — خطط 2030–2040.\nتحديات: الإشعاع، الجاذبية، الموارد."}.get(lang,"")

def sp_med_text(lang):
    return {"ru":"🩺 *Космическая медицина*\n\nНевесомость: потеря костной/мышечной массы.\nРадиация: лимит NASA — 600 мЗв за карьеру.\nИсследования МКС помогают при остеопорозе.",
            "en":"🩺 *Space Medicine*\n\nMicrogravity: bone & muscle loss.\nRadiation: NASA limit — 600 mSv per career.\nISS research helps with osteoporosis & aging.",
            "he":"🩺 *רפואת חלל*\n\nחוסר משקל: אובדן עצם ושריר.\nקרינה: מגבלת NASA — 600 mSv לקריירה.",
            "ar":"🩺 *الطب الفضائي*\n\nانعدام الوزن: فقدان العظام والعضلات.\nالإشعاع: حد ناسا — 600 mSv للمسيرة."}.get(lang,"")

def training_text(lang):
    return {"ru":"🎓 *Подготовка астронавтов*\n\nНейтральная плавучесть, центрифуги, тренажёры.\nРусский/английский для МКС. Аналоговые миссии (MDRS и др.).",
            "en":"🎓 *Astronaut Training*\n\nNeutral buoyancy, centrifuges, simulators.\nRussian/English for ISS. Analog missions (MDRS etc.).",
            "he":"🎓 *אימון אסטרונאוטים*\n\nציפה ניטרלית, צנטריפוגות, סימולטורים.\nרוסית/אנגלית ל-ISS. משימות אנלוג.",
            "ar":"🎓 *تدريب رواد الفضاء*\n\nالطفو المحايد، أجهزة الطرد المركزي، المحاكيات.\nالروسية/الإنجليزية لمحطة الفضاء."}.get(lang,"")

def debris_text(lang):
    return {"ru":"🛰 *Космический мусор*\n\n~50 000 отслеживаемых объектов. Скорость ~7.5 км/с.\nМКС маневрирует ~3 раза/год.\n[🔗 orbitaldebris.jsc.nasa.gov](https://orbitaldebris.jsc.nasa.gov)",
            "en":"🛰 *Space Debris*\n\n~50,000 tracked objects. Speed ~7.5 km/s.\nISS maneuvers ~3 times per year.\n[🔗 orbitaldebris.jsc.nasa.gov](https://orbitaldebris.jsc.nasa.gov)",
            "he":"🛰 *פסולת חלל*\n\n~50,000 עצמים עקובים. מהירות ~7.5 ק\"מ/ש'.\nISS מתמרנת ~3 פעמים בשנה.",
            "ar":"🛰 *حطام الفضاء*\n\n~50,000 جسم مرصود. السرعة ~7.5 كم/ث.\nمحطة الفضاء تناور ~3 مرات/سنة."}.get(lang,"")

def records_text(lang):
    return {"ru":"🏆 *Рекорды космоса*\n\n• Поляков — 437 суток (Мир, 1994–1995)\n• Кононенко — 1000+ суток (2024)\n• Вояджер-1 — >24 млрд км\n• Parker Probe — 700 000 км/ч\n• МКС — ~150 млрд $",
            "en":"🏆 *Space Records*\n\n• Polyakov — 437 days (Mir, 1994–1995)\n• Kononenko — 1000+ days total (2024)\n• Voyager-1 — >24B km\n• Parker Probe — 700,000 km/h\n• ISS — ~$150B",
            "he":"🏆 *שיאי חלל*\n\n• פוליאקוב — 437 ימים (Mir, 1994–1995)\n• קונוֹנֶנקוֹ — 1000+ ימים (2024)\n• Voyager-1 — >24 מיליארד ק\"מ\n• ISS — ~150 מיליארד $",
            "ar":"🏆 *أرقام قياسية فضائية*\n\n• بوليكوف — 437 يوماً (مير، 1994–1995)\n• كونونينكو — 1000+ يوم (2024)\n• Voyager-1 — >24 مليار كم\n• ISS — ~150 مليار $"}.get(lang,"")

def red_giants_text(lang):
    return {"ru":"🔴 *Красные гиганты и эволюция звёзд*\n\n• Солнце → красный гигант через ~5 млрд лет.\n• Сброс оболочки → планетарная туманность → белый карлик.\n• Звёзды >8 M☉ — сверхновая → нейтронная звезда или ЧД.\n\n💡 Бетельгейзе и Антарес видны невооружённым глазом.",
            "en":"🔴 *Red Giants & Stellar Evolution*\n\n• Sun → red giant in ~5B years.\n• Shell ejection → planetary nebula → white dwarf.\n• Stars >8 M☉ → supernova → neutron star or BH.\n\n💡 Betelgeuse & Antares are red supergiants visible to the naked eye.",
            "he":"🔴 *ענקים אדומים ואבולוציית כוכבים*\n\n• השמש תהיה ענק אדום בעוד ~5 מיליארד שנה.\n• פליטת מעטפת → ערפילית כוכבית → ננס לבן.\n• כוכבים >8 M☉ → סופרנובה → נייטרוני/חור שחור.",
            "ar":"🔴 *العمالقة الحمراء وتطور النجوم*\n\n• الشمس → عملاق أحمر بعد ~5 مليار سنة.\n• طرد الغلاف → سديم كوكبي → قزم أبيض.\n• نجوم >8 M☉ → مستعر أعظم → نجم نيوتروني أو ثقب أسود."}.get(lang,"")


# ── LIVE DATA HANDLERS ───────────────────────────────────────────────────────
SOLAR_WIND_URLS = [
    "https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json",
    "https://services.swpc.noaa.gov/json/solar-wind/plasma-5-minute.json",
]

async def live_solar_wind_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🔴 Solar Wind...")
    try:
        data = None
        for url in SOLAR_WIND_URLS:
            try:
                r = requests.get(url, timeout=12)
                if r.status_code == 200: data = r.json(); break
            except: continue
        if not data: raise Exception("NOAA solar wind temporarily unavailable")
        latest = data[-1] if data else {}
        speed   = latest[2] if len(latest)>2 else "?"
        density = latest[1] if len(latest)>1 else "?"
        time_str = str(latest[0])[:16].replace("T"," ") if latest else "?"
        try: spd_f = float(speed); status = "🟢 Calm" if spd_f<400 else "🟡 Moderate" if spd_f<600 else "🟠 Strong" if spd_f<800 else "🔴 STORM"
        except: status = "?"
        try: speed   = f"{float(speed):,.0f} km/s"
        except: pass
        try: density = f"{float(density):.2f} p/cm³"
        except: pass
        text = (f"🔴 *LIVE: Solar Wind*\n⏱ {time_str} UTC\n\n"
                f"{status}\n🚀 {speed}  |  🔵 {density}\n\n"
                f"Normal: 400–600 km/s. DSCOVR (L1).\n[NOAA](https://www.swpc.noaa.gov)")
        await safe_edit(q, text, reply_markup=back_kb(lang,"live_solar_wind",context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,context=context))

async def live_kp_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🔴 Kp...")
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json", timeout=12)
        r.raise_for_status()
        data    = r.json()
        current = (data[-12:] if len(data)>=12 else data)[-1] if data else {}
        kp_now  = current.get("kp_index", current.get("Kp","?"))
        time_   = current.get("time_tag","")[:16].replace("T"," ")
        try:
            kp_val = float(kp_now)
            state  = "🟢 Quiet" if kp_val<4 else "🟡 Minor" if kp_val<5 else "🟠 Moderate" if kp_val<6 else "🔴 Strong" if kp_val<8 else "🚨 G5"
            aurora = "Equatorial" if kp_val>=8 else "Mid-latitudes" if kp_val>=6 else "Scandinavia/Canada" if kp_val>=4 else "Polar regions only"
        except: state=aurora="?"
        text = (f"🔴 *LIVE: Kp-index*\n⏱ {time_} UTC\n\n"
                f"📊 Kp: *{kp_now}*  |  {state}\n🌈 Aurora: {aurora}\n\n"
                f"[NOAA](https://www.swpc.noaa.gov/products/planetary-k-index)")
        await safe_edit(q, text, reply_markup=back_kb(lang,"live_kp",context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,context=context))

async def live_flares_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🔴 Flares...")
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json", timeout=12)
        r.raise_for_status()
        xray   = r.json()
        latest = xray[-1] if xray else {}
        flux   = latest.get("flux", latest.get("current_int_xrsum","?"))
        time_  = latest.get("time_tag","")[:16].replace("T"," ")
        try:
            fv   = float(flux)
            cls_ = "🔴 X" if fv>=1e-4 else "🟠 M" if fv>=1e-5 else "🟡 C" if fv>=1e-6 else "🟢 B" if fv>=1e-7 else "⚪ A"
            fs   = f"{fv:.2e} W/m²"
        except: cls_="?"; fs=str(flux)
        text = (f"🔴 *LIVE: Solar X-rays (GOES)*\n⏱ {time_} UTC\n\n"
                f"⚡ *{cls_}* — `{fs}`\n\nA/B 🟢  C 🟡  M 🟠  X 🔴\n"
                f"[GOES](https://www.swpc.noaa.gov/products/goes-x-ray-flux)")
        await safe_edit(q, text, reply_markup=back_kb(lang,"live_flares",context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,context=context))

async def live_iss_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🔴 ISS...")
    try:
        pos  = requests.get("http://api.open-notify.org/iss-now.json", timeout=10).json()
        lat  = float(pos["iss_position"]["latitude"])
        lon  = float(pos["iss_position"]["longitude"])
        ts   = datetime.utcfromtimestamp(pos["timestamp"]).strftime("%H:%M:%S UTC")
        try:
            crew_r  = requests.get("http://api.open-notify.org/astros.json", timeout=8)
            people  = crew_r.json().get("people",[]) if crew_r.ok else []
            iss_c   = [p["name"] for p in people if p.get("craft")=="ISS"]
        except: iss_c=[]
        text = (f"🔴 *LIVE: ISS*\n⏱ {ts}\n\n"
                f"🌍 `{lat:+.4f}°` | 🌏 `{lon:+.4f}°`\n⚡ ~27,576 km/h  |  ~408 km\n"
                f"👨‍🚀 {', '.join(iss_c) or tx(lang,'iss_no_crew')}\n\n"
                f"[{tx(lang,'iss_map')}](https://www.google.com/maps?q={lat},{lon})  "
                f"[n2yo](https://www.n2yo.com/satellite/?s=25544)")
        await safe_edit(q, text, reply_markup=back_kb(lang,"live_iss",context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,context=context))

async def live_radiation_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🔴 Radiation...")
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/goes/primary/integral-protons-6-hour.json", timeout=12)
        r.raise_for_status()
        protons = r.json()
        latest  = protons[-1] if protons else {}
        flux_p  = latest.get("flux","?")
        time_p  = latest.get("time_tag","")[:16].replace("T"," ")
        try:
            fp = float(flux_p)
            rl = "🚨 S5" if fp>=1e4 else "🔴 S4" if fp>=1e3 else "🟠 S3" if fp>=1e2 else "🟡 S2" if fp>=10 else "🟢 S1" if fp>=1 else "⚪ Background"
            fs = f"{fp:.2e} p/(cm²·s·sr)"
        except: rl="?"; fs=str(flux_p)
        text = (f"🔴 *LIVE: Radiation*\n⏱ {time_p} UTC\n\n"
                f"☢️ Protons >10 MeV: `{fs}`\n🌡 *{rl}*\n\n"
                f"ISS: ~80 µSv/day. NASA limit: 600 mSv/career.\n"
                f"[NOAA](https://www.swpc.noaa.gov/products/goes-proton-flux)")
        await safe_edit(q, text, reply_markup=back_kb(lang,"live_radiation",context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,context=context))

async def live_aurora_forecast_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🔴 Aurora...")
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json", timeout=12)
        r.raise_for_status()
        data    = r.json()
        current = data[-1] if data else {}
        kp      = current.get("kp_index", current.get("Kp","?"))
        time_   = current.get("time_tag","")[:16].replace("T"," ")
        try:
            kp_val   = float(kp)
            forecast = ("🌈 Possible at mid-latitudes (Moscow, Kyiv)" if kp_val>=7 else
                        "🌈 Good chances in Scandinavia, Canada, Alaska" if kp_val>=5 else
                        "🌈 Visible near polar circle" if kp_val>=4 else "🌈 Mainly at poles")
        except: forecast="?"
        text = (f"🔴 *Aurora Forecast*\n⏱ {time_} UTC\n\nKp now: *{kp}*\n{forecast}\n\nData: NOAA")
        await safe_edit(q, text, reply_markup=back_kb(lang,"live_aurora_forecast",context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,context=context))

async def live_geomagnetic_alert_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🔴 Geomagnetic...")
    try:
        end   = date.today().isoformat()
        start = (date.today()-timedelta(days=2)).isoformat()
        storms = nasa("/DONKI/GST",{"startDate":start,"endDate":end}) or []
        text  = f"🔴 *Geomagnetic Storms (2d)*\n\nEvents: *{len(storms)}*\n\n"
        for s in (storms[-5:] if storms else []):
            t      = (s.get("startTime") or "?")[:16].replace("T"," ")
            kp_idx = s.get("allKpIndex",[{}])
            kp_val = kp_idx[-1].get("kpIndex","?") if kp_idx else "?"
            text  += f"• {t} UTC  Kp *{kp_val}*\n"
        if not storms:
            text += tx(lang,"live_nodata")
        text += "\n[NOAA](https://www.swpc.noaa.gov)"
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang,"live_geomagnetic_alert",context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,context=context))

async def live_sunspot_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🔴 Sunspots...")
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json", timeout=12)
        r.raise_for_status()
        data   = r.json()
        latest = data[-1] if data else {}
        ssn    = latest.get("smoothed_ssn", latest.get("ssn","?"))
        text = (f"🔴 *Sunspots (Cycle 25)*\n\n"
                f"Wolf number (smoothed): *{ssn}*\n\n"
                f"Cycle 25 is near maximum — more spots & flares. Peak ~2025.")
        await safe_edit(q, text, reply_markup=back_kb(lang,"live_sunspot",context))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang,context=context))

async def live_epic_latest_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🔴 EPIC...")
    try:
        data = nasa("/EPIC/api/natural")
        if not data:
            await safe_edit(q, tx(lang,"no_img"), reply_markup=back_kb(lang,"live_epic_latest",context)); return
        item = data[0]
        date_str = item.get("date","")[:10].replace("-","/")
        img  = item.get("image","")
        url  = f"https://epic.gsfc.nasa.gov/archive/natural/{date_str}/png/{img}.png"
        caption = f"🌍 *EPIC — Earth Real Time*\n📅 {date_str}\n\nDSCOVR (L1)."
        await del_msg(q)
        try:
            await context.bot.send_photo(chat_id=q.message.chat_id, photo=url,
                caption=caption, parse_mode="Markdown",
                reply_markup=back_kb(lang,"live_epic_latest",context))
        except:
            await context.bot.send_message(chat_id=q.message.chat_id,
                text=caption+f"\n\n[Open]({url})",
                reply_markup=back_kb(lang,"live_epic_latest",context))
    except Exception as e:
        logger.error(f"Live EPIC: {e}")
        await safe_edit(q, tx(lang,"no_img"), reply_markup=back_kb(lang,"live_epic_latest",context))

async def live_satellite_count_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, "🔴 Counting...")
    try:
        sl     = get_json("https://api.spacexdata.com/v4/starlink", timeout=10)
        total  = len(sl)
        active = sum(1 for s in sl if isinstance(s,dict) and not (s.get("spaceTrack") or {}).get("DECAY_DATE"))
    except: total=active="?"
    text = (f"🔴 *Satellites (SpaceX Starlink)*\n\n"
            f"Total: *{total}*  |  Active: *{active}*\n\n"
            f"Global: ~9,000+ in orbit, ~7,500+ active, ~27,000 debris.")
    await safe_edit(q, text, reply_markup=back_kb(lang,"live_satellite_count",context))


# ── ROUTER ───────────────────────────────────────────────────────────────────
async def back_handler(update, context):
    q = update.callback_query; await safe_answer(q)
    lang = get_lang(context)
    await safe_edit(q, tx(lang,"main_menu"), reply_markup=main_menu_kb(lang))

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    cb  = q.data
    lang = get_lang(context)

    # Language selection
    if cb == "choose_lang":
        await choose_lang_handler(update, context); return
    if cb.startswith("setlang_"):
        await setlang_handler(update, context); return

    # Category menus
    cat_map = {
        "cat_photo":    (cat_photo_kb,    "title_photo"),
        "cat_solarsys": (cat_solarsys_kb, "title_solarsys"),
        "cat_deepspace":(cat_deepspace_kb,"title_deepspace"),
        "cat_earth":    (cat_earth_kb,    "title_earth"),
        "cat_science":  (cat_science_kb,  "title_science"),
        "cat_live":     (cat_live_kb,     "title_live"),
    }
    if cb in cat_map:
        kb_fn, title_key = cat_map[cb]
        await safe_answer(q)
        context.user_data["last_category"] = cb
        await safe_edit(q, tx(lang, title_key) + tx(lang, "choose_sec"), reply_markup=kb_fn(lang))
        return

    if cb == "noop":
        await safe_answer(q); return
    if cb == "back":
        await back_handler(update, context); return

    # Image routes (queries → NASA image library)
    IMG = {
        "epic":       EARTH_Q,
        "gallery":    GALLERY_Q,
        "earth_night":["earth at night city lights nasa","night lights satellite","earth lights from space"],
        "eclipse":    ["solar eclipse nasa","lunar eclipse nasa","total eclipse satellite"],
        "jwst_gallery":["James Webb telescope","JWST deep field","Webb nebula","JWST galaxy"],
        "moon_gallery":["moon surface nasa","lunar crater","moon high resolution","apollo moon"],
        "blue_marble":["blue marble earth nasa","earth blue marble","whole earth nasa"],
        "ceres":      ["Ceres dwarf planet","Ceres Dawn nasa","Ceres bright spots"],
        "pluto_close":["Pluto New Horizons","Pluto heart Tombaugh","Pluto nasa"],
        "nebulae":    ["nebula hubble","eagle nebula","orion nebula","horsehead nebula"],
        "deepspace":  ["hubble deep field galaxy","andromeda galaxy","spiral galaxy nasa","james webb deep field"],
        "sun":        ["solar flare nasa SDO","sun corona nasa","sunspot solar dynamics"],
        "aurora":     ["aurora borealis from space ISS","northern lights nasa","aurora ISS astronaut photo"],
        "blackholes": ["black hole accretion disk nasa","quasar jet nasa hubble"],
        "supernovae": ["supernova remnant hubble","crab nebula supernova","SN 1987A hubble"],
        "clusters":   ["star cluster hubble nasa","globular cluster M13","pleiades star cluster"],
        "comets":     ["comet nasa hubble","comet NEOWISE","comet 67P rosetta"],
        "history":    ["apollo moon landing nasa","space shuttle launch","hubble telescope launch"],
        "giants":     ["jupiter great red spot nasa","saturn rings cassini","uranus voyager nasa"],
        "moons":      ["europa moon jupiter nasa","titan saturn cassini","enceladus geysers nasa"],
        "missions":   ["voyager spacecraft nasa","cassini saturn mission","perseverance rover mars"],
        "nearstars":  ["alpha centauri star","red dwarf star nasa","sirius star nasa hubble"],
        "pulsars":    ["pulsar neutron star nasa","crab pulsar nebula","magnetar nasa"],
        "milkyway":   ["milky way galaxy nasa","milky way center hubble","galactic center nasa"],
        "magnetosphere":["earth magnetosphere nasa","aurora magnetic field nasa","Van Allen belts nasa"],
        "dwarfplanets":["pluto new horizons nasa","ceres dawn nasa","dwarf planet nasa"],
        "climate":    ["arctic ice melt nasa satellite","sea level rise satellite","glacier melt nasa"],
        "quasars":    ["quasar nasa hubble","quasar jet","active galaxy nucleus"],
        "cmb":        ["cosmic microwave background","CMB Planck","relic radiation nasa"],
        "galaxy_collision":["galaxy collision hubble","antennae galaxies","merging galaxies nasa"],
        "star_formation":["star formation nebula","stellar nursery nasa","pillars of creation"],
        "cosmic_web": ["cosmic web filament","large scale structure universe"],
        "wildfires":  ["wildfire satellite nasa","forest fire from space","burn scar nasa"],
        "ice_sheets": ["ice sheet antarctica nasa","glacier melt satellite","arctic sea ice nasa"],
        "deforestation":["deforestation amazon satellite","forest loss nasa"],
        "night_lights":["earth at night city lights nasa","night lights world"],
        "ocean_temp": ["sea surface temperature nasa","SST nasa","ocean temperature satellite"],
        "volcanoes":  ["volcano eruption from space","volcanic eruption satellite","etna volcano satellite"],
        "hurricanes": ["hurricane from space satellite","tropical storm ISS","hurricane eye NASA"],
        "spacewalks": ["spacewalk EVA astronaut","spacewalk ISS nasa","extravehicular activity nasa"],
        "lunar_missions":["apollo moon mission","lunar landing nasa","artemis moon","lunar rover nasa"],
        "moon_landing_sites":["apollo landing site moon","tranquility base","moon landing site LRO"],
        "rocket_engines":["rocket engine nasa","RS-25 engine","spacex raptor engine"],
        "tornadoes":  ["tornado from space satellite","supercell tornado satellite"],
        "space_food": ["space food astronaut nasa","ISS food nasa","astronaut eating space"],
        "mars_rovers":None,  # handled separately
    }

    # Static text routes
    STATIC = {
        "kuiper_belt": kuiper_text, "planet_alignment": alignment_text,
        "solar_eclipse": solar_ecl_text, "orbital_scale": scale_text,
        "darkmatter": darkmatter_text, "seti": seti_text,
        "gravwaves": gravwaves_text, "future": future_text,
        "radioastro": radioastro_text, "grb": grb_text,
        "dark_energy": dark_energy_text, "ozone": ozone_text,
        "ocean_currents": ocean_cur_text, "space_stations": sp_stations_text,
        "women_in_space": women_text, "mars_colonization": mars_col_text,
        "space_medicine": sp_med_text, "astronaut_training": training_text,
        "debris": debris_text, "space_records": records_text,
        "red_giants": red_giants_text,
    }

    # Handler dispatch
    direct = {
        "apod": apod_handler, "apod_random": apod_random_handler,
        "mars": mars_handler, "mars_rovers": mars_rovers_handler,
        "asteroids": asteroids_handler, "iss": iss_handler,
        "exoplanets": exoplanets_handler, "spaceweather": spaceweather_handler,
        "launches": launches_handler, "spacefact": spacefact_handler,
        "channels": channels_handler, "planets": planets_handler,
        "moon": moon_handler, "satellites": satellites_handler,
        "meteors": meteors_handler, "telescopes": telescopes_handler,
        "live_solar_wipip install flask python-telegram-bot requestsnd": live_solar_wind_handler, "live_kp": live_kp_handler,
        "live_flares": live_flares_handler, "live_iss": live_iss_handler,
        "live_radiation": live_radiation_handler,
        "live_aurora_forecast": live_aurora_forecast_handler,
        "live_geomagnetic_alert": live_geomagnetic_alert_handler,
        "live_sunspot": live_sunspot_handler,
        "live_epic_latest": live_epic_latest_handler,
        "live_satellite_count": live_satellite_count_handler,
    }

    if cb in direct:
        await direct[cb](update, context)
    elif cb in STATIC:
        text_fn = STATIC[cb]
        await safe_answer(q)
        text = text_fn(lang)
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang, cb, context))
    elif cb in IMG and IMG[cb] is not None:
        await safe_answer(q)
        await safe_edit(q, "⏳...")
        await send_nasa_image(q, context, IMG[cb], cb)
    else:
        await safe_answer(q)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await update.message.reply_text(tx(lang,"unknown"), reply_markup=main_menu_kb(lang))

# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    keep_alive()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu",  menu_cmd))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.ALL, unknown))
    logger.info("🚀 NASA Bot started! Polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
