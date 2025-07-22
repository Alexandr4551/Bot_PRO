# virtual_trading/config.py
"""
Конфигурация виртуального трейдера V2
Расширяет существующую конфигурацию из config/
"""

import os
from typing import Dict, Any

# Интеграция с существующей конфигурацией
try:
    from config import ANTISPAM_CONFIG, ML_CONFIG, SYMBOLS, INTERVAL_SEC
    EXISTING_CONFIG_AVAILABLE = True
except ImportError:
    EXISTING_CONFIG_AVAILABLE = False
    print("[WARN] Конфигурация основной системы недоступна, используем значения по умолчанию")

# ПАРАМЕТРЫ ВИРТУАЛЬНОГО ТРЕЙДЕРА
VIRTUAL_TRADER_CONFIG = {
    # Финансовые параметры
    'initial_balance': 10000.0,          # Начальный баланс USD
    'position_size_percent': 2.0,        # Размер позиции в % от баланса
    'max_exposure_percent': 20.0,        # Максимальная экспозиция в %
    
    # Параметры риск-менеджмента
    'max_positions': 10,                 # Максимальное количество открытых позиций
    'max_daily_trades': 50,              # Максимальное количество сделок в день
    'stop_loss_percent': 2.0,            # Стандартный SL в %
    'take_profit_ratios': [1.5, 3.0, 5.0],  # R/R для TP1, TP2, TP3
    
    # Параметры частичного закрытия
    'tp1_close_percent': 50,             # Закрываем 50% на TP1
    'tp2_close_percent': 25,             # Закрываем 25% на TP2  
    'tp3_close_percent': 25,             # Закрываем 25% на TP3
    'move_sl_to_breakeven': True,        # Перенос SL в безубыток после TP1
    
    # Параметры логирования и отчетности
    'log_level': 'INFO',                 # Уровень логирования
    'results_directory': 'virtual_trading_results_v2',  # Директория результатов
    'save_stats_interval_minutes': 5,   # Интервал сохранения статистики
    'status_update_interval_seconds': 30, # Интервал обновления статуса
    
    # Параметры интеграции с timing системой
    'use_timing_system': True,           # Использовать timing для входов
    'timing_timeout_minutes': 15,        # Таймаут ожидания timing входа
    'immediate_entry_fallback': True,    # Немедленный вход при неудаче timing
    
    # Параметры блокировок
    'enable_balance_protection': True,   # Защита от торговли без средств
    'enable_exposure_limits': True,      # Ограничение экспозиции
    'min_balance_for_trading': 100.0,    # Минимальный баланс для торговли
    
    # Параметры отображения
    'show_detailed_logs': True,          # Детальные логи операций
    'show_timing_info': True,            # Информация о timing
    'console_status_line': True,         # Статусная строка в консоли
    'emoji_in_reports': True,            # Эмодзи в отчетах
}

# КОНФИГУРАЦИЯ СТАТИСТИКИ И АНАЛИТИКИ
STATISTICS_CONFIG = {
    # Метрики производительности
    'calculate_sharpe_ratio': True,      # Расчет Sharpe ratio
    'calculate_max_drawdown': True,      # Расчет максимальной просадки
    'calculate_profit_factor': True,     # Расчет profit factor
    'track_consecutive_trades': True,    # Отслеживание подряд идущих сделок
    
    # Анализ timing
    'analyze_timing_performance': True,  # Анализ эффективности timing
    'track_wait_times': True,            # Отслеживание времени ожидания
    'compare_timing_types': True,        # Сравнение типов timing
    
    # История и тренды
    'session_history_limit': 1000,      # Лимит записей истории сессии
    'keep_trade_history': True,          # Сохранение истории сделок
    'export_to_csv': False,              # Экспорт в CSV (опционально)
    'generate_charts': False,            # Генерация графиков (опционально)
}

# КОНФИГУРАЦИЯ ИНТЕГРАЦИИ
INTEGRATION_CONFIG = {
    # Совместимость с существующей системой
    'use_existing_api': True,            # Использовать существующий API
    'use_existing_logger': True,         # Использовать существующий logger
    'use_existing_telegram': True,       # Использовать существующий Telegram
    'use_existing_timing': True,         # Использовать существующий timing manager
    
    # Настройки адаптации
    'adapt_to_main_loop': True,          # Адаптация к главному циклу
    'respect_antispam_limits': True,     # Соблюдение antispam лимитов
    'inherit_symbols_config': True,      # Наследование списка символов
    'inherit_intervals': True,           # Наследование интервалов
}

