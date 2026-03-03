import asyncio
import calendar
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8715700469:AAEnKFSNxeVt9yg8Y0uQsDgehGWKzeXcu_U"
ADMIN_GROUP_ID = -5155431438  # без кавычек
ADMIN_CHAT_LINK = "https://t.me/mbicko"

bot = Bot(token=TOKEN)
dp = Dispatcher()

scheduler = AsyncIOScheduler()
scheduler.start()

async def check_reminders():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
        SELECT * FROM bookings
        WHERE approved = TRUE
        AND reminder_sent = FALSE
        AND event_date = CURRENT_DATE + INTERVAL '1 day'
        """)

        for row in rows:
            await bot.send_message(
                row["user_id"],
                f"🔔 Напоминание!\n\nЗавтра ваше мероприятие 🎉"
            )

            await conn.execute("""
            UPDATE bookings
            SET reminder_sent = TRUE
            WHERE id = $1
            """, row["id"])

# ================== ХРАНИЛИЩЕ ==================

@dp.message(Command("test_reminder"))
async def test_reminder(message: Message):
    await check_reminders()
    await message.answer("Проверка напоминаний запущена")
    
scheduler.add_job(check_reminders, "interval", hours=6)
# {(year, month, day): {user_id, username, persons, phone, event}}
bookings = {}

# временные состояния пользователей
user_states = {}

russian_months = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

# ================== МЕНЮ ==================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Бронь", callback_data="bron")]
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Календарь", callback_data="admin_calendar")]
    ])

# ================== МЕСЯЦА ==================

def month_keyboard():
    now = datetime.now()
    year = now.year
    keyboard = []

    for month in range(1, 13):
        total_days = calendar.monthrange(year, month)[1]
        busy = len([
            1 for (y, m, _) in bookings.keys()
            if y == year and m == month
        ])
        free = total_days - busy

        text = f"{russian_months[month]} ({free}/{total_days})"

        keyboard.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"month_{month}_{year}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def admin_month_keyboard():
    now = datetime.now()
    year = now.year
    keyboard = []

    for month in range(1, 13):
        total_days = calendar.monthrange(year, month)[1]
        busy = len([
            1 for (y, m, _) in bookings.keys()
            if y == year and m == month
        ])
        free = total_days - busy

        text = f"{russian_months[month]} ({free}/{total_days})"

        keyboard.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"admin_month_{month}_{year}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ================== КАЛЕНДАРЬ ==================

def generate_calendar(month, year, admin_mode=False):
    cal = calendar.monthcalendar(year, month)
    keyboard = []

    busy_days = [
        d for (y, m, d) in bookings.keys()
        if y == year and m == month
    ]

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                text = f"{day} ❌" if day in busy_days else f"{day} ✅"
                prefix = "admin_day_" if admin_mode else "day_"
                row.append(
                    InlineKeyboardButton(
                        text=text,
                        callback_data=f"{prefix}{day}_{month}_{year}"
                    )
                )
        keyboard.append(row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ================== START ==================

@dp.message(F.text == "/start")
async def start_handler(message: Message):
    await message.answer("Выберите пункт меню:", reply_markup=main_menu())

@dp.message(F.text == "/admin")
async def admin_handler(message: Message):
    if message.chat.id == ADMIN_GROUP_ID:
        await message.answer("⚙ Админ-меню:", reply_markup=admin_menu())

# ================== БРОНЬ ==================

@dp.callback_query(F.data == "bron")
async def bron_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Выберите месяц:", reply_markup=month_keyboard())

@dp.callback_query(F.data.startswith("month_"))
async def month_handler(callback: CallbackQuery):
    await callback.answer()
    _, month, year = callback.data.split("_")
    month, year = int(month), int(year)

    await callback.message.answer(
        f"Выберите день ({russian_months[month]}):",
        reply_markup=generate_calendar(month, year)
    )

@dp.callback_query(F.data.startswith("day_"))
async def day_handler(callback: CallbackQuery):
    await callback.answer()

    _, day, month, year = callback.data.split("_")
    day, month, year = int(day), int(month), int(year)
    user_id = callback.from_user.id

    if (year, month, day) in bookings:
        await callback.message.answer("Этот день уже занят ❌")
        return

    user_states[user_id] = {
        "year": year,
        "month": month,
        "day": day,
        "step": "persons"
    }

    await callback.message.answer(
        f"📅 Вы выбрали {day}.{month}.{year}\n\n"
        "Введите количество персон (только число):"
    )

# ================== ШАГИ ФОРМЫ ==================

@dp.message()
async def handle_user_steps(message: Message):
    user_id = message.from_user.id

    if user_id not in user_states:
        return

    state = user_states[user_id]

    if state["step"] == "persons":

        if not message.text.isdigit():
            await message.answer("Введите число (например: 5)")
            return

        state["persons"] = int(message.text)
        state["step"] = "event"

        await message.answer("Напишите тип мероприятия:")

    elif state["step"] == "event":

        state["event"] = message.text.strip()
        state["step"] = "phone"

        await message.answer("Введите номер телефона (начиная с +7):")

    elif state["step"] == "phone":

        phone = message.text.strip()

        if not phone.startswith("+7") or not phone[1:].isdigit():
            await message.answer("Телефон должен начинаться с +7 и содержать только цифры")
            return

        year = state["year"]
        month = state["month"]
        day = state["day"]
        persons = state["persons"]
        event = state["event"]

        approve_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"approve_{day}_{month}_{year}_{user_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject_{user_id}"
                )
            ]
        ])

        await bot.send_message(
            ADMIN_GROUP_ID,
            f"🔥 Новая бронь\n\n"
            f"👤 @{message.from_user.username}\n"
            f"🆔 ID: {user_id}\n"
            f"📅 Дата: {day}.{month}.{year}\n"
            f"👥 Персон: {persons}\n"
            f"🎉 Тип: {event}\n"
            f"📞 Телефон: {phone}",
            reply_markup=approve_keyboard
        )

        await message.answer("Заявка отправлена на рассмотрение ⏳")

        del user_states[user_id]

# ================== ПОДТВЕРЖДЕНИЕ ==================

@dp.callback_query(F.data.startswith("approve_"))
async def approve_handler(callback: CallbackQuery):
    await callback.answer()

    parts = callback.data.split("_")
    day = int(parts[1])
    month = int(parts[2])
    year = int(parts[3])
    user_id = int(parts[4])

    lines = callback.message.text.split("\n")

    persons = [l for l in lines if "Персон:" in l][0].split(": ")[1]
    event = [l for l in lines if "Тип:" in l][0].split(": ")[1]
    phone = [l for l in lines if "Телефон:" in l][0].split(": ")[1]

    bookings[(year, month, day)] = {
        "user_id": user_id,
        "username": lines[2].replace("👤 ", ""),
        "persons": persons,
        "event": event,
        "phone": phone
    }

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Перейти в чат", url=ADMIN_CHAT_LINK)]
    ])

    await bot.send_message(
        user_id,
        "✅ Заявка утверждена\n\n"
        "Для подробной информации можете перейти в чат с Администратором:",
        reply_markup=keyboard
    )

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Подтверждено"
    )

# ================== ОТКЛОНЕНИЕ ==================

@dp.callback_query(F.data.startswith("reject_"))
async def reject_handler(callback: CallbackQuery):
    await callback.answer()
    user_id = int(callback.data.split("_")[1])

    await bot.send_message(user_id, "❌ Ваша заявка отклонена.")
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ Отклонено"
    )

# ================== АДМИН КАЛЕНДАРЬ ==================

@dp.callback_query(F.data == "admin_calendar")
async def admin_calendar(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Выберите месяц:",
        reply_markup=admin_month_keyboard()
    )

@dp.callback_query(F.data.startswith("admin_month_"))
async def admin_month_handler(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_")
    month = int(parts[2])
    year = int(parts[3])

    await callback.message.answer(
        f"Календарь: {russian_months[month]}",
        reply_markup=generate_calendar(month, year, admin_mode=True)
    )

@dp.callback_query(F.data.startswith("admin_day_"))
async def admin_day_view(callback: CallbackQuery):
    await callback.answer()

    parts = callback.data.split("_")
    day = int(parts[2])
    month = int(parts[3])
    year = int(parts[4])

    key = (year, month, day)

    if key in bookings:
        b = bookings[key]
        text = (
            f"📅 {day}.{month}.{year}\n\n"
            f"🔒 Занят\n"
            f"👤 {b['username']}\n"
            f"👥 Персон: {b['persons']}\n"
            f"🎉 Тип: {b['event']}\n"
            f"📞 Телефон: {b['phone']}"
        )
    else:
        text = f"📅 {day}.{month}.{year}\n\n🟢 Свободен"

    await callback.message.answer(text)

@dp.callback_query(F.data == "ignore")
async def ignore(callback: CallbackQuery):
    await callback.answer()

async def main():
    print("Bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())