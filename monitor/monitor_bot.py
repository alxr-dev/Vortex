import asyncio
import os
import csv
import sys
from typing import List, Union
from telethon import TelegramClient, events
from aiogram import Bot, Dispatcher
from aiogram.types import Message


def load_keywords(filepath: str) -> List[str]:
    """Загружает ключевые слова для мониторинга из файла."""
    keywords = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    keywords.append(line.lower())
    except FileNotFoundError:
        print(f"Файл ключевых слов не найден: {filepath}")
    return keywords


def load_chats_from_csv(filepath: str) -> List[Union[str, int]]:
    """Загружает список чатов и каналов из CSV файла для мониторинга."""
    chats = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                username = row['username']
                if username:
                    chats.append(username)
                else:
                    chat_id = row['id']
                    if chat_id:
                        chats.append(int(chat_id))
    except FileNotFoundError:
        print(f"CSV файл не найден: {filepath}")
    return chats


async def main():
    """Главная асинхронная функция монитор-бота."""
    # Загрузка конфигурации из переменных окружения
    api_id_str = os.getenv('TELETHON_API_ID')
    api_hash = os.getenv('TELETHON_API_HASH')
    session = os.getenv('TELETHON_SESSION', 'session')
    bot_token = os.getenv('BOT_TOKEN')
    user_chat_id_str = os.getenv('USER_CHAT_ID')

    # Проверка обязательных переменных окружения
    if not api_id_str:
        print("Ошибка: переменная окружения TELETHON_API_ID не установлена.")
        sys.exit(1)
    if not api_hash:
        print("Ошибка: переменная окружения TELETHON_API_HASH не установлена.")
        sys.exit(1)
    if not bot_token:
        print("Ошибка: переменная окружения BOT_TOKEN не установлена.")
        sys.exit(1)
    if not user_chat_id_str:
        print("Ошибка: переменная окружения USER_CHAT_ID не установлена.")
        sys.exit(1)

    try:
        TELETHON_API_ID = int(api_id_str)
        TELETHON_API_HASH = api_hash
        USER_CHAT_ID = int(user_chat_id_str)
    except ValueError:
        print("Ошибка: TELETHON_API_ID и USER_CHAT_ID должны быть целыми числами.")
        sys.exit(1)

    TELETHON_SESSION = session
    BOT_TOKEN = bot_token

    # Используем файлы для мониторинга
    keywords = load_keywords('data/monitor_keywords.txt')
    if not keywords:
        print("Не загружено ни одного ключевого слова для мониторинга. Завершение работы.")
        return

    chat_ids = load_chats_from_csv('data/monitor_chats.csv')
    channel_ids = load_chats_from_csv('data/monitor_channels.csv')
    # Объединяем чаты и каналы для мониторинга
    monitor_entities = chat_ids + channel_ids
    if not monitor_entities:
        print("Нет чатов или каналов для мониторинга. Завершение работы.")
        return

    # Инициализация клиента Telethon
    telethon_client = TelegramClient(TELETHON_SESSION, TELETHON_API_ID, TELETHON_API_HASH)

    # Инициализация бота aiogram и диспетчера
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Обработчик новых сообщений от Telethon
    @telethon_client.on(events.NewMessage(chats=monitor_entities))
    async def handle_new_message(event):
        message_text = event.message.text
        if not message_text:
            return
        # Проверяем наличие ключевых слов (без учёта регистра)
        for keyword in keywords:
            if keyword in message_text.lower():
                # Формируем уведомление
                sender = await event.get_sender()
                if sender:
                    if hasattr(sender, 'first_name'):
                        sender_info = f"{sender.first_name} {sender.last_name or ''}".strip()
                    elif hasattr(sender, 'title'):
                        sender_info = sender.title
                    else:
                        sender_info = str(sender)
                else:
                    sender_info = "Неизвестно"
                chat = await event.get_chat()
                if chat:
                    if hasattr(chat, 'title'):
                        chat_title = chat.title
                    elif hasattr(chat, 'first_name'):
                        chat_title = chat.first_name
                    else:
                        chat_title = str(chat)
                else:
                    chat_title = "Неизвестно"
                # Формируем ссылку на сообщение
                link = "Ссылка недоступна"
                if hasattr(chat, 'username') and chat.username:
                    link = f"https://t.me/{chat.username}/{event.message.id}"
                # Примечание: для приватных чатов генерация ссылки сложнее и может быть невозможна без дополнительного контекста.

                notification = (
                    f"🔍 Найдено ключевое слово: '{keyword}'\n"
                    f"💬 Чат: {chat_title}\n"
                    f"👤 Отправитель: {sender_info}\n"
                    f"📨 Сообщение: {message_text}\n"
                    f"🔗 Ссылка: {link}"
                )
                # Отправляем уведомление через бота aiogram
                try:
                    await bot.send_message(USER_CHAT_ID, notification)
                except Exception as e:
                    print(f"Не удалось отправить уведомление: {e}")
                break  # Уведомляем только один раз за сообщение (даже если несколько ключевых слов совпали)

    # Запускаем оба клиента
    async with telethon_client:
        # Запускаем бота aiogram в режиме polling
        polling_task = asyncio.create_task(dp.start_polling(bot))
        try:
            await telethon_client.run_until_disconnected()
        finally:
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                pass
            await bot.session.close()


# Точка входа
if __name__ == '__main__':
    asyncio.run(main())