import asyncio
import os
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL", "http://localhost:8000/api")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://your-casino.com")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class DepositStates(StatesGroup):
    waiting_amount = State()
    waiting_proof = State()

class WithdrawStates(StatesGroup):
    waiting_amount = State()
    waiting_details = State()

async def api_call(method: str, endpoint: str, data: dict = None, token: str = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    async with aiohttp.ClientSession() as session:
        url = f"{API_URL}{endpoint}"
        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                return await resp.json(), resp.status
        elif method == "POST":
            async with session.post(url, json=data, headers=headers) as resp:
                return await resp.json(), resp.status

# =================== START ===================

@dp.message(CommandStart())
async def start(message: types.Message):
    telegram_id = str(message.from_user.id)
    username = message.from_user.username or message.from_user.first_name
    
    result, status = await api_call("POST", "/auth/telegram-register", {
        "telegram_id": telegram_id,
        "username": username
    })
    
    # Check required channels subscription
    channels_result, _ = await api_call("GET", "/admin/channels")
    if isinstance(channels_result, list) and channels_result:
        not_subscribed = []
        for channel in channels_result:
            try:
                member = await bot.get_chat_member(channel["channel_id"], message.from_user.id)
                if member.status in ["left", "kicked", "banned"]:
                    not_subscribed.append(channel)
            except Exception:
                pass
        
        if not_subscribed:
            buttons = []
            for ch in not_subscribed:
                buttons.append([InlineKeyboardButton(text=f"📢 {ch['name']}", url=ch['url'])])
            buttons.append([InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check_subscription")])
            
            await message.answer(
                "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
            return
    
    if result.get("already_exists"):
        kb = main_keyboard()
        await message.answer(
            f"👋 Xush kelibsiz!\n\n"
            f"🆔 Login: <code>{result['login']}</code>\n"
            f"ℹ️ Parolni unutgan bo'lsangiz /mylogin buyrug'ini bosing",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        kb = main_keyboard()
        await message.answer(
            f"🎰 <b>Casino'ga xush kelibsiz!</b>\n\n"
            f"✅ Akkauntingiz yaratildi!\n\n"
            f"🆔 Login: <code>{result['login']}</code>\n"
            f"🔑 Parol: <code>{result['password']}</code>\n\n"
            f"⚠️ Login va parolni saqlang! Web App'ga kirish uchun kerak bo'ladi.\n\n"
            f"🎮 O'yin boshlash uchun pastdagi tugmani bosing!",
            reply_markup=kb,
            parse_mode="HTML"
        )

@dp.callback_query(F.data == "check_subscription")
async def check_subscription(callback: types.CallbackQuery):
    await callback.answer("Tekshirilmoqda...")
    # Re-trigger start
    await start(callback.message)

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 O'yin boshlash", web_app=WebAppInfo(url=WEB_APP_URL))],
        [
            InlineKeyboardButton(text="💰 Balans", callback_data="balance"),
            InlineKeyboardButton(text="👤 Profil", callback_data="profile")
        ],
        [
            InlineKeyboardButton(text="➕ To'ldirish", callback_data="deposit"),
            InlineKeyboardButton(text="➖ Yechish", callback_data="withdraw")
        ],
        [InlineKeyboardButton(text="📊 Tarix", callback_data="history")]
    ])

# =================== BALANCE & PROFILE ===================

@dp.callback_query(F.data == "balance")
async def show_balance(callback: types.CallbackQuery):
    # Get user info via login - using telegram_id approach
    telegram_id = str(callback.from_user.id)
    # We need to get user token first - use a bot-level token
    # For bot commands, we use an internal endpoint
    result, status = await api_call("GET", f"/users/profile-by-telegram/{telegram_id}")
    
    if status == 200:
        await callback.message.answer(
            f"💰 <b>Balansingiz:</b> {result['balance']:,.0f} UZS",
            parse_mode="HTML"
        )
    await callback.answer()

@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    telegram_id = str(callback.from_user.id)
    result, status = await api_call("GET", f"/users/profile-by-telegram/{telegram_id}")
    
    if status == 200:
        u = result
        await callback.message.answer(
            f"👤 <b>Profil</b>\n\n"
            f"🆔 Login: <code>{u['login']}</code>\n"
            f"💰 Balans: {u['balance']:,.0f} UZS\n"
            f"✅ Jami yutuq: {u['total_wins']:,.0f} UZS\n"
            f"❌ Jami yutqazish: {u['total_losses']:,.0f} UZS\n"
            f"📅 Ro'yxat: {u['created_at'][:10]}",
            parse_mode="HTML"
        )
    await callback.answer()

@dp.message(Command("mylogin"))
async def my_login(message: types.Message):
    telegram_id = str(message.from_user.id)
    result, status = await api_call("GET", f"/users/profile-by-telegram/{telegram_id}")
    if status == 200:
        await message.answer(
            f"🔐 Login ma'lumotlaringiz:\n\n"
            f"🆔 Login: <code>{result['login']}</code>\n\n"
            f"⚠️ Parolni eslay olmayapsizmi? Yangi parol olish uchun admin bilan bog'laning.",
            parse_mode="HTML"
        )

# =================== DEPOSIT ===================

@dp.callback_query(F.data == "deposit")
async def deposit_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "💳 <b>Balans to'ldirish</b>\n\n"
        "Qancha to'ldirmoqchisiz? (UZS)\n"
        "Minimal: 10,000 UZS",
        parse_mode="HTML"
    )
    await state.set_state(DepositStates.waiting_amount)
    await callback.answer()

@dp.message(DepositStates.waiting_amount)
async def deposit_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "").replace(" ", ""))
        if amount < 10000:
            await message.answer("❌ Minimal summa 10,000 UZS")
            return
    except ValueError:
        await message.answer("❌ Noto'g'ri summa. Raqam kiriting.")
        return
    
    await state.update_data(amount=amount)
    
    # Get payment details from config
    await message.answer(
        f"💳 <b>To'lov ma'lumotlari:</b>\n\n"
        f"💰 Summa: {amount:,.0f} UZS\n\n"
        f"🏦 Karta: <code>8600 0000 0000 0000</code>\n"
        f"👤 Egasi: Casino Admin\n\n"
        f"✅ To'lovni amalga oshirgach, chek rasmini yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(DepositStates.waiting_proof)

@dp.message(DepositStates.waiting_proof)
async def deposit_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data["amount"]
    telegram_id = str(message.from_user.id)
    
    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_dep_{telegram_id}_{amount}"),
                    InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_dep_{telegram_id}_{amount}")
                ]
            ])
            
            text = (f"💰 <b>Depozit so'rovi</b>\n\n"
                    f"👤 @{message.from_user.username or 'user'}\n"
                    f"🆔 ID: {telegram_id}\n"
                    f"💵 Summa: {amount:,.0f} UZS\n"
                    f"⏰ Vaqt: {message.date.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if message.photo:
                await bot.send_photo(admin_id, message.photo[-1].file_id, caption=text, 
                                     reply_markup=kb, parse_mode="HTML")
            else:
                await bot.send_message(admin_id, text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
    
    await message.answer(
        "✅ So'rovingiz adminlarga yuborildi!\n"
        "Tasdiqlangach balansingizga tushadi."
    )
    await state.clear()

@dp.callback_query(F.data.startswith("approve_dep_"))
async def approve_deposit(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    parts = callback.data.split("_")
    telegram_id = parts[2]
    amount = float(parts[3])
    
    result, status = await api_call("POST", f"/admin/deposit-approve-telegram", {
        "telegram_id": telegram_id,
        "amount": amount
    })
    
    if status == 200:
        # Notify user
        try:
            await bot.send_message(
                int(telegram_id),
                f"✅ <b>Depozit tasdiqlandi!</b>\n\n"
                f"💰 +{amount:,.0f} UZS balansingizga tushdi.",
                parse_mode="HTML"
            )
        except Exception:
            pass
        
        await callback.message.edit_text(
            callback.message.text + f"\n\n✅ <b>TASDIQLANDI</b>",
            parse_mode="HTML"
        )
    await callback.answer("Tasdiqlandi!")

@dp.callback_query(F.data.startswith("reject_dep_"))
async def reject_deposit(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    parts = callback.data.split("_")
    telegram_id = parts[2]
    amount = float(parts[3])
    
    try:
        await bot.send_message(
            int(telegram_id),
            f"❌ Depozit so'rovingiz rad etildi.\n"
            f"Savol uchun admin bilan bog'laning.",
        )
    except Exception:
        pass
    
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>RAD ETILDI</b>",
        parse_mode="HTML"
    )
    await callback.answer("Rad etildi")

# =================== WITHDRAW ===================

@dp.callback_query(F.data == "withdraw")
async def withdraw_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "💸 <b>Pul yechish</b>\n\n"
        "Qancha yechmoqchisiz? (UZS)\n"
        "Minimal: 50,000 UZS",
        parse_mode="HTML"
    )
    await state.set_state(WithdrawStates.waiting_amount)
    await callback.answer()

@dp.message(WithdrawStates.waiting_amount)
async def withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "").replace(" ", ""))
        if amount < 50000:
            await message.answer("❌ Minimal summa 50,000 UZS")
            return
    except ValueError:
        await message.answer("❌ Noto'g'ri summa")
        return
    
    await state.update_data(amount=amount)
    await message.answer(
        "💳 Karta raqamingizni yuboring (pul o'tkaziladigan):"
    )
    await state.set_state(WithdrawStates.waiting_details)

