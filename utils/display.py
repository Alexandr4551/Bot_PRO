# utils/display.py
"""
Утилиты для отображения сигналов и статистики
"""

import logging
from config import ANTISPAM_CONFIG, PRICE_PRECISION

logger = logging.getLogger(__name__)

def display_signal(signal):
    """Красивое отображение сигнала с повышенной точностью цен"""
    direction_emoji = "ПОКУПКА" if signal['direction'] == 'buy' else "ПРОДАЖА"
    
    logger.info(f"\n{'='*50}")
    logger.info(f"{direction_emoji} {signal['symbol']}")
    logger.info(f"Цена входа: ${signal['price']:.5f}")
    logger.info(f"Уверенность: {signal['confidence']:.1%}")
    logger.info(f"Тип сигнала: {signal['signal_type']}")
    
    # ML информация
    if signal['ml_prediction']:
        ml_pred = signal['ml_prediction']
        logger.info(f"ML: {ml_pred['prediction_name']} ({ml_pred['confidence']:.1%})")
    
    # Техническая информация
    tech = signal['technical_signal']
    logger.info(f"Теханализ: Тренд {tech['trend']:.1f}, RSI {tech['rsi']:.1f}, BB {tech['bb_position']:.1%}")
    
    # Уровни с повышенной точностью
    if 'take_profit' in signal:
        logger.info(f"Тейк-профиты:")
        logger.info(f"   • TP1: ${signal['take_profit'][0]:.5f} (R/R 1:{ANTISPAM_CONFIG['MIN_RR_RATIO']})")
        logger.info(f"   • TP2: ${signal['take_profit'][1]:.5f}")
        logger.info(f"   • TP3: ${signal['take_profit'][2]:.5f} (R/R 1:{ANTISPAM_CONFIG['TARGET_RR_RATIO']})")
        logger.info(f"Стоп-лосс: ${signal['stop_loss']:.5f}")
        logger.info(f"Risk/Reward: 1:{signal['risk_reward']:.2f}")
        logger.info(f"Риск: {signal['risk_percent']:.1f}%")
    
    # Обоснование
    if signal['reasoning']:
        logger.info(f"Обоснование: {'; '.join(signal['reasoning'])}")
    
    logger.info(f"{'='*50}\n")

def display_cycle_stats(analyzed_count, signals_found, cycle_time):
    """Отображение статистики цикла"""
    logger.info(f"\nСтатистика цикла:")
    logger.info(f"  • Проанализировано: {analyzed_count} монет")
    logger.info(f"  • Найдено сигналов: {signals_found}")
    logger.info(f"  • Время анализа: {cycle_time:.1f} сек")
    logger.info(f"{'='*70}")

def display_startup_info():
    """Отображение информации при запуске"""
    from config import SYMBOLS, ML_CONFIG, ANTISPAM_CONFIG
    
    logger.info("Запуск улучшенной гибридной торговой системы")
    logger.info(f"Анализируемые монеты: {len(SYMBOLS)}")
    logger.info(f"ML сигналы: {'Включены' if ML_CONFIG['USE_ML_SIGNALS'] else 'Отключены'}")
    logger.info(f"Порог уверенности: {ML_CONFIG['CONFIDENCE_THRESHOLD']:.0%}")
    logger.info(f"Кулдаун: {ANTISPAM_CONFIG['COOLDOWN_MINUTES']} минут")
    logger.info(f"Мин R/R: 1:{ANTISPAM_CONFIG['MIN_RR_RATIO']}")
    
    # ИСПРАВЛЕНО: проверяем тип PRICE_PRECISION
    try:
        if isinstance(PRICE_PRECISION, dict):
            # Если это словарь
            precision = PRICE_PRECISION.get('default', 5)
        else:
            # Если это просто число
            precision = PRICE_PRECISION
        
        logger.info(f"Точность цен: {precision} знаков")
    except Exception as e:
        logger.warning(f"Ошибка получения точности цен: {e}")
        logger.info("Точность цен: 5 знаков (по умолчанию)")