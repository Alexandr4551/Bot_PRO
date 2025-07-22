# virtual_trading/__init__.py
"""
Виртуальный трейдер для тестирования торговых сигналов
Интегрируется с существующей core/ архитектурой

АРХИТЕКТУРА:
- models/: VirtualPosition, ClosedTrade
- services/: BalanceManager, PositionManager, StatisticsCalculator, ReportGenerator  
- core/: VirtualTraderV2 (основной оркестратор)

ИНТЕГРАЦИЯ:
- config/: использует существующие ANTISPAM_CONFIG, ML_CONFIG, logging_config
- core/: использует BybitFuturesAPI, HybridTradingEngineV2, SmartTimingManager
- utils/: использует display_startup_info, TelegramBot
"""

# Основные экспорты
from .core.virtual_trader_v2 import VirtualTraderV2
from .models.position import VirtualPosition
from .models.trade import ClosedTrade

# Сервисы (для расширенного использования)
from .services.balance_manager import BalanceManager
from .services.position_manager import PositionManager
from .services.statistics_calculator import StatisticsCalculator
from .services.report_generator import ReportGenerator

__version__ = "2.0.0"
__all__ = [
    # Основной класс (для совместимости с main.py)
    'VirtualTraderV2',
    
    # Модели данных
    'VirtualPosition', 
    'ClosedTrade',
    
    # Сервисы (для продвинутого использования)
    'BalanceManager',
    'PositionManager',
    'StatisticsCalculator', 
    'ReportGenerator'
]

# Информация о интеграции с существующей системой
INTEGRATION_INFO = {
    'core_systems': ['BybitFuturesAPI', 'HybridTradingEngineV2', 'SmartTimingManager'],
    'config_systems': ['logging_config', 'ANTISPAM_CONFIG', 'ML_CONFIG', 'SYMBOLS', 'INTERVAL_SEC'],
    'utils_systems': ['display_startup_info', 'TelegramBot', 'create_telegram_bot'],
    'backwards_compatible': True,
    'original_file': 'virtual_traider.py (900 строк → 7 модулей)'
}