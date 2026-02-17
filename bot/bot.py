import asyncio, os, logging, aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8278818578:AAF2b8dHXkLSiw5JpslnsBMovukcP1WbqS4")
API_URL   = os.getenv("API_URL", "https://qwertyuz-production.up.railway.app/api")
WEB_APP   = os.getenv("WEB_APP_URL", "https://asxabshasba.vercel.app")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "6365371142").split(",") if x.strip()]
CARD      = os.getenv("PAYMENT_CARD", "5614 6835 8227 9246")
CARD_OWN  = os.getenv("PAYMENT_OWNER", "Casino Admin")

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

class DepState(StatesGroup):
    amount = State()
    proof  = State()

class WdState(StatesGroup):
    amount = State()
    card   = State()

# ===== API HELPER =====
async def call(method, path, data=None):
    try:
        async with aiohttp.ClientSession() as s:
            url = API_URL + path
            if method == "GET":
                async with s.get(url) as r: return await r.json(), r.status
            else:
                async with s.post(url, json=data) as r: return await r.json(), r.status
    except Exception as e:
        return {"detail": str(e)}, 500

# ===== KEYBOARDS =====
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 O'yinlar", web_app=WebAppInfo(url=WEB_APP))],
        [InlineKeyboardButton(text="💰 Balans", callback_data="bal"),
         InlineKeyboardButton(text="👤 Profil", callback_data="prof")],
        [InlineKeyboardButton(text="➕ To'ldirish", callback_data="dep"),
         InlineKeyboardButton(text="➖ Yechish", callback_data="wd")],
        [InlineKeyboardButton(text="📊 Tarix", callback_data="hist"),
         InlineKeyboardButton(text="🎟 Promokod", callback_data="promo")],
    ])

# ===== /start =====
@dp.message(CommandStart())
async def start(msg: types.Message):
    tg_id = str(msg.from_user.id)
    uname = msg.from_user.username or msg.from_user.first_name

    # Check required channels
    ch_res, _ = await call("GET", "/admin/channels")
    if isinstance(ch_res, list) and ch_res:
        unsub = []
        for ch in ch_res:
            try:
                m = await bot.get_chat_member(ch["channel_id"], msg.from_user.id)
                if m.status in ("left", "kicked", "banned"): unsub.append(ch)
            except: pass
        if unsub:
            btns = [[InlineKeyboardButton(text=f"📢 {c['name']}", url=c['url'])] for c in unsub]
            btns.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="chk_sub")])
            await msg.answer(
                "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
            )
            return

    res, status = await call("POST", "/auth/telegram-register", {"telegram_id": tg_id, "username": uname})

    if res.get("already_exists"):
        await msg.answer(
            f"👋 Xush kelibsiz!\n\n"
            f"🆔 Login: <code>{res['login']}</code>\n\n"
            f"Parolni unutgan bo'lsangiz /mylogin yuboring.",
            reply_markup=main_kb(), parse_mode="HTML"
        )
    else:
        await msg.answer(
            f"🎰 <b>Casino'ga xush kelibsiz!</b>\n\n"
            f"✅ Akkauntingiz yaratildi!\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🆔 Login: <code>{res['login']}</code>\n"
            f"🔑 Parol: <code>{res['password']}</code>\n"
            f"━━━━━━━━━━━━━━━━━\n\n"
            f"⚠️ <b>Login va parolni saqlang!</b>\n"
            f"Web App'ga kirish uchun kerak bo'ladi.\n\n"
            f"🎮 O'yin boshlash uchun pastdagi tugmani bosing!",
            reply_markup=main_kb(), parse_mode="HTML"
        )

@dp.callback_query(F.data == "chk_sub")
async def chk_sub(cb: types.CallbackQuery):
    await cb.answer("Tekshirilmoqda...")
    await start(cb.message)

