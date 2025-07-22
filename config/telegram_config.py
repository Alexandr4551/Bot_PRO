# config/telegram_config.py
"""
Конфигурация Telegram бота
"""

# ===== Настройки Telegram =====
TELEGRAM_CONFIG = {
    # Получите токен у @BotFather в Telegram
    'BOT_TOKEN': '7594189137:AAF9-xQu6heeCyrG1tKV8K4PBvNRqKRLQzI',  # Замените на ваш токен
    
    # ID чата куда отправлять сигналы
    # Для получения ID: напишите боту @userinfobot
    'CHAT_ID': '903937778',  # Замените на ваш chat_id
    
    # Дополнительные настройки
    'SEND_STARTUP_MESSAGE': True,    # Отправлять сообщение при запуске
    'SEND_STATS': False,             # Отправлять статистику циклов  
    'EMOJI_ENABLED': True,           # Использовать эмодзи в сообщениях
}

# ===== Инструкция по настройке =====
"""
🔧 КАК НАСТРОИТЬ TELEGRAM БОТА:

1. Создайте бота:
   • Напишите @BotFather в Telegram
   • Отправьте команду /newbot
   • Придумайте имя и username для бота
   • Получите токен (выглядит как: 123456789:ABCDEF...)

2. Получите Chat ID:
   • Напишите вашему боту любое сообщение
   • Откройте: https://api.telegram.org/bot<TOKEN>/getUpdates
   • Найдите "chat":{"id": 123456789} - это ваш chat_id

3. Заполните конфигурацию:
   • Замените 'YOUR_BOT_TOKEN_HERE' на ваш токен
   • Замените 'YOUR_CHAT_ID_HERE' на ваш chat_id

4. Альтернативно - через переменные окружения:
   export TELEGRAM_BOT_TOKEN="ваш_токен"
   export TELEGRAM_CHAT_ID="ваш_chat_id"

Пример заполненной конфигурации:
TELEGRAM_CONFIG = {
    'BOT_TOKEN': '1234567890:ABCDEFghijklmnopqrstuvwxyz',
    'CHAT_ID': '987654321',
    'SEND_STARTUP_MESSAGE': True,
    'SEND_STATS': False,
    'EMOJI_ENABLED': True,
}
"""