# ПУТИ И ФАЙЛЫ
PATHS_CONFIG = {
    'results_base_dir': 'virtual_trading_results_v2',
    'session_stats_file': 'session_stats_v2.json',
    'trades_export_file': 'trades_export.csv',
    'positions_export_file': 'positions_export.csv',
    'performance_report_file': 'performance_report.txt',
    'logs_subdirectory': 'logs',
    'exports_subdirectory': 'exports',
}

def get_config() -> Dict[str, Any]:
    """Возвращает полную конфигурацию виртуального трейдера"""
    config = {
        'virtual_trader': VIRTUAL_TRADER_CONFIG,
        'statistics': STATISTICS_CONFIG,
        'integration': INTEGRATION_CONFIG,
        'paths': PATHS_CONFIG,
    }
    
    # Добавляем существующую конфигурацию если доступна
    if EXISTING_CONFIG_AVAILABLE:
        config['existing'] = {
            'antispam': ANTISPAM_CONFIG,
            'ml_config': ML_CONFIG,
            'symbols': SYMBOLS,
            'interval_sec': INTERVAL_SEC,
        }
    
    return config

def get_virtual_trader_params() -> Dict[str, float]:
    """Возвращает основные параметры для инициализации виртуального трейдера"""
    return {
        'initial_balance': VIRTUAL_TRADER_CONFIG['initial_balance'],
        'position_size_percent': VIRTUAL_TRADER_CONFIG['position_size_percent'],
        'max_exposure_percent': VIRTUAL_TRADER_CONFIG['max_exposure_percent'],
    }

def get_results_directory() -> str:
    """Возвращает путь к директории результатов"""
    return PATHS_CONFIG['results_base_dir']

def is_timing_enabled() -> bool:
    """Проверяет включена ли timing система"""
    return VIRTUAL_TRADER_CONFIG.get('use_timing_system', True)

def get_log_level() -> str:
    """Возвращает уровень логирования"""
    return VIRTUAL_TRADER_CONFIG.get('log_level', 'INFO')

def should_use_existing_config() -> bool:
    """Проверяет доступна ли существующая конфигурация"""
    return EXISTING_CONFIG_AVAILABLE

# Экспорт основных параметров для удобства
__all__ = [
    'VIRTUAL_TRADER_CONFIG',
    'STATISTICS_CONFIG', 
    'INTEGRATION_CONFIG',
    'PATHS_CONFIG',
    'get_config',
    'get_virtual_trader_params',
    'get_results_directory',
    'is_timing_enabled',
    'get_log_level',
    'should_use_existing_config'
]

# Валидация конфигурации
def validate_config():
    """Проверяет корректность конфигурации"""
    errors = []
    
    # Проверка финансовых параметров
    if VIRTUAL_TRADER_CONFIG['initial_balance'] <= 0:
        errors.append("initial_balance должен быть больше 0")
    
    if not (0 < VIRTUAL_TRADER_CONFIG['position_size_percent'] <= 10):
        errors.append("position_size_percent должен быть от 0 до 10%")
    
    if not (0 < VIRTUAL_TRADER_CONFIG['max_exposure_percent'] <= 100):
        errors.append("max_exposure_percent должен быть от 0 до 100%")
    
    # Проверка процентов закрытия
    total_close_percent = (VIRTUAL_TRADER_CONFIG['tp1_close_percent'] + 
                          VIRTUAL_TRADER_CONFIG['tp2_close_percent'] + 
                          VIRTUAL_TRADER_CONFIG['tp3_close_percent'])
    
    if total_close_percent != 100:
        errors.append(f"Сумма процентов закрытия должна быть 100%, получено {total_close_percent}%")
    
    if errors:
        raise ValueError("Ошибки конфигурации:\n" + "\n".join(f"- {error}" for error in errors))
    
    return True

# Автоматическая валидация при импорте
if __name__ != '__main__':
    try:
        validate_config()
    except ValueError as e:
        print(f"[ERROR] {e}")
        raise