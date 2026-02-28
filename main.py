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
HOROSCOPE_BDAY = 10
CAPSULE_MSG    = 20
ISS_CITY      = 30
DICT_TERM     = 31
QA_QUESTION   = 32
ROCKET_STEP   = 33
SMART_KP      = 34
SMART_LD      = 35
CHALLENGE_ANS = 36
COURSE_ENROLL = 37
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
    "news_esa": {
        "url": "https://www.esa.int/rssfeed/Our_Activities/Space_News",
        "url_fallback": "https://www.esa.int/rssfeed/Space_news",
        "name": "ESA",
        "emoji": "🛰",
        "fallback_img": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0193.jpg",
    },
    "news_universetoday": {
        "url": "https://www.universetoday.com/feed/",
        "name": "Universe Today",
        "emoji": "🪐",
        "fallback_img": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0171.jpg",
    },
    "news_skytel": {
        "url": "https://skyandtelescope.org/feed/",
        "url_fallback": "https://www.skyandtelescope.com/feed/",
        "name": "Sky & Telescope",
        "emoji": "🔭",
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
    "btn_news_esa":          "🛰 ESA",
    "btn_news_universetoday":"🪐 Universe Today",
    "btn_news_skytel":       "🔭 Sky & Telescope",
    "btn_news_next":"➡️ Следующая",
    "btn_news_source":"🔗 Источник",
    "news_loading":"📰 Загружаю новости...",
    "news_empty":"📭 Новостей не найдено",
    "news_counter":"Новость {idx}/{total}",
    "btn_spacefact":"⭐ Факт о космосе", "btn_channels":"📢 Наши каналы", "btn_lang":"🌍 Язык",
    "title_profile":    "👤 Мой профиль",
    "btn_favorites":    "Избранное",
    "btn_mystats":      "Статистика",
    "btn_achievements": "Достижения",
    "btn_smart_alerts": "Умные алерты",
    "btn_iss_schedule": "🌠 МКС над городом",
    "btn_meteorite_map":"🗺 Карта метеоритов",
    "btn_flight_calc":  "🧮 Калькулятор полёта",
    "btn_mission_status":"📡 Статус миссий",
    "btn_dictionary":   "📚 Космический словарь",
    "btn_course":       "🎓 Астрономия 30 дней",
    "btn_earthquakes":  "🌍 Землетрясения",
    "btn_sat_tracker":  "🛸 Трекер спутников",
    "btn_sw_digest":    "☀️ Дайджест погоды",
    "btn_exo_alert":    "🔭 Новые экзопланеты",
    "btn_challenge":    "🎯 Челлендж",
    "btn_rocket_game":  "👾 Посади ракету",
    "btn_daily_horoscope":"🌌 Гороскоп сегодня",
    "btn_space_qa":     "💬 Вопрос о космосе",
    "btn_profile":      "👤 Профиль",
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
    # ── NEW: handler-level translations ──
    "telescopes_text":"🔬 *Космические телескопы*\n\n🌌 *JWST* — зеркало 6.5м, орбита L2, инфракрасный\n🔭 *Хаббл* — зеркало 2.4м, оптический/УФ, орбита 600км\n📡 *Чандра* — рентген, эллиптическая орбита\n🌊 *XMM-Newton* — рентген, ESA\n🔭 *Спитцер* — инфракрасный (завершён 2020)\n📡 *VLT* — 4×8.2м, Атакама\n🌐 *FAST* — 500м радиотелескоп, Китай\n🔭 *ELT (~2028)* — зеркало 39м, ESA\n🌌 *Roman (~2027)* — широкоугольный инфракрасный, NASA",
    "spacefact_title":"⭐ *Факт о космосе*",
    "meteors_title":"🌠 *Метеорные потоки*",
    "moon_title":"🌙 *Фаза Луны — {d}*",
    "moon_photo_tip":"📸 Совет: ISO 100, f/11, 1/250s",
    "satellites_text":"📡 *Спутники на орбите*\n\n🌍 Всего отслеживается: ~9,000+\n🛸 *Starlink:* {total} всего, {active} активных\n🔭 *Другие:* OneWeb, GPS, Galileo, ГЛОНАСС\n\n[🔗 n2yo.com — трекинг](https://www.n2yo.com)",
    "launches_title":"🚀 *Ближайшие запуски*",
    "exoplanets_title":"🔭 *Экзопланеты*",
    "spaceweather_text_title":"*Космическая погода — Live*",
    "sw_calm":"🟢 Спокойно","sw_moderate":"🟡 Умеренно","sw_strong":"🟠 Сильно","sw_storm":"🔴 ШТОРМ",
    "kp_quiet":"🟢 Спокойно","kp_minor":"🟡 Незначительная","kp_moderate":"🟠 Умеренная","kp_strong":"🔴 Сильная","kp_extreme":"🚨 Экстремальная",
    "aurora_polar":"Только полярные области","aurora_scandinavia":"Скандинавия/Канада","aurora_mid":"Средние широты","aurora_equatorial":"Экватор",
    "live_solar_wind_title":"🔴 *LIVE: Солнечный ветер*",
    "live_kp_title":"🔴 *LIVE: Kp-индекс*",
    "live_flares_title":"🔴 *LIVE: Солнечные вспышки*",
    "live_iss_title":"🔴 *LIVE: МКС*",
    "live_radiation_title":"🔴 *LIVE: Радиация*",
    "live_aurora_title":"🔴 *Прогноз сияний*",
    "live_geomag_title":"🔴 *Геомагнитные бури (2д)*",
    "live_sunspot_title":"🔴 *Пятна Солнца (Цикл 25)*",
    "live_sunspot_text":"Число Вольфа: *{ssn}*\n\nЦикл 25 близок к максимуму — больше вспышек.",
    "live_epic_title":"🌍 *EPIC Live — Земля*",
    "live_epic_desc":"Спутник DSCOVR (L1).",
    "live_starlink_title":"🔴 *Starlink*\n\nВсего: *{total}*  |  Активных: *{active}*\n\nВсе спутники: ~9,000+ на орбите.",
    "planet_calc_title":"🪐 *Калькулятор планет*",
    "planet_calc_earth":"🌍 *Земля:* {age} лет  |  {weight} кг",
    "planet_calc_moon":"🌙 *Луна:* ⚖️ {w} кг (16.5% гравитации)",
    "planet_calc_days":"💡 Ты прожил *{days}* земных дней!",
    "name_callsign":"👨‍🚀 *Позывной:*","name_star":"⭐ *Твоя звезда:*",
    "name_constellation":"📡 Созвездие: {c}  |  Спектр: {s}","name_distance":"📍 Расстояние: {d} световых лет",
    "rover_active":"🟢 Активен","rover_inactive":"⚪ Неактивен",
    "rover_landing":"🛬 Посадка:","rover_sol":"☀️ Sol:","rover_photos":"📷 Фото:",
    "quiz_question_title":"🧠 *Вопрос {n}/10*",
    "challenge_title":"🎯 *Ежедневный челлендж*","challenge_question":"❓ *Что это за объект?*",
    "challenge_result_title":"🎯 *Результат челленджа*","challenge_correct":"✅ Правильно!",
    "challenge_wrong":"❌ Неверно! Ответ: *{ans}*","challenge_loading":"⏳ Загрузка изображения...",
    "challenge_next":"🎯 Следующий челлендж",
    "rocket_title":"🚀 *Симулятор посадки Falcon 9*","rocket_step_label":"━━ Шаг {n}/{total} ━━",
    "rocket_what_do":"*Что ты делаешь?*","rocket_abort":"❌ Прервать миссию",
    "rocket_boom":"💥 *БУУУМ!*","rocket_wrong_call":"❌ Неверное решение на шаге {n}.",
    "rocket_crashed":"Falcon 9 разбился о посадочную платформу. Попробуй снова!",
    "rocket_rsd":"🔧 SpaceX называет это «быстрой внеплановой разборкой».",
    "rocket_try_again":"🔄 Повторить","rocket_good_call":"✅ *Верное решение!*",
    "rocket_next":"➡️ Далее...","rocket_touchdown":"🎉 *КАСАНИЕ! ИДЕАЛЬНАЯ ПОСАДКА!*",
    "rocket_landed":"✅ Falcon 9 успешно сел на посадочную платформу!",
    "rocket_fuel":"⛽ Остаток топлива: 3%  |  Скорость касания: 2 м/с",
    "rocket_mastered":"🏅 Ты освоил алгоритм посадки Falcon 9.",
    "rocket_since2015":"_SpaceX делает это регулярно с 2015 года!_",
    "rocket_play_again":"🔄 Играть снова",
    "qa_chars_error":"❌ 3–500 символов","qa_thinking":"🤔 Думаю...","qa_cancelled":"❌ Отменено",
    "qa_ask_another":"❓ Ещё вопрос","qa_api_error":"❌ API Клод не настроен.",
    "fav_saved":"⭐ Сохранено!","fav_max":"❌ Максимум 50 избранных",
    "fav_title":"⭐ *Избранное*","fav_empty":"Сохранённых фото пока нет.\nНажми ⭐ на любом APOD, чтобы сохранить!",
    "fav_your":"⭐ *Твоё избранное*","fav_total":"_Всего: {n} фото_",
    "fav_clear":"🗑 Удалить всё","fav_cleared":"🗑 Избранное очищено.",
    "smart_title":"🔔 *Настройки Smart-оповещений*",
    "smart_kp_desc":"⚡ Оповещение Kp при ≥ *{v}* (видно сияние)",
    "smart_ast_desc":"☄️ Оповещение об астероиде при < *{v}* LD",
    "smart_eq_desc":"🌍 Оповещение о землетрясении при M ≥ *{v}*",
    "smart_tap":"_Нажми, чтобы изменить порог:_",
    "smart_kp_ask":"⚡ Отправь порог Kp (1–9, напр. *5* для умеренного сияния):",
    "smart_ld_ask":"☄️ Отправь порог расстояния LD (1–10, напр. *2* = 2 лунных расстояния):",
    "smart_eq_ask":"🌍 Отправь порог магнитуды (4–9, напр. *6*):",
    "smart_kp_err":"❌ Введи число 1–9","smart_ld_err":"❌ Введи число 0.5–20","smart_eq_err":"❌ Введи число 4–9",
    "smart_kp_set":"✅ Оповещение Kp установлено на ≥ *{v}*",
    "smart_ld_set":"✅ Оповещение об астероиде установлено на < *{v} LD*",
    "smart_eq_set":"✅ Оповещение о землетрясении установлено на M ≥ *{v}*",
    "smart_back":"🔔 К оповещениям",
    "stats_title":"📊 *Моя космостатистика*",
    "stats_apod":"📸 APOD просмотрено:","stats_quiz":"🧠 Квизов пройдено:",
    "stats_perfect":"🏆 Идеальных квизов:","stats_challenge":"🎯 Челленджей:",
    "stats_favorites":"⭐ Избранных:","stats_achievements":"🏅 Достижения:",
    "stats_streak":"🔥 Текущая серия:","stats_streak_days":"дней",
    "stats_since":"📅 Активен с:",
    "iss_sched_title":"🌠 *Расписание видимости МКС*","iss_sched_enter":"Введи название города:",
    "iss_sched_examples":"_Примеры: {cities}_",
    "iss_sched_not_found":"❌ Город не найден. Попробуй: Moscow, London, Tokyo, Tel Aviv, Dubai...",
    "iss_sched_over":"🌠 *МКС над {city}*",
    "iss_sched_api_na":"⚠️ API прогноза пролётов недоступен.",
    "iss_sched_position":"📍 Текущая позиция МКС:","iss_sched_alt":"Высота: ~408 км",
    "iss_sched_orbit":"🔄 МКС совершает один оборот каждые ~92 мин.",
    "iss_sched_passes":"⬆️ *Ближайшие пролёты:*",
    "iss_sched_times":"_Время в UTC. МКС движется со скоростью 28 000 км/ч._",
    "meteor_map_title":"🗺 *Топ-10 метеоритов (база NASA)*",
    "meteor_map_famous":"🗺 *Знаменитые метеориты*",
    "flight_title":"🧮 *Калькулятор полёта*","flight_choose":"Выбери пункт назначения:",
    "flight_to":"🚀 К *{name}* ({desc})\n\nВыбери скорость:",
    "flight_result_title":"🧮 *Результат калькулятора полёта*",
    "flight_from":"📍 Из: Земля  →  {name}","flight_distance":"📏 Расстояние: {km} км",
    "flight_speed_label":"⚡ Скорость: {name} ({kmh} км/ч)",
    "flight_time":"🕐 Время полёта: *{t}*",
    "flight_another":"🔄 Ещё расчёт",
    "flight_grandchildren":"_Твои праправнуки долетят._",
    "flight_lightspeed":"_На скорости света — всё равно 2.5 миллиона лет!_",
    "flight_fuel":"_Топлива нужно на сумму больше ВВП Земли._",
    "missions_title":"📡 *Активные космические миссии*","missions_select":"Выбери для подробностей:",
    "missions_all":"◀️ Все миссии","missions_learn":"🔗 Подробнее",
    "dict_title":"📚 *Космический словарь*","dict_choose":"Выбери термин:",
    "dict_funfact":"💡 *Интересный факт:*",
    "course_title":"🎓 *Астрономия за 30 дней*",
    "course_desc":"Ежедневный урок — от Солнечной системы до космической паутины.",
    "course_subscribe_btn":"🎓 Подписаться на курс","course_browse_btn":"📚 Все уроки",
    "course_already":"🎓 Ты уже подписан! День *{day}/30*.\nСледующий урок придёт в 10:00.",
    "course_subscribed":"✅ *Подписка на курс «Астрономия за 30 дней»!*\n\nВот первый урок:",
    "course_all":"📚 *Все 30 уроков*","course_day":"🎓 *День {day}/30 — Курс астрономии*",
    "ach_title":"🏆 *Достижения*","ach_earned":"_Получено: {n}/{total}_",
    "horo_title":"🌌 *Космогороскоп — {d}*",
    "horo_moon":"Луна:","horo_kp":"Kp-индекс:","horo_sign":"♾ *Ваш знак сегодня:*",
    "horo_aurora_high":"🌠 Высокий Kp: сегодня ночью возможно сияние!",
    "horo_energy_high":"🔴 Высокая космическая активность",
    "horo_energy_mod":"🟡 Умеренная космическая активность",
    "horo_energy_calm":"🟢 Спокойный космический день",
    "eq_title_eonet":"🌍 *Землетрясения NASA EONET (7 дней)*",
    "eq_title_usgs":"🌍 *Недавние землетрясения M≥5.0 (USGS)*",
    "eq_subscribe":"🔔 Подписаться на оповещения",
    "exo_loading":"🔭 Загружаю открытия...",
    "exo_title":"🔭 *Новые экзопланеты*",
    "exo_no_data":"Нет данных из архива NASA.",
    "exo_total":"Всего подтверждённых экзопланет: *5,700+*",
    "exo_recent":"🔭 *Недавние открытия экзопланет*",
    "exo_weekly":"🔔 Еженедельные оповещения",
    "sw_digest_title":"☀️ *Дайджест космической погоды*","sw_digest_loading":"☀️ Загрузка дайджеста...",
    "cancelled":"❌ Отменено",
    "capsule_chars_err":"❌ 5–2000 символов",
    "sat_tracker_title":"🛸 *Трекер спутников*","sat_tracker_choose":"Выбери аппарат:",
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
    "btn_news_esa":          "🛰 ESA",
    "btn_news_universetoday":"🪐 Universe Today",
    "btn_news_skytel":       "🔭 Sky & Telescope",
    "btn_news_next":"➡️ Next",
    "btn_news_source":"🔗 Source",
    "news_loading":"📰 Loading news...",
    "news_empty":"📭 No articles found",
    "news_counter":"Article {idx}/{total}",
    "btn_spacefact":"⭐ Space Fact", "btn_channels":"📢 Our Channels", "btn_lang":"🌍 Language",
    "title_profile":    "👤 My Profile",
    "btn_favorites":    "Favorites",
    "btn_mystats":      "My Stats",
    "btn_achievements": "Achievements",
    "btn_smart_alerts": "Smart Alerts",
    "btn_iss_schedule": "🌠 ISS over my city",
    "btn_meteorite_map":"🗺 Meteorite Map",
    "btn_flight_calc":  "🧮 Flight Calculator",
    "btn_mission_status":"📡 Mission Status",
    "btn_dictionary":   "📚 Space Dictionary",
    "btn_course":       "🎓 Astronomy 30 Days",
    "btn_earthquakes":  "🌍 Earthquakes",
    "btn_sat_tracker":  "🛸 Satellite Tracker",
    "btn_sw_digest":    "☀️ Space Weather Digest",
    "btn_exo_alert":    "🔭 New Exoplanets",
    "btn_challenge":    "🎯 Daily Challenge",
    "btn_rocket_game":  "👾 Land the Rocket",
    "btn_daily_horoscope":"🌌 Today's Horoscope",
    "btn_space_qa":     "💬 Ask about Space",
    "btn_profile":      "👤 Profile",
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
    # ── NEW: handler-level translations ──
    "telescopes_text":"🔬 *Space Telescopes*\n\n🌌 *JWST* — mirror 6.5m, orbit L2, infrared\n🔭 *Hubble* — mirror 2.4m, optical/UV, 600km orbit\n📡 *Chandra* — X-ray, high elliptical orbit\n🌊 *XMM-Newton* — X-ray, ESA\n🔭 *Spitzer* — infrared (retired 2020)\n📡 *VLT* — 4×8.2m, Atacama\n🌐 *FAST* — 500m radio dish, China\n🔭 *ELT (~2028)* — 39m mirror, ESA\n🌌 *Roman (~2027)* — wide-field infrared, NASA",
    "spacefact_title":"⭐ *Space Fact*",
    "meteors_title":"🌠 *Meteor Showers*",
    "moon_title":"🌙 *Moon Phase — {d}*",
    "moon_photo_tip":"📸 Photo tip: ISO 100, f/11, 1/250s",
    "satellites_text":"📡 *Satellites in Orbit*\n\n🌍 Total tracked: ~9,000+\n🛸 *Starlink:* {total} total, {active} active\n🔭 *Other constellations:* OneWeb, GPS, Galileo, GLONASS\n\n[🔗 n2yo.com — live tracking](https://www.n2yo.com)",
    "launches_title":"🚀 *Upcoming Launches*",
    "exoplanets_title":"🔭 *Exoplanets*",
    "spaceweather_text_title":"*Space Weather — Live*",
    "sw_calm":"🟢 Calm","sw_moderate":"🟡 Moderate","sw_strong":"🟠 Strong","sw_storm":"🔴 STORM",
    "kp_quiet":"🟢 Quiet","kp_minor":"🟡 Minor","kp_moderate":"🟠 Moderate","kp_strong":"🔴 Strong","kp_extreme":"🚨 G5",
    "aurora_polar":"Polar only","aurora_scandinavia":"Scandinavia/Canada","aurora_mid":"Mid-latitudes","aurora_equatorial":"Equatorial",
    "live_solar_wind_title":"🔴 *LIVE: Solar Wind*",
    "live_kp_title":"🔴 *LIVE: Kp-index*",
    "live_flares_title":"🔴 *LIVE: Solar Flares*",
    "live_iss_title":"🔴 *LIVE: ISS*",
    "live_radiation_title":"🔴 *LIVE: Radiation*",
    "live_aurora_title":"🔴 *Aurora Forecast*",
    "live_geomag_title":"🔴 *Geomagnetic Storms (2d)*",
    "live_sunspot_title":"🔴 *Sunspots (Cycle 25)*",
    "live_sunspot_text":"Wolf number: *{ssn}*\n\nCycle 25 near maximum — more flares.",
    "live_epic_title":"🌍 *EPIC Live — Earth*",
    "live_epic_desc":"DSCOVR satellite (L1).",
    "live_starlink_title":"🔴 *Starlink*\n\nTotal: *{total}*  |  Active: *{active}*\n\nAll satellites: ~9,000+ in orbit.",
    "planet_calc_title":"🪐 *Planet Calculator*",
    "planet_calc_earth":"🌍 *Earth:* {age} yrs  |  {weight} kg",
    "planet_calc_moon":"🌙 *Moon:* ⚖️ {w} kg (16.5% gravity)",
    "planet_calc_days":"💡 You've lived *{days}* Earth days!",
    "name_callsign":"👨‍🚀 *Callsign:*","name_star":"⭐ *Your star:*",
    "name_constellation":"📡 Constellation: {c}  |  Spectral: {s}","name_distance":"📍 Distance: {d} light-years",
    "rover_active":"🟢 Active","rover_inactive":"⚪ Inactive",
    "rover_landing":"🛬 Landing:","rover_sol":"☀️ Sol:","rover_photos":"📷 Photos:",
    "quiz_question_title":"🧠 *Question {n}/10*",
    "challenge_title":"🎯 *Daily Challenge*","challenge_question":"❓ *What is this object?*",
    "challenge_result_title":"🎯 *Challenge Result*","challenge_correct":"✅ Correct!",
    "challenge_wrong":"❌ Wrong! Answer: *{ans}*","challenge_loading":"⏳ Loading challenge image...",
    "challenge_next":"🎯 Next challenge",
    "rocket_title":"🚀 *Falcon 9 Landing Simulator*","rocket_step_label":"━━ Step {n}/{total} ━━",
    "rocket_what_do":"*What do you do?*","rocket_abort":"❌ Abort mission",
    "rocket_boom":"💥 *BOOOM!*","rocket_wrong_call":"❌ Wrong call at step {n}.",
    "rocket_crashed":"The Falcon 9 crashed into the drone ship. Try again!",
    "rocket_rsd":"🔧 SpaceX calls this a 'rapid unscheduled disassembly'.",
    "rocket_try_again":"🔄 Try again","rocket_good_call":"✅ *Good call!*",
    "rocket_next":"➡️ Next step...","rocket_touchdown":"🎉 *TOUCHDOWN! PERFECT LANDING!*",
    "rocket_landed":"✅ Falcon 9 successfully landed on the drone ship!",
    "rocket_fuel":"⛽ Fuel remaining: 3%  |  Speed at touchdown: 2 m/s",
    "rocket_mastered":"🏅 You've mastered the Falcon 9 landing algorithm.",
    "rocket_since2015":"_SpaceX does this routinely since 2015!_",
    "rocket_play_again":"🔄 Play again",
    "qa_chars_error":"❌ 3–500 chars","qa_thinking":"🤔 Thinking...","qa_cancelled":"❌ Cancelled",
    "qa_ask_another":"❓ Ask another","qa_api_error":"❌ Claude API key not configured.",
    "fav_saved":"⭐ Saved!","fav_max":"❌ Max 50 favorites",
    "fav_title":"⭐ *Favorites*","fav_empty":"No saved photos yet.\nTap ⭐ on any APOD to save it!",
    "fav_your":"⭐ *Your Favorites*","fav_total":"_Total: {n} photos_",
    "fav_clear":"🗑 Clear all","fav_cleared":"🗑 Favorites cleared.",
    "smart_title":"🔔 *Smart Alerts Settings*",
    "smart_kp_desc":"⚡ Kp alert when ≥ *{v}* (aurora visible)",
    "smart_ast_desc":"☄️ Asteroid alert when < *{v}* LD",
    "smart_eq_desc":"🌍 Earthquake alert when M ≥ *{v}*",
    "smart_tap":"_Tap to change a threshold:_",
    "smart_kp_ask":"⚡ Send Kp threshold (1–9, e.g. *5* for moderate aurora):",
    "smart_ld_ask":"☄️ Send asteroid LD threshold (1–10, e.g. *2* = within 2 lunar distances):",
    "smart_eq_ask":"🌍 Send earthquake M threshold (4–9, e.g. *6*):",
    "smart_kp_err":"❌ Enter 1–9","smart_ld_err":"❌ Enter 0.5–20","smart_eq_err":"❌ Enter 4–9",
    "smart_kp_set":"✅ Kp alert set to ≥ *{v}*",
    "smart_ld_set":"✅ Asteroid alert set to < *{v} LD*",
    "smart_eq_set":"✅ Earthquake alert set to M ≥ *{v}*",
    "smart_back":"🔔 Back to alerts",
    "stats_title":"📊 *My Space Stats*",
    "stats_apod":"📸 APOD viewed:","stats_quiz":"🧠 Quizzes taken:",
    "stats_perfect":"🏆 Perfect quizzes:","stats_challenge":"🎯 Challenges done:",
    "stats_favorites":"⭐ Favorites saved:","stats_achievements":"🏅 Achievements:",
    "stats_streak":"🔥 Current streak:","stats_streak_days":"days",
    "stats_since":"📅 Active since:",
    "iss_sched_title":"🌠 *ISS Visibility Schedule*","iss_sched_enter":"Enter your city name:",
    "iss_sched_examples":"_Examples: {cities}_",
    "iss_sched_not_found":"❌ City not found. Try: Moscow, London, Tokyo, Tel Aviv, Dubai...",
    "iss_sched_over":"🌠 *ISS over {city}*",
    "iss_sched_api_na":"⚠️ Pass prediction API unavailable.",
    "iss_sched_position":"📍 ISS current position:","iss_sched_alt":"Altitude: ~408 km",
    "iss_sched_orbit":"🔄 ISS completes one orbit every ~92 min.",
    "iss_sched_passes":"⬆️ *Upcoming passes:*",
    "iss_sched_times":"_Times are local UTC. ISS moves at 28,000 km/h._",
    "meteor_map_title":"🗺 *Top 10 Meteorites (NASA Database)*",
    "meteor_map_famous":"🗺 *Famous Meteorites*",
    "flight_title":"🧮 *Flight Calculator*","flight_choose":"Choose your destination:",
    "flight_to":"🚀 To *{name}* ({desc})\n\nChoose your spacecraft speed:",
    "flight_result_title":"🧮 *Flight Calculator Result*",
    "flight_from":"📍 From: Earth  →  {name}","flight_distance":"📏 Distance: {km} km",
    "flight_speed_label":"⚡ Speed: {name} ({kmh} km/h)",
    "flight_time":"🕐 Travel time: *{t}*",
    "flight_another":"🔄 Calculate another",
    "flight_grandchildren":"_Your great-great-grandchildren would arrive._",
    "flight_lightspeed":"_At lightspeed — still 2.5 million years!_",
    "flight_fuel":"_You'd need fuel worth more than the GDP of Earth._",
    "missions_title":"📡 *Active Space Missions*","missions_select":"Select to learn more:",
    "missions_all":"◀️ All missions","missions_learn":"🔗 Learn more",
    "dict_title":"📚 *Space Dictionary*","dict_choose":"Choose a term:",
    "dict_funfact":"💡 *Fun fact:*",
    "course_title":"🎓 *Astronomy in 30 Days*",
    "course_desc":"A daily lesson delivered to your inbox — from the Solar System to the cosmic web.",
    "course_subscribe_btn":"🎓 Subscribe to course","course_browse_btn":"📚 Browse all lessons",
    "course_already":"🎓 Already subscribed! You're on Day *{day}/30*.\nNext lesson comes daily at 10:00.",
    "course_subscribed":"✅ *Subscribed to 30-Day Astronomy Course!*\n\nHere's your first lesson:",
    "course_all":"📚 *All 30 Lessons*","course_day":"🎓 *Day {day}/30 — Astronomy Course*",
    "ach_title":"🏆 *Achievements*","ach_earned":"_Earned: {n}/{total}_",
    "horo_title":"🌌 *Space Horoscope — {d}*",
    "horo_moon":"Moon:","horo_kp":"Kp-index:","horo_sign":"♾ *Your sign today:*",
    "horo_aurora_high":"🌠 High Kp: Aurora possible tonight!",
    "horo_energy_high":"🔴 High cosmic activity",
    "horo_energy_mod":"🟡 Moderate cosmic activity",
    "horo_energy_calm":"🟢 Calm cosmic day",
    "eq_title_eonet":"🌍 *NASA EONET Earthquakes (7 days)*",
    "eq_title_usgs":"🌍 *Recent Earthquakes M≥5.0 (USGS)*",
    "eq_subscribe":"🔔 Subscribe alerts",
    "exo_loading":"🔭 Loading discoveries...",
    "exo_title":"🔭 *New Exoplanet Discoveries*",
    "exo_no_data":"No recent data available from NASA Archive.",
    "exo_total":"Total confirmed exoplanets: *5,700+*",
    "exo_recent":"🔭 *Recent Exoplanet Discoveries*",
    "exo_weekly":"🔔 Weekly alerts",
    "sw_digest_title":"☀️ *Space Weather Digest*","sw_digest_loading":"☀️ Loading digest...",
    "cancelled":"❌ Cancelled",
    "capsule_chars_err":"❌ 5–2000 chars",
    "sat_tracker_title":"🛸 *Satellite Tracker*","sat_tracker_choose":"Select a spacecraft:",
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
    "btn_news_esa":          "🛰 ESA",
    "btn_news_universetoday":"🪐 Universe Today",
    "btn_news_skytel":       "🔭 Sky & Tel",
    "btn_news_next":"➡️ הבא",
    "btn_news_source":"🔗 מקור",
    "news_loading":"📰 טוען חדשות...",
    "news_empty":"📭 לא נמצאו כתבות",
    "news_counter":"כתבה {idx}/{total}",
    "btn_spacefact":"⭐ עובדה", "btn_channels":"📢 ערוצים", "btn_lang":"🌍 שפה",
    "title_profile":    "👤 הפרופיל שלי",
    "btn_favorites":    "מועדפים",
    "btn_mystats":      "הסטטיסטיקה שלי",
    "btn_achievements": "הישגים",
    "btn_smart_alerts": "התראות חכמות",
    "btn_iss_schedule": "🌠 תחנת החלל מעל עירי",
    "btn_meteorite_map":"🗺 מפת מטאוריטים",
    "btn_flight_calc":  "🧮 מחשבון טיסה",
    "btn_mission_status":"📡 סטטוס משימות",
    "btn_dictionary":   "📚 מילון חלל",
    "btn_course":       "🎓 אסטרונומיה 30 ימים",
    "btn_earthquakes":  "🌍 רעידות אדמה",
    "btn_sat_tracker":  "🛸 עוקב לוויינים",
    "btn_sw_digest":    "☀️ תקציר מזג אוויר חלל",
    "btn_exo_alert":    "🔭 כוכבי לכת חדשים",
    "btn_challenge":    "🎯 אתגר יומי",
    "btn_rocket_game":  "👾 נחות את הרקטה",
    "btn_daily_horoscope":"🌌 הורוסקופ היום",
    "btn_space_qa":     "💬 שאל על חלל",
    "btn_profile":      "👤 פרופיל",
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
    # ── NEW: handler-level translations ──
    "telescopes_text":"🔬 *טלסקופים בחלל*\n\n🌌 *JWST* — מראה 6.5מ', מסלול L2, אינפרא-אדום\n🔭 *האבל* — מראה 2.4מ', אופטי/UV, 600 ק\"מ\n📡 *צ'נדרה* — רנטגן, מסלול אליפטי\n🌊 *XMM-Newton* — רנטגן, ESA\n🔭 *ספיצר* — אינפרא-אדום (הושבת 2020)\n📡 *VLT* — 4×8.2מ', אטקמה\n🌐 *FAST* — צלחת רדיו 500מ', סין\n🔭 *ELT (~2028)* — מראה 39מ', ESA\n🌌 *רומן (~2027)* — רחב שדה, NASA",
    "spacefact_title":"⭐ *עובדה מהחלל*",
    "meteors_title":"🌠 *גשמי מטאורים*",
    "moon_title":"🌙 *שלב הירח — {d}*",
    "moon_photo_tip":"📸 טיפ צילום: ISO 100, f/11, 1/250s",
    "satellites_text":"📡 *לוויינים במסלול*\n\n🌍 סה\"כ: ~9,000+\n🛸 *Starlink:* {total} סה\"כ, {active} פעילים\n🔭 *אחרים:* OneWeb, GPS, Galileo, GLONASS\n\n[🔗 n2yo.com](https://www.n2yo.com)",
    "launches_title":"🚀 *שיגורים קרובים*",
    "exoplanets_title":"🔭 *כוכבי לכת חוץ-שמשיים*",
    "spaceweather_text_title":"*מזג אוויר חלל — Live*",
    "sw_calm":"🟢 רגוע","sw_moderate":"🟡 בינוני","sw_strong":"🟠 חזק","sw_storm":"🔴 סערה",
    "kp_quiet":"🟢 רגוע","kp_minor":"🟡 קל","kp_moderate":"🟠 בינוני","kp_strong":"🔴 חזק","kp_extreme":"🚨 קיצוני",
    "aurora_polar":"קוטבי בלבד","aurora_scandinavia":"סקנדינביה/קנדה","aurora_mid":"רוחב ביניים","aurora_equatorial":"קו המשווה",
    "live_solar_wind_title":"🔴 *LIVE: רוח סולארית*",
    "live_kp_title":"🔴 *LIVE: מדד Kp*",
    "live_flares_title":"🔴 *LIVE: להבות סולאריות*",
    "live_iss_title":"🔴 *LIVE: ISS*",
    "live_radiation_title":"🔴 *LIVE: קרינה*",
    "live_aurora_title":"🔴 *תחזית זוהר*",
    "live_geomag_title":"🔴 *סערות גיאומגנטיות (יומיים)*",
    "live_sunspot_title":"🔴 *כתמי שמש (מחזור 25)*",
    "live_sunspot_text":"מספר וולף: *{ssn}*\n\nמחזור 25 קרוב למקסימום — יותר להבות.",
    "live_epic_title":"🌍 *EPIC Live — כדור הארץ*",
    "live_epic_desc":"לוויין DSCOVR (L1).",
    "live_starlink_title":"🔴 *Starlink*\n\nסה\"כ: *{total}*  |  פעילים: *{active}*\n\nכל הלוויינים: ~9,000+ במסלול.",
    "planet_calc_title":"🪐 *מחשבון כוכבים*",
    "planet_calc_earth":"🌍 *כדור הארץ:* {age} שנים  |  {weight} ק\"ג",
    "planet_calc_moon":"🌙 *ירח:* ⚖️ {w} ק\"ג (16.5% כבידה)",
    "planet_calc_days":"💡 חיית *{days}* ימי כדור הארץ!",
    "name_callsign":"👨‍🚀 *קוד קריאה:*","name_star":"⭐ *הכוכב שלך:*",
    "name_constellation":"📡 קבוצת כוכבים: {c}  |  ספקטרלי: {s}","name_distance":"📍 מרחק: {d} שנות אור",
    "rover_active":"🟢 פעיל","rover_inactive":"⚪ לא פעיל",
    "rover_landing":"🛬 נחיתה:","rover_sol":"☀️ Sol:","rover_photos":"📷 תמונות:",
    "quiz_question_title":"🧠 *שאלה {n}/10*",
    "challenge_title":"🎯 *אתגר יומי*","challenge_question":"❓ *מה האובייקט הזה?*",
    "challenge_result_title":"🎯 *תוצאת האתגר*","challenge_correct":"✅ נכון!",
    "challenge_wrong":"❌ לא נכון! תשובה: *{ans}*","challenge_loading":"⏳ טוען תמונת אתגר...",
    "challenge_next":"🎯 אתגר הבא",
    "rocket_title":"🚀 *סימולטור נחיתת Falcon 9*","rocket_step_label":"━━ שלב {n}/{total} ━━",
    "rocket_what_do":"*מה אתה עושה?*","rocket_abort":"❌ ביטול משימה",
    "rocket_boom":"💥 *בוום!*","rocket_wrong_call":"❌ החלטה שגויה בשלב {n}.",
    "rocket_crashed":"Falcon 9 התרסק על ספינת הנחיתה. נסה שוב!",
    "rocket_rsd":"🔧 SpaceX קוראים לזה 'פירוק לא מתוכנן מהיר'.",
    "rocket_try_again":"🔄 נסה שוב","rocket_good_call":"✅ *החלטה טובה!*",
    "rocket_next":"➡️ שלב הבא...","rocket_touchdown":"🎉 *נחיתה! מושלמת!*",
    "rocket_landed":"✅ Falcon 9 נחת בהצלחה על ספינת הנחיתה!",
    "rocket_fuel":"⛽ דלק שנשאר: 3%  |  מהירות נחיתה: 2 מ'/ש'",
    "rocket_mastered":"🏅 שלטת באלגוריתם הנחיתה של Falcon 9.",
    "rocket_since2015":"_SpaceX עושים את זה שגרתית מ-2015!_",
    "rocket_play_again":"🔄 שחק שוב",
    "qa_chars_error":"❌ 3–500 תווים","qa_thinking":"🤔 חושב...","qa_cancelled":"❌ בוטל",
    "qa_ask_another":"❓ שאל עוד","qa_api_error":"❌ מפתח API לא מוגדר.",
    "fav_saved":"⭐ נשמר!","fav_max":"❌ מקסימום 50 מועדפים",
    "fav_title":"⭐ *מועדפים*","fav_empty":"אין תמונות שמורות עדיין.\nלחץ ⭐ על כל APOD כדי לשמור!",
    "fav_your":"⭐ *המועדפים שלך*","fav_total":"_סה\"כ: {n} תמונות_",
    "fav_clear":"🗑 מחק הכל","fav_cleared":"🗑 המועדפים נמחקו.",
    "smart_title":"🔔 *הגדרות התראות חכמות*",
    "smart_kp_desc":"⚡ התראת Kp כש- ≥ *{v}* (זוהר נראה)",
    "smart_ast_desc":"☄️ התראת אסטרואיד כש- < *{v}* LD",
    "smart_eq_desc":"🌍 התראת רעידת אדמה כש- M ≥ *{v}*",
    "smart_tap":"_לחץ לשינוי סף:_",
    "smart_kp_ask":"⚡ שלח סף Kp (1–9, למשל *5* לזוהר בינוני):",
    "smart_ld_ask":"☄️ שלח סף LD (1–10, למשל *2* = 2 מרחקי ירח):",
    "smart_eq_ask":"🌍 שלח סף מגניטודה (4–9, למשל *6*):",
    "smart_kp_err":"❌ הכנס 1–9","smart_ld_err":"❌ הכנס 0.5–20","smart_eq_err":"❌ הכנס 4–9",
    "smart_kp_set":"✅ התראת Kp הוגדרה ל- ≥ *{v}*",
    "smart_ld_set":"✅ התראת אסטרואיד הוגדרה ל- < *{v} LD*",
    "smart_eq_set":"✅ התראת רעידה הוגדרה ל- M ≥ *{v}*",
    "smart_back":"🔔 חזרה להתראות",
    "stats_title":"📊 *הסטטיסטיקה שלי*",
    "stats_apod":"📸 APOD נצפו:","stats_quiz":"🧠 חידונים:",
    "stats_perfect":"🏆 חידונים מושלמים:","stats_challenge":"🎯 אתגרים:",
    "stats_favorites":"⭐ מועדפים:","stats_achievements":"🏅 הישגים:",
    "stats_streak":"🔥 רצף נוכחי:","stats_streak_days":"ימים",
    "stats_since":"📅 פעיל מאז:",
    "iss_sched_title":"🌠 *לוח מעברי ISS*","iss_sched_enter":"הכנס שם עיר:",
    "iss_sched_examples":"_דוגמאות: {cities}_",
    "iss_sched_not_found":"❌ עיר לא נמצאה. נסה: Moscow, London, Tokyo, Tel Aviv, Dubai...",
    "iss_sched_over":"🌠 *ISS מעל {city}*",
    "iss_sched_api_na":"⚠️ API חיזוי מעברים לא זמין.",
    "iss_sched_position":"📍 מיקום ISS נוכחי:","iss_sched_alt":"גובה: ~408 ק\"מ",
    "iss_sched_orbit":"🔄 ISS משלים מסלול כל ~92 דקות.",
    "iss_sched_passes":"⬆️ *מעברים קרובים:*",
    "iss_sched_times":"_הזמנים ב-UTC. ISS נע ב-28,000 קמ\"ש._",
    "meteor_map_title":"🗺 *10 מטאוריטים גדולים (NASA)*",
    "meteor_map_famous":"🗺 *מטאוריטים מפורסמים*",
    "flight_title":"🧮 *מחשבון טיסה*","flight_choose":"בחר יעד:",
    "flight_to":"🚀 אל *{name}* ({desc})\n\nבחר מהירות:",
    "flight_result_title":"🧮 *תוצאת מחשבון טיסה*",
    "flight_from":"📍 מ: כדור הארץ  →  {name}","flight_distance":"📏 מרחק: {km} ק\"מ",
    "flight_speed_label":"⚡ מהירות: {name} ({kmh} קמ\"ש)",
    "flight_time":"🕐 זמן נסיעה: *{t}*",
    "flight_another":"🔄 חישוב נוסף",
    "flight_grandchildren":"_הנינים שלך יגיעו._",
    "flight_lightspeed":"_במהירות האור — עדיין 2.5 מיליון שנה!_",
    "flight_fuel":"_דלק בעלות גבוהה מהתמ\"ג של כדור הארץ._",
    "missions_title":"📡 *משימות חלל פעילות*","missions_select":"בחר למידע נוסף:",
    "missions_all":"◀️ כל המשימות","missions_learn":"🔗 למידע נוסף",
    "dict_title":"📚 *מילון חלל*","dict_choose":"בחר מונח:",
    "dict_funfact":"💡 *עובדה מעניינת:*",
    "course_title":"🎓 *אסטרונומיה ב-30 ימים*",
    "course_desc":"שיעור יומי — ממערכת השמש ועד הרשת הקוסמית.",
    "course_subscribe_btn":"🎓 הרשמה לקורס","course_browse_btn":"📚 כל השיעורים",
    "course_already":"🎓 כבר רשום! אתה ביום *{day}/30*.\nהשיעור הבא ב-10:00.",
    "course_subscribed":"✅ *נרשמת לקורס אסטרונומיה 30 ימים!*\n\nהנה השיעור הראשון:",
    "course_all":"📚 *כל 30 השיעורים*","course_day":"🎓 *יום {day}/30 — קורס אסטרונומיה*",
    "ach_title":"🏆 *הישגים*","ach_earned":"_הושגו: {n}/{total}_",
    "horo_title":"🌌 *הורוסקופ חלל — {d}*",
    "horo_moon":"ירח:","horo_kp":"מדד Kp:","horo_sign":"♾ *המזל שלך היום:*",
    "horo_aurora_high":"🌠 Kp גבוה: זוהר אפשרי הלילה!",
    "horo_energy_high":"🔴 פעילות קוסמית גבוהה",
    "horo_energy_mod":"🟡 פעילות קוסמית בינונית",
    "horo_energy_calm":"🟢 יום קוסמי רגוע",
    "eq_title_eonet":"🌍 *רעידות אדמה NASA EONET (7 ימים)*",
    "eq_title_usgs":"🌍 *רעידות אחרונות M≥5.0 (USGS)*",
    "eq_subscribe":"🔔 הרשמה להתראות",
    "exo_loading":"🔭 טוען גילויים...",
    "exo_title":"🔭 *גילויי כוכבי לכת חדשים*",
    "exo_no_data":"אין נתונים עדכניים מארכיון NASA.",
    "exo_total":"סה\"כ כוכבי לכת מאושרים: *5,700+*",
    "exo_recent":"🔭 *גילויים אחרונים*",
    "exo_weekly":"🔔 התראות שבועיות",
    "sw_digest_title":"☀️ *תקציר מזג חלל*","sw_digest_loading":"☀️ טוען תקציר...",
    "cancelled":"❌ בוטל",
    "capsule_chars_err":"❌ 5–2000 תווים",
    "sat_tracker_title":"🛸 *עוקב לוויינים*","sat_tracker_choose":"בחר חללית:",
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
    "btn_news_esa":          "🛰 ESA",
    "btn_news_universetoday":"🪐 Universe Today",
    "btn_news_skytel":       "🔭 Sky & Tel",
    "btn_news_next":"➡️ التالي",
    "btn_news_source":"🔗 المصدر",
    "news_loading":"📰 جاري تحميل الأخبار...",
    "news_empty":"📭 لا توجد مقالات",
    "news_counter":"مقالة {idx}/{total}",
    "btn_spacefact":"⭐ حقيقة", "btn_channels":"📢 قنواتنا", "btn_lang":"🌍 اللغة",
   "title_profile":    "👤 ملفي الشخصي",
    "btn_favorites":    "المفضلة",
    "btn_mystats":      "إحصائياتي",
    "btn_achievements": "الإنجازات",
    "btn_smart_alerts": "تنبيهات ذكية",
    "btn_iss_schedule": "🌠 محطة الفضاء فوق مدينتي",
    "btn_meteorite_map":"🗺 خريطة النيازك",
    "btn_flight_calc":  "🧮 حاسبة الرحلة",
    "btn_mission_status":"📡 حالة المهمات",
    "btn_dictionary":   "📚 قاموس الفضاء",
    "btn_course":       "🎓 علم الفلك 30 يوماً",
    "btn_earthquakes":  "🌍 الزلازل",
    "btn_sat_tracker":  "🛸 متتبع الأقمار",
    "btn_sw_digest":    "☀️ ملخص طقس الفضاء",
    "btn_exo_alert":    "🔭 كواكب خارجية جديدة",
    "btn_challenge":    "🎯 تحدي يومي",
    "btn_rocket_game":  "👾 أهبط الصاروخ",
    "btn_daily_horoscope":"🌌 برج اليوم",
    "btn_space_qa":     "💬 اسأل عن الفضاء",
    "btn_profile":      "👤 الملف الشخصي",
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
    # ── NEW: handler-level translations ──
    "telescopes_text":"🔬 *تلسكوبات الفضاء*\n\n🌌 *JWST* — مرآة 6.5م، مدار L2، الأشعة تحت الحمراء\n🔭 *هابل* — مرآة 2.4م، بصري/فوق بنفسجي، 600 كم\n📡 *تشاندرا* — أشعة سينية، مدار إهليلجي\n🌊 *XMM-Newton* — أشعة سينية، ESA\n🔭 *سبيتزر* — تحت الحمراء (تقاعد 2020)\n📡 *VLT* — 4×8.2م، أتاكاما\n🌐 *FAST* — طبق راديو 500م، الصين\n🔭 *ELT (~2028)* — مرآة 39م، ESA\n🌌 *رومان (~2027)* — واسع المجال، NASA",
    "spacefact_title":"⭐ *حقيقة فضائية*",
    "meteors_title":"🌠 *زخات الشهب*",
    "moon_title":"🌙 *مرحلة القمر — {d}*",
    "moon_photo_tip":"📸 نصيحة: ISO 100, f/11, 1/250s",
    "satellites_text":"📡 *أقمار في المدار*\n\n🌍 المتعقّب: ~9,000+\n🛸 *Starlink:* {total} إجمالي، {active} نشط\n🔭 *أخرى:* OneWeb, GPS, Galileo, GLONASS\n\n[🔗 n2yo.com](https://www.n2yo.com)",
    "launches_title":"🚀 *إطلاقات قادمة*",
    "exoplanets_title":"🔭 *كواكب خارجية*",
    "spaceweather_text_title":"*طقس الفضاء — مباشر*",
    "sw_calm":"🟢 هادئ","sw_moderate":"🟡 معتدل","sw_strong":"🟠 قوي","sw_storm":"🔴 عاصفة",
    "kp_quiet":"🟢 هادئ","kp_minor":"🟡 طفيف","kp_moderate":"🟠 معتدل","kp_strong":"🔴 قوي","kp_extreme":"🚨 شديد",
    "aurora_polar":"القطب فقط","aurora_scandinavia":"سكندنافيا/كندا","aurora_mid":"خطوط العرض الوسطى","aurora_equatorial":"خط الاستواء",
    "live_solar_wind_title":"🔴 *مباشر: الرياح الشمسية*",
    "live_kp_title":"🔴 *مباشر: مؤشر Kp*",
    "live_flares_title":"🔴 *مباشر: التوهجات الشمسية*",
    "live_iss_title":"🔴 *مباشر: محطة الفضاء*",
    "live_radiation_title":"🔴 *مباشر: الإشعاع*",
    "live_aurora_title":"🔴 *توقعات الشفق*",
    "live_geomag_title":"🔴 *العواصف المغناطيسية (يومان)*",
    "live_sunspot_title":"🔴 *البقع الشمسية (الدورة 25)*",
    "live_sunspot_text":"رقم وولف: *{ssn}*\n\nالدورة 25 قرب الذروة — المزيد من التوهجات.",
    "live_epic_title":"🌍 *EPIC مباشر — الأرض*",
    "live_epic_desc":"القمر الصناعي DSCOVR (L1).",
    "live_starlink_title":"🔴 *Starlink*\n\nالإجمالي: *{total}*  |  النشط: *{active}*\n\nكل الأقمار: ~9,000+ في المدار.",
    "planet_calc_title":"🪐 *حاسبة الكواكب*",
    "planet_calc_earth":"🌍 *الأرض:* {age} سنة  |  {weight} كغ",
    "planet_calc_moon":"🌙 *القمر:* ⚖️ {w} كغ (16.5% جاذبية)",
    "planet_calc_days":"💡 عشت *{days}* يوماً أرضياً!",
    "name_callsign":"👨‍🚀 *رمز النداء:*","name_star":"⭐ *نجمك:*",
    "name_constellation":"📡 كوكبة: {c}  |  طيفي: {s}","name_distance":"📍 المسافة: {d} سنة ضوئية",
    "rover_active":"🟢 نشط","rover_inactive":"⚪ غير نشط",
    "rover_landing":"🛬 هبوط:","rover_sol":"☀️ Sol:","rover_photos":"📷 صور:",
    "quiz_question_title":"🧠 *سؤال {n}/10*",
    "challenge_title":"🎯 *تحدي يومي*","challenge_question":"❓ *ما هذا الجسم؟*",
    "challenge_result_title":"🎯 *نتيجة التحدي*","challenge_correct":"✅ صحيح!",
    "challenge_wrong":"❌ خطأ! الإجابة: *{ans}*","challenge_loading":"⏳ جاري تحميل صورة التحدي...",
    "challenge_next":"🎯 التحدي التالي",
    "rocket_title":"🚀 *محاكي هبوط Falcon 9*","rocket_step_label":"━━ خطوة {n}/{total} ━━",
    "rocket_what_do":"*ماذا تفعل؟*","rocket_abort":"❌ إلغاء المهمة",
    "rocket_boom":"💥 *بوووم!*","rocket_wrong_call":"❌ قرار خاطئ في الخطوة {n}.",
    "rocket_crashed":"Falcon 9 تحطم على سفينة الهبوط. حاول مرة أخرى!",
    "rocket_rsd":"🔧 SpaceX يسمون هذا 'تفكيك سريع غير مجدول'.",
    "rocket_try_again":"🔄 حاول مرة أخرى","rocket_good_call":"✅ *قرار صائب!*",
    "rocket_next":"➡️ الخطوة التالية...","rocket_touchdown":"🎉 *هبوط! مثالي!*",
    "rocket_landed":"✅ Falcon 9 هبط بنجاح على سفينة الهبوط!",
    "rocket_fuel":"⛽ الوقود المتبقي: 3%  |  سرعة الهبوط: 2 م/ث",
    "rocket_mastered":"🏅 أتقنت خوارزمية هبوط Falcon 9.",
    "rocket_since2015":"_SpaceX يفعلون هذا بشكل روتيني منذ 2015!_",
    "rocket_play_again":"🔄 العب مرة أخرى",
    "qa_chars_error":"❌ 3–500 حرف","qa_thinking":"🤔 أفكر...","qa_cancelled":"❌ تم الإلغاء",
    "qa_ask_another":"❓ اسأل مجدداً","qa_api_error":"❌ مفتاح API غير مُعدّ.",
    "fav_saved":"⭐ تم الحفظ!","fav_max":"❌ الحد الأقصى 50 مفضلة",
    "fav_title":"⭐ *المفضلة*","fav_empty":"لا توجد صور محفوظة بعد.\nاضغط ⭐ على أي APOD لحفظها!",
    "fav_your":"⭐ *مفضلاتك*","fav_total":"_الإجمالي: {n} صورة_",
    "fav_clear":"🗑 مسح الكل","fav_cleared":"🗑 تم مسح المفضلة.",
    "smart_title":"🔔 *إعدادات التنبيهات الذكية*",
    "smart_kp_desc":"⚡ تنبيه Kp عند ≥ *{v}* (شفق مرئي)",
    "smart_ast_desc":"☄️ تنبيه كويكب عند < *{v}* LD",
    "smart_eq_desc":"🌍 تنبيه زلزال عند M ≥ *{v}*",
    "smart_tap":"_اضغط لتغيير الحد:_",
    "smart_kp_ask":"⚡ أرسل حد Kp (1–9، مثلاً *5* لشفق معتدل):",
    "smart_ld_ask":"☄️ أرسل حد LD (1–10، مثلاً *2* = مسافتين قمريتين):",
    "smart_eq_ask":"🌍 أرسل حد المقدار (4–9، مثلاً *6*):",
    "smart_kp_err":"❌ أدخل 1–9","smart_ld_err":"❌ أدخل 0.5–20","smart_eq_err":"❌ أدخل 4–9",
    "smart_kp_set":"✅ تنبيه Kp ضُبط على ≥ *{v}*",
    "smart_ld_set":"✅ تنبيه الكويكب ضُبط على < *{v} LD*",
    "smart_eq_set":"✅ تنبيه الزلزال ضُبط على M ≥ *{v}*",
    "smart_back":"🔔 العودة للتنبيهات",
    "stats_title":"📊 *إحصائياتي الفضائية*",
    "stats_apod":"📸 APOD شوهدت:","stats_quiz":"🧠 اختبارات:",
    "stats_perfect":"🏆 اختبارات مثالية:","stats_challenge":"🎯 تحديات:",
    "stats_favorites":"⭐ المفضلة:","stats_achievements":"🏅 إنجازات:",
    "stats_streak":"🔥 السلسلة الحالية:","stats_streak_days":"أيام",
    "stats_since":"📅 نشط منذ:",
    "iss_sched_title":"🌠 *جدول رؤية ISS*","iss_sched_enter":"أدخل اسم مدينتك:",
    "iss_sched_examples":"_أمثلة: {cities}_",
    "iss_sched_not_found":"❌ المدينة غير موجودة. جرب: Moscow, London, Tokyo, Tel Aviv, Dubai...",
    "iss_sched_over":"🌠 *ISS فوق {city}*",
    "iss_sched_api_na":"⚠️ واجهة توقع المرور غير متاحة.",
    "iss_sched_position":"📍 موقع ISS الحالي:","iss_sched_alt":"الارتفاع: ~408 كم",
    "iss_sched_orbit":"🔄 ISS يكمل مداراً كل ~92 دقيقة.",
    "iss_sched_passes":"⬆️ *المرور القادم:*",
    "iss_sched_times":"_الأوقات بتوقيت UTC. ISS يتحرك بسرعة 28,000 كم/ساعة._",
    "meteor_map_title":"🗺 *أكبر 10 نيازك (قاعدة NASA)*",
    "meteor_map_famous":"🗺 *نيازك مشهورة*",
    "flight_title":"🧮 *حاسبة الرحلة*","flight_choose":"اختر وجهتك:",
    "flight_to":"🚀 إلى *{name}* ({desc})\n\nاختر سرعة مركبتك:",
    "flight_result_title":"🧮 *نتيجة حاسبة الرحلة*",
    "flight_from":"📍 من: الأرض  →  {name}","flight_distance":"📏 المسافة: {km} كم",
    "flight_speed_label":"⚡ السرعة: {name} ({kmh} كم/ساعة)",
    "flight_time":"🕐 وقت السفر: *{t}*",
    "flight_another":"🔄 حساب آخر",
    "flight_grandchildren":"_أحفاد أحفادك سيصلون._",
    "flight_lightspeed":"_بسرعة الضوء — لا يزال 2.5 مليون سنة!_",
    "flight_fuel":"_ستحتاج وقوداً بقيمة أكثر من الناتج المحلي للأرض._",
    "missions_title":"📡 *مهمات فضائية نشطة*","missions_select":"اختر لمعرفة المزيد:",
    "missions_all":"◀️ كل المهمات","missions_learn":"🔗 اعرف المزيد",
    "dict_title":"📚 *قاموس الفضاء*","dict_choose":"اختر مصطلحاً:",
    "dict_funfact":"💡 *حقيقة ممتعة:*",
    "course_title":"🎓 *علم الفلك في 30 يوماً*",
    "course_desc":"درس يومي — من المجموعة الشمسية إلى الشبكة الكونية.",
    "course_subscribe_btn":"🎓 اشترك في الدورة","course_browse_btn":"📚 كل الدروس",
    "course_already":"🎓 أنت مشترك بالفعل! أنت في اليوم *{day}/30*.\nالدرس القادم في 10:00.",
    "course_subscribed":"✅ *اشتركت في دورة علم الفلك 30 يوماً!*\n\nإليك الدرس الأول:",
    "course_all":"📚 *كل 30 درساً*","course_day":"🎓 *اليوم {day}/30 — دورة علم الفلك*",
    "ach_title":"🏆 *الإنجازات*","ach_earned":"_المكتسبة: {n}/{total}_",
    "horo_title":"🌌 *برج الفضاء — {d}*",
    "horo_moon":"القمر:","horo_kp":"مؤشر Kp:","horo_sign":"♾ *برجك اليوم:*",
    "horo_aurora_high":"🌠 Kp عالٍ: شفق محتمل الليلة!",
    "horo_energy_high":"🔴 نشاط كوني عالٍ",
    "horo_energy_mod":"🟡 نشاط كوني معتدل",
    "horo_energy_calm":"🟢 يوم كوني هادئ",
    "eq_title_eonet":"🌍 *زلازل NASA EONET (7 أيام)*",
    "eq_title_usgs":"🌍 *زلازل حديثة M≥5.0 (USGS)*",
    "eq_subscribe":"🔔 اشترك في التنبيهات",
    "exo_loading":"🔭 جاري تحميل الاكتشافات...",
    "exo_title":"🔭 *اكتشافات كواكب جديدة*",
    "exo_no_data":"لا تتوفر بيانات حديثة من أرشيف NASA.",
    "exo_total":"إجمالي الكواكب المؤكدة: *5,700+*",
    "exo_recent":"🔭 *اكتشافات حديثة*",
    "exo_weekly":"🔔 تنبيهات أسبوعية",
    "sw_digest_title":"☀️ *ملخص طقس الفضاء*","sw_digest_loading":"☀️ جاري تحميل الملخص...",
    "cancelled":"❌ تم الإلغاء",
    "capsule_chars_err":"❌ 5–2000 حرف",
    "sat_tracker_title":"🛸 *متتبع الأقمار الصناعية*","sat_tracker_choose":"اختر مركبة:",
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
async def safe_answer(q, text=None, show_alert=False):
    try: await q.answer(text=text, show_alert=show_alert)
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
         [InlineKeyboardButton(L("cat_interact_btn"), callback_data="cat_interact"),
         InlineKeyboardButton(L("btn_profile"),      callback_data="cat_profile")],
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
        [InlineKeyboardButton(L("btn_solar_wind"),  callback_data="live_solar_wind"),
         InlineKeyboardButton(L("btn_kp"),          callback_data="live_kp")],
        [InlineKeyboardButton(L("btn_flares"),      callback_data="live_flares"),
         InlineKeyboardButton(L("btn_live_iss"),    callback_data="live_iss")],
        [InlineKeyboardButton(L("btn_radiation"),   callback_data="live_radiation"),
         InlineKeyboardButton(L("btn_aurora_f"),    callback_data="live_aurora_forecast")],
        [InlineKeyboardButton(L("btn_geomag"),      callback_data="live_geomagnetic_alert"),
         InlineKeyboardButton(L("btn_sunspot"),     callback_data="live_sunspot")],
        [InlineKeyboardButton(L("btn_live_epic"),   callback_data="live_epic_latest"),
         InlineKeyboardButton(L("btn_sat_count"),   callback_data="live_satellite_count")],
        [InlineKeyboardButton(L("btn_sat_tracker"),  callback_data="satellite_tracker"),
         InlineKeyboardButton(L("btn_earthquakes"),  callback_data="earthquakes")],
        [InlineKeyboardButton(L("btn_sw_digest"),    callback_data="spaceweather_digest"),
         InlineKeyboardButton(L("btn_exo_alert"),    callback_data="exoplanet_alert")],
        [InlineKeyboardButton(L("back_menu"),       callback_data="back")],
    ])

