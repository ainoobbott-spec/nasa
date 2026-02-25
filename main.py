"""
NASA Space Bot — Webhook mode for Render.com
"""

# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: IMPORTS & ENVIRONMENT CONFIG                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
import os, logging, random, re, requests, asyncio, threading, json
import xml.etree.ElementTree as ET
from html import unescape
from flask import Flask, request
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                           ContextTypes, MessageHandler, filters, ConversationHandler)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
NASA_API_KEY   = os.environ.get("NASA_API_KEY", "UXsg0T63ukdHkImo2VAejU46MHdnZdGgtgrlcQmE")
WEBHOOK_URL    = os.environ.get("WEBHOOK_URL", "").rstrip("/")
NASA_BASE      = "https://api.nasa.gov"
PORT           = int(os.environ.get("PORT", 10000))
# ── End: IMPORTS & ENVIRONMENT CONFIG ─────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: CONVERSATION HANDLER STATES                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
# MUST be defined before handlers
PLANET_DATE, PLANET_WEIGHT, PLANET_CHOICE = range(3)
HOROSCOPE_BDAY = 10
CAPSULE_MSG    = 20
# ── End: CONVERSATION HANDLER STATES ──────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: LOGGING & FLASK INIT                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)
tg_app    = None
bot_loop  = None
# ── End: LOGGING & FLASK INIT ─────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: FILE STORAGE HELPERS (subscribers.json, capsules.json)                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
SUBSCRIBERS_FILE = "subscribers.json"
CAPSULES_FILE    = "capsules.json"

