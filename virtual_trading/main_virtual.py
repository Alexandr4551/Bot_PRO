# virtual_trading/main_virtual.py
"""
Запуск виртуального трейдера V2 с модульной архитектурой
Использует новую систему: models/ + services/ + core/

ЗАПУСК: 
  python -m virtual_trading.main_virtual
  или
  cd virtual_trading && python main_virtual.py
"""

import asyncio
import logging
import time
import signal
import sys
import os
from datetime import datetime

# Добавляем родительскую директорию в путь для импортов
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Настройка логирования
from config.logging_config import setup_logging
logger = setup_logging()

# Основные импорты из корневой директории
from config import SYMBOLS, INTERVAL_SEC
from core import BybitFuturesAPI
from core.trading_engine import HybridTradingEngineV2
from utils import display_startup_info

# 🆕 Импорт новой модульной системы виртуального трейдера
from .core.virtual_trader_v2 import VirtualTraderV2

# Глобальные переменные для корректного завершения
virtual_trader = None
is_running = True

def setup_signal_handlers():
    """Настройка обработчиков сигналов для корректного завершения"""
    def signal_handler(signum, frame):
        global is_running
        print(f"\n🛑 Получен сигнал завершения {signum}")
        logger.warning(f"🛑 Получен сигнал завершения {signum}")
        is_running = False
        
        # Сохраняем результаты виртуального трейдера
        if virtual_trader:
            print("💾 Сохраняем финальные результаты...")
            try:
                final_file = virtual_trader.save_results()
                if final_file:
                    print(f"✅ Результаты сохранены: {final_file}")
                else:
                    print("❌ Ошибка сохранения результатов")
                
                # Печатаем финальный отчет
                virtual_trader.print_final_report()
            except Exception as e:
                print(f"❌ Ошибка при сохранении: {e}")
                logger.error(f"Ошибка при сохранении: {e}")
        
        print("👋 Виртуальный трейдер завершен")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def run_virtual_trader():
    """Основная функция запуска виртуального трейдера"""
    global virtual_trader, is_running
    
    print("🤖 ВИРТУАЛЬНЫЙ ТРЕЙДЕР V2 - МОДУЛЬНАЯ АРХИТЕКТУРА")
    print("=" * 70)
    print("🎯 Режим: Виртуальное тестирование сигналов с timing")
    print("📋 Архитектура:")
    print("   • models/ - VirtualPosition, ClosedTrade")
    print("   • services/ - BalanceManager, PositionManager, Statistics, Reports")
    print("   • core/ - VirtualTraderV2 (главный оркестратор)")
    print("   • Интеграция с timing системой")
    print("   • Автоматическое сохранение результатов")
    print("=" * 70)
    
    display_startup_info()
    
    # Создаем виртуального трейдера с использованием новой модульной системы
    print("\n💼 ИНИЦИАЛИЗАЦИЯ ВИРТУАЛЬНОГО ТРЕЙДЕРА V2")
    print("=" * 60)
    
    virtual_trader = VirtualTraderV2(
        initial_balance=10000.0,      # $10,000 стартовый баланс
        position_size_percent=2.0,    # 2% на позицию
        max_exposure_percent=20.0     # Максимум 20% экспозиция
    )
    
    print(f"💰 Стартовый баланс: ${virtual_trader.initial_balance:,.2f}")
    print(f"📊 Размер позиции: {virtual_trader.balance_manager.position_size_percent}% (${virtual_trader.balance_manager.position_size_usd:,.0f})")
    print(f"🛡️ Максимальная экспозиция: {virtual_trader.balance_manager.max_exposure_percent}%")
    print(f"📁 Результаты: {virtual_trader.results_dir}/")
    print("✅ Виртуальный трейдер готов к работе")
    print("=" * 60)
    
    # Подключаемся к API и запускаем торговый движок
    print("\n🔗 Подключение к API и инициализация торгового движка...")
    
    async with BybitFuturesAPI() as api:
        print("✅ API подключен успешно")
        logger.info("✅ API подключен успешно")
        
        engine = HybridTradingEngineV2(api)
        print("✅ Торговый движок с timing инициализирован")
        logger.info("✅ Торговый движок с timing инициализирован")
        
        print(f"\n🔄 Начинаем виртуальную торговлю...")
        print(f"📊 Отслеживаемые символы: {len(SYMBOLS)}")
        print(f"⏱️ Интервал проверки: {INTERVAL_SEC} сек")
        print(f"💡 Для остановки нажмите Ctrl+C")
        print("=" * 70)
        
        cycle_count = 0
        total_signals_generated = 0
        total_entries_executed = 0
        
        # Основной цикл виртуальной торговли
        while is_running:
            try:
                cycle_count += 1
                start_time = time.time()
                
                logger.info(f"\n{'='*70}")
                logger.info(f"🔍 Цикл #{cycle_count}: Виртуальная торговля с timing (модульная архитектура)")
                logger.info(f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # ФАЗА 1: Генерация новых сигналов (добавляем в timing систему)
                new_signals = await engine.analyze_and_generate_signals(SYMBOLS)
                
                if new_signals:
                    total_signals_generated += len(new_signals)
                    virtual_trader.total_signals += len(new_signals)
                    
                    logger.info(f"📊 Новых сигналов добавлено в timing очередь: {len(new_signals)}")
                    print(f"📊 Цикл {cycle_count}: Найдено {len(new_signals)} новых сигналов для timing")
                    
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
                    print(f"🎯 Готовых к входу: {len(ready_entries)}")
                    
                    for entry_signal in ready_entries:
                        # Открываем виртуальную позицию через новую модульную систему
                        try:
                            await virtual_trader.open_virtual_position(entry_signal)
                            print(f"📈 {entry_signal['symbol']} {entry_signal['direction'].upper()} "
                                  f"добавлен в виртуальный портфель (модульная система)")
                        except Exception as vt_error:
                            logger.error(f"❌ Ошибка виртуальной торговли {entry_signal['symbol']}: {vt_error}")
                            print(f"❌ Ошибка: {entry_signal['symbol']} - {vt_error}")
                
                # ФАЗА 3: Проверка закрытия виртуальных позиций
                if virtual_trader.open_positions:
                    logger.debug(f"🔍 Проверяем закрытие {len(virtual_trader.open_positions)} виртуальных позиций...")
                    await virtual_trader.check_position_exits(api)
                
                # ФАЗА 4: Логирование статуса виртуального трейдера
                await virtual_trader.log_status(api, engine)
                
                # ФАЗА 5: Получение статуса timing системы
                timing_status = engine.get_timing_status()
                pending_count = len(timing_status.get('pending_entries', []))
                
                # Краткая статистика цикла
                cycle_time = time.time() - start_time
                
                logger.info(f"\n📊 ЦИКЛ #{cycle_count} ЗАВЕРШЕН:")
                logger.info(f"   🔍 Новых сигналов в очереди: {len(new_signals)}")
                logger.info(f"   🎯 Готовых входов: {len(ready_entries)}")
                logger.info(f"   ⏳ Ожидающих входов: {pending_count}")
                logger.info(f"   💼 Виртуальных позиций: {len(virtual_trader.open_positions)}")
                logger.info(f"   📈 Виртуальных сделок: {len(virtual_trader.closed_trades)}")
                logger.info(f"   ⏱️ Время цикла: {cycle_time:.1f} сек")
                
                # Детальный отчет каждые 20 циклов
                if cycle_count % 20 == 0:
                    print(f"\n📋 ДЕТАЛЬНЫЙ ОТЧЕТ (цикл {cycle_count}):")
                    print("=" * 50)
                    
                    # Статус timing
                    if pending_count > 0:
                        print(f"⏳ ОЖИДАЮЩИЕ ВХОДЫ ({pending_count}):")
                        for entry in timing_status.get('pending_entries', []):
                            print(f"   {entry['symbol']} {entry['direction'].upper()} "
                                  f"| {entry['timing_type']} "
                                  f"| Ждем: {entry['time_waiting']} "
                                  f"| Подтв.: {entry['confirmations']}")
                    else:
                        print("⏳ Ожидающих timing входов нет")
                    
                    # Статус виртуального трейдера (новая модульная система)
                    if len(virtual_trader.closed_trades) > 0:
                        stats = virtual_trader.calculate_statistics()
                        
                        print(f"\n💼 ВИРТУАЛЬНЫЙ ПОРТФЕЛЬ (МОДУЛЬНАЯ СИСТЕМА):")
                        print(f"   💰 Баланс: ${stats['current_balance']:,.2f} ({stats['balance_percent']:+.2f}%)")
                        print(f"   📊 Сделок: {stats['total_trades']} (винрейт: {stats['win_rate']:.1f}%)")
                        print(f"   📍 Позиций: {len(virtual_trader.open_positions)}")
                        print(f"   ⏰ Timing входов: {stats['timing_analysis']['entries_from_timing']}")
                        print(f"   ⚡ Немедленных входов: {stats['timing_analysis']['immediate_entries']}")
                        
                        # Показываем сводку по сервисам
                        balance_summary = virtual_trader.get_balance_summary()
                        positions_summary = virtual_trader.get_positions_summary()
                        trades_summary = virtual_trader.get_trades_summary()
                        
                        print(f"\n🔧 МОДУЛЬНАЯ СТАТИСТИКА:")
                        print(f"   BalanceManager: Экспозиция {balance_summary['exposure_percent']:.1f}%")
                        print(f"   PositionManager: {positions_summary['total_positions']} позиций")
                        print(f"   StatisticsCalculator: Обработано {len(virtual_trader.statistics_calculator.session_history)} записей")
                        print(f"   ReportGenerator: Сохранено в {virtual_trader.report_generator.results_dir}/")
                        
                        # Показываем последние 3 сделки
                        if virtual_trader.closed_trades:
                            print(f"\n📝 ПОСЛЕДНИЕ 3 СДЕЛКИ:")
                            for trade in virtual_trader.closed_trades[-3:]:
                                profit_emoji = "💚" if trade.pnl_usd > 0 else "❤️"
                                timing_type = trade.timing_info.get('timing_type', 'immediate') if trade.timing_info else 'immediate'
                                print(f"   {profit_emoji} {trade.symbol} {trade.direction.upper()} "
                                      f"{trade.pnl_percent:+.1f}% (${trade.pnl_usd:+.2f}) "
                                      f"{trade.exit_reason} [{timing_type}]")
                    else:
                        print(f"\n💼 ВИРТУАЛЬНЫЙ ПОРТФЕЛЬ: Пока нет закрытых сделок")
                        print(f"🔧 МОДУЛЬНАЯ СИСТЕМА: Готова к работе")
                    
                    print("=" * 50)
                
                # Автосохранение каждые 60 циклов
                if cycle_count % 60 == 0:
                    logger.info("💾 Автосохранение...")
                    try:
                        virtual_trader.save_results()
                        print(f"💾 Автосохранение выполнено (цикл {cycle_count})")
                    except Exception as save_error:
                        logger.error(f"❌ Ошибка автосохранения: {save_error}")
                
                logger.info(f"{'='*70}")
                
                # Пауза между циклами
                await asyncio.sleep(INTERVAL_SEC)
                
            except Exception as e:
                print(f"❌ Ошибка в цикле виртуального трейдера: {str(e)}")
                logger.error(f"Ошибка в цикле виртуального трейдера: {str(e)}")
                await asyncio.sleep(30)  # Пауза при ошибке

async def main():
    """Главная функция"""
    try:
        # Настраиваем обработчики сигналов
        setup_signal_handlers()
        
        # Запускаем виртуального трейдера
        await run_virtual_trader()
        
    except KeyboardInterrupt:
        print("\n👋 Виртуальный трейдер остановлен пользователем")
        logger.info("Виртуальный трейдер остановлен пользователем")
    except Exception as e:
        print(f"💥 Критическая ошибка: {str(e)}")
        logger.exception("Критическая ошибка в виртуальном трейдере")
    finally:
        # Финальное сохранение
        if virtual_trader:
            print("\n💾 Сохраняем финальные результаты...")
            try:
                final_file = virtual_trader.save_results()
                if final_file:
                    print(f"✅ Финальные результаты сохранены!")
                    print(f"📁 Файл: {final_file}")
                
                # Печатаем финальный отчет
                virtual_trader.print_final_report()
                
            except Exception as e:
                print(f"❌ Ошибка финального сохранения: {e}")
                logger.error(f"Ошибка финального сохранения: {e}")
        
        print("👋 Виртуальный трейдер завершен!")

if __name__ == "__main__":
    print("🚀 ЗАПУСК ВИРТУАЛЬНОГО ТРЕЙДЕРА V2 (МОДУЛЬНАЯ АРХИТЕКТУРА)")
    print("🎯 models/ + services/ + core/ = новая система")
    print("💡 Для остановки нажмите Ctrl+C")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Программа завершена пользователем")
    except Exception as e:
        print(f"💥 Критическая ошибка при запуске: {str(e)}")
        logging.exception("Критическая ошибка при запуске виртуального трейдера")