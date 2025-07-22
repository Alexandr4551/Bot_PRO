# virtual_trading/core/virtual_trader_v2.py
"""
Основной класс виртуального трейдера V2 - упрощенный оркестратор
Интегрируется с существующей архитектурой: core/, config/, utils/
"""

import logging
import signal
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional

# Интеграция с существующими системами
from config.logging_config import setup_logging  # Используем существующее логирование
from config import ANTISPAM_CONFIG, ML_CONFIG    # Используем существующие конфигурации

# Импорты сервисов
from ..services.balance_manager import BalanceManager
from ..services.position_manager import PositionManager
from ..services.statistics_calculator import StatisticsCalculator
from ..services.report_generator import ReportGenerator

logger = logging.getLogger('VirtualTrader')

class VirtualTraderV2:
    """Упрощенный виртуальный трейдер V2 - основной оркестратор"""
    
    def __init__(self, initial_balance=10000.0, position_size_percent=2.0, max_exposure_percent=20.0):
        logger.info("[INIT] Инициализация виртуального трейдера V2...")
        
        # Инициализация всех сервисов
        self.balance_manager = BalanceManager(initial_balance, position_size_percent, max_exposure_percent)
        self.position_manager = PositionManager(self.balance_manager)
        self.statistics_calculator = StatisticsCalculator()
        self.report_generator = ReportGenerator()
        
        # Основные параметры
        self.start_time = datetime.now()
        self.is_running = True
        
        # Статистика (переместили из оригинального класса)
        self.total_signals = 0
        self.total_trades_opened = 0
        self.blocked_by_exposure = 0
        self.blocked_by_balance = 0
        
        # Статистика для timing (интеграция с core/timing_manager.py)
        self.timing_stats = {
            'signals_queued': 0,
            'entries_from_timing': 0,
            'timing_timeouts': 0,
            'average_wait_time': 0,
            'immediate_entries': 0
        }
        
        # Периодическое сохранение
        self.last_stats_save = None
        self.stats_save_interval = 300  # 5 минут
        
        # История для статистики (делегируем в StatisticsCalculator)
        self.last_timing_status = {}
        
        # Настройка обработчиков сигналов
        self.setup_signal_handlers()
        
        logger.info("[INIT] Все сервисы инициализированы успешно")
        logger.info(f"[INIT] Результаты будут сохраняться в: {os.path.abspath(self.report_generator.results_dir)}/")
        logger.info("[SUCCESS] Виртуальный трейдер V2 готов к работе")
    
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов завершения"""
        def signal_handler(signum, frame):
            logger.warning(f"[SIGNAL] Получен сигнал завершения {signum}")
            print(f"\n[SIGNAL] Получен сигнал {signum}. Завершение работы...")
            self.is_running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.debug("[SETUP] Обработчики сигналов настроены")
    
    async def open_virtual_position(self, signal: Dict) -> None:
        """Открытие виртуальной позиции - делегирует в PositionManager"""
        success = await self.position_manager.open_position(signal)
        
        if success:
            self.total_trades_opened += 1
            
            # Обновляем timing статистику
            timing_info = signal.get('timing_info', {})
            if timing_info:
                self.timing_stats['entries_from_timing'] += 1
                wait_time = timing_info.get('wait_time_minutes', 0)
                if wait_time > 0:
                    current_avg = self.timing_stats['average_wait_time']
                    count = self.timing_stats['entries_from_timing']
                    if count > 0:
                        self.timing_stats['average_wait_time'] = ((current_avg * (count - 1)) + wait_time) / count
                logger.debug(f"[TIMING] Статистика timing обновлена: входов {self.timing_stats['entries_from_timing']}")
            else:
                self.timing_stats['immediate_entries'] += 1
                logger.debug(f"[TIMING] Статистика немедленных входов: {self.timing_stats['immediate_entries']}")
                
        else:
            # Обновляем статистику блокировок
            # Детали определяются в balance_manager
            pass
    
    async def check_position_exits(self, api) -> None:
        """Проверка закрытия позиций - делегирует в PositionManager"""
        await self.position_manager.check_position_exits(api)
    
    async def log_status(self, api=None, engine=None) -> None:
        """Логирование статуса - использует StatisticsCalculator"""
        try:
            # Получаем текущие цены для расчета нереализованного P&L
            current_prices = {}
            if api and self.position_manager.open_positions:
                logger.debug(f"[STATUS] Получаем текущие цены для {len(self.position_manager.open_positions)} позиций...")
                for symbol in self.position_manager.open_positions.keys():
                    try:
                        current_data = await api.get_ohlcv(symbol, 15, 1)
                        if not current_data.empty:
                            current_prices[symbol] = current_data['close'].iloc[-1]
                            logger.debug(f"[PRICE] {symbol}: ${current_data['close'].iloc[-1]:.5f}")
                    except Exception as e:
                        logger.debug(f"[WARN] Не удалось получить цену {symbol}: {e}")
            
            # Рассчитываем статистику через сервис
            stats = self.statistics_calculator.calculate_session_stats(
                balance_manager=self.balance_manager,
                positions=self.position_manager.open_positions,
                closed_trades=self.position_manager.closed_trades,
                current_prices=current_prices,
                timing_stats=self.timing_stats,
                start_time=self.start_time
            )
            
            # Получаем статус timing системы
            timing_status = ""
            if engine:
                try:
                    timing_info = engine.get_timing_status()
                    pending_count = len(timing_info.get('pending_entries', []))
                    
                    if pending_count > 0:
                        timing_status = f" | ⏳ Ожидающих: {pending_count}"
                        logger.debug(f"[TIMING] Ожидающих timing входов: {pending_count}")
                    
                    self.last_timing_status = timing_info
                except Exception as e:
                    logger.debug(f"[WARN] Ошибка получения timing статуса: {e}")
            
            # Отображаем статус (аналогично оригинальному коду)
            self._display_status_line(stats, timing_status)
            
            # Периодическое сохранение
            self.check_and_save_periodic_stats(stats)
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка в log_status: {e}", exc_info=True)
    
    def _display_status_line(self, stats: Dict, timing_status: str = "") -> None:
        """Отображение статусной строки (как в оригинальном коде)"""
        try:
            unrealized_pnl = stats.get('unrealized_pnl', 0)
            unrealized_status = f" | Нереализ. P&L: ${unrealized_pnl:+.2f}" if unrealized_pnl != 0 else ""
            
            status = (f"[MONEY] Баланс: ${stats['current_balance']:,.2f} ({stats['balance_percent']:+.2f}%){unrealized_status} | "
                     f"Доступно: ${stats['available_balance']:,.2f} | "
                     f"Инвестировано: ${stats['invested_capital']:,.0f} ({stats['exposure_percent']:.1f}%) | "
                     f"Позиций: {stats['open_positions_count']} | Сделок: {stats['total_trades']}{timing_status}")
            
            print(f"\r[STATUS] ВИРТУАЛЬНЫЙ ТРЕЙДЕР V2 | ⏰ {datetime.now().strftime('%H:%M:%S')} | {status}", end="", flush=True)
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка отображения статуса: {e}")
    
    def check_and_save_periodic_stats(self, stats: Dict) -> None:
        """Периодическое сохранение статистики"""
        try:
            now = datetime.now()
            
            if (self.last_stats_save is None or 
                (now - self.last_stats_save).total_seconds() >= self.stats_save_interval):
                
                logger.debug("[SAVE] Время сохранить периодическую статистику...")
                self.report_generator.save_periodic_stats(stats)
                self.last_stats_save = now
                logger.info("[SAVE] Периодическая статистика сохранена")
                
        except Exception as e:
            logger.error(f"[ERROR] Ошибка периодического сохранения: {e}", exc_info=True)
    
    def save_results(self) -> Optional[str]:
        """Сохранение результатов - делегирует в ReportGenerator"""
        return self.report_generator.save_final_results(
            balance_manager=self.balance_manager,
            positions=self.position_manager.open_positions,
            closed_trades=self.position_manager.closed_trades,
            timing_stats=self.timing_stats,
            start_time=self.start_time,
            additional_stats={
                'total_signals': self.total_signals,
                'total_trades_opened': self.total_trades_opened,
                'blocked_by_balance': self.blocked_by_balance,
                'blocked_by_exposure': self.blocked_by_exposure
            }
        )
    
    def print_final_report(self) -> None:
        """Печать финального отчета - делегирует в ReportGenerator"""
        self.report_generator.print_final_report(
            balance_manager=self.balance_manager,
            closed_trades=self.position_manager.closed_trades,
            timing_stats=self.timing_stats,
            start_time=self.start_time
        )
    
    def print_timing_status(self) -> None:
        """Печать статуса timing системы"""
        self.report_generator.print_timing_status(
            timing_status=self.last_timing_status,
            timing_stats=self.timing_stats
        )
    
    def calculate_statistics(self, current_prices=None) -> Dict:
        """Расчет статистики - делегирует в StatisticsCalculator"""
        return self.statistics_calculator.calculate_session_stats(
            balance_manager=self.balance_manager,
            positions=self.position_manager.open_positions,
            closed_trades=self.position_manager.closed_trades,
            current_prices=current_prices,
            timing_stats=self.timing_stats,
            start_time=self.start_time
        )
    
    # Свойства для совместимости с оригинальным кодом
    @property
    def open_positions(self) -> Dict:
        """Доступ к открытым позициям"""
        return self.position_manager.open_positions
    
    @property
    def closed_trades(self) -> List:
        """Доступ к закрытым сделкам"""
        return self.position_manager.closed_trades
    
    @property
    def initial_balance(self) -> float:
        """Начальный баланс"""
        return self.balance_manager.initial_balance
    
    @property
    def available_balance(self) -> float:
        """Доступный баланс"""
        return self.balance_manager.available_balance
    
    @property
    def results_dir(self) -> str:
        """Директория результатов"""
        return self.report_generator.results_dir
    
    # Дополнительные методы для интеграции
    def get_balance_summary(self, current_prices=None) -> Dict:
        """Получить сводку по балансу"""
        return self.balance_manager.get_balance_summary(self.open_positions, current_prices)
    
    def get_positions_summary(self) -> Dict:
        """Получить сводку по позициям"""
        return self.position_manager.get_positions_summary()
    
    def get_trades_summary(self) -> Dict:
        """Получить сводку по сделкам"""
        return self.position_manager.get_trades_summary()
    
    def get_risk_status(self) -> Dict:
        """Получить статус рисков"""
        return self.balance_manager.check_risk_limits(self.open_positions)