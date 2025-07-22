# virtual_trading/services/position_manager.py
"""
PRODUCTION-READY Position Manager V3.0
Простое управление позициями без избыточной сложности
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from ..models.position import VirtualPosition
from ..models.trade import ClosedTrade

logger = logging.getLogger('VirtualTrader.PositionManager')

class PositionManager:
    """Production-ready управление виртуальными позициями"""
    
    def __init__(self, balance_manager):
        self.balance_manager = balance_manager
        self.open_positions: Dict[str, VirtualPosition] = {}
        self.closed_trades: List[ClosedTrade] = []
        
        logger.info("[INIT] PositionManager V3.0 готов к работе")
    
    async def open_position(self, signal: Dict) -> bool:
        """Открытие позиции с простой логикой"""
        symbol = signal['symbol']
        
        # Проверки
        if symbol in self.open_positions:
            logger.debug(f"[SKIP] {symbol} уже открыт")
            return False
        
        can_open, reason = self.balance_manager.can_open_new_position(self.open_positions)
        if not can_open:
            logger.info(f"[BLOCK] {symbol}: {reason}")
            return False
        
        # Расчеты
        entry_price = signal['price']
        position_size_usd = self.balance_manager.position_size_usd
        quantity = position_size_usd / entry_price
        
        # Резервируем средства
        if not self.balance_manager.reserve_funds(position_size_usd):
            logger.error(f"[ERROR] Не удалось зарезервировать средства для {symbol}")
            return False
        
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
            timing_info=signal.get('timing_info', {})
        )
        
        self.open_positions[symbol] = position
        
        logger.info(f"[OPEN] {symbol} {signal['direction'].upper()} ${entry_price:.5f} (${position_size_usd:.0f})")
        return True
    
    async def check_position_exits(self, api) -> None:
        """Проверка закрытия позиций - упрощенная версия"""
        if not self.open_positions:
            return
        
        symbols_to_close = []
        
        for symbol, position in list(self.open_positions.items()):
            try:
                # Получаем данные
                current_data = await api.get_ohlcv(symbol, 15, 2)
                if current_data.empty:
                    continue
                
                current_price = current_data['close'].iloc[-1]
                high_price = current_data['high'].iloc[-1]
                low_price = current_data['low'].iloc[-1]
                
                # Проверяем выходы
                exit_info = self._check_exit_conditions(position, current_price, high_price, low_price)
                
                if exit_info:
                    self._close_position_partial(position, exit_info)
                    
                    # Проверяем полное закрытие
                    if position.is_fully_closed() or exit_info['reason'] == 'Stop Loss':
                        symbols_to_close.append(symbol)
            
            except Exception as e:
                logger.error(f"[ERROR] Ошибка проверки {symbol}: {e}")
        
        # Удаляем закрытые позиции
        for symbol in symbols_to_close:
            del self.open_positions[symbol]
    
    def _check_exit_conditions(self, position: VirtualPosition, current_price: float, high_price: float, low_price: float) -> Optional[Dict]:
        """Простая проверка условий выхода"""
        
        # Проверяем стоп-лосс
        if position.direction == 'buy' and low_price <= position.current_sl:
            return {
                'reason': 'Stop Loss',
                'price': position.current_sl,
                'quantity_percent': position.get_remaining_percent()
            }
        
        if position.direction == 'sell' and high_price >= position.current_sl:
            return {
                'reason': 'Stop Loss',
                'price': position.current_sl,
                'quantity_percent': position.get_remaining_percent()
            }
        
        # Проверяем тейк-профиты
        if position.direction == 'buy':
            if not position.tp1_filled and high_price >= position.tp1:
                return {'reason': 'TP1', 'price': position.tp1, 'quantity_percent': 50}
            elif position.tp1_filled and not position.tp2_filled and high_price >= position.tp2:
                return {'reason': 'TP2', 'price': position.tp2, 'quantity_percent': 25}
            elif position.tp2_filled and not position.tp3_filled and high_price >= position.tp3:
                return {'reason': 'TP3', 'price': position.tp3, 'quantity_percent': 25}
        else:  # sell
            if not position.tp1_filled and low_price <= position.tp1:
                return {'reason': 'TP1', 'price': position.tp1, 'quantity_percent': 50}
            elif position.tp1_filled and not position.tp2_filled and low_price <= position.tp2:
                return {'reason': 'TP2', 'price': position.tp2, 'quantity_percent': 25}
            elif position.tp2_filled and not position.tp3_filled and low_price <= position.tp3:
                return {'reason': 'TP3', 'price': position.tp3, 'quantity_percent': 25}
        
        return None
    
    def _close_position_partial(self, position: VirtualPosition, exit_info: Dict) -> None:
        """Частичное закрытие позиции - упрощенная версия"""
        exit_price = exit_info['price']
        quantity_percent = exit_info['quantity_percent']
        reason = exit_info['reason']
        
        # Расчеты
        quantity_to_close = position.quantity * (quantity_percent / 100)
        
        if position.direction == 'buy':
            pnl_per_unit = exit_price - position.entry_price
        else:
            pnl_per_unit = position.entry_price - exit_price
        
        pnl_usd = quantity_to_close * pnl_per_unit
        position_part_usd = self.balance_manager.position_size_usd * (quantity_percent / 100)
        pnl_percent = (pnl_usd / position_part_usd) * 100 if position_part_usd > 0 else 0
        
        # Освобождаем средства
        self.balance_manager.release_funds(position_part_usd, pnl_usd)
        position.realized_pnl += pnl_usd
        
        # Создаем сделку
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
        
        # Обновляем позицию
        if reason == 'TP1':
            position.tp1_filled = True
            position.current_sl = position.entry_price  # Перенос SL в безубыток
            position.sl_moved_to_breakeven = True
        elif reason == 'TP2':
            position.tp2_filled = True
        elif reason == 'TP3':
            position.tp3_filled = True
        
        profit_emoji = "💚" if pnl_usd > 0 else "❤️"
        logger.info(f"[CLOSE] {profit_emoji} {position.symbol} {reason}: {pnl_percent:+.1f}% (${pnl_usd:+.2f})")
    
    def get_positions_summary(self) -> Dict:
        """Краткая сводка позиций"""
        return {
            'total_positions': len(self.open_positions),
            'buy_positions': sum(1 for p in self.open_positions.values() if p.direction == 'buy'),
            'sell_positions': sum(1 for p in self.open_positions.values() if p.direction == 'sell'),
            'positions': [p.get_status_summary() for p in self.open_positions.values()]
        }
    
    def get_trades_summary(self) -> Dict:
        """Краткая сводка сделок"""
        if not self.closed_trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'win_rate': 0,
                'total_pnl': 0
            }
        
        winning_trades = [t for t in self.closed_trades if t.pnl_usd > 0]
        total_pnl = sum(t.pnl_usd for t in self.closed_trades)
        win_rate = len(winning_trades) / len(self.closed_trades) * 100
        
        return {
            'total_trades': len(self.closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(self.closed_trades) - len(winning_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'recent_trades': [t.format_summary() for t in self.closed_trades[-5:]]
        }