def cat_interact_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_planet_calc"),    callback_data="planet_calc"),
         InlineKeyboardButton(L("btn_horoscope"),      callback_data="horoscope_menu")],
        [InlineKeyboardButton(L("btn_space_name"),     callback_data="space_name"),
         InlineKeyboardButton(L("btn_quiz"),           callback_data="quiz_start_menu")],
        [InlineKeyboardButton(L("btn_poll"),           callback_data="daily_poll"),
         InlineKeyboardButton(L("btn_capsule"),        callback_data="capsule_menu")],
        [InlineKeyboardButton(L("btn_lunar_cal"),      callback_data="lunar_calendar"),
         InlineKeyboardButton(L("btn_mars_live"),      callback_data="mars_rover_live")],
        [InlineKeyboardButton(L("btn_notifications"),  callback_data="notifications_menu"),
         InlineKeyboardButton(L("btn_nasa_tv"),        callback_data="nasa_tv")],
        [InlineKeyboardButton(L("btn_challenge"),      callback_data="daily_challenge_start"),
         InlineKeyboardButton(L("btn_rocket_game"),    callback_data="rocket_game")],
        [InlineKeyboardButton(L("btn_daily_horoscope"),callback_data="daily_horoscope"),
         InlineKeyboardButton(L("btn_space_qa"),       callback_data="space_qa")],
        [InlineKeyboardButton(L("btn_iss_schedule"),   callback_data="iss_schedule"),
         InlineKeyboardButton(L("btn_meteorite_map"),  callback_data="meteorite_map")],
        [InlineKeyboardButton(L("btn_flight_calc"),    callback_data="flight_calculator"),
         InlineKeyboardButton(L("btn_mission_status"), callback_data="mission_status")],
        [InlineKeyboardButton(L("btn_dictionary"),     callback_data="space_dictionary"),
         InlineKeyboardButton(L("btn_course"),         callback_data="course_menu")],
        [InlineKeyboardButton(L("back_menu"),          callback_data="back")],
    ])

