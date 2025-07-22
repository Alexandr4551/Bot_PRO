# virtual_trading/services/position_manager.py
"""
Сервис управления виртуальными позициями
Обрабатывает открытие, закрытие и мониторинг позиций
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

# Импорты моделей
from ..models.position import VirtualPosition
from ..models.trade import ClosedTrade

logger = logging.getLogger('VirtualTrader.PositionManager')

class PositionManager:
    """Управляет виртуальными позициями и их жизненным циклом"""
    
    def __init__(self, balance_manager):
        self.balance_manager = balance_manager
        self.open_positions: Dict[str, VirtualPosition] = {}
        self.closed_trades: List[ClosedTrade] = []
        
        logger.info("[INIT] PositionManager инициализирован")
    
    async def open_position(self, signal: Dict) -> bool:
        """Открытие виртуальной позиции с timing информацией"""
        try:
            symbol = signal['symbol']
            logger.info(f"[OPEN] Попытка открыть позицию {symbol} {signal['direction'].upper()}")
            
            # Проверка на дублирование
            if symbol in self.open_positions:
                logger.warning(f"[SKIP] Позиция {symbol} уже открыта, пропускаем")
                return False
            
            # Проверка возможности открытия
            can_open, reason = self.balance_manager.can_open_new_position(self.open_positions)
            
            if not can_open:
                logger.warning(f"[BLOCK] БЛОКИРОВКА {symbol}: {reason}")
                return False
            
            # Рассчитываем количество
            entry_price = signal['price']
            position_size_usd = self.balance_manager.position_size_usd
            quantity = position_size_usd / entry_price
            
            logger.info(f"[CALC] Параметры позиции {symbol}:")
            logger.info(f"   Цена входа: ${entry_price:.5f}")
            logger.info(f"   Размер позиции: ${position_size_usd:.2f}")
            logger.info(f"   Количество: {quantity:.6f}")
            logger.info(f"   Направление: {signal['direction']}")
            
            # Резервируем средства
            if not self.balance_manager.reserve_funds(position_size_usd):
                logger.error(f"[ERROR] Не удалось зарезервировать средства для {symbol}")
                return False
            
            # Извлекаем timing информацию
            timing_info = signal.get('timing_info', {})
            if timing_info:
                logger.info(f"[TIMING] Timing информация:")
                logger.info(f"   Тип: {timing_info.get('timing_type', 'unknown')}")
                logger.info(f"   Время ожидания: {timing_info.get('wait_time_minutes', 0):.1f} мин")
                logger.info(f"   Причина входа: {timing_info.get('entry_reason', 'unknown')}")
            else:
                logger.info(f"[IMMEDIATE] Немедленный вход (без timing)")
            
            # Создаем позицию
            position = VirtualPosition(
                symbol=symbol,
                direction=signal['direction'],
                entry_price=entry_price,
                entry_time=datetime.now(),
                position_size_usd=position_size_usd,
                quantity=quantity,
                stop_loss=signal['stop_loss'],
                tp1=signal['take_profit'][0],
                tp2=signal['take_profit'][1],
                tp3=signal['take_profit'][2],
                timing_info=timing_info
            )
            
            self.open_positions[symbol] = position
            
            logger.info(f"[LEVELS] Уровни позиции {symbol}:")
            logger.info(f"   SL: ${position.stop_loss:.5f}")
            logger.info(f"   TP1: ${position.tp1:.5f} (50%)")
            logger.info(f"   TP2: ${position.tp2:.5f} (25%)")
            logger.info(f"   TP3: ${position.tp3:.5f} (25%)")
            
            logger.info(f"[SUCCESS] ПОЗИЦИЯ ОТКРЫТА: {symbol} {signal['direction'].upper()} ${entry_price:.5f}")
            return True
            
        except Exception as e:
            logger.error(f"[CRITICAL] Критическая ошибка открытия позиции {symbol}: {e}", exc_info=True)
            return False
    
    async def check_position_exits(self, api) -> None:
        """Проверка закрытия позиций"""
        if not self.open_positions:
            logger.debug("[CHECK] Нет открытых позиций для проверки")
            return
        
        logger.debug(f"[CHECK] Проверяем закрытие {len(self.open_positions)} позиций...")
        symbols_to_close = []
        
        for symbol, position in list(self.open_positions.items()):
            try:
                logger.debug(f"[CHECK] Проверяем позицию {symbol}...")
                
                # Получаем актуальные данные
                current_data = await api.get_ohlcv(symbol, 15, 5)
                if current_data.empty:
                    logger.warning(f"[DATA] Нет данных для {symbol}")
                    continue
                
                current_price = current_data['close'].iloc[-1]
                high_price = current_data['high'].iloc[-1]
                low_price = current_data['low'].iloc[-1]
                
                logger.debug(f"[PRICE] {symbol}: текущая ${current_price:.5f}, high ${high_price:.5f}, low ${low_price:.5f}")
                
                # Обновляем экстремумы
                self._update_position_extremes(position, current_price)
                
                # Проверяем условия выхода
                exit_info = self._check_exit_conditions(position, current_price, high_price, low_price)
                
                if exit_info:
                    logger.info(f"[EXIT] Найдено условие закрытия {symbol}: {exit_info['reason']} по ${exit_info['price']:.5f}")
                    await self._close_position_partial(position, exit_info)
                    
                    # Проверяем нужно ли удалить позицию полностью
                    if (position.tp1_filled and position.tp2_filled and position.tp3_filled) or exit_info['reason'] == 'Stop Loss':
                        symbols_to_close.append(symbol)
                        logger.info(f"[COMPLETE] {symbol} помечен для полного закрытия")
                else:
                    logger.debug(f"[WAIT] {symbol}: условий закрытия не найдено")
            
            except Exception as e:
                logger.error(f"[ERROR] Ошибка проверки позиции {symbol}: {e}", exc_info=True)
        
        # Удаляем полностью закрытые позиции
        for symbol in symbols_to_close:
            if symbol in self.open_positions:
                logger.info(f"[REMOVE] Удаляем полностью закрытую позицию {symbol}")
                del self.open_positions[symbol]
        
        if symbols_to_close:
            logger.info(f"[SUMMARY] Обработано закрытие {len(symbols_to_close)} позиций")
    
    def _check_exit_conditions(self, position: VirtualPosition, current_price: float, high_price: float, low_price: float) -> Optional[Dict]:
        """Проверка условий закрытия с детальным логированием"""
        logger.debug(f"[CONDITIONS] Проверяем условия выхода для {position.symbol}:")
        logger.debug(f"   Направление: {position.direction}")
        logger.debug(f"   Текущий SL: ${position.current_sl:.5f}")
        logger.debug(f"   TP статус: TP1={position.tp1_filled}, TP2={position.tp2_filled}, TP3={position.tp3_filled}")
        
        # Проверяем стоп-лосс
        if position.direction == 'buy':
            if low_price <= position.current_sl:
                remaining_percent = position.get_remaining_percent()
                
                logger.info(f"[SL] {position.symbol}: сработал STOP LOSS по ${position.current_sl:.5f} (остаток {remaining_percent}%)")
                return {
                    'reason': 'Stop Loss',
                    'price': position.current_sl,
                    'quantity_percent': remaining_percent
                }
        else:
            if high_price >= position.current_sl:
                remaining_percent = position.get_remaining_percent()
                
                logger.info(f"[SL] {position.symbol}: сработал STOP LOSS по ${position.current_sl:.5f} (остаток {remaining_percent}%)")
                return {
                    'reason': 'Stop Loss', 
                    'price': position.current_sl,
                    'quantity_percent': remaining_percent
                }
        
        # Проверяем тейк-профиты
        if position.direction == 'buy':
            if not position.tp1_filled and high_price >= position.tp1:
                logger.info(f"[TP1] {position.symbol}: достигнут TP1 ${position.tp1:.5f}")
                return {'reason': 'TP1', 'price': position.tp1, 'quantity_percent': 50}
            elif position.tp1_filled and not position.tp2_filled and high_price >= position.tp2:
                logger.info(f"[TP2] {position.symbol}: достигнут TP2 ${position.tp2:.5f}")
                return {'reason': 'TP2', 'price': position.tp2, 'quantity_percent': 25}
            elif position.tp2_filled and not position.tp3_filled and high_price >= position.tp3:
                logger.info(f"[TP3] {position.symbol}: достигнут TP3 ${position.tp3:.5f}")
                return {'reason': 'TP3', 'price': position.tp3, 'quantity_percent': 25}
        else:
            if not position.tp1_filled and low_price <= position.tp1:
                logger.info(f"[TP1] {position.symbol}: достигнут TP1 ${position.tp1:.5f}")
                return {'reason': 'TP1', 'price': position.tp1, 'quantity_percent': 50}
            elif position.tp1_filled and not position.tp2_filled and low_price <= position.tp2:
                logger.info(f"[TP2] {position.symbol}: достигнут TP2 ${position.tp2:.5f}")
                return {'reason': 'TP2', 'price': position.tp2, 'quantity_percent': 25}
            elif position.tp2_filled and not position.tp3_filled and low_price <= position.tp3:
                logger.info(f"[TP3] {position.symbol}: достигнут TP3 ${position.tp3:.5f}")
                return {'reason': 'TP3', 'price': position.tp3, 'quantity_percent': 25}
        
        logger.debug(f"[WAIT] {position.symbol}: условий закрытия не найдено")
        return None
    
    async def _close_position_partial(self, position: VirtualPosition, exit_info: Dict) -> None:
        """Частичное закрытие позиции с детальным логированием"""
        try:
            exit_price = exit_info['price']
            quantity_percent = exit_info['quantity_percent']
            reason = exit_info['reason']
            
            logger.info(f"[CLOSE] ЗАКРЫВАЕМ ПОЗИЦИЮ {position.symbol}:")
            logger.info(f"   Причина: {reason}")
            logger.info(f"   Цена закрытия: ${exit_price:.5f}")
            logger.info(f"   Процент позиции: {quantity_percent}%")
            
            # Расчеты
            quantity_to_close = position.quantity * (quantity_percent / 100)
            
            if position.direction == 'buy':
                pnl_per_unit = exit_price - position.entry_price
            else:
                pnl_per_unit = position.entry_price - exit_price
            
            pnl_usd = quantity_to_close * pnl_per_unit
            position_part_usd = self.balance_manager.position_size_usd * (quantity_percent / 100)
            pnl_percent = (pnl_usd / position_part_usd) * 100 if position_part_usd > 0 else 0
            
            logger.info(f"[PNL] Расчет P&L {position.symbol}:")
            logger.info(f"   P&L на единицу: ${pnl_per_unit:+.5f}")
            logger.info(f"   Количество к закрытию: {quantity_to_close:.6f}")
            logger.info(f"   P&L в USD: ${pnl_usd:+.2f}")
            logger.info(f"   P&L в процентах: {pnl_percent:+.2f}%")
            
            # Освобождаем средства
            self.balance_manager.release_funds(position_part_usd, pnl_usd)
            position.realized_pnl += pnl_usd
            
            # Создаем запись о закрытой сделке
            closed_trade = ClosedTrade(
                symbol=position.symbol,
                direction=position.direction,
                entry_price=position.entry_price,
                entry_time=position.entry_time,
                exit_price=exit_price,
                exit_time=datetime.now(),
                exit_reason=reason,
                position_size_usd=position_part_usd,
                quantity_closed=quantity_to_close,
                pnl_usd=pnl_usd,
                pnl_percent=pnl_percent,
                duration_minutes=int((datetime.now() - position.entry_time).total_seconds() / 60),
                timing_info=position.timing_info.copy()
            )
            
            self.closed_trades.append(closed_trade)
            logger.info(f"[TRADE] Сделка добавлена в историю, всего сделок: {len(self.closed_trades)}")
            
            # Обновляем статус позиции
            if reason == 'TP1':
                position.tp1_filled = True
                position.current_sl = position.entry_price
                position.sl_moved_to_breakeven = True
                logger.info(f"[TP1] {position.symbol}: TP1 исполнен, SL перенесен в безубыток ${position.entry_price:.5f}")
                
            elif reason == 'TP2':
                position.tp2_filled = True
                logger.info(f"[TP2] {position.symbol}: TP2 исполнен")
                
            elif reason == 'TP3':
                position.tp3_filled = True
                logger.info(f"[TP3] {position.symbol}: TP3 исполнен, позиция полностью закрыта")
                
            else:  # Stop Loss
                logger.info(f"[SL] {position.symbol}: сработал {reason}")
            
            logger.info(f"[SUCCESS] ЧАСТИЧНОЕ ЗАКРЫТИЕ ЗАВЕРШЕНО: {closed_trade.format_summary()}")
            
        except Exception as e:
            logger.error(f"[CRITICAL] Критическая ошибка закрытия позиции {position.symbol}: {e}", exc_info=True)
    
    def _update_position_extremes(self, position: VirtualPosition, current_price: float) -> None:
        """Обновление экстремумов позиции"""
        try:
            remaining_quantity = position.get_remaining_quantity()
            
            if remaining_quantity <= 0:
                logger.debug(f"[EXTREMES] {position.symbol}: позиция полностью закрыта, экстремумы не обновляются")
                return
                
            # Расчет текущего P&L
            if position.direction == 'buy':
                current_pnl = remaining_quantity * (current_price - position.entry_price)
            else:
                current_pnl = remaining_quantity * (position.entry_price - current_price)
            
            # Обновляем экстремумы
            if current_pnl > position.max_profit_usd:
                old_max = position.max_profit_usd
                position.max_profit_usd = current_pnl
                logger.debug(f"[EXTREMES] {position.symbol}: новый максимум прибыли ${current_pnl:+.2f} (было ${old_max:+.2f})")
                
            if current_pnl < position.max_loss_usd:
                old_max = position.max_loss_usd
                position.max_loss_usd = current_pnl
                logger.debug(f"[EXTREMES] {position.symbol}: новый максимум убытка ${current_pnl:+.2f} (было ${old_max:+.2f})")
                
        except Exception as e:
            logger.error(f"[ERROR] Ошибка обновления экстремумов {position.symbol}: {e}", exc_info=True)
    
    def get_positions_summary(self) -> Dict:
        """Возвращает краткую сводку по позициям"""
        if not self.open_positions:
            return {
                'total_positions': 0,
                'positions': []
            }
        
        positions_info = []
        for symbol, position in self.open_positions.items():
            positions_info.append({
                'symbol': symbol,
                'direction': position.direction,
                'entry_price': position.entry_price,
                'entry_time': position.entry_time.strftime('%H:%M:%S'),
                'remaining_percent': position.get_remaining_percent(),
                'tp1_filled': position.tp1_filled,
                'tp2_filled': position.tp2_filled,
                'tp3_filled': position.tp3_filled,
                'timing_type': position.timing_info.get('timing_type', 'immediate'),
                'status': position.get_status_summary()
            })
        
        return {
            'total_positions': len(self.open_positions),
            'positions': positions_info
        }
    
    def get_trades_summary(self) -> Dict:
        """Возвращает краткую сводку по сделкам"""
        if not self.closed_trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'trades': []
            }
        
        winning_trades = [t for t in self.closed_trades if t.pnl_usd > 0]
        losing_trades = [t for t in self.closed_trades if t.pnl_usd <= 0]
        total_pnl = sum(t.pnl_usd for t in self.closed_trades)
        win_rate = len(winning_trades) / len(self.closed_trades) * 100
        
        recent_trades = []
        for trade in self.closed_trades[-10:]:  # Последние 10 сделок
            recent_trades.append({
                'symbol': trade.symbol,
                'direction': trade.direction,
                'pnl_usd': trade.pnl_usd,
                'pnl_percent': trade.pnl_percent,
                'exit_reason': trade.exit_reason,
                'timing_type': trade.get_timing_type(),
                'summary': trade.format_summary()
            })
        
        return {
            'total_trades': len(self.closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'trades': recent_trades
        }