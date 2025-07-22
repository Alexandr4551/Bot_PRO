# core/trading_engine.py - ВЕРСИЯ С УЛУЧШЕННЫМ TIMING
"""
Гибридный торговый движок с УМНЫМ TIMING ВХОДА
ЭТАП 1.2: Ожидаемое улучшение +15% к винрейту
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, time
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange, BollingerBands

from config import ML_CONFIG, ANTISPAM_CONFIG
from .ml_predictor import MLPredictor
from .level_calculator import SmartLevelCalculator
from .antispam_filter import AntiSpamFilter
from .timing_manager import SmartTimingManager, EntryTiming

logger = logging.getLogger(__name__)

class HybridTradingEngineV2:
    """Торговый движок с ML + техническим анализом + УМНЫМ TIMING"""
    
    def __init__(self, api):
        self.api = api
        self.ml_predictor = MLPredictor()
        self.antispam = AntiSpamFilter()
        self.level_calculator = SmartLevelCalculator()
        self.timing_manager = SmartTimingManager()  # НОВЫЙ компонент
        self.ml_enabled = False
        
        # Статистика timing
        self.timing_stats = {
            'signals_generated': 0,
            'signals_pending': 0,
            'entries_executed': 0,
            'entries_timed_out': 0,
            'timing_improvement': 0
        }
        
        # Инициализация ML
        if ML_CONFIG['USE_ML_SIGNALS']:
            self.ml_enabled = self.ml_predictor.load_model()
    
    def is_trading_hours(self):
        """Проверка торговых часов"""
        current_hour = datetime.now().hour
        dangerous_hours = list(range(22, 24)) + list(range(0, 3)) + list(range(6, 9))
        return current_hour not in dangerous_hours
    
    async def analyze_and_generate_signals(self, symbols):
        """Анализирует символы и генерирует сигналы (но не входит сразу)"""
        new_signals = []
        
        # Проверяем торговые часы
        if not self.is_trading_hours():
            logger.debug(f"Торговля запрещена в текущий час: {datetime.now().hour}")
            return new_signals
        
        for symbol in symbols:
            try:
                signal = await self._analyze_single_symbol(symbol)
                if signal and signal.get('direction'):
                    self.timing_stats['signals_generated'] += 1
                    
                    # Определяем стратегию timing
                    timing_strategy = self._select_timing_strategy(signal)
                    
                    # Добавляем сигнал в менеджер timing вместо немедленного входа
                    pending = self.timing_manager.add_signal_for_timing(signal, timing_strategy)
                    self.timing_stats['signals_pending'] += 1
                    
                    logger.info(f"📊 Новый сигнал добавлен в очередь timing: {symbol} {signal['direction']} "
                               f"(стратегия: {timing_strategy}, уверенность: {signal.get('confidence', 0):.1%})")
                    
                    new_signals.append({
                        'type': 'signal_queued',
                        'signal': signal,
                        'timing_strategy': timing_strategy,
                        'pending_info': pending
                    })
            
            except Exception as e:
                logger.error(f"Ошибка анализа {symbol}: {str(e)}")
        
        return new_signals
    
    async def check_ready_entries(self):
        """Проверяет готовые к входу сигналы"""
        ready_entries = await self.timing_manager.check_pending_entries(self.api)
        processed_entries = []
        
        for entry_signal in ready_entries:
            try:
                # Повторно проверяем актуальность сигнала
                if self._validate_entry_signal(entry_signal):
                    self.timing_stats['entries_executed'] += 1
                    processed_entries.append(entry_signal)
                    
                    logger.info(f"🎯 ГОТОВ К ВХОДУ: {entry_signal['symbol']} {entry_signal['direction']} "
                               f"по ${entry_signal['price']:.5f} "
                               f"(timing: {entry_signal.get('timing_info', {}).get('timing_type', 'unknown')})")
                else:
                    logger.warning(f"⚠️ Сигнал {entry_signal['symbol']} устарел при проверке входа")
            
            except Exception as e:
                logger.error(f"Ошибка обработки готового входа {entry_signal.get('symbol', 'unknown')}: {str(e)}")
        
        return processed_entries
    
    def _select_timing_strategy(self, signal):
        """Выбирает оптимальную стратегию timing для сигнала"""
        signal_type = signal.get('signal_type', '')
        confidence = signal.get('confidence', 0)
        rsi = signal.get('technical_signal', {}).get('rsi', 50)
        
        # Экстремальные RSI сигналы - немедленный вход (рынок может быстро развернуться)
        if 'extreme_rsi' in signal_type:
            return EntryTiming.IMMEDIATE.value
        
        # Высокоуверенные ML сигналы - ждем pullback для лучшей цены
        if confidence > 0.85 and 'ml_' in signal_type:
            return EntryTiming.PULLBACK.value
        
        # Пробойные сигналы - ждем подтверждение пробоя
        if ('breakout' in signal_type or 
            (signal['direction'] == 'buy' and rsi > 60) or
            (signal['direction'] == 'sell' and rsi < 40)):
            return EntryTiming.BREAKOUT.value
        
        # По умолчанию - pullback (самая консервативная стратегия)
        return EntryTiming.PULLBACK.value
    
    def _validate_entry_signal(self, signal):
        """Проверяет актуальность сигнала перед входом"""
        try:
            timing_info = signal.get('timing_info', {})
            wait_time = timing_info.get('wait_time_minutes', 0)
            
            # Если ждали слишком долго - сигнал может быть неактуален
            if wait_time > 90:  # Больше 1.5 часов
                logger.debug(f"Сигнал {signal['symbol']} устарел (ждали {wait_time:.1f} мин)")
                return False
            
            # Проверяем что цена не ушла слишком далеко от первоначального сигнала
            original_price = timing_info.get('original_signal_price', signal['price'])
            current_price = signal['price']
            price_deviation = abs(current_price - original_price) / original_price
            
            # Максимальное отклонение 2%
            if price_deviation > 0.02:
                logger.debug(f"Цена {signal['symbol']} слишком отклонилась: {price_deviation:.1%}")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"Ошибка валидации сигнала: {str(e)}")
            return False
    
    async def _analyze_single_symbol(self, symbol):
        """Анализ одного символа (копия из предыдущей версии с небольшими улучшениями)"""
        try:
            # Сбор данных
            from config import LIMIT
            data_1m = await self.api.get_ohlcv(symbol, 1, min(LIMIT, 100))
            data_15m = await self.api.get_ohlcv(symbol, 15, LIMIT)
            data_30m = await self.api.get_ohlcv(symbol, 30, LIMIT)
            data_1h = await self.api.get_ohlcv(symbol, 60, min(LIMIT//2, 200))
            
            if data_15m.empty or data_30m.empty:
                return None
            
            # Генерация технических индикаторов
            data_1m = self.generate_technical_indicators(data_1m) if not data_1m.empty else pd.DataFrame()
            data_15m = self.generate_technical_indicators(data_15m)
            data_30m = self.generate_technical_indicators(data_30m)
            data_1h = self.generate_technical_indicators(data_1h) if not data_1h.empty else pd.DataFrame()
            
            # Текущая цена
            current_price = await self.api.get_current_price(symbol)
            if current_price <= 0:
                return None
            
            # Фильтр объемов
            if not self.check_volume_filter(data_15m):
                return None
            
            # ML предсказание
            ml_prediction = None
            if self.ml_enabled:
                ml_prediction = self.ml_predictor.predict(data_15m)
            
            # Технический анализ
            multi_tf_analysis = self.analyze_multiple_timeframes(data_1m, data_15m, data_30m, data_1h)
            technical_signal = self.generate_strict_technical_signal(data_15m, multi_tf_analysis)
            
            # Комбинированный сигнал
            combined_signal = self.combine_signals_strict(
                symbol=symbol,
                ml_prediction=ml_prediction,
                technical_signal=technical_signal,
                multi_tf_analysis=multi_tf_analysis,
                current_price=current_price,
                data_15m=data_15m
            )
            
            return combined_signal
            
        except Exception as e:
            logger.error(f"Ошибка анализа {symbol}: {str(e)}")
            return None
    
    # Методы из предыдущей версии (копируем без изменений)
    def check_volume_filter(self, df):
        """Строгий фильтр объемов"""
        if df.empty or len(df) < 20:
            return False
        
        try:
            current_volume = df['volume'].iloc[-1]
            avg_volume_20 = df['volume'].rolling(20).mean().iloc[-1]
            volume_ratio = current_volume / avg_volume_20 if avg_volume_20 > 0 else 0
            return volume_ratio >= 1.5
        except:
            return False
    
    def analyze_multiple_timeframes(self, data_1m, data_15m, data_30m, data_1h):
        """Анализ множественных таймфреймов"""
        analysis = {
            'trend_alignment': 0,
            'momentum_strength': 0,
            'volatility_regime': 'normal',
            'confirmation_count': 0
        }
        
        try:
            timeframes = [('1m', data_1m), ('15m', data_15m), ('30m', data_30m), ('1h', data_1h)]
            trend_scores = []
            momentum_scores = []
            
            for tf_name, df in timeframes:
                if df.empty or len(df) < 50:
                    continue
                
                try:
                    ema20 = df['ema20'].iloc[-1]
                    ema50 = df['ema50'].iloc[-1]
                    close = df['close'].iloc[-1]
                    
                    if pd.isna(ema20) or pd.isna(ema50):
                        continue
                    
                    if ema20 > ema50 * 1.005 and close > ema20:
                        trend_scores.append(1)
                    elif ema20 < ema50 * 0.995 and close < ema20:
                        trend_scores.append(-1)
                    else:
                        trend_scores.append(0)
                    
                    macd_hist = df['macd_hist'].iloc[-1] if 'macd_hist' in df.columns else 0
                    if not pd.isna(macd_hist):
                        momentum_scores.append(abs(macd_hist))
                
                except:
                    continue
            
            if trend_scores:
                analysis['trend_alignment'] = sum(trend_scores)
                analysis['confirmation_count'] = len([t for t in trend_scores if abs(t) > 0])
            
            if momentum_scores:
                analysis['momentum_strength'] = np.mean(momentum_scores)
            
            # Режим волатильности
            if not data_15m.empty and 'atr' in data_15m.columns:
                current_atr = data_15m['atr'].iloc[-1]
                avg_atr = data_15m['atr'].rolling(50).mean().iloc[-1]
                
                if not pd.isna(current_atr) and not pd.isna(avg_atr) and avg_atr > 0:
                    atr_ratio = current_atr / avg_atr
                    if atr_ratio > 1.5:
                        analysis['volatility_regime'] = 'high'
                    elif atr_ratio < 0.7:
                        analysis['volatility_regime'] = 'low'
        
        except Exception as e:
            logger.error(f"Ошибка мультитаймфреймового анализа: {str(e)}")
        
        return analysis
    
    def generate_strict_technical_signal(self, df_15m, multi_tf_analysis):
        """Строгий технический анализ"""
        try:
            if df_15m.empty or len(df_15m) < 50:
                return {'direction': None, 'strength': 0, 'reason': 'insufficient_data'}
            
            last_data = df_15m.iloc[-1]
            
            rsi = last_data.get('rsi', 50.0)
            macd_hist = last_data.get('macd_hist', 0.0)
            bb_upper = last_data.get('bb_upper', last_data['close'] * 1.02)
            bb_lower = last_data.get('bb_lower', last_data['close'] * 0.98)
            close = last_data['close']
            ema20 = last_data.get('ema20', close)
            ema50 = last_data.get('ema50', close)
            
            for var in [rsi, macd_hist, ema20, ema50]:
                if pd.isna(var):
                    return {'direction': None, 'strength': 0, 'reason': 'nan_indicators'}
            
            bb_position = (close - bb_lower) / (bb_upper - bb_lower) if (bb_upper != bb_lower) else 0.5
            
            if multi_tf_analysis['volatility_regime'] == 'high':
                return {'direction': None, 'strength': 0, 'reason': 'high_volatility'}
            
            # СТРОГИЕ CONDITIONS FOR BUY
            buy_conditions = [
                15 <= rsi <= 35,
                multi_tf_analysis['trend_alignment'] >= 2,
                multi_tf_analysis['confirmation_count'] >= 2,
                macd_hist > 0.001,
                bb_position <= 0.3,
                close > ema20 * 0.998,
                ema20 >= ema50 * 0.999,
                multi_tf_analysis['momentum_strength'] >= 0.01
            ]
            
            # СТРОГИЕ CONDITIONS FOR SELL  
            sell_conditions = [
                65 <= rsi <= 85,
                multi_tf_analysis['trend_alignment'] <= -2,
                multi_tf_analysis['confirmation_count'] >= 2,
                macd_hist < -0.001,
                bb_position >= 0.7,
                close < ema20 * 1.002,
                ema20 <= ema50 * 1.001,
                multi_tf_analysis['momentum_strength'] >= 0.01
            ]
            
            buy_score = sum(buy_conditions)
            sell_score = sum(sell_conditions)
            min_conditions = 5
            
            if buy_score >= min_conditions:
                return {
                    'direction': 'buy',
                    'strength': min(buy_score / 7.0 + 0.3, 1.0),
                    'reason': f'strict_buy_{buy_score}/7',
                    'rsi': rsi,
                    'macd_hist': macd_hist,
                    'bb_position': bb_position,
                    'tf_alignment': multi_tf_analysis['trend_alignment'],
                    'conditions_met': buy_score
                }
            
            elif sell_score >= min_conditions:
                return {
                    'direction': 'sell',
                    'strength': min(sell_score / 7.0 + 0.3, 1.0),
                    'reason': f'strict_sell_{sell_score}/7',
                    'rsi': rsi,
                    'macd_hist': macd_hist,
                    'bb_position': bb_position,
                    'tf_alignment': multi_tf_analysis['trend_alignment'],
                    'conditions_met': sell_score
                }
            
            else:
                return {
                    'direction': None,
                    'strength': 0,
                    'reason': f'insufficient_conditions_buy_{buy_score}_sell_{sell_score}',
                    'rsi': rsi,
                    'macd_hist': macd_hist,
                    'bb_position': bb_position,
                    'tf_alignment': multi_tf_analysis['trend_alignment']
                }
        
        except Exception as e:
            logger.error(f"Ошибка строгого технического анализа: {str(e)}")
            return {
                'direction': None,
                'strength': 0,
                'reason': f'error_{str(e)[:50]}',
                'rsi': 50.0,
                'macd_hist': 0.0,
                'bb_position': 0.5,
                'tf_alignment': 0
            }
    
    def combine_signals_strict(self, symbol, ml_prediction, technical_signal, multi_tf_analysis, current_price, data_15m):
        """Строгое комбинирование сигналов"""
        signal = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'price': current_price,
            'direction': None,
            'confidence': 0,
            'signal_type': 'none',
            'ml_prediction': ml_prediction,
            'technical_signal': technical_signal,
            'multi_tf_analysis': multi_tf_analysis,
            'reasoning': []
        }
        
        ml_direction = None
        ml_confidence = 0
        
        if ml_prediction and self.ml_enabled:
            ml_direction = ml_prediction.get('direction')
            ml_confidence = ml_prediction.get('confidence', 0)
        
        tech_direction = technical_signal.get('direction')
        tech_confidence = technical_signal.get('strength', 0)
        
        # Строгая логика комбинирования
        if (ml_direction and tech_direction == ml_direction and 
            ml_confidence > ML_CONFIG['CONFIDENCE_THRESHOLD'] and
            tech_confidence >= 0.7):
            
            signal['direction'] = ml_direction
            signal['confidence'] = min(ml_confidence * 0.6 + tech_confidence * 0.4, 0.98)
            signal['signal_type'] = 'ml_tech_perfect_alignment'
            signal['reasoning'].append(f"ИДЕАЛЬНОЕ СОВПАДЕНИЕ: ML({ml_confidence:.1%}) + ТА({tech_confidence:.1%})")
            
        elif (ml_direction and ml_confidence > 0.85 and
              multi_tf_analysis['confirmation_count'] >= 2):
            
            signal['direction'] = ml_direction  
            signal['confidence'] = ml_confidence * 0.9
            signal['signal_type'] = 'ml_high_confidence'
            signal['reasoning'].append(f"ML высокая уверенность: {ml_confidence:.1%}")
            
        elif (tech_direction and tech_confidence >= 0.8 and
              ML_CONFIG['FALLBACK_TO_TECHNICAL'] and
              multi_tf_analysis['confirmation_count'] >= 3):
            
            signal['direction'] = tech_direction
            signal['confidence'] = min(tech_confidence * 0.7 + 0.1, 0.8)
            signal['signal_type'] = 'technical_strict'
            signal['reasoning'].append(f"СТРОГИЙ ТА: {tech_confidence:.1%}")
        
        elif not signal['direction']:
            rsi = technical_signal.get('rsi', 50.0)
            tf_alignment = multi_tf_analysis['trend_alignment']
            
            if (rsi < 20 and tf_alignment >= 1 and 
                multi_tf_analysis['momentum_strength'] > 0.02):
                signal['direction'] = 'buy'
                signal['confidence'] = 0.65
                signal['signal_type'] = 'extreme_rsi_oversold'
                signal['reasoning'].append(f"Экстремальная перепроданность: RSI {rsi:.1f}")
                
            elif (rsi > 80 and tf_alignment <= -1 and 
                  multi_tf_analysis['momentum_strength'] > 0.02):
                signal['direction'] = 'sell'
                signal['confidence'] = 0.65
                signal['signal_type'] = 'extreme_rsi_overbought'  
                signal['reasoning'].append(f"Экстремальная перекупленность: RSI {rsi:.1f}")
        
        # Добавляем умные уровни если есть сигнал
        if signal['direction']:
            signal = self.level_calculator.calculate_smart_levels(
                signal, 
                data_15m,
                min_rr=2.0,
                target_rr=3.0,
                max_risk_percent=3.0
            )
            
            # Проверка антиспам фильтра
            if not signal.get('skip_reason'):
                if self.antispam.should_send_signal(symbol, signal):
                    self.antispam.register_signal(symbol, signal)
                else:
                    signal['direction'] = None
                    signal['reasoning'].append("Заблокирован антиспам фильтром")
            else:
                signal['direction'] = None
        
        return signal
    
    def generate_technical_indicators(self, df):
        """Генерация технических индикаторов"""
        if len(df) < 50:
            return df
        
        try:
            try:
                df['rsi'] = RSIIndicator(df['close'], window=14).rsi()
            except:
                df['rsi'] = 50.0
                
            try:
                df['ema20'] = EMAIndicator(df['close'], window=20).ema_indicator()
                df['ema50'] = EMAIndicator(df['close'], window=50).ema_indicator()
            except:
                df['ema20'] = df['close']
                df['ema50'] = df['close']
            
            try:
                macd = MACD(df['close'])
                df['macd'] = macd.macd()
                df['macd_signal'] = macd.macd_signal()
                df['macd_hist'] = df['macd'] - df['macd_signal']
            except:
                df['macd'] = 0.0
                df['macd_signal'] = 0.0  
                df['macd_hist'] = 0.0
            
            try:
                df['atr'] = AverageTrueRange(df['high'], df['low'], df['close']).average_true_range()
            except:
                df['atr'] = df['close'] * 0.02
            
            try:
                bb = BollingerBands(df['close'], window=20)
                df['bb_upper'] = bb.bollinger_hband()
                df['bb_middle'] = bb.bollinger_mavg()
                df['bb_lower'] = bb.bollinger_lband()
            except:
                df['bb_upper'] = df['close'] * 1.02
                df['bb_middle'] = df['close']
                df['bb_lower'] = df['close'] * 0.98
            
        except Exception as e:
            logger.error(f"Ошибка генерации технических индикаторов: {str(e)}")
        
        return df
    
    def get_timing_status(self):
        """Получает статус timing системы"""
        pending_status = self.timing_manager.get_pending_status()
        timing_stats = self.timing_manager.get_statistics()
        
        return {
            'pending_entries': pending_status,
            'timing_statistics': timing_stats,
            'system_stats': self.timing_stats
        }
    
    def get_detailed_status(self):
        """Получает детальный статус всей системы"""
        return {
            'timing_status': self.get_timing_status(),
            'ml_enabled': self.ml_enabled,
            'current_time': datetime.now().isoformat(),
            'trading_hours_active': self.is_trading_hours(),
            'system_statistics': self.timing_stats
        }