def load_subscribers():
    try:
        with open(SUBSCRIBERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_subscribers(data):
    try:
        with open(SUBSCRIBERS_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"save_subscribers: {e}")

def load_capsules():
    try:
        with open(CAPSULES_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_capsules(data):
    try:
        with open(CAPSULES_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"save_capsules: {e}")
# ── End: FILE STORAGE HELPERS ─────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: CHANNEL TEXTS (multilingual)                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
CHANNELS_TEXT = {
    "ru": ("📢 *Наши каналы*\n\n"
           "📡 [Канал NASA Space Bot](https://t.me/cosmic41)\n"
           "💬 [Группа — общение и вопросы](https://t.me/cosmic40)\n\n"
           "🚀 Подписывайтесь, чтобы не пропустить запуски, фото и новости!"),
    "en": ("📢 *Our Channels*\n\n"
           "📡 [NASA Space Bot Channel](https://t.me/cosmic41)\n"
           "💬 [Community Group](https://t.me/cosmic40)\n\n"
           "🚀 Subscribe for launches, photos and space news!"),
    "he": ("📢 *הערוצים שלנו*\n\n"
           "📡 [ערוץ NASA Space Bot](https://t.me/cosmic41)\n"
           "💬 [קבוצת קהילה](https://t.me/cosmic40)\n\n"
           "🚀 הצטרפו לעדכונים על שיגורים, תמונות וחדשות!"),
    "ar": ("📢 *قنواتنا*\n\n"
           "📡 [قناة NASA Space Bot](https://t.me/cosmic41)\n"
           "💬 [مجموعة المجتمع](https://t.me/cosmic40)\n\n"
           "🚀 اشترك لمتابعة الإطلاقات والصور وأخبار الفضاء!"),
}
# ── End: CHANNEL TEXTS ────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: NEWS SOURCES CONFIG                                                    ║
# FIX: Updated NASA URL (old /rss/dyn/ endpoint is dead)                       ║
# FIX: Added url_fallback for NASA and Planetary Society                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
NEWS_SOURCES = {
    "news_nasa": {
        # FIX: old URL https://www.nasa.gov/rss/dyn/breaking_news.rss is DEAD
        "url": "https://www.nasa.gov/news-release/feed/",
        "url_fallback": "https://blogs.nasa.gov/feed/",
        "name": "NASA",
        "emoji": "🚀",
        "fallback_img": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/NASA_logo.svg/800px-NASA_logo.svg.png",
    },
    "news_sfn": {
        "url": "https://spaceflightnow.com/feed/",
        "name": "SpaceflightNow",
        "emoji": "🛸",
        "fallback_img": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0193.jpg",
    },
    "news_spacenews": {
        "url": "https://spacenews.com/feed/",
        "name": "SpaceNews",
        "emoji": "📡",
        "fallback_img": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0171.jpg",
    },
    "news_spacedotcom": {
        "url": "https://www.space.com/feeds/all",
        "name": "Space.com",
        "emoji": "🌌",
        "fallback_img": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_HMIB.jpg",
    },
    "news_planetary": {
        # FIX: Planetary Society uses Atom format — handled by _parse_atom()
        "url": "https://www.planetary.org/articles.rss",
        "url_fallback": "https://www.planetary.org/feed",
        "name": "Planetary Society",
        "emoji": "🪐",
        "fallback_img": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0304.jpg",
    },
}
# ── End: NEWS SOURCES CONFIG ──────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: RSS / ATOM PARSING HELPERS                                             ║
# FIX: Added Atom format support (_parse_atom) — Planetary Society uses Atom   ║
# FIX: Extracted _parse_rss_items for cleaner code                             ║
# FIX: Improved link extraction (handles attribute href for Atom)               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def _rss_text(el):
    """Strip HTML tags and entities from RSS text element."""
    if el is None: return ""
    txt = el.text or ""
    txt = re.sub(r'<[^>]+>', ' ', txt)
    txt = unescape(txt).strip()
    return re.sub(r'\s+', ' ', txt)

def _rss_image(item_el, ns):
    """Extract image URL from an RSS <item> or Atom <entry> element."""
    # 1. media:content
    for tag in ["media:content",
                "{http://search.yahoo.com/mrss/}content",
                "{http://video.search.yahoo.com/mrss/}content"]:
        mc = item_el.find(tag)
        if mc is not None:
            url = mc.get("url", "")
            if url and url.startswith("http"): return url
    # 2. media:thumbnail
    for tag in ["media:thumbnail", "{http://search.yahoo.com/mrss/}thumbnail"]:
        mt = item_el.find(tag)
        if mt is not None:
            url = mt.get("url", "")
            if url and url.startswith("http"): return url
    # 3. enclosure
    enc = item_el.find("enclosure")
    if enc is not None:
        url = enc.get("url", "")
        if url and url.startswith("http") and any(
                ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            return url
    # 4. img tag inside description/content
    for tag in ["description", "content:encoded",
                "{http://purl.org/rss/1.0/modules/content/}encoded",
                "{http://www.w3.org/2005/Atom}content", "content", "summary"]:
        desc_el = item_el.find(tag)
        if desc_el is not None and desc_el.text:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc_el.text)
            if m:
                url = m.group(1)
                if url.startswith("http"): return url
    return ""

def _parse_rss_items(items, src, max_items):
    """Parse standard RSS 2.0 <item> elements."""
    articles = []
    for item in items[:max_items]:
        title = _rss_text(item.find("title")) or "No title"
        # Link: text node in RSS, attribute in some hybrid feeds
        link_el = item.find("link")
        if link_el is not None:
            link = (link_el.text or "").strip() or link_el.get("href", "")
        else:
            link = ""
        desc = (
            _rss_text(item.find("description")) or
            _rss_text(item.find("{http://purl.org/rss/1.0/modules/content/}encoded")) or ""
        )
        desc  = desc[:600]
        pub   = _rss_text(item.find("pubDate")) or _rss_text(item.find("published")) or ""
        pub   = pub[:30]
        guid  = _rss_text(item.find("guid")) or link or title
        img   = _rss_image(item, {})
        articles.append({
            "title": title, "link": link, "desc": desc,
            "pub": pub, "img": img, "guid": guid,
            "source": src["name"], "emoji": src["emoji"],
            "fallback_img": src["fallback_img"],
        })
    return articles

def _parse_atom(root, src, max_items):
    """
    Parse Atom 1.0 feed format.
    FIX: Planetary Society and some NASA feeds use Atom, not RSS.
    Atom uses <entry> (not <item>), <link href="..."> attribute, <summary>/<content>.
    """
    ATOM_NS = "http://www.w3.org/2005/Atom"

    def _find(el, tag):
        """Try namespaced then bare tag."""
        return el.find(f"{{{ATOM_NS}}}{tag}") or el.find(tag)

    def _findall(el, tag):
        result = el.findall(f"{{{ATOM_NS}}}{tag}")
        return result if result else el.findall(tag)

    entries  = _findall(root, "entry")
    articles = []
    for entry in entries[:max_items]:
        # Title
        title_el = _find(entry, "title")
        title    = unescape((title_el.text or "No title").strip()) if title_el is not None else "No title"

        # Link — Atom uses <link rel="alternate" href="...">
        link = ""
        for link_el in (_findall(entry, "link")):
            rel  = link_el.get("rel", "alternate")
            href = link_el.get("href", "")
            if href.startswith("http"):
                if rel == "alternate":
                    link = href; break
                elif not link:
                    link = href

        # Description: summary or content
        desc = ""
        for tag in ("summary", "content"):
            el = _find(entry, tag)
            if el is not None and el.text:
                desc = re.sub(r'<[^>]+>', ' ', el.text)
                desc = unescape(desc).strip()[:600]
                break

        # Published / updated
        pub = ""
        for tag in ("published", "updated"):
            el = _find(entry, tag)
            if el is not None and el.text:
                pub = el.text.strip()[:30]; break

        # GUID / id
        id_el = _find(entry, "id")
        guid  = (id_el.text or link or title) if id_el is not None else (link or title)

        img = _rss_image(entry, {})

        articles.append({
            "title": title, "link": link, "desc": desc,
            "pub": pub, "img": img, "guid": guid,
            "source": src["name"], "emoji": src["emoji"],
            "fallback_img": src["fallback_img"],
        })
    return articles


def fetch_rss(source_key: str, max_items: int = 30) -> list:
    """
    Fetch and parse RSS or Atom feed.
    FIX: Now handles both RSS 2.0 and Atom 1.0 formats.
    FIX: Tries url_fallback if primary URL fails.
    FIX: Better headers to avoid 403 blocks.
    Returns list of article dicts or [] on failure.
    """
    src = NEWS_SOURCES.get(source_key)
    if not src: return []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36 NASASpaceBot/2.0"
        ),
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }

    urls_to_try = [src["url"]]
    if src.get("url_fallback"):
        urls_to_try.append(src["url_fallback"])

    for url in urls_to_try:
        try:
            r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            r.raise_for_status()

            root = ET.fromstring(r.content)
            tag  = root.tag.lower()

            # Detect Atom: root tag is <feed> or contains "atom" namespace
            is_atom = (
                tag == "feed"
                or tag.endswith("}feed")
                or "atom" in tag
                or "{http://www.w3.org/2005/Atom}" in root.tag
            )

            if is_atom:
                articles = _parse_atom(root, src, max_items)
            else:
                channel  = root.find("channel") or root
                items    = channel.findall("item")
                articles = _parse_rss_items(items, src, max_items)

            if articles:
                logger.info(f"fetch_rss {source_key}: got {len(articles)} articles from {url}")
                return articles
            else:
                logger.warning(f"fetch_rss {source_key}: parsed 0 articles from {url}")

        except ET.ParseError as e:
            logger.error(f"fetch_rss {source_key} XML parse error at {url}: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"fetch_rss {source_key} request error at {url}: {e}")
        except Exception as e:
            logger.error(f"fetch_rss {source_key} unknown error at {url}: {e}")

    return []
# ── End: RSS / ATOM PARSING HELPERS ───────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: RSS CACHE (10-minute TTL)                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
_rss_cache: dict = {}
RSS_TTL = 600

def rss_cache_get(key):
    if key in _rss_cache:
        ts, data = _rss_cache[key]
        if (datetime.utcnow().timestamp() - ts) < RSS_TTL:
            return data
    return None

def rss_cache_set(key, data):
    _rss_cache[key] = (datetime.utcnow().timestamp(), data)
# ── End: RSS CACHE ────────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: TRANSLATIONS (T dictionary — ru/en/he/ar)                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
T = {
"ru": {
    "choose_lang":"🌍 *Выберите язык / Choose language / בחרו שפה / اختر اللغة*",
    "lang_set":"🇷🇺 Язык: *Русский*",
    "start_msg":"🚀 *NASA Space Bot* — твой проводник во Вселенную, {name}!\n\n*6 категорий, 50+ разделов* 👇\n\n📡 [Канал](https://t.me/cosmic41) | 💬 [Группа](https://t.me/cosmic40)",
    "main_menu":"🌠 *Главное меню:*", "choose_sec":"\n\nВыбери раздел 👇",
    "cat_photo":"📸 ФОТО И ГАЛЕРЕЯ", "cat_solarsys":"🪐 СОЛНЕЧНАЯ СИСТЕМА",
    "cat_deepspace":"🌌 ГЛУБОКИЙ КОСМОС", "cat_earth":"🌍 ЗЕМЛЯ И АТМОСФЕРА",
    "cat_science":"🔬 НАУКА И ИСТОРИЯ", "cat_live":"🔴 LIVE — РЕАЛЬНОЕ ВРЕМЯ",
    "cat_interact_btn":"🎮 ИНТЕРАКТИВ",
    "cat_news":"📰 НОВОСТИ КОСМОСА",
    "title_news":"📰 *Новости космоса*",
    "btn_news_nasa":"🚀 NASA News",
    "btn_news_sfn":"🛸 SpaceflightNow",
    "btn_news_spacenews":"📡 SpaceNews",
    "btn_news_spacedotcom":"🌌 Space.com",
    "btn_news_planetary":"🪐 Planetary Society",
    "btn_news_next":"➡️ Следующая",
    "btn_news_source":"🔗 Источник",
    "news_loading":"📰 Загружаю новости...",
    "news_empty":"📭 Новостей не найдено",
    "news_counter":"Новость {idx}/{total}",
    "btn_spacefact":"⭐ Факт о космосе", "btn_channels":"📢 Наши каналы", "btn_lang":"🌍 Язык",
    "back_menu":"◀️ Главное меню", "back_cat":"◀️ Назад",
    "btn_refresh":"🔄 Обновить", "btn_more_rnd":"🎲 Ещё", "btn_another":"🔄 Ещё снимок", "btn_other_rv":"🔄 Другой",
    "title_photo":"📸 *Фото и галерея*", "title_solarsys":"🪐 *Солнечная система*",
    "title_deepspace":"🌌 *Глубокий космос*", "title_earth":"🌍 *Земля и атмосфера*",
    "title_science":"🔬 *Наука и история*", "title_live":"🔴 *LIVE*",
    "title_interact":"🎮 *Интерактив*",
    "err":"❌ Ошибка", "no_data":"📭 Нет данных", "no_img":"📭 Снимки недоступны",
    "unknown":"🤔 Используй /start", "hazard_yes":"🔴 ОПАСЕН", "hazard_no":"🟢 Безопасен",
    "iss_map":"🗺 Карта", "iss_no_crew":"Нет данных", "live_nodata":"Нет данных.",
    "moon_phases":["Новолуние","Растущий серп","Первая четверть","Растущая Луна","Полнолуние","Убывающая Луна","Последняя четверть","Убывающий серп"],
    "btn_planet_calc":"🪐 Калькулятор планет",
    "btn_horoscope":"🔮 Космогороскоп",
    "btn_space_name":"👨‍🚀 Космическое имя",
    "btn_quiz":"🧠 Космовикторина",
    "btn_poll":"📊 Опрос дня",
    "btn_capsule":"⏳ Капсула времени",
    "btn_lunar_cal":"📅 Лунный календарь",
    "btn_mars_live":"🤖 Марсоход Live",
    "btn_notifications":"🔔 Уведомления",
    "btn_nasa_tv":"📺 NASA TV",
    "planet_calc_ask_date":"📅 Введите дату рождения в формате *ДД.ММ.ГГГГ*\nПример: 15.04.1990",
    "planet_calc_ask_weight":"⚖️ Введите ваш вес в *кг*\nПример: 70",
    "planet_calc_error_date":"❌ Неверный формат даты. Попробуй: *15.04.1990*",
    "planet_calc_error_weight":"❌ Неверный вес. Введи число от 1 до 500 кг",
    "horoscope_ask":"♈ Введи дату рождения (день и месяц)\nПример: *15.04*",
    "horoscope_error":"❌ Неверный формат. Попробуй: *15.04*",
    "quiz_start":"🧠 *Космовикторина*\n\n10 вопросов о космосе.\nГотов проверить знания?",
    "quiz_btn_start":"🚀 Начать!",
    "quiz_next":"➡️ Следующий",
    "quiz_finish":"🏁 Результат",
    "quiz_correct":"Правильно! ✅",
    "quiz_wrong":"Неверно ❌. Правильный ответ:",
    "quiz_result":"🏆 *Результат: {score}/10*\n\n{grade}",
    "capsule_ask":"⏳ *Капсула времени*\n\nНапиши послание себе в будущем (до 2000 символов).\nОно придёт тебе ровно через год! ✨",
    "capsule_saved":"✅ *Капсула сохранена!*\n\n📅 Откроется: *{date}*\n\n🚀 Через год я напомню тебе об этом послании!",
    "capsule_cancel":"❌ Отменено",
    "name_gen_title":"👨‍🚀 *Твоё космическое имя*\n\n",
    "notif_title":"🔔 *Управление уведомлениями*\n\nВыбери, о чём хочешь получать оповещения:",
    "notif_subscribed":"✅ Подписка активирована",
    "notif_unsubscribed":"🔕 Подписка отключена",
    "notif_sub_ast":"☄️ Опасные астероиды",
    "notif_sub_meteor":"🌠 Метеорные потоки",
    "notif_sub_sw":"🌞 Космическая погода (Kp≥5)",
    "notif_sub_lunar":"🌕 Фазы Луны",
    "notif_sub_news":"📰 Новости NASA",
    "mars_rover_title":"🤖 *Марсоходы — статус*\n\n",
    "lunar_cal_title":"📅 *Лунный календарь*\n\n",
    "nasa_tv_title":"📺 *NASA TV*\n\n🔴 [Прямой эфир](https://www.nasa.gov/nasatv)\n\nСмотри запуски, МКС и пресс-конференции в прямом эфире!",
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
},
"en": {
    "choose_lang":"🌍 *Choose language / Выберите язык / בחרו שפה / اختر اللغة*",
    "lang_set":"🇬🇧 Language: *English*",
    "start_msg":"🚀 *NASA Space Bot* — your guide to the Universe, {name}!\n\n*6 categories, 50+ sections* 👇\n\n📡 [Channel](https://t.me/cosmic41) | 💬 [Group](https://t.me/cosmic40)",
    "main_menu":"🌠 *Main Menu:*", "choose_sec":"\n\nChoose section 👇",
    "cat_photo":"📸 PHOTO & GALLERY", "cat_solarsys":"🪐 SOLAR SYSTEM",
    "cat_deepspace":"🌌 DEEP SPACE", "cat_earth":"🌍 EARTH & ATMOSPHERE",
    "cat_science":"🔬 SCIENCE & HISTORY", "cat_live":"🔴 LIVE — REAL TIME",
    "cat_interact_btn":"🎮 INTERACTIVE",
    "cat_news":"📰 SPACE NEWS",
    "title_news":"📰 *Space News*",
    "btn_news_nasa":"🚀 NASA News",
    "btn_news_sfn":"🛸 SpaceflightNow",
    "btn_news_spacenews":"📡 SpaceNews",
    "btn_news_spacedotcom":"🌌 Space.com",
    "btn_news_planetary":"🪐 Planetary Society",
    "btn_news_next":"➡️ Next",
    "btn_news_source":"🔗 Source",
    "news_loading":"📰 Loading news...",
    "news_empty":"📭 No articles found",
    "news_counter":"Article {idx}/{total}",
    "btn_spacefact":"⭐ Space Fact", "btn_channels":"📢 Our Channels", "btn_lang":"🌍 Language",
    "back_menu":"◀️ Main Menu", "back_cat":"◀️ Back",
    "btn_refresh":"🔄 Refresh", "btn_more_rnd":"🎲 More", "btn_another":"🔄 Another", "btn_other_rv":"🔄 Other Rover",
    "title_photo":"📸 *Photo & Gallery*", "title_solarsys":"🪐 *Solar System*",
    "title_deepspace":"🌌 *Deep Space*", "title_earth":"🌍 *Earth & Atmosphere*",
    "title_science":"🔬 *Science & History*", "title_live":"🔴 *LIVE*",
    "title_interact":"🎮 *Interactive*",
    "err":"❌ Error", "no_data":"📭 No data", "no_img":"📭 Images unavailable",
    "unknown":"🤔 Use /start", "hazard_yes":"🔴 HAZARDOUS", "hazard_no":"🟢 Safe",
    "iss_map":"🗺 Map", "iss_no_crew":"No data", "live_nodata":"No data.",
    "moon_phases":["New Moon","Waxing Crescent","First Quarter","Waxing Gibbous","Full Moon","Waning Gibbous","Last Quarter","Waning Crescent"],
    "btn_planet_calc":"🪐 Planet Calculator",
    "btn_horoscope":"🔮 Space Horoscope",
    "btn_space_name":"👨‍🚀 Space Name",
    "btn_quiz":"🧠 Space Quiz",
    "btn_poll":"📊 Daily Poll",
    "btn_capsule":"⏳ Time Capsule",
    "btn_lunar_cal":"📅 Lunar Calendar",
    "btn_mars_live":"🤖 Rover Live",
    "btn_notifications":"🔔 Notifications",
    "btn_nasa_tv":"📺 NASA TV",
    "planet_calc_ask_date":"📅 Enter your birth date in format *DD.MM.YYYY*\nExample: 15.04.1990",
    "planet_calc_ask_weight":"⚖️ Enter your weight in *kg*\nExample: 70",
    "planet_calc_error_date":"❌ Wrong date format. Try: *15.04.1990*",
    "planet_calc_error_weight":"❌ Wrong weight. Enter a number from 1 to 500 kg",
    "horoscope_ask":"♈ Enter your birth date (day and month)\nExample: *15.04*",
    "horoscope_error":"❌ Wrong format. Try: *15.04*",
    "quiz_start":"🧠 *Space Quiz*\n\n10 questions about space.\nReady to test your knowledge?",
    "quiz_btn_start":"🚀 Start!",
    "quiz_next":"➡️ Next",
    "quiz_finish":"🏁 Results",
    "quiz_correct":"Correct! ✅",
    "quiz_wrong":"Wrong ❌. Correct answer:",
    "quiz_result":"🏆 *Score: {score}/10*\n\n{grade}",
    "capsule_ask":"⏳ *Time Capsule*\n\nWrite a message to your future self (up to 2000 chars).\nIt will be delivered in exactly one year! ✨",
    "capsule_saved":"✅ *Capsule saved!*\n\n📅 Opens: *{date}*\n\n🚀 I'll remind you in a year!",
    "capsule_cancel":"❌ Cancelled",
    "name_gen_title":"👨‍🚀 *Your Space Name*\n\n",
    "notif_title":"🔔 *Notification Settings*\n\nChoose what you want to be notified about:",
    "notif_subscribed":"✅ Subscribed",
    "notif_unsubscribed":"🔕 Unsubscribed",
    "notif_sub_ast":"☄️ Hazardous Asteroids",
    "notif_sub_meteor":"🌠 Meteor Showers",
    "notif_sub_sw":"🌞 Space Weather (Kp≥5)",
    "notif_sub_lunar":"🌕 Moon Phases",
    "notif_sub_news":"📰 NASA News",
    "mars_rover_title":"🤖 *Mars Rovers — Status*\n\n",
    "lunar_cal_title":"📅 *Lunar Calendar*\n\n",
    "nasa_tv_title":"📺 *NASA TV*\n\n🔴 [Live Stream](https://www.nasa.gov/nasatv)\n\nWatch launches, ISS activities and press conferences live!",
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
},
"he": {
    "choose_lang":"🌍 *Выберите язык / Choose language / בחרו שפה / اختر اللغة*",
    "lang_set":"🇮🇱 שפה: *עברית*",
    "start_msg":"🚀 *NASA Space Bot* — המדריך שלך ליקום, {name}!\n\n*6 קטגוריות, 50+ מדורים* 👇",
    "main_menu":"🌠 *תפריט ראשי:*", "choose_sec":"\n\nבחר מדור 👇",
    "cat_photo":"📸 תמונות", "cat_solarsys":"🪐 מערכת השמש",
    "cat_deepspace":"🌌 חלל עמוק", "cat_earth":"🌍 כדור הארץ",
    "cat_science":"🔬 מדע", "cat_live":"🔴 LIVE",
    "cat_interact_btn":"🎮 אינטראקטיב",
    "cat_news":"📰 חדשות חלל",
    "title_news":"📰 *חדשות החלל*",
    "btn_news_nasa":"🚀 NASA",
    "btn_news_sfn":"🛸 SpaceflightNow",
    "btn_news_spacenews":"📡 SpaceNews",
    "btn_news_spacedotcom":"🌌 Space.com",
    "btn_news_planetary":"🪐 Planetary",
    "btn_news_next":"➡️ הבא",
    "btn_news_source":"🔗 מקור",
    "news_loading":"📰 טוען חדשות...",
    "news_empty":"📭 לא נמצאו כתבות",
    "news_counter":"כתבה {idx}/{total}",
    "btn_spacefact":"⭐ עובדה", "btn_channels":"📢 ערוצים", "btn_lang":"🌍 שפה",
    "back_menu":"◀️ תפריט", "back_cat":"◀️ חזרה",
    "btn_refresh":"🔄 רענון", "btn_more_rnd":"🎲 עוד", "btn_another":"🔄 עוד", "btn_other_rv":"🔄 אחר",
    "title_photo":"📸 *תמונות*", "title_solarsys":"🪐 *מערכת השמש*",
    "title_deepspace":"🌌 *חלל עמוק*", "title_earth":"🌍 *כדור הארץ*",
    "title_science":"🔬 *מדע*", "title_live":"🔴 *LIVE*",
    "title_interact":"🎮 *אינטראקטיב*",
    "err":"❌ שגיאה", "no_data":"📭 אין נתונים", "no_img":"📭 אין תמונות",
    "unknown":"🤔 /start", "hazard_yes":"🔴 מסוכן", "hazard_no":"🟢 בטוח",
    "iss_map":"🗺 מפה", "iss_no_crew":"אין", "live_nodata":"אין נתונים.",
    "moon_phases":["ירח חדש","סהר עולה","רבע ראשון","ירח עולה","ירח מלא","ירח יורד","רבע אחרון","סהר יורד"],
    "btn_planet_calc":"🪐 מחשבון כוכבים","btn_horoscope":"🔮 הורוסקופ","btn_space_name":"👨‍🚀 שם קוסמי",
    "btn_quiz":"🧠 חידון","btn_poll":"📊 סקר","btn_capsule":"⏳ קפסולת זמן",
    "btn_lunar_cal":"📅 לוח ירח","btn_mars_live":"🤖 רובר","btn_notifications":"🔔 התראות","btn_nasa_tv":"📺 NASA TV",
    "planet_calc_ask_date":"📅 הכנס תאריך לידה: *DD.MM.YYYY*\nדוגמה: 15.04.1990",
    "planet_calc_ask_weight":"⚖️ הכנס משקל בק\"ג\nדוגמה: 70",
    "planet_calc_error_date":"❌ פורמט שגוי. נסה: *15.04.1990*",
    "planet_calc_error_weight":"❌ משקל שגוי. 1–500 ק\"ג",
    "horoscope_ask":"♈ הכנס יום וחודש לידה\nדוגמה: *15.04*",
    "horoscope_error":"❌ פורמט שגוי. נסה: *15.04*",
    "quiz_start":"🧠 *חידון חלל*\n\n10 שאלות. מוכן?",
    "quiz_btn_start":"🚀 התחל!","quiz_next":"➡️ הבא","quiz_finish":"🏁 תוצאה",
    "quiz_correct":"נכון! ✅","quiz_wrong":"לא נכון ❌. תשובה נכונה:",
    "quiz_result":"🏆 *תוצאה: {score}/10*\n\n{grade}",
    "capsule_ask":"⏳ *קפסולת זמן*\n\nכתוב הודעה לעצמך בעתיד (עד 2000 תווים). תגיע בעוד שנה! ✨",
    "capsule_saved":"✅ *נשמר!*\n\n📅 ייפתח: *{date}*",
    "capsule_cancel":"❌ בוטל",
    "name_gen_title":"👨‍🚀 *השם הקוסמי שלך*\n\n",
    "notif_title":"🔔 *הגדרות התראות*\n\nבחר על מה לקבל התראות:",
    "notif_subscribed":"✅ נרשמת","notif_unsubscribed":"🔕 בוטל",
    "notif_sub_ast":"☄️ אסטרואידים","notif_sub_meteor":"🌠 מטאורים",
    "notif_sub_sw":"🌞 מזג חלל","notif_sub_lunar":"🌕 שלבי ירח","notif_sub_news":"📰 חדשות",
    "mars_rover_title":"🤖 *מצב הרובר*\n\n","lunar_cal_title":"📅 *לוח ירח*\n\n",
    "nasa_tv_title":"📺 *NASA TV*\n\n🔴 [שידור חי](https://www.nasa.gov/nasatv)",
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
},
"ar": {
    "choose_lang":"🌍 *Выберите язык / Choose language / בחרו שפה / اختر اللغة*",
    "lang_set":"🇦🇪 اللغة: *العربية*",
    "start_msg":"🚀 *NASA Space Bot* — دليلك إلى الكون، {name}!\n\n*6 فئات، 50+ قسماً* 👇",
    "main_menu":"🌠 *القائمة الرئيسية:*", "choose_sec":"\n\nاختر قسماً 👇",
    "cat_photo":"📸 الصور", "cat_solarsys":"🪐 المجموعة الشمسية",
    "cat_deepspace":"🌌 الفضاء العميق", "cat_earth":"🌍 الأرض",
    "cat_science":"🔬 العلوم", "cat_live":"🔴 مباشر",
    "cat_interact_btn":"🎮 تفاعلي",
    "cat_news":"📰 أخبار الفضاء",
    "title_news":"📰 *أخبار الفضاء*",
    "btn_news_nasa":"🚀 NASA",
    "btn_news_sfn":"🛸 SpaceflightNow",
    "btn_news_spacenews":"📡 SpaceNews",
    "btn_news_spacedotcom":"🌌 Space.com",
    "btn_news_planetary":"🪐 Planetary",
    "btn_news_next":"➡️ التالي",
    "btn_news_source":"🔗 المصدر",
    "news_loading":"📰 جاري تحميل الأخبار...",
    "news_empty":"📭 لا توجد مقالات",
    "news_counter":"مقالة {idx}/{total}",
    "btn_spacefact":"⭐ حقيقة", "btn_channels":"📢 قنواتنا", "btn_lang":"🌍 اللغة",
    "back_menu":"◀️ القائمة", "back_cat":"◀️ العودة",
    "btn_refresh":"🔄 تحديث", "btn_more_rnd":"🎲 المزيد", "btn_another":"🔄 أخرى", "btn_other_rv":"🔄 مركبة",
    "title_photo":"📸 *الصور*", "title_solarsys":"🪐 *المجموعة الشمسية*",
    "title_deepspace":"🌌 *الفضاء العميق*", "title_earth":"🌍 *الأرض*",
    "title_science":"🔬 *العلوم*", "title_live":"🔴 *مباشر*",
    "title_interact":"🎮 *تفاعلي*",
    "err":"❌ خطأ", "no_data":"📭 لا بيانات", "no_img":"📭 لا صور",
    "unknown":"🤔 /start", "hazard_yes":"🔴 خطير", "hazard_no":"🟢 آمن",
    "iss_map":"🗺 خريطة", "iss_no_crew":"لا بيانات", "live_nodata":"لا بيانات.",
    "moon_phases":["محاق","هلال متزايد","تربيع أول","بدر متزايد","بدر","بدر متناقص","تربيع أخير","هلال متناقص"],
    "btn_planet_calc":"🪐 حاسبة الكواكب","btn_horoscope":"🔮 برج","btn_space_name":"👨‍🚀 اسم فضائي",
    "btn_quiz":"🧠 مسابقة","btn_poll":"📊 استطلاع","btn_capsule":"⏳ كبسولة زمن",
    "btn_lunar_cal":"📅 تقويم قمري","btn_mars_live":"🤖 مركبة","btn_notifications":"🔔 إشعارات","btn_nasa_tv":"📺 NASA TV",
    "planet_calc_ask_date":"📅 أدخل تاريخ الميلاد: *DD.MM.YYYY*\nمثال: 15.04.1990",
    "planet_calc_ask_weight":"⚖️ أدخل وزنك بالكيلوغرام\nمثال: 70",
    "planet_calc_error_date":"❌ تنسيق خاطئ. جرب: *15.04.1990*",
    "planet_calc_error_weight":"❌ وزن خاطئ. 1–500 كغ",
    "horoscope_ask":"♈ أدخل يوم وشهر الميلاد\nمثال: *15.04*",
    "horoscope_error":"❌ تنسيق خاطئ. جرب: *15.04*",
    "quiz_start":"🧠 *مسابقة الفضاء*\n\n10 أسئلة. هل أنت مستعد؟",
    "quiz_btn_start":"🚀 ابدأ!","quiz_next":"➡️ التالي","quiz_finish":"🏁 النتيجة",
    "quiz_correct":"صحيح! ✅","quiz_wrong":"خطأ ❌. الإجابة الصحيحة:",
    "quiz_result":"🏆 *النتيجة: {score}/10*\n\n{grade}",
    "capsule_ask":"⏳ *كبسولة الزمن*\n\nاكتب رسالة لنفسك في المستقبل (حتى 2000 حرف). ستصلك بعد سنة! ✨",
    "capsule_saved":"✅ *تم الحفظ!*\n\n📅 ستُفتح: *{date}*",
    "capsule_cancel":"❌ تم الإلغاء",
    "name_gen_title":"👨‍🚀 *اسمك الفضائي*\n\n",
    "notif_title":"🔔 *إعدادات الإشعارات*\n\nاختر ما تريد الإشعار به:",
    "notif_subscribed":"✅ تم الاشتراك","notif_unsubscribed":"🔕 تم الإلغاء",
    "notif_sub_ast":"☄️ كويكبات خطرة","notif_sub_meteor":"🌠 شهب",
    "notif_sub_sw":"🌞 طقس الفضاء","notif_sub_lunar":"🌕 أطوار القمر","notif_sub_news":"📰 أخبار NASA",
    "mars_rover_title":"🤖 *حالة المركبة*\n\n","lunar_cal_title":"📅 *التقويم القمري*\n\n",
    "nasa_tv_title":"📺 *NASA TV*\n\n🔴 [بث مباشر](https://www.nasa.gov/nasatv)",
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
},
}
# ── End: TRANSLATIONS ─────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: TRANSLATION & UTILITY HELPERS                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def tx(lang, key, **kw):
    val = T.get(lang, T["en"]).get(key) or T["en"].get(key) or key
    return val.format(**kw) if kw else val

def get_lang(ctx): return ctx.user_data.get("lang", "ru")
def strip_html(t): return re.sub(r'<[^>]+>', '', t or '')
# ── End: TRANSLATION & UTILITY HELPERS ────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: NASA API & HTTP HELPERS                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def nasa_req(path, params=None):
    p = {"api_key": NASA_API_KEY}
    if params: p.update(params)
    r = requests.get(f"{NASA_BASE}{path}", params=p, timeout=15)
    r.raise_for_status(); return r.json()

def get_json(url, params=None, timeout=12):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status(); return r.json()
# ── End: NASA API & HTTP HELPERS ──────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: ISS POSITION & CREW HELPERS (dual-API fallback)                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def get_iss_position() -> dict:
    """Try wheretheiss.at first (reliable), fall back to open-notify.org."""
    for url, parser in [
        ("https://api.wheretheiss.at/v1/satellites/25544",
         lambda d: {"lat": float(d["latitude"]), "lon": float(d["longitude"]),
                    "ts": datetime.utcnow().strftime("%H:%M:%S UTC")}),
        ("http://api.open-notify.org/iss-now.json",
         lambda d: {"lat": float(d["iss_position"]["latitude"]),
                    "lon": float(d["iss_position"]["longitude"]),
                    "ts": datetime.utcfromtimestamp(d["timestamp"]).strftime("%H:%M:%S UTC")}),
    ]:
        try:
            r = requests.get(url, timeout=8); r.raise_for_status()
            return parser(r.json())
        except Exception:
            continue
    raise RuntimeError("ISS position unavailable (both APIs failed)")

def get_iss_crew() -> list:
    """Fetch ISS crew list; returns [] on failure."""
    try:
        r = requests.get("http://api.open-notify.org/astros.json", timeout=8)
        if r.ok:
            return [p["name"] for p in r.json().get("people", []) if p.get("craft") == "ISS"]
    except Exception:
        pass
    return []
# ── End: ISS POSITION & CREW HELPERS ─────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: IN-MEMORY CACHE (30-minute TTL)                                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
_cache: dict = {}
CACHE_TTL = 1800

def cache_get(key: str):
    if key in _cache:
        ts, data = _cache[key]
        if (datetime.utcnow().timestamp() - ts) < CACHE_TTL:
            return data
    return None

def cache_set(key: str, data):
    _cache[key] = (datetime.utcnow().timestamp(), data)
# ── End: IN-MEMORY CACHE ──────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: TELEGRAM MESSAGE HELPERS (safe_answer, safe_edit, del_msg)             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def safe_answer(q):
    try: await q.answer()
    except: pass

async def safe_edit(q, text, reply_markup=None):
    try:
        await q.edit_message_text(text, parse_mode="Markdown",
                                   reply_markup=reply_markup, disable_web_page_preview=True)
    except:
        try: await q.message.delete()
        except: pass
        try: await q.message.chat.send_message(text, parse_mode="Markdown",
                                                reply_markup=reply_markup, disable_web_page_preview=True)
        except: pass

async def del_msg(q):
    try: await q.message.delete()
    except: pass
# ── End: TELEGRAM MESSAGE HELPERS ─────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: INLINE KEYBOARDS                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
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
        [InlineKeyboardButton(L("cat_photo"),        callback_data="cat_photo")],
        [InlineKeyboardButton(L("cat_solarsys"),     callback_data="cat_solarsys")],
        [InlineKeyboardButton(L("cat_deepspace"),    callback_data="cat_deepspace")],
        [InlineKeyboardButton(L("cat_earth"),        callback_data="cat_earth")],
        [InlineKeyboardButton(L("cat_science"),      callback_data="cat_science")],
        [InlineKeyboardButton(L("cat_live"),         callback_data="cat_live")],
        [InlineKeyboardButton(L("cat_interact_btn"), callback_data="cat_interact")],
        [InlineKeyboardButton(L("cat_news"),         callback_data="cat_news")],
        [InlineKeyboardButton(L("btn_spacefact"),    callback_data="spacefact"),
         InlineKeyboardButton(L("btn_channels"),     callback_data="channels")],
        [InlineKeyboardButton(L("btn_lang"),         callback_data="choose_lang")],
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
        [InlineKeyboardButton(L("btn_apod"),        callback_data="apod"),
         InlineKeyboardButton(L("btn_apod_rnd"),    callback_data="apod_random")],
        [InlineKeyboardButton(L("btn_gallery"),     callback_data="gallery"),
         InlineKeyboardButton(L("btn_hubble"),      callback_data="deepspace")],
        [InlineKeyboardButton(L("btn_mars"),        callback_data="mars"),
         InlineKeyboardButton(L("btn_mars_rv"),     callback_data="mars_rovers")],
        [InlineKeyboardButton(L("btn_epic"),        callback_data="epic"),
         InlineKeyboardButton(L("btn_earth_night"), callback_data="earth_night")],
        [InlineKeyboardButton(L("btn_nebulae"),     callback_data="nebulae"),
         InlineKeyboardButton(L("btn_clusters"),    callback_data="clusters")],
        [InlineKeyboardButton(L("btn_eclipse"),     callback_data="eclipse"),
         InlineKeyboardButton(L("btn_jwst"),        callback_data="jwst_gallery")],
        [InlineKeyboardButton(L("btn_moon_gal"),    callback_data="moon_gallery"),
         InlineKeyboardButton(L("btn_blue_marble"), callback_data="blue_marble")],
        [InlineKeyboardButton(L("btn_spacewalks"),  callback_data="spacewalks")],
        [InlineKeyboardButton(L("back_menu"),       callback_data="back")],
    ])

