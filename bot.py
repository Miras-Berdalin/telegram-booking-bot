import asyncio
import calendar
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from apscheduler.schedulers.asyncio import AsyncIOScheduler


# ================== НАСТРОЙКИ ==================

TOKEN = "ТВОЙ_ТОКЕН"
ADMIN_GROUP_ID = -5155431438
ADMIN_CHAT_LINK = "https://t.me/mbicko"

bot = Bot(token=TOKEN)
dp = Dispatcher()

scheduler = AsyncIOScheduler()

# ================== ХРАНИЛИЩЕ ==================

# {(year, month, day): {...}}
bookings = {}
user_states = {}

russian_months = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

# ================== НАПОМИНАНИЯ ==================

async def check_reminders():
    print("Checking reminders...")

    now = datetime.now()

    for (year, month, day), data in bookings.items():
        event_date = datetime(year, month, day)

        # Напоминание за 1 день
        if event_date.date() == (now + timedelta(days=1)).date():
            await bot.send_message(
                data["user_id"],
                "🔔 Напоминание!\n\n"
                "Завтра ваше мероприятие 🎉"
            )

@dp.message(Command("test_reminder"))
async def test_reminder(message: Message):
    await check_reminders()
    await message.answer("🔄 Проверка напоминаний запущена")


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
        busy = len([1 for (y, m, _) in bookings if y == year and m == month])
        free = total_days - busy

        text = f"{russian_months[month]} ({free}/{total_days})"

        keyboard.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"month_{month}_{year}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ================== КАЛЕНДАРЬ ==================

def generate_calendar(month, year):
    cal = calendar.monthcalendar(year, month)
    keyboard = []

    busy_days = [d for (y, m, d) in bookings if y == year and m == month]

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                text = f"{day} ❌" if day in busy_days else f"{day} ✅"
                row.append(
                    InlineKeyboardButton(
                        text=text,
                        callback_data=f"day_{day}_{month}_{year}"
                    )
                )
        keyboard.append(row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ================== START ==================

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Выберите пункт меню:", reply_markup=main_menu())


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

    if (year, month, day) in bookings:
        await callback.message.answer("Этот день уже занят ❌")
        return

    user_states[callback.from_user.id] = {
        "year": year,
        "month": month,
        "day": day,
        "step": "persons"
    }

    await callback.message.answer("Введите количество персон:")


# ================== ШАГИ ФОРМЫ ==================

@dp.message()
async def handle_steps(message: Message):
    user_id = message.from_user.id

    if user_id not in user_states:
        return

    state = user_states[user_id]

    if state["step"] == "persons":
        if not message.text.isdigit():
            await message.answer("Введите число.")
            return

        state["persons"] = message.text
        state["step"] = "event"
        await message.answer("Введите тип мероприятия:")

    elif state["step"] == "event":
        state["event"] = message.text
        state["step"] = "phone"
        await message.answer("Введите номер телефона (+7...):")

    elif state["step"] == "phone":

        if not message.text.startswith("+7"):
            await message.answer("Телефон должен начинаться с +7")
            return

        year = state["year"]
        month = state["month"]
        day = state["day"]

        bookings[(year, month, day)] = {
            "user_id": user_id,
            "persons": state["persons"],
            "event": state["event"],
            "phone": message.text
        }

        await message.answer("✅ Заявка утверждена!")

        del user_states[user_id]


@dp.callback_query(F.data == "ignore")
async def ignore(callback: CallbackQuery):
    await callback.answer()


# ================== ЗАПУСК ==================

async def main():
    scheduler.add_job(check_reminders, "interval", hours=6)
    scheduler.start()

    print("Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())