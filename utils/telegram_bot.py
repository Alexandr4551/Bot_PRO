# utils/telegram_bot.py
"""
Улучшенный Telegram бот - только сигналы, без статистики
"""

import asyncio
import aiohttp
import logging
from datetime import datetime

# Попытка импорта конфигурации с обработкой ошибок
try:
    from config import ANTISPAM_CONFIG
except ImportError:
    # Fallback если config не найден
    ANTISPAM_CONFIG = {
        'MIN_RR_RATIO': 1.5,
        'TARGET_RR_RATIO': 2.5
    }

logger = logging.getLogger(__name__)

class TelegramBot:
    """Класс для отправки высококачественных торговых сигналов в Telegram"""
    
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}" if bot_token else None
        self.session = None
        self.enabled = bool(bot_token and chat_id)
        
        if self.enabled:
            logger.info("✅ Telegram бот активирован (режим: только высококачественные сигналы)")
        else:
            logger.warning("⚠️ Telegram бот не настроен (отправка в логи)")
    
    async def __aenter__(self):
        if self.enabled:
            self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()
    
    async def send_message(self, text, parse_mode="HTML"):
        """Отправка сообщения в Telegram"""
        if not self.enabled:
            logger.debug("Telegram не настроен, сообщение только в логи")
            return True
        
        if not self.session:
            logger.error("Telegram сессия не инициализирована")
            return False
        
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        try:
            async with self.session.post(url, json=data) as response:
                if response.status == 200:
                    logger.debug("✅ Сообщение отправлено в Telegram")
                    return True
                else:
                    result = await response.json()
                    logger.error(f"❌ Ошибка Telegram API: {result}")
                    return False
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в Telegram: {str(e)}")
            return False
    
    def format_high_quality_signal(self, signal):
        """Форматирование высококачественного сигнала для Telegram"""
        # Определяем эмодзи и цвет
        if signal['direction'] == 'buy':
            direction_emoji = "🟢"
            direction_text = "ПОКУПКА"
            color_emoji = "📈"
        else:
            direction_emoji = "🔴" 
            direction_text = "ПРОДАЖА"
            color_emoji = "📉"
        
        # Заголовок с акцентом на качество
        message = f"""
{direction_emoji} <b>ВЫСОКОКАЧЕСТВЕННЫЙ СИГНАЛ</b>

{color_emoji} <b>{signal['symbol']}</b> - {direction_text}

💰 <b>Цена входа:</b> ${signal['price']:.5f}
🎯 <b>Уверенность:</b> {signal['confidence']:.1%}
🏆 <b>Тип:</b> {self._get_signal_type_description(signal['signal_type'])}

"""
        
        # Анализ обеих систем
        if signal.get('ml_prediction'):
            ml = signal['ml_prediction']
            message += f"🤖 <b>ML анализ:</b> {ml['prediction_name']} ({ml['confidence']:.1%})\n"
        
        tech = signal['technical_signal']
        message += f"📊 <b>Технический анализ:</b> Сила {tech['strength']:.1%}, RSI {tech['rsi']:.1f}\n"
        message += f"📈 <b>Тренд:</b> {self._format_trend_strength(tech['trend'])}\n\n"
        
        # Торговые уровни с улучшенным форматированием
        if 'take_profit' in signal:
            message += f"🎯 <b>Цели прибыли:</b>\n"
            message += f"   🥉 TP1: <code>${signal['take_profit'][0]:.5f}</code> (R/R 1:{ANTISPAM_CONFIG['MIN_RR_RATIO']})\n"
            message += f"   🥈 TP2: <code>${signal['take_profit'][1]:.5f}</code>\n"
            message += f"   🥇 TP3: <code>${signal['take_profit'][2]:.5f}</code> (R/R 1:{ANTISPAM_CONFIG['TARGET_RR_RATIO']})\n\n"
            
            message += f"🛡️ <b>Стоп-лосс:</b> <code>${signal['stop_loss']:.5f}</code>\n"
            message += f"⚖️ <b>Risk/Reward:</b> 1:{signal['risk_reward']:.2f}\n"
            message += f"💸 <b>Риск позиции:</b> {signal['risk_percent']:.1f}%\n\n"
        
        # Обоснование сигнала
        if signal.get('reasoning'):
            message += f"💭 <b>Обоснование:</b>\n"
            for reason in signal['reasoning']:
                message += f"   • {reason}\n"
            message += "\n"
        
        # Время и призыв к действию
        message += f"⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}\n"
        message += f"🔥 <i>Высококачественный сигнал требует внимания!</i>"
        
        return message
    
    def _get_signal_type_description(self, signal_type):
        """Описание типа сигнала"""
        descriptions = {
            'high_quality_consensus': '🤝 ML + ТА согласие',
            'high_quality_technical': '📊 Мощный теханализ',
            'ml_technical_agree': '🤖📊 Полное согласие',
            'ml_dominant': '🤖 ML доминирует'
        }
        return descriptions.get(signal_type, signal_type)
    
    def _format_trend_strength(self, trend_strength):
        """Форматирование силы тренда"""
        if trend_strength >= 2.0:
            return "🔥 Очень сильный восходящий"
        elif trend_strength >= 1.0:
            return "📈 Сильный восходящий"
        elif trend_strength > 0:
            return "⬆️ Умеренный восходящий"
        elif trend_strength <= -2.0:
            return "❄️ Очень сильный нисходящий"
        elif trend_strength <= -1.0:
            return "📉 Сильный нисходящий"
        elif trend_strength < 0:
            return "⬇️ Умеренный нисходящий"
        else:
            return "➡️ Боковой"
    
    async def send_signal(self, signal):
        """Отправка высококачественного торгового сигнала"""
        try:
            message = self.format_high_quality_signal(signal)
            return await self.send_message(message)
        except Exception as e:
            logger.error(f"Ошибка форматирования сигнала: {str(e)}")
            return False
    
    async def send_startup_message(self):
        """Сообщение о запуске системы в режиме высокого качества"""
        message = """
🚀 <b>Система высококачественных сигналов запущена!</b>

🎯 <b>Режим работы:</b> Премиум качество
🤖 ML модель: Активна
📊 Технический анализ: Активен
🔒 <b>Фильтр:</b> Только согласованные сигналы 90%+

⚡ <b>Критерии отбора:</b>
   • ML + ТА должны совпадать
   • Уверенность ≥ 90%
   • Сильные трендовые условия
   • Качественные R/R уровни

🏆 <i>Ожидайте только лучшие торговые возможности!</i>
"""
        return await self.send_message(message)
    
    async def send_system_message(self, title, text, emoji="ℹ️"):
        """Отправка системных сообщений (ошибки, уведомления)"""
        message = f"""
{emoji} <b>{title}</b>

{text}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        return await self.send_message(message)
    
    async def test_connection(self):
        """Тест подключения к Telegram"""
        if not self.enabled:
            logger.info("Telegram не настроен для тестирования")
            return False
        
        test_message = """
🧪 <b>Тест системы высококачественных сигналов</b>

✅ Подключение к Telegram: OK
🔧 Система готова к работе

<i>Если вы видите это сообщение, бот работает корректно!</i>
"""
        result = await self.send_message(test_message)
        
        if result:
            logger.info("✅ Telegram бот работает корректно")
        else:
            logger.error("❌ Telegram бот не работает")
        
        return result

# Вспомогательная функция для создания бота из конфигурации
def create_telegram_bot():
    """Создание Telegram бота из переменных окружения или конфигурации"""
    import os
    
    # Попытка получить настройки из переменных окружения
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    # Если нет в переменных окружения, попробуем из config
    if not bot_token or not chat_id:
        try:
            from config.telegram_config import TELEGRAM_CONFIG
            bot_token = TELEGRAM_CONFIG.get('BOT_TOKEN')
            chat_id = TELEGRAM_CONFIG.get('CHAT_ID')
        except ImportError:
            logger.debug("Файл telegram_config.py не найден")
    
    return TelegramBot(bot_token, chat_id)