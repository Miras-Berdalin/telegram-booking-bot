import asyncio
import os
import calendar
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command

from apscheduler.schedulers.asyncio import AsyncIOScheduler


# ===================== НАСТРОЙКИ =====================

TOKEN = os.getenv("TOKEN")  # Railway Variables
ADMIN_GROUP_ID = -5155431438  # твоя админ группа
ADMIN_CHAT_LINK = "https://t.me/mbicko"

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()


# ===================== ХРАНИЛИЩЕ =====================

# подтвержденные брони
bookings = {}

# заявки до подтверждения
pending_bookings = {}

# состояния пользователей
user_states = {}

# закрытые админом дни
manually_closed_days = set()

russian_months = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}


# ===================== МЕНЮ =====================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Бронь", callback_data="bron")]
    ])


def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Календарь", callback_data="admin_calendar")]
    ])


# ===================== МЕСЯЦА =====================

def month_keyboard(admin_mode=False):
    now = datetime.now()
    year = now.year
    keyboard = []

    for month in range(1, 13):
        total_days = calendar.monthrange(year, month)[1]

        busy = len([
            1 for (y, m, _) in bookings
            if y == year and m == month
        ])

        free = total_days - busy

        text = f"{russian_months[month]} ({free}/{total_days})"

        prefix = "admin_month_" if admin_mode else "month_"

        keyboard.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"{prefix}{month}_{year}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ===================== КАЛЕНДАРЬ =====================

def generate_calendar(month, year, admin_mode=False):
    cal = calendar.monthcalendar(year, month)
    keyboard = []

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
                continue

            key = (year, month, day)

            if key in bookings:
                text = f"{day} ❌"
            elif key in manually_closed_days:
                text = f"{day} ❌"
            else:
                text = f"{day} ✅"

            prefix = "admin_day_" if admin_mode else "day_"

            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"{prefix}{day}_{month}_{year}"
                )
            )
        keyboard.append(row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ===================== START =====================

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Выберите пункт меню:", reply_markup=main_menu())


@dp.message(Command("admin"))
async def admin_handler(message: Message):
    if message.chat.id == ADMIN_GROUP_ID:
        await message.answer("⚙ Админ-меню:", reply_markup=admin_menu())

from aiogram.filters import Command


@dp.message(Command("test_reminder"))
async def test_reminder(message: Message):
    if message.chat.id != ADMIN_GROUP_ID:
        await message.answer("Команда доступна только админу.")
        return

    await check_reminders()
    await message.answer("🔔 Проверка напоминаний выполнена.")

# ===================== БРОНЬ =====================

@dp.callback_query(F.data == "bron")
async def bron_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Выберите месяц:", reply_markup=month_keyboard())


@dp.callback_query(F.data.startswith("month_"))
async def month_handler(callback: CallbackQuery):
    await callback.answer()
    _, month, year = callback.data.split("_")
    await callback.message.answer(
        f"Выберите день ({russian_months[int(month)]}):",
        reply_markup=generate_calendar(int(month), int(year))
    )


@dp.callback_query(F.data.startswith("day_"))
async def day_handler(callback: CallbackQuery):
    await callback.answer()

    _, day, month, year = callback.data.split("_")
    key = (int(year), int(month), int(day))

    if key in bookings or key in manually_closed_days:
        await callback.message.answer("Этот день недоступен ❌")
        return

    user_states[callback.from_user.id] = {
        "year": int(year),
        "month": int(month),
        "day": int(day),
        "step": "persons"
    }

    await callback.message.answer("Введите количество персон (только число):")


# ===================== ШАГИ ФОРМЫ =====================

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

        pending_bookings[user_id] = {
            "year": year,
            "month": month,
            "day": day,
            "persons": state["persons"],
            "event": state["event"],
            "phone": message.text
        }

        approve_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"approve_{user_id}"
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
            f"📅 {day}.{month}.{year}\n"
            f"👥 Персон: {state['persons']}\n"
            f"🎉 Тип: {state['event']}\n"
            f"📞 {message.text}",
            reply_markup=approve_keyboard
        )

        await message.answer("Заявка отправлена на рассмотрение ⏳")
        del user_states[user_id]


