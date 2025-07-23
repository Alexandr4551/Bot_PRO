#!/usr/bin/env python3
"""
Тест исправления логики подсчета статистики
Проверяем группировку частичных выходов как одной сделки
"""

import json
from datetime import datetime
from virtual_trading.services.statistics_calculator import StatisticsCalculator
from virtual_trading.models.trade import ClosedTrade

def test_statistics_fix():
    """Тестируем исправленную логику статистики"""
    print("🧪 ТЕСТ ИСПРАВЛЕННОЙ ЛОГИКИ СТАТИСТИКИ")
    print("=" * 50)
    
    # Создаем калькулятор статистики
    stats_calc = StatisticsCalculator()
    
    # Читаем реальные данные из закрытых сделок
    try:
        with open('virtual_trading_results_v2/closed_trades_20250722_230106.json', 'r') as f:
            trades_data = json.load(f)
        
        print(f"📂 Загружено {len(trades_data)} записей о выходах")
        
        # Конвертируем в объекты ClosedTrade
        closed_trades = []
        for trade_data in trades_data:
            trade = ClosedTrade(
                symbol=trade_data['symbol'],
                direction=trade_data['direction'],
                entry_price=trade_data['entry_price'],
                entry_time=datetime.fromisoformat(trade_data['entry_time']),
                exit_price=trade_data['exit_price'],
                exit_time=datetime.fromisoformat(trade_data['exit_time']),
                exit_reason=trade_data['exit_reason'],
                position_size_usd=trade_data['position_size_usd'],
                quantity_closed=trade_data['quantity_closed'],
                pnl_usd=trade_data['pnl_usd'],
                pnl_percent=trade_data['pnl_percent'],
                duration_minutes=trade_data['duration_minutes'],
                timing_info=trade_data.get('timing_info', {})
            )
            closed_trades.append(trade)
        
        print(f"✅ Конвертировано в {len(closed_trades)} объектов ClosedTrade")
        
        # Рассчитываем статистику старым способом (как частичные выходы)
        print("\n🔴 СТАРАЯ ЛОГИКА (каждый выход = отдельная сделка):")
        print(f"   Всего 'сделок': {len(closed_trades)}")
        for i, trade in enumerate(closed_trades, 1):
            print(f"   {i}. {trade.symbol} {trade.exit_reason}: ${trade.pnl_usd:+.2f}")
        
        # Рассчитываем статистику новым способом (группировка)
        print("\n🟢 НОВАЯ ЛОГИКА (группировка частичных выходов):")
        stats = stats_calc.calculate_trades_statistics(closed_trades)
        
        print(f"   Всего сделок: {stats['total_trades']}")
        print(f"   Выигрышных: {stats['winning_trades']}")
        print(f"   Проигрышных: {stats['losing_trades']}")
        print(f"   Винрейт: {stats['win_rate']:.1f}%")
        print(f"   Общий P&L: ${stats['total_pnl']:+.2f}")
        print(f"   Средний P&L: ${stats['average_pnl']:+.2f}")
        print(f"   Всего частичных выходов: {stats['total_partial_exits']}")
        
        print(f"\n📊 Детали группировки:")
        for detail in stats['grouped_trades_details']:
            print(f"   • {detail}")
        
        # Проверяем корректность
        print(f"\n🔍 ПРОВЕРКА КОРРЕКТНОСТИ:")
        total_pnl_manual = sum(t.pnl_usd for t in closed_trades)
        print(f"   Сумма P&L вручную: ${total_pnl_manual:+.2f}")
        print(f"   Сумма P&L в статистике: ${stats['total_pnl']:+.2f}")
        print(f"   ✅ P&L сходится: {abs(total_pnl_manual - stats['total_pnl']) < 0.01}")
        
        # Ожидаемые результаты для LTCUSDT
        print(f"\n✅ ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ:")
        print(f"   • 1 сделка LTCUSDT с 3 частичными выходами (TP1, TP2, TP3)")
        print(f"   • Общий P&L: ${total_pnl_manual:+.2f}")
        print(f"   • Винрейт: 100% (1 выигрышная сделка из 1)")
        
        print(f"\n🎯 РЕЗУЛЬТАТ ТЕСТА:")
        if stats['total_trades'] == 1 and stats['win_rate'] == 100.0:
            print("   ✅ ТЕСТ ПРОЙДЕН! Логика исправлена корректно")
            return True
        else:
            print("   ❌ ТЕСТ НЕ ПРОЙДЕН! Требуется дополнительная корректировка")
            return False
            
    except FileNotFoundError:
        print("❌ Файл с данными о сделках не найден")
        return False
    except Exception as e:
        print(f"❌ Ошибка в тесте: {e}")
        return False

if __name__ == "__main__":
    test_statistics_fix()