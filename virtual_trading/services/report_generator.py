# virtual_trading/services/report_generator.py
"""
Сервис генерации отчетов и сохранения результатов
Интегрируется с существующей системой логирования
"""

import json
import os
import logging
from datetime import datetime
from dataclasses import asdict
from typing import Dict, List, Optional

logger = logging.getLogger('VirtualTrader.Reports')

class ReportGenerator:
    """Генерирует отчеты и сохраняет результаты виртуальной торговли"""
    
    def __init__(self, results_dir: str = "virtual_trading_results_v2"):
        self.results_dir = results_dir
        os.makedirs(self.results_dir, exist_ok=True)
        
        logger.info(f"[INIT] ReportGenerator инициализирован")
        logger.info(f"[INIT] Директория результатов: {os.path.abspath(self.results_dir)}/")
    
    def save_final_results(
        self,
        balance_manager,
        positions: Dict,
        closed_trades: List,
        timing_stats: Dict,
        start_time: datetime,
        additional_stats: Optional[Dict] = None
    ) -> Optional[str]:
        """Сохранение финальных результатов"""
        try:
            logger.info("[SAVE] Сохранение финальных результатов...")
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Создаем основную статистику
            from .statistics_calculator import StatisticsCalculator
            stats_calc = StatisticsCalculator()
            
            stats = stats_calc.calculate_session_stats(
                balance_manager=balance_manager,
                positions=positions,
                closed_trades=closed_trades,
                timing_stats=timing_stats,
                start_time=start_time
            )
            
            # Добавляем дополнительную информацию
            if additional_stats:
                stats.update(additional_stats)
            
            stats['save_reason'] = 'final_results'
            stats['session_end_time'] = datetime.now().isoformat()
            
            # Основная статистика
            stats_file = f"{self.results_dir}/final_statistics_{timestamp}.json"
            self._save_json_safely(stats, stats_file)
            
            logger.info(f"[SAVE] Основная статистика: {stats_file}")
            
            # Сохраняем историю сделок
            if closed_trades:
                trades_file = f"{self.results_dir}/closed_trades_{timestamp}.json"
                self._save_trades_data(closed_trades, trades_file)
                logger.info(f"[SAVE] Сделки сохранены: {trades_file} ({len(closed_trades)} сделок)")
            
            # Сохраняем открытые позиции
            if positions:
                positions_file = f"{self.results_dir}/open_positions_{timestamp}.json"
                self._save_positions_data(positions, positions_file)
                logger.info(f"[SAVE] Позиции сохранены: {positions_file} ({len(positions)} позиций)")
            
            # Создаем текстовый отчет
            try:
                report_file = f"{self.results_dir}/final_report_{timestamp}.txt"
                self.create_text_report(stats, report_file)
                logger.info(f"[SAVE] Отчет создан: {report_file}")
            except Exception as e:
                logger.error(f"[ERROR] Ошибка создания отчета: {e}")
            
            return stats_file
            
        except Exception as e:
            logger.error(f"[CRITICAL] Критическая ошибка сохранения: {e}", exc_info=True)
            return None
    
    def create_text_report(self, stats: Dict, filename: str) -> None:
        """Создание детального текстового отчета"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write("        ОТЧЕТ ВИРТУАЛЬНОГО ТРЕЙДЕРА V2 С TIMING\n")
                f.write("="*80 + "\n\n")
                
                # Заголовок
                f.write(f"Отчет создан: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Причина сохранения: {stats.get('save_reason', 'unknown')}\n")
                f.write(f"Длительность сессии: {stats.get('session_duration_hours', 0):.2f} часов\n\n")
                
                # Финансовые результаты
                f.write("[MONEY] ФИНАНСОВЫЕ РЕЗУЛЬТАТЫ:\n")
                f.write("-" * 50 + "\n")
                f.write(f"Начальный баланс:      ${stats.get('initial_balance', 0):,.2f}\n")
                f.write(f"Текущий баланс:        ${stats.get('current_balance', 0):,.2f}\n")
                f.write(f"Общий P&L:             ${stats.get('total_pnl', 0):+,.2f}\n")
                f.write(f"P&L в процентах:       {stats.get('balance_percent', 0):+.2f}%\n")
                f.write(f"Нереализованный P&L:   ${stats.get('unrealized_pnl', 0):+,.2f}\n\n")
                
                # Торговая статистика
                f.write("[STATS] ТОРГОВАЯ СТАТИСТИКА:\n")
                f.write("-" * 50 + "\n")
                f.write(f"Всего сделок:          {stats.get('total_trades', 0)}\n")
                f.write(f"Выигрышных:            {stats.get('winning_trades', 0)}\n")
                f.write(f"Проигрышных:           {stats.get('losing_trades', 0)}\n")
                f.write(f"Винрейт:               {stats.get('win_rate', 0):.2f}%\n")
                f.write(f"Открытых позиций:      {stats.get('open_positions_count', 0)}\n")
                f.write(f"Средний P&L:           ${stats.get('average_pnl', 0):+.2f}\n")
                f.write(f"Profit Factor:         {stats.get('profit_factor', 0):.2f}\n\n")
                
                # Timing статистика
                timing = stats.get('timing_analysis', {})
                f.write("[TIME] TIMING СТАТИСТИКА:\n")
                f.write("-" * 50 + "\n")
                f.write(f"Входов через timing:   {timing.get('entries_from_timing', 0)}\n")
                f.write(f"Немедленных входов:    {timing.get('immediate_entries', 0)}\n")
                f.write(f"Среднее ожидание:      {timing.get('average_wait_time_minutes', 0):.1f} мин\n")
                f.write(f"Использование timing:  {timing.get('timing_usage_rate', 0):.1f}%\n\n")
                
                # Производительность
                perf = stats.get('performance_metrics', {})
                f.write("[PERF] МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ:\n")
                f.write("-" * 50 + "\n")
                f.write(f"Sharpe Ratio:          {perf.get('sharpe_ratio', 0):.2f}\n")
                f.write(f"Максимальная просадка: {perf.get('max_drawdown_percent', 0):.2f}%\n")
                f.write(f"Recovery Factor:       {perf.get('recovery_factor', 0):.2f}\n")
                f.write(f"Прибыль в день:        ${perf.get('profit_per_day', 0):+.2f}\n")
                f.write(f"Сделок в день:         {perf.get('trades_per_day', 0):.1f}\n\n")
                
                # Блокировки и ограничения
                f.write("[BLOCKS] БЛОКИРОВКИ:\n")
                f.write("-" * 50 + "\n")
                f.write(f"По балансу:            {stats.get('blocked_by_balance', 0)}\n")
                f.write(f"По экспозиции:         {stats.get('blocked_by_exposure', 0)}\n\n")
                
                # Timing производительность по типам
                timing_perf = timing.get('timing_performance_by_type', {})
                if timing_perf:
                    f.write("[TIMING_PERF] ПРОИЗВОДИТЕЛЬНОСТЬ ПО ТИПАМ TIMING:\n")
                    f.write("-" * 50 + "\n")
                    for timing_type, perf_data in timing_perf.items():
                        f.write(f"{timing_type.upper()}:\n")
                        f.write(f"  Сделок:        {perf_data.get('count', 0)}\n")
                        f.write(f"  Винрейт:       {perf_data.get('win_rate', 0):.1f}%\n")
                        f.write(f"  Средний P&L:   ${perf_data.get('average_pnl', 0):+.2f}\n")
                        f.write(f"  Ср. ожидание:  {perf_data.get('average_wait_time', 0):.1f} мин\n\n")
                
                f.write("="*80 + "\n")
                f.write("                           КОНЕЦ ОТЧЕТА\n")
                f.write("="*80 + "\n")
                
        except Exception as e:
            logger.error(f"[ERROR] Ошибка создания текстового отчета: {e}", exc_info=True)
    
    def print_final_report(
        self,
        balance_manager,
        closed_trades: List,
        timing_stats: Dict,
        start_time: datetime
    ) -> None:
        """Печать финального отчета в консоль"""
        try:
            logger.info("[REPORT] Генерируем финальный отчет...")
            
            # Рассчитываем статистику
            from .statistics_calculator import StatisticsCalculator
            stats_calc = StatisticsCalculator()
            
            stats = stats_calc.calculate_session_stats(
                balance_manager=balance_manager,
                positions={},  # Для финального отчета позиции уже закрыты
                closed_trades=closed_trades,
                timing_stats=timing_stats,
                start_time=start_time
            )
            
            print("\n" + "="*70)
            print("[FINAL] ФИНАЛЬНЫЙ ОТЧЕТ ВИРТУАЛЬНОГО ТРЕЙДЕРА V2 (С TIMING)")
            print("="*70)
            
            # Основные метрики
            print(f"[MONEY] Стартовый баланс: ${stats['initial_balance']:,.2f}")
            print(f"[MONEY] Финальный баланс: ${stats['current_balance']:,.2f}")
            print(f"[MONEY] Общий P&L: ${stats['total_pnl']:+,.2f} ({stats['balance_percent']:+.2f}%)")
            
            print(f"\n[TRADES] ТОРГОВАЯ СТАТИСТИКА:")
            print(f"   Всего сделок: {stats['total_trades']}")
            print(f"   Выигрышных: {stats['winning_trades']} ({stats['win_rate']:.1f}%)")
            print(f"   Проигрышных: {stats['losing_trades']}")
            print(f"   Profit Factor: {stats.get('profit_factor', 0):.2f}")
            
            print(f"\n[BLOCKS] БЛОКИРОВКИ:")
            print(f"   По балансу: {stats.get('blocked_by_balance', 0)}")
            print(f"   По лимиту экспозиции: {stats.get('blocked_by_exposure', 0)}")
            
            # Timing статистика
            timing = stats.get('timing_analysis', {})
            print(f"\n[TIME] TIMING СТАТИСТИКА:")
            print(f"   Входов через timing: {timing.get('entries_from_timing', 0)}")
            print(f"   Немедленных входов: {timing.get('immediate_entries', 0)}")
            print(f"   Среднее ожидание: {timing.get('average_wait_time_minutes', 0):.1f} мин")
            print(f"   Использование timing: {timing.get('timing_usage_rate', 0):.1f}%")
            
            # Производительность
            perf = stats.get('performance_metrics', {})
            print(f"\n[PERF] ПРОИЗВОДИТЕЛЬНОСТЬ:")
            print(f"   Sharpe Ratio: {perf.get('sharpe_ratio', 0):.2f}")
            print(f"   Max Drawdown: {perf.get('max_drawdown_percent', 0):.2f}%")
            print(f"   Прибыль/день: ${perf.get('profit_per_day', 0):+.2f}")
            
            # Timing performance по типам
            timing_perf = timing.get('timing_performance_by_type', {})
            if timing_perf:
                print(f"\n[TIMING_DETAILED] ПРОИЗВОДИТЕЛЬНОСТЬ ПО ТИПАМ TIMING:")
                for timing_type, perf_data in timing_perf.items():
                    print(f"   {timing_type.upper()}:")
                    print(f"     Сделок: {perf_data.get('count', 0)}")
                    print(f"     Винрейт: {perf_data.get('win_rate', 0):.1f}%")
                    print(f"     Средний P&L: ${perf_data.get('average_pnl', 0):+.2f}")
                    print(f"     Ср. ожидание: {perf_data.get('average_wait_time', 0):.1f} мин")
            
            print("="*70)
            
            logger.info("[REPORT] Финальный отчет завершен")
            
        except Exception as e:
            logger.error(f"[CRITICAL] Ошибка печати финального отчета: {e}", exc_info=True)
            print("[ERROR] Ошибка при создании отчета")
    
    def print_timing_status(self, timing_status: Dict, timing_stats: Dict) -> None:
        """Печать статуса timing системы"""
        try:
            pending_entries = timing_status.get('pending_entries', [])
            
            if pending_entries:
                print(f"\n[TIME] ОЖИДАЮЩИЕ ВХОДЫ ({len(pending_entries)}):")
                logger.info(f"[TIME] Ожидающие входы: {len(pending_entries)}")
                
                for entry in pending_entries:
                    entry_info = (f"   {entry['symbol']} {entry['direction'].upper()} "
                                 f"| Стратегия: {entry['timing_type']} "
                                 f"| Ждем: {entry['time_waiting']} "
                                 f"| Осталось: {entry['time_remaining']} "
                                 f"| Подтв.: {entry['confirmations']}")
                    print(entry_info)
                    logger.info(entry_info)
            else:
                print(f"\n[TIME] Ожидающих timing входов нет")
                logger.info("[TIME] Нет ожидающих timing входов")
            
            # Общая статистика timing
            print(f"\n[TIME_STATS] TIMING СТАТИСТИКА:")
            print(f"   Входов через timing: {timing_stats.get('entries_from_timing', 0)}")
            print(f"   Немедленных входов: {timing_stats.get('immediate_entries', 0)}")
            print(f"   Среднее время ожидания: {timing_stats.get('average_wait_time', 0):.1f} мин")
            
            total_attempts = timing_stats.get('entries_from_timing', 0) + timing_stats.get('immediate_entries', 0)
            if total_attempts > 0:
                success_rate = (timing_stats.get('entries_from_timing', 0) / total_attempts) * 100
                print(f"   Использование timing: {success_rate:.1f}%")
            
            logger.info(f"[TIME_STATS] Timing статистика: через timing {timing_stats.get('entries_from_timing', 0)}, "
                       f"немедленно {timing_stats.get('immediate_entries', 0)}")
                       
        except Exception as e:
            logger.error(f"[ERROR] Ошибка печати timing статуса: {e}", exc_info=True)
            print(f"[ERROR] Ошибка отображения timing статуса: {e}")
    
    def _save_json_safely(self, data: Dict, filename: str) -> None:
        """Безопасное сохранение JSON с правильной сериализацией"""
        def safe_serialize(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif hasattr(obj, 'isoformat'):
                return obj.isoformat()
            return obj
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=safe_serialize)
    
    def _save_trades_data(self, closed_trades: List, filename: str) -> None:
        """Сохранение данных о сделках"""
        trades_data = []
        
        for trade in closed_trades:
            if hasattr(trade, 'to_dict'):
                trade_dict = trade.to_dict()
            else:
                trade_dict = asdict(trade)
                # Конвертируем datetime в строки
                for key, value in trade_dict.items():
                    if isinstance(value, datetime):
                        trade_dict[key] = value.isoformat()
            
            trades_data.append(trade_dict)
        
        self._save_json_safely(trades_data, filename)
    
    def _save_positions_data(self, positions: Dict, filename: str) -> None:
        """Сохранение данных о позициях"""
        positions_data = []
        
        for position in positions.values():
            pos_dict = asdict(position)
            # Конвертируем datetime в строки
            for key, value in pos_dict.items():
                if isinstance(value, datetime):
                    pos_dict[key] = value.isoformat()
            positions_data.append(pos_dict)
        
        self._save_json_safely(positions_data, filename)
    
    def save_periodic_stats(self, stats: Dict) -> None:
        """Периодическое сохранение статистики сессии"""
        try:
            stats_file = f"{self.results_dir}/session_stats_v2.json"
            stats['save_reason'] = 'periodic_save'
            stats['save_time'] = datetime.now().isoformat()
            
            self._save_json_safely(stats, stats_file)
            logger.debug(f"[PERIODIC] Статистика сохранена в {stats_file}")
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка периодического сохранения: {e}", exc_info=True)