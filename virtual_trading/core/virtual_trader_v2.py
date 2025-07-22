# virtual_trading/core/virtual_trader_v2.py
"""
PRODUCTION-READY VirtualTrader V3.0
Простой оркестратор без избыточной сложности
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

# Интеграция с существующими системами
from config.logging_config import setup_logging
from config import ANTISPAM_CONFIG, ML_CONFIG

# Импорты сервисов
from ..services.balance_manager import BalanceManager
from ..services.position_manager import PositionManager
from ..services.statistics_calculator import StatisticsCalculator
from ..services.report_generator import ReportGenerator

logger = logging.getLogger('VirtualTrader')

class VirtualTraderV2:
    """Production-ready виртуальный трейдер V3.0 - простой и надежный"""
    
    def __init__(self, initial_balance=10000.0, position_size_percent=2.0, max_exposure_percent=20.0):
        logger.info("[INIT] Инициализация VirtualTrader V3.0...")
        
        # Инициализация сервисов
        self.balance_manager = BalanceManager(initial_balance, position_size_percent, max_exposure_percent)
        self.position_manager = PositionManager(self.balance_manager)
        self.statistics_calculator = StatisticsCalculator()
        self.report_generator = ReportGenerator()
        
        # Основные параметры
        self.start_time = datetime.now()
        self.is_running = True
        
        # Простая статистика
        self.total_signals = 0
        self.total_trades_opened = 0
        self.blocked_by_exposure = 0
        self.blocked_by_balance = 0
        
        # Timing статистика
        self.timing_stats = {
            'signals_queued': 0,
            'entries_from_timing': 0,
            'immediate_entries': 0,
            'average_wait_time': 0
        }
        
        logger.info("[SUCCESS] VirtualTrader V3.0 готов к работе")
        logger.info(f"   Баланс: ${initial_balance:,.0f} | Позиция: {position_size_percent}% | Лимит: {max_exposure_percent}%")
    
    async def open_virtual_position(self, signal: Dict) -> None:
        """Открытие виртуальной позиции - простая логика"""
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
            else:
                self.timing_stats['immediate_entries'] += 1
        else:
            # Определяем причину блокировки
            can_open, reason = self.balance_manager.can_open_new_position(self.open_positions)
            if reason == "insufficient_balance":
                self.blocked_by_balance += 1
            elif reason == "exposure_limit":
                self.blocked_by_exposure += 1
    
    async def check_position_exits(self, api) -> None:
        """Проверка закрытия позиций - делегируем в PositionManager"""
        await self.position_manager.check_position_exits(api)
    
    async def log_status(self, api=None, engine=None) -> None:
        """Логирование статуса - упрощенная версия"""
        try:
            # Получаем текущие цены
            current_prices = {}
            if api and self.position_manager.open_positions:
                for symbol in self.position_manager.open_positions.keys():
                    try:
                        current_data = await api.get_ohlcv(symbol, 15, 1)
                        if not current_data.empty:
                            current_prices[symbol] = current_data['close'].iloc[-1]
                    except:
                        pass
            
            # Рассчитываем статистику
            stats = self.statistics_calculator.calculate_session_stats(
                balance_manager=self.balance_manager,
                positions=self.position_manager.open_positions,
                closed_trades=self.position_manager.closed_trades,
                current_prices=current_prices,
                timing_stats=self.timing_stats,
                start_time=self.start_time
            )
            
            # Получаем timing статус
            timing_status = ""
            if engine:
                try:
                    timing_info = engine.get_timing_status()
                    pending_count = len(timing_info.get('pending_entries', []))
                    if pending_count > 0:
                        timing_status = f" | ⏳ Ожидающих: {pending_count}"
                except:
                    pass
            
            # Отображаем статус
            self._display_status_line(stats, timing_status)
            
            # Периодическое сохранение
            self._check_periodic_save(stats)
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка в log_status: {e}")
    
    def _display_status_line(self, stats: Dict, timing_status: str = "") -> None:
        """Простое отображение статуса"""
        unrealized_pnl = stats.get('unrealized_pnl', 0)
        unrealized_status = f" | Нереализ. P&L: ${unrealized_pnl:+.2f}" if unrealized_pnl != 0 else ""
        
        status = (f"Баланс: ${stats['current_balance']:,.2f} ({stats['balance_percent']:+.2f}%){unrealized_status} | "
                 f"Доступно: ${stats['available_balance']:,.2f} | "
                 f"Инвестировано: ${stats['invested_capital']:,.0f} ({stats['exposure_percent']:.1f}%) | "
                 f"Позиций: {stats['open_positions_count']} | Сделок: {stats['total_trades']}{timing_status}")
        
        print(f"\r[VT3.0] {datetime.now().strftime('%H:%M:%S')} | {status}", end="", flush=True)
    
    def _check_periodic_save(self, stats: Dict) -> None:
        """Простое периодическое сохранение"""
        try:
            now = datetime.now()
            
            if not hasattr(self, 'last_save') or (now - self.last_save).total_seconds() >= 300:  # 5 минут
                self.report_generator.save_periodic_stats(stats)
                self.last_save = now
        except Exception as e:
            logger.debug(f"[SAVE] Ошибка периодического сохранения: {e}")
    
    def save_results(self) -> Optional[str]:
        """Сохранение результатов - делегируем в ReportGenerator"""
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
        """Печать финального отчета"""
        self.report_generator.print_final_report(
            balance_manager=self.balance_manager,
            closed_trades=self.position_manager.closed_trades,
            timing_stats=self.timing_stats,
            start_time=self.start_time
        )
    
    def quick_save(self) -> Optional[str]:
        """Простое быстрое сохранение для экстренных случаев"""
        try:
            timestamp = datetime.now().strftime('%H%M%S')
            
            # Простая статистика
            balance_summary = self.balance_manager.get_balance_summary(self.open_positions)
            
            emergency_data = {
                'emergency_save': True,
                'save_time': datetime.now().isoformat(),
                'session_duration_hours': (datetime.now() - self.start_time).total_seconds() / 3600,
                
                # Баланс
                **balance_summary,
                
                # Сделки
                'total_trades': len(self.closed_trades),
                'winning_trades': len([t for t in self.closed_trades if t.pnl_usd > 0]),
                'total_pnl': sum(t.pnl_usd for t in self.closed_trades),
                
                # Позиции и статистика
                'open_positions_count': len(self.open_positions),
                'timing_stats': self.timing_stats,
                'total_signals': self.total_signals,
                'blocked_by_balance': self.blocked_by_balance,
                'blocked_by_exposure': self.blocked_by_exposure
            }
            
            # Сохраняем
            emergency_file = f"{self.results_dir}/emergency_save_{timestamp}.json"
            
            with open(emergency_file, 'w', encoding='utf-8') as f:
                json.dump(emergency_data, f, indent=2, default=str)
            
            logger.info(f"[EMERGENCY] Экстренное сохранение: {emergency_file}")
            return emergency_file
            
        except Exception as e:
            logger.error(f"[EMERGENCY] Ошибка экстренного сохранения: {e}")
            return None
    
    def calculate_statistics(self, current_prices=None) -> Dict:
        """Расчет статистики"""
        return self.statistics_calculator.calculate_session_stats(
            balance_manager=self.balance_manager,
            positions=self.position_manager.open_positions,
            closed_trades=self.position_manager.closed_trades,
            current_prices=current_prices,
            timing_stats=self.timing_stats,
            start_time=self.start_time
        )
    
    def validate_system(self) -> Dict:
        """Простая валидация системы"""
        validation = self.balance_manager.validate_state()
        
        validation.update({
            'open_positions': len(self.open_positions),
            'closed_trades': len(self.closed_trades),
            'system_uptime_hours': (datetime.now() - self.start_time).total_seconds() / 3600,
            'timing_entries': self.timing_stats['entries_from_timing'],
            'immediate_entries': self.timing_stats['immediate_entries']
        })
        
        return validation
    
    # Свойства для совместимости с существующим кодом
    @property
    def open_positions(self) -> Dict:
        return self.position_manager.open_positions
    
    @property
    def closed_trades(self) -> List:
        return self.position_manager.closed_trades
    
    @property
    def initial_balance(self) -> float:
        return self.balance_manager.initial_balance
    
    @property
    def available_balance(self) -> float:
        return self.balance_manager.available_balance
    
    @property
    def results_dir(self) -> str:
        return self.report_generator.results_dir
    
    # Методы для интеграции
    def get_balance_summary(self, current_prices=None) -> Dict:
        return self.balance_manager.get_balance_summary(self.open_positions, current_prices)
    
    def get_positions_summary(self) -> Dict:
        return self.position_manager.get_positions_summary()
    
    def get_trades_summary(self) -> Dict:
        return self.position_manager.get_trades_summary()
    
    def get_risk_status(self) -> Dict:
        return self.balance_manager.check_risk_limits(self.open_positions)