def cat_solarsys_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_planets"),    callback_data="planets"),
         InlineKeyboardButton(L("btn_giants"),     callback_data="giants")],
        [InlineKeyboardButton(L("btn_dwarfs"),     callback_data="dwarfplanets"),
         InlineKeyboardButton(L("btn_moons"),      callback_data="moons")],
        [InlineKeyboardButton(L("btn_asteroids"),  callback_data="asteroids"),
         InlineKeyboardButton(L("btn_comets"),     callback_data="comets")],
        [InlineKeyboardButton(L("btn_moon"),       callback_data="moon"),
         InlineKeyboardButton(L("btn_meteors"),    callback_data="meteors")],
        [InlineKeyboardButton(L("btn_sun"),        callback_data="sun"),
         InlineKeyboardButton(L("btn_spaceweather"), callback_data="spaceweather")],
        [InlineKeyboardButton(L("btn_ceres"),      callback_data="ceres"),
         InlineKeyboardButton(L("btn_pluto"),      callback_data="pluto_close")],
        [InlineKeyboardButton(L("btn_kuiper"),     callback_data="kuiper_belt"),
         InlineKeyboardButton(L("btn_alignment"),  callback_data="planet_alignment")],
        [InlineKeyboardButton(L("btn_solar_ecl"),  callback_data="solar_eclipse"),
         InlineKeyboardButton(L("btn_scale"),      callback_data="orbital_scale")],
        [InlineKeyboardButton(L("btn_lunar_miss"), callback_data="lunar_missions")],
        [InlineKeyboardButton(L("back_menu"),      callback_data="back")],
    ])

def cat_deepspace_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_deepspace"),  callback_data="deepspace"),
         InlineKeyboardButton(L("btn_milkyway"),   callback_data="milkyway")],
        [InlineKeyboardButton(L("btn_blackholes"), callback_data="blackholes"),
         InlineKeyboardButton(L("btn_supernovae"), callback_data="supernovae")],
        [InlineKeyboardButton(L("btn_pulsars"),    callback_data="pulsars"),
         InlineKeyboardButton(L("btn_nearstars"),  callback_data="nearstars")],
        [InlineKeyboardButton(L("btn_exoplanets"), callback_data="exoplanets"),
         InlineKeyboardButton(L("btn_seti"),       callback_data="seti")],
        [InlineKeyboardButton(L("btn_gravwaves"),  callback_data="gravwaves"),
         InlineKeyboardButton(L("btn_darkmatter"), callback_data="darkmatter")],
        [InlineKeyboardButton(L("btn_future"),     callback_data="future"),
         InlineKeyboardButton(L("btn_radioastro"), callback_data="radioastro")],
        [InlineKeyboardButton(L("btn_quasars"),    callback_data="quasars"),
         InlineKeyboardButton(L("btn_grb"),        callback_data="grb")],
        [InlineKeyboardButton(L("btn_cmb"),        callback_data="cmb"),
         InlineKeyboardButton(L("btn_gal_coll"),   callback_data="galaxy_collision")],
        [InlineKeyboardButton(L("btn_starform"),   callback_data="star_formation"),
         InlineKeyboardButton(L("btn_dark_en"),    callback_data="dark_energy")],
        [InlineKeyboardButton(L("btn_cosm_web"),   callback_data="cosmic_web"),
         InlineKeyboardButton(L("btn_red_giants"), callback_data="red_giants")],
        [InlineKeyboardButton(L("back_menu"),      callback_data="back")],
    ])

def cat_earth_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_epic"),       callback_data="epic"),
         InlineKeyboardButton(L("btn_climate"),    callback_data="climate")],
        [InlineKeyboardButton(L("btn_volcanoes"),  callback_data="volcanoes"),
         InlineKeyboardButton(L("btn_hurricanes"), callback_data="hurricanes")],
        [InlineKeyboardButton(L("btn_aurora"),     callback_data="aurora"),
         InlineKeyboardButton(L("btn_magneto"),    callback_data="magnetosphere")],
        [InlineKeyboardButton(L("btn_satellites"), callback_data="satellites"),
         InlineKeyboardButton(L("btn_debris"),     callback_data="debris")],
        [InlineKeyboardButton(L("btn_wildfires"),  callback_data="wildfires"),
         InlineKeyboardButton(L("btn_ice"),        callback_data="ice_sheets")],
        [InlineKeyboardButton(L("btn_deforest"),   callback_data="deforestation"),
         InlineKeyboardButton(L("btn_nightlights"),callback_data="night_lights")],
        [InlineKeyboardButton(L("btn_ozone"),      callback_data="ozone"),
         InlineKeyboardButton(L("btn_ocean_temp"), callback_data="ocean_temp")],
        [InlineKeyboardButton(L("btn_ocean_cur"),  callback_data="ocean_currents"),
         InlineKeyboardButton(L("btn_tornadoes"),  callback_data="tornadoes")],
        [InlineKeyboardButton(L("back_menu"),      callback_data="back")],
    ])

def cat_science_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_launches"),   callback_data="launches"),
         InlineKeyboardButton(L("btn_missions"),   callback_data="missions")],
        [InlineKeyboardButton(L("btn_history"),    callback_data="history"),
         InlineKeyboardButton(L("btn_iss"),        callback_data="iss")],
        [InlineKeyboardButton(L("btn_telescopes"), callback_data="telescopes"),
         InlineKeyboardButton(L("btn_sp_stations"),callback_data="space_stations")],
        [InlineKeyboardButton(L("btn_moon_sites"), callback_data="moon_landing_sites"),
         InlineKeyboardButton(L("btn_women"),      callback_data="women_in_space")],
        # FIX: mars_colonization is now properly handled in STATIC_TEXTS + IMG_MAP
        [InlineKeyboardButton(L("btn_mars_col"),   callback_data="mars_colonization"),
         InlineKeyboardButton(L("btn_sp_med"),     callback_data="space_medicine")],
        [InlineKeyboardButton(L("btn_rockets"),    callback_data="rocket_engines"),
         InlineKeyboardButton(L("btn_training"),   callback_data="astronaut_training")],
        [InlineKeyboardButton(L("btn_records"),    callback_data="space_records"),
         InlineKeyboardButton(L("btn_food"),       callback_data="space_food")],
        [InlineKeyboardButton(L("back_menu"),      callback_data="back")],
    ])

def cat_live_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_solar_wind"),  callback_data="live_solar_wind")],
        [InlineKeyboardButton(L("btn_kp"),          callback_data="live_kp"),
         InlineKeyboardButton(L("btn_flares"),      callback_data="live_flares")],
        [InlineKeyboardButton(L("btn_live_iss"),    callback_data="live_iss"),
         InlineKeyboardButton(L("btn_radiation"),   callback_data="live_radiation")],
        [InlineKeyboardButton(L("btn_aurora_f"),    callback_data="live_aurora_forecast"),
         InlineKeyboardButton(L("btn_geomag"),      callback_data="live_geomagnetic_alert")],
        [InlineKeyboardButton(L("btn_sunspot"),     callback_data="live_sunspot"),
         InlineKeyboardButton(L("btn_live_epic"),   callback_data="live_epic_latest")],
        [InlineKeyboardButton(L("btn_sat_count"),   callback_data="live_satellite_count")],
        [InlineKeyboardButton(L("back_menu"),       callback_data="back")],
    ])

def cat_interact_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_planet_calc"),   callback_data="planet_calc")],
        [InlineKeyboardButton(L("btn_horoscope"),     callback_data="horoscope_menu")],
        [InlineKeyboardButton(L("btn_space_name"),    callback_data="space_name")],
        [InlineKeyboardButton(L("btn_quiz"),          callback_data="quiz_start_menu")],
        [InlineKeyboardButton(L("btn_poll"),          callback_data="daily_poll")],
        [InlineKeyboardButton(L("btn_capsule"),       callback_data="capsule_menu")],
        [InlineKeyboardButton(L("btn_lunar_cal"),     callback_data="lunar_calendar")],
        [InlineKeyboardButton(L("btn_mars_live"),     callback_data="mars_rover_live")],
        [InlineKeyboardButton(L("btn_notifications"), callback_data="notifications_menu")],
        [InlineKeyboardButton(L("btn_nasa_tv"),       callback_data="nasa_tv")],
        [InlineKeyboardButton(L("back_menu"),         callback_data="back")],
    ])

def cat_news_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_news_nasa"),        callback_data="news_nasa")],
        [InlineKeyboardButton(L("btn_news_sfn"),         callback_data="news_sfn")],
        [InlineKeyboardButton(L("btn_news_spacenews"),   callback_data="news_spacenews")],
        [InlineKeyboardButton(L("btn_news_spacedotcom"), callback_data="news_spacedotcom")],
        [InlineKeyboardButton(L("btn_news_planetary"),   callback_data="news_planetary")],
        [InlineKeyboardButton(L("back_menu"),            callback_data="back")],
    ])

def news_article_kb(lang, source_key, idx, total, article_link):
    rows = []
    if total > 1:
        next_idx = (idx + 1) % total
        rows.append([InlineKeyboardButton(
            f"{tx(lang,'btn_news_next')} ({next_idx+1}/{total})",
            callback_data=f"news_page_{source_key}_{next_idx}"
        )])
    src_row = []
    if article_link:
        src_row.append(InlineKeyboardButton(tx(lang, "btn_news_source"), url=article_link))
    src_row.append(InlineKeyboardButton(tx(lang, "back_menu"), callback_data="back"))
    rows.append(src_row)
    return InlineKeyboardMarkup(rows)

def notifications_kb(lang, subs, chat_id):
    def btn(key, cb):
        label  = tx(lang, key)
        topic  = cb.replace("notif_toggle_", "")
        status = "✅" if chat_id in subs.get(topic, []) else "🔔"
        return InlineKeyboardButton(f"{status} {label}", callback_data=cb)
    return InlineKeyboardMarkup([
        [btn("notif_sub_ast",    "notif_toggle_asteroids")],
        [btn("notif_sub_meteor", "notif_toggle_meteors")],
        [btn("notif_sub_sw",     "notif_toggle_space_weather")],
        [btn("notif_sub_lunar",  "notif_toggle_lunar")],
        [btn("notif_sub_news",   "notif_toggle_nasa_news")],
        [InlineKeyboardButton(tx(lang, "back_menu"), callback_data="back")],
    ])

def quiz_kb(lang, q_index, answered=False):
    if answered:
        nxt   = "quiz_next" if q_index < 9 else "quiz_finish"
        label = tx(lang, "quiz_next") if q_index < 9 else tx(lang, "quiz_finish")
        return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=nxt)]])
    opts = QUIZ_QUESTIONS[q_index]["options"]
    rows = [[InlineKeyboardButton(opt, callback_data=f"quiz_ans_{q_index}_{i}")]
            for i, opt in enumerate(opts)]
    return InlineKeyboardMarkup(rows)
# ── End: INLINE KEYBOARDS ─────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: STATIC DATA (planets, facts, showers, exoplanets, gravity, zodiac…)   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
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

SPACE_FACTS = {
    "ru":["🌌 Вселенной ~13.8 млрд лет.","⭐ Звёзд больше, чем песчинок на всех пляжах.","🌑 Следы Армстронга на Луне сохранятся миллионы лет.","☀️ Свет от Солнца летит 8 мин 20 сек.","🪐 День на Венере длиннее года.","🌊 На Энцеладе — гейзеры воды.","⚫ Если сжать Землю до горошины — чёрная дыра.","🚀 Вояджер-1 покинул Солнечную систему в 2012 году."],
    "en":["🌌 Universe is ~13.8 billion years old.","⭐ More stars than grains of sand on all beaches.","🌑 Armstrong's footprints last millions of years.","☀️ Sunlight takes 8 min 20 sec to reach Earth.","🪐 A day on Venus is longer than its year.","🌊 Enceladus has water geysers.","⚫ Earth compressed to marble = black hole.","🚀 Voyager 1 entered interstellar space in 2012."],
    "he":["🌌 היקום בן ~13.8 מיליארד שנה.","⭐ יותר כוכבים מגרגרי חול.","🌑 עקבות ארמסטרונג ישמרו מיליוני שנים.","☀️ אור השמש מגיע תוך 8 דקות ו-20 שניות.","🪐 יום על נוגה ארוך מהשנה.","🌊 לאנקלדוס יש גייזרים.","⚫ כדור הארץ לגולה = חור שחור.","🚀 ווֹיאַג'ר 1 — 2012."],
    "ar":["🌌 عمر الكون ~13.8 مليار سنة.","⭐ نجوم أكثر من حبات الرمل.","🌑 آثار أرمسترونغ ملايين السنين.","☀️ ضوء الشمس 8 دقائق و20 ثانية.","🪐 يوم الزهرة أطول من سنتها.","🌊 إنسيلادوس لديه ينابيع.","⚫ الأرض بحجم رخامة = ثقب أسود.","🚀 فوياجر 1 — 2012."],
}

METEOR_SHOWERS = [
    {"name":{"ru":"Персеиды","en":"Perseids","he":"פרסאידים","ar":"البرشاويات"},"peak":"12-13 Aug","rate":"100+/h","parent":"Swift-Tuttle","speed":"59km/s"},
    {"name":{"ru":"Геминиды","en":"Geminids","he":"גמינידים","ar":"الجوزائيات"},"peak":"13-14 Dec","rate":"120+/h","parent":"3200 Phaethon","speed":"35km/s"},
    {"name":{"ru":"Леониды","en":"Leonids","he":"ליאונידים","ar":"الأسديات"},"peak":"17-18 Nov","rate":"10-15/h","parent":"Tempel-Tuttle","speed":"71km/s"},
]

KNOWN_EXOPLANETS = [
    {"name":"Kepler-452b","star":"Kepler-452","year":2015,"radius":1.63,"period":384.8,"dist_ly":1400,"note":{"ru":"Двойник Земли","en":"Earth twin","he":"כפיל כדור הארץ","ar":"توأم الأرض"}},
    {"name":"TRAPPIST-1e","star":"TRAPPIST-1","year":2017,"radius":0.92,"period":6.1,"dist_ly":39,"note":{"ru":"Возможна жидкая вода","en":"Possible liquid water","he":"מים נוזליים אפשריים","ar":"ماء سائل محتمل"}},
    {"name":"Proxima Centauri b","star":"Proxima Cen","year":2016,"radius":1.3,"period":11.2,"dist_ly":4.2,"note":{"ru":"Ближайшая экзопланета!","en":"Nearest exoplanet!","he":"הקרובה ביותר!","ar":"الأقرب!"}},
    {"name":"TOI 700 d","star":"TOI 700","year":2020,"radius":1.19,"period":37.4,"dist_ly":101,"note":{"ru":"Земного размера","en":"Earth-sized","he":"בגודל כדור הארץ","ar":"بحجم الأرض"}},
]

PLANET_GRAVITY   = {"☿ Mercury":0.376,"♀ Venus":0.904,"🌍 Earth":1.0,"♂ Mars":0.379,
                     "♃ Jupiter":2.528,"♄ Saturn":1.065,"⛢ Uranus":0.886,"♆ Neptune":1.137}
PLANET_YEAR_DAYS = {"☿ Mercury":87.97,"♀ Venus":224.70,"🌍 Earth":365.25,"♂ Mars":686.97,
                     "♃ Jupiter":4332.59,"♄ Saturn":10759.22,"⛢ Uranus":30688.50,"♆ Neptune":60182.0}

ZODIAC_RANGES = [
    ((3,21),(4,19),"Aries"),((4,20),(5,20),"Taurus"),((5,21),(6,20),"Gemini"),
    ((6,21),(7,22),"Cancer"),((7,23),(8,22),"Leo"),((8,23),(9,22),"Virgo"),
    ((9,23),(10,22),"Libra"),((10,23),(11,21),"Scorpio"),((11,22),(12,21),"Sagittarius"),
    ((12,22),(12,31),"Capricorn"),((1,1),(1,19),"Capricorn"),((1,20),(2,18),"Aquarius"),
    ((2,19),(3,20),"Pisces"),
]

NAME_PREFIXES = ["Alpha","Beta","Gamma","Delta","Zeta","Omega","Nova","Astro","Cosmo","Stellar",
                 "Nebula","Quasar","Pulsar","Photon","Plasma","Corona","Aurora","Vega","Orion","Sirius"]
NAME_SUFFIXES = ["Prime","Major","Centauri","Nexus","Proxima","Maxima","Ultima","Eternis",
                 "Vortex","Zenith","Polaris","Astra","Solara","Lunara","Helios","Gaia","Infinity"]
STAR_CODES    = ["2025","2026","X","VII","Omega","Alpha","3C","HD","NGC"]

