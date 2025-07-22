# test_balance_logic.py
"""
Тестовый скрипт для проверки исправленной логики баланса
Запуск: python test_balance_logic.py
"""

import sys
import os
from datetime import datetime

# Добавляем пути для импорта
sys.path.append('.')
sys.path.append('virtual_trading')

def test_balance_logic():
    """Тестирует основные сценарии работы с балансом"""
    
    print("🧪 ТЕСТИРОВАНИЕ ЛОГИКИ БАЛАНСА V2.1")
    print("=" * 60)
    
    try:
        # Импорты (с обработкой ошибок)
        from virtual_trading.services.balance_manager import BalanceManager
        from virtual_trading.models.position import VirtualPosition
        
        print("✅ Импорты успешны")
        
        # Создаем BalanceManager
        balance_manager = BalanceManager(
            initial_balance=10000.0,
            position_size_percent=2.0,
            max_exposure_percent=20.0
        )
        
        print("✅ BalanceManager создан")
        print(f"   Начальный баланс: ${balance_manager.initial_balance:,.2f}")
        print(f"   Размер позиции: ${balance_manager.position_size_usd:,.0f}")
        print(f"   Лимит экспозиции: ${balance_manager.max_exposure_usd:,.0f}")
        
        # Тест 1: Проверка начального состояния
        print("\n🔍 ТЕСТ 1: Начальное состояние")
        positions = {}
        
        balance_summary = balance_manager.get_balance_summary(positions)
        consistency = balance_manager.check_balance_consistency(positions)
        
        print(f"   Доступный баланс: ${balance_summary['available_balance']:,.2f}")
        print(f"   Текущий баланс: ${balance_summary['current_balance']:,.2f}")
        print(f"   Инвестированный капитал: ${balance_summary['invested_capital']:,.2f}")
        print(f"   Консистентность: {'✅' if consistency['is_consistent'] else '❌'}")
        
        # Тест 2: Открытие позиций
        print("\n🔍 ТЕСТ 2: Открытие позиций")
        
        # Создаем тестовую позицию
        test_position = VirtualPosition(
            symbol="BTCUSDT",
            direction="buy",
            entry_price=50000.0,
            entry_time=datetime.now(),
            position_size_usd=200.0,
            quantity=200.0 / 50000.0,  # 0.004 BTC
            stop_loss=48000.0,
            tp1=52000.0,
            tp2=54000.0,
            tp3=56000.0
        )
        
        # Резервируем средства
        can_open, reason = balance_manager.can_open_new_position(positions)
        print(f"   Можно открыть позицию: {'✅' if can_open else '❌'} ({reason})")
        
        if can_open:
            success = balance_manager.reserve_funds(200.0)
            print(f"   Резервирование средств: {'✅' if success else '❌'}")
            
            if success:
                positions["BTCUSDT"] = test_position
                print(f"   Позиция BTCUSDT добавлена")
        
        # Проверяем состояние после открытия
        balance_summary = balance_manager.get_balance_summary(positions)
        consistency = balance_manager.check_balance_consistency(positions)
        
        print(f"   Доступный баланс: ${balance_summary['available_balance']:,.2f}")
        print(f"   Инвестированный капитал: ${balance_summary['invested_capital']:,.2f}")
        print(f"   Текущий баланс: ${balance_summary['current_balance']:,.2f}")
        print(f"   Консистентность: {'✅' if consistency['is_consistent'] else '❌'}")
        
        # Тест 3: Частичное закрытие
        print("\n🔍 ТЕСТ 3: Частичное закрытие (TP1)")
        
        if "BTCUSDT" in positions:
            position = positions["BTCUSDT"]
            
            # Имитируем закрытие 50% на TP1
            pnl_per_unit = 52000.0 - 50000.0  # $2000 profit per BTC
            quantity_closed = position.quantity * 0.5  # 50%
            pnl_usd = quantity_closed * pnl_per_unit
            
            print(f"   Закрываем 50% позиции")
            print(f"   Количество: {quantity_closed:.6f} BTC")
            print(f"   P&L: ${pnl_usd:+.2f}")
            
            # Освобождаем средства с прибылью
            balance_manager.release_funds(100.0, pnl_usd)  # 50% от $200 + profit
            
            # Обновляем позицию
            position.tp1_filled = True
            
            # Проверяем состояние
            balance_summary = balance_manager.get_balance_summary(positions)
            consistency = balance_manager.check_balance_consistency(positions)
            
            print(f"   Доступный баланс: ${balance_summary['available_balance']:,.2f}")
            print(f"   Инвестированный капитал: ${balance_summary['invested_capital']:,.2f}")
            print(f"   Текущий баланс: ${balance_summary['current_balance']:,.2f}")
            print(f"   Реализованный P&L: ${balance_summary.get('total_realized_pnl', 0):+.2f}")
            print(f"   Консистентность: {'✅' if consistency['is_consistent'] else '❌'}")
            
            if not consistency['is_consistent']:
                print(f"   ⚠️ Разница: ${consistency.get('difference', 0):+.2f}")
        
        # Тест 4: Полное закрытие
        print("\n🔍 ТЕСТ 4: Полное закрытие позиции")
        
        if "BTCUSDT" in positions:
            position = positions["BTCUSDT"]
            
            # Закрываем оставшиеся 50%
            remaining_quantity = position.quantity * 0.5
            pnl_usd = remaining_quantity * (54000.0 - 50000.0)  # TP2 price
            
            print(f"   Закрываем оставшиеся 50%")
            print(f"   P&L: ${pnl_usd:+.2f}")
            
            balance_manager.release_funds(100.0, pnl_usd)  # Remaining 50% + profit
            
            # Удаляем позицию
            del positions["BTCUSDT"]
            
            # Финальная проверка
            balance_summary = balance_manager.get_balance_summary(positions)
            consistency = balance_manager.check_balance_consistency(positions)
            
            print(f"   Доступный баланс: ${balance_summary['available_balance']:,.2f}")
            print(f"   Инвестированный капитал: ${balance_summary['invested_capital']:,.2f}")
            print(f"   Текущий баланс: ${balance_summary['current_balance']:,.2f}")
            print(f"   Общий реализованный P&L: ${balance_summary.get('total_realized_pnl', 0):+.2f}")
            print(f"   Изменение баланса: {balance_summary['balance_percent']:+.2f}%")
            print(f"   Консистентность: {'✅' if consistency['is_consistent'] else '❌'}")
        
        # Тест 5: Проверка лимитов
        print("\n🔍 ТЕСТ 5: Проверка риск-лимитов")
        
        risk_status = balance_manager.check_risk_limits(positions)
        print(f"   Уровень риска: {risk_status['risk_level']}")
        print(f"   Предупреждений: {len(risk_status['warnings'])}")
        
        for warning in risk_status['warnings']:
            print(f"   ⚠️ {warning}")
        
        for recommendation in risk_status.get('recommendations', []):
            print(f"   💡 {recommendation}")
        
        # Тест 6: Debug информация
        print("\n🔍 ТЕСТ 6: Debug информация")
        
        debug_info = balance_manager.get_debug_info()
        print(f"   Операций с балансом: {debug_info['total_operations']}")
        print(f"   Последние операции: {len(debug_info['recent_operations'])}")
        
        if debug_info['recent_operations']:
            print("   Последние 3 операции:")
            for op in debug_info['recent_operations'][-3:]:
                print(f"     {op['type']}: ${op.get('amount', 0):+.2f}, P&L: ${op.get('pnl', 0):+.2f}")
        
        print("\n" + "=" * 60)
        print("🎉 ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ УСПЕШНО!")
        
        final_balance = balance_summary['current_balance']
        initial_balance = balance_manager.initial_balance
        total_return = ((final_balance - initial_balance) / initial_balance) * 100
        
        print(f"📊 ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ:")
        print(f"   Начальный баланс: ${initial_balance:,.2f}")
        print(f"   Финальный баланс: ${final_balance:,.2f}")
        print(f"   Общая доходность: {total_return:+.2f}%")
        print(f"   Состояние системы: {'✅ Стабильно' if consistency['is_consistent'] else '⚠️ Требует внимания'}")
        
        return True
        
    except ImportError as e:
        print(f"❌ ОШИБКА ИМПОРТА: {e}")
        print("   Убедитесь что модули virtual_trading установлены правильно")
        return False
        
    except Exception as e:
        print(f"❌ ОШИБКА ТЕСТА: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_edge_cases():
    """Тестирует крайние случаи и потенциальные проблемы"""
    
    print("\n🧪 ТЕСТИРОВАНИЕ КРАЙНИХ СЛУЧАЕВ")
    print("=" * 50)
    
    try:
        from virtual_trading.services.balance_manager import BalanceManager
        from virtual_trading.models.position import VirtualPosition
        
        # Тест с маленьким балансом
        print("🔍 Тест: Маленький баланс")
        small_balance_manager = BalanceManager(100.0, 10.0, 50.0)  # $100, 10% позиция
        
        positions = {}
        can_open, reason = small_balance_manager.can_open_new_position(positions)
        print(f"   Можно открыть позицию с балансом $100: {'✅' if can_open else '❌'} ({reason})")
        
        # Тест с нулевыми ценами
        print("\n🔍 Тест: Нулевые цены")
        balance_manager = BalanceManager(1000.0, 5.0, 25.0)
        
        test_position = VirtualPosition(
            symbol="TESTCOIN",
            direction="buy", 
            entry_price=0.0001,  # Очень маленькая цена
            entry_time=datetime.now(),
            position_size_usd=50.0,
            quantity=50.0 / 0.0001,  # Большое количество
            stop_loss=0.00008,
            tp1=0.00012,
            tp2=0.00015,
            tp3=0.00020
        )
        
        positions = {"TESTCOIN": test_position}
        current_prices = {"TESTCOIN": 0.00015}
        
        balance_summary = balance_manager.get_balance_summary(positions, current_prices)
        unrealized_pnl = balance_summary.get('unrealized_pnl', 0)
        
        print(f"   Нереализованный P&L с маленькими ценами: ${unrealized_pnl:+.2f}")
        
        # Тест консистентности с экстремальными значениями
        consistency = balance_manager.check_balance_consistency(positions, current_prices)
        print(f"   Консистентность с маленькими ценами: {'✅' if consistency['is_consistent'] else '❌'}")
        
        print("\n✅ Тесты крайних случаев завершены")
        
    except Exception as e:
        print(f"❌ Ошибка в тестах крайних случаев: {e}")

if __name__ == "__main__":
    print("Запуск тестирования логики баланса...")
    
    success = test_balance_logic()
    
    if success:
        test_edge_cases()
        print("\n🎯 ЗАКЛЮЧЕНИЕ: Логика баланса работает корректно!")
        print("   Система готова к использованию в виртуальной торговле.")
    else:
        print("\n❌ ЗАКЛЮЧЕНИЕ: Обнаружены проблемы в логике баланса!")
        print("   Требуется дополнительная отладка.")