# ===== BALANCE & PROFILE =====
@dp.callback_query(F.data == "bal")
async def show_bal(cb: types.CallbackQuery):
    res, s = await call("GET", f"/users/profile-by-telegram/{cb.from_user.id}")
    if s == 200:
        await cb.message.answer(
            f"💰 <b>Balansingiz:</b>\n\n"
            f"<b>{res['balance']:,.0f} UZS</b>",
            parse_mode="HTML"
        )
    else:
        await cb.message.answer("❌ Xato yuz berdi")
    await cb.answer()

@dp.callback_query(F.data == "prof")
async def show_prof(cb: types.CallbackQuery):
    res, s = await call("GET", f"/users/profile-by-telegram/{cb.from_user.id}")
    if s == 200:
        net = res['total_wins'] - res['total_losses']
        await cb.message.answer(
            f"👤 <b>Profil</b>\n\n"
            f"🆔 Login: <code>{res['login']}</code>\n"
            f"💰 Balans: <b>{res['balance']:,.0f} UZS</b>\n"
            f"✅ Yutuq: {res['total_wins']:,.0f} UZS\n"
            f"❌ Yutqazish: {res['total_losses']:,.0f} UZS\n"
            f"📊 Sof: {'+'if net>=0 else ''}{net:,.0f} UZS\n"
            f"📅 Ro'yxat: {res['created_at'][:10]}",
            parse_mode="HTML"
        )
    await cb.answer()

@dp.message(Command("mylogin"))
async def mylogin(msg: types.Message):
    res, s = await call("GET", f"/users/profile-by-telegram/{msg.from_user.id}")
    if s == 200:
        await msg.answer(
            f"🔐 <b>Login ma'lumotlaringiz</b>\n\n"
            f"🆔 Login: <code>{res['login']}</code>\n\n"
            f"Parolni o'zgartirish yoki tiklash uchun admin bilan bog'laning.",
            parse_mode="HTML"
        )

# ===== O'YIN TARIXI =====
@dp.callback_query(F.data == "hist")
async def show_hist(cb: types.CallbackQuery):
    res, s = await call("GET", f"/users/history-by-telegram/{cb.from_user.id}")
    if s == 200 and res:
        gnames = {"aviator": "✈️ Aviator", "mines": "💣 Mines", "apple_fortune": "🍎 Apple"}
        text = "📊 <b>So'nggi o'yinlar:</b>\n\n"
        for g in res[:8]:
            em = "✅" if g["result"] == "win" else "❌"
            text += f"{em} {gnames.get(g['game_type'], g['game_type'])} | {g['bet']:,.0f} → x{g['multiplier']:.2f}\n"
        await cb.message.answer(text, parse_mode="HTML")
    else:
        await cb.message.answer("📊 O'yinlar tarixi bo'sh")
    await cb.answer()

# ===== PROMOKOD =====
@dp.callback_query(F.data == "promo")
async def promo_info(cb: types.CallbackQuery):
    await cb.message.answer(
        "🎟 <b>Promokod ishlatish</b>\n\n"
        "Promokod yuborish uchun:\n"
        "<code>/promo KODINGIZ</code>",
        parse_mode="HTML"
    )
    await cb.answer()

@dp.message(Command("promo"))
async def use_promo(msg: types.Message):
    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer("Ishlatish: /promo KODINGIZ")
        return
    code = parts[1].upper()
    # Need user token - simplified: just show message
    await msg.answer(
        f"🎟 Promokod <code>{code}</code> ni ishlatish uchun Web App'ga kiring va Profil bo'limida kiriting.",
        parse_mode="HTML"
    )

