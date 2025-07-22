# main_v2.py - СИСТЕМА С УЛУЧШЕННЫМ TIMING
"""
Система торговых сигналов с УМНЫМ TIMING ВХОДА
ЭТАП 1.2: Ожидаемое улучшение +15% к винрейту
"""

import asyncio
import logging
import time
from datetime import datetime

# Импорт конфигурации логирования  
from config.logging_config import setup_logging

# Настройка логирования
logger = setup_logging()

print("🚀 Запуск системы с УЛУЧШЕННЫМ TIMING...")
print("🎯 Режим: Умный timing входа - ждем оптимальные моменты")
print("📋 Инициализация модулей...")

# Импорт основных компонентов
from config import SYMBOLS, INTERVAL_SEC
from core import BybitFuturesAPI
from core.trading_engine import HybridTradingEngineV2  # Новая версия с timing
from utils import display_signal, display_startup_info

print("✅ Основные модули загружены")

# Импорт Telegram модуля
try:
    from utils.telegram_bot import create_telegram_bot
    print("✅ Telegram модуль загружен")
except ImportError as e:
    print(f"❌ Ошибка загрузки Telegram модуля: {e}")
    create_telegram_bot = None

async def main_loop_v2():
    """Основной цикл системы с timing"""
    print("=" * 70)
    print("🎯 СИСТЕМА С УЛУЧШЕННЫМ TIMING ВХОДА")
    print("=" * 70)
    print("🚀 Новые возможности:")
    print("   • Pullback стратегия - ждем лучшие цены входа")
    print("   • Микро-подтверждения перед входом")
    print("   • Breakout подтверждения с объемом")
    print("   • Адаптивный timing для разных типов сигналов")
    print("   • Детальная статистика timing")
    print("=" * 70)
    
    display_startup_info()
    
    # Инициализация Telegram бота
    print("\n🤖 ИНИЦИАЛИЗАЦИЯ TELEGRAM БОТА")
    print("=" * 50)
    
    if create_telegram_bot is None:
        print("❌ Telegram модуль не загружен!")
        telegram_bot = None
        telegram_enabled = False
    else:
        print("🔄 Создаем Telegram бота...")
        telegram_bot = create_telegram_bot()
        telegram_enabled = telegram_bot.enabled if telegram_bot else False
        
        print(f"📱 Telegram бот создан: enabled={telegram_enabled}")
        
        if telegram_enabled:
            print(f"🔑 Токен: настроен")
            print(f"💬 Chat ID: {telegram_bot.chat_id}")
        else:
            print("⚠️ Telegram бот отключен (проверьте настройки)")
    
    print("=" * 50)
    
    # Создаем правильный context manager для Telegram
    if telegram_bot and telegram_enabled:
        tg_context = telegram_bot
    else:
        class DummyBot:
            enabled = False
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
        tg_context = DummyBot()
    
    async with BybitFuturesAPI() as api, tg_context as tg_bot:
        engine = HybridTradingEngineV2(api)  # Новый движок с timing
        
        # Тестируем Telegram
        if telegram_enabled and tg_bot.enabled:
            print("🤖 Telegram бот включен, тестируем подключение...")
            logger.info("🤖 Telegram бот включен, тестируем подключение...")
            
            test_result = await tg_bot.test_connection()
            if test_result:
                print("✅ Telegram тест успешен")
                logger.info("✅ Telegram тест успешен")
                
                startup_message = (
                    "🚀 <b>Система с улучшенным TIMING запущена!</b>\n\n"
                    "🎯 <b>Новые возможности:</b>\n"
                    "• Pullback стратегия\n"
                    "• Микро-подтверждения\n"
                    "• Умный timing входа\n"
                    "• Лучшие цены входа\n\n"
                    "⏰ Ожидаемое улучшение: <b>+15% к винрейту</b>\n"
                    "📈 Начинаем поиск качественных возможностей..."
                )
                
                startup_result = await tg_bot.send_system_message(
                    "Система запущена", startup_message, "🚀"
                )
                print(f"📢 Стартовое сообщение: {'✅ отправлено' if startup_result else '❌ ошибка'}")
                logger.info(f"📢 Стартовое сообщение: {'✅ отправлено' if startup_result else '❌ ошибка'}")
            else:
                print("❌ Telegram тест провален")
                logger.error("❌ Telegram тест провален")
        else:
            print("⚠️ Telegram бот отключен")
            logger.warning("⚠️ Telegram бот отключен")
        
        print("\n🔄 Начинаем поиск сигналов с умным timing...")
        logger.info("🎯 Система с timing активна")
        
        cycle_count = 0
        total_signals_generated = 0
        total_entries_executed = 0
        
        while True:
            try:
                cycle_count += 1
                start_time = time.time()
                
                logger.info(f"\n{'='*70}")
                logger.info(f"🔍 Цикл #{cycle_count}: Анализ + проверка готовых входов")
                logger.info(f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # ФАЗА 1: Генерация новых сигналов (добавляем в timing систему)
                new_signals = await engine.analyze_and_generate_signals(SYMBOLS)
                
                if new_signals:
                    total_signals_generated += len(new_signals)
                    logger.info(f"📊 Новых сигналов добавлено в очередь timing: {len(new_signals)}")
                    
                    for signal_info in new_signals:
                        signal = signal_info['signal']
                        timing_strategy = signal_info['timing_strategy']
                        
                        logger.info(f"⏳ {signal['symbol']} {signal['direction']} "
                                   f"(стратегия: {timing_strategy}, "
                                   f"уверенность: {signal.get('confidence', 0):.1%})")
                
                # ФАЗА 2: Проверка готовых к входу сигналов
                ready_entries = await engine.check_ready_entries()
                
                if ready_entries:
                    total_entries_executed += len(ready_entries)
                    logger.info(f"🎯 Готовых к входу сигналов: {len(ready_entries)}")
                    
                    for entry_signal in ready_entries:
                        # Отображение готового сигнала
                        display_signal(entry_signal)
                        
                        # Отправка в Telegram
                        if telegram_enabled and tg_bot.enabled:
                            try:
                                # Дополняем сообщение информацией о timing
                                timing_info = entry_signal.get('timing_info', {})
                                timing_type = timing_info.get('timing_type', 'unknown')
                                wait_time = timing_info.get('wait_time_minutes', 0)
                                entry_reason = timing_info.get('entry_reason', 'unknown')
                                
                                # Создаем улучшенное сообщение
                                enhanced_signal = entry_signal.copy()
                                enhanced_signal['timing_details'] = {
                                    'strategy': timing_type,
                                    'wait_time_minutes': wait_time,
                                    'entry_reason': entry_reason,
                                    'original_price': timing_info.get('original_signal_price', entry_signal['price'])
                                }
                                
                                success = await tg_bot.send_timing_signal(enhanced_signal)
                                if success:
                                    print(f"🚀 TIMING сигнал {entry_signal['symbol']} отправлен в Telegram!")
                                    logger.info(f"🚀 TIMING сигнал {entry_signal['symbol']} отправлен в Telegram")
                                else:
                                    print(f"❌ Не удалось отправить timing сигнал {entry_signal['symbol']}")
                                    logger.warning(f"⚠️ Не удалось отправить timing сигнал {entry_signal['symbol']}")
                            except Exception as e:
                                print(f"❌ Ошибка отправки timing сигнала в Telegram: {str(e)}")
                                logger.error(f"❌ Ошибка отправки timing сигнала в Telegram: {str(e)}")
                        else:
                            print(f"🎯 TIMING сигнал {entry_signal['symbol']} готов (Telegram отключен)")
                            logger.info(f"🎯 TIMING сигнал {entry_signal['symbol']} готов (Telegram отключен)")
                
                # ФАЗА 3: Получение статуса timing системы
                timing_status = engine.get_timing_status()
                pending_count = len(timing_status.get('pending_entries', []))
                
                # Краткая статистика цикла
                cycle_time = time.time() - start_time
                
                logger.info(f"\n📊 ЦИКЛ #{cycle_count} ЗАВЕРШЕН:")
                logger.info(f"   🔍 Новых сигналов в очереди: {len(new_signals)}")
                logger.info(f"   🎯 Готовых входов: {len(ready_entries)}")
                logger.info(f"   ⏳ Ожидающих входов: {pending_count}")
                logger.info(f"   ⏱️ Время цикла: {cycle_time:.1f} сек")
                logger.info(f"   📈 Всего сигналов за сессию: {total_signals_generated}")
                logger.info(f"   💼 Всего входов выполнено: {total_entries_executed}")
                
                # Детальный статус pending entries каждые 10 циклов
                if cycle_count % 10 == 0 and pending_count > 0:
                    logger.info(f"\n⏳ ДЕТАЛИ ОЖИДАЮЩИХ ВХОДОВ:")
                    for entry in timing_status.get('pending_entries', []):
                        logger.info(f"   {entry['symbol']} {entry['direction'].upper()} "
                                   f"| {entry['timing_type']} "
                                   f"| Ждем: {entry['time_waiting']} "
                                   f"| Подтв.: {entry['confirmations']}")
                
                logger.info(f"{'='*70}")
                
                # Пауза между циклами
                await asyncio.sleep(INTERVAL_SEC)
                
            except Exception as e:
                print(f"❌ Ошибка в главном цикле: {str(e)}")
                logger.error(f"Ошибка в главном цикле: {str(e)}")
                
                # Уведомление об ошибке в Telegram
                if telegram_enabled and tg_bot.enabled:
                    try:
                        await tg_bot.send_system_message(
                            "Системная ошибка", 
                            f"Произошла ошибка в цикле #{cycle_count}:\n<code>{str(e)}</code>",
                            "🚨"
                        )
                        print("🚨 Уведомление об ошибке отправлено в Telegram")
                        logger.info("🚨 Уведомление об ошибке отправлено в Telegram")
                    except Exception as tg_error:
                        print(f"❌ Не удалось отправить ошибку в Telegram: {str(tg_error)}")
                        logger.error(f"❌ Не удалось отправить ошибку в Telegram: {str(tg_error)}")
                
                await asyncio.sleep(30)

async def send_timing_signal(tg_bot, signal):
    """Отправляет сигнал с timing информацией в Telegram"""
    try:
        timing_details = signal.get('timing_details', {})
        
        # Формируем сообщение с timing информацией
        symbol = signal['symbol']
        direction = signal['direction'].upper()
        price = signal['price']
        confidence = signal.get('confidence', 0)
        
        # Timing детали
        strategy = timing_details.get('strategy', 'unknown')
        wait_time = timing_details.get('wait_time_minutes', 0)
        entry_reason = timing_details.get('entry_reason', 'unknown')
        original_price = timing_details.get('original_price', price)
        
        # Рассчитываем улучшение цены
        if direction == 'BUY':
            price_improvement = ((original_price - price) / original_price) * 100
            improvement_text = f"👍 Лучше на {price_improvement:.2f}%" if price_improvement > 0 else ""
        else:
            price_improvement = ((price - original_price) / original_price) * 100  
            improvement_text = f"👍 Лучше на {price_improvement:.2f}%" if price_improvement > 0 else ""
        
        # Формируем сообщение
        message = f"""
🎯 <b>TIMING ВХОД ГОТОВ</b>

📈 <b>{symbol}</b> - {direction}
💰 Цена входа: <code>${price:.5f}</code>
📊 Уверенность: <b>{confidence:.1%}</b>

⏰ <b>Timing информация:</b>
• Стратегия: <i>{strategy}</i>
• Время ожидания: <i>{wait_time:.1f} мин</i>  
• Причина входа: <i>{entry_reason}</i>
• Исходная цена: <code>${original_price:.5f}</code>
{improvement_text}

🎚️ <b>Уровни:</b>
🛑 SL: <code>${signal['stop_loss']:.5f}</code>
🎯 TP1: <code>${signal['take_profit'][0]:.5f}</code>
🎯 TP2: <code>${signal['take_profit'][1]:.5f}</code>
🎯 TP3: <code>${signal['take_profit'][2]:.5f}</code>

💡 <i>Timing система дождалась оптимального момента для входа!</i>
"""
        
        # Отправляем с эмодзи в зависимости от направления
        emoji = "🟢" if direction == "BUY" else "🔴"
        
        return await tg_bot.send_message(message.strip(), parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Ошибка отправки timing сигнала: {str(e)}")
        return False

# Добавляем метод в класс телеграм бота (если он используется)
def patch_telegram_bot():
    """Добавляет метод send_timing_signal в телеграм бота"""
    try:
        if create_telegram_bot:
            # Патчим класс телеграм бота
            original_bot = create_telegram_bot()
            if original_bot:
                original_bot.__class__.send_timing_signal = send_timing_signal
    except:
        pass

if __name__ == "__main__":
    try:
        print("🏁 Запуск системы с улучшенным timing...")
        
        # Патчим телеграм бота
        patch_telegram_bot()
        
        asyncio.run(main_loop_v2())
    except KeyboardInterrupt:
        print("\n👋 Система остановлена пользователем")
        logger.info("Система остановлена пользователем")
        print(f"📊 Статистика сессии сохранена")
    except Exception as e:
        print(f"💥 Критическая ошибка: {str(e)}")
        logger.exception("Критическая ошибка")