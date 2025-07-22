# virtual_traider.py - ПОЛНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ
"""
Виртуальный трейдер с улучшенным timing входа + ДЕТАЛЬНЫЕ ЛОГИ
ЭТАП 1.2: Ожидаемое улучшение +15% к винрейту
"""

import asyncio
import json
import logging
import time
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import signal
import sys

# НОВОЕ: Настройка детального логирования
def setup_detailed_logging():
    """Настройка детального логирования для виртуального трейдера"""
    
    # Создаем директорию для логов
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Настройка форматирования
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)-15s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Основной логгер
    logger = logging.getLogger('VirtualTrader')
    logger.setLevel(logging.DEBUG)
    
    # Убираем старые обработчики
    logger.handlers.clear()
    
    # 1. Консольный вывод (INFO и выше)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # 2. Детальный файл лог (DEBUG и выше)
    session_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    detailed_file_handler = logging.FileHandler(
        f'{log_dir}/virtual_trader_detailed_{session_time}.log', 
        encoding='utf-8'
    )
    detailed_file_handler.setLevel(logging.DEBUG)
    detailed_file_handler.setFormatter(detailed_formatter)
    logger.addHandler(detailed_file_handler)
    
    # 3. Файл только для торговых операций (INFO и выше)
    trading_file_handler = logging.FileHandler(
        f'{log_dir}/virtual_trader_trading_{session_time}.log', 
        encoding='utf-8'
    )
    trading_file_handler.setLevel(logging.INFO)
    trading_file_handler.setFormatter(detailed_formatter)
    logger.addHandler(trading_file_handler)
    
    # 4. Файл ошибок (WARNING и выше)
    error_file_handler = logging.FileHandler(
        f'{log_dir}/virtual_trader_errors_{session_time}.log', 
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.WARNING)
    error_file_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_file_handler)
    
    # Настраиваем логгеры для других модулей
    modules_to_log = ['core.trading_engine', 'core.timing_manager', 'core.bybit_api', 'core.ml_predictor']
    for module_name in modules_to_log:
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(logging.DEBUG)
        # Они будут использовать обработчики родительского логгера
        module_logger.propagate = True
    
    # Подавляем избыточное логирование от некоторых библиотек
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    logger.info("="*70)
    logger.info("🚀 СИСТЕМА ЛОГИРОВАНИЯ ВИРТУАЛЬНОГО ТРЕЙДЕРА ИНИЦИАЛИЗИРОВАНА")
    logger.info(f"📁 Логи сохраняются в директорию: {os.path.abspath(log_dir)}/")
    logger.info(f"📋 Детальный лог: virtual_trader_detailed_{session_time}.log")
    logger.info(f"💼 Торговые операции: virtual_trader_trading_{session_time}.log") 
    logger.info(f"⚠️ Ошибки: virtual_trader_errors_{session_time}.log")
    logger.info("="*70)
    
    return logger

# Импорты для торговой системы
from config import SYMBOLS, INTERVAL_SEC
from core import BybitFuturesAPI
from core.trading_engine import HybridTradingEngineV2
from utils import display_startup_info

# ИНИЦИАЛИЗИРУЕМ ЛОГИРОВАНИЕ В НАЧАЛЕ
logger = setup_detailed_logging()

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

