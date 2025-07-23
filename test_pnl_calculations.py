#!/usr/bin/env python3
"""
ТЕСТ ТОЧНОСТИ РАСЧЕТОВ P&L В POSITION MANAGER
Проверяем математику для SELL позиции LTCUSDT
"""

def test_pnl_calculations():
    """Проверяем точность расчетов P&L в PositionManager"""
    print("ТЕСТ РАСЧЕТОВ P&L В POSITION MANAGER")
    print("=" * 50)
    
    # Данные из реальной сделки LTCUSDT SELL
    position_size_usd = 200.0
    entry_price = 119.45
    
    # Расчет количества для SELL позиции
    total_quantity = position_size_usd / entry_price
    print(f"📊 ИСХОДНЫЕ ДАННЫЕ:")
    print(f"   Направление: SELL")
    print(f"   Размер позиции: ${position_size_usd:.2f}")
    print(f"   Цена входа: ${entry_price:.5f}")
    print(f"   Общее количество: {total_quantity:.10f}")
    
    # TP1: 50% позиции
    tp1_percent = 50
    tp1_price = 117.78
    tp1_quantity = total_quantity * (tp1_percent / 100)
    tp1_amount_usd = position_size_usd * (tp1_percent / 100)
    
    # Расчет P&L для SELL: прибыль когда цена падает
    tp1_pnl_per_unit = entry_price - tp1_price  # 119.45 - 117.78 = 1.67
    tp1_pnl_usd = tp1_quantity * tp1_pnl_per_unit
    tp1_pnl_percent = (tp1_pnl_usd / tp1_amount_usd) * 100
    
    print(f"\nTP1 (50% позиции):")
    print(f"   Цена выхода: ${tp1_price:.5f}")
    print(f"   Количество: {tp1_quantity:.10f}")
    print(f"   Сумма USD: ${tp1_amount_usd:.2f}")
    print(f"   P&L за единицу: ${tp1_pnl_per_unit:.5f}")
    print(f"   P&L USD: ${tp1_pnl_usd:.10f}")
    print(f"   P&L %: {tp1_pnl_percent:.10f}%")
    print(f"   Ожидаемый P&L: $1.3980745081624124")
    print(f"   Расхождение: ${abs(tp1_pnl_usd - 1.3980745081624124):.10f}")
    
    # TP2: 25% позиции
    tp2_percent = 25
    tp2_price = 117.165
    tp2_quantity = total_quantity * (tp2_percent / 100)
    tp2_amount_usd = position_size_usd * (tp2_percent / 100)
    
    tp2_pnl_per_unit = entry_price - tp2_price  # 119.45 - 117.165 = 2.285
    tp2_pnl_usd = tp2_quantity * tp2_pnl_per_unit
    tp2_pnl_percent = (tp2_pnl_usd / tp2_amount_usd) * 100
    
    print(f"\nTP2 (25% позиции):")
    print(f"   Цена выхода: ${tp2_price:.5f}")
    print(f"   Количество: {tp2_quantity:.10f}")
    print(f"   Сумма USD: ${tp2_amount_usd:.2f}")
    print(f"   P&L за единицу: ${tp2_pnl_per_unit:.5f}")
    print(f"   P&L USD: ${tp2_pnl_usd:.10f}")
    print(f"   P&L %: {tp2_pnl_percent:.10f}%")
    print(f"   Ожидаемый P&L: $0.956467141063205")
    print(f"   Расхождение: ${abs(tp2_pnl_usd - 0.956467141063205):.10f}")
    
    # TP3: 25% позиции
    tp3_percent = 25
    tp3_price = 116.96
    tp3_quantity = total_quantity * (tp3_percent / 100)
    tp3_amount_usd = position_size_usd * (tp3_percent / 100)
    
    tp3_pnl_per_unit = entry_price - tp3_price  # 119.45 - 116.96 = 2.49
    tp3_pnl_usd = tp3_quantity * tp3_pnl_per_unit
    tp3_pnl_percent = (tp3_pnl_usd / tp3_amount_usd) * 100
    
    print(f"\nTP3 (25% позиции):")
    print(f"   Цена выхода: ${tp3_price:.5f}")
    print(f"   Количество: {tp3_quantity:.10f}")
    print(f"   Сумма USD: ${tp3_amount_usd:.2f}")
    print(f"   P&L за единицу: ${tp3_pnl_per_unit:.5f}")
    print(f"   P&L USD: ${tp3_pnl_usd:.10f}")
    print(f"   P&L %: {tp3_pnl_percent:.10f}%")
    print(f"   Ожидаемый P&L: $1.0422771033905438")
    print(f"   Расхождение: ${abs(tp3_pnl_usd - 1.0422771033905438):.10f}")
    
    # Итоговая проверка
    total_calculated_pnl = tp1_pnl_usd + tp2_pnl_usd + tp3_pnl_usd
    total_expected_pnl = 1.3980745081624124 + 0.956467141063205 + 1.0422771033905438
    
    print(f"\n🎯 ИТОГОВАЯ ПРОВЕРКА:")
    print(f"   Рассчитанный общий P&L: ${total_calculated_pnl:.10f}")
    print(f"   Ожидаемый общий P&L: ${total_expected_pnl:.10f}")
    print(f"   Расхождение: ${abs(total_calculated_pnl - total_expected_pnl):.10f}")
    
    # Проверка проценттов
    expected_percent_tp1 = 1.3980745081624124
    expected_percent_tp2 = 1.91293428212641  # из файла
    expected_percent_tp3 = 2.0845542067810876  # из файла
    
    print(f"\n📈 ПРОВЕРКА ПРОЦЕНТОВ:")
    print(f"   TP1: рассчитано {tp1_pnl_percent:.10f}%, ожидается {expected_percent_tp1:.10f}%")
    print(f"   TP2: рассчитано {tp2_pnl_percent:.10f}%, ожидается {expected_percent_tp2:.10f}%")
    print(f"   TP3: рассчитано {tp3_pnl_percent:.10f}%, ожидается {expected_percent_tp3:.10f}%")
    
    # Проверяем точность
    tolerance = 0.000000001  # 1 наноцент
    tp1_accurate = abs(tp1_pnl_usd - 1.3980745081624124) < tolerance
    tp2_accurate = abs(tp2_pnl_usd - 0.956467141063205) < tolerance
    tp3_accurate = abs(tp3_pnl_usd - 1.0422771033905438) < tolerance
    total_accurate = abs(total_calculated_pnl - total_expected_pnl) < tolerance
    
    print(f"\n✅ РЕЗУЛЬТАТЫ:")
    print(f"   TP1 точный: {tp1_accurate}")
    print(f"   TP2 точный: {tp2_accurate}")
    print(f"   TP3 точный: {tp3_accurate}")
    print(f"   Общий P&L точный: {total_accurate}")
    
    if tp1_accurate and tp2_accurate and tp3_accurate and total_accurate:
        print(f"\nВСЕ РАСЧЕТЫ P&L ТОЧНЫЕ!")
        return True
    else:
        print(f"\n❌ НАЙДЕНЫ ОШИБКИ В РАСЧЕТАХ P&L!")
        return False

if __name__ == "__main__":
    test_pnl_calculations()