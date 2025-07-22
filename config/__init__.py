# config/__init__.py - ОБНОВЛЕННАЯ КОНФИГУРАЦИЯ для Этапа 1.1
"""
Конфигурация с УЖЕСТОЧЕННЫМИ параметрами
Ожидаемое улучшение: +20% винрейт
"""

# ОСНОВНЫЕ ТОРГОВЫЕ ПАРАМЕТРЫ - СТРОЖЕ
SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 
    'XRPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LINKUSDT',
    'UNIUSDT', 'LTCUSDT', 'NEARUSDT', 'ATOMUSDT', 'FILUSDT'
]

INTERVAL_SEC = 180  # Увеличиваем интервал с 120 до 180 сек (меньше шума)
LIMIT = 500  # Количество свечей для анализа

# КОНФИГУРАЦИЯ ML - УЖЕСТОЧЕННАЯ
ML_CONFIG = {
    'USE_ML_SIGNALS': True,
    'MODEL_PATH': 'trained_models',
    'CONFIDENCE_THRESHOLD': 0.75,  # ПОВЫШЕНО с 0.6 до 0.75
    'FALLBACK_TO_TECHNICAL': True,
    
    # НОВЫЕ параметры для строгого режима
    'REQUIRE_ML_AGREEMENT': True,    # Требовать согласия ML и TA
    'MIN_ML_CONFIDENCE': 0.85,       # Минимум для ML доминирования  
    'STRICT_MODE': True,             # Включить строгий режим
    'MAX_SIGNALS_PER_HOUR': 3,       # Максимум сигналов в час
}

# АНТИСПАМ КОНФИГУРАЦИЯ - ЗНАЧИТЕЛЬНО УЖЕСТОЧЕНА
ANTISPAM_CONFIG = {
    'COOLDOWN_MINUTES': 90,           # УВЕЛИЧЕНО с 60 до 90 минут
    'MIN_PRICE_CHANGE_PERCENT': 1.0,  # УВЕЛИЧЕНО с 0.5% до 1.0%
    'MIN_RR_RATIO': 2.0,              # УВЕЛИЧЕНО с 1.5 до 2.0
    'TARGET_RR_RATIO': 3.0,           # УВЕЛИЧЕНО с 2.5 до 3.0
    'MAX_RISK_PERCENT': 3.0,          # УМЕНЬШЕНО с 5% до 3%
    
    # НОВЫЕ строгие параметры
    'MAX_SIGNALS_PER_4H': 2,          # Максимум 2 сигнала за 4 часа на пару
    'MIN_CONFIDENCE_TECHNICAL': 0.75, # Минимум для чисто технических сигналов
    'MIN_CONFIDENCE_COMBINED': 0.65,  # Минимум для комбинированных
    'OPPOSITE_DIRECTION_COOLDOWN_MULTIPLIER': 2,  # x2 кулдаун для противоположного направления
}

# ТЕХНИЧЕСКИЙ АНАЛИЗ - СТРОГИЕ ПОРОГИ
TECHNICAL_CONFIG = {
    # RSI пороги - ЗНАЧИТЕЛЬНО УЖЕСТОЧЕНЫ
    'RSI_OVERSOLD_MAX': 35,      # Было нет лимита, теперь строгий лимит
    'RSI_OVERSOLD_MIN': 15,      # Минимум для покупок
    'RSI_OVERBOUGHT_MIN': 65,    # Минимум для продаж
    'RSI_OVERBOUGHT_MAX': 85,    # Максимум для продаж
    
    # Экстремальные значения для особых сигналов
    'RSI_EXTREME_OVERSOLD': 20,  # Для экстремальных сигналов
    'RSI_EXTREME_OVERBOUGHT': 80,# Для экстремальных сигналов
    
    # MACD пороги - УЖЕСТОЧЕНЫ
    'MACD_MIN_POSITIVE': 0.001,  # Минимальное положительное значение
    'MACD_MIN_NEGATIVE': -0.001, # Максимальное отрицательное значение
    
    # Bollinger Bands позиции - СТРОЖЕ
    'BB_LOWER_POSITION_MAX': 0.3, # Максимальная позиция в нижней части для покупки
    'BB_UPPER_POSITION_MIN': 0.7, # Минимальная позиция в верхней части для продажи
    
    # Требования к подтверждениям
    'MIN_TIMEFRAME_CONFIRMATIONS': 2,  # Минимум подтверждений на разных ТФ
    'MIN_CONDITIONS_MET': 5,           # Минимум условий из 7 для сигнала
    
    # Объемы
    'VOLUME_MULTIPLIER_MIN': 1.5,      # Минимум 150% от среднего объема
    
    # Моментум
    'MIN_MOMENTUM_STRENGTH': 0.01,     # Минимальная сила моментума
}

# ВРЕМЕННЫЕ ОГРАНИЧЕНИЯ - НОВЫЕ
TRADING_HOURS_CONFIG = {
    'FORBIDDEN_HOURS_UTC': [22, 23, 0, 1, 2, 6, 7, 8],  # Часы когда не торгуем
    'PREFERRED_HOURS_UTC': [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
    'HIGH_VOLATILITY_HOURS': [13, 14, 15, 16],  # Часы повышенной осторожности
}

# МУЛЬТИТАЙМФРЕЙМОВЫЙ АНАЛИЗ - НОВЫЕ ПАРАМЕТРЫ
MULTI_TF_CONFIG = {
    'TIMEFRAMES': [1, 15, 30, 60],     # Таймфреймы для анализа
    'MIN_TREND_ALIGNMENT': 2,          # Минимальное совпадение трендов
    'MIN_CONFIRMATIONS': 2,            # Минимум подтверждений
    'VOLATILITY_THRESHOLD_HIGH': 1.5,  # Порог высокой волатильности
    'VOLATILITY_THRESHOLD_LOW': 0.7,   # Порог низкой волатильности
}

# ТОЧНОСТЬ ЦЕН
PRICE_PRECISION = 5

# ЛОГИРОВАНИЕ
LOGGING_CONFIG = {
    'LEVEL': 'INFO',
    'DETAILED_SIGNAL_LOGGING': True,
    'LOG_REJECTED_SIGNALS': True,      # Логировать отклоненные сигналы
    'LOG_ANTISPAM_BLOCKS': True,       # Логировать блокировки антиспам
}

# TELEGRAM (если используется)
TELEGRAM_CONFIG = {
    'SEND_ONLY_HIGH_QUALITY': True,    # Отправлять только высококачественные сигналы
    'MIN_CONFIDENCE_TO_SEND': 0.75,    # Минимальная уверенность для отправки
    'INCLUDE_REJECTION_STATS': True,   # Включать статистику отклонений
}