class VirtualTraderV2:
    """Виртуальный трейдер для новой TIMING системы с детальным логированием"""
    
    def __init__(self, initial_balance=10000.0, position_size_percent=2.0, max_exposure_percent=20.0):
        logger.info("🏗️ Инициализация виртуального трейдера V2...")
        
        # Базовые параметры
        self.initial_balance = initial_balance
        self.available_balance = initial_balance
        self.position_size_percent = position_size_percent
        self.position_size_usd = initial_balance * (position_size_percent / 100)
        self.max_exposure_percent = max_exposure_percent
        self.max_exposure_usd = initial_balance * (max_exposure_percent / 100)
        
        logger.info(f"💰 Настройки баланса:")
        logger.info(f"   Начальный баланс: ${self.initial_balance:,.2f}")
        logger.info(f"   Размер позиции: {self.position_size_percent}% (${self.position_size_usd:,.0f})")
        logger.info(f"   Максимальная экспозиция: {self.max_exposure_percent}% (${self.max_exposure_usd:,.0f})")
        
        # Позиции и история
        self.open_positions: Dict[str, VirtualPosition] = {}
        self.closed_trades: List[ClosedTrade] = []
        
        # Статистика
        self.start_time = datetime.now()
        self.total_signals = 0
        self.total_trades_opened = 0
        self.blocked_by_exposure = 0
        self.blocked_by_balance = 0
        
        # Статистика для timing
        self.timing_stats = {
            'signals_queued': 0,
            'entries_from_timing': 0,
            'timing_timeouts': 0,
            'average_wait_time': 0,
            'immediate_entries': 0
        }
        
        # Сохранение статистики
        self.last_stats_save = None
        self.stats_save_interval = 300
        
        # Результаты
        self.results_dir = "virtual_trading_results_v2"
        os.makedirs(self.results_dir, exist_ok=True)
        
        # История для полной статистики
        self.session_history = []
        
        # Флаг для корректного завершения
        self.is_running = True
        self.setup_signal_handlers()
        
        # Последний статус timing для отображения
        self.last_timing_status = {}
        
        logger.info(f"📁 Результаты будут сохраняться в: {os.path.abspath(self.results_dir)}/")
        logger.info("✅ Виртуальный трейдер инициализирован успешно")
    
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""
        def signal_handler(signum, frame):
            logger.warning(f"🛑 Получен сигнал завершения {signum}")
            print(f"\n🛑 Получен сигнал {signum}. Завершение работы...")
            self.is_running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.debug("🔧 Обработчики сигналов настроены")
    
    def get_invested_capital(self):
        """Расчет инвестированного капитала"""
        total_invested = 0
        for position in self.open_positions.values():
            remaining_percent = 100
            if position.tp1_filled:
                remaining_percent -= 50
            if position.tp2_filled:
                remaining_percent -= 25
            if position.tp3_filled:
                remaining_percent -= 25
            
            if remaining_percent > 0:
                total_invested += self.position_size_usd * (remaining_percent / 100)
        
        logger.debug(f"💼 Инвестированный капитал: ${total_invested:,.2f}")
        return total_invested
    
    def get_current_balance(self, current_prices=None):
        """Расчет текущего баланса"""
        invested_capital = self.get_invested_capital()
        unrealized_pnl = self.get_unrealized_pnl(current_prices)
        total_balance = self.available_balance + invested_capital + unrealized_pnl
        
        logger.debug(f"💰 Компоненты баланса: доступно ${self.available_balance:,.2f} + "
                    f"инвестировано ${invested_capital:,.2f} + нереализ. ${unrealized_pnl:+,.2f} = "
                    f"итого ${total_balance:,.2f}")
        
        return total_balance
    
    def get_unrealized_pnl(self, current_prices=None):
        """Расчет нереализованной прибыли"""
        if not current_prices:
            logger.debug("📊 Текущие цены не предоставлены, нереализованный P&L = 0")
            return 0.0
            
        total_unrealized_pnl = 0.0
        
        for symbol, position in self.open_positions.items():
            if symbol not in current_prices:
                logger.debug(f"⚠️ Нет текущей цены для {symbol}")
                continue
                
            current_price = current_prices[symbol]
            
            remaining_quantity = position.quantity
            if position.tp1_filled:
                remaining_quantity -= position.quantity * 0.5
            if position.tp2_filled:
                remaining_quantity -= position.quantity * 0.25
            if position.tp3_filled:
                remaining_quantity -= position.quantity * 0.25
            
            if remaining_quantity <= 0:
                logger.debug(f"📊 {symbol}: позиция полностью закрыта")
                continue
                
            if position.direction == 'buy':
                unrealized_pnl = remaining_quantity * (current_price - position.entry_price)
            else:
                unrealized_pnl = remaining_quantity * (position.entry_price - current_price)
            
            logger.debug(f"📊 {symbol}: нереализ. P&L ${unrealized_pnl:+.2f} "
                        f"(цена ${current_price:.5f}, вход ${position.entry_price:.5f}, "
                        f"остаток {remaining_quantity:.6f})")
            
            total_unrealized_pnl += unrealized_pnl
            
        logger.debug(f"📊 Общий нереализованный P&L: ${total_unrealized_pnl:+,.2f}")
        return total_unrealized_pnl
    
    def can_open_new_position(self):
        """Проверка возможности открытия новой позиции"""
        if self.available_balance < self.position_size_usd:
            logger.warning(f"🚫 Недостаточно средств: доступно ${self.available_balance:.2f}, "
                          f"нужно ${self.position_size_usd:.2f}")
            return False, "insufficient_balance"
        
        current_invested = self.get_invested_capital()
        would_be_invested = current_invested + self.position_size_usd
        
        if would_be_invested > self.max_exposure_usd:
            logger.warning(f"🚫 Превышен лимит экспозиции: текущая ${current_invested:.2f} + "
                          f"новая ${self.position_size_usd:.2f} = ${would_be_invested:.2f} > "
                          f"лимит ${self.max_exposure_usd:.2f}")
            return False, "exposure_limit"
        
        logger.debug(f"✅ Можно открыть позицию: доступно ${self.available_balance:.2f}, "
                    f"экспозиция будет ${would_be_invested:.2f}/{self.max_exposure_usd:.2f}")
        return True, "ok"
    
    async def log_status(self, api=None, engine=None):
        """Логирование статуса с информацией о timing"""
        try:
            # Получаем текущие цены для расчета нереализованного P&L
            current_prices = {}
            if api and self.open_positions:
                logger.debug(f"📡 Получаем текущие цены для {len(self.open_positions)} позиций...")
                for symbol in self.open_positions.keys():
                    try:
                        current_data = await api.get_ohlcv(symbol, 15, 1)
                        if not current_data.empty:
                            current_prices[symbol] = current_data['close'].iloc[-1]
                            logger.debug(f"📡 {symbol}: ${current_data['close'].iloc[-1]:.5f}")
                    except Exception as e:
                        logger.debug(f"⚠️ Не удалось получить цену {symbol}: {e}")
            
            # Рассчитываем все балансы
            invested_capital = self.get_invested_capital()
            unrealized_pnl = self.get_unrealized_pnl(current_prices)
            current_balance = self.get_current_balance(current_prices)
            
            exposure_percent = (invested_capital / self.initial_balance) * 100
            balance_change = current_balance - self.initial_balance
            balance_percent = (balance_change / self.initial_balance) * 100
            
            # Получаем статус timing системы
            timing_status = ""
            if engine:
                try:
                    timing_info = engine.get_timing_status()
                    pending_count = len(timing_info.get('pending_entries', []))
                    
                    if pending_count > 0:
                        timing_status = f" | ⏳ Ожидающих: {pending_count}"
                        logger.debug(f"⏳ Ожидающих timing входов: {pending_count}")
                    
                    self.last_timing_status = timing_info
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка получения timing статуса: {e}")
            
            # Формируем статус
            unrealized_status = f" | Нереализ. P&L: ${unrealized_pnl:+.2f}" if unrealized_pnl != 0 else ""
            
            status = (f"💰 Баланс: ${current_balance:,.2f} ({balance_percent:+.2f}%){unrealized_status} | "
                     f"Доступно: ${self.available_balance:,.2f} | "
                     f"Инвестировано: ${invested_capital:,.0f} ({exposure_percent:.1f}%) | "
                     f"Позиций: {len(self.open_positions)} | Сделок: {len(self.closed_trades)}{timing_status}")
            
            print(f"\r🤖 ВИРТУАЛЬНЫЙ ТРЕЙДЕР V2 | ⏰ {datetime.now().strftime('%H:%M:%S')} | {status}", end="", flush=True)
            
            # Добавляем запись в историю сессии
            session_record = {
                'timestamp': datetime.now().isoformat(),
                'total_balance': current_balance,
                'available_balance': self.available_balance,
                'invested_capital': invested_capital,
                'unrealized_pnl': unrealized_pnl,
                'balance_percent': balance_percent,
                'open_positions_count': len(self.open_positions),
                'closed_trades_count': len(self.closed_trades),
                'exposure_percent': exposure_percent,
                'total_signals': self.total_signals,
                'blocked_by_exposure': self.blocked_by_exposure,
                'blocked_by_balance': self.blocked_by_balance,
                'timing_stats': self.timing_stats.copy()
            }
            
            self.session_history.append(session_record)
            logger.debug(f"📊 История обновлена, записей: {len(self.session_history)}")
            
            self.check_and_save_periodic_stats()
            
        except Exception as e:
            logger.error(f"💥 Ошибка в log_status: {e}", exc_info=True)
    
    def check_and_save_periodic_stats(self):
        """Периодическое сохранение статистики"""
        try:
            now = datetime.now()
            
            if (self.last_stats_save is None or 
                (now - self.last_stats_save).total_seconds() >= self.stats_save_interval):
                
                logger.debug(f"💾 Время сохранить периодическую статистику...")
                self.save_periodic_stats()
                self.last_stats_save = now
                logger.info(f"💾 Периодическая статистика сохранена")
                
        except Exception as e:
            logger.error(f"💥 Ошибка периодического сохранения: {e}", exc_info=True)
    
    def save_periodic_stats(self):
        """Сохранение статистики"""
        try:
            stats = self.calculate_statistics()
            stats['session_history'] = self.session_history
            stats['timing_status'] = self.last_timing_status
            
            stats_file = f"{self.results_dir}/session_stats_v2.json"
            
            # Безопасная сериализация
            def safe_serialize(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                elif hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                return obj
            
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False, default=safe_serialize)
            
            logger.debug(f"💾 Статистика сохранена в {stats_file}: {len(self.session_history)} записей")
            
        except Exception as e:
            logger.error(f"💥 Ошибка сохранения статистики: {e}", exc_info=True)
    
    async def open_virtual_position(self, signal):
        """Открытие виртуальной позиции с timing информацией"""
        try:
            symbol = signal['symbol']
            logger.info(f"📈 Попытка открыть позицию {symbol} {signal['direction'].upper()}")
            
            if symbol in self.open_positions:
                logger.warning(f"⚠️ Позиция {symbol} уже открыта, пропускаем")
                return
            
            can_open, reason = self.can_open_new_position()
            
            if not can_open:
                if reason == "insufficient_balance":
                    self.blocked_by_balance += 1
                    logger.warning(f"🚫 БЛОКИРОВКА {symbol}: недостаточно средств")
                    print(f"\n🚫 НЕДОСТАТОЧНО СРЕДСТВ: {symbol}")
                elif reason == "exposure_limit":
                    self.blocked_by_exposure += 1
                    logger.warning(f"🚫 БЛОКИРОВКА {symbol}: превышен лимит экспозиции")
                    print(f"\n🚫 ЛИМИТ ЭКСПОЗИЦИИ: {symbol}")
                return
            
            # Рассчитываем количество
            entry_price = signal['price']
            quantity = self.position_size_usd / entry_price
            
            logger.info(f"💼 Параметры позиции {symbol}:")
            logger.info(f"   Цена входа: ${entry_price:.5f}")
            logger.info(f"   Размер позиции: ${self.position_size_usd:.2f}")
            logger.info(f"   Количество: {quantity:.6f}")
            logger.info(f"   Направление: {signal['direction']}")
            
            # Резервируем средства
            old_balance = self.available_balance
            self.available_balance -= self.position_size_usd
            logger.info(f"💰 Баланс изменен: ${old_balance:.2f} → ${self.available_balance:.2f} "
                       f"(резерв ${self.position_size_usd:.2f})")
            
            # Извлекаем timing информацию
            timing_info = signal.get('timing_info', {})
            if timing_info:
                logger.info(f"⏰ Timing информация:")
                logger.info(f"   Тип: {timing_info.get('timing_type', 'unknown')}")
                logger.info(f"   Время ожидания: {timing_info.get('wait_time_minutes', 0):.1f} мин")
                logger.info(f"   Причина входа: {timing_info.get('entry_reason', 'unknown')}")
            else:
                logger.info(f"⚡ Немедленный вход (без timing)")
            
            # Создаем позицию
            position = VirtualPosition(
                symbol=symbol,
                direction=signal['direction'],
                entry_price=entry_price,
                entry_time=datetime.now(),
                position_size_usd=self.position_size_usd,
                quantity=quantity,
                stop_loss=signal['stop_loss'],
                tp1=signal['take_profit'][0],
                tp2=signal['take_profit'][1],
                tp3=signal['take_profit'][2],
                timing_info=timing_info
            )
            
            self.open_positions[symbol] = position
            self.total_trades_opened += 1
            
            logger.info(f"🎯 Уровни позиции {symbol}:")
            logger.info(f"   SL: ${position.stop_loss:.5f}")
            logger.info(f"   TP1: ${position.tp1:.5f} (50%)")
            logger.info(f"   TP2: ${position.tp2:.5f} (25%)")
            logger.info(f"   TP3: ${position.tp3:.5f} (25%)")
            
            # Статистика timing
            if timing_info:
                self.timing_stats['entries_from_timing'] += 1
                wait_time = timing_info.get('wait_time_minutes', 0)
                if wait_time > 0:
                    current_avg = self.timing_stats['average_wait_time']
                    count = self.timing_stats['entries_from_timing']
                    self.timing_stats['average_wait_time'] = ((current_avg * (count - 1)) + wait_time) / count
                logger.debug(f"📊 Статистика timing обновлена: входов {self.timing_stats['entries_from_timing']}")
            else:
                self.timing_stats['immediate_entries'] += 1
                logger.debug(f"📊 Статистика немедленных входов: {self.timing_stats['immediate_entries']}")
            
            # Улучшенное логирование с timing информацией
            timing_text = ""
            if timing_info:
                timing_type = timing_info.get('timing_type', 'unknown')
                wait_time = timing_info.get('wait_time_minutes', 0)
                entry_reason = timing_info.get('entry_reason', 'unknown')
                timing_text = f" [Timing: {timing_type}, ждали {wait_time:.1f}мин, причина: {entry_reason}]"
            
            success_msg = (f"📈 ОТКРЫЛ: {symbol} {signal['direction'].upper()} ${entry_price:.5f} "
                          f"(${self.position_size_usd}, {quantity:.6f}){timing_text}")
            
            print(f"\n{success_msg}")
            print(f"   SL: ${position.stop_loss:.5f} | TP1: ${position.tp1:.5f} | "
                  f"TP2: ${position.tp2:.5f} | TP3: ${position.tp3:.5f}")
            print(f"   Доступный баланс: ${self.available_balance:.2f}")
            
            logger.info(f"✅ ПОЗИЦИЯ ОТКРЫТА УСПЕШНО: {success_msg}")
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка открытия позиции {symbol}: {e}", exc_info=True)
    
    async def check_position_exits(self, api):
        """Проверка закрытия позиций"""
        if not self.open_positions:
            logger.debug("📊 Нет открытых позиций для проверки")
            return
        
        logger.debug(f"🔍 Проверяем закрытие {len(self.open_positions)} позиций...")
        symbols_to_close = []
        
        for symbol, position in self.open_positions.items():
            try:
                logger.debug(f"🔍 Проверяем позицию {symbol}...")
                
                current_data = await api.get_ohlcv(symbol, 15, 5)
                if current_data.empty:
                    logger.warning(f"⚠️ Нет данных для {symbol}")
                    continue
                
                current_price = current_data['close'].iloc[-1]
                high_price = current_data['high'].iloc[-1]
                low_price = current_data['low'].iloc[-1]
                
                logger.debug(f"📊 {symbol}: цена ${current_price:.5f}, максимум ${high_price:.5f}, минимум ${low_price:.5f}")
                
                self._update_position_extremes(position, current_price)
                
                exit_info = self._check_exit_conditions(position, current_price, high_price, low_price)
                
                if exit_info:
                    logger.info(f"🎯 Найдено условие закрытия {symbol}: {exit_info['reason']} по ${exit_info['price']:.5f}")
                    await self._close_position_partial(position, exit_info)
                    
                    if (position.tp1_filled and position.tp2_filled and position.tp3_filled) or exit_info['reason'] == 'Stop Loss':
                        symbols_to_close.append(symbol)
                        logger.info(f"📝 {symbol} помечен для полного закрытия")
                else:
                    logger.debug(f"⏸️ {symbol}: условий закрытия не найдено")
            
            except Exception as e:
                logger.error(f"💥 Ошибка проверки позиции {symbol}: {e}", exc_info=True)
        
        # Удаляем полностью закрытые позиции
        for symbol in symbols_to_close:
            if symbol in self.open_positions:
                logger.info(f"🗑️ Удаляем полностью закрытую позицию {symbol}")
                del self.open_positions[symbol]
        
        if symbols_to_close:
            logger.info(f"✅ Обработано закрытие {len(symbols_to_close)} позиций")
    
    def _check_exit_conditions(self, position, current_price, high_price, low_price):
        """Проверка условий закрытия с логированием"""
        logger.debug(f"🔍 Проверяем условия выхода для {position.symbol}:")
        logger.debug(f"   Направление: {position.direction}")
        logger.debug(f"   Текущий SL: ${position.current_sl:.5f}")
        logger.debug(f"   TP статус: TP1={position.tp1_filled}, TP2={position.tp2_filled}, TP3={position.tp3_filled}")
        
        # Проверяем стоп-лосс
        if position.direction == 'buy':
            if low_price <= position.current_sl:
                remaining_percent = 100
                if position.tp1_filled:
                    remaining_percent -= 50
                if position.tp2_filled:
                    remaining_percent -= 25
                if position.tp3_filled:
                    remaining_percent -= 25
                
                logger.info(f"🛑 {position.symbol}: сработал STOP LOSS по ${position.current_sl:.5f} (остаток {remaining_percent}%)")
                return {
                    'reason': 'Stop Loss',
                    'price': position.current_sl,
                    'quantity_percent': remaining_percent
                }
        else:
            if high_price >= position.current_sl:
                remaining_percent = 100
                if position.tp1_filled:
                    remaining_percent -= 50
                if position.tp2_filled:
                    remaining_percent -= 25
                if position.tp3_filled:
                    remaining_percent -= 25
                
                logger.info(f"🛑 {position.symbol}: сработал STOP LOSS по ${position.current_sl:.5f} (остаток {remaining_percent}%)")
                return {
                    'reason': 'Stop Loss', 
                    'price': position.current_sl,
                    'quantity_percent': remaining_percent
                }
        
        # Проверяем тейк-профиты
        if position.direction == 'buy':
            if not position.tp1_filled and high_price >= position.tp1:
                logger.info(f"💰 {position.symbol}: достигнут TP1 ${position.tp1:.5f}")
                return {'reason': 'TP1', 'price': position.tp1, 'quantity_percent': 50}
            elif position.tp1_filled and not position.tp2_filled and high_price >= position.tp2:
                logger.info(f"💰 {position.symbol}: достигнут TP2 ${position.tp2:.5f}")
                return {'reason': 'TP2', 'price': position.tp2, 'quantity_percent': 25}
            elif position.tp2_filled and not position.tp3_filled and high_price >= position.tp3:
                logger.info(f"🎉 {position.symbol}: достигнут TP3 ${position.tp3:.5f}")
                return {'reason': 'TP3', 'price': position.tp3, 'quantity_percent': 25}
        else:
            if not position.tp1_filled and low_price <= position.tp1:
                logger.info(f"💰 {position.symbol}: достигнут TP1 ${position.tp1:.5f}")
                return {'reason': 'TP1', 'price': position.tp1, 'quantity_percent': 50}
            elif position.tp1_filled and not position.tp2_filled and low_price <= position.tp2:
                logger.info(f"💰 {position.symbol}: достигнут TP2 ${position.tp2:.5f}")
                return {'reason': 'TP2', 'price': position.tp2, 'quantity_percent': 25}
            elif position.tp2_filled and not position.tp3_filled and low_price <= position.tp3:
                logger.info(f"🎉 {position.symbol}: достигнут TP3 ${position.tp3:.5f}")
                return {'reason': 'TP3', 'price': position.tp3, 'quantity_percent': 25}
        
        logger.debug(f"⏸️ {position.symbol}: условий закрытия не найдено")
        return None
    
    async def _close_position_partial(self, position, exit_info):
        """Частичное закрытие позиции с детальным логированием"""
        try:
            exit_price = exit_info['price']
            quantity_percent = exit_info['quantity_percent']
            reason = exit_info['reason']
            
            logger.info(f"💼 ЗАКРЫВАЕМ ПОЗИЦИЮ {position.symbol}:")
            logger.info(f"   Причина: {reason}")
            logger.info(f"   Цена закрытия: ${exit_price:.5f}")
            logger.info(f"   Процент позиции: {quantity_percent}%")
            
            quantity_to_close = position.quantity * (quantity_percent / 100)
            
            if position.direction == 'buy':
                pnl_per_unit = exit_price - position.entry_price
            else:
                pnl_per_unit = position.entry_price - exit_price
            
            pnl_usd = quantity_to_close * pnl_per_unit
            position_part_usd = self.position_size_usd * (quantity_percent / 100)
            pnl_percent = (pnl_usd / position_part_usd) * 100
            
            logger.info(f"💰 Расчет P&L {position.symbol}:")
            logger.info(f"   P&L на единицу: ${pnl_per_unit:+.5f}")
            logger.info(f"   Количество к закрытию: {quantity_to_close:.6f}")
            logger.info(f"   P&L в USD: ${pnl_usd:+.2f}")
            logger.info(f"   P&L в процентах: {pnl_percent:+.2f}%")
            
            old_balance = self.available_balance
            self.available_balance += position_part_usd + pnl_usd
            position.realized_pnl += pnl_usd
            
            logger.info(f"💰 Баланс обновлен: ${old_balance:.2f} + ${position_part_usd:.2f} + ${pnl_usd:+.2f} = ${self.available_balance:.2f}")
            
            # Создаем запись о закрытой сделке с timing информацией
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
                timing_info=position.timing_info
            )
            
            self.closed_trades.append(closed_trade)
            logger.info(f"📝 Сделка добавлена в историю, всего сделок: {len(self.closed_trades)}")
            
            # Обновляем статус позиции и выводим результат
            if reason == 'TP1':
                position.tp1_filled = True
                position.current_sl = position.entry_price
                position.sl_moved_to_breakeven = True
                logger.info(f"🎯 {position.symbol}: TP1 исполнен, SL перенесен в безубыток ${position.entry_price:.5f}")
                print(f"\n💰 {reason}: {position.symbol} 50% закрыто {pnl_percent:+.2f}% (${pnl_usd:+.2f}) | SL→безубыток")
            elif reason == 'TP2':
                position.tp2_filled = True
                logger.info(f"🎯 {position.symbol}: TP2 исполнен")
                print(f"\n💰 {reason}: {position.symbol} 25% закрыто {pnl_percent:+.2f}% (${pnl_usd:+.2f})")
            elif reason == 'TP3':
                position.tp3_filled = True
                logger.info(f"🎉 {position.symbol}: TP3 исполнен, позиция полностью закрыта")
                print(f"\n🎉 {reason}: {position.symbol} 25% закрыто {pnl_percent:+.2f}% (${pnl_usd:+.2f}) | Позиция закрыта")
            else:
                logger.info(f"🛑 {position.symbol}: сработал {reason}")
                print(f"\n📉 {reason}: {position.symbol} закрыто {pnl_percent:+.2f}% (${pnl_usd:+.2f})")
            
            print(f"   Доступный баланс: ${self.available_balance:.2f}")
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка закрытия позиции {position.symbol}: {e}", exc_info=True)
    
    def _update_position_extremes(self, position, current_price):
        """Обновление экстремумов с логированием"""
        try:
            remaining_quantity = position.quantity
            if position.tp1_filled:
                remaining_quantity -= position.quantity * 0.5
            if position.tp2_filled:
                remaining_quantity -= position.quantity * 0.25
            if position.tp3_filled:
                remaining_quantity -= position.quantity * 0.25
            
            if remaining_quantity <= 0:
                logger.debug(f"📊 {position.symbol}: позиция полностью закрыта, экстремумы не обновляются")
                return
                
            if position.direction == 'buy':
                current_pnl = remaining_quantity * (current_price - position.entry_price)
            else:
                current_pnl = remaining_quantity * (position.entry_price - current_price)
            
            old_max_profit = position.max_profit_usd
            old_max_loss = position.max_loss_usd
            
            if current_pnl > position.max_profit_usd:
                position.max_profit_usd = current_pnl
                logger.debug(f"📊 {position.symbol}: новый максимум прибыли ${current_pnl:+.2f} (было ${old_max_profit:+.2f})")
            if current_pnl < position.max_loss_usd:
                position.max_loss_usd = current_pnl
                logger.debug(f"📊 {position.symbol}: новый максимум убытка ${current_pnl:+.2f} (было ${old_max_loss:+.2f})")
                
        except Exception as e:
            logger.error(f"💥 Ошибка обновления экстремумов {position.symbol}: {e}", exc_info=True)
    
    def calculate_statistics(self, current_prices=None):
        """Расчет статистики с логированием"""
        logger.debug("📊 Рассчитываем статистику...")
        
        try:
            # Базовая статистика
            session_duration = (datetime.now() - self.start_time).total_seconds() / 3600 if self.start_time else 0
            current_balance = self.get_current_balance(current_prices)
            unrealized_pnl = self.get_unrealized_pnl(current_prices)
            
            # Анализ сделок
            total_trades = len(self.closed_trades)
            winning_trades = [t for t in self.closed_trades if t.pnl_usd > 0]
            losing_trades = [t for t in self.closed_trades if t.pnl_usd < 0]
            
            win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
            total_pnl = sum([t.pnl_usd for t in self.closed_trades])
            
            logger.debug(f"📊 Базовая статистика: сделок {total_trades}, винрейт {win_rate:.1f}%, P&L ${total_pnl:+.2f}")
            
            # Анализ timing статистики
            timing_analysis = {
                'entries_from_timing': self.timing_stats['entries_from_timing'],
                'immediate_entries': self.timing_stats['immediate_entries'], 
                'average_wait_time_minutes': self.timing_stats['average_wait_time'],
                'timing_usage_rate': (self.timing_stats['entries_from_timing'] / max(1, self.total_trades_opened)) * 100
            }
            
            logger.debug(f"⏰ Timing статистика: через timing {timing_analysis['entries_from_timing']}, "
                        f"немедленно {timing_analysis['immediate_entries']}")
            
            # Анализ по типам timing для закрытых сделок
            timing_performance = {}
            for trade in self.closed_trades:
                if trade.timing_info:
                    timing_type = trade.timing_info.get('timing_type', 'unknown')
                    if timing_type not in timing_performance:
                        timing_performance[timing_type] = {
                            'count': 0,
                            'total_pnl': 0,
                            'wins': 0,
                            'average_wait_time': 0
                        }
                    
                    timing_performance[timing_type]['count'] += 1
                    timing_performance[timing_type]['total_pnl'] += trade.pnl_usd
                    if trade.pnl_usd > 0:
                        timing_performance[timing_type]['wins'] += 1
                    
                    wait_time = trade.timing_info.get('wait_time_minutes', 0)
                    timing_performance[timing_type]['average_wait_time'] += wait_time
            
            # Рассчитываем средние значения
            for timing_type, stats in timing_performance.items():
                if stats['count'] > 0:
                    stats['win_rate'] = (stats['wins'] / stats['count']) * 100
                    stats['average_pnl'] = stats['total_pnl'] / stats['count']
                    stats['average_wait_time'] = stats['average_wait_time'] / stats['count']
            
            return {
                'session_duration_hours': session_duration,
                'initial_balance': self.initial_balance,
                'current_balance': current_balance,
                'total_pnl': total_pnl,
                'unrealized_pnl': unrealized_pnl,
                'balance_change_percent': (current_balance - self.initial_balance) / self.initial_balance * 100,
                'total_trades': total_trades,
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': win_rate,
                'open_positions': len(self.open_positions),
                'blocked_by_balance': self.blocked_by_balance,
                'blocked_by_exposure': self.blocked_by_exposure,
                'timing_analysis': timing_analysis,
                'timing_performance_by_type': timing_performance,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"💥 Ошибка расчета статистики: {e}", exc_info=True)
            return {}
    
    def print_timing_status(self):
        """Печать статуса timing системы"""
        try:
            if self.last_timing_status:
                pending_entries = self.last_timing_status.get('pending_entries', [])
                
                if pending_entries:
                    print(f"\n⏳ ОЖИДАЮЩИЕ ВХОДЫ ({len(pending_entries)}):")
                    logger.info(f"⏳ Ожидающие входы: {len(pending_entries)}")
                    
                    for entry in pending_entries:
                        entry_info = (f"   {entry['symbol']} {entry['direction'].upper()} "
                                     f"| Стратегия: {entry['timing_type']} "
                                     f"| Ждем: {entry['time_waiting']} "
                                     f"| Осталось: {entry['time_remaining']} "
                                     f"| Подтв.: {entry['confirmations']}")
                        print(entry_info)
                        logger.info(entry_info)
                else:
                    print(f"\n⏳ Ожидающих timing входов нет")
                    logger.info("⏳ Нет ожидающих timing входов")
            else:
                print(f"\n⏳ Статус timing системы недоступен")
                logger.debug("⏳ Статус timing системы недоступен")
            
            # Статистика timing
            print(f"\n📊 TIMING СТАТИСТИКА:")
            print(f"   Входов через timing: {self.timing_stats['entries_from_timing']}")
            print(f"   Немедленных входов: {self.timing_stats['immediate_entries']}")
            print(f"   Среднее время ожидания: {self.timing_stats['average_wait_time']:.1f} мин")
            
            success_rate = 0
            total_attempts = self.timing_stats['entries_from_timing'] + self.timing_stats['immediate_entries']
            if total_attempts > 0:
                success_rate = (self.timing_stats['entries_from_timing'] / total_attempts) * 100
            print(f"   Использование timing: {success_rate:.1f}%")
            
            logger.info(f"📊 Timing статистика: через timing {self.timing_stats['entries_from_timing']}, "
                       f"немедленно {self.timing_stats['immediate_entries']}, "
                       f"использование {success_rate:.1f}%")
                       
        except Exception as e:
            logger.error(f"💥 Ошибка печати timing статуса: {e}", exc_info=True)
            print(f"⚠️ Ошибка отображения timing статуса: {e}")
    
    def save_results(self):
        """Сохранение результатов торговли"""
        try:
            logger.info("💾 Сохранение финальных результатов...")
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Рассчитываем статистику
            stats = self.calculate_statistics()
            stats['session_history'] = self.session_history
            stats['timing_status'] = self.last_timing_status
            stats['save_reason'] = 'final_results'
            
            # Убеждаемся что директория существует
            os.makedirs(self.results_dir, exist_ok=True)
            
            # Сохраняем основную статистику
            stats_file = f"{self.results_dir}/final_statistics_{timestamp}.json"
            
            # Безопасная сериализация
            def safe_serialize(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                elif hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                return obj
            
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False, default=safe_serialize)
            
            logger.info(f"✅ Основная статистика: {stats_file}")
            print(f"\n💾 Статистика сохранена: {os.path.abspath(stats_file)}")
            
            # Сохраняем историю сделок
            if self.closed_trades:
                trades_file = f"{self.results_dir}/closed_trades_{timestamp}.json"
                trades_data = []
                
                for trade in self.closed_trades:
                    trade_dict = asdict(trade)
                    # Конвертируем datetime в строки
                    for key, value in trade_dict.items():
                        if isinstance(value, datetime):
                            trade_dict[key] = value.isoformat()
                    trades_data.append(trade_dict)
                
                with open(trades_file, 'w', encoding='utf-8') as f:
                    json.dump(trades_data, f, indent=2, ensure_ascii=False, default=safe_serialize)
                
                logger.info(f"✅ Сделки сохранены: {trades_file} ({len(self.closed_trades)} сделок)")
                print(f"💼 Сделки: {os.path.abspath(trades_file)}")
            
            # Сохраняем открытые позиции
            if self.open_positions:
                positions_file = f"{self.results_dir}/open_positions_{timestamp}.json"
                positions_data = []
                
                for position in self.open_positions.values():
                    pos_dict = asdict(position)
                    # Конвертируем datetime в строки
                    for key, value in pos_dict.items():
                        if isinstance(value, datetime):
                            pos_dict[key] = value.isoformat()
                    positions_data.append(pos_dict)
                
                with open(positions_file, 'w', encoding='utf-8') as f:
                    json.dump(positions_data, f, indent=2, ensure_ascii=False, default=safe_serialize)
                
                logger.info(f"✅ Позиции сохранены: {positions_file} ({len(self.open_positions)} позиций)")
                print(f"📊 Позиции: {os.path.abspath(positions_file)}")
            
            # Создаем текстовый отчет
            try:
                report_file = f"{self.results_dir}/final_report_{timestamp}.txt"
                self.create_text_report(stats, report_file)
                logger.info(f"✅ Отчет создан: {report_file}")
                print(f"📋 Отчет: {os.path.abspath(report_file)}")
            except Exception as e:
                logger.error(f"❌ Ошибка создания отчета: {e}")
            
            return stats_file
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка сохранения: {e}", exc_info=True)
            print(f"💥 ОШИБКА СОХРАНЕНИЯ: {e}")
            return None
    
    def create_text_report(self, stats, filename):
        """Создание текстового отчета"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write("        ОТЧЕТ ВИРТУАЛЬНОГО ТРЕЙДЕРА V2 С TIMING\n")
                f.write("="*80 + "\n\n")
                
                # Время сохранения
                f.write(f"Отчет создан: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Причина сохранения: {stats.get('save_reason', 'unknown')}\n\n")
                
                # Основная статистика
                f.write("💰 ФИНАНСОВЫЕ РЕЗУЛЬТАТЫ:\n")
                f.write("-" * 50 + "\n")
                f.write(f"Начальный баланс:      ${self.initial_balance:,.2f}\n")
                f.write(f"Текущий баланс:        ${stats.get('current_balance', 0):,.2f}\n")
                f.write(f"Общий P&L:             ${stats.get('total_pnl', 0):+,.2f}\n")
                f.write(f"P&L в процентах:       {stats.get('balance_change_percent', 0):+.2f}%\n")
                f.write(f"Нереализованный P&L:   ${stats.get('unrealized_pnl', 0):+,.2f}\n\n")
                
                # Торговая статистика
                f.write("📊 ТОРГОВАЯ СТАТИСТИКА:\n")
                f.write("-" * 50 + "\n")
                f.write(f"Всего сделок:          {stats.get('total_trades', 0)}\n")
                f.write(f"Выигрышных:            {stats.get('winning_trades', 0)}\n")
                f.write(f"Проигрышных:           {stats.get('losing_trades', 0)}\n")
                f.write(f"Винрейт:               {stats.get('win_rate', 0):.2f}%\n")
                f.write(f"Открытых позиций:      {stats.get('open_positions', 0)}\n\n")
                
                # Timing статистика
                timing = stats.get('timing_analysis', {})
                f.write("⏰ TIMING СТАТИСТИКА:\n")
                f.write("-" * 50 + "\n")
                f.write(f"Входов через timing:   {timing.get('entries_from_timing', 0)}\n")
                f.write(f"Немедленных входов:    {timing.get('immediate_entries', 0)}\n")
                f.write(f"Среднее ожидание:      {timing.get('average_wait_time_minutes', 0):.1f} мин\n")
                f.write(f"Использование timing:  {timing.get('timing_usage_rate', 0):.1f}%\n\n")
                
                # Блокировки
                f.write("🚫 БЛОКИРОВКИ:\n")
                f.write("-" * 50 + "\n")
                f.write(f"По балансу:            {stats.get('blocked_by_balance', 0)}\n")
                f.write(f"По экспозиции:         {stats.get('blocked_by_exposure', 0)}\n\n")
                
                # История сделок
                if self.closed_trades:
                    f.write(f"📋 ИСТОРИЯ СДЕЛОК ({len(self.closed_trades)}):\n")
                    f.write("-" * 50 + "\n")
                    
                    for i, trade in enumerate(self.closed_trades, 1):
                        entry_time = trade.entry_time.strftime('%H:%M:%S') if isinstance(trade.entry_time, datetime) else str(trade.entry_time)
                        f.write(f"{i:2d}. {trade.symbol} {trade.direction.upper()} | "
                               f"${trade.pnl_usd:+6.2f} ({trade.pnl_percent:+5.1f}%) | "
                               f"{entry_time} | {trade.exit_reason}\n")
                    f.write("\n")
                
                f.write("="*80 + "\n")
                f.write("                           КОНЕЦ ОТЧЕТА\n")
                f.write("="*80 + "\n")
        except Exception as e:
            logger.error(f"❌ Ошибка создания текстового отчета: {e}")
    
    def print_final_report(self):
        """Финальный отчет с timing информацией"""
        try:
            logger.info("📋 Генерируем финальный отчет...")
            
            stats = self.calculate_statistics()
            
            print("\n" + "="*70)
            print("📊 ФИНАЛЬНЫЙ ОТЧЕТ ВИРТУАЛЬНОГО ТРЕЙДЕРА V2 (С TIMING)")
            print("="*70)
            
            logger.info("📋 ФИНАЛЬНАЯ СЕССИОННАЯ СТАТИСТИКА:")
            logger.info(f"   Длительность сессии: {stats['session_duration_hours']:.2f} часов")
            logger.info(f"   Стартовый баланс: ${self.initial_balance:,.2f}")
            logger.info(f"   Финальный баланс: ${stats['current_balance']:,.2f}")
            logger.info(f"   Общий P&L: ${stats['total_pnl']:+,.2f} ({stats['balance_change_percent']:+.2f}%)")
            
            print(f"💰 Стартовый баланс: ${self.initial_balance:,.2f}")
            print(f"💰 Финальный баланс: ${stats['current_balance']:,.2f}")
            print(f"📈 Общий P&L: ${stats['total_pnl']:+,.2f} ({stats['balance_change_percent']:+.2f}%)")
            
            logger.info(f"📊 ТОРГОВАЯ СТАТИСТИКА:")
            logger.info(f"   Всего сделок: {stats['total_trades']}")
            logger.info(f"   Выигрышных: {stats['winning_trades']} ({stats['win_rate']:.1f}%)")
            logger.info(f"   Проигрышных: {stats['losing_trades']}")
            logger.info(f"   Открытых позиций: {stats['open_positions']}")
            
            print(f"\n📊 ТОРГОВАЯ СТАТИСТИКА:")
            print(f"   Всего сделок: {stats['total_trades']}")
            print(f"   Выигрышных: {stats['winning_trades']} ({stats['win_rate']:.1f}%)")
            print(f"   Проигрышных: {stats['losing_trades']}")
            print(f"   Открытых позиций: {stats['open_positions']}")
            
            print(f"\n⚠️ БЛОКИРОВКИ:")
            print(f"   По балансу: {stats['blocked_by_balance']}")
            print(f"   По лимиту экспозиции: {stats['blocked_by_exposure']}")
            
            # Timing статистика
            timing = stats.get('timing_analysis', {})
            print(f"\n⏰ TIMING СТАТИСТИКА:")
            print(f"   Входов через timing: {timing.get('entries_from_timing', 0)}")
            print(f"   Немедленных входов: {timing.get('immediate_entries', 0)}")
            print(f"   Среднее ожидание: {timing.get('average_wait_time_minutes', 0):.1f} мин")
            print(f"   Использование timing: {timing.get('timing_usage_rate', 0):.1f}%")
            
            # Timing performance по типам
            timing_perf = stats.get('timing_performance_by_type', {})
            if timing_perf:
                print(f"\n📈 ПРОИЗВОДИТЕЛЬНОСТЬ ПО ТИПАМ TIMING:")
                for timing_type, perf in timing_perf.items():
                    print(f"   {timing_type.upper()}:")
                    print(f"     Сделок: {perf['count']}")
                    print(f"     Винрейт: {perf.get('win_rate', 0):.1f}%")
                    print(f"     Средний P&L: ${perf.get('average_pnl', 0):+.2f}")
                    print(f"     Ср. ожидание: {perf.get('average_wait_time', 0):.1f} мин")
            
            logger.info("📋 Финальный отчет завершен")
            print("="*70)
            
        except Exception as e:
            logger.error(f"💥 Ошибка печати финального отчета: {e}", exc_info=True)
            print("❌ Ошибка при создании отчета")

# ОСНОВНАЯ ФУНКЦИЯ с детальным логированием
async def main():
    """Основная функция с полным логированием"""
    logger.info("🚀 ЗАПУСК ВИРТУАЛЬНОГО ТРЕЙДЕРА V2 С TIMING СИСТЕМОЙ")
    logger.info("🎯 Новые возможности:")
    logger.info("   • Timing стратегии входа")
    logger.info("   • Pullback ожидания") 
    logger.info("   • Микро-подтверждения")
    logger.info("   • Улучшенная статистика")
    logger.info("   • ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ")
    
    print("🚀 Запуск виртуального трейдера V2 с TIMING системой")
    print("🎯 Новые возможности:")
    print("   • Timing стратегии входа")
    print("   • Pullback ожидания") 
    print("   • Микро-подтверждения")
    print("   • Улучшенная статистика")
    print("   • ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ")
    print("="*70)
    
    display_startup_info()
    
    # Создаем виртуального трейдера
    trader = VirtualTraderV2(
        initial_balance=10000.0,
        position_size_percent=2.0,
        max_exposure_percent=20.0
    )
    
    logger.info("🔗 Подключаемся к API и инициализируем торговый движок...")
    
    # Основной цикл
    async with BybitFuturesAPI() as api:
        logger.info("✅ API подключен успешно")
        engine = HybridTradingEngineV2(api)
        logger.info("✅ Торговый движок с timing инициализирован")
        
        print(f"🔄 Начинаем торговлю с timing системой...")
        print(f"💰 Стартовый баланс: ${trader.initial_balance:,.2f}")
        print(f"📊 Размер позиции: {trader.position_size_percent}% (${trader.position_size_usd:,.0f})")
        print(f"🛡️ Максимальная экспозиция: {trader.max_exposure_percent}%")
        
        logger.info(f"🎬 Начинаем основной торговый цикл...")
        cycle = 0
        
        try:
            while trader.is_running:
                cycle += 1
                cycle_start = time.time()
                logger.debug(f"🔄 === ЦИКЛ {cycle} НАЧАТ ===")
                
                # ФАЗА 1: Генерация новых сигналов
                logger.debug("🔍 ФАЗА 1: Поиск новых сигналов...")
                new_signals = await engine.analyze_and_generate_signals(SYMBOLS)
                
                if new_signals:
                    trader.total_signals += len(new_signals)
                    trader.timing_stats['signals_queued'] += len(new_signals)
                    
                    logger.info(f"📊 ЦИКЛ {cycle}: Найдено {len(new_signals)} новых сигналов")
                    
                    for signal_info in new_signals:
                        signal = signal_info['signal']
                        timing_strategy = signal_info['timing_strategy']
                        
                        logger.info(f"⏳ {signal['symbol']} {signal['direction']} → timing очередь "
                                   f"(стратегия: {timing_strategy}, уверенность: {signal.get('confidence', 0):.1%})")
                else:
                    logger.debug(f"🔍 ЦИКЛ {cycle}: Новых сигналов не найдено")
                
                # ФАЗА 2: Проверка готовых к входу сигналов
                logger.debug("🎯 ФАЗА 2: Проверка готовых входов...")
                ready_entries = await engine.check_ready_entries()
                
                if ready_entries:
                    logger.info(f"🎯 ЦИКЛ {cycle}: Готовых к входу: {len(ready_entries)}")
                    for entry_signal in ready_entries:
                        await trader.open_virtual_position(entry_signal)
                else:
                    logger.debug("🎯 ФАЗА 2: Готовых входов нет")
                
                # ФАЗА 3: Проверка закрытия позиций
                logger.debug("🔍 ФАЗА 3: Проверка закрытия позиций...")
                await trader.check_position_exits(api)
                
                # ФАЗА 4: Логирование статуса
                logger.debug("📊 ФАЗА 4: Обновление статуса...")
                await trader.log_status(api, engine)
                
                # ФАЗА 5: Периодические отчеты
                if cycle % 20 == 0:
                    logger.info(f"📋 ПЕРИОДИЧЕСКИЙ ОТЧЕТ (цикл {cycle}):")
                    
                    if len(trader.closed_trades) > 0:
                        print("\n")
                        trader.print_timing_status()
                        
                        stats = trader.calculate_statistics()
                        print(f"\n📊 Цикл {cycle}: Сделок {stats['total_trades']}, "
                              f"Винрейт {stats['win_rate']:.1f}%, P&L ${stats['total_pnl']:+.2f}")
                    else:
                        logger.info("📋 Пока нет закрытых сделок для отчета")
                
                # Измеряем время цикла
                cycle_time = time.time() - cycle_start
                logger.debug(f"⏱️ ЦИКЛ {cycle} завершен за {cycle_time:.2f} сек")
                
                # Пауза
                await asyncio.sleep(INTERVAL_SEC)
                
        except KeyboardInterrupt:
            logger.warning("🛑 Получен сигнал прерывания от пользователя")
            print("\n\n🛑 Остановка по запросу пользователя...")
            trader.is_running = False
        except Exception as e:
            logger.error(f"💥 Критическая ошибка в main цикле: {e}", exc_info=True)
            print(f"\n❌ Критическая ошибка: {str(e)}")
        finally:
            logger.info("🔄 Начинаем процедуру завершения...")
            print("\n🔄 Завершение работы...")
            
            logger.info("💾 Сохраняем финальные результаты...")
            print("\n💾 Сохраняем финальную статистику...")
            
            final_file = trader.save_results()
            if final_file:
                print(f"✅ Финальная статистика сохранена!")
                print(f"📁 Файл: {os.path.abspath(final_file)}")
            else:
                print("❌ Ошибка сохранения финальной статистики")
            
            logger.info("📋 Генерируем финальный отчет...")
            trader.print_final_report()
            
            logger.info("✅ Виртуальный трейдер завершил работу корректно")
            print("👋 До свидания!")

# ТОЧКА ВХОДА
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("👋 Программа завершена пользователем через Ctrl+C")
        print("\n👋 Программа завершена пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка при запуске: {e}", exc_info=True)
        print(f"💥 Критическая ошибка при запуске: {str(e)}")