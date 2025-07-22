import logging
import sys
import os
from datetime import datetime

class UTFFormatter(logging.Formatter):
    """Форматтер с поддержкой UTF-8 и безопасным выводом эмодзи"""
    
    def format(self, record):
        # Получаем базовое форматирование
        formatted = super().format(record)
        
        # Заменяем эмодзи на текстовые эквиваленты для совместимости
        emoji_replacements = {
            '🚀': '[START]',
            '📊': '[STATS]',
            '⚙️': '[CONFIG]',
            '🎯': '[TARGET]',
            '⏱️': '[TIME]',
            '📈': '[CHART]',
            '🔄': '[CYCLE]',
            '✅': '[OK]',
            '❌': '[ERROR]',
            '🤖': '[ML]',
            '🟢': '[BUY]',
            '🔴': '[SELL]',
            '💰': '[PRICE]',
            '🛡️': '[STOP]',
            '⚖️': '[RR]',
            '💸': '[RISK]',
            '💭': '[REASON]',
            '🚫': '[BLOCK]',
            '⚠️': '[WARN]',
            '🛑': '[STOP]',
            '🎉': '[SUCCESS]',
            '🏆': '[BEST]',
            '⏰': '[TIMEOUT]',
            '🔧': '[TECH]',
            '📄': '[REPORT]',
            '💾': '[SAVE]',
            '🔥': '[CRITICAL]'
        }
        
        for emoji, replacement in emoji_replacements.items():
            formatted = formatted.replace(emoji, replacement)
        
        return formatted

def setup_logging():
    """Настройка логирования с поддержкой UTF-8"""
    
    # Создаем директорию для логов если не существует
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Имя файла лога с датой
    log_filename = f"{log_dir}/trading_bot_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Настройка форматирования
    formatter = UTFFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Получаем root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Очищаем существующие обработчики
    logger.handlers.clear()
    
    # Файловый обработчик
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Настройка кодировки для консоли
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    logger.addHandler(console_handler)
    
    # Устанавливаем уровень для библиотек
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    return logger

# Инициализация логирования при импорте
setup_logging()