# ===== DEPOZIT =====
@dp.callback_query(F.data == "dep")
async def dep_start(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(
        f"💳 <b>Balans to'ldirish</b>\n\n"
        f"Qancha to'ldirmoqchisiz?\n"
        f"<i>Minimal: 10,000 UZS</i>\n\n"
        f"Faqat raqam yuboring (masalan: 100000)",
        parse_mode="HTML"
    )
    await state.set_state(DepState.amount)
    await cb.answer()

@dp.message(DepState.amount)
async def dep_amount(msg: types.Message, state: FSMContext):
    try:
        am = float(msg.text.replace(",","").replace(" ","").replace("_",""))
        if am < 10000:
            await msg.answer("❌ Minimal 10,000 UZS yuboring"); return
    except:
        await msg.answer("❌ Faqat raqam yuboring"); return

    await state.update_data(amount=am)
    await msg.answer(
        f"💳 <b>To'lov ma'lumotlari:</b>\n\n"
        f"💰 Summa: <b>{am:,.0f} UZS</b>\n\n"
        f"🏦 Karta: <code>{CARD}</code>\n"
        f"👤 Egasi: <b>{CARD_OWN}</b>\n\n"
        f"✅ To'lovni amalga oshiring va <b>to'lov cheki (screenshot)</b> yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(DepState.proof)

@dp.message(DepState.proof)
async def dep_proof(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    am = data["amount"]
    tg_id = str(msg.from_user.id)

    for admin_id in ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"adp_{tg_id}_{am}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"adr_{tg_id}_{am}")
            ]])
            cap = (f"💰 <b>DEPOZIT SO'ROVI</b>\n\n"
                   f"👤 @{msg.from_user.username or 'user'}\n"
                   f"🆔 ID: <code>{tg_id}</code>\n"
                   f"💵 Summa: <b>{am:,.0f} UZS</b>\n"
                   f"⏰ {msg.date.strftime('%d.%m.%Y %H:%M:%S')}")
            if msg.photo:
                await bot.send_photo(admin_id, msg.photo[-1].file_id, caption=cap, reply_markup=kb, parse_mode="HTML")
            elif msg.document:
                await bot.send_document(admin_id, msg.document.file_id, caption=cap, reply_markup=kb, parse_mode="HTML")
            else:
                await bot.send_message(admin_id, cap + f"\n\n📝 Izoh: {msg.text}", reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Admin notify error: {e}")

    await msg.answer(
        f"✅ <b>So'rovingiz yuborildi!</b>\n\n"
        f"💵 Summa: {am:,.0f} UZS\n"
        f"Admin tekshirib, tez orada balansingizga tushiradi.",
        parse_mode="HTML"
    )
    await state.clear()

@dp.callback_query(F.data.startswith("adp_"))
async def admin_dep_approve(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("❌ Ruxsat yo'q!"); return
    _, tg_id, am = cb.data.split("_", 2)
    res, s = await call("POST", "/admin/deposit-approve-telegram", {"telegram_id": tg_id, "amount": float(am)})
    if s == 200:
        try:
            await bot.send_message(
                int(tg_id),
                f"✅ <b>Depozit tasdiqlandi!</b>\n\n"
                f"💰 +{float(am):,.0f} UZS balansingizga tushdi!\n"
                f"🎮 O'yin boshlashingiz mumkin!",
                reply_markup=main_kb(), parse_mode="HTML"
            )
        except: pass
        try:
            await cb.message.edit_caption(
                cb.message.caption + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML"
            )
        except:
            await cb.message.edit_text(cb.message.text + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML")
        await cb.answer("✅ Tasdiqlandi!")
    else:
        await cb.answer("❌ Xato yuz berdi!")

@dp.callback_query(F.data.startswith("adr_"))
async def admin_dep_reject(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("❌ Ruxsat yo'q!"); return
    _, tg_id, am = cb.data.split("_", 2)
    try:
        await bot.send_message(
            int(tg_id),
            f"❌ Depozit so'rovingiz rad etildi.\n"
            f"Savol bo'lsa admin bilan bog'laning.",
        )
    except: pass
    try:
        await cb.message.edit_caption(cb.message.caption + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")
    except:
        await cb.message.edit_text(cb.message.text + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")
    await cb.answer("❌ Rad etildi")

# ===== YECHISH =====
@dp.callback_query(F.data == "wd")
async def wd_start(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(
        "💸 <b>Pul yechish</b>\n\n"
        "Qancha yechmoqchisiz?\n"
        "<i>Minimal: 50,000 UZS</i>",
        parse_mode="HTML"
    )
    await state.set_state(WdState.amount)
    await cb.answer()

@dp.message(WdState.amount)
async def wd_amount(msg: types.Message, state: FSMContext):
    try:
        am = float(msg.text.replace(",","").replace(" ",""))
        if am < 50000:
            await msg.answer("❌ Minimal 50,000 UZS"); return
    except:
        await msg.answer("❌ Faqat raqam yuboring"); return
    await state.update_data(amount=am)
    await msg.answer("💳 Pulni qaysi kartaga o'tkazish kerak?\nKarta raqamini yuboring:")
    await state.set_state(WdState.card)

@dp.message(WdState.card)
async def wd_card(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    am = data["amount"]
    tg_id = str(msg.from_user.id)

    res, s = await call("POST", "/admin/withdraw-request-telegram", {
        "telegram_id": tg_id, "amount": am, "payment_details": msg.text
    })
    if s == 200:
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"💸 <b>YECHISH SO'ROVI</b>\n\n"
                    f"👤 @{msg.from_user.username or 'user'}\n"
                    f"🆔 ID: <code>{tg_id}</code>\n"
                    f"💵 Summa: <b>{am:,.0f} UZS</b>\n"
                    f"💳 Karta: <code>{msg.text}</code>",
                    parse_mode="HTML"
                )
            except: pass
        await msg.answer(
            f"✅ <b>So'rov qabul qilindi!</b>\n\n"
            f"💵 {am:,.0f} UZS\n"
            f"💳 {msg.text}\n\n"
            f"24 soat ichida admin ko'rib chiqadi.",
            parse_mode="HTML"
        )
    else:
        await msg.answer(f"❌ Xato: {res.get('detail', 'Noma\\'lum xato')}")
    await state.clear()

# ===== ADMIN =====
@dp.message(Command("admin"))
async def admin_panel(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats")],
        [InlineKeyboardButton(text="💰 Kutayotgan to'lovlar", callback_data="adm_pending")],
        [InlineKeyboardButton(text="🌐 Admin Panel", url=f"{WEB_APP}/admin")],
    ])
    await msg.answer("👑 <b>Admin Panel</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "adm_stats")
async def adm_stats(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    res, s = await call("GET", "/admin/stats")
    if s == 200:
        await cb.message.answer(
            f"📊 <b>Statistika</b>\n\n"
            f"👥 Foydalanuvchilar: {res['total_users']}\n"
            f"💰 Jami balans: {res['total_balance']:,.0f} UZS\n"
            f"📈 Bugungi foyda: {res['daily_profit']:,.0f} UZS\n"
            f"🎮 Bugun aktiv: {res['active_users_today']}",
            parse_mode="HTML"
        )
    await cb.answer()

@dp.callback_query(F.data == "adm_pending")
async def adm_pending(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    res, s = await call("GET", "/admin/transactions/pending")
    if s == 200:
        if not res:
            await cb.message.answer("✅ Kutayotgan so'rovlar yo'q")
        else:
            for t in res[:5]:
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅", callback_data=f"adp_{t['telegram_id']}_{t['amount']}"),
                    InlineKeyboardButton(text="❌", callback_data=f"adr_{t['telegram_id']}_{t['amount']}")
                ]])
                await cb.message.answer(
                    f"{'➕' if t['type']=='deposit' else '➖'} <b>{t['type'].upper()}</b>\n"
                    f"👤 {t['user_login']} ({t['telegram_id']})\n"
                    f"💵 {t['amount']:,.0f} UZS",
                    reply_markup=kb, parse_mode="HTML"
                )
    await cb.answer()

@dp.message(Command("broadcast"))
async def broadcast(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    text = msg.text.replace("/broadcast", "", 1).strip()
    if not text: await msg.answer("Ishlatish: /broadcast <xabar>"); return
    res, s = await call("GET", "/admin/users?limit=10000")
    if s == 200:
        cnt = 0
        for u in res:
            try:
                await bot.send_message(int(u["telegram_id"]), f"📢 {text}")
                cnt += 1
                await asyncio.sleep(0.05)
            except: pass
        await msg.answer(f"✅ {cnt} ta foydalanuvchiga yuborildi")

async def main():
    logging.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