def cat_news_kb(lang):
    L = lambda k: tx(lang, k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L("btn_news_sfn"),         callback_data="news_sfn"),
         InlineKeyboardButton(L("btn_news_spacenews"),   callback_data="news_spacenews")],
        [InlineKeyboardButton(L("btn_news_esa"),         callback_data="news_esa"),
         InlineKeyboardButton(L("btn_news_universetoday"), callback_data="news_universetoday")],
        [InlineKeyboardButton(L("btn_news_nasa"),        callback_data="news_nasa"),
         InlineKeyboardButton(L("btn_news_skytel"),      callback_data="news_skytel")],
        [InlineKeyboardButton(L("btn_news_planetary"),   callback_data="news_planetary"),
         InlineKeyboardButton(L("btn_news_spacedotcom"), callback_data="news_spacedotcom")],
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
    src_row.append(InlineKeyboardButton(tx(lang, "back_cat"), callback_data="cat_news"))
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
    "he": {
        "Aries":"♈ *טלה*\n\nרוח סולארית מתונה. מאדים במיקום טוב — יום לפרויקטים חדשים!\n\n🔬 Kp יציב. ⚡ אנרגיה: ████████░░ 80%",
        "Taurus":"♉ *שור*\n\nנוגה בפריהליון — זמן לתוכניות ארוכות.\n\n🔬 פעילות סולארית נמוכה. ⚡ אנרגיה: ██████░░░░ 60%",
        "Gemini":"♊ *תאומים*\n\nשני קטבי אורנוס: היה גמיש!\n\n🔬 סופרנובות באזורך. ⚡ אנרגיה: █████████░ 90%",
        "Cancer":"♋ *סרטן*\n\nהירח באפוגי — זמן לחשיבה.\n\n🔬 שלבי הירח משפיעים על האיונוספרה. ⚡ אנרגיה: ████░░░░░░ 40%",
        "Leo":"♌ *אריה*\n\nלהבות מסוג M — אנרגיה מקסימלית!\n\n🔬 ייתכן זוהר הלילה! ⚡ אנרגיה: ██████████ 100%",
        "Virgo":"♍ *בתולה*\n\nJWST: הפרטים חשובים.\n\n🔬 Webb מצלם כוכבי לכת. ⚡ אנרגיה: ███████░░░ 70%",
        "Libra":"♎ *מאזניים*\n\nמרכז המסה ארץ-ירח מאוזן.\n\n🔬 LIGO זיהה גלים. ⚡ אנרגיה: ███████░░░ 70%",
        "Scorpio":"♏ *עקרב*\n\nחומר אפל: כוחות נסתרים אמיתיים.\n\n🔬 27% מהיקום — חומר אפל. ⚡ אנרגיה: ████████░░ 80%",
        "Sagittarius":"♐ *קשת*\n\nחץ לעבר קשת A*!\n\n🔬 מרכז הגלקסיה מאחורי אבק. ⚡ אנרגיה: █████████░ 90%",
        "Capricorn":"♑ *גדי*\n\nשבתאי: מבנה זה המפתח.\n\n🔬 טבעות שבתאי בעובי 100 מ'. ⚡ אנרגיה: ██████░░░░ 60%",
        "Aquarius":"♒ *דלי*\n\nאורנוס נוטה 98° — לא שגרתי!\n\n🔬 אורנוס מסתובב על הצד. ⚡ אנרגיה: ████████░░ 80%",
        "Pisces":"♓ *דגים*\n\nגייזרים של אנקלדוס: סמוך על האינטואיציה.\n\n🔬 אוקיינוס נוזלי מתחת לקרח. ⚡ אנרגיה: █████░░░░░ 50%",
    },
    "ar": {
        "Aries":"♈ *الحمل*\n\nرياح شمسية معتدلة. المريخ في موقع جيد — يوم لمشاريع جديدة!\n\n🔬 Kp مستقر. ⚡ الطاقة: ████████░░ 80%",
        "Taurus":"♉ *الثور*\n\nالزهرة في الحضيض — وقت للخطط طويلة.\n\n🔬 نشاط شمسي منخفض. ⚡ الطاقة: ██████░░░░ 60%",
        "Gemini":"♊ *الجوزاء*\n\nقطبا أورانوس: كن مرناً!\n\n🔬 مستعرات عظمى قريبة. ⚡ الطاقة: █████████░ 90%",
        "Cancer":"♋ *السرطان*\n\nالقمر في الأوج — وقت للتأمل.\n\n🔬 أطوار القمر تؤثر على الأيونوسفير. ⚡ الطاقة: ████░░░░░░ 40%",
        "Leo":"♌ *الأسد*\n\nتوهجات من فئة M — طاقة قصوى!\n\n🔬 شفق محتمل الليلة! ⚡ الطاقة: ██████████ 100%",
        "Virgo":"♍ *العذراء*\n\nJWST: التفاصيل مهمة.\n\n🔬 ويب يصور كواكب خارجية. ⚡ الطاقة: ███████░░░ 70%",
        "Libra":"♎ *الميزان*\n\nمركز ثقل الأرض-القمر متوازن.\n\n🔬 LIGO رصد موجات. ⚡ الطاقة: ███████░░░ 70%",
        "Scorpio":"♏ *العقرب*\n\nالمادة المظلمة: القوى الخفية حقيقية.\n\n🔬 27% من الكون مادة مظلمة. ⚡ الطاقة: ████████░░ 80%",
        "Sagittarius":"♐ *القوس*\n\nسهم نحو القوس A*!\n\n🔬 مركز المجرة خلف الغبار. ⚡ الطاقة: █████████░ 90%",
        "Capricorn":"♑ *الجدي*\n\nزحل: البنية هي المفتاح.\n\n🔬 حلقات زحل بسمك 100م. ⚡ الطاقة: ██████░░░░ 60%",
        "Aquarius":"♒ *الدلو*\n\nأورانوس مائل 98° — غير تقليدي!\n\n🔬 أورانوس يدور على جانبه. ⚡ الطاقة: ████████░░ 80%",
        "Pisces":"♓ *الحوت*\n\nينابيع إنسيلادوس: ثق بحدسك.\n\n🔬 محيط سائل تحت جليد إنسيلادوس. ⚡ الطاقة: █████░░░░░ 50%",
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
        # Build keyboard with ⭐ Save to favorites button
        save_btn = InlineKeyboardButton(tx(lang, "fav_saved").replace("!",""), callback_data="favorites_save")
        if not params:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(tx(lang, "btn_more_rnd"), callback_data="apod_random"), save_btn],
                [InlineKeyboardButton(tx(lang, "back_menu"), callback_data="back")],
            ])
        else:
            kb = InlineKeyboardMarkup([
                [save_btn],
                [InlineKeyboardButton(tx(lang, "back_menu"), callback_data="back")],
            ])
        # Save data for favorites handler
        ctx.user_data["last_apod"] = {"title": title, "url": url, "hdurl": hdurl, "date": d}
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
    text = tx(lang, "exoplanets_title") + "\n\n"
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
        text = tx(lang, "launches_title") + "\n\n"
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
    text = tx(lang, "satellites_text", total=total, active=active)
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
    text = tx(lang, "meteors_title") + "\n\n"
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
    text = (f"{emoji} {tx(lang, 'moon_title', d=str(date.today()))}\n\n🌙 *{phase_name}*\n"
            f"💡 ~{illum}%  |  Day {cycle_day:.1f}/29.5\n\n"
            f"{tx(lang, 'moon_photo_tip')}")
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
    text = tx(lang, "telescopes_text")
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
    text = f"{tx(lang, 'spacefact_title')}\n\n{fact}"
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
        try: spd_f=float(speed); status=tx(lang,"sw_calm") if spd_f<400 else tx(lang,"sw_moderate") if spd_f<600 else tx(lang,"sw_strong") if spd_f<800 else tx(lang,"sw_storm")
        except: status="?"
        try: speed=f"{float(speed):,.0f} km/s"
        except: pass
        try: density=f"{float(density):.2f} p/cm³"
        except: pass
        await safe_edit(q,f"{tx(lang,'live_solar_wind_title')}\n⏱ {time_str} UTC\n\n{status}\n🚀 {speed}  |  🔵 {density}\n\n[NOAA](https://www.swpc.noaa.gov)",
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
            state=tx(lang,"kp_quiet") if kp_val<4 else tx(lang,"kp_minor") if kp_val<5 else tx(lang,"kp_moderate") if kp_val<6 else tx(lang,"kp_strong") if kp_val<8 else tx(lang,"kp_extreme")
            aurora=tx(lang,"aurora_polar") if kp_val<4 else tx(lang,"aurora_scandinavia") if kp_val<6 else tx(lang,"aurora_mid") if kp_val<8 else tx(lang,"aurora_equatorial")
        except: state=aurora="?"
        await safe_edit(q,f"{tx(lang,'live_kp_title')}\n⏱ {time_} UTC\n\nKp: *{kp_now}*  |  {state}\n🌈 Aurora: {aurora}",
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
        await safe_edit(q,f"{tx(lang,'live_flares_title')}\n⏱ {time_} UTC\n\n⚡ *{cls_}* — `{fs}`",
            reply_markup=back_kb(lang,"live_flares",ctx))
    except Exception as e:
        await safe_edit(q,f"{tx(lang,'err')}: `{e}`",reply_markup=back_kb(lang,ctx=ctx))

async def live_iss_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        pos=get_iss_position()
        lat,lon,ts=pos["lat"],pos["lon"],pos["ts"]
        iss_c=get_iss_crew()
        text=(f"{tx(lang,'live_iss_title')}\n⏱ {ts}\n\n🌍 `{lat:+.4f}°` | 🌏 `{lon:+.4f}°`\n"
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
        await safe_edit(q,f"{tx(lang,'live_radiation_title')}\n⏱ {time_p} UTC\n\n☢️ `{fs}`\n🌡 *{rl}*",
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
            forecast=("🌈 "+tx(lang,"aurora_mid")) if kp_val>=7 else ("🌈 "+tx(lang,"aurora_scandinavia")) if kp_val>=5 else ("🌈 "+tx(lang,"aurora_polar")) if kp_val>=4 else ("🌈 "+tx(lang,"aurora_polar"))
        except: forecast="?"
        await safe_edit(q,f"{tx(lang,'live_aurora_title')}\n⏱ {time_} UTC\n\nKp: *{kp}*\n{forecast}",
            reply_markup=back_kb(lang,"live_aurora_forecast",ctx))
    except Exception as e:
        await safe_edit(q,f"{tx(lang,'err')}: `{e}`",reply_markup=back_kb(lang,ctx=ctx))

async def live_geomag_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🔴...")
    try:
        end=date.today().isoformat(); start=(date.today()-timedelta(days=2)).isoformat()
        storms=nasa_req("/DONKI/GST",{"startDate":start,"endDate":end}) or []
        text=f"{tx(lang,'live_geomag_title')}\n\nEvents: *{len(storms)}*\n\n"
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
        await safe_edit(q,f"{tx(lang,'live_sunspot_title')}\n\n{tx(lang,'live_sunspot_text',ssn=ssn)}",
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
        caption=f"{tx(lang,'live_epic_title')}\n📅 {date_str}\n\n{tx(lang,'live_epic_desc')}"
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
    await safe_edit(q,tx(lang,"live_starlink_title",total=total,active=active),
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
    lines=[tx(lang,"planet_calc_title")+"\n"]
    lines.append(tx(lang,"planet_calc_earth",age=f"{age_days/365.25:.1f}",weight=f"{weight:.1f}")+"\n")
    for pname,gravity in PLANET_GRAVITY.items():
        if pname=="🌍 Earth": continue
        age_p=age_days/PLANET_YEAR_DAYS[pname]; w_p=weight*gravity
        lines.append(f"{pname}: *{age_p:.1f} yrs*  |  ⚖️ *{w_p:.1f} kg*")
    lines.append("\n"+tx(lang,"planet_calc_moon",w=f"{weight*0.165:.1f}"))
    lines.append("\n"+tx(lang,"planet_calc_days",days=f"{age_days:,}"))
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
        await update.message.reply_text(tx(lang,"capsule_chars_err")); return CAPSULE_MSG
    deliver_on=(date.today()+timedelta(days=365)).isoformat()
    capsules=load_capsules()
    capsules.append({"chat_id":update.effective_chat.id,"message":user_msg,"deliver_on":deliver_on,"created_at":date.today().isoformat()})
    save_capsules(capsules)
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")]])
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
    await safe_edit(q,f"{tx(lang,'quiz_question_title',n=qi+1)}\n\n{q_text}\n\n{opts_txt}",reply_markup=quiz_kb(lang,qi))

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
    text=(tx(lang,"name_gen_title")+f"{tx(lang,'name_callsign')}\n`{callsign}`\n\n{tx(lang,'name_star')}\n`{star_name}`\n"
          f"{tx(lang,'name_constellation',c=const,s=spec)}\n{tx(lang,'name_distance',d=str(dist))}")
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
                status_e=tx(lang,"rover_active") if m.get("status")=="active" else tx(lang,"rover_inactive")
                text+=(f"🤖 *{m.get('name',rover.title())}* — {status_e}\n"
                       f"   {tx(lang,'rover_landing')} {m.get('landing_date','?')}\n"
                       f"   {tx(lang,'rover_sol')} {m.get('max_sol',0)}  |  📅 {m.get('max_date','?')}\n"
                       f"   {tx(lang,'rover_photos')} {m.get('total_photos',0):,}\n\n")
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
async def news_esa_h(update, ctx):          await news_source_h(update, ctx, "news_esa")
async def news_universetoday_h(update, ctx): await news_source_h(update, ctx, "news_universetoday")
async def news_skytel_h(update, ctx):       await news_source_h(update, ctx, "news_skytel")

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
    "news_esa":           news_esa_h,
    "news_universetoday": news_universetoday_h,
    "news_skytel":        news_skytel_h,
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
# PART 3 — 15 NEW FEATURES                                                      ║
# Place BEFORE setup_bot() in the combined file (after part2 handlers)          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
#
# INTEGRATION — add these 2 lines to setup_bot() after the existing handlers:
#   for h in get_new_conv_handlers(): tg_app.add_handler(h)
#   if jq: register_new_jobs(jq)
#
# INTEGRATION — add these 2 lines after DIRECT_MAP = {...} in part2:
#   DIRECT_MAP.update(NEW_DIRECT_MAP)
#   CAT_MAP.update(NEW_CAT_MAP)
#
# INTEGRATION — add to part1 translations (each lang):
#   See TRANSLATION KEYS block below
# ═══════════════════════════════════════════════════════════════════════════════

# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: NEW CONVERSATION STATE CONSTANTS (defined at file top — no duplicate)  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
# ISS_CITY=30, DICT_TERM=31 etc. already defined above — skipping redefinition
# ── End: NEW CONVERSATION STATE CONSTANTS ─────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: NEW ENV VARS                                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-haiku-4-5-20251001"
# ── End: NEW ENV VARS ─────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: NEW STORAGE HELPERS                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
FAVORITES_FILE    = "favorites.json"
ACHIEVEMENTS_FILE = "achievements.json"
STATS_FILE        = "user_stats.json"
SMART_ALERTS_FILE = "smart_alerts.json"
COURSE_FILE       = "course_progress.json"

def _jload(f, d):
    try:
        with open(f) as fp: return json.load(fp)
    except: return d

def _jsave(f, data):
    try:
        with open(f,"w") as fp: json.dump(data,fp,ensure_ascii=False,indent=2)
    except Exception as e: logger.error(f"_jsave {f}: {e}")

def load_favorites():     return _jload(FAVORITES_FILE, {})
def save_favorites(d):    _jsave(FAVORITES_FILE, d)
def load_achievements():  return _jload(ACHIEVEMENTS_FILE, {})
def save_achievements(d): _jsave(ACHIEVEMENTS_FILE, d)
def load_stats():         return _jload(STATS_FILE, {})
def save_stats(d):        _jsave(STATS_FILE, d)
def load_smart_alerts():  return _jload(SMART_ALERTS_FILE, {})
def save_smart_alerts(d): _jsave(SMART_ALERTS_FILE, d)
def load_course():        return _jload(COURSE_FILE, {})
def save_course(d):       _jsave(COURSE_FILE, d)
# ── End: NEW STORAGE HELPERS ──────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: NEW STATIC DATA                                                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# ── Космический словарь (25 терминов) ─────────────────────────────────────────
SPACE_DICT = {
    "blackhole":   {"emoji":"🕳","ru":("Чёрная дыра","Область пространства с гравитацией настолько мощной, что даже свет не может её покинуть. Образуется при коллапсе массивной звезды.","Сверхмассивная ЧД в центре M87 имеет массу 6,5 млрд Солнц"),"en":("Black Hole","Region where gravity is so strong that not even light can escape. Forms from the collapse of a massive star.","The M87 black hole weighs 6.5 billion solar masses")},
    "quasar":      {"emoji":"💥","ru":("Квазар","Активное ядро далёкой галактики, питаемое сверхмассивной чёрной дырой. Самые яркие объекты во Вселенной.","Квазар 3C 273 виден в любительский телескоп"),"en":("Quasar","Active galactic nucleus powered by a supermassive black hole. The brightest objects in the universe.","Quasar 3C 273 is visible through amateur telescopes")},
    "pulsar":      {"emoji":"📡","ru":("Пульсар","Нейтронная звезда, быстро вращающаяся и испускающая пучки радиоволн. Вращается до 700 оборотов в секунду.","Первый пульсар открыла Джоселин Белл в 1967 году"),"en":("Pulsar","Rapidly rotating neutron star emitting beams of radio waves. Can spin up to 700 times per second.","The first pulsar was discovered by Jocelyn Bell in 1967")},
    "nebula":      {"emoji":"🌌","ru":("Туманность","Огромное облако газа и пыли в космосе. Бывают эмиссионные (светятся), отражательные и тёмные.","Туманность Орёл размером 90×65 световых лет"),"en":("Nebula","Vast cloud of gas and dust in space. Can be emission, reflection, or dark types.","The Eagle Nebula spans 90×65 light-years")},
    "redshift":    {"emoji":"🔴","ru":("Красное смещение","Смещение спектра объекта к красному концу при удалении от наблюдателя. Доказывает расширение Вселенной.","Именно по красному смещению Хаббл открыл расширение Вселенной"),"en":("Redshift","Shift of an object's spectrum toward red as it moves away. Proves the universe is expanding.","Hubble used redshift to discover the universe's expansion")},
    "darkmatter":  {"emoji":"🌑","ru":("Тёмная материя","Невидимое вещество, составляющее ~27% Вселенной. Обнаруживается только по гравитационному влиянию на обычную материю.","Нет ни одного прямого наблюдения — только косвенные доказательства"),"en":("Dark Matter","Invisible matter making up ~27% of the universe. Only detected by its gravitational effects on visible matter.","Not one direct observation exists — only indirect evidence")},
    "darkener":    {"emoji":"⚫","ru":("Тёмная энергия","Загадочная сила, ускоряющая расширение Вселенной. Составляет ~68% всей энергии Вселенной.","Открыта в 1998 году при наблюдении сверхновых Ia"),"en":("Dark Energy","Mysterious force accelerating the universe's expansion. Makes up ~68% of the universe's total energy.","Discovered in 1998 studying Type Ia supernovae")},
    "singularity": {"emoji":"♾","ru":("Сингулярность","Точка бесконечной плотности в центре чёрной дыры или в начале Большого взрыва. Уравнения физики здесь перестают работать.","Сингулярность — это граница наших знаний о физике"),"en":("Singularity","Point of infinite density at a black hole's center or at the Big Bang. Physics equations break down here.","A singularity marks the boundary of our physical knowledge")},
    "neutronstar": {"emoji":"⭐","ru":("Нейтронная звезда","Сверхплотный остаток взорвавшейся звезды. Чайная ложка вещества весит 1 млрд тонн.","Размер — ~20 км, но масса в 2 раза больше Солнца"),"en":("Neutron Star","Ultra-dense remnant of an exploded star. One teaspoon of material weighs 1 billion tons.","Roughly 20 km across but twice the mass of our Sun")},
    "gravitylens": {"emoji":"🔭","ru":("Гравитационное линзирование","Искривление пути света вблизи массивного объекта. Используется для обнаружения тёмной материи и далёких галактик.","Эйнштейн предсказал этот эффект в 1915 году"),"en":("Gravitational Lensing","Bending of light near a massive object. Used to detect dark matter and distant galaxies.","Einstein predicted this effect in 1915")},
    "exoplanet":   {"emoji":"🪐","ru":("Экзопланета","Планета, вращающаяся вокруг другой звезды. Открыто более 5700 экзопланет. Некоторые находятся в зоне обитаемости.","Первую экзопланету подтвердили в 1992 году"),"en":("Exoplanet","Planet orbiting another star. Over 5,700 confirmed. Some lie in the habitable zone.","The first confirmed exoplanet was in 1992")},
    "event_horizon":{"emoji":"🌀","ru":("Горизонт событий","Граница вокруг чёрной дыры, за которую ничто не возвращается. Не физическая поверхность, а точка невозврата.","Горизонт событий ЧД M87 размером с Солнечную систему"),"en":("Event Horizon","Boundary around a black hole beyond which nothing returns. Not a physical surface — a point of no return.","M87's event horizon is the size of our solar system")},
    "supernova":   {"emoji":"💫","ru":("Сверхновая","Мощнейший звёздный взрыв. За секунды высвобождает больше энергии, чем Солнце за всю жизнь.","Сверхновая 1987A — ближайшая за 400 лет"),"en":("Supernova","The most powerful stellar explosion. Releases more energy in seconds than the Sun in its lifetime.","Supernova 1987A was the closest in 400 years")},
    "cosmicweb":   {"emoji":"🕸","ru":("Космическая паутина","Крупнейшая структура Вселенной: нити галактик, узлы и пустоты. Растянута на миллиарды световых лет.","Похожа на нейронную сеть мозга — случайное совпадение?"),"en":("Cosmic Web","The universe's largest structure: filaments of galaxies, nodes, and voids. Spans billions of light-years.","It resembles a neural network — coincidence?")},
    "antimatter":  {"emoji":"⚡","ru":("Антиматерия","Зеркальная копия обычной материи с противоположным зарядом. При встрече с материей аннигилирует.","Сделать 1 г антиматерии = стоимость бюджета NASA за 1000 лет"),"en":("Antimatter","Mirror copy of ordinary matter with opposite charge. Annihilates on contact with matter.","Producing 1g of antimatter would cost NASA's budget × 1000 years")},
    "redgiant":    {"emoji":"🔴","ru":("Красный гигант","Стадия умирающей звезды — она расширяется, охлаждается и краснеет. Солнце станет красным гигантом через 5 млрд лет.","Бетельгейзе уже красный гигант и скоро взорвётся"),"en":("Red Giant","Dying star stage — it expands, cools, and turns red. Our Sun will become one in 5 billion years.","Betelgeuse is already a red giant nearing explosion")},
    "wormhole":    {"emoji":"🌀","ru":("Червоточина","Гипотетический тоннель в пространстве-времени, соединяющий далёкие точки. Разрешена уравнениями ОТО, но не обнаружена.","Называется червоточиной потому что червяк прогрызает яблоко короче"),"en":("Wormhole","Hypothetical tunnel in spacetime connecting distant points. Allowed by GR equations but never observed.","Named 'wormhole' as a worm tunneling through an apple takes a shorter path")},
    "magnetar":    {"emoji":"🧲","ru":("Магнетар","Нейтронная звезда с магнитным полем в 10¹⁵ раз сильнее земного. Вспышки магнетаров достигают Земли с расстояния 50 000 св. лет.","SGR 1806-20 в 2004 году отправил вспышку видимую с Земли"),"en":("Magnetar","Neutron star with a magnetic field 10¹⁵ times Earth's. Magnetar flares reach us from 50,000 light-years away.","SGR 1806-20 sent a flare in 2004 visible from Earth")},
    "lightyear":   {"emoji":"📏","ru":("Световой год","Расстояние, которое свет преодолевает за год — ~9,46 трлн км. НЕ единица времени!","До ближайшей звезды Проксима Центавра — 4,24 световых года"),"en":("Light Year","Distance light travels in one year — ~9.46 trillion km. NOT a unit of time!","Proxima Centauri, the nearest star, is 4.24 light-years away")},
    "spacetime":   {"emoji":"🕸","ru":("Пространство-время","Единое четырёхмерное пространство (3D + время) по Эйнштейну. Масса искривляет пространство-время — это и есть гравитация.","GPS-спутники должны делать поправку на искривление пространства-времени"),"en":("Spacetime","Einstein's unified 4D fabric (3D + time). Mass warps spacetime — that IS gravity.","GPS satellites must correct for spacetime curvature")},
    "hawkingradiation":{"emoji":"🌡","ru":("Излучение Хокинга","Теоретическое излучение чёрных дыр, из-за которого они медленно испаряются. Для ЧД звёздной массы испарение займёт 10⁶⁷ лет.","Никогда не наблюдалось — слишком слабое для современных приборов"),"en":("Hawking Radiation","Theoretical radiation from black holes causing slow evaporation. A stellar-mass BH takes 10⁶⁷ years to evaporate.","Never observed — too faint for current instruments")},
    "accretiondisk":{"emoji":"💫","ru":("Аккреционный диск","Плоское вращающееся облако вещества вокруг чёрной дыры или нейтронной звезды. Раскаляется до миллионов градусов.","Вещество в диске разгоняется до 30% скорости света"),"en":("Accretion Disk","Flat rotating cloud of matter around a black hole or neutron star. Heats up to millions of degrees.","Material in the disk accelerates to 30% of light speed")},
    "parallax":    {"emoji":"📐","ru":("Параллакс","Метод измерения расстояний до звёзд по смещению их видимого положения при движении Земли.","Точно работает до 1000 световых лет — дальше погрешность велика"),"en":("Parallax","Method to measure star distances using their apparent shift as Earth orbits the Sun.","Accurate up to 1,000 light-years — beyond that errors grow large")},
    "oortcloud":   {"emoji":"☁","ru":("Облако Оорта","Огромная сферическая оболочка ледяных тел на краю Солнечной системы. Источник долгопериодических комет.","Простирается до 100 000 а.е. — почти до Альфы Центавра"),"en":("Oort Cloud","Vast spherical shell of icy bodies at the edge of the Solar System. Source of long-period comets.","Extends up to 100,000 AU — nearly reaching Alpha Centauri")},
    "habzone":     {"emoji":"🌿","ru":("Зона обитаемости","Расстояние от звезды, при котором на планете может существовать жидкая вода. Иногда называют 'зоной Златовласки'.","Земля находится почти идеально в центре зоны обитаемости"),"en":("Habitable Zone","Distance from a star where liquid water can exist on a planet's surface. Also called the Goldilocks zone.","Earth sits nearly perfectly in the center of our habitable zone")},
}

DICT_KEYS = list(SPACE_DICT.keys())

# ── Активные миссии (12) ──────────────────────────────────────────────────────
MISSIONS_DATA = [
    {"name":"🔭 James Webb Space Telescope","agency":"NASA/ESA/CSA","type":"Observatory","launched":"Dec 25, 2021","status":"🟢 Operational","progress":100,"orbit":"L2 Lagrange point","desc":"Infrared successor to Hubble, studying the first galaxies and exoplanet atmospheres.","url":"https://webb.nasa.gov"},
    {"name":"🚀 Perseverance Rover","agency":"NASA","type":"Mars Rover","launched":"Jul 30, 2020","status":"🟢 Operational","progress":100,"orbit":"Jezero Crater, Mars","desc":"Collecting rock samples for future return to Earth. Also deployed the Ingenuity helicopter.","url":"https://mars.nasa.gov/mars2020"},
    {"name":"🌙 Artemis Program","agency":"NASA","type":"Crewed Lunar","launched":"Nov 16, 2022 (I)","status":"🟡 Artemis II prep","progress":45,"orbit":"Lunar orbit","desc":"Returning humans to the Moon. Artemis II (first crewed flight) planned for 2025–2026.","url":"https://www.nasa.gov/artemis"},
    {"name":"🛸 Voyager 1","agency":"NASA","type":"Interstellar","launched":"Sep 5, 1977","status":"🟢 Active — 24B km","progress":100,"orbit":"Interstellar space","desc":"Farthest human-made object. Still sending data from beyond the heliosphere.","url":"https://voyager.jpl.nasa.gov"},
    {"name":"🪐 Europa Clipper","agency":"NASA","type":"Outer Planets","launched":"Oct 14, 2024","status":"🟢 En route to Jupiter","progress":15,"orbit":"En route","desc":"Will perform 49 flybys of Europa to study its subsurface ocean for habitability.","url":"https://europa.nasa.gov"},
    {"name":"🌞 Parker Solar Probe","agency":"NASA","type":"Solar","launched":"Aug 12, 2018","status":"🟢 Operational","progress":100,"orbit":"Solar orbit","desc":"Closest spacecraft to the Sun ever. Flew through the solar corona in 2021.","url":"https://www.nasa.gov/parker"},
    {"name":"🔴 Mars Express","agency":"ESA","type":"Mars Orbiter","launched":"Jun 2, 2003","status":"🟢 Operational","progress":100,"orbit":"Mars orbit","desc":"Over 20 years mapping Mars. Confirmed subsurface water ice in 2018.","url":"https://www.esa.int/marsexpress"},
    {"name":"🌌 Gaia","agency":"ESA","type":"Astrometry","launched":"Dec 19, 2013","status":"🟢 Operational","progress":100,"orbit":"L2 point","desc":"Mapping 1 billion stars in the Milky Way with unprecedented precision.","url":"https://www.esa.int/gaia"},
    {"name":"🪐 Cassini Legacy","agency":"NASA/ESA","type":"Saturn orbiter","launched":"Oct 15, 1997","status":"⚪ Completed 2017","progress":100,"orbit":"Burned in Saturn","desc":"13-year Saturn mission. Discovered Enceladus geysers and Titan's lakes.","url":"https://saturn.jpl.nasa.gov"},
    {"name":"🚀 SpaceX Starship","agency":"SpaceX","type":"Super Heavy Rocket","launched":"2023 (tests)","status":"🟡 Test flights","progress":60,"orbit":"Suborbital/LEO tests","desc":"Fully reusable rocket for Moon, Mars and beyond. Multiple integrated flight tests in 2023–2024.","url":"https://www.spacex.com/vehicles/starship"},
    {"name":"🌍 Sentinel-6","agency":"ESA/NASA","type":"Earth Obs.","launched":"Nov 21, 2020","status":"🟢 Operational","progress":100,"orbit":"LEO ~1336 km","desc":"Monitoring global sea level rise with millimeter precision.","url":"https://www.esa.int/sentinel6"},
    {"name":"☄️ DART Mission","agency":"NASA","type":"Planetary Defense","launched":"Nov 24, 2021","status":"⚪ Success — 2022","progress":100,"orbit":"Mission complete","desc":"First test of asteroid deflection. Successfully changed Dimorphos's orbit by 32 minutes.","url":"https://dart.jhuapl.edu"},
]

# ── Система достижений (12 значков) ───────────────────────────────────────────
ACHIEVEMENTS_DEF = [
    {"id":"first_apod",   "emoji":"🌅","ru":"Первый APOD",       "en":"First APOD",       "he":"APOD ראשון",      "ar":"أول APOD",         "condition":"apod>=1"},
    {"id":"apod10",       "emoji":"📸","ru":"10 снимков NASA",   "en":"10 NASA Photos",   "he":"10 תמונות NASA",  "ar":"10 صور NASA",      "condition":"apod>=10"},
    {"id":"apod50",       "emoji":"🏅","ru":"50 снимков NASA",   "en":"50 NASA Photos",   "he":"50 תמונות NASA",  "ar":"50 صورة NASA",     "condition":"apod>=50"},
    {"id":"first_quiz",   "emoji":"🧠","ru":"Первый квиз",       "en":"First Quiz",       "he":"חידון ראשון",     "ar":"أول اختبار",       "condition":"quiz>=1"},
    {"id":"quiz_perfect", "emoji":"🏆","ru":"Квиз без ошибок",   "en":"Perfect Quiz",     "he":"חידון מושלם",     "ar":"اختبار مثالي",     "condition":"quiz_perfect>=1"},
    {"id":"explorer",     "emoji":"🚀","ru":"Исследователь",     "en":"Explorer",         "he":"חוקר",            "ar":"مستكشف",           "condition":"sections>=5"},
    {"id":"mars_fan",     "emoji":"🔴","ru":"Фанат Марса",       "en":"Mars Fan",         "he":"חובב מאדים",      "ar":"محب المريخ",       "condition":"mars>=3"},
    {"id":"news_reader",  "emoji":"📰","ru":"Читатель новостей", "en":"News Reader",      "he":"קורא חדשות",      "ar":"قارئ الأخبار",     "condition":"news>=5"},
    {"id":"week_streak",  "emoji":"🔥","ru":"7 дней подряд",     "en":"7-Day Streak",     "he":"7 ימים ברצף",     "ar":"7 أيام متواصلة",   "condition":"streak>=7"},
    {"id":"challenge_win","emoji":"🎯","ru":"Первый челлендж",   "en":"First Challenge",  "he":"אתגר ראשון",      "ar":"أول تحدي",         "condition":"challenge>=1"},
    {"id":"favorite5",    "emoji":"⭐","ru":"5 избранных",       "en":"5 Favorites",      "he":"5 מועדפים",       "ar":"5 مفضلات",         "condition":"favorites>=5"},
    {"id":"night_owl",    "emoji":"🦉","ru":"Ночной наблюдатель","en":"Night Owl",        "he":"ינשוף לילה",      "ar":"بومة الليل",       "condition":"night_session>=1"},
]

# ── Ежедневный челлендж (20 объектов) ─────────────────────────────────────────
CHALLENGE_DATA = [
    {"img_q":"Pillars of Creation Eagle Nebula Hubble","answer":1,"options":["Milky Way core","Pillars of Creation 🌌","Saturn's rings","Mars surface"],"fact":"The Pillars of Creation in the Eagle Nebula are 5 light-years tall and active star-forming regions."},
    {"img_q":"Great Red Spot Jupiter Cassini","answer":0,"options":["Jupiter's Great Red Spot 🔴","Solar flare SDO","Mars dust storm","Neptune's storm"],"fact":"Jupiter's Great Red Spot is a storm that has raged for over 350 years, bigger than Earth."},
    {"img_q":"Crab Nebula pulsar supernova remnant","answer":2,"options":["Andromeda galaxy","Cat's Eye nebula","Crab Nebula 💥","Whirlpool galaxy"],"fact":"The Crab Nebula is the remnant of a supernova observed by Chinese astronomers in 1054 AD."},
    {"img_q":"Saturn rings Cassini close up","answer":3,"options":["Uranus rings","Jupiter rings","Neptune rings","Saturn's rings 🪐"],"fact":"Saturn's rings are incredibly thin — only 10–100 meters deep despite spanning 282,000 km."},
    {"img_q":"Horsehead Nebula dark nebula Orion","answer":1,"options":["Carina nebula","Horsehead Nebula 🐴","Helix nebula","Boomerang nebula"],"fact":"The Horsehead Nebula is a dark cloud of gas and dust silhouetted against a glowing background."},
    {"img_q":"Whirlpool Galaxy M51 Hubble spiral","answer":2,"options":["Andromeda M31","Triangulum Galaxy","Whirlpool Galaxy M51 🌀","Sombrero Galaxy"],"fact":"The Whirlpool Galaxy (M51) is being distorted by gravitational interaction with its companion NGC 5195."},
    {"img_q":"Enceladus geysers south pole Cassini","answer":0,"options":["Enceladus geysers 💧","Europa surface","Titan surface","Io volcanoes"],"fact":"Enceladus ejects water vapor geysers from its south pole, suggesting a subsurface ocean."},
    {"img_q":"Hubble Ultra Deep Field galaxies","answer":3,"options":["Star cluster","Milky Way center","Nearby stars","Hubble Ultra Deep Field 🌌"],"fact":"The Hubble Ultra Deep Field contains ~10,000 galaxies in a patch of sky smaller than a grain of sand held at arm's length."},
    {"img_q":"Olympus Mons Mars volcanic shield","answer":1,"options":["Hawaii volcano","Olympus Mons 🔴","Venus Maxwell Montes","Moon crater"],"fact":"Olympus Mons on Mars is the largest volcano in the Solar System — 22 km high and 600 km wide."},
    {"img_q":"International Space Station ISS orbit","answer":2,"options":["Tiangong station","Hubble telescope","ISS 🛸","MIR station"],"fact":"The ISS travels at 28,000 km/h and completes an orbit every 90 minutes."},
    {"img_q":"aurora borealis ISS northern lights","answer":0,"options":["Aurora Borealis 🌈","Noctilucent clouds","Lightning storm","City lights"],"fact":"Auroras occur when solar particles collide with Earth's atmosphere at altitudes of 100–300 km."},
    {"img_q":"Pluto heart feature New Horizons","answer":3,"options":["Charon","Eris","Makemake","Pluto with Tombaugh Regio 💜"],"fact":"Pluto's heart-shaped region is called Tombaugh Regio, named after Pluto's discoverer."},
    {"img_q":"Black hole M87 EHT first image","answer":1,"options":["Neutron star","M87 Black Hole 🕳","Quasar jet","Galaxy merger"],"fact":"The first image of a black hole (M87*) was captured in 2019 by the Event Horizon Telescope."},
    {"img_q":"Titan Saturn moon haze atmosphere Cassini","answer":2,"options":["Venus","Io","Titan 🟠","Triton"],"fact":"Titan is the only moon with a dense atmosphere, liquid lakes of methane on its surface."},
    {"img_q":"Valles Marineris Mars canyon system","answer":0,"options":["Valles Marineris 🔴","Grand Canyon Arizona","Mariana Trench","Hellas Basin"],"fact":"Valles Marineris stretches 4,000 km — as wide as the USA. It would be the deepest canyon in the Solar System."},
    {"img_q":"solar flare corona SDO NASA","answer":1,"options":["Jupiter aurora","Solar flare ☀️","Pulsar jets","Magnetar burst"],"fact":"Solar flares can release the energy of 1 billion hydrogen bombs in minutes."},
    {"img_q":"Andromeda galaxy M31 spiral","answer":3,"options":["Milky Way","Triangulum","Large Magellanic Cloud","Andromeda Galaxy 🌌"],"fact":"Andromeda is on a collision course with the Milky Way — they'll merge in ~4.5 billion years."},
    {"img_q":"Europa moon Jupiter ice cracks surface","answer":0,"options":["Europa 🧊","Ganymede","Callisto","Io"],"fact":"Europa's subsurface ocean may contain more liquid water than all of Earth's oceans combined."},
    {"img_q":"comet 67P Rosetta nucleus close up","answer":2,"options":["Asteroid Bennu","Comet Hale-Bopp","Comet 67P Churyumov–Gerasimenko ☄️","Ceres surface"],"fact":"Rosetta mission landed Philae probe on Comet 67P in 2014 — first soft landing on a comet."},
    {"img_q":"Helix Nebula eye of god planetary","answer":1,"options":["Ant Nebula","Helix Nebula 👁","Ring Nebula","Owl Nebula"],"fact":"The Helix Nebula is nicknamed the 'Eye of God.' It's one of the closest planetary nebulae at 700 light-years."},
]

# ── Трекер спутников (8 аппаратов с NORAD ID) ─────────────────────────────────
SATELLITE_CATALOG = {
    "hubble": {"name":"Hubble Space Telescope","norad":20580,"emoji":"🔭","alt_km":538,"period_min":95,"launched":"Apr 24, 1990","desc":"Legendary telescope in LEO. Over 1.5 million observations, 19,000 scientific papers."},
    "jwst":   {"name":"James Webb Space Telescope","norad":50463,"emoji":"🌌","alt_km":1500000,"period_min":180*24*60,"launched":"Dec 25, 2021","desc":"At L2 Lagrange point, 1.5 million km from Earth. Observes in infrared."},
    "iss":    {"name":"International Space Station","norad":25544,"emoji":"🛸","alt_km":408,"period_min":92,"launched":"Nov 20, 1998","desc":"Continuously inhabited since 2000. 6–7 crew at all times."},
    "tess":   {"name":"TESS","norad":43435,"emoji":"🔍","alt_km":200000,"period_min":13.7*24*60,"launched":"Apr 18, 2018","desc":"Transiting Exoplanet Survey Satellite. Found 400+ confirmed exoplanets."},
    "chandra":{"name":"Chandra X-ray Observatory","norad":25867,"emoji":"⚡","alt_km":139000,"period_min":64*60,"launched":"Jul 23, 1999","desc":"X-ray telescope in high elliptical orbit. Studies black holes, neutron stars, supernovae."},
    "tiangong":{"name":"Tiangong Space Station","norad":48274,"emoji":"🇨🇳","alt_km":390,"period_min":92,"launched":"Apr 29, 2021","desc":"China's permanent space station. 3-person crew. Full completion in 2022."},
    "terra":  {"name":"Terra (Earth Observation)","norad":25994,"emoji":"🌍","alt_km":705,"period_min":99,"launched":"Dec 18, 1999","desc":"NASA's flagship Earth observer. Studies atmosphere, land, ocean interactions."},
    "gaia":   {"name":"Gaia (ESA)","norad":39479,"emoji":"⭐","alt_km":1500000,"period_min":180*24*60,"launched":"Dec 19, 2013","desc":"Mapping 1 billion stars. At L2 point with JWST. Most precise stellar catalog in history."},
}

# ── Курс «Астрономия за 30 дней» ─────────────────────────────────────────────
COURSE_LESSONS = [
    {"day":1, "title":"🌌 Масштаб Вселенной","text":"Вселенная существует около 13,8 млрд лет. Наблюдаемая часть — сфера диаметром 93 млрд световых лет. В ней ~2 трлн галактик, в каждой — сотни миллиардов звёзд.\n\n💡 *Факт дня:* Если сжать Солнечную систему до размера монеты, Млечный Путь будет размером с США."},
    {"day":2, "title":"☀️ Наше Солнце","text":"Солнце — звезда класса G2V. Возраст 4,6 млрд лет, температура поверхности 5778 К. Каждую секунду превращает 600 млн тонн водорода в гелий через ядерный синтез.\n\n💡 *Факт дня:* Солнечный свет, который вы видите сейчас, образовался в ядре ~100 000 лет назад."},
    {"day":3, "title":"🪐 Газовые гиганты","text":"Юпитер и Сатурн — газовые гиганты без твёрдой поверхности. Юпитер больше всех остальных планет Солнечной системы вместе взятых. Кольца Сатурна состоят из льда и камней.\n\n💡 *Факт дня:* Один день на Юпитере — всего 10 часов."},
    {"day":4, "title":"❄️ Ледяные миры","text":"Уран и Нептун — «ледяные гиганты», богатые водой, метаном и аммиаком в твёрдом состоянии. Уран вращается «на боку» — его полюс направлен почти к Солнцу.\n\n💡 *Факт дня:* На Нептуне дуют ветры 2100 км/ч — самые быстрые в Солнечной системе."},
    {"day":5, "title":"🌕 Луна — наш спутник","text":"Луна образовалась 4,5 млрд лет назад при столкновении Земли с протопланетой Тейя. Её гравитация стабилизирует ось Земли и создаёт приливы. На Луне нет атмосферы.\n\n💡 *Факт дня:* Луна удаляется от Земли на 3,8 см в год."},
    {"day":6, "title":"☄️ Кометы и астероиды","text":"Кометы — ледяные тела из внешней Солнечной системы. При приближении к Солнцу образуют кому и хвост. Пояс астероидов между Марсом и Юпитером содержит миллионы объектов.\n\n💡 *Факт дня:* Комета Галлея возвращается каждые 75–76 лет. Следующее появление — 2061 год."},
    {"day":7, "title":"🌟 Жизнь звезды","text":"Звёзды рождаются в туманностях из облаков газа и пыли. Масса определяет всё: жизнь маленьких звёзд — 100 млрд лет, массивных — 1–10 млн лет. Финал: белый карлик, нейтронная звезда или чёрная дыра.\n\n💡 *Факт дня:* Все атомы тяжелее железа в вашем теле созданы при взрыве сверхновой."},
    {"day":8, "title":"💥 Взрывы сверхновых","text":"Сверхновые — самые яркие взрывы во Вселенной. За несколько секунд высвобождают больше энергии, чем Солнце за всю жизнь. Именно они обогащают космос тяжёлыми элементами.\n\n💡 *Факт дня:* Сверхновая 1054 года (Крабовидная туманность) была видна днём."},
    {"day":9, "title":"🕳 Чёрные дыры","text":"Чёрные дыры образуются при коллапсе массивных звёзд. Горизонт событий — точка невозврата. Сверхмассивные ЧД в центрах галактик в миллиарды раз массивнее Солнца.\n\n💡 *Факт дня:* Время вблизи горизонта событий замедляется — эффект предсказан ОТО Эйнштейна."},
    {"day":10,"title":"🌌 Млечный Путь","text":"Наша галактика — спиральная, диаметром 100 000 световых лет с 100–400 млрд звёзд. Солнце находится в рукаве Ориона, в 26 000 световых лет от центра.\n\n💡 *Факт дня:* Млечный Путь вращается: Солнце совершает оборот за 225 млн лет — один «галактический год»."},
    {"day":11,"title":"🔭 История телескопов","text":"Галилей направил телескоп в небо в 1609 году. С тех пор телескопы ушли в космос: Хаббл (1990), Спитцер, Чандра, JWST (2021). Каждое поколение открывало невидимую прежде Вселенную.\n\n💡 *Факт дня:* JWST в 100 раз мощнее Хаббла и видит первые галактики после Большого взрыва."},
    {"day":12,"title":"🚀 Эра космонавтики","text":"4 октября 1957 — первый спутник. 12 апреля 1961 — Гагарин. 20 июля 1969 — Армстронг на Луне. За 65 лет человечество отправило 600+ космонавтов, 200+ миссий.\n\n💡 *Факт дня:* Программа Аполлон доставила 382 кг лунного грунта на Землю."},
    {"day":13,"title":"🌍 Земля из космоса","text":"«Снимок бледно-голубой точки» Вояджера-1 в 1990 году изменил наше восприятие Земли. Фото «Восход Земли» с Аполлона-8 (1968) стало символом экологического движения.\n\n💡 *Факт дня:* На МКС сутки сменяются 16 раз — из-за быстрого орбитального движения."},
    {"day":14,"title":"🔴 Марс","text":"Красная планета — главная цель будущей экспансии человечества. Марсианские сутки (сол) чуть длиннее земных — 24 ч 37 мин. Rovers Curiosity и Perseverance изучают возможность древней жизни.\n\n💡 *Факт дня:* На Марсе два раза в год бывают глобальные пылевые бури, накрывающие всю планету."},
    {"day":15,"title":"💧 Жидкая вода в Солнечной системе","text":"Жидкая вода существует не только на Земле: под льдом Европы, Энцелада, Каллисто, Тритона — целые океаны. Энцелад выбрасывает в космос гейзеры воды.\n\n💡 *Факт дня:* Подлёдный океан Европы содержит больше воды, чем все океаны Земли."},
    {"day":16,"title":"👾 Экзопланеты","text":"Первую экзопланету подтвердили в 1992 году. Сейчас известно 5700+. Методы обнаружения: транзитный (TESS, Кеплер), лучевых скоростей, гравитационного линзирования.\n\n💡 *Факт дня:* Kepler-452b — «двойник Земли» в 1400 световых годах, в зоне обитаемости."},
    {"day":17,"title":"☢️ Космическая радиация","text":"В открытом космосе нет защиты атмосферы. Солнечные вспышки и галактические лучи опасны для астронавтов. На МКС доза радиации в 10 раз выше земной.\n\n💡 *Факт дня:* За полёт на Луну (8 дней) астронавт получает дозу радиации, эквивалентную 6-месячному пребыванию на МКС."},
    {"day":18,"title":"🌊 Приливные силы","text":"Луна притягивает разные части Земли с разной силой, вызывая приливы. Приливные силы «замедлили» Луну — она всегда повёрнута к нам одной стороной.\n\n💡 *Факт дня:* Io (спутник Юпитера) разогревается до расплавленного состояния из-за приливных сил самого Юпитера."},
    {"day":19,"title":"🌑 Тёмная материя и энергия","text":"Обычная материя — лишь 5% Вселенной. 27% — тёмная материя (невидима, обнаруживается по гравитации). 68% — тёмная энергия, ускоряющая расширение Вселенной.\n\n💡 *Факт дня:* Несмотря на 80 лет исследований, природа тёмной материи до сих пор неизвестна."},
    {"day":20,"title":"🎯 Поиск внеземной жизни","text":"SETI ищет сигналы с 1960 года. Марсоходы ищут следы древней жизни. Астробиологи изучают экстремофилов на Земле как модели для жизни в других мирах.\n\n💡 *Факт дня:* Лучший кандидат — не Марс, а Энцелад: тепло, вода, органика — всё уже известно."},
    {"day":21,"title":"🛰 Спутники и орбиты","text":"На орбите более 9000 активных и неактивных спутников. Типы орбит: LEO (160–2000 км), MEO, GEO (35 786 км). GPS, погода, ТВ — всё это спутниковые услуги.\n\n💡 *Факт дня:* Первый коммерческий спутник Telstar-1 запущен в 1962 году — транслировал ТВ через Атлантику."},
    {"day":22,"title":"🌠 Метеоры и метеориты","text":"Каждый день на Землю падает 50–150 тонн космического вещества. Большинство сгорает в атмосфере. Метеоры — «падающие звёзды» — это не звёзды: просто пыль размером с горошину.\n\n💡 *Факт дня:* Самый крупный упавший метеорит — Хоба в Намибии, 60 тонн."},
    {"day":23,"title":"🔬 Астрохимия","text":"В космосе обнаружено 300+ молекул, включая сахара, аминокислоты, спирт. Органические молекулы найдены в метеоритах и кометах — это строительные блоки жизни.\n\n💡 *Факт дня:* В центре Млечного Пути найдено облако с концентрацией этилового спирта."},
    {"day":24,"title":"⏱ Теория относительности и космос","text":"ОТО Эйнштейна объясняет гравитацию как искривление пространства-времени. GPS-спутники делают поправку на замедление времени в слабом поле и при движении.\n\n💡 *Факт дня:* Без поправки на относительность GPS ошибался бы на 11 км в сутки."},
    {"day":25,"title":"🌪 Погода в космосе","text":"Космическая погода — активность Солнца: вспышки, выбросы корональной массы, солнечный ветер. Влияет на спутники, связь, электросети, авиацию.\n\n💡 *Факт дня:* Буря 1989 года обесточила провинцию Квебек на 9 часов из-за перегрузки электросетей."},
    {"day":26,"title":"🔵 Нейтронные звёзды и пульсары","text":"Нейтронные звёзды — плотнейшие видимые объекты. Диаметр ~20 км, масса 2× масса Солнца. Пульсары — вращающиеся нейтронные звёзды, точнейшие «часы» Вселенной.\n\n💡 *Факт дня:* Пульсар PSR J1748-2446ad вращается 716 раз в секунду."},
    {"day":27,"title":"🏔 Геология других планет","text":"Марс имел древние реки, озёра, возможно океаны. Венера — вулканически активна. На Плутоне — азотные ледники и горы изо льда высотой 3 км.\n\n💡 *Факт дня:* Вулкан Олимп Монс на Марсе — высочайший в Солнечной системе: 22 км над уровнем равнины."},
    {"day":28,"title":"📡 Радиоастрономия","text":"Радиотелескопы улавливают радиоволны от далёких объектов. VLA, Arecibo (до 2020), FAST (Китай, 500 м) — крупнейшие. Открытие пульсаров, реликтового излучения — заслуга радиоастрономии.\n\n💡 *Факт дня:* Китайский телескоп FAST обнаружил более 700 новых пульсаров."},
    {"day":29,"title":"🌐 Будущее космонавтики","text":"Artemis — возвращение на Луну и лунная база к 2030-м. SpaceX Starship — первые люди на Марсе в 2030-х. Космический туризм уже реален. Роботы-телескопы ищут ещё 5000 экзопланет.\n\n💡 *Факт дня:* SpaceX стоит дешевле вывода 1 кг на орбиту в 10+ раз по сравнению с шаттлом."},
    {"day":30,"title":"🏆 Финал курса — Место человека во Вселенной","text":"Вы прошли путь от Солнца до края Вселенной. Мы — звёздная пыль, способная осознать себя. Каждый атом вашего тела был рождён в сверхновой миллиарды лет назад.\n\n_«Звёзды не беспокоятся о том, наблюдают ли их. Это делаем мы.»_ — Карл Саган\n\n🎓 Поздравляем с завершением курса «Астрономия за 30 дней»!"},
]

# ── Калькулятор полётного времени ─────────────────────────────────────────────
FLIGHT_TARGETS = {
    "moon":    {"name":"🌕 Moon",    "km":384400,    "desc":"Earth's satellite"},
    "mars":    {"name":"🔴 Mars",    "km":78000000,  "desc":"Avg. closest approach"},
    "jupiter": {"name":"🪐 Jupiter", "km":628730000, "desc":"Avg. distance"},
    "saturn":  {"name":"🪐 Saturn",  "km":1277000000,"desc":"Avg. distance"},
    "pluto":   {"name":"🔵 Pluto",   "km":5906000000,"desc":"Avg. distance"},
    "proxima": {"name":"⭐ Proxima Centauri","km":40208000000000,"desc":"Nearest star"},
    "andromeda":{"name":"🌌 Andromeda","km":2.365e19,"desc":"Nearest spiral galaxy"},
}
FLIGHT_SPEEDS = {
    "car":     {"name":"🚗 Car",         "kmh":120},
    "plane":   {"name":"✈️ Plane",       "kmh":900},
    "rocket":  {"name":"🚀 Rocket (Apollo)","kmh":39600},
    "starship":{"name":"🛸 Starship (projected)","kmh":100000},
    "light":   {"name":"⚡ Lightspeed",  "kmh":1079251200},
}
# ── End: NEW STATIC DATA ──────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: NEW KEYBOARDS                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def profile_kb(lang):
    L=lambda k:tx(lang,k)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ "+L("btn_favorites"),    callback_data="favorites_view"),
         InlineKeyboardButton("📊 "+L("btn_mystats"),     callback_data="my_stats")],
        [InlineKeyboardButton("🏆 "+L("btn_achievements"),callback_data="achievements"),
         InlineKeyboardButton("🔔 "+L("btn_smart_alerts"),callback_data="smart_alerts_menu")],
        [InlineKeyboardButton(L("btn_iss_schedule"),       callback_data="iss_schedule")],
        [InlineKeyboardButton(L("back_menu"), callback_data="back")],
    ])

def missions_kb(lang):
    rows=[]
    for i,m in enumerate(MISSIONS_DATA):
        rows.append([InlineKeyboardButton(m["name"][:40],callback_data=f"mission_{i}")])
    rows.append([InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")])
    return InlineKeyboardMarkup(rows)

def satellite_kb(lang):
    rows=[]
    items=list(SATELLITE_CATALOG.items())
    for i in range(0,len(items),2):
        row=[]
        for key,sat in items[i:i+2]:
            row.append(InlineKeyboardButton(f"{sat['emoji']} {sat['name'][:15]}",callback_data=f"sat_{key}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")])
    return InlineKeyboardMarkup(rows)

def flight_target_kb(lang):
    rows=[]
    items=list(FLIGHT_TARGETS.items())
    for i in range(0,len(items),2):
        row=[InlineKeyboardButton(v["name"],callback_data=f"flight_target_{k}") for k,v in items[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")])
    return InlineKeyboardMarkup(rows)

def flight_speed_kb(lang,target_key):
    rows=[]
    for k,v in FLIGHT_SPEEDS.items():
        rows.append([InlineKeyboardButton(v["name"],callback_data=f"flight_calc_{target_key}_{k}")])
    rows.append([InlineKeyboardButton(tx(lang,"back_menu"),callback_data="flight_calculator")])
    return InlineKeyboardMarkup(rows)

def challenge_kb(lang, q_idx, answered=False):
    q=CHALLENGE_DATA[q_idx]
    if answered:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(tx(lang,"challenge_next"),callback_data="daily_challenge_start"),
            InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back"),
        ]])
    rows=[[InlineKeyboardButton(f"{chr(65+i)}. {opt[:30]}",callback_data=f"challenge_ans_{q_idx}_{i}")] for i,opt in enumerate(q["options"])]
    rows.append([InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")])
    return InlineKeyboardMarkup(rows)

def dict_kb(lang):
    rows=[]
    items=[(k,v) for k,v in SPACE_DICT.items()]
    for i in range(0,len(items),3):
        row=[InlineKeyboardButton(v["emoji"]+" "+v.get(lang,v["en"])[0][:14],callback_data=f"dict_{k}") for k,v in items[i:i+3]]
        rows.append(row)
    rows.append([InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")])
    return InlineKeyboardMarkup(rows)

def course_kb(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tx(lang,"course_subscribe_btn"),callback_data="course_subscribe")],
        [InlineKeyboardButton(tx(lang,"course_browse_btn"),callback_data="course_browse")],
        [InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")],
    ])
# ── End: NEW KEYBOARDS ────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: ACHIEVEMENT TRACKER                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def update_stats(chat_id, action, value=1):
    """Call this from existing handlers to track user activity."""
    cid=str(chat_id); stats=load_stats()
    if cid not in stats:
        stats[cid]={"apod":0,"quiz":0,"quiz_perfect":0,"mars":0,"news":0,"sections":0,
                    "challenge":0,"favorites":0,"streak":0,"night_session":0,"days":[]}
    s=stats[cid]
    if action in s: s[action]=s.get(action,0)+value
    today=date.today().isoformat()
    if today not in s.get("days",[]):
        s.setdefault("days",[]).append(today)
        # check streak
        days=sorted(s["days"])[-8:]
        streak=1
        for i in range(len(days)-1,0,-1):
            d1=datetime.strptime(days[i],"%Y-%m-%d").date()
            d2=datetime.strptime(days[i-1],"%Y-%m-%d").date()
            if (d1-d2).days==1: streak+=1
            else: break
        s["streak"]=streak
    # check night (20:00-05:00)
    h=datetime.now().hour
    if h>=20 or h<=5: s["night_session"]=s.get("night_session",0)+1
    save_stats(stats)
    _check_new_achievements(chat_id, s)

def _check_new_achievements(chat_id, s):
    cid=str(chat_id); ach=load_achievements()
    if cid not in ach: ach[cid]={"earned":[]}
    new_badges=[]
    for badge in ACHIEVEMENTS_DEF:
        if badge["id"] in ach[cid]["earned"]: continue
        cond=badge["condition"]; field,_,val=cond.partition(">=")
        try:
            if s.get(field,0)>=int(val):
                ach[cid]["earned"].append(badge["id"])
                new_badges.append(badge)
        except: pass
    if new_badges:
        save_achievements(ach)
    return new_badges
# ── End: ACHIEVEMENT TRACKER ──────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: SATELLITE TRACKER HANDLER                                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def satellite_tracker_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    await safe_edit(q,f"{tx(lang,'sat_tracker_title')}\n\n{tx(lang,'sat_tracker_choose')}",reply_markup=satellite_kb(lang))

async def sat_detail_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    sat_key=q.data.replace("sat_","")
    sat=SATELLITE_CATALOG.get(sat_key)
    if not sat: await safe_edit(q,"❌ Not found",reply_markup=back_kb(lang,ctx=ctx)); return
    # Try live position from wheretheiss.at or N2YO
    pos_text=""; url_text=""
    try:
        if sat_key=="iss":
            pos=get_iss_position()
            pos_text=f"\n🌍 *Live position:* `{pos['lat']:+.3f}°, {pos['lon']:+.3f}°`"
            url_text=f"\n[📍 Live map](https://www.google.com/maps?q={pos['lat']},{pos['lon']})"
        else:
            r=requests.get(f"https://api.wheretheiss.at/v1/satellites/{sat['norad']}",timeout=8)
            if r.status_code==200:
                d=r.json()
                lat=d.get("latitude",0); lon=d.get("longitude",0)
                alt=d.get("altitude",sat["alt_km"]); spd=d.get("velocity",0)
                pos_text=f"\n🌍 *Live:* `{lat:+.3f}°, {lon:+.3f}°`\n⬆️ Alt: {alt:.0f} km  |  ⚡ {spd:.0f} km/h"
                url_text=f"\n[📍 Map](https://www.google.com/maps?q={lat},{lon})"
    except: pos_text=f"\n📍 Orbit: {sat['alt_km']:,} km"
    text=(f"{sat['emoji']} *{sat['name']}*\n"
          f"🚀 Launched: {sat['launched']}\n"
          f"🔄 Orbital period: {sat.get('period_min',92)} min\n"
          f"{pos_text}\n\n_{sat['desc']}_{url_text}")
    await safe_edit(q,text[:4096],reply_markup=back_kb(lang,"satellite_tracker",ctx))
# ── End: SATELLITE TRACKER HANDLER ───────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: EARTHQUAKE / EONET HANDLER                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def earthquakes_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🌍...")
    try:
        r=requests.get("https://eonet.gsfc.nasa.gov/api/v3/events?category=earthquakes&limit=10&status=open&days=7",timeout=12)
        r.raise_for_status(); events=r.json().get("events",[])
    except:
        events=[]
    if not events:
        # Fallback: USGS
        try:
            r=requests.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/5.0_week.geojson",timeout=12)
            feats=r.json().get("features",[])[:8]
            lines=[tx(lang,"eq_title_usgs")+"\n"]
            for f in feats:
                p=f["properties"]; c=f["geometry"]["coordinates"]
                mag=p.get("mag","?"); place=p.get("place","?")[:40]
                t_ms=p.get("time",0); t_str=datetime.fromtimestamp(t_ms/1000).strftime("%d.%m %H:%M") if t_ms else "?"
                lat=c[1]; lon=c[0]
                lines.append(f"⚡ *M{mag}* — {place}\n   📅 {t_str} UTC | [Map](https://www.google.com/maps?q={lat},{lon})\n")
            text="\n".join(lines)[:4096]
        except Exception as e:
            text=f"❌ Could not load earthquake data: {e}"
    else:
        lines=[tx(lang,"eq_title_eonet")+"\n"]
        for ev in events[:8]:
            title=ev.get("title","?"); geom=ev.get("geometry",[{}])
            coords=geom[0].get("coordinates",[0,0,0]) if geom else [0,0,0]
            date_ev=(geom[0].get("date","?") or "?")[:16].replace("T"," ")
            lat,lon=coords[1],coords[0]
            lines.append(f"⚡ *{title}*\n   📅 {date_ev} | [Map](https://www.google.com/maps?q={lat},{lon})\n")
        text="\n".join(lines)[:4096]
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"eq_subscribe"),callback_data="notif_toggle_earthquakes"),InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")]])
    await safe_edit(q,text,reply_markup=kb)

async def job_earthquake_alert(context):
    subs=load_subscribers(); chat_ids=subs.get("earthquakes",[])
    if not chat_ids: return
    try:
        r=requests.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/6.0_day.geojson",timeout=12)
        feats=r.json().get("features",[])
        if not feats: return
        msg="🚨 *Earthquake Alert M≥6.0!*\n\n"
        for f in feats[:3]:
            p=f["properties"]; mag=p.get("mag","?"); place=p.get("place","?")[:50]
            msg+=f"⚡ *M{mag}* — {place}\n"
        for cid in chat_ids:
            try: await context.bot.send_message(cid,msg[:4096],parse_mode="Markdown")
            except: pass
    except Exception as e: logger.error(f"job_earthquake_alert: {e}")
# ── End: EARTHQUAKE / EONET HANDLER ──────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: SPACEWEATHER DIGEST                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def spaceweather_digest_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,tx(lang,"sw_digest_loading"))
    sections=[]
    # 1. Kp index
    try:
        r=requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",timeout=10); r.raise_for_status()
        data=r.json(); kp=float(data[-1].get("kp_index",data[-1].get("Kp",0)))
        kp_bar="🟢" if kp<4 else "🟡" if kp<6 else "🟠" if kp<8 else "🔴"
        sections.append(f"{kp_bar} *Kp-index:* {kp:.1f}/9")
    except: sections.append("⚪ Kp: N/A")
    # 2. Solar wind speed
    try:
        r=requests.get("https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json",timeout=10); r.raise_for_status()
        data=r.json(); spd=float(data[-1][2])
        sections.append(f"💨 *Solar wind:* {spd:,.0f} km/s")
    except: sections.append("💨 Solar wind: N/A")
    # 3. X-ray flux
    try:
        r=requests.get("https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json",timeout=10); r.raise_for_status()
        flux=float(r.json()[-1].get("flux",0))
        cls_="X" if flux>=1e-4 else "M" if flux>=1e-5 else "C" if flux>=1e-6 else "B" if flux>=1e-7 else "A"
        sections.append(f"⚡ *Flares:* Class {cls_} ({flux:.1e} W/m²)")
    except: sections.append("⚡ Flares: N/A")
    # 4. Moon
    emoji,_,_,illum=get_moon_phase(date.today())
    sections.append(f"{emoji} *Moon:* {illum}% illuminated")
    text=(f"{tx(lang,'sw_digest_title')}\n📅 {date.today().strftime('%d %b %Y')}\n\n"+"\n".join(sections)+
          "\n\n[🔗 NOAA SWPC](https://www.swpc.noaa.gov)")
    await safe_edit(q,text,reply_markup=back_kb(lang,"spaceweather_digest",ctx))

async def job_spaceweather_digest(context):
    subs=load_subscribers(); chat_ids=subs.get("spaceweather_digest",[])
    if not chat_ids: return
    try:
        sections=[]
        r=requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",timeout=10)
        kp=float(r.json()[-1].get("kp_index",0))
        sections.append(f"🌡 Kp: {kp:.1f}"); sections.append(f"📅 {date.today().strftime('%d %b')}")
        msg="☀️ *Daily Space Weather*\n\n"+"\n".join(sections)
        for cid in chat_ids:
            try: await context.bot.send_message(cid,msg,parse_mode="Markdown")
            except: pass
    except Exception as e: logger.error(f"job_spaceweather_digest: {e}")
# ── End: SPACEWEATHER DIGEST ──────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: EXOPLANET ALERT HANDLER + SCHEDULED JOB                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def exoplanet_alert_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,tx(lang,"exo_loading"))
    try:
        # NASA Exoplanet Archive — confirmed planets in the last 30 days
        r=requests.get(
            "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=select+pl_name,disc_year,discoverymethod,pl_orbper,pl_rade,st_dist+from+pscomppars+where+disc_year>=2025+order+by+rowupdate+desc&format=json",
            timeout=15)
        planets=r.json() if r.status_code==200 else []
    except: planets=[]
    if not planets:
        text=(f"{tx(lang,'exo_title')}\n\n"
              f"{tx(lang,'exo_no_data')}\n\n"
              f"{tx(lang,'exo_total')}\n"
              f"[NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu)")
    else:
        text=tx(lang,"exo_recent")+"\n\n"
        for p in planets[:8]:
            name=p.get("pl_name","?"); method=p.get("discoverymethod","?")
            dist=p.get("st_dist","?"); period=p.get("pl_orbper","?")
            try: dist=f"{float(dist):.1f} pc"
            except: dist=str(dist)
            try: period=f"{float(period):.1f} days"
            except: period=str(period)
            text+=f"🪐 *{name}*\n   Method: {method} | Period: {period} | Dist: {dist}\n\n"
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"exo_weekly"),callback_data="notif_toggle_exoplanets"),InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")]])
    await safe_edit(q,text[:4096],reply_markup=kb)

async def job_exoplanet_alert(context):
    subs=load_subscribers(); chat_ids=subs.get("exoplanets",[])
    if not chat_ids: return
    try:
        r=requests.get("https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=select+pl_name,discoverymethod+from+pscomppars+where+disc_year>=2025+order+by+rowupdate+desc&format=json&maxrec=5",timeout=15)
        planets=r.json() if r.status_code==200 else []
        if not planets: return
        msg="🔭 *New Exoplanet Discoveries This Week!*\n\n"
        for p in planets[:5]: msg+=f"🪐 *{p.get('pl_name','?')}* — {p.get('discoverymethod','?')}\n"
        for cid in chat_ids:
            try: await context.bot.send_message(cid,msg,parse_mode="Markdown")
            except: pass
    except: pass
# ── End: EXOPLANET ALERT HANDLER ─────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: ACHIEVEMENTS HANDLER                                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def achievements_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    cid=str(q.message.chat_id); ach=load_achievements()
    earned=ach.get(cid,{}).get("earned",[])
    lines=[tx(lang,"ach_title")+"\n"]
    for badge in ACHIEVEMENTS_DEF:
        got=badge["id"] in earned
        name=badge.get(lang, badge["en"])
        lines.append(f"{'✅' if got else '🔒'} {badge['emoji']} {name}")
    lines.append("\n"+tx(lang,"ach_earned",n=len(earned),total=len(ACHIEVEMENTS_DEF)))
    await safe_edit(q,"\n".join(lines),reply_markup=back_kb(lang,"cat_interact",ctx))
# ── End: ACHIEVEMENTS HANDLER ─────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: DAILY HOROSCOPE (TODAY with live Kp + moon)                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def daily_horoscope_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🌌 Computing...")
    # Get live Kp
    kp=0.0
    try:
        r=requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",timeout=10)
        kp=float(r.json()[-1].get("kp_index",r.json()[-1].get("Kp",0)))
    except: pass
    # Moon
    moon_emoji,moon_idx,moon_day,moon_illum=get_moon_phase(date.today())
    # Star sign based on today's date as "birthday"
    today=date.today(); sign=get_zodiac(today.month,today.day)
    # Cosmic energy based on Kp + moon
    if kp>=7 or moon_idx==4: energy=tx(lang,"horo_energy_high")
    elif kp>=4 or moon_idx in (2,6): energy=tx(lang,"horo_energy_mod")
    else: energy=tx(lang,"horo_energy_calm")
    DAILY_ADVICE={
        "ru":["Идеальный день для новых начинаний","Время для размышлений","Обрати взгляд на звёзды","Сила Вселенной на твоей стороне","День открытий и чудес"],
        "en":["Perfect day for new beginnings","Time for reflection","Look up to the stars","The universe's force is with you","A day of discoveries"],
        "he":["יום מושלם להתחלות חדשות","זמן לחשיבה","הבט לכוכבים","כוח היקום איתך","יום של גילויים"],
        "ar":["يوم مثالي لبدايات جديدة","وقت للتأمل","انظر إلى النجوم","قوة الكون معك","يوم اكتشافات"],
    }
    seed=today.toordinal()%len(DAILY_ADVICE["en"])
    advice=DAILY_ADVICE.get(lang,DAILY_ADVICE["en"])[seed]
    text=(f"{tx(lang,'horo_title',d=today.strftime('%d %b %Y'))}\n\n"
          f"{moon_emoji} *{tx(lang,'horo_moon')}* {moon_illum}% | Day {moon_day}/30\n"
          f"⚡ *{tx(lang,'horo_kp')}* {kp:.1f}  |  {energy}\n\n"
          f"{tx(lang,'horo_sign')} {sign}\n"
          f"✨ _{advice}_\n\n"
          f"{tx(lang,'horo_aurora_high') if kp>=4 else ''}")
    await safe_edit(q,text.strip(),reply_markup=back_kb(lang,"daily_horoscope",ctx))
# ── End: DAILY HOROSCOPE ──────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: DAILY CHALLENGE CONV HANDLER                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def daily_challenge_start(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    q_idx=date.today().toordinal()%len(CHALLENGE_DATA)
    ctx.user_data["challenge_q"]=q_idx; ctx.user_data["challenge_answered"]=False
    chall=CHALLENGE_DATA[q_idx]
    await safe_edit(q,tx(lang,"challenge_loading"))
    caption=f"{tx(lang,'challenge_title')}\n\n{tx(lang,'challenge_question')}"
    try:
        r=requests.get("https://images-api.nasa.gov/search",
            params={"q":chall["img_q"],"media_type":"image","page_size":10},timeout=12)
        items=[it for it in r.json().get("collection",{}).get("items",[]) if it.get("links")]
        if items:
            img_url=(random.choice(items[:8]).get("links",[{}])[0]).get("href","")
            if img_url:
                await del_msg(q)
                await ctx.bot.send_photo(chat_id=q.message.chat_id,photo=img_url,
                    caption=caption,parse_mode="Markdown",reply_markup=challenge_kb(lang,q_idx))
                return
    except: pass
    await del_msg(q)
    await ctx.bot.send_message(chat_id=q.message.chat_id,
        text=caption,parse_mode="Markdown",reply_markup=challenge_kb(lang,q_idx))

async def challenge_answer_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    parts=q.data.split("_"); q_idx=int(parts[2]); ans=int(parts[3])
    chall=CHALLENGE_DATA[q_idx]; correct=chall["answer"]; is_right=(ans==correct)
    update_stats(q.message.chat_id,"challenge",1)
    if is_right: update_stats(q.message.chat_id,"sections",1)
    result=tx(lang,"challenge_correct") if is_right else tx(lang,"challenge_wrong",ans=chall['options'][correct])
    text=f"{tx(lang,'challenge_result_title')}\n\n{result}\n\n💡 _{chall['fact']}_"
    await safe_edit(q,text,reply_markup=challenge_kb(lang,q_idx,answered=True))
# ── End: DAILY CHALLENGE ──────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: ROCKET LANDING GAME CONV HANDLER (Falcon 9)                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
ROCKET_STEPS=[
    {"alt":70,"vel":1800,"fuel":42,"desc":"Stage separation complete. Reentry burn starting.",
     "choices":{"A":("Initiate reentry burn",True),"B":("Skip burn to save fuel",False),"C":("Abort — return to orbit",False)},
     "hint":"You need the reentry burn to reduce speed before atmosphere."},
    {"alt":30,"vel":800,"fuel":28,"desc":"Atmospheric reentry. Grid fins deployed.",
     "choices":{"A":("Deploy grid fins early",True),"B":("Hold grid fins",False),"C":("Increase throttle",False)},
     "hint":"Grid fins help steer and slow the rocket in the atmosphere."},
    {"alt":5,"vel":250,"fuel":15,"desc":"Final approach. Landing site confirmed. 5km altitude.",
     "choices":{"A":("Initiate boostback burn",False),"B":("Deploy landing legs + ignite engine",True),"C":("Cut engine",False)},
     "hint":"You need landing legs and engine to cushion the touchdown."},
    {"alt":0.01,"vel":5,"fuel":3,"desc":"10 meters. Touchdown in 3 seconds.",
     "choices":{"A":("Full throttle",False),"B":("Cut engine",False),"C":("Hover and settle",True)},
     "hint":"Gentle hover lets legs absorb the last meters safely."},
]

async def rocket_game_start(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    ctx.user_data["rocket_step"]=0; ctx.user_data["rocket_alive"]=True
    await _show_rocket_step(q,ctx,0)
    return ROCKET_STEP

async def _show_rocket_step(q,ctx,step_idx):
    s=ROCKET_STEPS[step_idx]; lang=get_lang(ctx)
    text=(f"{tx(lang,'rocket_title')}\n"
          f"{tx(lang,'rocket_step_label',n=step_idx+1,total=len(ROCKET_STEPS))}\n\n"
          f"📍 Alt: *{s['alt']} km*  |  💨 Speed: *{s['vel']} m/s*  |  ⛽ Fuel: *{s['fuel']}%*\n\n"
          f"_{s['desc']}_\n\n"
          f"{tx(lang,'rocket_what_do')}")
    rows=[[InlineKeyboardButton(f"{k}. {v[0]}",callback_data=f"rocket_choice_{step_idx}_{k}")] for k,v in s["choices"].items()]
    rows.append([InlineKeyboardButton(tx(lang,"rocket_abort"),callback_data="back")])
    await safe_edit(q,text,reply_markup=InlineKeyboardMarkup(rows))

async def rocket_choice_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    parts=q.data.split("_"); step_idx=int(parts[2]); choice=parts[3]
    s=ROCKET_STEPS[step_idx]; is_correct=s["choices"][choice][1]
    if not is_correct:
        text=(f"{tx(lang,'rocket_boom')}\n\n"
              f"{tx(lang,'rocket_wrong_call',n=step_idx+1)}\n"
              f"💡 _{s['hint']}_\n\n"
              f"{tx(lang,'rocket_crashed')}\n{tx(lang,'rocket_rsd')}")
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"rocket_try_again"),callback_data="rocket_game"),InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")]])
        await safe_edit(q,text,reply_markup=kb)
        return ConversationHandler.END
    next_step=step_idx+1
    if next_step>=len(ROCKET_STEPS):
        text=(f"{tx(lang,'rocket_touchdown')}\n\n"
              f"{tx(lang,'rocket_landed')}\n"
              f"{tx(lang,'rocket_fuel')}\n\n"
              f"{tx(lang,'rocket_mastered')}\n"
              f"{tx(lang,'rocket_since2015')}")
        update_stats(q.message.chat_id,"sections",1)
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"rocket_play_again"),callback_data="rocket_game"),InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")]])
        await safe_edit(q,text,reply_markup=kb)
        return ConversationHandler.END
    ctx.user_data["rocket_step"]=next_step
    text=f"{tx(lang,'rocket_good_call')}\n_{s['hint']}_\n\n{tx(lang,'rocket_next')}"
    await safe_edit(q,text)
    await _show_rocket_step(q,ctx,next_step)
    return ROCKET_STEP
