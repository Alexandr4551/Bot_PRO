# virtual_trading/services/__init__.py
"""
Сервисы для виртуального трейдера
"""

from .balance_manager import BalanceManager
from .position_manager import PositionManager
from .statistics_calculator import StatisticsCalculator
from .report_generator import ReportGenerator

__all__ = [
    'BalanceManager',
    'PositionManager', 
    'StatisticsCalculator',
    'ReportGenerator'
]