#!/usr/bin/env python3
"""
КРИТИЧЕСКИЙ ТЕСТ ТОЧНОСТИ РАСЧЕТА БАЛАНСА
Проверяет математику на реальных данных LTCUSDT
"""

import json
from datetime import datetime
from virtual_trading.services.balance_manager import BalanceManager

def test_balance_accuracy():
    """Проверяем точность расчета баланса на реальных данных"""
    print("🧮 КРИТИЧЕСКИЙ ТЕСТ РАСЧЕТА БАЛАНСА")
    print("=" * 50)
    
    # Исходные данные LTCUSDT из реальной торговли
    initial_balance = 10000.0
    position_size_percent = 2.0
    position_size_usd = 200.0  # 2% от 10000
    
    # Данные реальной сделки LTCUSDT
    entry_price = 119.45
    tp1_price = 117.78
    tp2_price = 117.165  
    tp3_price = 116.96
    
    # Реальные P&L из файла
    tp1_pnl = 1.3980745081624124
    tp2_pnl = 0.956467141063205
    tp3_pnl = 1.0422771033905438
    total_expected_pnl = tp1_pnl + tp2_pnl + tp3_pnl
    
    print(f"📊 ИСХОДНЫЕ ДАННЫЕ:")
    print(f"   Баланс: ${initial_balance:,.2f}")
    print(f"   Размер позиции: ${position_size_usd:.2f} ({position_size_percent}%)")
    print(f"   Вход: ${entry_price:.2f}")
    print(f"   TP1: ${tp1_price:.2f} → P&L: ${tp1_pnl:+.2f}")
    print(f"   TP2: ${tp2_price:.2f} → P&L: ${tp2_pnl:+.2f}")
    print(f"   TP3: ${tp3_price:.2f} → P&L: ${tp3_pnl:+.2f}")
    print(f"   Ожидаемый общий P&L: ${total_expected_pnl:+.2f}")
    
    # Создаем BalanceManager
    balance_manager = BalanceManager(
        initial_balance=initial_balance,
        position_size_percent=position_size_percent,
        max_exposure_percent=20.0
    )
    
    print(f"\n🔧 ИНИЦИАЛИЗАЦИЯ BALANCE MANAGER:")
    print(f"   Доступный баланс: ${balance_manager.available_balance:,.2f}")
    print(f"   Размер позиции: ${balance_manager.position_size_usd:.2f}")
    print(f"   Инвестировано: ${balance_manager.total_invested:.2f}")
    print(f"   Реализованный P&L: ${balance_manager.total_realized_pnl:.2f}")
    
    # Шаг 1: Резервируем средства для позиции
    print(f"\n📥 ШАГ 1: РЕЗЕРВИРОВАНИЕ СРЕДСТВ")
    reserved = balance_manager.reserve_funds(position_size_usd)
    print(f"   Зарезервировано: ${position_size_usd:.2f} → {reserved}")
    print(f"   Доступный баланс: ${balance_manager.available_balance:.2f}")
    print(f"   Инвестировано: ${balance_manager.total_invested:.2f}")
    
    # Проверка после резервирования
    expected_available = initial_balance - position_size_usd
    if abs(balance_manager.available_balance - expected_available) > 0.01:
        print(f"   ❌ ОШИБКА: доступный должен быть ${expected_available:.2f}")
        return False
    
    # Шаг 2: Частичные закрытия TP1, TP2, TP3
    print(f"\n💰 ШАГ 2: ЧАСТИЧНЫЕ ЗАКРЫТИЯ")
    
    # TP1 (50%)
    tp1_amount = position_size_usd * 0.5  # 50% = $100
    balance_manager.release_funds(tp1_amount, tp1_pnl)
    print(f"   TP1: ${tp1_amount:.2f} + P&L ${tp1_pnl:+.2f}")
    print(f"   Доступный: ${balance_manager.available_balance:.2f}")
    print(f"   Инвестировано: ${balance_manager.total_invested:.2f}")
    print(f"   Реализованный P&L: ${balance_manager.total_realized_pnl:.2f}")
    
    # TP2 (25%)
    tp2_amount = position_size_usd * 0.25  # 25% = $50
    balance_manager.release_funds(tp2_amount, tp2_pnl)
    print(f"   TP2: ${tp2_amount:.2f} + P&L ${tp2_pnl:+.2f}")
    print(f"   Доступный: ${balance_manager.available_balance:.2f}")
    print(f"   Инвестировано: ${balance_manager.total_invested:.2f}")
    print(f"   Реализованный P&L: ${balance_manager.total_realized_pnl:.2f}")
    
    # TP3 (25%)
    tp3_amount = position_size_usd * 0.25  # 25% = $50
    balance_manager.release_funds(tp3_amount, tp3_pnl)
    print(f"   TP3: ${tp3_amount:.2f} + P&L ${tp3_pnl:+.2f}")
    print(f"   Доступный: ${balance_manager.available_balance:.2f}")
    print(f"   Инвестировано: ${balance_manager.total_invested:.2f}")
    print(f"   Реализованный P&L: ${balance_manager.total_realized_pnl:.2f}")
    
    # Финальная проверка
    print(f"\n🎯 ФИНАЛЬНАЯ ПРОВЕРКА:")
    final_balance = balance_manager.available_balance
    expected_final = initial_balance + total_expected_pnl
    
    print(f"   Финальный баланс: ${final_balance:.2f}")
    print(f"   Ожидаемый баланс: ${expected_final:.2f}")
    print(f"   Расхождение: ${abs(final_balance - expected_final):.6f}")
    print(f"   Реализованный P&L: ${balance_manager.total_realized_pnl:.2f}")
    print(f"   Ожидаемый P&L: ${total_expected_pnl:.2f}")
    print(f"   Инвестировано: ${balance_manager.total_invested:.2f} (должно быть 0)")
    
    # Валидация состояния
    validation = balance_manager.validate_state()
    print(f"\n✅ ВАЛИДАЦИЯ СОСТОЯНИЯ:")
    print(f"   Состояние валидно: {validation['is_valid']}")
    if validation['issues']:
        for issue in validation['issues']:
            print(f"   ❌ {issue}")
    
    # Проверка точности
    balance_accurate = abs(final_balance - expected_final) < 0.000001  # 1 микроцент
    pnl_accurate = abs(balance_manager.total_realized_pnl - total_expected_pnl) < 0.000001
    invested_zero = abs(balance_manager.total_invested) < 0.000001
    
    print(f"\n🔍 РЕЗУЛЬТАТЫ ПРОВЕРКИ:")
    print(f"   ✅ Баланс точный: {balance_accurate}")
    print(f"   ✅ P&L точный: {pnl_accurate}")
    print(f"   ✅ Инвестировано = 0: {invested_zero}")
    print(f"   ✅ Состояние валидно: {validation['is_valid']}")
    
    all_passed = balance_accurate and pnl_accurate and invested_zero and validation['is_valid']
    
    if all_passed:
        print(f"\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! РАСЧЕТ БАЛАНСА ТОЧНЫЙ!")
        return True
    else:
        print(f"\n❌ НАЙДЕНЫ ОШИБКИ В РАСЧЕТЕ БАЛАНСА!")
        return False

if __name__ == "__main__":
    test_balance_accuracy()