# ── End: ROCKET LANDING GAME ──────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: CLAUDE API Q&A CONV HANDLER                                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def qa_start(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    ctx.user_data["qa_lang"]=lang
    await del_msg(q)
    prompt={"ru":"💬 Задай любой вопрос о космосе — отвечу с точностью астронома!",
            "en":"💬 Ask me anything about space — I'll answer with an astronomer's precision!",
            "he":"💬 שאל אותי כל שאלה על החלל!",
            "ar":"💬 اسألني أي شيء عن الفضاء!"}
    await ctx.bot.send_message(chat_id=q.message.chat_id,text=prompt.get(lang,prompt["en"]),
        parse_mode="Markdown")
    return QA_QUESTION

async def qa_answer(update, ctx):
    lang=ctx.user_data.get("qa_lang","en")
    question=update.message.text.strip()
    if len(question)<3 or len(question)>500:
        await update.message.reply_text(tx(lang,"qa_chars_error")); return QA_QUESTION
    thinking=await update.message.reply_text(tx(lang,"qa_thinking"))
    if not ANTHROPIC_API_KEY:
        await thinking.edit_text(tx(lang,"qa_api_error"))
        return ConversationHandler.END
    try:
        sys_prompt=f"You are an expert astronomer and space scientist. Answer in {lang} language. Be concise (max 300 words), accurate, and engaging. Use emojis sparingly. End with one fascinating related fact."
        resp=requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            json={"model":CLAUDE_MODEL,"max_tokens":512,"system":sys_prompt,
                  "messages":[{"role":"user","content":question}]},timeout=30)
        answer=resp.json()["content"][0]["text"]
    except Exception as e:
        answer=f"❌ Error: {e}"
    update_stats(update.effective_chat.id,"sections",1)
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"qa_ask_another"),callback_data="space_qa"),InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")]])
    await thinking.edit_text(f"🔭 *Q: {question[:60]}...*\n\n{answer}"[:4096],
        parse_mode="Markdown",reply_markup=kb)
    return ConversationHandler.END

