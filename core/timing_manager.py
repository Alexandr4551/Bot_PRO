# core/timing_manager.py - НОВЫЙ МОДУЛЬ
"""
Менеджер улучшенного timing входа
ЭТАП 1.2: Ожидаемое улучшение +15% к винрейту
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class EntryTiming(Enum):
    """Типы timing для входа"""
    IMMEDIATE = "immediate"      # Немедленный вход (старый способ)
    PULLBACK = "pullback"        # Ждать pullback
    BREAKOUT = "breakout"        # Ждать пробой уровня
    VOLUME_SPIKE = "volume_spike" # Ждать всплеск объема

@dataclass
class PendingEntry:
    """Ожидающий вход"""
    symbol: str
    direction: str
    signal_price: float
    signal_time: datetime
    signal_data: dict
    
    # Timing параметры
    timing_type: EntryTiming
    target_entry_price: float = None
    max_wait_minutes: int = 60  # Максимальное время ожидания
    
    # Pullback параметры
    pullback_target: float = None  # Цена для pullback
    pullback_tolerance: float = 0.002  # 0.2% толерантность
    
    # Микро-подтверждения
    required_confirmations: int = 2
    confirmations_received: int = 0
    
    # Статус
    is_active: bool = True
    timeout_time: datetime = None
    entry_attempts: int = 0
    max_attempts: int = 3
    
    def __post_init__(self):
        if self.timeout_time is None:
            self.timeout_time = self.signal_time + timedelta(minutes=self.max_wait_minutes)

class SmartTimingManager:
    """Менеджер умного timing входа"""
    
    def __init__(self):
        self.pending_entries: Dict[str, PendingEntry] = {}
        self.entry_history: List[dict] = []
        
    def add_signal_for_timing(self, signal, timing_strategy="auto"):
        """Добавляет сигнал для обработки timing"""
        symbol = signal['symbol']
        
        # Если уже есть ожидающий вход для этого символа - отменяем старый
        if symbol in self.pending_entries:
            logger.info(f"Отменяем предыдущий ожидающий вход для {symbol}")
            del self.pending_entries[symbol]
        
        # Определяем стратегию timing
        timing_type = self._determine_timing_strategy(signal, timing_strategy)
        
        # Создаем ожидающий вход
        pending = PendingEntry(
            symbol=symbol,
            direction=signal['direction'],
            signal_price=signal['price'],
            signal_time=datetime.now(),
            signal_data=signal,
            timing_type=timing_type
        )
        
        # Настраиваем параметры в зависимости от стратегии
        self._configure_timing_parameters(pending, signal)
        
        self.pending_entries[symbol] = pending
        
        logger.info(f"🕐 Добавлен ожидающий вход: {symbol} {signal['direction']} "
                   f"(стратегия: {timing_type.value}, цель: ${pending.pullback_target:.5f})")
        
        return pending
    
    def _determine_timing_strategy(self, signal, strategy_hint):
        """Определяет оптимальную стратегию timing"""
        if strategy_hint != "auto":
            return EntryTiming(strategy_hint)
        
        # Автоматическое определение на основе сигнала
        signal_type = signal.get('signal_type', '')
        confidence = signal.get('confidence', 0)
        
        # Для ML сигналов с высокой уверенностью - ждем pullback
        if 'ml_' in signal_type and confidence > 0.8:
            return EntryTiming.PULLBACK
        
        # Для экстремальных RSI - немедленный вход
        if 'extreme_rsi' in signal_type:
            return EntryTiming.IMMEDIATE
        
        # Для строгих технических - ждем подтверждение
        if 'strict' in signal_type:
            return EntryTiming.PULLBACK
        
        # По умолчанию - pullback
        return EntryTiming.PULLBACK
    
    def _configure_timing_parameters(self, pending, signal):
        """Настраивает параметры timing"""
        if pending.timing_type == EntryTiming.IMMEDIATE:
            pending.target_entry_price = pending.signal_price
            pending.max_wait_minutes = 5  # Быстрый вход
            pending.required_confirmations = 1
            
        elif pending.timing_type == EntryTiming.PULLBACK:
            # Рассчитываем цель для pullback
            if pending.direction == 'buy':
                # Для покупки ждем откат к EMA20 или немного ниже
                pullback_distance = pending.signal_price * 0.005  # 0.5% откат
                pending.pullback_target = pending.signal_price - pullback_distance
                pending.target_entry_price = pending.pullback_target
                
            else:  # sell
                # Для продажи ждем отбой к EMA20 или немного выше
                pullback_distance = pending.signal_price * 0.005  # 0.5% отбой
                pending.pullback_target = pending.signal_price + pullback_distance
                pending.target_entry_price = pending.pullback_target
            
            pending.max_wait_minutes = 60  # Даем час на pullback
            pending.required_confirmations = 2
            
        elif pending.timing_type == EntryTiming.BREAKOUT:
            # Ждем пробой ключевого уровня
            if pending.direction == 'buy':
                pending.target_entry_price = pending.signal_price * 1.002  # +0.2%
            else:
                pending.target_entry_price = pending.signal_price * 0.998  # -0.2%
            
            pending.max_wait_minutes = 30
            pending.required_confirmations = 2
    
    async def check_pending_entries(self, api):
        """Проверяет все ожидающие входы"""
        ready_entries = []
        expired_entries = []
        
        for symbol, pending in list(self.pending_entries.items()):
            try:
                # Проверяем timeout
                if datetime.now() > pending.timeout_time:
                    expired_entries.append(symbol)
                    continue
                
                # Получаем текущие данные
                current_data = await api.get_ohlcv(symbol, 15, 5)
                if current_data.empty:
                    continue
                
                current_price = current_data['close'].iloc[-1]
                
                # Проверяем условия входа
                entry_decision = self._evaluate_entry_conditions(pending, current_data, current_price)
                
                if entry_decision['should_enter']:
                    # Обновляем цену входа
                    pending.signal_data['price'] = entry_decision['entry_price']
                    pending.signal_data['timing_info'] = {
                        'original_signal_price': pending.signal_price,
                        'timing_type': pending.timing_type.value,
                        'wait_time_minutes': (datetime.now() - pending.signal_time).total_seconds() / 60,
                        'confirmations': pending.confirmations_received,
                        'entry_reason': entry_decision['reason']
                    }
                    
                    ready_entries.append(pending.signal_data)
                    expired_entries.append(symbol)  # Удаляем из ожидающих
                    
                    logger.info(f"✅ Готов к входу: {symbol} {pending.direction} "
                               f"по ${entry_decision['entry_price']:.5f} "
                               f"(причина: {entry_decision['reason']})")
            
            except Exception as e:
                logger.error(f"Ошибка проверки ожидающего входа {symbol}: {str(e)}")
        
        # Удаляем обработанные и истекшие
        for symbol in expired_entries:
            if symbol in self.pending_entries:
                pending = self.pending_entries[symbol]
                if symbol not in [entry['symbol'] for entry in ready_entries]:
                    logger.info(f"⏰ Истек timeout для {symbol} "
                               f"(ждали {pending.timing_type.value})")
                del self.pending_entries[symbol]
        
        return ready_entries
    
    def _evaluate_entry_conditions(self, pending, current_data, current_price):
        """Оценивает условия для входа"""
        if pending.timing_type == EntryTiming.IMMEDIATE:
            return {
                'should_enter': True,
                'entry_price': current_price,
                'reason': 'immediate_entry'
            }
        
        elif pending.timing_type == EntryTiming.PULLBACK:
            return self._check_pullback_conditions(pending, current_data, current_price)
        
        elif pending.timing_type == EntryTiming.BREAKOUT:
            return self._check_breakout_conditions(pending, current_data, current_price)
        
        return {'should_enter': False, 'entry_price': current_price, 'reason': 'no_conditions'}
    
    def _check_pullback_conditions(self, pending, current_data, current_price):
        """Проверяет условия для pullback входа"""
        try:
            # Рассчитываем EMA для текущих данных
            if len(current_data) >= 20:
                ema20 = current_data['close'].ewm(span=20).mean().iloc[-1]
            else:
                ema20 = current_price
            
            # Получаем последние несколько свечей для анализа
            recent_highs = current_data['high'].tail(4).values
            recent_lows = current_data['low'].tail(4).values
            recent_volumes = current_data['volume'].tail(4).values
            recent_closes = current_data['close'].tail(4).values
            
            if pending.direction == 'buy':
                # Для покупки: ждем когда цена опустится к pullback_target
                target_reached = any(low <= pending.pullback_target * (1 + pending.pullback_tolerance) 
                                   for low in recent_lows)
                
                # Микро-подтверждения
                confirmations = 0
                
                # 1. Цена касается или пересекает EMA20
                if current_price <= ema20 * 1.003:  # В пределах 0.3% от EMA20
                    confirmations += 1
                
                # 2. Объем растет (интерес покупателей)
                if len(recent_volumes) >= 2 and recent_volumes[-1] > recent_volumes[-2]:
                    confirmations += 1
                
                # 3. Формируется разворотная свеча (зеленая после красных)
                if (len(recent_closes) >= 2 and 
                    recent_closes[-1] > recent_closes[-2] and
                    recent_closes[-2] < recent_closes[-3]):
                    confirmations += 1
                
                # 4. Цена выше минимума предыдущей свечи (нет нового минимума)
                if len(recent_lows) >= 2 and recent_lows[-1] > recent_lows[-2]:
                    confirmations += 1
                
                pending.confirmations_received = confirmations
                
                if target_reached and confirmations >= pending.required_confirmations:
                    return {
                        'should_enter': True,
                        'entry_price': current_price,
                        'reason': f'pullback_buy_confirmed_{confirmations}'
                    }
            
            else:  # sell
                # Для продажи: ждем когда цена поднимется к pullback_target
                target_reached = any(high >= pending.pullback_target * (1 - pending.pullback_tolerance)
                                   for high in recent_highs)
                
                # Микро-подтверждения для продажи
                confirmations = 0
                
                # 1. Цена касается или пересекает EMA20
                if current_price >= ema20 * 0.997:  # В пределах 0.3% от EMA20
                    confirmations += 1
                
                # 2. Объем растет (интерес продавцов)
                if len(recent_volumes) >= 2 and recent_volumes[-1] > recent_volumes[-2]:
                    confirmations += 1
                
                # 3. Формируется разворотная свеча (красная после зеленых)
                if (len(recent_closes) >= 2 and 
                    recent_closes[-1] < recent_closes[-2] and
                    recent_closes[-2] > recent_closes[-3]):
                    confirmations += 1
                
                # 4. Цена ниже максимума предыдущей свечи (нет нового максимума)
                if len(recent_highs) >= 2 and recent_highs[-1] < recent_highs[-2]:
                    confirmations += 1
                
                pending.confirmations_received = confirmations
                
                if target_reached and confirmations >= pending.required_confirmations:
                    return {
                        'should_enter': True,
                        'entry_price': current_price,
                        'reason': f'pullback_sell_confirmed_{confirmations}'
                    }
        
        except Exception as e:
            logger.error(f"Ошибка проверки pullback условий: {str(e)}")
        
        return {'should_enter': False, 'entry_price': current_price, 'reason': 'pullback_waiting'}
    
    def _check_breakout_conditions(self, pending, current_data, current_price):
        """Проверяет условия для breakout входа"""
        try:
            recent_volumes = current_data['volume'].tail(3).values
            
            if pending.direction == 'buy':
                # Пробой вверх с объемом
                price_breakout = current_price >= pending.target_entry_price
                volume_confirmation = (len(recent_volumes) >= 2 and 
                                     recent_volumes[-1] > recent_volumes[-2] * 1.2)
                
                if price_breakout and volume_confirmation:
                    return {
                        'should_enter': True,
                        'entry_price': current_price,
                        'reason': 'breakout_buy_confirmed'
                    }
            
            else:  # sell
                # Пробой вниз с объемом
                price_breakout = current_price <= pending.target_entry_price
                volume_confirmation = (len(recent_volumes) >= 2 and 
                                     recent_volumes[-1] > recent_volumes[-2] * 1.2)
                
                if price_breakout and volume_confirmation:
                    return {
                        'should_enter': True,
                        'entry_price': current_price,
                        'reason': 'breakout_sell_confirmed'
                    }
        
        except Exception as e:
            logger.error(f"Ошибка проверки breakout условий: {str(e)}")
        
        return {'should_enter': False, 'entry_price': current_price, 'reason': 'breakout_waiting'}
    
    def get_pending_status(self):
        """Получает статус всех ожидающих входов"""
        status = []
        for symbol, pending in self.pending_entries.items():
            time_waiting = (datetime.now() - pending.signal_time).total_seconds() / 60
            time_remaining = (pending.timeout_time - datetime.now()).total_seconds() / 60
            
            status.append({
                'symbol': symbol,
                'direction': pending.direction,
                'timing_type': pending.timing_type.value,
                'signal_price': pending.signal_price,
                'target_price': pending.pullback_target,
                'confirmations': f"{pending.confirmations_received}/{pending.required_confirmations}",
                'time_waiting': f"{time_waiting:.1f}min",
                'time_remaining': f"{max(0, time_remaining):.1f}min"
            })
        
        return status
    
    def cancel_pending_entry(self, symbol, reason="manual"):
        """Отменяет ожидающий вход"""
        if symbol in self.pending_entries:
            pending = self.pending_entries[symbol]
            logger.info(f"❌ Отменен ожидающий вход: {symbol} {pending.direction} "
                       f"(причина: {reason})")
            del self.pending_entries[symbol]
            return True
        return False
    
    def get_statistics(self):
        """Получает статистику по timing"""
        if not self.entry_history:
            return {}
        
        total_entries = len(self.entry_history)
        timing_types = {}
        wait_times = []
        
        for entry in self.entry_history:
            timing_type = entry.get('timing_type', 'unknown')
            timing_types[timing_type] = timing_types.get(timing_type, 0) + 1
            
            if 'wait_time_minutes' in entry:
                wait_times.append(entry['wait_time_minutes'])
        
        return {
            'total_entries': total_entries,
            'timing_distribution': timing_types,
            'average_wait_time': np.mean(wait_times) if wait_times else 0,
            'max_wait_time': max(wait_times) if wait_times else 0,
            'current_pending': len(self.pending_entries)
        }