import os
from typing import List


def load_keywords(filepath: str) -> List[str]:
    """Загружает ключевые слова из файла (по одному на строку). Игнорирует пустые строки и комментарии."""
    keywords = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                keywords.append(line.lower())
    return keywords


def get_api_credentials() -> tuple:
    """Получает учетные данные API из переменных окружения."""
    api_id = os.environ.get('TELETHON_API_ID')
    api_hash = os.environ.get('TELETHON_API_HASH')
    
    if not api_id or not api_hash:
        raise ValueError(
            "Не заданы переменные окружения. Установите TELETHON_API_ID и TELETHON_API_HASH"
        )
    
    return int(api_id), api_hash


def write_keywords(filepath: str, keywords: List[str]):
    """Записывает ключевые слова в файл (по одному на строку)."""
    with open(filepath, 'w', encoding='utf-8') as f:
        for keyword in keywords:
            f.write(f"{keyword}\n")