async def qa_cancel(update, ctx):
    lang=ctx.user_data.get("qa_lang","en")
    await update.message.reply_text(tx(lang,"cancelled")); return ConversationHandler.END
# ── End: CLAUDE API Q&A ───────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: FAVORITES HANDLERS                                                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def favorites_save_h(update, ctx):
    """Called when user taps ⭐ Save on APOD. Data passed via ctx.user_data."""
    q=update.callback_query; lang=get_lang(ctx); await safe_answer(q,tx(lang,"fav_saved"),show_alert=False)
    apod_data=ctx.user_data.get("last_apod",{})
    if not apod_data: return
    cid=str(q.message.chat_id); favs=load_favorites()
    if cid not in favs: favs[cid]=[]
    if len(favs[cid])>=50:
        await safe_answer(q,tx(lang,"fav_max"),show_alert=True); return
    entry={"date":apod_data.get("date",date.today().isoformat()),"title":apod_data.get("title","APOD"),"url":apod_data.get("url",""),"hdurl":apod_data.get("hdurl","")}
    if not any(f["date"]==entry["date"] for f in favs[cid]):
        favs[cid].insert(0,entry); save_favorites(favs)
        update_stats(q.message.chat_id,"favorites",1)

async def favorites_view_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    cid=str(q.message.chat_id); favs=load_favorites(); my_favs=favs.get(cid,[])
    if not my_favs:
        await safe_edit(q,f"{tx(lang,'fav_title')}\n\n{tx(lang,'fav_empty')}",
            reply_markup=back_kb(lang,ctx=ctx)); return
    lines=[tx(lang,"fav_your")+"\n"]
    for i,f in enumerate(my_favs[:15]):
        link=f"[{f['title'][:35]}]({f.get('hdurl') or f.get('url','')})"
        lines.append(f"{i+1}. {link} _{f['date']}_")
    lines.append("\n"+tx(lang,"fav_total",n=len(my_favs)))
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"fav_clear"),callback_data="favorites_clear"),InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")]])
    await safe_edit(q,"\n".join(lines)[:4096],reply_markup=kb)

