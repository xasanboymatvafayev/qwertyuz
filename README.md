# 🎰 Casino Platform — To'liq Qo'llanma

## 📁 Loyiha Tuzilmasi

```
casino/
├── backend/           # FastAPI backend
│   ├── main.py        # App entry point
│   ├── models.py      # Database models  
│   ├── database.py    # DB connection
│   ├── auth_utils.py  # JWT, parol
│   ├── requirements.txt
│   ├── Dockerfile
│   └── routers/
│       ├── auth.py    # Login, /start
│       ├── games.py   # Aviator, Mines, Apple
│       ├── balance.py # Depozit, yechish, promo
│       ├── admin.py   # Admin API
│       └── users.py   # Profil
├── bot/               # Telegram Bot (aiogram 3)
│   ├── bot.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/          # Web App (HTML+CSS+JS)
│   └── index.html     # Barcha 3 o'yin bilan
├── admin/             # Admin Panel
│   └── index.html
├── docker-compose.yml
├── nginx.conf
└── .env.example
```

---

## 🚀 O'rnatish

### 1. Telegram Bot Yaratish

```
@BotFather → /newbot → token olish
/setmenubutton → Web App tugmasini qo'shish
/setdomain → your-casino.com ni ruxsat berish
```

### 2. Server Tayyorlash (Ubuntu 22.04)

```bash
# Docker o'rnatish
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Loyihani clone qilish
git clone your-repo casino
cd casino

# .env fayl
cp .env.example .env
nano .env  # O'z sozlamalaringizni kiriting
```

### 3. SSL Sertifikat (Let's Encrypt)

```bash
sudo apt install certbot
certbot certonly --standalone -d your-casino.com
mkdir ssl
cp /etc/letsencrypt/live/your-casino.com/fullchain.pem ssl/
cp /etc/letsencrypt/live/your-casino.com/privkey.pem ssl/
```

### 4. API URL ni o'zgartirish

`frontend/index.html` va `admin/index.html` fayllarida:
```javascript
const API = 'https://your-casino.com/api'; // Shu qatorni o'zgartiring
```

### 5. Ishga tushirish

```bash
docker-compose up -d --build
```

### 6. Admin akkount yaratish

```bash
# PostgreSQL ga kiring
docker exec -it casino_db_1 psql -U casino_user casino_db

# Admin qiling
UPDATE users SET is_admin = true WHERE telegram_id = 'YOUR_TELEGRAM_ID';
```

---

## 🎮 O'yinlar

### ✈️ Aviator
- RNG orqali crash nuqtasi oldindan belgilanadi
- 5% ehtimol — darhol 1.0x da crash
- Qolgan hollarda: `0.99 / (1 - random)` formulasi
- Auto cashout va manual cashout
- House edge: ~3%

### 💣 Mines (5×5)
- 25 katakli maydon, 1-24 mina
- Har ochilgan xavfsiz katak koeffitsientni oshiradi
- Formula: `∏(safe_remaining/total_remaining) × 0.97`
- Mina ursa — to'liq maydon ko'rinadi
- House edge: ~3%

### 🍎 Apple of Fortune
- 5 qavat (sozlanadi 3-8 gacha)
- Har qavatda 3 olma: 1 ta yomon, 2 ta yaxshi
- Koeffitsient bosqichma-bosqich: 1.5x → 2.1x → 2.94x...
- Istalgan qavatda cashout
- House edge: ~4%

---

## 💰 Balans Tizimi

### Depozit Jarayoni:
1. Foydalanuvchi bot yoki web app da summa kiritadi
2. To'lov ma'lumotlari ko'rsatiladi
3. Foydalanuvchi to'lov chekini yuboradi
4. **Admin tasdiqlaydi → balans tushadi**

### Yechish Jarayoni:
1. Foydalanuvchi summa + karta kiritadi
2. Balansdan ayiriladi (reserve)
3. **Admin ko'rib chiqadi → pul o'tkazadi**
4. Agar rad etsa → balans qaytariladi

---

## 🔐 Xavfsizlik

- Barcha game logikasi server tomonda (RNG client da emas)
- JWT token 7 kun amal qiladi
- bcrypt parol hashlash
- Admin panelga IP restriction qo'shish mumkin (nginx.conf)
- SQL injection himoya: SQLAlchemy ORM
- Rate limiting: nginx yoki FastAPI middleware orqali qo'shish mumkin

---

## 📊 Admin Panel

URL: `https://your-casino.com/admin`

Imkoniyatlar:
- 📊 Real-time statistika (foyda, balanslar, aktiv o'yinchilar)
- ✅❌ Depozit/yechish so'rovlarini tasdiqlash/rad etish
- 👥 Foydalanuvchilarni bloklash, muzlatish, o'yin taqiqlash
- 🎟 Promokod yaratish (foiz/belgilangan, muddatli/cheksiz)
- 📢 Majburiy kanal qo'shish
- 📣 Banner/popup/bot reklama boshqarish

---

## 🤖 Bot Buyruqlari

| Buyruq | Tavsif |
|--------|--------|
| `/start` | Ro'yxat + login/parol |
| `/mylogin` | Login ma'lumotlari |
| `/admin` | Admin panel (adminlar uchun) |
| `/broadcast <xabar>` | Barcha userlarga xabar (admin) |

---

## ⚙️ Muhim O'zgartirishlar

1. **`.env` faylini to'ldirish** — BOT_TOKEN, SECRET_KEY, ADMIN_IDS
2. **`frontend/index.html`** — `API` const ni o'zgartirish
3. **`admin/index.html`** — `API` const ni o'zgartirish
4. **`nginx.conf`** — domain nomini o'zgartirish
5. **`bot.py`** — To'lov karta ma'lumotlarini o'zgartirish

---

## 📞 Qo'shimcha Xizmatlar

Platformani yanada kuchaytirish uchun qo'shish mumkin:
- **WebSocket** — Aviator uchun real-time multiplayer (barcha o'yinchilar bir vaqtda ko'radi)
- **Redis** — Session cache, rate limiting
- **Celery** — Async task queue (bot broadcast)
- **Provably Fair** — Blockchain orqali tekshirish imkoni