DAILY_POLLS = [
    {"q":{"ru":"Где бы ты предпочёл жить?","en":"Where would you prefer to live?"},
     "opts":{"ru":["В облаках Венеры ☁️","В пещерах Марса 🪐","На Луне 🌙","У Юпитера ♃"],
             "en":["Venus clouds ☁️","Mars caves 🪐","The Moon 🌙","Jupiter station ♃"]}},
    {"q":{"ru":"Что важнее для человечества?","en":"What matters most for humanity?"},
     "opts":{"ru":["Колонизация Марса 🔴","Экзопланеты 🔭","Тёмная материя ⚫","Астероиды ☄️"],
             "en":["Mars 🔴","Exoplanets 🔭","Dark matter ⚫","Asteroid mining ☄️"]}},
    {"q":{"ru":"Любимая миссия NASA?","en":"Favorite NASA mission?"},
     "opts":{"ru":["Аполлон 🌙","Вояджер 🚀","Хаббл 🔭","Персеверанс 🤖"],
             "en":["Apollo 🌙","Voyager 🚀","Hubble 🔭","Perseverance 🤖"]}},
    {"q":{"ru":"Что взял бы на МКС?","en":"What would you bring to the ISS?"},
     "opts":{"ru":["Гитару 🎸","Книги 📚","Спортзал 🏋️","Телескоп 🔭"],
             "en":["Guitar 🎸","Books 📚","Gym 🏋️","Telescope 🔭"]}},
]

HOROSCOPES = {
    "ru": {
        "Aries":"♈ *Овен*\n\nСолнечный ветер умеренный. Марс в благоприятной позиции — хороший день для запуска новых проектов!\n\n🔬 Kp-индекс стабилен. ⚡ Энергия: ████████░░ 80%",
        "Taurus":"♉ *Телец*\n\nВенера в перигелии — время долгосрочных планов.\n\n🔬 Солнечная активность низкая. ⚡ Энергия: ██████░░░░ 60%",
        "Gemini":"♊ *Близнецы*\n\nДва полюса Урана: будь гибок!\n\n🔬 Сверхновые в твоём секторе. ⚡ Энергия: █████████░ 90%",
        "Cancer":"♋ *Рак*\n\nЛуна в апогее — время для рефлексии.\n\n🔬 Лунные фазы влияют на ионосферу. ⚡ Энергия: ████░░░░░░ 40%",
        "Leo":"♌ *Лев*\n\nВспышки класса M — энергия зашкаливает!\n\n🔬 Возможны полярные сияния! ⚡ Энергия: ██████████ 100%",
        "Virgo":"♍ *Дева*\n\nДанные JWST: детали решают всё.\n\n🔬 Webb фиксирует новые экзопланеты. ⚡ Энергия: ███████░░░ 70%",
        "Libra":"♎ *Весы*\n\nЦентр масс Земля-Луна в равновесии.\n\n🔬 Гравитационные волны зафиксированы LIGO. ⚡ Энергия: ███████░░░ 70%",
        "Scorpio":"♏ *Скорпион*\n\nТёмная материя реальна. Изучай скрытое.\n\n🔬 27% Вселенной — тёмная материя. ⚡ Энергия: ████████░░ 80%",
        "Sagittarius":"♐ *Стрелец*\n\nСтрела летит к Стрельцу A*!\n\n🔬 Центр галактики за пылевыми облаками. ⚡ Энергия: █████████░ 90%",
        "Capricorn":"♑ *Козерог*\n\nСатурн с кольцами — структура и порядок.\n\n🔬 Кольца Сатурна ~100м толщиной. ⚡ Энергия: ██████░░░░ 60%",
        "Aquarius":"♒ *Водолей*\n\nУран наклонён 98° — нестандартные решения!\n\n🔬 Уран вращается на боку. ⚡ Энергия: ████████░░ 80%",
        "Pisces":"♓ *Рыбы*\n\nГейзеры Энцелада: интуиция ведёт к жизни.\n\n🔬 Под льдом Энцелада — океан. ⚡ Энергия: █████░░░░░ 50%",
    },
    "en": {
        "Aries":"♈ *Aries*\n\nSolar wind moderate — Mars favorable. Launch day!\n\n🔬 Kp stable. ⚡ Energy: ████████░░ 80%",
        "Taurus":"♉ *Taurus*\n\nVenus at perihelion — long-term plans.\n\n🔬 Low solar activity. ⚡ Energy: ██████░░░░ 60%",
        "Gemini":"♊ *Gemini*\n\nUranus dual poles — stay flexible!\n\n🔬 Supernova activity nearby. ⚡ Energy: █████████░ 90%",
        "Cancer":"♋ *Cancer*\n\nMoon at apogee — reflect.\n\n🔬 Lunar phases affect ionosphere. ⚡ Energy: ████░░░░░░ 40%",
        "Leo":"♌ *Leo*\n\nM-class flares — energy off charts!\n\n🔬 Aurora possible tonight! ⚡ Energy: ██████████ 100%",
        "Virgo":"♍ *Virgo*\n\nJWST: details matter.\n\n🔬 Webb imaging exoplanets. ⚡ Energy: ███████░░░ 70%",
        "Libra":"♎ *Libra*\n\nEarth-Moon barycenter balanced.\n\n🔬 LIGO detected waves. ⚡ Energy: ███████░░░ 70%",
        "Scorpio":"♏ *Scorpio*\n\nDark matter: hidden forces are real.\n\n🔬 27% of Universe is dark matter. ⚡ Energy: ████████░░ 80%",
        "Sagittarius":"♐ *Sagittarius*\n\nArrow toward Sgr A*!\n\n🔬 Galactic center behind dust. ⚡ Energy: █████████░ 90%",
        "Capricorn":"♑ *Capricorn*\n\nSaturn: structure is key.\n\n🔬 Saturn's rings 100m thick. ⚡ Energy: ██████░░░░ 60%",
        "Aquarius":"♒ *Aquarius*\n\nUranus tilted 98° — unconventional!\n\n🔬 Uranus rotates on its side. ⚡ Energy: ████████░░ 80%",
        "Pisces":"♓ *Pisces*\n\nEnceladus geysers: trust intuition.\n\n🔬 Liquid ocean under Enceladus ice. ⚡ Energy: █████░░░░░ 50%",
    },
}

QUIZ_QUESTIONS = [
    {"q":{"ru":"Сколько планет в Солнечной системе?","en":"How many planets in the Solar System?","he":"כמה כוכבי לכת?","ar":"كم عدد الكواكب؟"},
     "options":["7","8","9","10"],"answer":1,
     "exp":{"ru":"С 2006 г. — 8 (Плутон стал карликовой планетой).","en":"Since 2006 — 8 (Pluto became dwarf).","he":"מ-2006 — 8.","ar":"منذ 2006 — 8."}},
    {"q":{"ru":"Какая планета самая горячая?","en":"Which planet is the hottest?","he":"איזה כוכב חם ביותר?","ar":"أي الكواكب أكثر سخونة؟"},
     "options":["Mercury","Venus","Mars","Jupiter"],"answer":1,
     "exp":{"ru":"Венера (+465°C) — парниковый эффект!","en":"Venus (+465°C) — greenhouse effect!","he":"נוגה (+465°C).","ar":"الزهرة (+465°C)."}},
    {"q":{"ru":"Как называется наша галактика?","en":"What is our galaxy called?","he":"מה שם הגלקסיה שלנו?","ar":"ما اسم مجرتنا؟"},
     "options":["Andromeda","Triangulum","Milky Way","Sombrero"],"answer":2,
     "exp":{"ru":"Млечный Путь — 200–400 млрд звёзд.","en":"Milky Way — 200–400 billion stars.","he":"שביל החלב.","ar":"درب التبانة."}},
    {"q":{"ru":"Световой год — это мера...","en":"A light-year measures...","he":"שנת אור מודדת...","ar":"السنة الضوئية تقيس..."},
     "options":["Time/Времени","Distance/Расстояния","Mass/Массы","Speed/Скорости"],"answer":1,
     "exp":{"ru":"Расстояния (~9.46 трлн км). Не время!","en":"Distance (~9.46 trillion km). Not time!","he":"מרחק (~9.46 טריליון ק\"מ).","ar":"مسافة (~9.46 تريليون كم)."}},
    {"q":{"ru":"Кто первым вышел в открытый космос?","en":"Who first walked in space?","he":"מי יצא לחלל ראשון?","ar":"من مشى في الفضاء أولاً؟"},
     "options":["Armstrong","Gagarin","Leonov","Aldrin"],"answer":2,
     "exp":{"ru":"Алексей Леонов, 18 марта 1965 г.","en":"Alexei Leonov, March 18, 1965.","he":"אלכסיי לאונוב, 18 מרץ 1965.","ar":"أليكسي ليونوف، 18 مارس 1965."}},
    {"q":{"ru":"Когда запущен телескоп Джеймс Уэбб?","en":"When was JWST launched?","he":"מתי הושק JWST?","ar":"متى أُطلق JWST؟"},
     "options":["2019","2020","2021","2022"],"answer":2,
     "exp":{"ru":"25 декабря 2021 г. Зеркало 6.5 м.","en":"Dec 25, 2021. Mirror 6.5m.","he":"25 דצמבר 2021.","ar":"25 ديسمبر 2021."}},
    {"q":{"ru":"Сколько летит свет от Солнца до Земли?","en":"How long for sunlight to reach Earth?","he":"כמה זמן ניידהאור?","ar":"كم يستغرق ضوء الشمس؟"},
     "options":["3 min","8 min 20 sec","1 hour","24 hours"],"answer":1,
     "exp":{"ru":"~8 мин 20 сек (150M км ÷ 300 000 км/с).","en":"~8 min 20 sec (150M km ÷ 300,000 km/s).","he":"~8 דקות 20 שניות.","ar":"~8 دقائق و20 ثانية."}},
    {"q":{"ru":"Что в центре Млечного Пути?","en":"What is at the Milky Way center?","he":"מה במרכז שביל החלב?","ar":"ما في مركز درب التبانة؟"},
     "options":["White dwarf","Pulsar","Supermassive black hole","Neutron star"],"answer":2,
     "exp":{"ru":"Стрелец A* — 4 млн масс Солнца.","en":"Sagittarius A* — 4M solar masses.","he":"קשת A* — 4 מיליון שמשות.","ar":"القوس A* — 4 ملايين شمس."}},
    {"q":{"ru":"Самая маленькая планета?","en":"Smallest planet?","he":"הכוכב הקטן ביותר?","ar":"أصغر كوكب؟"},
     "options":["Mars","Venus","Mercury","Pluto"],"answer":2,
     "exp":{"ru":"Меркурий — радиус 2440 км.","en":"Mercury — radius 2,440 km.","he":"מרקורי — 2,440 ק\"מ.","ar":"عطارد — 2,440 كم."}},
    {"q":{"ru":"На каком спутнике Сатурна есть гейзеры?","en":"Which Saturn moon has water geysers?","he":"לאיזה ירח של שבתאי יש גייזרים?","ar":"أي قمر لزحل لديه ينابيع ماء؟"},
     "options":["Titan","Mimas","Enceladus","Rhea"],"answer":2,
     "exp":{"ru":"Энцелад — гейзеры из южного полюса.","en":"Enceladus — geysers from south pole.","he":"אנקלדוס — גייזרים מהקוטב הדרומי.","ar":"إنسيلادوس — ينابيع من القطب الجنوبي."}},
]
# ── End: STATIC DATA ──────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: MOON PHASE & ZODIAC HELPERS                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def get_moon_phase(for_date):
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

def get_zodiac(month, day):
    for (sm, sd), (em, ed), sign in ZODIAC_RANGES:
        if (month == sm and day >= sd) or (month == em and day <= ed): return sign
    return "Aries"
# ── End: MOON PHASE & ZODIAC HELPERS ─────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: IMAGE QUERY CONSTANTS                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
EARTH_Q   = ["earth from space nasa", "earth orbit ISS view", "earth blue marble", "earth from satellite"]
GALLERY_Q = ["nebula", "galaxy", "supernova", "aurora", "saturn rings", "jupiter", "andromeda galaxy"]
MARS_Q    = ["mars surface curiosity", "mars landscape nasa", "mars perseverance"]
ROVER_NAMES = ["curiosity", "perseverance"]
MARS_FACTS = {
    "ru": ["Олимп — 21 км!", "Curiosity проехал >33 км.", "Сутки — 24 ч 37 мин.", "Гравитация 38%."],
    "en": ["Olympus Mons 21km!", "Curiosity >33km.", "Day — 24h 37min.", "Gravity 38%."],
    "he": ["הר אולימפוס 21 ק\"מ.", "קיוריוסיטי >33 ק\"מ.", "יום — 24:37.", "כבידה 38%."],
    "ar": ["أوليمبوس 21 كم.", "كيوريوسيتي >33 كم.", "اليوم 24:37.", "جاذبية 38%."]
}
# ── End: IMAGE QUERY CONSTANTS ────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: STATIC TEXT CONTENT (science/history/deepspace articles)               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
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
    # FIX: mars_colonization was silent when NASA Image API failed;
    # now callback_router falls back to text if image unavailable
    "mars_colonization":{"ru":"🔴 *Марс — Колонизация*\n\nSpaceX, NASA, Китай — планы 2030–2040.\nПроблемы: радиация, гравитация 38%, ресурсы.\nStarship рассчитан на 100 человек.\n\n🔗 [SpaceX Mars](https://www.spacex.com/human-spaceflight/mars/)","en":"🔴 *Mars Colonization*\n\nSpaceX, NASA, China — plans 2030–2040.\nChallenges: radiation, 38% gravity, resources.\nStarship designed for 100 people.\n\n🔗 [SpaceX Mars](https://www.spacex.com/human-spaceflight/mars/)","he":"🔴 *מאדים — קולוניזציה*\n\nSpaceX, NASA, סין — 2030–2040.\nאתגרים: קרינה, כבידה 38%, משאבים.","ar":"🔴 *استعمار المريخ*\n\nSpaceX، ناسا، الصين — 2030–2040.\nتحديات: إشعاع، جاذبية 38٪، موارد."},
    "space_medicine":  {"ru":"🩺 *Медицина*\n\nНевесомость — потеря костной массы.\nЛимит NASA — 600 мЗв.","en":"🩺 *Space Medicine*\n\nMicrogravity — bone loss.\nNASA limit — 600 mSv.","he":"🩺 *רפואה*\n\nאובדן עצם. 600 mSv.","ar":"🩺 *طب*\n\nفقدان العظام. 600 mSv."},
    "astronaut_training":{"ru":"🎓 *Подготовка*\n\nНейтральная плавучесть, центрифуги, тренажёры. Русский/английский для МКС.","en":"🎓 *Training*\n\nNeutral buoyancy, centrifuges, simulators. Russian/English for ISS.","he":"🎓 *אימון*\n\nציפה ניטרלית, צנטריפוגות.","ar":"🎓 *التدريب*\n\nالطفو المحايد، أجهزة الطرد."},
    "debris":          {"ru":"🛰 *Мусор*\n\n~50 000 объектов. Скорость ~7.5 км/с. МКС маневрирует ~3 раза/год.","en":"🛰 *Space Debris*\n\n~50,000 objects. Speed ~7.5 km/s. ISS maneuvers ~3×/year.","he":"🛰 *פסולת*\n\n~50,000 עצמים. 7.5 ק\"מ/ש'.","ar":"🛰 *الحطام*\n\n~50,000 جسم. 7.5 كم/ث."},
    "space_records":   {"ru":"🏆 *Рекорды*\n\n• Поляков — 437 суток (Мир)\n• Кононенко — 1000+ суток (2024)\n• Вояджер-1 — >24 млрд км","en":"🏆 *Records*\n\n• Polyakov — 437 days (Mir)\n• Kononenko — 1000+ days (2024)\n• Voyager-1 — >24B km","he":"🏆 *שיאים*\n\n• פוליאקוב 437 ימים. • Voyager-1 >24 מיליארד ק\"מ.","ar":"🏆 *أرقام*\n\n• بوليكوف 437 يوماً. • Voyager-1 >24 مليار كم."},
    "red_giants":      {"ru":"🔴 *Красные гиганты*\n\nСолнце → гигант через ~5 млрд лет.\nЗвёзды >8 M☉ — сверхновая → нейтронная звезда или ЧД.","en":"🔴 *Red Giants*\n\nSun → red giant in ~5B years.\nStars >8 M☉ → supernova → neutron star or BH.","he":"🔴 *ענקים אדומים*\n\nהשמש → ענק אדום בעוד ~5 מיליארד שנה.","ar":"🔴 *العمالقة الحمراء*\n\nالشمس → عملاق أحمر بعد ~5 مليار سنة."},
    "space_food":      {"ru":"🍽 *Еда в космосе*\n\nСублимированные и термостабилизированные продукты. На МКС >200 блюд. Алкоголь запрещён.","en":"🍽 *Space Food*\n\nFreeze-dried & thermostabilized. ISS has 200+ dishes. Alcohol prohibited.","he":"🍽 *אוכל בחלל*\n\nמזון מיובש בהקפאה. ISS — 200+ מנות.","ar":"🍽 *طعام الفضاء*\n\nجفف بالتجميد. ISS لديه 200+ طبق."},
    "rocket_engines":  {"ru":"🚀 *Двигатели*\n\n• Merlin (SpaceX) — 845 кН\n• RS-25 (NASA SLS) — 2090 кН\n• Raptor 3 (SpaceX) — ~2700 кН","en":"🚀 *Rocket Engines*\n\n• Merlin (SpaceX) — 845 kN\n• RS-25 (NASA SLS) — 2090 kN\n• Raptor 3 (SpaceX) — ~2700 kN","he":"🚀 *מנועים*\n\n• Merlin 845 kN • RS-25 2090 kN","ar":"🚀 *المحركات*\n\n• Merlin 845 kN • RS-25 2090 kN"},
}
# ── End: STATIC TEXT CONTENT ──────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: NASA IMAGE SEARCH HELPER                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def send_nasa_image(q, ctx, queries, cb=""):
    lang = get_lang(ctx)
    try:
        r = requests.get("https://images-api.nasa.gov/search",
            params={"q": random.choice(queries), "media_type": "image", "page_size": 40},
            timeout=12)
        r.raise_for_status()
        items = [it for it in r.json().get("collection", {}).get("items", []) if it.get("links")]
        if not items:
            await safe_edit(q, tx(lang, "no_img"), reply_markup=back_kb(lang, ctx=ctx)); return
        item    = random.choice(items[:25])
        data    = item.get("data", [{}])[0]
        title   = data.get("title", "NASA")
        desc    = strip_html(data.get("description", ""))[:400]
        date_c  = (data.get("date_created") or "")[:10]
        center  = data.get("center", "NASA")
        img_url = (item.get("links", [{}])[0]).get("href", "")
        caption = f"*{title}*\n📅 {date_c}  |  🏛 {center}\n\n{desc + '…' if desc else ''}"
        kb = action_kb(lang, cb, "btn_another", ctx) if cb else back_kb(lang, ctx=ctx)
        await del_msg(q)
        if img_url:
            try:
                await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                    caption=caption[:1024], parse_mode="Markdown", reply_markup=kb)
                return
            except: pass
        await ctx.bot.send_message(chat_id=q.message.chat_id, text=caption[:4096],
            parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang, ctx=ctx))