async def favorites_clear_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    cid=str(q.message.chat_id); favs=load_favorites()
    favs[cid]=[]; save_favorites(favs)
    await safe_edit(q,tx(lang,"fav_cleared"),reply_markup=back_kb(lang,ctx=ctx))
# ── End: FAVORITES HANDLERS ───────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: SMART ALERTS CONV HANDLER                                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def smart_alerts_menu_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    cid=str(q.message.chat_id); alerts=load_smart_alerts(); my=alerts.get(cid,{})
    kp_t=my.get("kp_threshold",7); ld_t=my.get("asteroid_ld",2); eq_t=my.get("earthquake_min",6)
    text=(f"{tx(lang,'smart_title')}\n\n"
          f"{tx(lang,'smart_kp_desc',v=kp_t)}\n"
          f"{tx(lang,'smart_ast_desc',v=ld_t)}\n"
          f"{tx(lang,'smart_eq_desc',v=eq_t)}\n\n"
          f"{tx(lang,'smart_tap')}")
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚡ Kp ≥ {kp_t} (change)",callback_data="smart_set_kp")],
        [InlineKeyboardButton(f"☄️ Asteroid < {ld_t} LD (change)",callback_data="smart_set_ld")],
        [InlineKeyboardButton(f"🌍 Earthquake M ≥ {eq_t} (change)",callback_data="smart_set_eq")],
        [InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")],
    ])
    await safe_edit(q,text,reply_markup=kb)

