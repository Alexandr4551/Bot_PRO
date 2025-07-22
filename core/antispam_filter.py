# core/antispam_filter.py - УЛУЧШЕННАЯ ВЕРСИЯ
"""
СТРОГИЙ антиспам фильтр для высококачественных сигналов
ЭТАП 1.1: Снижение количества сигналов, повышение качества
"""

import logging
from datetime import datetime, timedelta
from collections import defaultdict

from config import ANTISPAM_CONFIG

logger = logging.getLogger(__name__)

class AntiSpamFilter:
    """СТРОГАЯ фильтрация для высококачественных сигналов"""
    
    def __init__(self):
        self.last_signals = defaultdict(lambda: {'timestamp': None, 'price': 0, 'direction': None})
        self.signal_history = defaultdict(list)
        self.symbol_cooldowns = defaultdict(int)  # Счетчик неуспешных сигналов
    
    def should_send_signal(self, symbol, signal):
        """СТРОГАЯ проверка сигнала"""
        current_time = datetime.now()
        last_signal = self.last_signals[symbol]
        
        # 1. УВЕЛИЧЕННЫЙ кулдаун - больше времени между сигналами
        base_cooldown = ANTISPAM_CONFIG['COOLDOWN_MINUTES']
        
        # Динамический кулдаун: больше кулдаун после неуспешных сигналов
        cooldown_multiplier = 1 + (self.symbol_cooldowns[symbol] * 0.5)  # +50% за каждый неуспешный
        actual_cooldown = min(base_cooldown * cooldown_multiplier, 180)  # Максимум 3 часа
        
        if last_signal['timestamp']:
            time_diff = (current_time - last_signal['timestamp']).total_seconds() / 60
            if time_diff < actual_cooldown:
                logger.debug(f"🚫 {symbol}: Кулдаун активен ({time_diff:.1f}/{actual_cooldown:.1f} мин)")
                return False
        
        # 2. УВЕЛИЧЕННОЕ минимальное изменение цены
        min_price_change = ANTISPAM_CONFIG['MIN_PRICE_CHANGE_PERCENT'] * 1.5  # Увеличиваем в 1.5 раза
        
        if last_signal['price'] > 0:
            price_change = abs((signal['price'] - last_signal['price']) / last_signal['price'] * 100)
            if price_change < min_price_change:
                logger.debug(f"🚫 {symbol}: Малое изменение цены ({price_change:.2f}% < {min_price_change:.2f}%)")
                return False
        
        # 3. ЗАПРЕТ противоположных сигналов в короткий срок
        if (last_signal['direction'] and 
            last_signal['direction'] != signal['direction'] and
            last_signal['timestamp']):
            
            time_since_opposite = (current_time - last_signal['timestamp']).total_seconds() / 60
            min_opposite_time = actual_cooldown * 2  # Двойной кулдаун для противоположного направления
            
            if time_since_opposite < min_opposite_time:
                logger.debug(f"🚫 {symbol}: Слишком рано для противоположного сигнала ({time_since_opposite:.1f}/{min_opposite_time:.1f} мин)")
                return False
        
        # 4. СТРОГИЙ анализ недавней истории
        recent_history = [s for s in self.signal_history[symbol] 
                         if (current_time - s['timestamp']).total_seconds() < 14400]  # 4 часа
        
        if recent_history:
            # a) Максимум 2 сигнала за 4 часа (было без лимита)
            if len(recent_history) >= 2:
                logger.debug(f"🚫 {symbol}: Превышен лимит сигналов (2 за 4 часа)")
                return False
            
            # b) Проверяем похожие уровни - УЖЕСТОЧЕННЫЕ условия
            for hist_signal in recent_history:
                # Проверяем схожесть цен входа
                entry_price_diff = abs(signal['price'] - hist_signal['price']) / signal['price']
                if entry_price_diff < 0.01:  # Менее 1% разницы в цене входа
                    logger.debug(f"🚫 {symbol}: Слишком похожая цена входа")
                    return False
                
                # Проверяем схожесть уровней SL и TP
                if hist_signal.get('stop_loss') and hist_signal.get('take_profit'):
                    sl_diff = abs(signal.get('stop_loss', 0) - hist_signal.get('stop_loss', 0)) / signal['price']
                    
                    tp1_current = signal.get('take_profit', [0])[0] if signal.get('take_profit') else 0
                    tp1_hist = hist_signal.get('take_profit', [0])[0] if hist_signal.get('take_profit') else 0
                    tp_diff = abs(tp1_current - tp1_hist) / signal['price'] if signal['price'] > 0 else 0
                    
                    # Если и SL и TP очень похожи - это дубликат
                    if sl_diff < 0.003 and tp_diff < 0.003:  # 0.3% различие - очень строго
                        logger.debug(f"🚫 {symbol}: Повторяющийся сетап (SL: {sl_diff:.1%}, TP: {tp_diff:.1%})")
                        return False
        
        # 5. ПРОВЕРКА качества сигнала
        confidence = signal.get('confidence', 0)
        signal_type = signal.get('signal_type', '')
        
        # Минимальная уверенность для прохождения
        min_confidence = 0.65  # Повышаем с базового порога
        
        # Особые требования для разных типов сигналов
        if signal_type == 'technical_strict':
            min_confidence = 0.75  # Для чисто технических сигналов - выше порог
        elif signal_type in ['extreme_rsi_oversold', 'extreme_rsi_overbought']:
            min_confidence = 0.7   # Для RSI экстремумов - высокий порог
        
        if confidence < min_confidence:
            logger.debug(f"🚫 {symbol}: Недостаточная уверенность ({confidence:.1%} < {min_confidence:.1%})")
            return False
        
        # 6. ФИНАЛЬНАЯ проверка R/R
        if signal.get('risk_reward', 0) < 2.0:  # Требуем минимум 1:2
            logger.debug(f"🚫 {symbol}: Низкий R/R {signal.get('risk_reward', 0):.2f}")
            return False
        
        return True
    
    def register_signal(self, symbol, signal):
        """Регистрация сигнала с расширенной информацией"""
        current_time = datetime.now()
        
        self.last_signals[symbol] = {
            'timestamp': current_time,
            'price': signal['price'],
            'direction': signal['direction'],
            'confidence': signal.get('confidence', 0),
            'signal_type': signal.get('signal_type', '')
        }
        
        # Сохраняем в историю
        self.signal_history[symbol].append({
            'timestamp': current_time,
            'price': signal['price'],
            'direction': signal['direction'],
            'stop_loss': signal.get('stop_loss'),
            'take_profit': signal.get('take_profit'),
            'confidence': signal.get('confidence', 0),
            'signal_type': signal.get('signal_type', ''),
            'risk_reward': signal.get('risk_reward', 0)
        })
        
        # Очистка старой истории (оставляем только последние 24 часа)
        cutoff_time = current_time - timedelta(hours=24)
        self.signal_history[symbol] = [s for s in self.signal_history[symbol] 
                                      if s['timestamp'] > cutoff_time]
        
        logger.info(f"✅ Сигнал зарегистрирован: {symbol} {signal['direction']} "
                   f"(уверенность: {signal.get('confidence', 0):.1%}, "
                   f"тип: {signal.get('signal_type', 'unknown')})")
    
    def register_signal_failure(self, symbol):
        """Регистрация неуспешного сигнала для увеличения кулдауна"""
        self.symbol_cooldowns[symbol] += 1
        logger.debug(f"📉 Неуспешный сигнал {symbol}, счетчик: {self.symbol_cooldowns[symbol]}")
    
    def register_signal_success(self, symbol):
        """Регистрация успешного сигнала для сброса кулдауна"""
        if self.symbol_cooldowns[symbol] > 0:
            self.symbol_cooldowns[symbol] = max(0, self.symbol_cooldowns[symbol] - 1)
            logger.debug(f"📈 Успешный сигнал {symbol}, счетчик сброшен: {self.symbol_cooldowns[symbol]}")
    
    def get_symbol_stats(self, symbol):
        """Получение статистики по символу"""
        recent_signals = len([s for s in self.signal_history[symbol] 
                            if (datetime.now() - s['timestamp']).total_seconds() < 14400])
        
        return {
            'recent_signals_4h': recent_signals,
            'failure_count': self.symbol_cooldowns[symbol],
            'last_signal_time': self.last_signals[symbol]['timestamp'],
            'current_cooldown_multiplier': 1 + (self.symbol_cooldowns[symbol] * 0.5)
        }