# ── End: NASA IMAGE SEARCH HELPER ─────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: COMMAND HANDLERS (/start, /menu)                                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(tx("ru", "choose_lang"),
                                    parse_mode="Markdown", reply_markup=lang_kb())

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await update.message.reply_text(tx(lang, "main_menu"),
                                    parse_mode="Markdown", reply_markup=main_menu_kb(lang))

async def choose_lang_h(update, ctx):
    q = update.callback_query; await safe_answer(q)
    await safe_edit(q, tx("ru", "choose_lang"), reply_markup=lang_kb())

async def setlang_h(update, ctx):
    q = update.callback_query; await safe_answer(q)
    lang = q.data.split("_")[1]; ctx.user_data["lang"] = lang
    name = q.from_user.first_name or "explorer"
    await safe_edit(q, tx(lang, "lang_set") + "\n\n" + tx(lang, "start_msg", name=name),
                    reply_markup=main_menu_kb(lang))
# ── End: COMMAND HANDLERS ─────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: APOD HANDLER (Astronomy Picture of the Day)                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def _send_apod(q, ctx, params=None):
    lang = get_lang(ctx)
    try:
        data    = nasa_req("/planetary/apod", params)
        title   = data.get("title", "")
        expl    = strip_html(data.get("explanation", ""))[:900]
        url     = data.get("url", "")
        hdurl   = data.get("hdurl", url)
        mtype   = data.get("media_type", "image")
        d       = data.get("date", "")
        copy_   = data.get("copyright", "NASA").strip().replace("\n", " ")
        caption = f"🌌 *{title}*\n📅 {d}  |  © {copy_}\n\n{expl}…\n\n[🔗 HD]({hdurl})"
        kb = action_kb(lang, "apod_random", "btn_more_rnd", ctx) if not params else back_kb(lang, ctx=ctx)
        await del_msg(q)
        if mtype == "image":
            await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=url,
                caption=caption[:1024], parse_mode="Markdown", reply_markup=kb)
        else:
            await ctx.bot.send_message(chat_id=q.message.chat_id,
                text=caption[:4096] + f"\n\n[▶️]({url})", parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')} APOD: `{e}`", reply_markup=back_kb(lang, ctx=ctx))

async def apod_h(update, ctx):
    q = update.callback_query; await safe_answer(q); await safe_edit(q, "⏳...")
    await _send_apod(q, ctx)

async def apod_random_h(update, ctx):
    q = update.callback_query; await safe_answer(q); await safe_edit(q, "🎲...")
    s   = date(1995, 6, 16)
    rnd = s + timedelta(days=random.randint(0, (date.today() - s).days))
    await _send_apod(q, ctx, {"date": rnd.isoformat()})
# ── End: APOD HANDLER ─────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: MARS PHOTO HANDLER                                                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def mars_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q, "🤖...")
    try:
        photos = []
        for sol in random.sample([100, 200, 300, 500, 750, 1000, 1200, 1500], 4):
            try:
                r = requests.get(f"{NASA_BASE}/mars-photos/api/v1/rovers/curiosity/photos",
                    params={"sol": sol, "api_key": NASA_API_KEY, "page": 1}, timeout=10)
                if r.status_code == 200:
                    photos = r.json().get("photos", [])
                    if photos: break
            except: continue
        if photos:
            p    = random.choice(photos[:20])
            fact = random.choice(MARS_FACTS.get(lang, MARS_FACTS["en"]))
            cap  = (f"🤖 *{p['rover']['name']}*\n📅 {p['earth_date']}  |  Sol {p['sol']}\n"
                    f"📷 {p['camera']['full_name']}\n\n💡 {fact}")
            await del_msg(q)
            await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=p["img_src"],
                caption=cap, parse_mode="Markdown",
                reply_markup=action_kb(lang, "mars", "btn_another", ctx))
            return
    except Exception as e:
        logger.error(f"Mars: {e}")
    await send_nasa_image(q, ctx, MARS_Q, "mars")
# ── End: MARS PHOTO HANDLER ───────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: MARS ROVERS GALLERY HANDLER                                             ║
# FIX: Replaced unreliable random-sol loop with /latest_photos endpoint         ║
# FIX: Added fallback to second rover if first has no photos                    ║
# FIX: Added final fallback to NASA Image Search                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def mars_rovers_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q, "🤖...")
    try:
        rover  = random.choice(ROVER_NAMES)
        photos = []

        # PRIMARY: use latest_photos endpoint — always has data, no guessing sol numbers
        for rv in [rover] + [r for r in ROVER_NAMES if r != rover]:
            try:
                r = requests.get(
                    f"{NASA_BASE}/mars-photos/api/v1/rovers/{rv}/latest_photos",
                    params={"api_key": NASA_API_KEY}, timeout=12
                )
                if r.status_code == 200:
                    photos = r.json().get("latest_photos", [])
                    if photos:
                        rover = rv; break
            except Exception as e:
                logger.warning(f"mars_rovers latest_photos {rv}: {e}")
                continue

        if photos:
            p   = random.choice(photos[:20])
            img = p.get("img_src", "")
            if img:
                cap = (f"🤖 *{p.get('rover', {}).get('name', rover.title())}*\n"
                       f"📅 {p.get('earth_date', '')}  |  Sol {p.get('sol', '')}\n"
                       f"📷 {p.get('camera', {}).get('full_name', '—')}")
                await del_msg(q)
                await ctx.bot.send_photo(
                    chat_id=q.message.chat_id, photo=img, caption=cap,
                    parse_mode="Markdown",
                    reply_markup=action_kb(lang, "mars_rovers", "btn_other_rv", ctx)
                )
                return

        # FALLBACK: NASA image search for Mars rover photos
        logger.warning("mars_rovers_h: no latest_photos — falling back to image search")
        await send_nasa_image(
            q, ctx,
            ["mars rover surface curiosity", "perseverance rover mars", "mars landscape rover"],
            "mars_rovers"
        )
    except Exception as e:
        logger.error(f"mars_rovers_h: {e}")
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang, ctx=ctx))
# ── End: MARS ROVERS GALLERY HANDLER ─────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: ASTEROIDS HANDLER                                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def asteroids_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q, "☄️...")
    try:
        today = date.today().isoformat()
        data  = nasa_req("/neo/rest/v1/feed", {"start_date": today, "end_date": today})
        neos  = data["near_earth_objects"].get(today, [])
        if not neos:
            await safe_edit(q, tx(lang, "no_data"), reply_markup=back_kb(lang, "asteroids", ctx)); return
        danger = sum(1 for a in neos if a["is_potentially_hazardous_asteroid"])
        neos_s = sorted(neos, key=lambda a: float(
            a["close_approach_data"][0]["miss_distance"]["kilometers"])
            if a["close_approach_data"] else 9e99)
        text = f"☄️ *{today}*\n📊 {len(neos)} NEOs  |  ⚠️ {danger}\n\n"
        for i, ast in enumerate(neos_s[:5], 1):
            name  = ast["name"].replace("(", "").replace(")", "").strip()
            d_min = ast["estimated_diameter"]["meters"]["estimated_diameter_min"]
            d_max = ast["estimated_diameter"]["meters"]["estimated_diameter_max"]
            hz    = tx(lang, "hazard_yes") if ast["is_potentially_hazardous_asteroid"] else tx(lang, "hazard_no")
            ap    = ast["close_approach_data"][0] if ast["close_approach_data"] else {}
            speed = ap.get("relative_velocity", {}).get("kilometers_per_hour", "?")
            dist_ld = ap.get("miss_distance", {}).get("lunar", "?")
            try: speed = f"{float(speed):,.0f} km/h"
            except: pass
            try: dist_ld = f"{float(dist_ld):.2f} LD"
            except: pass
            text += f"*{i}. {name}*  {hz}\n📏 {d_min:.0f}–{d_max:.0f}m  🚀 {speed}  📍 {dist_ld}\n\n"
        text += "[🔗 NASA CNEOS](https://cneos.jpl.nasa.gov)"
        ast_imgs = ["asteroid close up nasa dawn", "asteroid bennu osiris rex nasa",
                    "asteroid ryugu hayabusa", "near earth asteroid space"]
        try:
            ri = requests.get("https://images-api.nasa.gov/search",
                params={"q": random.choice(ast_imgs), "media_type": "image", "page_size": 20}, timeout=10)
            items = [it for it in ri.json().get("collection", {}).get("items", []) if it.get("links")]
            if items:
                img_url = (random.choice(items[:15]).get("links", [{}])[0]).get("href", "")
                if img_url:
                    await del_msg(q)
                    await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                        caption=text[:1024], parse_mode="Markdown",
                        reply_markup=back_kb(lang, "asteroids", ctx))
                    return
        except: pass
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang, "asteroids", ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang, ctx=ctx))
# ── End: ASTEROIDS HANDLER ────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: ISS HANDLER                                                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def iss_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q, "🛸...")
    try:
        pos  = get_iss_position()
        lat, lon, ts = pos["lat"], pos["lon"], pos["ts"]
        iss_crew = get_iss_crew()
        crew_str = "\n".join(f"   👨‍🚀 {n}" for n in iss_crew) or f"   {tx(lang,'iss_no_crew')}"
        text = (f"🛸 *ISS — {ts}*\n\n🌍 `{lat:.4f}°` | 🌏 `{lon:.4f}°`\n"
                f"⚡ ~27,600 km/h  |  🏔 ~408 km\n\n👨‍🚀 Crew ({len(iss_crew)}):\n{crew_str}\n\n"
                f"[{tx(lang,'iss_map')}](https://www.google.com/maps?q={lat},{lon})")
        iss_images = ["ISS international space station orbit", "ISS from earth telescope",
                      "space station earth view"]
        try:
            r = requests.get("https://images-api.nasa.gov/search",
                params={"q": random.choice(iss_images), "media_type": "image", "page_size": 20},
                timeout=12)
            items = [it for it in r.json().get("collection", {}).get("items", []) if it.get("links")]
            if items:
                img_url = (random.choice(items[:15]).get("links", [{}])[0]).get("href", "")
                if img_url:
                    await del_msg(q)
                    await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                        caption=text[:1024], parse_mode="Markdown",
                        reply_markup=back_kb(lang, "iss", ctx))
                    return
        except: pass
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang, "iss", ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')} ISS: `{e}`", reply_markup=back_kb(lang, ctx=ctx))
# ── End: ISS HANDLER ──────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: EXOPLANETS HANDLER                                                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def exoplanets_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    sel  = random.sample(KNOWN_EXOPLANETS, min(4, len(KNOWN_EXOPLANETS)))
    text = "🔭 *Exoplanets*\n\n"
    for p in sel:
        note = p["note"].get(lang, p["note"]["en"])
        text += (f"🪐 *{p['name']}* — {p['star']}\n"
                 f"   📅 {p['year']}  |  📏 {p['radius']}R🌍  |  🔄 {p['period']}d  |  📡 {p['dist_ly']}ly\n"
                 f"   💡 _{note}_\n\n")
    text += "[🔗 NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu)"
    exo_imgs = ["exoplanet artist concept nasa", "TRAPPIST-1 system nasa",
                "Kepler exoplanet nasa", "habitable zone planet artist",
                "James Webb exoplanet atmosphere"]
    try:
        r = requests.get("https://images-api.nasa.gov/search",
            params={"q": random.choice(exo_imgs), "media_type": "image", "page_size": 20}, timeout=12)
        items = [it for it in r.json().get("collection", {}).get("items", []) if it.get("links")]
        if items:
            img_url = (random.choice(items[:15]).get("links", [{}])[0]).get("href", "")
            if img_url:
                await del_msg(q)
                await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                    caption=text[:1024], parse_mode="Markdown",
                    reply_markup=back_kb(lang, "exoplanets", ctx))
                return
    except: pass
    await safe_edit(q, text[:4096], reply_markup=back_kb(lang, "exoplanets", ctx))
# ── End: EXOPLANETS HANDLER ───────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: SPACE WEATHER HANDLER                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def spaceweather_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q, "🌞...")
    try:
        kp_val, kp_time, kp_state = "?", "?", "?"
        try:
            r = requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json", timeout=10)
            r.raise_for_status()
            kp_data = r.json(); cur = kp_data[-1] if kp_data else {}
            kp_val  = cur.get("kp_index", cur.get("Kp", "?"))
            kp_time = cur.get("time_tag", "")[:16].replace("T", " ")
            try:
                kv = float(kp_val)
                kp_state = ("🟢 Calm" if kv<4 else "🟡 Minor" if kv<5 else "🟠 Moderate" if kv<6
                             else "🔴 Strong" if kv<8 else "🚨 Extreme")
            except: kp_state = "?"
        except: pass
        sw_speed, sw_density = "?", "?"
        try:
            r2 = requests.get("https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json", timeout=10)
            r2.raise_for_status()
            sw_data = r2.json(); sw_lat = sw_data[-1] if sw_data else []
            if len(sw_lat) > 2:
                try: sw_speed   = f"{float(sw_lat[2]):,.0f} km/s"
                except: sw_speed   = str(sw_lat[2])
                try: sw_density = f"{float(sw_lat[1]):.2f} p/cm3"
                except: sw_density = str(sw_lat[1])
        except: pass
        flare_cls, flare_flux = "?", "?"
        try:
            r3 = requests.get("https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json", timeout=10)
            r3.raise_for_status()
            xray = r3.json(); xl = xray[-1] if xray else {}; flux = xl.get("flux", "?")
            try:
                fv = float(flux)
                flare_cls  = ("X-class" if fv>=1e-4 else "M-class" if fv>=1e-5
                               else "C-class" if fv>=1e-6 else "B-class" if fv>=1e-7 else "A-class")
                flare_flux = f"{fv:.2e} W/m2"
            except: flare_cls = "?"; flare_flux = str(flux)
        except: pass
        ssn = "?"
        try:
            r4 = requests.get("https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json", timeout=10)
            r4.raise_for_status(); sc = r4.json()
            ssn = sc[-1].get("smoothed_ssn", sc[-1].get("ssn", "?")) if sc else "?"
        except: pass
        try:
            aurora_vis = ("Equatorial" if float(str(kp_val))>=8 else "Mid-latitudes" if float(str(kp_val))>=6
                          else "Scandinavia/Canada" if float(str(kp_val))>=4 else "Polar only")
        except: aurora_vis = "Polar only"
        text = (f"*Space Weather — Live*\n"
                f"*Kp-index:* {kp_val} {kp_state}\n"
                f"*Solar Wind:* {sw_speed} | {sw_density}\n"
                f"*Flare class:* {flare_cls} ({flare_flux})\n"
                f"*Sunspot #:* {ssn}\n\n"
                f"Aurora: {aurora_vis}\n\n"
                f"[NOAA SWPC](https://www.swpc.noaa.gov)")
        try:
            sun_url = "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0193.jpg"
            await del_msg(q)
            await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=sun_url,
                caption=text[:1024], parse_mode="Markdown",
                reply_markup=back_kb(lang, "spaceweather", ctx))
            return
        except: pass
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang, "spaceweather", ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang, ctx=ctx))
# ── End: SPACE WEATHER HANDLER ────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: LAUNCHES HANDLER                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def launches_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q, "🚀...")
    try:
        launches = cache_get("launches")
        if not launches:
            data = get_json("https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=7&ordering=net&mode=list", timeout=15)
            launches = data.get("results", [])
            if launches: cache_set("launches", launches)
        if not launches:
            await safe_edit(q, tx(lang, "no_data"), reply_markup=back_kb(lang, ctx=ctx)); return
        text = "🚀 *Upcoming Launches*\n\n"
        for i, lc in enumerate(launches[:6], 1):
            if not isinstance(lc, dict): continue
            try:
                name   = str(lc.get("name", "?"))
                rocket = str((lc.get("rocket") or {}).get("configuration", {}).get("name", "?"))
                prov   = str((lc.get("launch_service_provider") or {}).get("name", "?"))
                net    = str(lc.get("net", "?"))
                stat_a = str((lc.get("status") or {}).get("abbrev", "?"))
                emoji  = {"Go":"✅","TBD":"❓","TBC":"🔸","Success":"🎉","Failure":"❌"}.get(stat_a, "🕐")
                try:
                    dt  = datetime.fromisoformat(net.replace("Z", "+00:00"))
                    net = dt.strftime("%d.%m.%Y %H:%M UTC")
                except: pass
                text += f"*{i}. {name}*\n   🚀 {rocket}  |  {prov}\n   ⏰ {net}  {emoji}\n\n"
            except: continue
        launch_imgs = ["rocket launch nasa", "SpaceX falcon launch pad", "rocket liftoff pad exhaust",
                       "space launch vehicle liftoff", "falcon 9 launch"]
        try:
            ri = requests.get("https://images-api.nasa.gov/search",
                params={"q": random.choice(launch_imgs), "media_type": "image", "page_size": 20}, timeout=10)
            items = [it for it in ri.json().get("collection", {}).get("items", []) if it.get("links")]
            if items:
                img_url = (random.choice(items[:15]).get("links", [{}])[0]).get("href", "")
                if img_url:
                    await del_msg(q)
                    await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                        caption=text[:1024], parse_mode="Markdown",
                        reply_markup=back_kb(lang, "launches", ctx))
                    return
        except: pass
        await safe_edit(q, text[:4096], reply_markup=back_kb(lang, "launches", ctx))
    except Exception as e:
        await safe_edit(q, f"{tx(lang,'err')}: `{e}`", reply_markup=back_kb(lang, ctx=ctx))
# ── End: LAUNCHES HANDLER ─────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: SATELLITES HANDLER                                                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def satellites_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx); await safe_edit(q, "📡...")
    cached = cache_get("starlink")
    if cached:
        total, active = cached
    else:
        try:
            sl     = get_json("https://api.spacexdata.com/v4/starlink", timeout=12)
            total  = len(sl)
            active = sum(1 for s in sl if isinstance(s, dict) and
                         not (s.get("spaceTrack") or {}).get("DECAY_DATE"))
            cache_set("starlink", (total, active))
        except: total = active = "?"
    text = (f"📡 *Satellites in Orbit*\n\n"
            f"🌍 Total tracked: ~9,000+\n"
            f"🛸 *Starlink:* {total} total, {active} active\n"
            f"🔭 *Other constellations:* OneWeb, GPS, Galileo, GLONASS\n\n"
            f"[🔗 n2yo.com — live tracking](https://www.n2yo.com)")
    sat_imgs = ["satellite orbit earth nasa", "starlink constellation night sky",
                "GPS satellite earth orbit", "communication satellite deployment space"]
    try:
        ri = requests.get("https://images-api.nasa.gov/search",
            params={"q": random.choice(sat_imgs), "media_type": "image", "page_size": 20}, timeout=10)
        items = [it for it in ri.json().get("collection", {}).get("items", []) if it.get("links")]
        if items:
            img_url = (random.choice(items[:15]).get("links", [{}])[0]).get("href", "")
            if img_url:
                await del_msg(q)
                await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                    caption=text[:1024], parse_mode="Markdown",
                    reply_markup=back_kb(lang, "satellites", ctx))
                return
    except: pass
    await safe_edit(q, text, reply_markup=back_kb(lang, "satellites", ctx))
