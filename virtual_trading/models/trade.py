# virtual_trading/models/trade.py
"""
Модель закрытой сделки с timing информацией
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict

@dataclass
class ClosedTrade:
    """Закрытая сделка с timing информацией"""
    symbol: str
    direction: str
    entry_price: float
    entry_time: datetime
    exit_price: float
    exit_time: datetime
    exit_reason: str
    position_size_usd: float
    quantity_closed: float
    pnl_usd: float
    pnl_percent: float
    duration_minutes: int
    timing_info: dict = None
    
    def __post_init__(self):
        if self.timing_info is None:
            self.timing_info = {}
    
    def is_profitable(self) -> bool:
        """Проверяет была ли сделка прибыльной"""
        return self.pnl_usd > 0
    
    def get_risk_reward_ratio(self) -> float:
        """Вычисляет фактическое R/R соотношение"""
        if self.exit_reason == 'Stop Loss':
            return 0.0
        
        # Для TP сделок пытаемся определить R/R
        entry_price = self.entry_price
        exit_price = self.exit_price
        
        if self.direction == 'buy':
            reward = exit_price - entry_price
            # Предполагаем SL на 1-3% ниже входа
            estimated_risk = entry_price * 0.02  # 2% предполагаемый риск
        else:
            reward = entry_price - exit_price  
            estimated_risk = entry_price * 0.02
        
        return reward / estimated_risk if estimated_risk > 0 else 0.0
    
    def get_duration_hours(self) -> float:
        """Возвращает длительность сделки в часах"""
        return self.duration_minutes / 60.0
    
    def get_exit_type(self) -> str:
        """Определяет тип выхода"""
        if 'TP1' in self.exit_reason:
            return 'TP1'
        elif 'TP2' in self.exit_reason:
            return 'TP2'
        elif 'TP3' in self.exit_reason:
            return 'TP3'
        elif 'Stop Loss' in self.exit_reason:
            return 'SL'
        else:
            return 'Other'
    
    def get_timing_type(self) -> str:
        """Возвращает тип timing использованный для входа"""
        if not self.timing_info:
            return 'immediate'
        return self.timing_info.get('timing_type', 'unknown')
    
    def get_wait_time(self) -> float:
        """Возвращает время ожидания входа в минутах"""
        if not self.timing_info:
            return 0.0
        return self.timing_info.get('wait_time_minutes', 0.0)
    
    def format_summary(self) -> str:
        """Возвращает краткое описание сделки"""
        profit_emoji = "💚" if self.is_profitable() else "❤️"
        timing_type = self.get_timing_type()
        
        return (f"{profit_emoji} {self.symbol} {self.direction.upper()} "
                f"{self.pnl_percent:+.1f}% (${self.pnl_usd:+.2f}) "
                f"{self.get_exit_type()} [{timing_type}]")
    
    def to_dict(self) -> Dict:
        """Конвертирует сделку в словарь для сохранения"""
        return {
            'symbol': self.symbol,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat() if isinstance(self.entry_time, datetime) else str(self.entry_time),
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if isinstance(self.exit_time, datetime) else str(self.exit_time),
            'exit_reason': self.exit_reason,
            'position_size_usd': self.position_size_usd,
            'quantity_closed': self.quantity_closed,
            'pnl_usd': self.pnl_usd,
            'pnl_percent': self.pnl_percent,
            'duration_minutes': self.duration_minutes,
            'timing_info': self.timing_info,
            'risk_reward': self.get_risk_reward_ratio(),
            'timing_type': self.get_timing_type(),
            'wait_time_minutes': self.get_wait_time()
        }