async def smart_set_kp_start(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    ctx.user_data["smart_lang"]=lang
    await del_msg(q)
    await ctx.bot.send_message(q.message.chat_id,tx(lang,"smart_kp_ask"),parse_mode="Markdown")
    return SMART_KP

async def smart_kp_received(update, ctx):
    lang=ctx.user_data.get("smart_lang","en")
    try:
        val=int(update.message.text.strip())
        if not 1<=val<=9: raise ValueError
    except:
        await update.message.reply_text(tx(lang,"smart_kp_err")); return SMART_KP
    cid=str(update.effective_chat.id); alerts=load_smart_alerts()
    if cid not in alerts: alerts[cid]={}
    alerts[cid]["kp_threshold"]=val; save_smart_alerts(alerts)
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"smart_back"),callback_data="smart_alerts_menu")]])
    await update.message.reply_text(tx(lang,"smart_kp_set",v=val),parse_mode="Markdown",reply_markup=kb)
    return ConversationHandler.END

async def smart_set_ld_start(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    ctx.user_data["smart_lang"]=lang
    await del_msg(q)
    await ctx.bot.send_message(q.message.chat_id,tx(lang,"smart_ld_ask"),parse_mode="Markdown")
    return SMART_LD

async def smart_ld_received(update, ctx):
    lang=ctx.user_data.get("smart_lang","en")
    try:
        val=float(update.message.text.strip().replace(",","."))
        if not 0.5<=val<=20: raise ValueError
    except:
        await update.message.reply_text(tx(lang,"smart_ld_err")); return SMART_LD
    cid=str(update.effective_chat.id); alerts=load_smart_alerts()
    if cid not in alerts: alerts[cid]={}
    alerts[cid]["asteroid_ld"]=val; save_smart_alerts(alerts)
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"smart_back"),callback_data="smart_alerts_menu")]])
    await update.message.reply_text(tx(lang,"smart_ld_set",v=val),parse_mode="Markdown",reply_markup=kb)
    return ConversationHandler.END

async def smart_set_eq_start(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    ctx.user_data["smart_lang"]=lang
    await del_msg(q)
    await ctx.bot.send_message(q.message.chat_id,tx(lang,"smart_eq_ask"),parse_mode="Markdown")
    return SMART_KP  # reuse same state

async def smart_eq_received(update, ctx):
    lang=ctx.user_data.get("smart_lang","en")
    try:
        val=float(update.message.text.strip()); assert 4<=val<=9
    except:
        await update.message.reply_text(tx(lang,"smart_eq_err")); return SMART_KP
    cid=str(update.effective_chat.id); alerts=load_smart_alerts()
    if cid not in alerts: alerts[cid]={}
    alerts[cid]["earthquake_min"]=val; save_smart_alerts(alerts)
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"smart_back"),callback_data="smart_alerts_menu")]])
    await update.message.reply_text(tx(lang,"smart_eq_set",v=val),parse_mode="Markdown",reply_markup=kb)
    return ConversationHandler.END

async def smart_cancel(update, ctx):
    lang=ctx.user_data.get("smart_lang","en")
    await update.message.reply_text(tx(lang,"cancelled")); return ConversationHandler.END

async def job_smart_alerts_check(context):
    """Hourly: check live Kp + asteroids against user thresholds."""
    alerts=load_smart_alerts()
    if not alerts: return
    # Get Kp
    try:
        r=requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",timeout=10)
        kp=float(r.json()[-1].get("kp_index",0))
    except: kp=0
    # Get asteroid
    today=date.today().isoformat()
    neo_danger=[]
    try:
        data=nasa_req("/neo/rest/v1/feed",{"start_date":today,"end_date":today})
        neos=data["near_earth_objects"].get(today,[])
        for a in neos:
            ap=a["close_approach_data"][0] if a["close_approach_data"] else {}
            ld_dist=float(ap.get("miss_distance",{}).get("lunar","999"))
            neo_danger.append({"name":a["name"],"ld":ld_dist})
    except: pass
    for cid,prefs in alerts.items():
        try:
            cid_int=int(cid)
            # Kp alert
            kp_thresh=prefs.get("kp_threshold",7)
            if kp>=kp_thresh:
                try: await context.bot.send_message(cid_int,f"⚡ *Smart Alert: Kp {kp:.1f}!*\nThreshold {kp_thresh} reached — aurora may be visible!",parse_mode="Markdown")
                except: pass
            # Asteroid alert
            ld_thresh=prefs.get("asteroid_ld",2)
            for neo in neo_danger:
                if neo["ld"]<=ld_thresh:
                    try: await context.bot.send_message(cid_int,f"☄️ *Smart Alert: Close Asteroid!*\n{neo['name']} at {neo['ld']:.2f} LD (threshold {ld_thresh})",parse_mode="Markdown")
                    except: pass
        except: continue