# ===================== APPROVE =====================

@dp.callback_query(F.data.startswith("approve_"))
async def approve_handler(callback: CallbackQuery):
    await callback.answer()

    user_id = int(callback.data.split("_")[1])
    data = pending_bookings.get(user_id)

    if not data:
        return

    key = (data["year"], data["month"], data["day"])
    bookings[key] = data

    await bot.send_message(
        user_id,
        "✅ Заявка утверждена!\n\n"
        "Для подробностей свяжитесь с администратором:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Перейти в чат", url=ADMIN_CHAT_LINK)]
        ])
    )

    await callback.message.edit_text(callback.message.text + "\n\n✅ Подтверждено")

    del pending_bookings[user_id]


# ===================== REJECT =====================

@dp.callback_query(F.data.startswith("reject_"))
async def reject_handler(callback: CallbackQuery):
    await callback.answer()

    user_id = int(callback.data.split("_")[1])

    await bot.send_message(user_id, "❌ Ваша заявка отклонена.")
    await callback.message.edit_text(callback.message.text + "\n\n❌ Отклонено")

    if user_id in pending_bookings:
        del pending_bookings[user_id]


# ===================== АДМИН КАЛЕНДАРЬ =====================

@dp.callback_query(F.data == "admin_calendar")
async def admin_calendar(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Выберите месяц:",
        reply_markup=month_keyboard(admin_mode=True)
    )


@dp.callback_query(F.data.startswith("admin_month_"))
async def admin_month(callback: CallbackQuery):
    await callback.answer()
    _, _, month, year = callback.data.split("_")

    await callback.message.answer(
        f"Календарь {russian_months[int(month)]}",
        reply_markup=generate_calendar(int(month), int(year), admin_mode=True)
    )


@dp.callback_query(F.data.startswith("admin_day_"))
async def admin_day(callback: CallbackQuery):
    await callback.answer()

    parts = callback.data.split("_")

    day = int(parts[2])
    month = int(parts[3])
    year = int(parts[4])

    key = (year, month, day)

    if key in bookings:
        data = bookings[key]
        text = (
            f"📅 {day}.{month}.{year}\n\n"
            f"👥 Персон: {data['persons']}\n"
            f"🎉 Тип: {data['event']}\n"
            f"📞 Телефон: {data['phone']}"
        )
    else:
        text = f"📅 {day}.{month}.{year}\n\n🟢 Свободен"

    await callback.message.answer(text)

    close_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔒 Закрыть день",
                callback_data=f"close_{day}_{month}_{year}"
            )
        ]
    ])

    await callback.message.answer(text, reply_markup=close_keyboard)


@dp.callback_query(F.data.startswith("close_"))
async def close_day(callback: CallbackQuery):
    await callback.answer()
    _, day, month, year = callback.data.split("_")
    manually_closed_days.add((int(year), int(month), int(day)))
    await callback.message.answer("День закрыт 🔒")


@dp.callback_query(F.data == "ignore")
async def ignore(callback: CallbackQuery):
    await callback.answer()


# ===================== НАПОМИНАНИЯ =====================

async def check_reminders():
    now = datetime.now()
    for (year, month, day), data in bookings.items():
        event_date = datetime(year, month, day)
        if event_date.date() == (now + timedelta(days=1)).date():
            await bot.send_message(
                data["user_id"],
                "🔔 Напоминание!\n\nЗавтра ваше мероприятие 🎉"
            )


# ===================== ЗАПУСК =====================

async def main():
    scheduler.add_job(check_reminders, "interval", hours=6)
    scheduler.start()

    print("Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())