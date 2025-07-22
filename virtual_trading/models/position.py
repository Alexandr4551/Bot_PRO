# virtual_trading/models/position.py
"""
Модель виртуальной торговой позиции с timing информацией
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict

@dataclass
class VirtualPosition:
    """Виртуальная торговая позиция с timing информацией"""
    symbol: str
    direction: str
    entry_price: float
    entry_time: datetime
    position_size_usd: float
    quantity: float
    
    # Уровни
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    
    # Исполнение
    tp1_filled: bool = False
    tp2_filled: bool = False
    tp3_filled: bool = False
    sl_moved_to_breakeven: bool = False
    
    # Статистика
    current_sl: float = None
    max_profit_usd: float = 0.0
    max_loss_usd: float = 0.0
    
    # Timing информация
    timing_info: dict = None
    
    # Отслеживание частичных закрытий
    remaining_quantity: float = None
    realized_pnl: float = 0.0
    
    def __post_init__(self):
        if self.current_sl is None:
            self.current_sl = self.stop_loss
        if self.remaining_quantity is None:
            self.remaining_quantity = self.quantity
        if self.timing_info is None:
            self.timing_info = {}
    
    def get_remaining_quantity(self) -> float:
        """Вычисляет оставшееся количество с учетом частичных закрытий"""
        remaining = self.quantity
        if self.tp1_filled:
            remaining -= self.quantity * 0.5
        if self.tp2_filled:
            remaining -= self.quantity * 0.25
        if self.tp3_filled:
            remaining -= self.quantity * 0.25
        return max(0, remaining)
    
    def get_remaining_percent(self) -> int:
        """Возвращает оставшийся процент позиции"""
        percent = 100
        if self.tp1_filled:
            percent -= 50
        if self.tp2_filled:
            percent -= 25
        if self.tp3_filled:
            percent -= 25
        return max(0, percent)
    
    def is_fully_closed(self) -> bool:
        """Проверяет полностью ли закрыта позиция"""
        return self.tp1_filled and self.tp2_filled and self.tp3_filled
    
    def get_status_summary(self) -> str:
        """Возвращает краткую информацию о статусе позиции"""
        status = f"{self.symbol} {self.direction.upper()}"
        if self.tp1_filled:
            status += " TP1✓"
        if self.tp2_filled:
            status += " TP2✓"
        if self.tp3_filled:
            status += " TP3✓"
        if self.sl_moved_to_breakeven:
            status += " SL→BE"
        
        remaining = self.get_remaining_percent()
        if remaining > 0:
            status += f" ({remaining}% остается)"
        
        return status