import asyncio
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.enums import PollType
from aiogram.filters import Command

from config import (
    BOT_TOKEN,
    GROUP_CHAT_ID,
    ADMIN_CHAT_ID,
    POLL_TIME,
    ANALYTICS_TIME
)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

USERS_FILE = "storage.txt"
TOTAL_FILE = "storage_total.txt"
MODE_FILE = "storage_mode.txt"

poll_id = None
votes = {0: [], 1: []}

def read_users() -> set[str]:
    if not os.path.exists(USERS_FILE):
        return set()
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return {l.strip() for l in f if l.strip()}

def write_users(users: set[str]):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(users)))

def get_total() -> int | None:
    if not os.path.exists(TOTAL_FILE):
        return None
    value = open(TOTAL_FILE, "r", encoding="utf-8").read().strip()
    return int(value) if value.isdigit() and int(value) > 0 else None

def set_total(value: int):
    open(TOTAL_FILE, "w", encoding="utf-8").write(str(value))

def get_mode() -> str:
    if not os.path.exists(MODE_FILE):
        return "total"
    return open(MODE_FILE, "r", encoding="utf-8").read().strip()

def set_mode(mode: str):
    open(MODE_FILE, "w", encoding="utf-8").write(mode)


@dp.message(Command("set_total"))
async def cmd_set_total(msg: types.Message):
    if msg.chat.type != "private":
        return
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer("Используй: /set_total 15")
        return
    set_total(int(parts[1]))
    await msg.answer("✅ Количество сохранено")

@dp.message(Command("set_users"))
async def cmd_set_users(msg: types.Message):
    if msg.chat.type != "private":
        return
    users = {u.lstrip("@") for u in msg.text.split()[1:] if u.startswith("@")}
    write_users(users)
    await msg.answer(f"✅ Список сохранён ({len(users)})")

@dp.message(Command("get_users"))
async def cmd_get_users(msg: types.Message):
    if msg.chat.type != "private":
        return
    users = read_users()
    if not users:
        await msg.answer("📭 Список пуст")
        return
    await msg.answer("📋 Список:\n" + "\n".join(f"• @{u}" for u in sorted(users)))

@dp.message(Command("use_list"))
async def cmd_use_list(msg: types.Message):
    if msg.chat.type != "private":
        return
    if not read_users():
        await msg.answer("❌ Список пуст. Нельзя включить режим списка.")
        return
    set_mode("list")
    await msg.answer("📛 Используется подсчёт по списку")

@dp.message(Command("use_total"))
async def cmd_use_total(msg: types.Message):
    if msg.chat.type != "private":
        return
    set_mode("total")
    await msg.answer("🔢 Используется подсчёт по количеству")

@dp.message(Command("get_mode"))
async def cmd_get_mode(msg: types.Message):
    if msg.chat.type != "private":
        return
    await msg.answer(f"⚙️ Текущий режим: {get_mode()}")


async def send_poll():
    global poll_id, votes
    votes = {0: [], 1: []}
    poll = await bot.send_poll(
        GROUP_CHAT_ID,
        "Отметка:",
        ["На рабочем месте", "Опаздываю"],
        is_anonymous=False,
        type=PollType.REGULAR
    )
    poll_id = poll.poll.id

@dp.poll_answer()
async def poll_answer(answer: types.PollAnswer):
    if answer.poll_id != poll_id:
        return
    for v in votes.values():
        if answer.user in v:
            v.remove(answer.user)
    votes[answer.option_ids[0]].append(answer.user)


async def send_analytics():
    users = read_users()
    total = get_total()
    mode = get_mode()

    voted_users = {u for v in votes.values() for u in v}
    voted_usernames = {u.username for u in voted_users if u.username}

    text = "📊 Аналитика опроса\n\n"
    text += f"👥 Проголосовало: {len(voted_users)}\n\n"

    for i, title in enumerate(("На рабочем месте", "Опаздываю")):
        text += f"✅ {title}: {len(votes[i])}\n"
        for u in votes[i]:
            uname = f"@{u.username}" if u.username else "—"
            text += f"• {uname} — {u.full_name}\n"
        text += "\n"

    if mode == "list":
        not_voted = users - voted_usernames
        text += "📛 Не проголосовали (по списку):\n"
        if not not_voted:
            text += "🎉 Все отметились!"
        else:
            text += "\n".join(f"• @{u}" for u in sorted(not_voted))

    elif mode == "total" and total is not None:
        diff = total - len(voted_users)
        text += f"❗ Не проголосовало: {diff if diff > 0 else 0} чел."

    await bot.send_message(ADMIN_CHAT_ID, text)


def is_weekend():
    return datetime.now().weekday() >= 5

async def wait_until(t):
    while datetime.now().strftime("%H:%M") != t:
        await asyncio.sleep(20)

async def scheduler():
    while True:
        await wait_until(POLL_TIME)
        if not is_weekend():
            await send_poll()
        await asyncio.sleep(60)

        await wait_until(ANALYTICS_TIME)
        if not is_weekend():
            await send_analytics()
        await asyncio.sleep(60)


async def main():
    await bot.set_my_commands([])
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
