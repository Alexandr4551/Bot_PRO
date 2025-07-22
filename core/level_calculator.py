# core/level_calculator.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
"""
Умный расчет уровней стоп-лосса и тейк-профита
ИСПРАВЛЕНИЕ: Проблема одинаковых TP1 и TP2
"""

import numpy as np
import pandas as pd
import logging
from ta.volatility import BollingerBands

from config import PRICE_PRECISION

logger = logging.getLogger(__name__)

class SmartLevelCalculator:
    """Расчет уровней с правильным R/R соотношением"""
    
    @staticmethod
    def find_swing_levels(df, lookback=20):
        """Поиск swing high/low для определения уровней"""
        try:
            highs = df['high'].rolling(window=lookback, center=True).max()
            lows = df['low'].rolling(window=lookback, center=True).min()
            
            # Локальные максимумы и минимумы
            swing_highs = df[df['high'] == highs]['high'].dropna().values
            swing_lows = df[df['low'] == lows]['low'].dropna().values
            
            return swing_highs, swing_lows
        except Exception as e:
            logger.error(f"Ошибка поиска swing levels: {str(e)}")
            return np.array([]), np.array([])
    
    @staticmethod
    def calculate_psychological_levels(price, range_percent=5):
        """Расчет психологических уровней (круглые числа)"""
        levels = []
        
        try:
            # Определяем масштаб
            if price > 10000:
                round_to = 1000
            elif price > 1000:
                round_to = 100
            elif price > 100:
                round_to = 10
            elif price > 10:
                round_to = 1
            elif price > 1:
                round_to = 0.1
            else:
                round_to = 0.01
            
            # Ближайшие круглые уровни
            lower_bound = price * (1 - range_percent/100)
            upper_bound = price * (1 + range_percent/100)
            
            current = int(lower_bound / round_to) * round_to
            while current <= upper_bound:
                if lower_bound <= current <= upper_bound:
                    levels.append(current)
                current += round_to
        except Exception as e:
            logger.error(f"Ошибка расчета психологических уровней: {str(e)}")
        
        return levels
    
    @staticmethod
    def format_price(price):
        """Форматирование цены с нужной точностью"""
        try:
            # Просто округляем до 5 знаков
            return round(float(price), 5)
        except:
            return float(price)
    
    @staticmethod
    def calculate_smart_levels(signal, df, min_rr=1.5, target_rr=2.5, max_risk_percent=5.0):
        """Умный расчет уровней с ИСПРАВЛЕННОЙ логикой TP"""
        try:
            price = signal['price']
            direction = signal['direction']
            
            # ATR для базовой волатильности
            atr = df['atr'].iloc[-1] if 'atr' in df.columns and not pd.isna(df['atr'].iloc[-1]) else price * 0.02
            
            # Swing уровни
            swing_highs, swing_lows = SmartLevelCalculator.find_swing_levels(df)
            
            # Bollinger Bands для динамических уровней
            try:
                bb = BollingerBands(df['close'], window=20)
                bb_upper = bb.bollinger_hband().iloc[-1]
                bb_lower = bb.bollinger_lband().iloc[-1]
                bb_middle = bb.bollinger_mavg().iloc[-1]
            except:
                bb_upper = price * 1.02
                bb_lower = price * 0.98
                bb_middle = price
            
            # EMA уровни
            try:
                ema20 = df['close'].ewm(span=20).mean().iloc[-1]
                ema50 = df['close'].ewm(span=50).mean().iloc[-1]
            except:
                ema20 = price
                ema50 = price
            
            if direction == 'buy':
                # Поиск ближайшей поддержки для стоп-лосса
                supports = []
                
                # Добавляем swing lows
                if len(swing_lows) > 0:
                    recent_lows = swing_lows[swing_lows < price]
                    if len(recent_lows) > 0:
                        supports.extend(recent_lows[-3:])
                
                # Добавляем BB и EMA как поддержки
                if bb_lower < price:
                    supports.append(bb_lower)
                if ema20 < price:
                    supports.append(ema20)
                if ema50 < price:
                    supports.append(ema50)
                
                # Психологические уровни
                psych_levels = SmartLevelCalculator.calculate_psychological_levels(price)
                psych_supports = [lvl for lvl in psych_levels if lvl < price]
                if psych_supports:
                    supports.append(max(psych_supports))
                
                # Выбираем оптимальный стоп-лосс
                if supports:
                    supports = sorted(supports, reverse=True)
                    
                    optimal_sl = None
                    for support in supports:
                        risk_percent = ((price - support) / price) * 100
                        if 0.3 <= risk_percent <= max_risk_percent:
                            optimal_sl = support * 0.998  # Чуть ниже поддержки
                            break
                    
                    if optimal_sl is None:
                        optimal_sl = price - atr * 1.0
                else:
                    optimal_sl = price - atr * 1.0
                
                # ИСПРАВЛЕННЫЙ расчет тейк-профитов
                risk = price - optimal_sl
                
                # НОВАЯ ЛОГИКА: Равномерное распределение TP
                if min_rr >= 2.0:
                    # Если min_rr высокий, создаем логичную прогрессию
                    tp1 = price + risk * min_rr          # min_rr (например 2.0)
                    tp2 = price + risk * (min_rr + 0.75)  # min_rr + 0.75 (например 2.75) 
                    tp3 = price + risk * target_rr       # target_rr (например 3.0)
                else:
                    # Классическая логика для низких min_rr
                    tp1 = price + risk * min_rr          # 1.5
                    tp2 = price + risk * 2.0             # 2.0
                    tp3 = price + risk * target_rr       # 2.5
                
                # Проверяем сопротивления для корректировки TP
                resistances = []
                if len(swing_highs) > 0:
                    recent_highs = swing_highs[swing_highs > price]
                    if len(recent_highs) > 0:
                        resistances.extend(recent_highs[:3])
                if bb_upper > price:
                    resistances.append(bb_upper)
                
                if resistances:
                    nearest_resistance = min(resistances)
                    if tp1 > nearest_resistance:
                        # Корректируем TP уровни если они слишком агрессивные
                        tp1 = nearest_resistance * 0.998
                        tp2 = tp1 + risk * 0.3  # Небольшое увеличение
                        tp3 = tp1 + risk * 0.6  # Умеренное увеличение
                
            else:  # sell
                # Поиск ближайшего сопротивления для стоп-лосса
                resistances = []
                
                # Добавляем swing highs
                if len(swing_highs) > 0:
                    recent_highs = swing_highs[swing_highs > price]
                    if len(recent_highs) > 0:
                        resistances.extend(recent_highs[:3])
                
                # Добавляем BB и EMA как сопротивления
                if bb_upper > price:
                    resistances.append(bb_upper)
                if ema20 > price:
                    resistances.append(ema20)
                if ema50 > price:
                    resistances.append(ema50)
                
                # Психологические уровни
                psych_levels = SmartLevelCalculator.calculate_psychological_levels(price)
                psych_resistances = [lvl for lvl in psych_levels if lvl > price]
                if psych_resistances:
                    resistances.append(min(psych_resistances))
                
                # Выбираем оптимальный стоп-лосс
                if resistances:
                    resistances = sorted(resistances)
                    
                    optimal_sl = None
                    for resistance in resistances:
                        risk_percent = ((resistance - price) / price) * 100
                        if 0.3 <= risk_percent <= max_risk_percent:
                            optimal_sl = resistance * 1.002  # Чуть выше сопротивления
                            break
                    
                    if optimal_sl is None:
                        optimal_sl = price + atr * 1.0
                else:
                    optimal_sl = price + atr * 1.0
                
                # ИСПРАВЛЕННЫЙ расчет тейк-профитов для SELL
                risk = optimal_sl - price
                
                # НОВАЯ ЛОГИКА: Равномерное распределение TP для SELL
                if min_rr >= 2.0:
                    # Если min_rr высокий, создаем логичную прогрессию
                    tp1 = price - risk * min_rr          # min_rr (например 2.0)
                    tp2 = price - risk * (min_rr + 0.75)  # min_rr + 0.75 (например 2.75)
                    tp3 = price - risk * target_rr       # target_rr (например 3.0)
                else:
                    # Классическая логика для низких min_rr
                    tp1 = price - risk * min_rr          # 1.5
                    tp2 = price - risk * 2.0             # 2.0
                    tp3 = price - risk * target_rr       # 2.5
                
                # Проверяем поддержки для корректировки TP
                supports = []
                if len(swing_lows) > 0:
                    recent_lows = swing_lows[swing_lows < price]
                    if len(recent_lows) > 0:
                        supports.extend(recent_lows[-3:])
                if bb_lower < price:
                    supports.append(bb_lower)
                
                if supports:
                    nearest_support = max(supports)
                    if tp1 < nearest_support:
                        # Корректируем TP уровни если они слишком агрессивные
                        tp1 = nearest_support * 1.002
                        tp2 = tp1 - risk * 0.3  # Небольшое уменьшение
                        tp3 = tp1 - risk * 0.6  # Умеренное уменьшение
            
            # Финальная проверка R/R
            actual_risk = abs(price - optimal_sl)
            actual_reward = abs(tp1 - price)
            actual_rr = actual_reward / actual_risk if actual_risk > 0 else 0
            
            # Если R/R плохой, пропускаем сигнал
            if actual_rr < min_rr:
                logger.warning(f"Плохой R/R: {actual_rr:.2f}, сигнал пропущен")
                signal['skip_reason'] = f"Low R/R: {actual_rr:.2f}"
                return signal
            
            # ПРОВЕРКА: TP уровни должны быть разными
            if abs(tp1 - tp2) < price * 0.001:  # Менее 0.1% разница
                logger.warning(f"TP1 и TP2 слишком близко: {tp1:.5f} vs {tp2:.5f}")
                # Принудительно разводим TP уровни
                if direction == 'buy':
                    tp2 = tp1 + risk * 0.5  # Добавляем половину риска
                    tp3 = tp2 + risk * 0.5  # Еще половину риска
                else:
                    tp2 = tp1 - risk * 0.5  # Вычитаем половину риска
                    tp3 = tp2 - risk * 0.5  # Еще половину риска
            
            # Форматируем все цены с повышенной точностью
            signal['take_profit'] = [
                SmartLevelCalculator.format_price(tp1),
                SmartLevelCalculator.format_price(tp2),
                SmartLevelCalculator.format_price(tp3)
            ]
            signal['stop_loss'] = SmartLevelCalculator.format_price(optimal_sl)
            signal['risk_reward'] = actual_rr
            signal['risk_percent'] = (actual_risk / price) * 100
            
            # ФИНАЛЬНАЯ ПРОВЕРКА: Логируем уровни для отладки
            logger.debug(f"📊 {signal['symbol']} {direction.upper()}: "
                        f"Entry=${price:.5f}, SL=${optimal_sl:.5f}, "
                        f"TP1=${tp1:.5f}, TP2=${tp2:.5f}, TP3=${tp3:.5f}, "
                        f"R/R={actual_rr:.2f}")
            
            return signal
            
        except Exception as e:
            logger.error(f"Ошибка расчета умных уровней: {str(e)}")
            return signal