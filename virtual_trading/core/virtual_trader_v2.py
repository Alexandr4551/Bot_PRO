# virtual_trading/core/virtual_trader_v2.py
"""
ИСПРАВЛЕННЫЙ основной класс виртуального трейдера V2 - упрощенный оркестратор
Версия 2.1 - исправлена интеграция с BalanceManager и логика баланса
"""

import logging
import json
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
    """Исправленный виртуальный трейдер V2 с корректной логикой баланса"""
    
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
        
        logger.info("[INIT] Все сервисы инициализированы успешно")
        logger.info(f"[INIT] Результаты будут сохраняться в: {os.path.abspath(self.report_generator.results_dir)}/")
        logger.info("[SUCCESS] Виртуальный трейдер V2 готов к работе")
    
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
            # ИСПРАВЛЕНО: Обновляем статистику блокировок на основе причины
            # Получаем причину блокировки из balance_manager
            can_open, reason = self.balance_manager.can_open_new_position(self.open_positions)
            if reason == "insufficient_balance":
                self.blocked_by_balance += 1
            elif reason == "exposure_limit":
                self.blocked_by_exposure += 1
    
    async def check_position_exits(self, api) -> None:
        """Проверка закрытия позиций - делегирует в PositionManager"""
        await self.position_manager.check_position_exits(api)
        
        # ИСПРАВЛЕНО: Проверка консистентности после изменений позиций
        try:
            consistency = self.balance_manager.check_balance_consistency(self.open_positions)
            if not consistency.get('is_consistent', True):
                consistency_level = consistency.get('consistency_level', 'UNKNOWN')
                difference = consistency.get('difference', 0)
                logger.warning(f"[CONSISTENCY] Обнаружена несогласованность баланса: "
                              f"${difference:+.2f}, уровень: {consistency_level}")
                
                # При критической несогласованности - дополнительное логирование
                if consistency_level == 'CRITICAL':
                    debug_info = self.balance_manager.get_debug_info()
                    logger.error(f"[CRITICAL] Критическая ошибка баланса. Debug info: {debug_info}")
                    
        except Exception as e:
            logger.debug(f"[CONSISTENCY] Ошибка проверки консистентности: {e}")
    
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
        """Отображение статусной строки с ИСПРАВЛЕННОЙ диагностикой баланса"""
        try:
            unrealized_pnl = stats.get('unrealized_pnl', 0)
            unrealized_status = f" | Нереализ. P&L: ${unrealized_pnl:+.2f}" if unrealized_pnl != 0 else ""
            
            # НОВОЕ: Показываем предупреждение если есть проблемы с балансом
            balance_warning = ""
            if stats.get('has_balance_issue', False):
                balance_difference = stats.get('balance_difference', 0)
                balance_warning = f" | ⚠️ Баланс: разница ${balance_difference:+.2f}"
            
            status = (f"[MONEY] Баланс: ${stats['current_balance']:,.2f} ({stats['balance_percent']:+.2f}%){unrealized_status}{balance_warning} | "
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
    
    def quick_save(self) -> Optional[str]:
        """ИСПРАВЛЕННОЕ быстрое сохранение с корректной логикой баланса"""
        try:
            timestamp = datetime.now().strftime('%H%M%S')
            
            # ИСПРАВЛЕНО: Используем правильные методы balance_manager
            balance_summary = self.balance_manager.get_balance_summary(self.open_positions)
            
            # Быстрая статистика без долгих операций
            stats = {
                'emergency_save': True,
                'save_time': datetime.now().isoformat(),
                'session_duration_hours': (datetime.now() - self.start_time).total_seconds() / 3600,
                
                # ИСПРАВЛЕНО: Используем правильные значения из balance_summary
                'initial_balance': balance_summary['initial_balance'],
                'available_balance': balance_summary['available_balance'],
                'current_balance': balance_summary['current_balance'],
                'balance_change': balance_summary['balance_change'],
                'balance_percent': balance_summary['balance_percent'],
                
                # Диагностическая информация
                'invested_capital': balance_summary['invested_capital'],
                'unrealized_pnl': balance_summary['unrealized_pnl'],
                'total_realized_pnl': balance_summary.get('total_realized_pnl', 0),
                'market_value_positions': balance_summary.get('market_value_positions', 0),
                'current_balance_v2': balance_summary.get('current_balance_v2', 0),
                'balance_difference': balance_summary.get('balance_difference', 0),
                'has_balance_issue': balance_summary.get('has_balance_issue', False),
                
                # Быстрая статистика сделок
                'total_trades': len(self.closed_trades),
                'winning_trades': len([t for t in self.closed_trades if t.pnl_usd > 0]),
                'losing_trades': len([t for t in self.closed_trades if t.pnl_usd <= 0]),
                'win_rate': (len([t for t in self.closed_trades if t.pnl_usd > 0]) / max(1, len(self.closed_trades))) * 100,
                'total_pnl': sum(t.pnl_usd for t in self.closed_trades),
                
                # Позиции
                'open_positions_count': len(self.open_positions),
                
                # Timing
                'timing_stats': self.timing_stats.copy(),
                
                # Блокировки
                'total_signals': self.total_signals,
                'blocked_by_balance': self.blocked_by_balance,
                'blocked_by_exposure': self.blocked_by_exposure,
                
                # ИСПРАВЛЕНО: Проверки консистентности с обработкой ошибок
                'consistency_check': self._safe_consistency_check(),
                'positions_consistency': self._safe_positions_consistency_check(),
                
                # НОВОЕ: Debug информация от BalanceManager
                'balance_debug_info': self.balance_manager.get_debug_info()
            }
            
            # Profit Factor
            if stats['total_trades'] > 0:
                total_profit = sum(t.pnl_usd for t in self.closed_trades if t.pnl_usd > 0)
                total_loss = abs(sum(t.pnl_usd for t in self.closed_trades if t.pnl_usd < 0))
                stats['profit_factor'] = total_profit / total_loss if total_loss > 0 else float('inf')
            else:
                stats['profit_factor'] = 0
            
            # Сохраняем в emergency файл
            emergency_file = f"{self.results_dir}/emergency_save_{timestamp}.json"
            
            with open(emergency_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, default=str)
            
            logger.info(f"[EMERGENCY] Экстренное сохранение: {emergency_file}")
            
            # ИСПРАВЛЕНО: Логируем потенциальные проблемы с правильными проверками
            if stats.get('has_balance_issue', False):
                logger.warning(f"[EMERGENCY] Обнаружена проблема с балансом: ${stats['balance_difference']:+.2f}")
            
            consistency = stats.get('consistency_check', {})
            if not consistency.get('is_consistent', True):
                logger.warning(f"[EMERGENCY] Несогласованность баланса: {consistency.get('consistency_level', 'UNKNOWN')}")
            
            return emergency_file
            
        except Exception as e:
            logger.error(f"[EMERGENCY] Ошибка экстренного сохранения: {e}")
            return None
    
    def _safe_consistency_check(self) -> Dict:
        """Безопасная проверка консистентности баланса"""
        try:
            return self.balance_manager.check_balance_consistency(self.open_positions)
        except Exception as e:
            logger.debug(f"[DEBUG] Ошибка проверки консистентности баланса: {e}")
            return {'is_consistent': True, 'error': str(e)}
    
    def _safe_positions_consistency_check(self) -> Dict:
        """Безопасная проверка консистентности позиций"""
        try:
            if hasattr(self.position_manager, 'check_positions_consistency'):
                return self.position_manager.check_positions_consistency()
            else:
                # Простая проверка если метода нет
                issues = []
                for symbol, position in self.open_positions.items():
                    try:
                        remaining_percent = position.get_remaining_percent()
                        if remaining_percent < 0 or remaining_percent > 100:
                            issues.append(f"{symbol}: некорректный remaining_percent {remaining_percent}")
                    except Exception as e:
                        issues.append(f"{symbol}: ошибка проверки - {e}")
                
                return {
                    'total_issues': len(issues),
                    'positions_with_issues': issues,
                    'is_consistent': len(issues) == 0
                }
        except Exception as e:
            logger.debug(f"[DEBUG] Ошибка проверки консистентности позиций: {e}")
            return {'total_issues': 0, 'error': str(e)}

    def create_quick_txt_summary(self, stats: Dict) -> None:
        """ИСПРАВЛЕННЫЙ создает быстрый txt отчет с улучшенной отладочной информацией"""
        try:
            summary_file = f"{self.results_dir}/session_summary.txt"
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write("=== ИТОГИ ТОРГОВОЙ СЕССИИ (V2.1) ===\n")
                f.write(f"Завершено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Длительность: {stats['session_duration_hours']:.1f} часов\n")
                f.write("=" * 40 + "\n\n")
                
                f.write("💰 ФИНАНСОВЫЕ РЕЗУЛЬТАТЫ:\n")
                f.write(f"   Начальный баланс: ${stats['initial_balance']:,.0f}\n")
                f.write(f"   Итоговый баланс:  ${stats['current_balance']:,.0f}\n")
                f.write(f"   Общий P&L:        ${stats['total_pnl']:+,.0f}\n")
                f.write(f"   P&L в процентах:  {stats['balance_percent']:+.2f}%\n")
                
                # ИСПРАВЛЕНО: Показываем диагностику баланса если есть проблемы
                if stats.get('has_balance_issue', False):
                    f.write(f"\n⚠️ ДИАГНОСТИКА БАЛАНСА:\n")
                    f.write(f"   Доступный баланс:     ${stats['available_balance']:,.2f}\n")
                    f.write(f"   Инвестированный:      ${stats.get('invested_capital', 0):,.2f}\n")
                    f.write(f"   Нереализованный P&L:  ${stats.get('unrealized_pnl', 0):+,.2f}\n")
                    f.write(f"   Рыночная стоимость:   ${stats.get('market_value_positions', 0):,.2f}\n")
                    f.write(f"   Realized P&L:         ${stats.get('total_realized_pnl', 0):+,.2f}\n")
                    f.write(f"   Альтернативный баланс: ${stats.get('current_balance_v2', 0):,.2f}\n")
                    f.write(f"   Разница в расчетах:   ${stats.get('balance_difference', 0):+.2f}\n")
                
                f.write("\n📊 ТОРГОВАЯ СТАТИСТИКА:\n")
                f.write(f"   Всего сделок:     {stats['total_trades']}\n")
                f.write(f"   Прибыльных:       {stats['winning_trades']}\n")
                f.write(f"   Убыточных:        {stats['losing_trades']}\n")
                f.write(f"   Винрейт:          {stats['win_rate']:.1f}%\n")
                
                if stats['total_trades'] > 0:
                    avg_pnl = stats['total_pnl'] / stats['total_trades']
                    f.write(f"   Средний P&L:      ${avg_pnl:+.2f}\n")
                    f.write(f"   Profit Factor:    {stats.get('profit_factor', 0):.2f}\n")
                
                f.write(f"   Открытых позиций: {stats['open_positions_count']}\n\n")
                
                f.write("⏰ TIMING СТАТИСТИКА:\n")
                timing = stats['timing_stats']
                f.write(f"   Через timing:     {timing.get('entries_from_timing', 0)}\n")
                f.write(f"   Немедленных:      {timing.get('immediate_entries', 0)}\n")
                f.write(f"   Среднее ожидание: {timing.get('average_wait_time', 0):.1f} мин\n")
                
                total_entries = timing.get('entries_from_timing', 0) + timing.get('immediate_entries', 0)
                if total_entries > 0:
                    timing_usage = (timing.get('entries_from_timing', 0) / total_entries) * 100
                    f.write(f"   Использование:    {timing_usage:.1f}%\n")
                
                f.write("\n🚫 БЛОКИРОВКИ:\n")
                f.write(f"   По балансу:       {stats['blocked_by_balance']}\n")
                f.write(f"   По экспозиции:    {stats['blocked_by_exposure']}\n")
                f.write(f"   Всего сигналов:   {stats['total_signals']}\n")
                
                # ИСПРАВЛЕНО: Показываем проблемы консистентности
                consistency = stats.get('consistency_check', {})
                if not consistency.get('is_consistent', True):
                    f.write(f"\n⚠️ ПРОБЛЕМЫ КОНСИСТЕНТНОСТИ:\n")
                    f.write(f"   Уровень проблемы: {consistency.get('consistency_level', 'UNKNOWN')}\n")
                    f.write(f"   Разница в балансе: ${consistency.get('difference', 0):+.2f}\n")
                    f.write(f"   Процент разницы:   {consistency.get('difference_percent', 0):.3f}%\n")
                
                pos_consistency = stats.get('positions_consistency', {})
                if pos_consistency.get('total_issues', 0) > 0:
                    f.write(f"\n⚠️ ПРОБЛЕМЫ ПОЗИЦИЙ:\n")
                    f.write(f"   Проблемных позиций: {len(pos_consistency.get('positions_with_issues', []))}\n")
                    f.write(f"   Всего проблем:      {pos_consistency.get('total_issues', 0)}\n")
                
                # НОВОЕ: Debug информация от BalanceManager
                debug_info = stats.get('balance_debug_info', {})
                if debug_info.get('total_operations', 0) > 0:
                    f.write(f"\n🔧 DEBUG ИНФОРМАЦИЯ:\n")
                    f.write(f"   Операций с балансом: {debug_info.get('total_operations', 0)}\n")
                    f.write(f"   Общий realized P&L:  ${debug_info.get('total_realized_pnl', 0):+.2f}\n")
                
                f.write("\n" + "=" * 40 + "\n")
                if stats['win_rate'] >= 60:
                    f.write("🎉 Отличная сессия!\n")
                elif stats['win_rate'] >= 50:
                    f.write("👍 Хорошая сессия!\n") 
                else:
                    f.write("📈 Есть что улучшать!\n")
                f.write("Сессия завершена (V2.1 - исправленная логика баланса).\n")
            
            logger.info(f"[SUMMARY] Краткий отчет создан: {summary_file}")
            
        except Exception as e:
            logger.error(f"[SUMMARY] Ошибка создания txt отчета: {e}")
    
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
    
    def get_balance_debug_info(self) -> Dict:
        """НОВЫЙ метод для получения отладочной информации о балансе"""
        try:
            return {
                'balance_manager_debug': self.balance_manager.get_debug_info(),
                'consistency_check': self.balance_manager.check_balance_consistency(self.open_positions),
                'risk_status': self.balance_manager.check_risk_limits(self.open_positions),
                'balance_summary': self.balance_manager.get_balance_summary(self.open_positions)
            }
        except Exception as e:
            logger.error(f"[DEBUG] Ошибка получения debug информации: {e}")
            return {'error': str(e)}
    
    def cleanup_balance_operations(self):
        """НОВЫЙ метод для очистки истории операций (экономия памяти)"""
        try:
            self.balance_manager.reset_debug_operations()
            logger.info("[CLEANUP] История операций баланса очищена")
        except Exception as e:
            logger.error(f"[CLEANUP] Ошибка очистки операций: {e}")