# ── End: SATELLITES HANDLER ───────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: METEORS HANDLER                                                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def meteors_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    text = "🌠 *Meteor Showers*\n\n"
    for m in METEOR_SHOWERS:
        name = m["name"].get(lang, m["name"]["en"])
        text += f"✨ *{name}* — {m['peak']}\n   ⚡ {m['speed']}  |  🌠 {m['rate']}  |  {m['parent']}\n\n"
    text += "[🔗 AMS Meteor Calendar](https://www.amsmeteors.org/meteor-showers/meteor-shower-calendar/)"
    meteor_imgs = ["meteor shower long exposure night sky", "perseid meteor shower",
                   "shooting star night sky nasa", "leonids meteor shower", "geminids fireball"]
    try:
        r = requests.get("https://images-api.nasa.gov/search",
            params={"q": random.choice(meteor_imgs), "media_type": "image", "page_size": 20}, timeout=12)
        items = [it for it in r.json().get("collection", {}).get("items", []) if it.get("links")]
        if items:
            img_url = (random.choice(items[:15]).get("links", [{}])[0]).get("href", "")
            if img_url:
                await del_msg(q)
                await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                    caption=text[:1024], parse_mode="Markdown",
                    reply_markup=back_kb(lang, ctx=ctx))
                return
    except: pass
    await safe_edit(q, text, reply_markup=back_kb(lang, ctx=ctx))
# ── End: METEORS HANDLER ──────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: PLANETS HANDLER                                                         ║
# FIX: Added text fallback when NASA Image API fails                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def planets_h(update, ctx):
    q    = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    p    = random.choice(PLANETS)
    fact = p["fact"].get(lang, p["fact"]["en"])
    text = (f"*{p['name']}*\n\n📏 {p['radius']}  |  📡 {p['dist']}\n"
            f"🔄 {p['period']}  |  🌅 {p['day']}\n🌡 {p['temp']}  |  🌙 {p['moons']}\n\n💡 {fact}")
    planet_queries = {
        "☿ Mercury": ["mercury planet nasa messenger spacecraft"],
        "♀ Venus":   ["venus planet nasa surface mariner"],
        "🌍 Earth":  ["earth from space nasa blue marble"],
        "♂ Mars":    ["mars planet nasa surface red"],
        "♃ Jupiter": ["jupiter great red spot nasa cassini"],
        "♄ Saturn":  ["saturn rings cassini nasa planet"],
        "⛢ Uranus":  ["uranus planet voyager nasa rings"],
        "♆ Neptune": ["neptune planet voyager nasa blue"],
    }
    queries = planet_queries.get(p["name"], ["solar system planet nasa"])
    try:
        r = requests.get("https://images-api.nasa.gov/search",
            params={"q": random.choice(queries), "media_type": "image", "page_size": 20}, timeout=12)
        items = [it for it in r.json().get("collection", {}).get("items", []) if it.get("links")]
        if items:
            img_url = (random.choice(items[:15]).get("links", [{}])[0]).get("href", "")
            if img_url:
                await del_msg(q)
                await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                    caption=text[:1024], parse_mode="Markdown",
                    reply_markup=action_kb(lang, "planets", "btn_another", ctx))
                return
    except Exception as e:
        logger.warning(f"planets_h image: {e}")
    # FIX: Always show text even when image fails
    await safe_edit(q, text, reply_markup=action_kb(lang, "planets", "btn_another", ctx))
# ── End: PLANETS HANDLER ──────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: MOON HANDLER                                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def moon_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    emoji, idx, cycle_day, illum = get_moon_phase(date.today())
    phases     = tx(lang, "moon_phases")
    phase_name = phases[idx] if isinstance(phases, list) else "?"
    text = (f"{emoji} *Moon Phase — {date.today()}*\n\n🌙 *{phase_name}*\n"
            f"💡 ~{illum}%  |  Day {cycle_day:.1f}/29.5\n\n"
            f"📸 Photo tip: ISO 100, f/11, 1/250s")
    moon_images = ["moon surface nasa apollo", "lunar crater full moon",
                   "moon high resolution nasa", "moon from space ISS", "lunar surface close up"]
    try:
        r = requests.get("https://images-api.nasa.gov/search",
            params={"q": random.choice(moon_images), "media_type": "image", "page_size": 20}, timeout=12)
        items = [it for it in r.json().get("collection", {}).get("items", []) if it.get("links")]
        if items:
            img_url = (random.choice(items[:15]).get("links", [{}])[0]).get("href", "")
            if img_url:
                await del_msg(q)
                await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                    caption=text[:1024], parse_mode="Markdown",
                    reply_markup=back_kb(lang, "moon", ctx))
                return
    except: pass
    await safe_edit(q, text, reply_markup=back_kb(lang, "moon", ctx))
# ── End: MOON HANDLER ─────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: TELESCOPES HANDLER                                                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def telescopes_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    text = ("🔬 *Space Telescopes*\n\n"
            "🌌 *JWST* — mirror 6.5m, orbit L2, infrared\n"
            "🔭 *Hubble* — mirror 2.4m, optical/UV, 600km orbit\n"
            "📡 *Chandra* — X-ray, high elliptical orbit\n"
            "🌊 *XMM-Newton* — X-ray, ESA\n"
            "🔭 *Spitzer* — infrared (retired 2020)\n"
            "📡 *VLT* — 4×8.2m, Atacama\n"
            "🌐 *FAST* — 500m radio dish, China\n"
            "🔭 *ELT (~2028)* — 39m mirror, ESA\n"
            "🌌 *Roman (~2027)* — wide-field infrared, NASA")
    tel_imgs = ["James Webb Space Telescope NASA", "Hubble Space Telescope orbit",
                "Chandra X-ray telescope", "very large telescope ESO",
                "telescope mirror primary hexagonal", "space observatory nasa"]
    try:
        ri = requests.get("https://images-api.nasa.gov/search",
            params={"q": random.choice(tel_imgs), "media_type": "image", "page_size": 20}, timeout=10)
        items = [it for it in ri.json().get("collection", {}).get("items", []) if it.get("links")]
        if items:
            img_url = (random.choice(items[:15]).get("links", [{}])[0]).get("href", "")
            if img_url:
                await del_msg(q)
                await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                    caption=text[:1024], parse_mode="Markdown",
                    reply_markup=back_kb(lang, ctx=ctx))
                return
    except: pass
    await safe_edit(q, text, reply_markup=back_kb(lang, ctx=ctx))
# ── End: TELESCOPES HANDLER ───────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: SPACE FACT & CHANNELS HANDLERS                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def spacefact_h(update, ctx):
    q    = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    fact = random.choice(SPACE_FACTS.get(lang, SPACE_FACTS["en"]))
    text = f"⭐ *Space Fact*\n\n{fact}"
    fact_imgs = ["space stars galaxy nasa", "universe deep field", "cosmos stars milky way",
                 "nebula colorful nasa hubble", "star formation space", "galaxy spiral nasa"]
    try:
        ri = requests.get("https://images-api.nasa.gov/search",
            params={"q": random.choice(fact_imgs), "media_type": "image", "page_size": 20}, timeout=10)
        items = [it for it in ri.json().get("collection", {}).get("items", []) if it.get("links")]
        if items:
            img_url = (random.choice(items[:15]).get("links", [{}])[0]).get("href", "")
            if img_url:
                await del_msg(q)
                await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url,
                    caption=text[:1024], parse_mode="Markdown",
                    reply_markup=back_kb(lang, "spacefact", ctx))
                return
    except: pass
    await safe_edit(q, text, reply_markup=back_kb(lang, "spacefact", ctx))

async def channels_h(update, ctx):
    q = update.callback_query; await safe_answer(q); lang = get_lang(ctx)
    await safe_edit(q, CHANNELS_TEXT.get(lang, CHANNELS_TEXT["ru"]),
                    reply_markup=back_kb(lang, ctx=ctx))
# ── End: SPACE FACT & CHANNELS HANDLERS ──────────────────────────────────────

# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: LIVE HANDLERS (solar wind, Kp, flares, ISS live, radiation, aurora,   ║
#        geomagnetic, sunspot, EPIC, satellite count)                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def live_solar_wind_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        r=requests.get("https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json",timeout=12); r.raise_for_status()
        data=r.json(); latest=data[-1] if data else {}
        speed=latest[2] if len(latest)>2 else "?"; density=latest[1] if len(latest)>1 else "?"
        time_str=str(latest[0])[:16].replace("T"," ") if latest else "?"
        try: spd_f=float(speed); status="🟢 Calm" if spd_f<400 else "🟡 Moderate" if spd_f<600 else "🟠 Strong" if spd_f<800 else "🔴 STORM"
        except: status="?"
        try: speed=f"{float(speed):,.0f} km/s"
        except: pass
        try: density=f"{float(density):.2f} p/cm³"
        except: pass
        await safe_edit(q,f"🔴 *LIVE: Solar Wind*\n⏱ {time_str} UTC\n\n{status}\n🚀 {speed}  |  🔵 {density}\n\n[NOAA](https://www.swpc.noaa.gov)",
            reply_markup=back_kb(lang,"live_solar_wind",ctx))
    except Exception as e:
        await safe_edit(q,f"{tx(lang,'err')}: `{e}`",reply_markup=back_kb(lang,ctx=ctx))

async def live_kp_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        r=requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",timeout=12); r.raise_for_status()
        data=r.json(); current=data[-1] if data else {}
        kp_now=current.get("kp_index",current.get("Kp","?")); time_=current.get("time_tag","")[:16].replace("T"," ")
        try:
            kp_val=float(kp_now)
            state="🟢 Quiet" if kp_val<4 else "🟡 Minor" if kp_val<5 else "🟠 Moderate" if kp_val<6 else "🔴 Strong" if kp_val<8 else "🚨 G5"
            aurora="Polar only" if kp_val<4 else "Scandinavia/Canada" if kp_val<6 else "Mid-latitudes" if kp_val<8 else "Equatorial"
        except: state=aurora="?"
        await safe_edit(q,f"🔴 *LIVE: Kp-index*\n⏱ {time_} UTC\n\nKp: *{kp_now}*  |  {state}\n🌈 Aurora: {aurora}",
            reply_markup=back_kb(lang,"live_kp",ctx))
    except Exception as e:
        await safe_edit(q,f"{tx(lang,'err')}: `{e}`",reply_markup=back_kb(lang,ctx=ctx))

async def live_flares_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        r=requests.get("https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json",timeout=12); r.raise_for_status()
        xray=r.json(); latest=xray[-1] if xray else {}
        flux=latest.get("flux","?"); time_=latest.get("time_tag","")[:16].replace("T"," ")
        try:
            fv=float(flux)
            cls_="🔴 X" if fv>=1e-4 else "🟠 M" if fv>=1e-5 else "🟡 C" if fv>=1e-6 else "🟢 B" if fv>=1e-7 else "⚪ A"
            fs=f"{fv:.2e} W/m²"
        except: cls_="?"; fs=str(flux)
        await safe_edit(q,f"🔴 *LIVE: Solar Flares*\n⏱ {time_} UTC\n\n⚡ *{cls_}* — `{fs}`",
            reply_markup=back_kb(lang,"live_flares",ctx))
    except Exception as e:
        await safe_edit(q,f"{tx(lang,'err')}: `{e}`",reply_markup=back_kb(lang,ctx=ctx))

async def live_iss_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        pos=get_iss_position()
        lat,lon,ts=pos["lat"],pos["lon"],pos["ts"]
        iss_c=get_iss_crew()
        text=(f"🔴 *LIVE: ISS*\n⏱ {ts}\n\n🌍 `{lat:+.4f}°` | 🌏 `{lon:+.4f}°`\n"
              f"⚡ ~27,576 km/h  |  ~408 km\n👨‍🚀 {', '.join(iss_c) or tx(lang,'iss_no_crew')}\n\n"
              f"[{tx(lang,'iss_map')}](https://www.google.com/maps?q={lat},{lon})")
        await safe_edit(q,text,reply_markup=back_kb(lang,"live_iss",ctx))
    except Exception as e:
        await safe_edit(q,f"{tx(lang,'err')}: `{e}`",reply_markup=back_kb(lang,ctx=ctx))

async def live_radiation_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        r=requests.get("https://services.swpc.noaa.gov/json/goes/primary/integral-protons-6-hour.json",timeout=12); r.raise_for_status()
        protons=r.json(); latest=protons[-1] if protons else {}
        flux_p=latest.get("flux","?"); time_p=latest.get("time_tag","")[:16].replace("T"," ")
        try:
            fp=float(flux_p)
            rl="🚨 S5" if fp>=1e4 else "🔴 S4" if fp>=1e3 else "🟠 S3" if fp>=1e2 else "🟡 S2" if fp>=10 else "🟢 S1" if fp>=1 else "⚪ BG"
            fs=f"{fp:.2e} p/(cm²·s·sr)"
        except: rl="?"; fs=str(flux_p)
        await safe_edit(q,f"🔴 *LIVE: Radiation*\n⏱ {time_p} UTC\n\n☢️ `{fs}`\n🌡 *{rl}*",
            reply_markup=back_kb(lang,"live_radiation",ctx))
    except Exception as e:
        await safe_edit(q,f"{tx(lang,'err')}: `{e}`",reply_markup=back_kb(lang,ctx=ctx))

async def live_aurora_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        r=requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",timeout=12); r.raise_for_status()
        data=r.json(); current=data[-1] if data else {}
        kp=current.get("kp_index",current.get("Kp","?")); time_=current.get("time_tag","")[:16].replace("T"," ")
        try:
            kp_val=float(kp)
            forecast=("🌈 Mid-latitudes (Moscow, Kyiv)" if kp_val>=7 else "🌈 Scandinavia, Canada, Alaska" if kp_val>=5 else "🌈 Near polar circle" if kp_val>=4 else "🌈 Polar regions only")
        except: forecast="?"
        await safe_edit(q,f"🔴 *Aurora Forecast*\n⏱ {time_} UTC\n\nKp: *{kp}*\n{forecast}",
            reply_markup=back_kb(lang,"live_aurora_forecast",ctx))
    except Exception as e:
        await safe_edit(q,f"{tx(lang,'err')}: `{e}`",reply_markup=back_kb(lang,ctx=ctx))

async def live_geomag_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        end=date.today().isoformat(); start=(date.today()-timedelta(days=2)).isoformat()
        storms=nasa_req("/DONKI/GST",{"startDate":start,"endDate":end}) or []
        text=f"🔴 *Geomagnetic Storms (2d)*\n\nEvents: *{len(storms)}*\n\n"
        for s in (storms[-5:] if storms else []):
            t=(s.get("startTime") or "?")[:16].replace("T"," ")
            kp_i=s.get("allKpIndex",[{}]); kp_v=kp_i[-1].get("kpIndex","?") if kp_i else "?"
            text+=f"• {t} UTC  Kp *{kp_v}*\n"
        if not storms: text+=tx(lang,"live_nodata")
        await safe_edit(q,text[:4096],reply_markup=back_kb(lang,"live_geomagnetic_alert",ctx))
    except Exception as e:
        await safe_edit(q,f"{tx(lang,'err')}: `{e}`",reply_markup=back_kb(lang,ctx=ctx))

async def live_sunspot_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        r=requests.get("https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json",timeout=12); r.raise_for_status()
        data=r.json(); latest=data[-1] if data else {}; ssn=latest.get("smoothed_ssn",latest.get("ssn","?"))
        await safe_edit(q,f"🔴 *Sunspots (Cycle 25)*\n\nWolf number: *{ssn}*\n\nCycle 25 near maximum — more flares.",
            reply_markup=back_kb(lang,"live_sunspot",ctx))
    except Exception as e:
        await safe_edit(q,f"{tx(lang,'err')}: `{e}`",reply_markup=back_kb(lang,ctx=ctx))

async def live_epic_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        data=nasa_req("/EPIC/api/natural")
        if not data:
            await safe_edit(q,tx(lang,"no_img"),reply_markup=back_kb(lang,ctx=ctx)); return
        item=data[0]; date_str=item.get("date","")[:10].replace("-","/"); img=item.get("image","")
        url=f"https://epic.gsfc.nasa.gov/archive/natural/{date_str}/png/{img}.png"
        caption=f"🌍 *EPIC Live — Earth*\n📅 {date_str}\n\nDSCOVR satellite (L1)."
        await del_msg(q)
        try:
            await ctx.bot.send_photo(chat_id=q.message.chat_id,photo=url,caption=caption,
                parse_mode="Markdown",reply_markup=back_kb(lang,"live_epic_latest",ctx))
        except:
            await ctx.bot.send_message(chat_id=q.message.chat_id,text=caption+f"\n\n[Open]({url})",
                parse_mode="Markdown",reply_markup=back_kb(lang,ctx=ctx),disable_web_page_preview=True)
    except Exception as e:
        await safe_edit(q,tx(lang,"no_img"),reply_markup=back_kb(lang,ctx=ctx))

async def live_sat_count_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        sl=get_json("https://api.spacexdata.com/v4/starlink",timeout=10)
        total=len(sl); active=sum(1 for s in sl if isinstance(s,dict) and not (s.get("spaceTrack") or {}).get("DECAY_DATE"))
    except: total=active="?"
    await safe_edit(q,f"🔴 *Starlink*\n\nTotal: *{total}*  |  Active: *{active}*\n\nAll satellites: ~9,000+ in orbit.",
        reply_markup=back_kb(lang,"live_satellite_count",ctx))
# ── End: LIVE HANDLERS ────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: NOTIFICATIONS HANDLERS (menu + toggle)                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def notifications_menu_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    subs=load_subscribers(); chat_id=q.message.chat_id
    await safe_edit(q,tx(lang,"notif_title"),reply_markup=notifications_kb(lang,subs,chat_id))

async def notif_toggle_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    topic=q.data.replace("notif_toggle_",""); chat_id=q.message.chat_id
    subs=load_subscribers()
    if topic not in subs: subs[topic]=[]
    if chat_id in subs[topic]:
        subs[topic].remove(chat_id); msg=tx(lang,"notif_unsubscribed")
    else:
        subs[topic].append(chat_id); msg=tx(lang,"notif_subscribed")
    save_subscribers(subs)
    try: await q.answer(msg,show_alert=False)
    except: pass
    await safe_edit(q,tx(lang,"notif_title"),reply_markup=notifications_kb(lang,subs,chat_id))
# ── End: NOTIFICATIONS HANDLERS ──────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: CONVERSATION HANDLER — Planet Calculator                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def planet_calc_start(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    ctx.user_data["planet_calc_lang"]=lang
    await del_msg(q)
    await ctx.bot.send_message(chat_id=q.message.chat_id,text=tx(lang,"planet_calc_ask_date"),parse_mode="Markdown")
    return PLANET_DATE

