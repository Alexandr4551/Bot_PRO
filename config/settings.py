# config/settings.py
"""
Конфигурация торговой системы
"""

# ===== Список криптовалют =====
SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'SOLUSDT',
    'ADAUSDT', 'AVAXUSDT', 'DOGEUSDT', 'DOTUSDT', 
    'LINKUSDT', 'LTCUSDT', 'NEARUSDT', 'ATOMUSDT', 'UNIUSDT',
    'XLMUSDT', 'HBARUSDT', 'APTUSDT', 'ARBUSDT'
    # Убрали MATICUSDT и FTMUSDT по запросу
]

# ===== Основные параметры =====
TIMEFRAMES = [15, 30]   # Основные таймфреймы
LIMIT = 500             # Количество свечей
INTERVAL_SEC = 60       # Интервал анализа (секунды)

# ===== ML модель конфигурация =====
ML_CONFIG = {
    'CONFIDENCE_THRESHOLD': 0.65,  # Порог уверенности ML
    'MODEL_PATH': 'trained_models',
    'USE_ML_SIGNALS': True,
    'FALLBACK_TO_TECHNICAL': True
}

# ===== Антиспам конфигурация =====
ANTISPAM_CONFIG = {
    'COOLDOWN_MINUTES': 3,         # Кулдаун между сигналами
    'MIN_PRICE_CHANGE_PERCENT': 0.1,  # Мин. изменение цены
    'MAX_RISK_PERCENT': 5.0,       # Макс. риск
    'MIN_RR_RATIO': 1.5,           # Мин. R/R ratio
    'TARGET_RR_RATIO': 2.5         # Целевой R/R ratio
}

# ===== Форматирование цен =====
PRICE_PRECISION = {
    'default': 5,  # Количество знаков после запятой
}