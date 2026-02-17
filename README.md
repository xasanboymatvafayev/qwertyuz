# 🎰 Casino Platform — Deploy Qo'llanma

## ✅ Sizning ma'lumotlaringiz TAYYOR qo'yilgan:
- API URL: https://qwertyuz-production.up.railway.app/api
- Web App: https://asxabshasba.vercel.app
- Bot Token: 8278818578:AAF2b8dHXkLSiw5JpslnsBMovukcP1WbqS4
- Admin ID: 6365371142
- DB: Railway PostgreSQL (to'g'ridan ulangan)
- Karta: 5614 6835 8227 9246

---

## 📁 Papkalar:
```
frontend/  → Vercel'ga deploy (Web App o'yinlar)
admin/     → Vercel'ga deploy (Admin panel)
backend/   → Railway'ga deploy (API)
bot/       → Railway'ga deploy (Telegram Bot)
```

---

## 🚀 DEPLOY TARTIBI

### 1️⃣ BACKEND → Railway

1. railway.app ga kiring
2. New Project → Deploy from GitHub repo
   YOKI: New Project → Empty Project → Add Service → "Deploy from local directory"
3. `backend/` papkasini deploy qiling
4. Environment variables qo'shing:
   ```
   DATABASE_URL=postgresql://postgres:BotQmCAxSRUraMVIGcosMrhtigKaqdFd@centerbeam.proxy.rlwy.net:22111/railway
   SECRET_KEY=95951223sabriya-95951223sabriya
   PORT=8000
   ```
5. Deploy URL: https://qwertyuz-production.up.railway.app ✅ (Sizda bor)

### 2️⃣ FRONTEND → Vercel (asxabshasba.vercel.app)

**MUHIM**: Faqat `frontend/` papkasini deploy qiling!

1. vercel.com → Add New Project
2. GitHub'ga `frontend/` papkasini push qiling YOKI:
   - Vercel Dashboard → Import → "Upload" tugmasini bosing
   - `frontend/` papkasini drag & drop qiling (PAPKANI, ZIP ni emas!)
3. Settings:
   - Framework: **Other**
   - Root Directory: **bo'sh qoldiring**
   - Build Command: **bo'sh**
   - Output Directory: **bo'sh**
4. Deploy ✅

### 3️⃣ ADMIN → Vercel (yangi loyiha)

`admin/` papkasini xuddi shunday deploy qiling.
URL: masalan `casino-admin-uz.vercel.app`

### 4️⃣ BOT → Railway

1. Railway'da yangi service → `bot/` papkasini deploy
2. Environment variables:
   ```
   BOT_TOKEN=8278818578:AAF2b8dHXkLSiw5JpslnsBMovukcP1WbqS4
   API_URL=https://qwertyuz-production.up.railway.app/api
   WEB_APP_URL=https://asxabshasba.vercel.app
   ADMIN_IDS=6365371142
   PAYMENT_CARD=5614 6835 8227 9246
   PAYMENT_OWNER=Casino Admin
   ```

---

## 👑 ADMIN QILISH

Backend deploy bo'lgach, DBga kiring va o'zingizni admin qiling:

Railway PostgreSQL → Query:
```sql
UPDATE users SET is_admin = true WHERE telegram_id = '6365371142';
```

Yoki Railway dashboard → PostgreSQL → Query tab

---

## 🧪 TEST

1. Botga /start yuboring
2. Login/parol oling
3. Web App'ni oching: https://asxabshasba.vercel.app
4. Login/parol bilan kiring
5. O'yin o'ynang!

---

## ❗ MUAMMOLAR

**404 Vercel da** → `vercel.json` bor ekanligini tekshiring (frontend/ papkasida bor)

**CORS xatosi** → Backend CORS'ni `*` qabul qiladi, muammo bo'lmasligi kerak

**DB ulanmaydi** → Railway PostgreSQL ishlayotganini tekshiring

**Bot javob bermaydi** → BOT_TOKEN to'g'riligini tekshiring, `/start` yuboring
