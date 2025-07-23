# virtual_trading/services/statistics_calculator.py
"""
Сервис расчета статистики и аналитики
Вычисляет метрики производительности виртуального трейдера
"""

import logging
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger('VirtualTrader.Statistics')

class StatisticsCalculator:
    """Расчет статистики и производительности виртуального трейдера"""
    
    def __init__(self):
        self.session_history: List[Dict] = []
        logger.debug("[INIT] StatisticsCalculator инициализирован")
    
    def calculate_session_stats(
        self,
        balance_manager,
        positions: Dict,
        closed_trades: List,
        current_prices: Optional[Dict] = None,
        timing_stats: Optional[Dict] = None,
        start_time: Optional[datetime] = None
    ) -> Dict:
        """Рассчитывает статистику текущей сессии"""
        try:
            logger.debug("[CALC] Рассчитываем сессионную статистику...")
            
            # Базовая информация
            session_duration = 0
            if start_time:
                session_duration = (datetime.now() - start_time).total_seconds() / 3600
            
            # Баланс и финансы
            balance_summary = balance_manager.get_balance_summary(positions, current_prices)
            
            # Статистика сделок
            trades_stats = self.calculate_trades_statistics(closed_trades)
            
            # Статистика timing
            timing_analysis = self.analyze_timing_performance(closed_trades, timing_stats or {})
            
            # Статистика позиций
            positions_stats = self.analyze_positions(positions)
            
            stats = {
                # Время
                'session_duration_hours': session_duration,
                'timestamp': datetime.now().isoformat(),
                
                # Баланс
                **balance_summary,
                
                # Сделки
                **trades_stats,
                
                # Позиции
                **positions_stats,
                
                # Timing
                'timing_analysis': timing_analysis,
                
                # Производительность
                'performance_metrics': self.calculate_performance_metrics(closed_trades, balance_summary)
            }
            
            # Добавляем в историю сессии
            self.session_history.append({
                'timestamp': datetime.now().isoformat(),
                'snapshot': stats
            })
            
            # Ограничиваем размер истории
            if len(self.session_history) > 1000:
                self.session_history = self.session_history[-500:]
            
            logger.debug(f"[CALC] Статистика рассчитана: {trades_stats['total_trades']} сделок, "
                        f"винрейт {trades_stats['win_rate']:.1f}%, P&L ${trades_stats['total_pnl']:+.2f}")
            
            return stats
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка расчета статистики: {e}", exc_info=True)
            return self._get_empty_stats()
    
    def calculate_trades_statistics(self, closed_trades: List) -> Dict:
        """Рассчитывает статистику по сделкам - группирует частичные выходы как одну сделку"""
        if not closed_trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'average_pnl': 0,
                'average_win': 0,
                'average_loss': 0,
                'profit_factor': 0,
                'max_consecutive_wins': 0,
                'max_consecutive_losses': 0
            }
        
        # Группируем закрытые части по позициям (symbol + entry_time)
        grouped_trades = {}
        for trade in closed_trades:
            # Ключ для группировки: символ + время входа + направление
            key = f"{trade.symbol}_{trade.entry_time}_{trade.direction}"
            
            if key not in grouped_trades:
                grouped_trades[key] = {
                    'symbol': trade.symbol,
                    'direction': trade.direction,
                    'entry_time': trade.entry_time,
                    'total_pnl': 0,
                    'parts': []
                }
            
            grouped_trades[key]['total_pnl'] += trade.pnl_usd
            grouped_trades[key]['parts'].append(trade)
        
        # Создаем список агрегированных сделок
        aggregated_trades = []
        for group_key, group_data in grouped_trades.items():
            aggregated_trades.append({
                'symbol': group_data['symbol'],
                'direction': group_data['direction'],
                'entry_time': group_data['entry_time'],
                'total_pnl': group_data['total_pnl'],
                'parts_count': len(group_data['parts']),
                'exit_reasons': [part.exit_reason for part in group_data['parts']]
            })
        
        # Рассчитываем статистику по агрегированным сделкам
        winning_trades = [t for t in aggregated_trades if t['total_pnl'] > 0]
        losing_trades = [t for t in aggregated_trades if t['total_pnl'] <= 0]
        
        total_pnl = sum(t['total_pnl'] for t in aggregated_trades)
        total_profit = sum(t['total_pnl'] for t in winning_trades)
        total_loss = abs(sum(t['total_pnl'] for t in losing_trades))
        
        win_rate = len(winning_trades) / len(aggregated_trades) * 100 if aggregated_trades else 0
        average_pnl = total_pnl / len(aggregated_trades) if aggregated_trades else 0
        average_win = total_profit / len(winning_trades) if winning_trades else 0
        average_loss = total_loss / len(losing_trades) if losing_trades else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Consecutive wins/losses по агрегированным сделкам
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0
        
        # Сортируем по времени входа для правильного подсчета последовательности
        sorted_trades = sorted(aggregated_trades, key=lambda x: x['entry_time'])
        
        for trade in sorted_trades:
            if trade['total_pnl'] > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
        
        return {
            'total_trades': len(aggregated_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'average_pnl': average_pnl,
            'average_win': average_win,
            'average_loss': average_loss,
            'profit_factor': profit_factor,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            # Дополнительная информация для отладки
            'total_partial_exits': len(closed_trades),
            'grouped_trades_details': [
                f"{t['symbol']} ({t['parts_count']} частей): ${t['total_pnl']:+.2f}"
                for t in aggregated_trades
            ]
        }
    
    def analyze_timing_performance(self, closed_trades: List, timing_stats: Dict) -> Dict:
        """Анализирует производительность timing системы"""
        timing_analysis = {
            'entries_from_timing': timing_stats.get('entries_from_timing', 0),
            'immediate_entries': timing_stats.get('immediate_entries', 0),
            'average_wait_time_minutes': timing_stats.get('average_wait_time', 0),
            'timing_usage_rate': 0,
            'timing_performance_by_type': {}
        }
        
        if not closed_trades:
            return timing_analysis
        
        # Общий процент использования timing
        total_entries = timing_stats.get('entries_from_timing', 0) + timing_stats.get('immediate_entries', 0)
        if total_entries > 0:
            timing_analysis['timing_usage_rate'] = (timing_stats.get('entries_from_timing', 0) / total_entries) * 100
        
        # Анализ по типам timing для закрытых сделок - группируем по позициям
        timing_performance = {}
        grouped_positions = {}
        
        # Сначала группируем части позиций
        for trade in closed_trades:
            if not hasattr(trade, 'timing_info') or not trade.timing_info:
                continue
                
            # Ключ для группировки позиций
            position_key = f"{trade.symbol}_{trade.entry_time}_{trade.direction}"
            
            if position_key not in grouped_positions:
                grouped_positions[position_key] = {
                    'total_pnl': 0,
                    'timing_info': trade.timing_info,
                    'parts': []
                }
            
            grouped_positions[position_key]['total_pnl'] += trade.pnl_usd
            grouped_positions[position_key]['parts'].append(trade)
        
        # Теперь анализируем по типам timing для целых позиций
        for position_data in grouped_positions.values():
            timing_info = position_data['timing_info']
            timing_type = timing_info.get('timing_type', 'unknown')
            
            if timing_type not in timing_performance:
                timing_performance[timing_type] = {
                    'count': 0,
                    'total_pnl': 0,
                    'wins': 0,
                    'total_wait_time': 0
                }
            
            timing_performance[timing_type]['count'] += 1
            timing_performance[timing_type]['total_pnl'] += position_data['total_pnl']
            if position_data['total_pnl'] > 0:
                timing_performance[timing_type]['wins'] += 1
            
            wait_time = timing_info.get('wait_time_minutes', 0)
            timing_performance[timing_type]['total_wait_time'] += wait_time
        
        # Рассчитываем средние значения
        for timing_type, stats in timing_performance.items():
            if stats['count'] > 0:
                stats['win_rate'] = (stats['wins'] / stats['count']) * 100
                stats['average_pnl'] = stats['total_pnl'] / stats['count']
                stats['average_wait_time'] = stats['total_wait_time'] / stats['count']
        
        timing_analysis['timing_performance_by_type'] = timing_performance
        
        return timing_analysis
    
    def analyze_positions(self, positions: Dict) -> Dict:
        """Анализирует открытые позиции"""
        if not positions:
            return {
                'open_positions_count': 0,
                'positions_by_direction': {'buy': 0, 'sell': 0},
                'positions_with_profit': 0,
                'avg_position_age_minutes': 0
            }
        
        # Статистика по направлениям
        buy_positions = sum(1 for p in positions.values() if p.direction == 'buy')
        sell_positions = sum(1 for p in positions.values() if p.direction == 'sell')
        
        # Позиции в профите (нужны текущие цены для точного расчета)
        positions_with_profit = 0
        total_age_minutes = 0
        current_time = datetime.now()
        
        for position in positions.values():
            # Возраст позиции
            position_age = (current_time - position.entry_time).total_seconds() / 60
            total_age_minutes += position_age
            
            # Простая проверка на профит (без текущих цен)
            if position.max_profit_usd > 0:
                positions_with_profit += 1
        
        avg_age = total_age_minutes / len(positions) if positions else 0
        
        return {
            'open_positions_count': len(positions),
            'positions_by_direction': {'buy': buy_positions, 'sell': sell_positions},
            'positions_with_profit': positions_with_profit,
            'avg_position_age_minutes': avg_age
        }
    
    def calculate_performance_metrics(self, closed_trades: List, balance_summary: Dict) -> Dict:
        """Рассчитывает метрики производительности"""
        if not closed_trades:
            return {
                'sharpe_ratio': 0,
                'max_drawdown_percent': 0,
                'recovery_factor': 0,
                'profit_per_day': 0,
                'trades_per_day': 0
            }
        
        try:
            # Дневная прибыль
            if closed_trades:
                first_trade_time = min(t.entry_time for t in closed_trades)
                days_trading = (datetime.now() - first_trade_time).days or 1
                profit_per_day = balance_summary['total_pnl'] / days_trading
                trades_per_day = len(closed_trades) / days_trading
            else:
                profit_per_day = 0
                trades_per_day = 0
            
            # Простая версия Sharpe ratio (без risk-free rate)
            daily_returns = []
            for i, trade in enumerate(closed_trades):
                if i == 0:
                    continue
                daily_returns.append(trade.pnl_percent)
            
            sharpe_ratio = 0
            if daily_returns and np.std(daily_returns) > 0:
                sharpe_ratio = np.mean(daily_returns) / np.std(daily_returns)
            
            # Максимальная просадка (приблизительно)
            max_drawdown = 0
            running_max = balance_summary['initial_balance']
            
            # Простой расчет на основе кумулятивного P&L
            cumulative_pnl = 0
            for trade in closed_trades:
                cumulative_pnl += trade.pnl_usd
                current_balance = balance_summary['initial_balance'] + cumulative_pnl
                
                if current_balance > running_max:
                    running_max = current_balance
                
                drawdown = (running_max - current_balance) / running_max * 100
                max_drawdown = max(max_drawdown, drawdown)
            
            # Recovery factor
            recovery_factor = balance_summary['total_pnl'] / max_drawdown if max_drawdown > 0 else 0
            
            return {
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown_percent': max_drawdown,
                'recovery_factor': recovery_factor,
                'profit_per_day': profit_per_day,
                'trades_per_day': trades_per_day
            }
        
        except Exception as e:
            logger.error(f"[ERROR] Ошибка расчета метрик производительности: {e}")
            return {
                'sharpe_ratio': 0,
                'max_drawdown_percent': 0,
                'recovery_factor': 0,
                'profit_per_day': 0,
                'trades_per_day': 0
            }
    
    def get_session_history_summary(self, last_n_records: int = 100) -> Dict:
        """Возвращает сводку истории сессии"""
        if not self.session_history:
            return {'total_records': 0, 'history': []}
        
        recent_history = self.session_history[-last_n_records:]
        
        return {
            'total_records': len(self.session_history),
            'records_returned': len(recent_history),
            'history': recent_history
        }
    
    def _get_empty_stats(self) -> Dict:
        """Возвращает пустую статистику при ошибках"""
        return {
            'session_duration_hours': 0,
            'timestamp': datetime.now().isoformat(),
            'initial_balance': 0,
            'current_balance': 0,
            'total_pnl': 0,
            'balance_percent': 0,
            'total_trades': 0,
            'win_rate': 0,
            'open_positions_count': 0,
            'timing_analysis': {
                'entries_from_timing': 0,
                'immediate_entries': 0,
                'timing_usage_rate': 0
            },
            'performance_metrics': {
                'sharpe_ratio': 0,
                'max_drawdown_percent': 0,
                'profit_per_day': 0
            }
        }
    
    def generate_performance_report(self, stats: Dict) -> str:
        """Генерирует текстовый отчет о производительности"""
        try:
            report = []
            report.append("="*50)
            report.append("ОТЧЕТ О ПРОИЗВОДИТЕЛЬНОСТИ")
            report.append("="*50)
            
            # Баланс
            report.append(f"💰 Баланс: ${stats['current_balance']:,.2f} ({stats['balance_percent']:+.2f}%)")
            report.append(f"📈 P&L: ${stats['total_pnl']:+,.2f}")
            
            # Сделки
            report.append(f"📊 Сделок: {stats['total_trades']} (винрейт: {stats['win_rate']:.1f}%)")
            report.append(f"📍 Позиций: {stats['open_positions_count']}")
            
            # Timing
            timing = stats['timing_analysis']
            report.append(f"⏰ Timing: {timing['entries_from_timing']} входов, {timing['timing_usage_rate']:.1f}% использование")
            
            # Производительность
            perf = stats['performance_metrics']
            report.append(f"📈 Sharpe: {perf['sharpe_ratio']:.2f}")
            report.append(f"📉 Max DD: {perf['max_drawdown_percent']:.1f}%")
            report.append(f"💵 Прибыль/день: ${perf['profit_per_day']:+.2f}")
            
            report.append("="*50)
            
            return "\n".join(report)
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка генерации отчета: {e}")
            return "Ошибка генерации отчета о производительности"