import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.types import Message, PollAnswer
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError
import config

bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

current_poll_id = None
votes = {}
users_cache = {}


# =========================
# Работа с файлом
# =========================

def load_users():
    users = {}
    try:
        with open("storage.txt", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    username, alias, status = line.strip().split("|")
                    users[username.lower()] = {
                        "alias": alias,
                        "status": int(status)
                    }
    except FileNotFoundError:
        pass
    return users


def save_users(users):
    with open("storage.txt", "w", encoding="utf-8") as f:
        for username, data in users.items():
            f.write(f"{username}|{data['alias']}|{data['status']}\n")


# =========================
# Поиск пользователя
# =========================

def find_user(users, identifier: str):
    identifier = identifier.lower().replace("@", "")

    if identifier in users:
        return identifier

    for username, data in users.items():
        if data["alias"].lower() == identifier:
            return username

    return None


# =========================
# Создание опроса
# =========================

async def create_poll():
    global current_poll_id, votes

    votes = {}
    users_cache.clear()

    poll = await bot.send_poll(
        chat_id=config.GROUP_CHAT_ID,
        question="Отметь статус",
        options=["На рабочем месте", "Опаздываю"],
        is_anonymous=False
    )

    current_poll_id = poll.poll.id


@dp.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer):
    global votes, users_cache

    if poll_answer.poll_id != current_poll_id:
        return

    user = poll_answer.user
    votes[user.id] = poll_answer.option_ids[0]

    users_cache[user.id] = {
        "username": user.username,
        "full_name": user.full_name
    }


# =========================
# Аналитика (ТОЛЬКО В ЛС)
# =========================

async def send_analytics():
    users = load_users()

    required_users = [
        username for username, data in users.items()
        if data["status"] == 1
    ]

    voted_usernames = [
        (users_cache.get(uid, {}).get("username") or "").lower()
        for uid in votes.keys()
    ]

    voted_1 = []
    voted_2 = []

    for user_id, choice in votes.items():
        user_data = users_cache.get(user_id)
        if not user_data:
            continue

        username = (user_data["username"] or "").lower()
        full_name = user_data["full_name"]
        alias = users.get(username, {}).get("alias", "Без алиаса")

        formatted = f"{full_name} (@{user_data['username']}) — {alias}"

        if choice == 0:
            voted_1.append(formatted)
        else:
            voted_2.append(formatted)

    not_voted = [
        username for username in required_users
        if username not in voted_usernames
    ]

    text = (
        "📊 <b>Аналитика</b>\n\n"
        f"Должно проголосовать: {len(required_users)}\n"
        f"Проголосовало: {len(voted_usernames)}\n\n"
    )

    text += "✅ <b>На рабочем месте:</b>\n"
    text += "\n".join(voted_1) if voted_1 else "Нет"
    text += "\n\n"

    text += "⏳ <b>Опаздывают:</b>\n"
    text += "\n".join(voted_2) if voted_2 else "Нет"
    text += "\n\n"

    if not_voted:
        text += "📛 <b>Не проголосовали:</b>\n"
        for username in not_voted:
            alias = users[username]["alias"]
            text += f"{username} (@{username}) — {alias}\n"
    else:
        text += "✅ Все обязательные пользователи проголосовали"

    try:
        await bot.send_message(config.ADMIN_CHAT_ID, text)
    except TelegramForbiddenError:
        pass


# =========================
# Команды (ЛС)
# =========================

@dp.message(Command("add_user"))
async def add_user(message: Message):
    if message.chat.type != "private":
        return
    if message.chat.id != config.ADMIN_CHAT_ID:
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Использование:\n/add_user username alias")
        return

    username = args[1].replace("@", "").lower()
    alias = args[2]

    users = load_users()
    users[username] = {"alias": alias, "status": 1}
    save_users(users)

    await message.answer(f"Добавлен @{username} — {alias}")


@dp.message(Command("remove_user"))
async def remove_user(message: Message):
    if message.chat.type != "private":
        return
    if message.chat.id != config.ADMIN_CHAT_ID:
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование:\n/remove_user username или alias")
        return

    users = load_users()
    found = find_user(users, args[1])

    if not found:
        await message.answer("Пользователь не найден")
        return

    users.pop(found)
    save_users(users)

    await message.answer(f"Удалён @{found}")


@dp.message(Command("set_status"))
async def set_status(message: Message):
    if message.chat.type != "private":
        return
    if message.chat.id != config.ADMIN_CHAT_ID:
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Использование:\n/set_status username/alias 0|1")
        return

    users = load_users()
    found = find_user(users, args[1])

    if not found:
        await message.answer("Пользователь не найден")
        return

    status = int(args[2])
    users[found]["status"] = status
    save_users(users)

    await message.answer(f"Статус @{found} изменён на {status}")


@dp.message(Command("list"))
async def list_users(message: Message):
    if message.chat.type != "private":
        return
    if message.chat.id != config.ADMIN_CHAT_ID:
        return

    users = load_users()

    text = "📋 <b>Список пользователей:</b>\n\n"
    for username, data in users.items():
        text += f"@{username} — {data['alias']} (статус: {data['status']})\n"

    await message.answer(text)


# =========================
# Планировщик без дублей
# =========================

async def scheduler():
    last_poll_date = None
    last_analytics_date = None

    while True:
        now = datetime.now()
        weekday = now.weekday()
        today = now.date()

        if weekday not in (5, 6):

            if (
                now.strftime("%H:%M") == config.POLL_TIME
                and last_poll_date != today
            ):
                await create_poll()
                last_poll_date = today

            if (
                now.strftime("%H:%M") == config.ANALYTICS_TIME
                and last_analytics_date != today
            ):
                await send_analytics()
                last_analytics_date = today

        await asyncio.sleep(20)


# =========================

async def main():
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