@dp.message(WithdrawStates.waiting_details)
async def withdraw_details(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data["amount"]
    telegram_id = str(message.from_user.id)
    
    # Create withdrawal request via API
    result, status = await api_call("POST", f"/admin/withdraw-request-telegram", {
        "telegram_id": telegram_id,
        "amount": amount,
        "payment_details": message.text
    })
    
    if status == 200:
        # Notify admins
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"💸 <b>Yechish so'rovi</b>\n\n"
                    f"👤 @{message.from_user.username or 'user'}\n"
                    f"🆔 ID: {telegram_id}\n"
                    f"💵 Summa: {amount:,.0f} UZS\n"
                    f"💳 Karta: {message.text}",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        
        await message.answer(
            f"✅ Yechish so'rovi qabul qilindi!\n"
            f"💵 Summa: {amount:,.0f} UZS\n"
            f"Admin 24 soat ichida ko'rib chiqadi."
        )
    else:
        await message.answer(f"❌ Xato: {result.get('detail', 'Noma\\'lum xato')}")
    
    await state.clear()

# =================== ADMIN COMMANDS ===================

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 Kutayotgan to'lovlar", callback_data="admin_pending")],
        [InlineKeyboardButton(text="🌐 Admin Panel", url=f"{WEB_APP_URL}/admin")]
    ])
    await message.answer("👑 <b>Admin Panel</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    result, status = await api_call("GET", "/admin/stats")
    if status == 200:
        s = result
        await callback.message.answer(
            f"📊 <b>Statistika</b>\n\n"
            f"👥 Jami foydalanuvchilar: {s['total_users']}\n"
            f"💰 Jami balans: {s['total_balance']:,.0f} UZS\n"
            f"📈 Bugungi foyda: {s['daily_profit']:,.0f} UZS\n"
            f"🎮 Bugun aktiv: {s['active_users_today']}",
            parse_mode="HTML"
        )
    await callback.answer()

# =================== BROADCAST ===================

@dp.message(Command("broadcast"))
async def broadcast(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    text = message.text.replace("/broadcast ", "")
    if not text:
        await message.answer("Usage: /broadcast <xabar>")
        return
    
    # Get all users
    result, status = await api_call("GET", "/admin/users?limit=10000")
    if status == 200:
        count = 0
        for user in result:
            try:
                await bot.send_message(int(user["telegram_id"]), f"📢 {text}")
                count += 1
            except Exception:
                pass
        await message.answer(f"✅ {count} ta foydalanuvchiga yuborildi")

# =================== HISTORY ===================

@dp.callback_query(F.data == "history")
async def show_history(callback: types.CallbackQuery):
    telegram_id = str(callback.from_user.id)
    result, status = await api_call("GET", f"/users/history-by-telegram/{telegram_id}")
    
    if status == 200 and result:
        text = "📊 <b>So'nggi o'yinlar:</b>\n\n"
        for g in result[:10]:
            emoji = "✅" if g["result"] == "win" else "❌"
            text += f"{emoji} {g['game_type']} | Bet: {g['bet']:,.0f} | x{g['multiplier']} | {g['result']}\n"
        await callback.message.answer(text, parse_mode="HTML")
    else:
        await callback.message.answer("O'yinlar tarixi bo'sh")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
