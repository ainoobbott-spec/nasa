#!/usr/bin/env python3
"""
Запустите этот скрипт рядом с main.py:
    python3 fix_main.py

Он исправит все 6 ошибок и создаст main_fixed.py
"""

import subprocess

with open("main.py", "r", encoding="utf-8") as f:
    code = f.read()

errors_fixed = []

# ═══════════════════════════════════════════════════════════════════════════════
# ПАТЧ 1: Пропущенная запятая в main_menu_kb (SyntaxError)
# ═══════════════════════════════════════════════════════════════════════════════
old = '''        [InlineKeyboardButton(L("btn_channels"),     callback_data="channels")]
        [InlineKeyboardButton(L("btn_lang"),         callback_data="choose_lang")],'''
new = '''        [InlineKeyboardButton(L("btn_channels"),     callback_data="channels")],
        [InlineKeyboardButton(L("btn_lang"),         callback_data="choose_lang")],'''
if old in code:
    code = code.replace(old, new, 1)
    errors_fixed.append("✅ ПАТЧ 1: Запятая в main_menu_kb")
else:
    errors_fixed.append("⚠️  ПАТЧ 1: main_menu_kb — не найден (возможно уже исправлен)")

# ═══════════════════════════════════════════════════════════════════════════════
# ПАТЧ 2: DIRECT_MAP.update вызван ДО определения NEW_DIRECT_MAP (NameError)
# Удалить преждевременные вызовы из блока CALLBACK ROUTER
# ═══════════════════════════════════════════════════════════════════════════════
old2 = "DIRECT_MAP.update(NEW_DIRECT_MAP)\nCAT_MAP.update(NEW_CAT_MAP)\n# ── End: CALLBACK ROUTER — IMG_MAP, DIRECT_MAP, CAT_MAP"
new2 = "# ── End: CALLBACK ROUTER — IMG_MAP, DIRECT_MAP, CAT_MAP"
if old2 in code:
    code = code.replace(old2, new2, 1)
    errors_fixed.append("✅ ПАТЧ 2: Убраны преждевременные DIRECT_MAP.update()")
else:
    errors_fixed.append("⚠️  ПАТЧ 2: DIRECT_MAP.update — не найден")

# ═══════════════════════════════════════════════════════════════════════════════
# ПАТЧ 3: Добавить DIRECT_MAP.update ПОСЛЕ определения NEW_DIRECT_MAP
# ═══════════════════════════════════════════════════════════════════════════════
marker = '''NEW_CAT_MAP = {
    "cat_profile": (profile_kb, "title_profile"),
}
# ── End: NEW_DIRECT_MAP ADDITIONS'''
replacement = '''NEW_CAT_MAP = {
    "cat_profile": (profile_kb, "title_profile"),
}
# Применяем расширения к роутеру
DIRECT_MAP.update(NEW_DIRECT_MAP)
CAT_MAP.update(NEW_CAT_MAP)
# ── End: NEW_DIRECT_MAP ADDITIONS'''
if marker in code:
    code = code.replace(marker, replacement, 1)
    errors_fixed.append("✅ ПАТЧ 3: DIRECT_MAP.update перемещён после определения")
else:
    errors_fixed.append("⚠️  ПАТЧ 3: NEW_CAT_MAP маркер — не найден")

# ═══════════════════════════════════════════════════════════════════════════════
# ПАТЧ 4: Отступ 3 пробела в setup_bot → 4 пробела (IndentationError строка ~4211)
# ═══════════════════════════════════════════════════════════════════════════════
old4 = '    tg_app.add_handler(CommandHandler("menu",menu_cmd))\n   tg_app.add_handler(planet_conv)'
new4 = '    tg_app.add_handler(CommandHandler("menu",menu_cmd))\n    tg_app.add_handler(planet_conv)'
if old4 in code:
    code = code.replace(old4, new4, 1)
    errors_fixed.append("✅ ПАТЧ 4: Отступ planet_conv (3→4 пробела)")
else:
    errors_fixed.append("⚠️  ПАТЧ 4: Отступ planet_conv — не найден")

# ═══════════════════════════════════════════════════════════════════════════════
# ПАТЧ 5: Отступ 5 пробелов у jq= в setup_bot → 4 пробела (IndentationError)
# ═══════════════════════════════════════════════════════════════════════════════
old5 = "    tg_app.add_handler(MessageHandler(filters.ALL, unknown))\n\n     jq=tg_app.job_queue"
new5 = "    tg_app.add_handler(MessageHandler(filters.ALL, unknown))\n\n    jq=tg_app.job_queue"
if old5 in code:
    code = code.replace(old5, new5, 1)
    errors_fixed.append("✅ ПАТЧ 5: Отступ jq= (5→4 пробела)")
else:
    errors_fixed.append("⚠️  ПАТЧ 5: Отступ jq= — не найден")

