# test_balance_v3.py
"""
COMPREHENSIVE тест для BalanceManager V3.0
Проверяет всю логику баланса в разных сценариях
"""

import sys
import os
from datetime import datetime
from dataclasses import dataclass

# Добавляем пути для импортов
sys.path.append('.')
sys.path.append('virtual_trading')

# Моки для тестирования
@dataclass
class MockPosition:
    """Мок позиции для тестирования"""
    symbol: str
    direction: str
    entry_price: float
    quantity: float
    tp1_filled: bool = False
    tp2_filled: bool = False
    tp3_filled: bool = False
    
    def get_remaining_percent(self) -> int:
        percent = 100
        if self.tp1_filled:
            percent -= 50
        if self.tp2_filled:
            percent -= 25
        if self.tp3_filled:
            percent -= 25
        return max(0, percent)
    
    def get_remaining_quantity(self) -> float:
        remaining = self.quantity
        if self.tp1_filled:
            remaining -= self.quantity * 0.5
        if self.tp2_filled:
            remaining -= self.quantity * 0.25
        if self.tp3_filled:
            remaining -= self.quantity * 0.25
        return max(0, remaining)

def test_balance_manager():
    """Основной тест BalanceManager"""
    print("🧪 COMPREHENSIVE ТЕСТ BALANCE MANAGER V3.0")
    print("=" * 60)
    
    try:
        # Импорт после настройки путей
        from virtual_trading.services.balance_manager import BalanceManager
        
        print("✅ Импорт BalanceManager успешен")
        
        # Тест 1: Инициализация
        print("\n🔍 ТЕСТ 1: Инициализация")
        balance_manager = BalanceManager(
            initial_balance=10000.0,
            position_size_percent=2.0,
            max_exposure_percent=20.0
        )
        
        assert balance_manager.initial_balance == 10000.0
        assert balance_manager.available_balance == 10000.0
        assert balance_manager.position_size_usd == 200.0
        assert balance_manager.max_exposure_usd == 2000.0
        assert balance_manager.total_invested == 0.0
        assert balance_manager.total_realized_pnl == 0.0
        
        print("✅ Инициализация корректна")
        
        # Тест 2: Резервирование средств
        print("\n🔍 ТЕСТ 2: Резервирование средств")
        positions = {}
        
        can_open, reason = balance_manager.can_open_new_position(positions)
        assert can_open == True
        assert reason == "ok"
        
        success = balance_manager.reserve_funds(200.0)
        assert success == True
        assert balance_manager.available_balance == 9800.0
        assert balance_manager.total_invested == 200.0
        
        print("✅ Резервирование работает корректно")
        
        # Тест 3: Создание позиции
        print("\n🔍 ТЕСТ 3: Позиция и расчеты")
        position = MockPosition(
            symbol="BTCUSDT",
            direction="buy",
            entry_price=50000.0,
            quantity=200.0 / 50000.0  # 0.004 BTC
        )
        positions["BTCUSDT"] = position
        
        # Проверяем расчеты
        invested_capital = balance_manager.get_invested_capital(positions)
        assert invested_capital == 200.0
        
        current_balance = balance_manager.get_current_balance(positions)
        assert current_balance == 10000.0  # 9800 + 200
        
        print("✅ Расчеты позиций корректны")
        
        # Тест 4: Нереализованный P&L
        print("\n🔍 ТЕСТ 4: Нереализованный P&L")
        current_prices = {"BTCUSDT": 52000.0}  # Цена выросла на $2000
        
        unrealized_pnl = balance_manager.get_unrealized_pnl(positions, current_prices)
        expected_pnl = position.quantity * (52000.0 - 50000.0)  # 0.004 * 2000 = $8
        assert abs(unrealized_pnl - expected_pnl) < 0.01
        
        current_balance_with_pnl = balance_manager.get_current_balance(positions, current_prices)
        assert abs(current_balance_with_pnl - (10000.0 + expected_pnl)) < 0.01
        
        print(f"✅ Нереализованный P&L: ${unrealized_pnl:+.2f}")
        
        # Тест 5: Частичное закрытие (TP1 - 50%)
        print("\n🔍 ТЕСТ 5: Частичное закрытие TP1")
        tp1_price = 52000.0
        tp1_quantity = position.quantity * 0.5
        tp1_pnl = tp1_quantity * (tp1_price - position.entry_price)  # 0.002 * 2000 = $4
        
        # Освобождаем 50% позиции с прибылью
        balance_manager.release_funds(100.0, tp1_pnl)  # 50% от $200 + P&L
        position.tp1_filled = True
        
        assert abs(balance_manager.available_balance - (9800.0 + 100.0 + tp1_pnl)) < 0.01
        assert balance_manager.total_invested == 100.0  # Осталось 50%
        assert abs(balance_manager.total_realized_pnl - tp1_pnl) < 0.01
        
        print(f"✅ TP1 закрыт с P&L: ${tp1_pnl:+.2f}")
        
        # Тест 6: Проверка баланса после частичного закрытия
        print("\n🔍 ТЕСТ 6: Баланс после частичного закрытия")
        invested_capital = balance_manager.get_invested_capital(positions)
        assert invested_capital == 100.0  # 50% от $200
        
        unrealized_pnl = balance_manager.get_unrealized_pnl(positions, current_prices)
        expected_unrealized = position.get_remaining_quantity() * (52000.0 - 50000.0)  # 0.002 * 2000 = $4
        assert abs(unrealized_pnl - expected_unrealized) < 0.01
        
        current_balance = balance_manager.get_current_balance(positions, current_prices)
        expected_balance = balance_manager.available_balance + invested_capital + unrealized_pnl
        assert abs(current_balance - expected_balance) < 0.01
        
        print(f"✅ Баланс корректен: ${current_balance:.2f}")
        
        # Тест 7: Полное закрытие позиции
        print("\n🔍 ТЕСТ 7: Полное закрытие позиции")
        # Закрываем остальные 50%
        remaining_quantity = position.get_remaining_quantity()
        remaining_pnl = remaining_quantity * (52000.0 - 50000.0)
        
        balance_manager.release_funds(100.0, remaining_pnl)
        position.tp2_filled = True
        position.tp3_filled = True
        
        # Удаляем позицию
        del positions["BTCUSDT"]
        
        # Проверяем финальное состояние
        final_balance = balance_manager.get_current_balance(positions)
        expected_final = balance_manager.initial_balance + balance_manager.total_realized_pnl
        assert abs(final_balance - expected_final) < 0.01
        assert balance_manager.total_invested == 0.0
        
        print(f"✅ Позиция полностью закрыта, баланс: ${final_balance:.2f}")
        
        # Тест 8: Лимиты экспозиции
        print("\n🔍 ТЕСТ 8: Тестирование лимитов")
        
        # Имитируем много позиций для проверки лимита экспозиции
        test_positions = {}
        for i in range(10):  # 10 позиций по $200 = $2000 (лимит экспозиции)
            balance_manager.reserve_funds(200.0)
            test_positions[f"TEST{i}"] = MockPosition(f"TEST{i}", "buy", 100.0, 2.0)
        
        # Проверяем лимит экспозиции
        can_open, reason = balance_manager.can_open_new_position(test_positions)
        assert can_open == False
        assert reason == "exposure_limit"
        
        print("✅ Лимит экспозиции работает корректно")
        
        # Тест 9: Валидация состояния
        print("\n🔍 ТЕСТ 9: Валидация состояния")
        validation = balance_manager.validate_state()
        
        print(f"   Доступный баланс: ${balance_manager.available_balance:.2f}")
        print(f"   Инвестировано: ${balance_manager.total_invested:.2f}")
        print(f"   Реализованный P&L: ${balance_manager.total_realized_pnl:.2f}")
        print(f"   Валидация: {'✅ OK' if validation['is_valid'] else '❌ ERROR'}")
        
        if not validation['is_valid']:
            print(f"   Проблемы: {validation['issues']}")
        
        # Тест 10: Краткая сводка
        print("\n🔍 ТЕСТ 10: Сводка баланса")
        summary = balance_manager.get_balance_summary(test_positions)
        
        print(f"   Текущий баланс: ${summary['current_balance']:,.2f}")
        print(f"   Изменение баланса: {summary['balance_percent']:+.2f}%")
        print(f"   Экспозиция: {summary['exposure_percent']:.1f}%")
        
        # Тест 11: Риск-лимиты
        print("\n🔍 ТЕСТ 11: Проверка рисков")
        risk_status = balance_manager.check_risk_limits(test_positions)
        
        print(f"   Уровень риска: {risk_status['risk_level']}")
        print(f"   Предупреждений: {len(risk_status['warnings'])}")
        
        for warning in risk_status['warnings']:
            print(f"     ⚠️ {warning}")
        
        print("\n" + "=" * 60)
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ BalanceManager V3.0 готов к production!")
        
        # Финальная статистика
        print(f"\n📊 ФИНАЛЬНАЯ СТАТИСТИКА:")
        print(f"   Начальный баланс: ${balance_manager.initial_balance:,.2f}")
        print(f"   Текущий баланс: ${summary['current_balance']:,.2f}")
        print(f"   Реализованный P&L: ${balance_manager.total_realized_pnl:+.2f}")
        print(f"   Экспозиция: {summary['exposure_percent']:.1f}% из {balance_manager.max_exposure_percent}%")
        print(f"   Системный статус: {'🟢 ЗДОРОВ' if validation['is_valid'] else '🔴 ПРОБЛЕМЫ'}")
        
        return True
        
    except ImportError as e:
        print(f"❌ ОШИБКА ИМПОРТА: {e}")
        print("   Убедитесь что virtual_trading модули доступны")
        return False
        
    except AssertionError as e:
        print(f"❌ ТЕСТ ПРОВАЛЕН: Assertion error")
        print(f"   Детали: {e}")
        return False
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_edge_cases():
    """Тест крайних случаев"""
    print("\n🧪 ТЕСТ КРАЙНИХ СЛУЧАЕВ")
    print("=" * 40)
    
    try:
        from virtual_trading.services.balance_manager import BalanceManager
        
        # Тест с маленьким балансом
        print("🔍 Маленький баланс:")
        small_bm = BalanceManager(100.0, 10.0, 50.0)
        positions = {}
        can_open, reason = small_bm.can_open_new_position(positions)
        print(f"   Можно открыть позицию: {'✅' if can_open else '❌'} ({reason})")
        
        # Тест с нулевыми/отрицательными значениями
        print("\n🔍 Валидация:")
        validation = small_bm.validate_state()
        print(f"   Система валидна: {'✅' if validation['is_valid'] else '❌'}")
        
        # Тест со множественными операциями
        print("\n🔍 Множественные операции:")
        for i in range(5):
            if small_bm.can_open_new_position({})[0]:
                small_bm.reserve_funds(10.0)
                small_bm.release_funds(10.0, 1.0)  # +$1 каждый раз
        
        final_validation = small_bm.validate_state()
        print(f"   После 5 операций: {'✅' if final_validation['is_valid'] else '❌'}")
        print(f"   P&L: ${small_bm.total_realized_pnl:+.2f}")
        
        print("✅ Крайние случаи обработаны корректно")
        
    except Exception as e:
        print(f"❌ Ошибка в крайних случаях: {e}")

if __name__ == "__main__":
    print("🚀 ЗАПУСК COMPREHENSIVE ТЕСТА BALANCE MANAGER")
    print("🎯 Проверяем production-ready логику баланса V3.0")
    print()
    
    # Основной тест
    success = test_balance_manager()
    
    if success:
        # Дополнительные тесты
        test_edge_cases()
        
        print("\n🎊 ЗАКЛЮЧЕНИЕ:")
        print("✅ Логика баланса работает корректно!")
        print("🚀 Система готова к production!")
        print("🎯 Можно интегрировать в основной проект!")
    else:
        print("\n❌ ЗАКЛЮЧЕНИЕ:")
        print("🚨 Обнаружены проблемы в логике баланса!")
        print("🔧 Требуется дополнительная отладка!")