# ── End: SMART ALERTS ─────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: MY STATS HANDLER                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def my_stats_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    cid=str(q.message.chat_id); stats=load_stats(); s=stats.get(cid,{})
    ach=load_achievements(); earned=len(ach.get(cid,{}).get("earned",[]))
    favs=load_favorites(); fav_count=len(favs.get(cid,[]))
    text=(f"{tx(lang,'stats_title')}\n\n"
          f"{tx(lang,'stats_apod')} *{s.get('apod',0)}*\n"
          f"{tx(lang,'stats_quiz')} *{s.get('quiz',0)}*\n"
          f"{tx(lang,'stats_perfect')} *{s.get('quiz_perfect',0)}*\n"
          f"{tx(lang,'stats_challenge')} *{s.get('challenge',0)}*\n"
          f"{tx(lang,'stats_favorites')} *{fav_count}*\n"
          f"{tx(lang,'stats_achievements')} *{earned}/{len(ACHIEVEMENTS_DEF)}*\n"
          f"{tx(lang,'stats_streak')} *{s.get('streak',0)} {tx(lang,'stats_streak_days')}*\n"
          f"{tx(lang,'stats_since')} *{min(s.get('days',[date.today().isoformat()]))[:10]}*")
    await safe_edit(q,text,reply_markup=back_kb(lang,"cat_interact",ctx))
# ── End: MY STATS HANDLER ─────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: ISS VISIBILITY SCHEDULE CONV HANDLER                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
# Major cities lookup (lat, lon)
CITY_COORDS = {
    "moscow":("Moscow 🇷🇺",55.7558,37.6173),"london":("London 🇬🇧",51.5074,-0.1278),
    "new york":("New York 🇺🇸",40.7128,-74.0060),"tel aviv":("Tel Aviv 🇮🇱",32.0853,34.7818),
    "dubai":("Dubai 🇦🇪",25.2048,55.2708),"tokyo":("Tokyo 🇯🇵",35.6762,139.6503),
    "paris":("Paris 🇫🇷",48.8566,2.3522),"berlin":("Berlin 🇩🇪",52.5200,13.4050),
    "kyiv":("Kyiv 🇺🇦",50.4501,30.5234),"istanbul":("Istanbul 🇹🇷",41.0082,28.9784),
    "beijing":("Beijing 🇨🇳",39.9042,116.4074),"sydney":("Sydney 🇦🇺",-33.8688,151.2093),
    "rio":("Rio de Janeiro 🇧🇷",-22.9068,-43.1729),"toronto":("Toronto 🇨🇦",43.6532,-79.3832),
    "cairo":("Cairo 🇪🇬",30.0444,31.2357),"singapore":("Singapore 🇸🇬",1.3521,103.8198),
}

async def iss_schedule_start(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    ctx.user_data["iss_sched_lang"]=lang
    await del_msg(q)
    cities=", ".join(k.title() for k in list(CITY_COORDS.keys())[:8])+"..."
    await ctx.bot.send_message(q.message.chat_id,
        f"{tx(lang,'iss_sched_title')}\n\n{tx(lang,'iss_sched_enter')}\n{tx(lang,'iss_sched_examples',cities=cities)}",
        parse_mode="Markdown")
    return ISS_CITY

async def iss_city_received(update, ctx):
    lang=ctx.user_data.get("iss_sched_lang","en")
    city_input=update.message.text.strip().lower()
    # Find city
    match=None
    for k,(name,lat,lon) in CITY_COORDS.items():
        if k in city_input or city_input in k:
            match=(name,lat,lon); break
    if not match:
        # Try geocoding via Nominatim
        try:
            r=requests.get(f"https://nominatim.openstreetmap.org/search?q={city_input}&format=json&limit=1",
                headers={"User-Agent":"NASASpaceBot/2.0"},timeout=8)
            res=r.json()
            if res:
                lat=float(res[0]["lat"]); lon=float(res[0]["lon"])
                city_name=res[0].get("display_name","").split(",")[0]
                match=(city_name,lat,lon)
        except: pass
    if not match:
        await update.message.reply_text(tx(lang,"iss_sched_not_found"))
        return ISS_CITY
    city_name,lat,lon=match
    # Get ISS passes from Open Notify
    passes=[]
    try:
        r=requests.get(f"http://api.open-notify.org/iss-pass.json?lat={lat}&lon={lon}&n=5",timeout=10)
        if r.status_code==200:
            for p in r.json().get("response",[]):
                rise_ts=p.get("risetime",0); dur=p.get("duration",0)
                rise_dt=datetime.fromtimestamp(rise_ts).strftime("%d.%m %H:%M")
                dur_min=f"{dur//60}m{dur%60:02d}s"
                passes.append(f"🛸 *{rise_dt}*  |  Duration: {dur_min}")
    except: pass
    if not passes:
        # Fallback: calculate from current position
        try:
            pos=get_iss_position()
            text=(f"{tx(lang,'iss_sched_over',city=city_name)}\n\n"
                  f"{tx(lang,'iss_sched_api_na')}\n\n"
                  f"{tx(lang,'iss_sched_position')}\n"
                  f"   Lat: {pos['lat']:+.2f}°  |  Lon: {pos['lon']:+.2f}°\n"
                  f"   {tx(lang,'iss_sched_alt')}\n\n"
                  f"{tx(lang,'iss_sched_orbit')}\n"
                  f"[Heavens Above](https://www.heavens-above.com/PassSummary.aspx?lat={lat}&lng={lon})")
        except: text=f"{tx(lang,'iss_sched_over',city=city_name)}\n\n[Heavens Above](https://heavens-above.com)"
    else:
        text=(f"{tx(lang,'iss_sched_over',city=city_name)}\n📍 {lat:+.2f}°, {lon:+.2f}°\n\n"
              f"{tx(lang,'iss_sched_passes')}\n\n"+"\n".join(passes)+
              f"\n\n{tx(lang,'iss_sched_times')}")
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")]])
    await update.message.reply_text(text[:4096],parse_mode="Markdown",reply_markup=kb,disable_web_page_preview=True)
    return ConversationHandler.END

async def iss_city_cancel(update, ctx):
    lang=ctx.user_data.get("iss_sched_lang","en")
    await update.message.reply_text(tx(lang,"cancelled")); return ConversationHandler.END
# ── End: ISS VISIBILITY ───────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: METEORITE MAP HANDLER                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def meteorite_map_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx); await safe_edit(q,"🗺 Loading...")
    try:
        r=requests.get("https://data.nasa.gov/resource/gh4g-9sfh.json?$limit=2000&$order=mass+DESC",timeout=15)
        r.raise_for_status(); data=r.json()[:10]
        lines=[tx(lang,"meteor_map_title")+"\n"]
        for m in data:
            name=m.get("name","?"); mass=m.get("mass","?")
            year=str(m.get("year","?"))[:4]
            rec=m.get("recclass","?")
            try: mass_t=f"{float(mass)/1000:,.1f} kg"
            except: mass_t=f"{mass} g"
            geo=m.get("geolocation",{})
            lat=geo.get("latitude","?"); lon=geo.get("longitude","?")
            try: map_link=f"[📍]( https://www.google.com/maps?q={lat},{lon})"
            except: map_link=""
            lines.append(f"☄️ *{name}* ({year}) — {mass_t} — {rec} {map_link}")
        text="\n".join(lines)+"\n\n[🔗 Full NASA Database](https://data.nasa.gov/resource/gh4g-9sfh.json)"
    except Exception as e:
        text=(tx(lang,"meteor_map_famous")+"\n\n"
              "☄️ *Hoba* (Namibia, 1920) — 60 tons — largest ever found\n"
              "☄️ *Chelyabinsk* (Russia, 2013) — 13,000 tons — injured 1,600 people\n"
              "☄️ *Allende* (Mexico, 1969) — 2 tons — oldest material in solar system\n"
              "☄️ *ALH84001* (Antarctica) — Martian meteorite with possible microfossils\n"
              "☄️ *Willamette* (USA) — 15.5 tons — largest in North America\n\n"
              "[🔗 NASA Meteorite Database](https://data.nasa.gov/resource/gh4g-9sfh.json)")
    await safe_edit(q,text[:4096],reply_markup=back_kb(lang,"meteorite_map",ctx))
# ── End: METEORITE MAP ────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: FLIGHT CALCULATOR HANDLER                                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def flight_calculator_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    await safe_edit(q,f"{tx(lang,'flight_title')}\n\n{tx(lang,'flight_choose')}",reply_markup=flight_target_kb(lang))

async def flight_target_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    target_key=q.data.replace("flight_target_","")
    target=FLIGHT_TARGETS.get(target_key)
    if not target: return
    ctx.user_data["flight_target"]=target_key
    await safe_edit(q,tx(lang,"flight_to",name=target['name'],desc=target['desc']),
        reply_markup=flight_speed_kb(lang,target_key))

async def flight_calc_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    parts=q.data.split("_"); speed_key=parts[-1]
    target_key="_".join(parts[2:-1]) if len(parts)>3 else parts[2]
    target=FLIGHT_TARGETS.get(target_key); speed=FLIGHT_SPEEDS.get(speed_key)
    if not target or not speed: return
    dist_km=target["km"]; kmh=speed["kmh"]
    hours=dist_km/kmh; days=hours/24; years=days/365.25
    if years>=1e6:     time_str=f"{years/1e6:.2f} million years"
    elif years>=1000:  time_str=f"{years:,.0f} years"
    elif years>=1:     time_str=f"{years:.1f} years"
    elif days>=1:      time_str=f"{days:.1f} days"
    else:              time_str=f"{hours:.1f} hours"
    # Fun context
    context_lines=[]
    if years>4 and speed_key!="light": context_lines.append(tx(lang,"flight_grandchildren"))
    if speed_key=="light" and target_key=="andromeda": context_lines.append(tx(lang,"flight_lightspeed"))
    if speed_key=="car" and target_key!="moon": context_lines.append(tx(lang,"flight_fuel"))
    text=(f"{tx(lang,'flight_result_title')}\n\n"
          f"{tx(lang,'flight_from',name=target['name'])}\n"
          f"{tx(lang,'flight_distance',km=f'{dist_km:,.0f}')}\n"
          f"{tx(lang,'flight_speed_label',name=speed['name'],kmh=f'{kmh:,.0f}')}\n\n"
          f"{tx(lang,'flight_time',t=time_str)}\n\n"
          f"{chr(10).join(context_lines)}")
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"flight_another"),callback_data="flight_calculator"),InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")]])
    await safe_edit(q,text.strip(),reply_markup=kb)
# ── End: FLIGHT CALCULATOR ────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: MISSION STATUS HANDLER                                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def mission_status_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    await safe_edit(q,f"{tx(lang,'missions_title')}\n{tx(lang,'missions_select')}",reply_markup=missions_kb(lang))

async def mission_detail_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    idx=int(q.data.replace("mission_",""))
    m=MISSIONS_DATA[idx]
    bar_len=20; filled=int(m["progress"]/100*bar_len)
    bar="█"*filled+"░"*(bar_len-filled)
    text=(f"{m['name']}\n"
          f"🏢 {m['agency']}  |  🛰 {m['type']}\n"
          f"🚀 Launch: {m['launched']}\n"
          f"📍 Location: {m['orbit']}\n"
          f"{m['status']}\n"
          f"[{bar}] {m['progress']}%\n\n"
          f"_{m['desc']}_\n\n"
          f"[🔗 Learn more]({m['url']})")
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"missions_all"),callback_data="mission_status"),InlineKeyboardButton(tx(lang,"back_menu"),callback_data="back")]])
    await safe_edit(q,text[:4096],reply_markup=kb)
# ── End: MISSION STATUS HANDLER ───────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: SPACE DICTIONARY HANDLER                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def space_dictionary_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    await safe_edit(q,f"{tx(lang,'dict_title')}\n\n{tx(lang,'dict_choose')}",reply_markup=dict_kb(lang))

async def dict_term_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    term_key=q.data.replace("dict_","")
    entry=SPACE_DICT.get(term_key)
    if not entry: return
    data=entry.get(lang, entry.get("en"))
    title,text,fact=data
    full_text=(f"{entry['emoji']} *{title}*\n\n{text}\n\n{tx(lang,'dict_funfact')} _{fact}_")
    await safe_edit(q,full_text,reply_markup=back_kb(lang,"space_dictionary",ctx))
# ── End: SPACE DICTIONARY ─────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: 30-DAY COURSE                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def course_menu_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    await safe_edit(q,f"{tx(lang,'course_title')}\n\n{tx(lang,'course_desc')}",reply_markup=course_kb(lang))

async def course_subscribe_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    cid=str(q.message.chat_id); cp=load_course()
    if cid in cp:
        day=cp[cid].get("day",1)
        await safe_edit(q,tx(lang,"course_already",day=day),
            reply_markup=back_kb(lang,"course_menu",ctx)); return
    cp[cid]={"day":1,"subscribed":date.today().isoformat(),"lang":lang}
    save_course(cp)
    # Send first lesson immediately
    lesson=COURSE_LESSONS[0]
    await safe_edit(q,f"{tx(lang,'course_subscribed')}\n\n{lesson['title']}\n\n{lesson['text']}",
        reply_markup=back_kb(lang,"course_menu",ctx))

async def course_browse_h(update, ctx):
    q=update.callback_query; await safe_answer(q); lang=get_lang(ctx)
    lines=[tx(lang,"course_all")+"\n"]
    for l in COURSE_LESSONS: lines.append(f"Day {l['day']:02d}. {l['title']}")
    await safe_edit(q,"\n".join(lines)[:4096],reply_markup=back_kb(lang,"course_menu",ctx))

async def job_course_lesson(context):
    cp=load_course()
    if not cp: return
    updated=False
    for cid,data in cp.items():
        day=data.get("day",1)
        if day>30: continue
        lesson=COURSE_LESSONS[day-1]
        lang=data.get("lang","en")
        text=f"{tx(lang,'course_day',day=day)}\n\n{lesson['title']}\n\n{lesson['text']}"
        try:
            await context.bot.send_message(int(cid),text[:4096],parse_mode="Markdown")
            cp[cid]["day"]=day+1; updated=True
        except Exception as e: logger.warning(f"Course {cid}: {e}")
    if updated: save_course(cp)

async def job_earth_fact(context):
    """Daily Earth-from-space fact with EPIC image."""
    subs=load_subscribers(); chat_ids=subs.get("earth_fact",[])
    if not chat_ids: return
    try:
        data=nasa_req("/EPIC/api/natural")
        if data:
            item=data[0]; date_str=item.get("date","")[:10].replace("-","/")
            img_name=item.get("image",""); url=f"https://epic.gsfc.nasa.gov/archive/natural/{date_str}/png/{img_name}.png"
            facts=["Earth looks like a blue marble from space — because oceans cover 71% of its surface.",
                   "From space, Earth is the only planet with clearly visible weather systems.",
                   "The Amazon rainforest is visible from space as a massive green swath.",
                   "City lights at night reveal human civilization's footprint from orbit.",
                   "The Sahara Desert is almost as large as the continental United States."]
            fact=facts[date.today().toordinal()%len(facts)]
            caption=f"🌍 *Earth Fact of the Day*\n\n_{fact}_\n\n📅 {date_str} UTC"
            for cid in chat_ids:
                try:
                    await context.bot.send_photo(int(cid),url,caption=caption,parse_mode="Markdown")
                except: await context.bot.send_message(int(cid),caption,parse_mode="Markdown")
    except Exception as e: logger.error(f"job_earth_fact: {e}")
# ── End: 30-DAY COURSE ────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: NEW_DIRECT_MAP ADDITIONS                                                ║
# Add this AFTER DIRECT_MAP = {...} in part2:                                   ║
#   DIRECT_MAP.update(NEW_DIRECT_MAP)                                           ║
#   CAT_MAP.update(NEW_CAT_MAP)                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
NEW_DIRECT_MAP = {
    # Live & alerts
    "satellite_tracker":   satellite_tracker_h,
    "earthquakes":         earthquakes_h,
    "spaceweather_digest": spaceweather_digest_h,
    "exoplanet_alert":     exoplanet_alert_h,
    # Interactive
    "achievements":        achievements_h,
    "daily_horoscope":     daily_horoscope_h,
    "daily_challenge_start": daily_challenge_start,
    # Profile
    "favorites_view":      favorites_view_h,
    "favorites_clear":     favorites_clear_h,
    "my_stats":            my_stats_h,
    "smart_alerts_menu":   smart_alerts_menu_h,
    # Useful
    "mission_status":      mission_status_h,
    "meteorite_map":       meteorite_map_h,
    "flight_calculator":   flight_calculator_h,
    # Education
    "space_dictionary":    space_dictionary_h,
    "course_menu":         course_menu_h,
    "course_subscribe":    course_subscribe_h,
    "course_browse":       course_browse_h,
}

NEW_CAT_MAP = {
    "cat_profile": (profile_kb, "title_profile"),
}
DIRECT_MAP.update(NEW_DIRECT_MAP)
CAT_MAP.update(NEW_CAT_MAP)
# ── End: NEW_DIRECT_MAP ADDITIONS ─────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: CALLBACK ROUTER ADDITIONS                                               ║
# These are extra patterns — add handling to callback_router() in part2:        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
async def route_new_callbacks(update, q, cb, ctx, lang):
    """Returns True if this function handled the callback, False otherwise."""
    if cb.startswith("sat_"):           await sat_detail_h(update,ctx); return True
    if cb.startswith("mission_"):       await mission_detail_h(update,ctx); return True
    if cb.startswith("flight_target_"): await flight_target_h(update,ctx); return True
    if cb.startswith("flight_calc_"):   await flight_calc_h(update,ctx); return True
    if cb.startswith("dict_"):          await dict_term_h(update,ctx); return True
    if cb.startswith("challenge_ans_"): await challenge_answer_h(update,ctx); return True
    if cb=="favorites_save":            await favorites_save_h(update,ctx); return True
    if cb=="smart_set_kp":              await smart_set_kp_start(update,ctx); return True
    if cb=="smart_set_ld":              await smart_set_ld_start(update,ctx); return True
    if cb=="smart_set_eq":              await smart_set_eq_start(update,ctx); return True
    if cb=="cat_profile":
        await safe_answer(q); ctx.user_data["last_cat"]="cat_profile"
        await safe_edit(q,tx(lang,"title_profile")+"\n\n"+tx(lang,"choose_sec"),reply_markup=profile_kb(lang)); return True
    return False
# ── End: CALLBACK ROUTER ADDITIONS ───────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════╗
# BLOCK: SETUP ADDITIONAL HANDLERS & JOBS                                        ║
# Call get_new_conv_handlers() and register_new_jobs() from setup_bot() in part2║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def get_new_conv_handlers():
    qa_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(qa_start,pattern="^space_qa$")],
        states={QA_QUESTION:[MessageHandler(filters.TEXT & ~filters.COMMAND,qa_answer)]},
        fallbacks=[CommandHandler("cancel",qa_cancel)], allow_reentry=True,
    )
    iss_vis_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(iss_schedule_start,pattern="^iss_schedule$")],
        states={ISS_CITY:[MessageHandler(filters.TEXT & ~filters.COMMAND,iss_city_received)]},
        fallbacks=[CommandHandler("cancel",iss_city_cancel)], allow_reentry=True,
    )
    rocket_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(rocket_game_start,pattern="^rocket_game$")],
        states={ROCKET_STEP:[CallbackQueryHandler(rocket_choice_h,pattern="^rocket_choice_")]},
        fallbacks=[CallbackQueryHandler(back_h,pattern="^back$")], allow_reentry=True,
    )
    smart_kp_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(smart_set_kp_start,pattern="^smart_set_kp$")],
        states={SMART_KP:[MessageHandler(filters.TEXT & ~filters.COMMAND,smart_kp_received)]},
        fallbacks=[CommandHandler("cancel",smart_cancel)], allow_reentry=True,
    )
    smart_ld_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(smart_set_ld_start,pattern="^smart_set_ld$")],
        states={SMART_LD:[MessageHandler(filters.TEXT & ~filters.COMMAND,smart_ld_received)]},
        fallbacks=[CommandHandler("cancel",smart_cancel)], allow_reentry=True,
    )
    smart_eq_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(smart_set_eq_start,pattern="^smart_set_eq$")],
        states={SMART_KP:[MessageHandler(filters.TEXT & ~filters.COMMAND,smart_eq_received)]},
        fallbacks=[CommandHandler("cancel",smart_cancel)], allow_reentry=True,
    )
    return [qa_conv, iss_vis_conv, rocket_conv, smart_kp_conv, smart_ld_conv, smart_eq_conv]

def register_new_jobs(jq):
    from datetime import time as dtime
    jq.run_daily(job_spaceweather_digest, time=dtime(8,30,0))
    jq.run_daily(job_earth_fact,          time=dtime(9,15,0))
    jq.run_daily(job_course_lesson,       time=dtime(10,0,0))
    jq.run_daily(job_earthquake_alert,    time=dtime(8,0,0))
    jq.run_repeating(job_exoplanet_alert,    interval=7*24*3600, first=600)
    jq.run_repeating(job_smart_alerts_check, interval=3600,      first=300)
# ── End: SETUP ADDITIONAL HANDLERS & JOBS ─────────────────────────────────────


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
    if await route_new_callbacks(update, q, cb, ctx, lang):
        return
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
    for h in get_new_conv_handlers():
        tg_app.add_handler(h)
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
        register_new_jobs(jq)
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







