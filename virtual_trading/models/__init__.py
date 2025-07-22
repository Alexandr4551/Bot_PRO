# virtual_trading/models/__init__.py
"""
Модели данных для виртуального трейдера
"""

from .position import VirtualPosition
from .trade import ClosedTrade

__all__ = [
    'VirtualPosition',
    'ClosedTrade'
]