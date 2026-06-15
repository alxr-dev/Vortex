import argparse
import asyncio
import sys
import csv
from typing import Set
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.channels import SearchPostsRequest
from telethon.tl.types import InputPeerEmpty
from telethon.utils import get_peer_id
from telethon.errors import FloodWaitError

from .utils import load_keywords, get_api_credentials


# Инициализация CSV файла с заголовками
def init_csv_file(filepath: str) -> None:
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'title', 'username', 'participants_count', 'description'])
        writer.writeheader()


# Запись сущности (чат/канал) в CSV файл
def write_entity_to_csv(entity, filepath: str) -> None:
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'title', 'username', 'participants_count', 'description'])
        writer.writerow({
            'id': entity.id,
            'title': entity.title or '',
            'username': entity.username or '',
            'participants_count': getattr(entity, 'participants_count', 0) or 0,
            'description': getattr(entity, 'about', '') or ''
        })


async def search_new_channels_chats(client, keywords: list, mode: str, limit: int | None, output_chat: str, output_channel: str):
    """Поиск публичных каналов и чатов по ключевым словам через contacts.SearchRequest."""
    processed_chat_ids: Set[int] = set()
    processed_channel_ids: Set[int] = set()
    
    # Инициализация выходных файлов
    if mode in ('chats', 'both'):
        init_csv_file(output_chat)
    if mode in ('channels', 'both'):
        init_csv_file(output_channel)
    
    for keyword in keywords:
        try:
            result = await client(SearchRequest(
                q=keyword,
                limit=limit if limit else 100,
            ))
            
            for chat in result.chats:
                is_channel = getattr(chat, 'broadcast', False)
                is_group = getattr(chat, 'megagroup', False)
                
                if mode in ('channels', 'both') and is_channel:
                    if chat.id not in processed_channel_ids:
                        processed_channel_ids.add(chat.id)
                        write_entity_to_csv(chat, output_channel)
                
                elif mode in ('chats', 'both') and is_group:
                    if chat.id not in processed_chat_ids:
                        processed_chat_ids.add(chat.id)
                        write_entity_to_csv(chat, output_chat)
            
            await asyncio.sleep(0.5)
            
        except FloodWaitError as e:
            print(f"Flood wait error: sleeping for {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            continue
        except Exception as e:
            print(f"Error searching for '{keyword}': {e}")


async def search_public_posts(client, keywords: list, mode: str, limit: int | None, output_chat: str, output_channel: str):
    """Глобальный поиск публичных каналов и чатов по ключевым словам (требуется Telegram Premium)."""
    processed_chat_ids: Set[int] = set()
    processed_channel_ids: Set[int] = set()
    
    # Инициализация выходного файла каналов (для глобального поиска сохраняются только каналы)
    if mode in ('channels', 'both'):
        init_csv_file(output_channel)
    
    for keyword in keywords:
        try:
            offset_peer = InputPeerEmpty()
            offset_id = 0
            offset_rate = 0
            results_count = 0
            max_results = limit if limit else 100
            
            while True:
                result = await client(SearchPostsRequest(
                    query=keyword,
                    offset_rate=offset_rate,
                    offset_peer=offset_peer,
                    offset_id=offset_id,
                    limit=min(100, max_results - results_count),
                ))
                
                entities = {get_peer_id(en): en for en in result.chats + result.users}
                
                for message in result.messages:
                    if results_count >= max_results:
                        break
                    
                    if message.peer_id:
                        entity = entities.get(get_peer_id(message.peer_id))
                        if entity and hasattr(entity, 'title'):
                            is_channel = getattr(entity, 'broadcast', False)
                            is_group = getattr(entity, 'megagroup', False)
                            
                            if mode in ('channels', 'both') and is_channel:
                                if entity.id not in processed_channel_ids:
                                    processed_channel_ids.add(entity.id)
                                    results_count += 1
                                    write_entity_to_csv(entity, output_channel)
                            
                            elif mode in ('chats', 'both') and is_group:
                                if entity.id not in processed_chat_ids:
                                    processed_chat_ids.add(entity.id)
                                    results_count += 1
                                    write_entity_to_csv(entity, output_chat)
                
                if not result.messages or results_count >= max_results:
                    break
                
                offset_rate = getattr(result, 'next_rate', 0)
                if not offset_rate:
                    break
                
                last_msg = result.messages[-1]
                offset_peer = last_msg.peer_id
                offset_id = last_msg.id
                
                await asyncio.sleep(0.5)
                
        except FloodWaitError as e:
            print(f"Flood wait error: sleeping for {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            continue
        except Exception as e:
            print(f"Error searching for '{keyword}': {e}")


async def run_grabber(mode: str, keywords_file: str, limit: int | None, output_chat: str, output_channel: str, search_mode: str):
    """Основная функция-запускатор для grabber'а."""
    keywords = load_keywords(keywords_file)
    if not keywords:
        print("Не загружено ни одного ключевого слова. Завершение работы.")
        return
    
    try:
        api_id, api_hash = get_api_credentials()
    except ValueError as e:
        print(e)
        raise RuntimeError(str(e))
    
    async with TelegramClient('session', api_id, api_hash) as client:
        if search_mode == 'global':
            await search_public_posts(client, keywords, mode, limit, output_chat, output_channel)
        else:
            await search_new_channels_chats(client, keywords, mode, limit, output_chat, output_channel)


def main():
    """CLI интерфейс для grabber'а."""
    parser = argparse.ArgumentParser(
        description='Telegram chat/channel grabber - поиск публичных каналов и групп по ключевым словам.'
    )
    parser.add_argument(
        '--mode',
        choices=['chats', 'channels', 'both'],
        default='both',
        help='Режим работы: парсить чаты (chats), каналы (channels) или оба (both) (по умолчанию: both)'
    )
    parser.add_argument(
        '--keywords-file',
        default='data/keywords.txt',
        help='Файл с ключевыми словами (по одному на строку) (по умолчанию: data/keywords.txt)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Максимальное количество результатов на ключевое слово (по умолчанию: 100)'
    )
    parser.add_argument(
        '--output-chat',
        default='data/chats.csv',
        help='Выходной CSV файл для групп/чатов (по умолчанию: data/chats.csv)'
    )
    parser.add_argument(
        '--output-channel',
        default='data/channels.csv',
        help='Выходной CSV файл для каналов (по умолчанию: data/channels.csv)'
    )
    parser.add_argument(
        '--search-mode',
        choices=['contacts', 'global'],
        default='contacts',
        help='Режим поиска: contacts (по умолчанию) ищет в контактах, global использует SearchPostsRequest (требуется Telegram Premium)'
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_grabber(args.mode, args.keywords_file, args.limit, args.output_chat, args.output_channel, args.search_mode))
    except KeyboardInterrupt:
        print("Прервано пользователем")
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()