async def planet_date_received(update, ctx):
    lang=ctx.user_data.get("planet_calc_lang","ru")
    try:
        bday=datetime.strptime(update.message.text.strip(),"%d.%m.%Y").date()
        if bday>date.today() or bday.year<1900: raise ValueError
        ctx.user_data["planet_bday"]=bday
        await update.message.reply_text(tx(lang,"planet_calc_ask_weight"),parse_mode="Markdown")
        return PLANET_WEIGHT
    except:
        await update.message.reply_text(tx(lang,"planet_calc_error_date"),parse_mode="Markdown")
        return PLANET_DATE

async def planet_weight_received(update, ctx):
    lang=ctx.user_data.get("planet_calc_lang","ru")
    try:
        weight=float(update.message.text.strip().replace(",","."))
        if not (1<=weight<=500): raise ValueError
    except:
        await update.message.reply_text(tx(lang,"planet_calc_error_weight"),parse_mode="Markdown")
        return PLANET_WEIGHT
    bday=ctx.user_data.get("planet_bday"); today=date.today()
    age_days=(today-bday).days
    lines=["🪐 *Planet Calculator*\n"]
    lines.append(f"🌍 *Earth:* {age_days/365.25:.1f} yrs  |  {weight:.1f} kg\n")
    for pname,gravity in PLANET_GRAVITY.items():
        if pname=="🌍 Earth": continue
        age_p=age_days/PLANET_YEAR_DAYS[pname]; w_p=weight*gravity
        lines.append(f"{pname}: *{age_p:.1f} yrs*  |  ⚖️ *{w_p:.1f} kg*")
    lines.append(f"\n🌙 *Moon:* ⚖️ {weight*0.165:.1f} kg (16.5% gravity)")
    lines.append(f"\n💡 You've lived *{age_days:,}* Earth days!")
    kb=InlineKeyboardMarkup([[
        InlineKeyboardButton(tx(lang,"cat_interact_btn"),callback_data="cat_interact"),
        InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")
    ]])
    await update.message.reply_text("\n".join(lines)[:4096],parse_mode="Markdown",reply_markup=kb)
    return ConversationHandler.END

async def planet_calc_cancel(update, ctx):
    lang=ctx.user_data.get("planet_calc_lang","ru")
    await update.message.reply_text(tx(lang,"capsule_cancel")); return ConversationHandler.END
# ── End: CONVERSATION HANDLER — Planet Calculator ─────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: CONVERSATION HANDLER — Horoscope                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def horoscope_menu_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    ctx.user_data["horoscope_lang"]=lang
    await del_msg(q)
    await ctx.bot.send_message(chat_id=q.message.chat_id,text=tx(lang,"horoscope_ask"),parse_mode="Markdown")
    return HOROSCOPE_BDAY

async def horoscope_date_received(update, ctx):
    lang=ctx.user_data.get("horoscope_lang","ru")
    try:
        parts=update.message.text.strip().split(".")
        if len(parts)<2: raise ValueError
        day,month=int(parts[0]),int(parts[1])
        if not (1<=day<=31 and 1<=month<=12): raise ValueError
    except:
        await update.message.reply_text(tx(lang,"horoscope_error"),parse_mode="Markdown")
        return HOROSCOPE_BDAY
    sign=get_zodiac(month,day)
    horoscopes=HOROSCOPES.get(lang,HOROSCOPES["en"])
    horoscope=horoscopes.get(sign,horoscopes.get("Aries",""))
    kb=InlineKeyboardMarkup([[
        InlineKeyboardButton(tx(lang,"cat_interact_btn"),callback_data="cat_interact"),
        InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")
    ]])
    await update.message.reply_text(horoscope,parse_mode="Markdown",reply_markup=kb)
    return ConversationHandler.END

async def horoscope_cancel(update, ctx):
    lang=ctx.user_data.get("horoscope_lang","ru")
    await update.message.reply_text(tx(lang,"capsule_cancel"))
    return ConversationHandler.END
# ── End: CONVERSATION HANDLER — Horoscope ─────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: CONVERSATION HANDLER — Time Capsule                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def capsule_menu_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    ctx.user_data["capsule_lang"]=lang
    await del_msg(q)
    await ctx.bot.send_message(chat_id=q.message.chat_id,text=tx(lang,"capsule_ask"),parse_mode="Markdown")
    return CAPSULE_MSG

async def capsule_msg_received(update, ctx):
    lang=ctx.user_data.get("capsule_lang","ru")
    user_msg=update.message.text.strip()
    if len(user_msg)<5 or len(user_msg)>2000:
        await update.message.reply_text("❌ 5–2000 chars"); return CAPSULE_MSG
    deliver_on=(date.today()+timedelta(days=365)).isoformat()
    capsules=load_capsules()
    capsules.append({"chat_id":update.effective_chat.id,"message":user_msg,"deliver_on":deliver_on,"created_at":date.today().isoformat()})
    save_capsules(capsules)
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Menu",callback_data="back")]])
    await update.message.reply_text(tx(lang,"capsule_saved",date=deliver_on),parse_mode="Markdown",reply_markup=kb)
    return ConversationHandler.END

async def capsule_cancel(update, ctx):
    lang=ctx.user_data.get("capsule_lang","ru")
    await update.message.reply_text(tx(lang,"capsule_cancel"))
    return ConversationHandler.END
# ── End: CONVERSATION HANDLER — Time Capsule ──────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: QUIZ HANDLERS                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def quiz_start_menu_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    ctx.user_data["quiz_score"]=0; ctx.user_data["quiz_q"]=0; ctx.user_data["quiz_answered"]=False
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"quiz_btn_start"),callback_data="quiz_next")]])
    await safe_edit(q,tx(lang,"quiz_start"),reply_markup=kb)

async def quiz_next_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    qi=ctx.user_data.get("quiz_q",0)
    if qi>=10: await quiz_finish_h(update,ctx); return
    question=QUIZ_QUESTIONS[qi]
    q_text=question["q"].get(lang,question["q"]["en"])
    opts_txt="\n".join(f"{chr(65+i)}. {opt}" for i,opt in enumerate(question["options"]))
    ctx.user_data["quiz_answered"]=False
    await safe_edit(q,f"🧠 *Question {qi+1}/10*\n\n{q_text}\n\n{opts_txt}",reply_markup=quiz_kb(lang,qi))

async def quiz_answer_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    if ctx.user_data.get("quiz_answered",False): return
    ctx.user_data["quiz_answered"]=True
    parts=q.data.split("_"); q_index=int(parts[2]); ans_idx=int(parts[3])
    question=QUIZ_QUESTIONS[q_index]; correct=question["answer"]
    is_right=(ans_idx==correct)
    if is_right: ctx.user_data["quiz_score"]=ctx.user_data.get("quiz_score",0)+1
    exp=question["exp"].get(lang,question["exp"]["en"])
    correct_opt=question["options"][correct]
    result_line=tx(lang,"quiz_correct") if is_right else f"{tx(lang,'quiz_wrong')} ✔️ {correct_opt}"
    ctx.user_data["quiz_q"]=q_index+1
    text=(f"🧠 #{q_index+1}/10\n\n{'✅' if is_right else '❌'} {result_line}\n\n💡 _{exp}_\n\n🏆 {ctx.user_data['quiz_score']}/{q_index+1}")
    await safe_edit(q,text,reply_markup=quiz_kb(lang,q_index,answered=True))

async def quiz_finish_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    score=ctx.user_data.get("quiz_score",0)
    if   score<=3: grade={"ru":"🌑 Новичок — продолжай учиться!","en":"🌑 Beginner — keep learning!","he":"🌑 מתחיל!","ar":"🌑 مبتدئ!"}
    elif score<=6: grade={"ru":"🌓 Исследователь — хорошее знание!","en":"🌓 Explorer — solid knowledge!","he":"🌓 חוקר!","ar":"🌓 مستكشف!"}
    elif score<=8: grade={"ru":"🌕 Астронавт — впечатляет!","en":"🌕 Astronaut — impressive!","he":"🌕 אסטרונאוט!","ar":"🌕 رائد فضاء!"}
    else:          grade={"ru":"🚀 Легенда NASA — ты эксперт!","en":"🚀 NASA Legend — true expert!","he":"🚀 אגדת NASA!","ar":"🚀 أسطورة NASA!"}
    g=grade.get(lang,grade["en"])
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"btn_more_rnd"),callback_data="quiz_start_menu"),InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")]])
    await safe_edit(q,tx(lang,"quiz_result",score=score,grade=g),reply_markup=kb)
# ── End: QUIZ HANDLERS ────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: INTERACTIVE HANDLERS (space name, daily poll, mars rover live,         ║
#        lunar calendar, NASA TV)                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def space_name_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    user=q.from_user; name=(user.first_name or "Explorer").upper()
    seed=sum(ord(c) for c in name)+date.today().toordinal()
    random.seed(seed)
    prefix=random.choice(NAME_PREFIXES); suffix=random.choice(NAME_SUFFIXES); code=random.choice(STAR_CODES)
    callsign=f"{prefix}-{name[:3]}-{suffix}"; star_name=f"{prefix} {name[:4].title()} {code}"
    const=random.choice(["Orion","Lyra","Cygnus","Perseus","Aquila","Centaurus","Vela"])
    spec=random.choice(["G2V ☀️","K5V 🟠","M4V 🔴","F8V 🟡","A1V 🔵"]); dist=random.randint(10,9999)
    random.seed()
    text=(tx(lang,"name_gen_title")+f"👨‍🚀 *Callsign:*\n`{callsign}`\n\n⭐ *Your star:*\n`{star_name}`\n"
          f"📡 Constellation: {const}  |  Spectral: {spec}\n📍 Distance: {dist} light-years")
    await safe_edit(q,text,reply_markup=back_kb(lang,"space_name",ctx))

async def daily_poll_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    poll_data=DAILY_POLLS[date.today().toordinal()%len(DAILY_POLLS)]
    question=poll_data["q"].get(lang,poll_data["q"]["en"])
    options=poll_data["opts"].get(lang,poll_data["opts"]["en"])
    await del_msg(q)
    try:
        await ctx.bot.send_poll(chat_id=q.message.chat_id,question=f"🌌 {question}",options=options,is_anonymous=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"cat_interact_btn"),callback_data="cat_interact")]]))
    except:
        text=f"📊 *{question}*\n\n"+"".join(f"• {o}\n" for o in options)
        await ctx.bot.send_message(chat_id=q.message.chat_id,text=text,parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"cat_interact_btn"),callback_data="cat_interact")]]))

async def mars_rover_live_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🛰...")
    text=tx(lang,"mars_rover_title")
    for rover in ["perseverance","curiosity"]:
        try:
            r=requests.get(f"{NASA_BASE}/mars-photos/api/v1/manifests/{rover}",params={"api_key":NASA_API_KEY},timeout=10)
            if r.status_code==200:
                m=r.json().get("photo_manifest",{})
                status_e="🟢 Active" if m.get("status")=="active" else "⚪ Inactive"
                text+=(f"🤖 *{m.get('name',rover.title())}* — {status_e}\n"
                       f"   🛬 Landing: {m.get('landing_date','?')}\n"
                       f"   ☀️ Sol: {m.get('max_sol',0)}  |  📅 {m.get('max_date','?')}\n"
                       f"   📷 Photos: {m.get('total_photos',0):,}\n\n")
        except: continue
    text+="📍 [Mars Trek Map](https://trek.nasa.gov/mars/)"
    await safe_edit(q,text[:4096],reply_markup=back_kb(lang,"mars_rover_live",ctx))

async def lunar_calendar_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    today=date.today()
    text=tx(lang,"lunar_cal_title")+f"📅 *{today.strftime('%B %Y')}*\n\n"
    _mp=tx(lang,"moon_phases")
    phase_names={0:f"🌑 {_mp[0]}",2:f"🌓 {_mp[2]}",4:f"🌕 {_mp[4]}",6:f"🌗 {_mp[6]}"}
    seen=set()
    for i in range(30):
        d=today+timedelta(days=i); emoji,idx,cycle_day,illum=get_moon_phase(d)
        if idx in (0,2,4,6) and idx not in seen:
            seen.add(idx); text+=f"• {d.strftime('%d.%m')} — *{phase_names[idx]}* (~{illum}%)\n"
    text+="\n📸 *Tips:* Full Moon f/11 ISO100 1/250s | New Moon f/2.8 ISO3200 20s"
    await safe_edit(q,text[:4096],reply_markup=back_kb(lang,"lunar_calendar",ctx))

async def nasa_tv_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    await safe_edit(q,tx(lang,"nasa_tv_title"),reply_markup=back_kb(lang,ctx=ctx))
# ── End: INTERACTIVE HANDLERS ─────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: NEWS HANDLERS                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def _show_news_article(q, ctx, lang, source_key, idx):
    """Display one news article with photo (or text fallback)."""
    src = NEWS_SOURCES.get(source_key, {})
    articles = rss_cache_get(source_key)
    if not articles:
        articles = fetch_rss(source_key, max_items=30)
        if articles:
            rss_cache_set(source_key, articles)
    if not articles:
        await safe_edit(q, tx(lang,"news_empty"), reply_markup=back_kb(lang,"cat_news",ctx))
        return

    total = len(articles)
    idx   = idx % total
    art   = articles[idx]

    title  = art["title"]
    desc   = art["desc"]
    pub    = art["pub"]
    source = art["source"]
    emoji  = art["emoji"]
    link   = art["link"]

    caption = (f"{emoji} *{source}*\n"
               f"📅 _{pub}_\n\n"
               f"*{title}*\n\n"
               f"{desc}")
    caption = caption[:1020]

    kb = news_article_kb(lang, source_key, idx, total, link)
    img_url = art.get("img","") or art.get("fallback_img","")

    await del_msg(q)
    if img_url:
        try:
            await ctx.bot.send_photo(
                chat_id=q.message.chat_id, photo=img_url,
                caption=caption, parse_mode="Markdown", reply_markup=kb)
            return
        except Exception:
            pass
    # fallback: SDO solar image as header
    try:
        await ctx.bot.send_photo(
            chat_id=q.message.chat_id,
            photo=src.get("fallback_img","https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0193.jpg"),
            caption=caption, parse_mode="Markdown", reply_markup=kb)
    except Exception:
        await ctx.bot.send_message(
            chat_id=q.message.chat_id, text=caption[:4096],
            parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)

async def news_source_h(update, ctx, source_key):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    await safe_edit(q, tx(lang,"news_loading"))
    seen_key = f"news_seen_{source_key}"
    seen = ctx.user_data.get(seen_key, set())
    articles = rss_cache_get(source_key) or fetch_rss(source_key, 30)
    if articles: rss_cache_set(source_key, articles)
    start_idx = 0
    if articles:
        for i, art in enumerate(articles):
            if art["guid"] not in seen:
                start_idx = i
                break
        else:
            ctx.user_data[seen_key] = set()
            start_idx = 0
    ctx.user_data[seen_key] = seen | {articles[start_idx]["guid"]} if articles else seen
    ctx.user_data["last_cat"] = "cat_news"
    await _show_news_article(q, ctx, lang, source_key, start_idx)

async def news_nasa_h(update, ctx):      await news_source_h(update, ctx, "news_nasa")
async def news_sfn_h(update, ctx):       await news_source_h(update, ctx, "news_sfn")
async def news_spacenews_h(update, ctx): await news_source_h(update, ctx, "news_spacenews")
async def news_spacedotcom_h(update, ctx): await news_source_h(update, ctx, "news_spacedotcom")
async def news_planetary_h(update, ctx): await news_source_h(update, ctx, "news_planetary")

async def news_page_h(update, ctx):
    """Handle news_page_{source}_{idx} callbacks."""
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    parts = q.data.split("_")
    try:
        idx = int(parts[-1])
        source_key = "_".join(parts[2:-1])
    except Exception:
        await safe_answer(q); return
    seen_key = f"news_seen_{source_key}"
    articles = rss_cache_get(source_key) or []
    if articles and idx < len(articles):
        seen = ctx.user_data.get(seen_key, set())
        seen.add(articles[idx]["guid"])
        ctx.user_data[seen_key] = seen
    await _show_news_article(q, ctx, lang, source_key, idx)
# ── End: NEWS HANDLERS ────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: SCHEDULED JOB HANDLERS (asteroid/meteor/space weather/lunar alerts,   ║
#        time capsule delivery)                                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def job_asteroid_alert(context):
    subs=load_subscribers(); chat_ids=subs.get("asteroids",[])
    if not chat_ids: return
    try:
        today=date.today().isoformat()
        data=nasa_req("/neo/rest/v1/feed",{"start_date":today,"end_date":today})
        neos=data["near_earth_objects"].get(today,[])
        danger=[a for a in neos if a["is_potentially_hazardous_asteroid"]]
        if not danger: return
        msg=f"☄️ *Asteroid Alert!*\n📅 {today}\n\n⚠️ *{len(danger)} hazardous NEO(s)!*\n\n"
        for ast in danger[:3]:
            name=ast["name"].replace("(","").replace(")","").strip()
            ap=ast["close_approach_data"][0] if ast["close_approach_data"] else {}
            dist=ap.get("miss_distance",{}).get("lunar","?")
            try: dist=f"{float(dist):.1f} LD"
            except: pass
            d_max=ast["estimated_diameter"]["meters"]["estimated_diameter_max"]
            msg+=f"🔴 *{name}* — ~{d_max:.0f}m  📍 {dist}\n"
        msg+="\n[🔗 NASA NEO](https://cneos.jpl.nasa.gov)"
        for cid in chat_ids:
            try: await context.bot.send_message(chat_id=cid,text=msg[:4096],parse_mode="Markdown",disable_web_page_preview=True)
            except Exception as e: logger.warning(f"Asteroid alert {cid}: {e}")
    except Exception as e: logger.error(f"job_asteroid_alert: {e}")

async def job_meteor_alert(context):
    subs=load_subscribers(); chat_ids=subs.get("meteors",[])
    if not chat_ids: return
    today=date.today(); parts=[]
    for shower in METEOR_SHOWERS:
        try:
            peak_str=shower["peak"].split("–")[0].strip()
            peak_dt=datetime.strptime(f"{peak_str} {today.year}","%d %b %Y").date()
            if 0<=(peak_dt-today).days<=7:
                name=shower["name"].get("ru",shower["name"]["en"])
                parts.append(f"🌠 *{name}* — {shower['peak']}\n   {shower['rate']}  ⚡ {shower['speed']}")
        except: continue
    if not parts: return
    msg="🌠 *Meteor Shower This Week!*\n\n"+"\n\n".join(parts)
    for cid in chat_ids:
        try: await context.bot.send_message(chat_id=cid,text=msg[:4096],parse_mode="Markdown")
        except Exception as e: logger.warning(f"Meteor alert {cid}: {e}")