# ═══════════════════════════════════════════════════════════════════════════════
# ПАТЧ 6: nasa_image_search не определена в daily_challenge_start (NameError)
# ═══════════════════════════════════════════════════════════════════════════════
old6 = '''    await safe_edit(q,"⏳ Loading challenge image...")
    await del_msg(q)
    try:
        img=nasa_image_search(chall["img_q"],1)
        caption=f"🎯 *Daily Challenge*\\n\\n❓ *What is this object?*"
        await ctx.bot.send_photo(chat_id=q.message.chat_id,photo=img,caption=caption,
            parse_mode="Markdown",reply_markup=challenge_kb(lang,q_idx))
    except:
        await ctx.bot.send_message(chat_id=q.message.chat_id,
            text=f"🎯 *Daily Challenge*\\n\\n❓ *What is this object?*",
            parse_mode="Markdown",reply_markup=challenge_kb(lang,q_idx))'''
new6 = '''    caption = f"🎯 *Daily Challenge*\\n\\n❓ *What is this object?*"
    await del_msg(q)
    img_url = ""
    try:
        ri = requests.get("https://images-api.nasa.gov/search",
            params={"q": chall["img_q"], "media_type": "image", "page_size": 20}, timeout=12)
        items = [it for it in ri.json().get("collection", {}).get("items", []) if it.get("links")]
        if items:
            img_url = (random.choice(items[:15]).get("links", [{}])[0]).get("href", "")
    except:
        pass
    if img_url:
        try:
            await ctx.bot.send_photo(chat_id=q.message.chat_id, photo=img_url, caption=caption,
                parse_mode="Markdown", reply_markup=challenge_kb(lang, q_idx))
            return
        except:
            pass
    await ctx.bot.send_message(chat_id=q.message.chat_id, text=caption,
        parse_mode="Markdown", reply_markup=challenge_kb(lang, q_idx))'''
if old6 in code:
    code = code.replace(old6, new6, 1)
    errors_fixed.append("✅ ПАТЧ 6: nasa_image_search заменена на requests.get")
else:
    errors_fixed.append("⚠️  ПАТЧ 6: nasa_image_search — не найдена в коде")

# ═══════════════════════════════════════════════════════════════════════════════
# ПАТЧ 7: q._update_ref не существует в route_new_callbacks (AttributeError)
# ═══════════════════════════════════════════════════════════════════════════════
if "q._update_ref" in code:
    code = code.replace("q._update_ref", "update", )
    # Also fix the function signature
    code = code.replace(
        "async def route_new_callbacks(q, cb, ctx, lang):",
        "async def route_new_callbacks(update, cb, ctx, lang):\n    q = update.callback_query",
        1
    )
    errors_fixed.append("✅ ПАТЧ 7: q._update_ref → update в route_new_callbacks")
else:
    errors_fixed.append("⚠️  ПАТЧ 7: q._update_ref — не найден")

# ═══════════════════════════════════════════════════════════════════════════════
# ПАТЧ 8: Передаём update вместо q в route_new_callbacks из callback_router
# ═══════════════════════════════════════════════════════════════════════════════
old8 = "    if await route_new_callbacks(q, cb, ctx, lang):"
new8 = "    if await route_new_callbacks(update, cb, ctx, lang):"
if old8 in code:
    code = code.replace(old8, new8, 1)
    errors_fixed.append("✅ ПАТЧ 8: callback_router передаёт update в route_new_callbacks")
else:
    errors_fixed.append("⚠️  ПАТЧ 8: route_new_callbacks вызов — не найден")

# ═══════════════════════════════════════════════════════════════════════════════
# ПАТЧ 9: get_new_conv_handlers() должен вызываться внутри setup_bot()
# Если строки for h in get_new_conv_handlers() нет в setup_bot — добавляем
# ═══════════════════════════════════════════════════════════════════════════════
if "for h in get_new_conv_handlers()" not in code:
    old9 = "    await set_bot_descriptions(tg_app.bot)\n\ndef init_worker():"
    new9 = "    # Регистрируем новые ConversationHandler-ы (Part 3)\n    for h in get_new_conv_handlers():\n        tg_app.add_handler(h)\n    await set_bot_descriptions(tg_app.bot)\n\ndef init_worker():"
    if old9 in code:
        code = code.replace(old9, new9, 1)
        errors_fixed.append("✅ ПАТЧ 9: get_new_conv_handlers() добавлен в setup_bot()")
    else:
        errors_fixed.append("⚠️  ПАТЧ 9: маркер set_bot_descriptions — не найден")
else:
    errors_fixed.append("ℹ️  ПАТЧ 9: get_new_conv_handlers уже есть")

# ═══════════════════════════════════════════════════════════════════════════════
# Сохраняем исправленный файл
# ═══════════════════════════════════════════════════════════════════════════════
with open("main_fixed.py", "w", encoding="utf-8") as f:
    f.write(code)

print("\n" + "="*60)
print("       РЕЗУЛЬТАТЫ ПАТЧИНГА main.py")
print("="*60)
for msg in errors_fixed:
    print(msg)

print("\n" + "="*60)
print("ПРОВЕРКА СИНТАКСИСА...")
result = subprocess.run(
    ["python3", "-m", "py_compile", "main_fixed.py"],
    capture_output=True, text=True
)
if result.returncode == 0:
    print("✅ Синтаксических ошибок НЕТ!")
    print("\n✅ Файл main_fixed.py готов.")
    print("   Переименуйте его в main.py и загрузите на GitHub.")
else:
    print("❌ Остались ошибки:")
    print(result.stderr)
    print("\nПроверьте оставшиеся строки вручную.")