async def job_space_weather_alert(context):
    subs=load_subscribers(); chat_ids=subs.get("space_weather",[])
    if not chat_ids: return
    try:
        r=requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",timeout=12); r.raise_for_status()
        data=r.json()
        recent=[float(d.get("kp_index",d.get("Kp",0))) for d in data[-5:] if d]
        kp_max=max(recent) if recent else 0
        if kp_max<5: return
        state="🟠 G2" if kp_max<6 else "🔴 G3" if kp_max<7 else "🚨 G4+"
        aurora="Scandinavia/Canada (>60°)" if kp_max<6 else "Central Europe (>50°)" if kp_max<7 else "Mid-latitudes (>40°)"
        msg=f"🌞 *Space Weather Alert!*\n\nKp: *{kp_max:.1f}* {state}\n🌈 Aurora: {aurora}\n\n[NOAA](https://www.swpc.noaa.gov)"
        for cid in chat_ids:
            try: await context.bot.send_message(chat_id=cid,text=msg,parse_mode="Markdown",disable_web_page_preview=True)
            except Exception as e: logger.warning(f"SW alert {cid}: {e}")
    except Exception as e: logger.error(f"job_space_weather_alert: {e}")

async def job_lunar_alert(context):
    subs=load_subscribers(); chat_ids=subs.get("lunar",[])
    if not chat_ids: return
    emoji,idx,cycle_day,illum=get_moon_phase(date.today())
    if idx not in (0,4): return
    is_full=(idx==4); phase_name="Full Moon 🌕" if is_full else "New Moon 🌑"
    tip=("📸 Full Moon: ISO 100, f/11, 1/250s" if is_full else "📸 New Moon: ISO 3200, f/2.8, 20-30s")
    msg=f"{emoji} *Lunar Alert: {phase_name}*\n\nIllum: ~{illum}%\n\n{tip}"
    for cid in chat_ids:
        try: await context.bot.send_message(chat_id=cid,text=msg,parse_mode="Markdown")
        except Exception as e: logger.warning(f"Lunar alert {cid}: {e}")

async def job_check_capsules(context):
    capsules=load_capsules(); today_str=date.today().isoformat(); remaining=[]
    for cap in capsules:
        if cap.get("deliver_on","")<=today_str:
            try:
                text=(f"⏳ *Time Capsule*\n\nA year ago you wrote:\n\n_{cap['message']}_\n\n🚀 Did it come true?")
                await context.bot.send_message(chat_id=cap["chat_id"],text=text[:4096],parse_mode="Markdown")
            except Exception as e: logger.warning(f"Capsule {cap.get('chat_id')}: {e}")
        else: remaining.append(cap)
    if len(remaining)!=len(capsules): save_capsules(remaining)
# ── End: SCHEDULED JOB HANDLERS ──────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: NAVIGATION HANDLERS (back, unknown message)                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def back_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    await safe_edit(q,tx(lang,"main_menu"),reply_markup=main_menu_kb(lang))

async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang=get_lang(ctx)
    await update.message.reply_text(tx(lang,"unknown"),reply_markup=main_menu_kb(lang))
# ── End: NAVIGATION HANDLERS ──────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: CALLBACK ROUTER — IMG_MAP, DIRECT_MAP, CAT_MAP                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
IMG_MAP = {
    "epic": EARTH_Q, "gallery": GALLERY_Q,
    "earth_night": ["earth at night city lights nasa","night lights satellite ISS","city lights from space"],
    "eclipse": ["solar eclipse nasa","total eclipse corona","lunar eclipse blood moon","diamond ring solar eclipse"],
    "jwst_gallery": ["James Webb JWST deep field","Webb nebula infrared","JWST carina nebula","Webb Pillars of Creation","James Webb galaxy cluster"],
    "moon_gallery": ["moon surface nasa apollo","lunar crater full moon","moon from ISS nasa","lunar south pole crater"],
    "blue_marble": ["blue marble earth nasa","whole earth from space","earth from moon apollo","earth deep space voyager"],
    "ceres": ["Ceres Dawn nasa bright spots","Ceres dwarf planet surface","Ceres occator crater"],
    "pluto_close": ["Pluto New Horizons nasa","Pluto heart feature","Pluto mountains nitrogen ice"],
    "nebulae": ["nebula hubble","eagle nebula pillars","orion nebula hubble","carina nebula webb","helix nebula eye god"],
    "deepspace": ["hubble deep field galaxy","james webb deep field","hubble ultra deep field","galaxy cluster hubble"],
    "sun": ["solar flare nasa SDO","sun corona sdo","sunspot close up","solar prominence nasa"],
    "aurora": ["aurora borealis ISS","northern lights nasa","aurora australis space","polar lights from orbit"],
    "blackholes": ["black hole accretion disk nasa","M87 black hole image","black hole jet galaxy nasa"],
    "supernovae": ["supernova remnant hubble","crab nebula pulsar","cassiopeia supernova nasa","supernova 1987A"],
    "clusters": ["star cluster hubble","globular cluster omega centauri","pleiades star cluster","hercules cluster"],
    "comets": ["comet nasa hubble","comet NEOWISE","comet 67P rosetta","comet tail sun"],
    "history": ["apollo moon landing nasa","space shuttle launch","neil armstrong moon","saturn V launch apollo"],
    "giants": ["jupiter great red spot nasa","saturn rings cassini","jupiter bands close up","saturn polar hexagon cassini"],
    "moons": ["europa moon jupiter nasa","titan saturn cassini","enceladus geysers south pole","ganymede jwst"],
    "missions": ["voyager spacecraft nasa","cassini saturn rings","perseverance rover nasa","new horizons pluto flyby"],
    "nearstars": ["alpha centauri telescope","red dwarf star nasa","proxima centauri flare","barnard star"],
    "pulsars": ["pulsar nebula nasa","crab pulsar hubble","vela pulsar jets","neutron star pulsar"],
    "milkyway": ["milky way galaxy nasa","galactic center milky way","milky way arch long exposure"],
    "magnetosphere": ["earth magnetosphere nasa","Van Allen belts radiation","aurora magnetosphere"],
    "dwarfplanets": ["pluto new horizons nasa","ceres dawn nasa","haumea dwarf planet","eris kuiper belt"],
    "climate": ["arctic ice melt nasa","sea level rise satellite","glacier retreat nasa","polar ice cap nasa"],
    "quasars": ["quasar nasa hubble","active galactic nucleus jet","quasar 3C273 hubble","blazar nasa"],
    "cmb": ["cosmic microwave background Planck","CMB temperature map","big bang afterglow nasa"],
    "galaxy_collision": ["galaxy collision hubble","antennae galaxies hubble","mice galaxies merging","galaxy pair merger"],
    "star_formation": ["star formation nebula","pillars of creation webb","stellar nursery hubble","protostar disk"],
    "cosmic_web": ["cosmic web simulation","large scale structure universe","galaxy filament dark matter"],
    "wildfires": ["wildfire satellite nasa","forest fire space view","california wildfire smoke ISS"],
    "ice_sheets": ["ice sheet antarctica nasa","arctic sea ice extent","glacier calving nasa","greenland ice melt"],
    "deforestation": ["deforestation amazon satellite","forest loss satellite","amazon river deforestation"],
    "night_lights": ["earth at night city lights nasa","city lights ISS time lapse","europe night lights satellite"],
    "ocean_temp": ["sea surface temperature nasa","pacific ocean heat satellite","ocean temperature anomaly"],
    "volcanoes": ["volcano eruption space","hawaii volcano lava nasa","etna eruption satellite","kilauea lava flows"],
    "hurricanes": ["hurricane from space satellite","tropical storm ISS eye","hurricane irma dorian satellite","cyclone space view"],
    "spacewalks": ["spacewalk EVA astronaut ISS","astronaut tethered spacewalk","EVA hubble repair","astronaut floating space"],
    "lunar_missions": ["apollo moon mission surface","artemis moon nasa","apollo 17 lunar rover","lunar lander nasa"],
    "moon_landing_sites": ["apollo landing site moon","tranquility base nasa","apollo 11 footprint","lunar module nasa"],
    "rocket_engines": ["rocket engine RS-25 nasa","raptor engine test fire","saturn V engine f1","engine plume rocket"],
    "tornadoes": ["tornado from space satellite","supercell storm satellite","tornado weather damage aerial"],
    "space_food": ["space food astronaut nasa ISS","astronaut eating weightless","food packaging ISS"],
    "kuiper_belt": ["kuiper belt pluto new horizons","dwarf planets kuiper belt","arrokoth new horizons flyby"],
    "mars_colonization": ["mars base concept nasa","mars colony artist render","spacex starship mars"],
    "space_medicine": ["astronaut health medical space","bone loss microgravity","space medicine ISS experiments"],
    "astronaut_training": ["astronaut training underwater NASA","centrifuge astronaut training","neutral buoyancy pool nasa"],
    "debris": ["space debris orbit earth","orbital junk satellite nasa","space junk simulation earth orbit"],
    "space_records": ["cosmonaut long duration space record","ISS long stay astronaut","Voyager 1 distance solar system"],
    "space_stations": ["international space station ISS orbit","ISS exterior solar panels","space station earth view"],
    "women_in_space": ["women astronauts nasa ISS","Sally Ride nasa first american","female astronaut spacewalk"],
    "kuiper": ["kuiper belt pluto new horizons","dwarf planets kuiper belt","arrokoth new horizons flyby"],
    "ozone": ["ozone layer nasa satellite","ozone hole antarctica","ozone depletion south pole"],
    "ocean_currents": ["ocean currents satellite nasa","gulf stream atlantic satellite","ocean circulation pattern"],
    "seti": ["radio telescope dish array","very large array VLA","arecibo telescope history","radio telescope night sky"],
    "gravwaves": ["gravitational waves LIGO detector","black hole merger art nasa","neutron star collision kilonova"],
    "darkmatter": ["dark matter cosmic web simulation","galaxy cluster dark matter lensing","dark matter map hubble"],
    "future": ["mars base concept nasa art","lunar base artemis concept","space station future nasa concept"],
    "radioastro": ["very large array VLA telescope","radio galaxy jets nasa","radio telescope dish"],
    "grb": ["gamma ray burst nasa swift","gamma ray sky fermi telescope","GRB afterglow optical"],
    "dark_energy": ["supernovae accelerating universe","dark energy survey telescope","type Ia supernova distance"],
    "planet_alignment": ["planet parade conjunction sky","planets alignment photo","multiple planets night sky"],
    "solar_eclipse": ["solar eclipse totality","total solar eclipse corona diamond ring","eclipse path shadow"],
    "orbital_scale": ["solar system scale comparison","planets size comparison nasa","solar system distance scale"],
    "red_giants": ["red giant star nasa","betelgeuse red supergiant","red giant stellar evolution"],
    "rocket_engines": ["rocket engine RS-25 nasa","raptor engine test fire","saturn V engine f1"],
}

DIRECT_MAP = {
    "apod": apod_h, "apod_random": apod_random_h,
    "mars": mars_h, "mars_rovers": mars_rovers_h,
    "asteroids": asteroids_h, "planets": planets_h,
    "moon": moon_h, "meteors": meteors_h, "spaceweather": spaceweather_h,
    "iss": iss_h, "launches": launches_h,
    "satellites": satellites_h, "telescopes": telescopes_h,
    "exoplanets": exoplanets_h,
    "spacefact": spacefact_h, "channels": channels_h,
    "live_solar_wind":        live_solar_wind_h,
    "live_kp":                live_kp_h,
    "live_flares":            live_flares_h,
    "live_iss":               live_iss_h,
    "live_radiation":         live_radiation_h,
    "live_aurora_forecast":   live_aurora_h,
    "live_geomagnetic_alert": live_geomag_h,
    "live_sunspot":           live_sunspot_h,
    "live_epic_latest":       live_epic_h,
    "live_satellite_count":   live_sat_count_h,
    "notifications_menu": notifications_menu_h,
    "space_name":         space_name_h,
    "quiz_start_menu":    quiz_start_menu_h,
    "quiz_next":          quiz_next_h,
    "quiz_finish":        quiz_finish_h,
    "daily_poll":         daily_poll_h,
    "mars_rover_live":    mars_rover_live_h,
    "nasa_tv":            nasa_tv_h,
    "lunar_calendar":     lunar_calendar_h,
    "news_nasa":          news_nasa_h,
    "news_sfn":           news_sfn_h,
    "news_spacenews":     news_spacenews_h,
    "news_spacedotcom":   news_spacedotcom_h,
    "news_planetary":     news_planetary_h,
}

CAT_MAP = {
    "cat_photo":     (cat_photo_kb,     "title_photo"),
    "cat_solarsys":  (cat_solarsys_kb,  "title_solarsys"),
    "cat_deepspace": (cat_deepspace_kb, "title_deepspace"),
    "cat_earth":     (cat_earth_kb,     "title_earth"),
    "cat_science":   (cat_science_kb,   "title_science"),
    "cat_live":      (cat_live_kb,      "title_live"),
    "cat_interact":  (cat_interact_kb,  "title_interact"),
    "cat_news":      (cat_news_kb,      "title_news"),
}
# ── End: CALLBACK ROUTER — IMG_MAP, DIRECT_MAP, CAT_MAP ──────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: CALLBACK ROUTER FUNCTION                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def callback_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; cb=q.data; lang=get_lang(ctx)
    if cb=="choose_lang":           await choose_lang_h(update,ctx); return
    if cb.startswith("setlang_"):   await setlang_h(update,ctx); return
    if cb=="back":                  await back_h(update,ctx); return
    if cb=="noop":                  await safe_answer(q); return
    if cb.startswith("news_page_"): await news_page_h(update,ctx); return
    if cb in CAT_MAP:
        kb_fn,title_key=CAT_MAP[cb]; await safe_answer(q)
        ctx.user_data["last_cat"]=cb
        await safe_edit(q,tx(lang,title_key)+tx(lang,"choose_sec"),reply_markup=kb_fn(lang)); return
    if cb in DIRECT_MAP:
        await DIRECT_MAP[cb](update,ctx); return
    if cb.startswith("notif_toggle_"):
        await notif_toggle_h(update,ctx); return
    if cb.startswith("quiz_ans_"):
        await quiz_answer_h(update,ctx); return
    if cb in STATIC_TEXTS:
        await safe_answer(q)
        texts=STATIC_TEXTS[cb]; text=texts.get(lang,texts.get("en",""))
        img_queries = IMG_MAP.get(cb, [])
        if img_queries:
            await safe_edit(q,"⏳...")
            await send_nasa_image(q, ctx, img_queries, cb)
        else:
            await safe_edit(q,text[:4096],reply_markup=back_kb(lang,cb,ctx))
        return
    if cb in IMG_MAP:
        await safe_answer(q); await safe_edit(q,"⏳...")
        await send_nasa_image(q,ctx,IMG_MAP[cb],cb); return
    await safe_answer(q)
# ── End: CALLBACK ROUTER FUNCTION ────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: FLASK ROUTES (webhook endpoint, health check)                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@flask_app.route("/")
def index(): return "🚀 NASA Bot is alive!", 200

@flask_app.route("/health")
def health(): return "OK", 200

@flask_app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    if tg_app is None: return "Bot not ready", 503
    data=request.get_json(force=True)
    future=asyncio.run_coroutine_threadsafe(process_update(data),bot_loop)
    try: future.result(timeout=30)
    except Exception as e: logger.error(f"Webhook processing error: {e}")
    return "ok", 200

async def process_update(data):
    update=Update.de_json(data,tg_app.bot)
    await tg_app.process_update(update)
# ── End: FLASK ROUTES ─────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: BOT SETUP & STARTUP (setup_bot, set_bot_descriptions, init_worker)    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def _run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

async def set_bot_descriptions(bot):
    descriptions = {
        "ru": "🚀 Твой проводник во Вселенную! Фото NASA, Марс, МКС, астероиды, живые данные о космической погоде и многое другое.",
        "en": "🚀 Your guide to the Universe! NASA photos, Mars, ISS, asteroids, live space weather data and much more.",
        "he": "🚀 המדריך שלך ליקום! תמונות NASA, מאדים, ISS, אסטרואידים ועוד.",
        "ar": "🚀 دليلك إلى الكون! صور NASA، المريخ، محطة الفضاء، الكويكبات والمزيد.",
    }
    try:
        for lang_code,desc in descriptions.items():
            await bot.set_my_description(description=desc,language_code=lang_code)
        logger.info("✅ Bot descriptions set")
    except Exception as e:
        logger.error(f"Failed to set descriptions: {e}")

async def setup_bot():
    global tg_app
    builder=Application.builder().token(TELEGRAM_TOKEN)
    tg_app=builder.build()

    planet_conv=ConversationHandler(
        entry_points=[CallbackQueryHandler(planet_calc_start,pattern="^planet_calc$")],
        states={
            PLANET_DATE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, planet_date_received)],
            PLANET_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, planet_weight_received)],
        },
        fallbacks=[CommandHandler("cancel",planet_calc_cancel)],
        allow_reentry=True,
    )
    capsule_conv=ConversationHandler(
        entry_points=[CallbackQueryHandler(capsule_menu_h,pattern="^capsule_menu$")],
        states={
            CAPSULE_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, capsule_msg_received)],
        },
        fallbacks=[CommandHandler("cancel",capsule_cancel)],
        allow_reentry=True,
    )
    horoscope_conv=ConversationHandler(
        entry_points=[CallbackQueryHandler(horoscope_menu_h,pattern="^horoscope_menu$")],
        states={
            HOROSCOPE_BDAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, horoscope_date_received)],
        },
        fallbacks=[CommandHandler("cancel",horoscope_cancel)],
        allow_reentry=True,
    )

    tg_app.add_handler(CommandHandler("start",start))
    tg_app.add_handler(CommandHandler("menu",menu_cmd))
    tg_app.add_handler(planet_conv)
    tg_app.add_handler(capsule_conv)
    tg_app.add_handler(horoscope_conv)
    tg_app.add_handler(CallbackQueryHandler(callback_router))
    tg_app.add_handler(MessageHandler(filters.ALL, unknown))

    jq=tg_app.job_queue
    if jq:
        from datetime import time as dtime
        jq.run_daily(job_asteroid_alert, time=dtime(9,0,0))
        jq.run_daily(job_lunar_alert,    time=dtime(7,0,0))
        jq.run_daily(job_check_capsules, time=dtime(10,0,0))
        jq.run_repeating(job_space_weather_alert, interval=3600, first=60)
        jq.run_repeating(job_meteor_alert, interval=7*24*3600, first=120)
    else:
        logger.warning("job_queue not available — scheduled alerts disabled")

    await tg_app.initialize()
    await tg_app.start()
    if WEBHOOK_URL and TELEGRAM_TOKEN:
        wh_url=f"{WEBHOOK_URL}/webhook/{TELEGRAM_TOKEN}"
        try:
            await tg_app.bot.set_webhook(wh_url,drop_pending_updates=True)
            logger.info(f"✅ Webhook: {wh_url}")
        except Exception as e:
            logger.error(f"set_webhook: {e}")
    await set_bot_descriptions(tg_app.bot)

def init_worker():
    global bot_loop
    bot_loop=asyncio.new_event_loop()
    t=threading.Thread(target=_run_loop,args=(bot_loop,),daemon=True)
    t.start()
    future=asyncio.run_coroutine_threadsafe(setup_bot(),bot_loop)
    future.result(timeout=30)
    logger.info("✅ Worker initialized — bot loop running")

if __name__=="__main__":
    init_worker()
    flask_app.run(host="0.0.0.0",port=PORT)
# ── End: BOT SETUP & STARTUP ──────────────────────────────────────────────────
