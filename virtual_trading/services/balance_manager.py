# virtual_trading/services/balance_manager.py
"""
ИСПРАВЛЕННЫЙ сервис управления балансом и экспозицией
Версия 2.1 - исправлена логика баланса и добавлена валидация
"""

import logging
from typing import Dict, Tuple, Optional
from datetime import datetime

# Используем существующую конфигурацию
from config import ANTISPAM_CONFIG

logger = logging.getLogger('VirtualTrader.BalanceManager')

class BalanceManager:
    """Управляет балансом и экспозицией виртуального трейдера с корректной логикой"""
    
    def __init__(self, initial_balance: float, position_size_percent: float, max_exposure_percent: float):
        self.initial_balance = initial_balance
        self.available_balance = initial_balance
        self.position_size_percent = position_size_percent
        self.position_size_usd = initial_balance * (position_size_percent / 100)
        self.max_exposure_percent = max_exposure_percent
        self.max_exposure_usd = initial_balance * (max_exposure_percent / 100)
        
        # НОВОЕ: Отслеживание общего реализованного P&L
        self.total_realized_pnl = 0.0
        
        # НОВОЕ: Отслеживание истории операций для отладки
        self.balance_operations = []
        
        logger.info(f"[INIT] BalanceManager инициализирован:")
        logger.info(f"   Начальный баланс: ${self.initial_balance:,.2f}")
        logger.info(f"   Размер позиции: {self.position_size_percent}% (${self.position_size_usd:,.0f})")
        logger.info(f"   Максимальная экспозиция: {self.max_exposure_percent}% (${self.max_exposure_usd:,.0f})")
    
    def get_invested_capital(self, positions: Dict) -> float:
        """ИСПРАВЛЕННЫЙ расчет инвестированного капитала с учетом частичных закрытий"""
        total_invested = 0
        
        for symbol, position in positions.items():
            try:
                # ИСПРАВЛЕНО: Используем метод из модели для получения оставшегося процента
                remaining_percent = position.get_remaining_percent()
                
                if remaining_percent > 0:
                    invested_amount = self.position_size_usd * (remaining_percent / 100)
                    total_invested += invested_amount
                    
                    logger.debug(f"[CAPITAL] {symbol}: {remaining_percent}% = ${invested_amount:.2f}")
                else:
                    logger.debug(f"[CAPITAL] {symbol}: полностью закрыта")
                    
            except Exception as e:
                logger.error(f"[ERROR] Ошибка расчета капитала для {symbol}: {e}")
                # Fallback: считаем как полную позицию если не можем рассчитать
                total_invested += self.position_size_usd
        
        logger.debug(f"[CAPITAL] Общий инвестированный капитал: ${total_invested:,.2f}")
        return total_invested
    
    def get_unrealized_pnl(self, positions: Dict, current_prices: Optional[Dict] = None) -> float:
        """ИСПРАВЛЕННЫЙ расчет нереализованной прибыли/убытка"""
        if not current_prices:
            logger.debug("[PNL] Текущие цены не предоставлены, нереализованный P&L = 0")
            return 0.0
        
        total_unrealized_pnl = 0.0
        
        for symbol, position in positions.items():
            try:
                if symbol not in current_prices:
                    logger.debug(f"[PNL] Нет текущей цены для {symbol}")
                    continue
                
                current_price = current_prices[symbol]
                
                # ИСПРАВЛЕНО: Используем метод из модели
                remaining_quantity = position.get_remaining_quantity()
                
                if remaining_quantity <= 0:
                    logger.debug(f"[PNL] {symbol}: позиция полностью закрыта")
                    continue
                
                # Расчет нереализованного P&L для оставшегося количества
                if position.direction == 'buy':
                    unrealized_pnl = remaining_quantity * (current_price - position.entry_price)
                else:
                    unrealized_pnl = remaining_quantity * (position.entry_price - current_price)
                
                total_unrealized_pnl += unrealized_pnl
                
                logger.debug(f"[PNL] {symbol}: ${unrealized_pnl:+.2f} "
                            f"(цена ${current_price:.5f}, вход ${position.entry_price:.5f}, "
                            f"остаток {remaining_quantity:.6f})")
                            
            except Exception as e:
                logger.error(f"[ERROR] Ошибка расчета P&L для {symbol}: {e}")
        
        logger.debug(f"[PNL] Общий нереализованный P&L: ${total_unrealized_pnl:+,.2f}")
        return total_unrealized_pnl
    
    def get_current_balance(self, positions: Dict, current_prices: Optional[Dict] = None) -> float:
        """ОСНОВНОЙ метод расчета текущего баланса"""
        invested_capital = self.get_invested_capital(positions)
        unrealized_pnl = self.get_unrealized_pnl(positions, current_prices)
        total_balance = self.available_balance + invested_capital + unrealized_pnl
        
        logger.debug(f"[BALANCE] Компоненты: доступно ${self.available_balance:,.2f} + "
                    f"инвестировано ${invested_capital:,.2f} + нереализ. ${unrealized_pnl:+,.2f} = "
                    f"итого ${total_balance:,.2f}")
        
        return total_balance
    
    def get_current_balance_v2(self, positions: Dict, current_prices: Optional[Dict] = None) -> float:
        """АЛЬТЕРНАТИВНЫЙ метод расчета баланса для проверки консистентности"""
        try:
            # Альтернативная логика: начальный баланс + реализованный P&L + нереализованный P&L
            
            # 1. Реализованный P&L уже учтен в available_balance через операции reserve/release
            # 2. Добавляем нереализованный P&L от открытых позиций
            unrealized_pnl = self.get_unrealized_pnl(positions, current_prices)
            
            # 3. Рыночная стоимость открытых позиций
            market_value = 0.0
            if current_prices:
                for symbol, position in positions.items():
                    if symbol in current_prices:
                        remaining_quantity = position.get_remaining_quantity()
                        market_value += remaining_quantity * current_prices[symbol]
            
            # Альтернативный расчет: доступный баланс + рыночная стоимость позиций
            alternative_balance = self.available_balance + market_value
            
            logger.debug(f"[BALANCE_V2] Альтернативный расчет: ${self.available_balance:,.2f} + ${market_value:,.2f} = ${alternative_balance:,.2f}")
            
            return alternative_balance
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка альтернативного расчета баланса: {e}")
            # Fallback на основной метод
            return self.get_current_balance(positions, current_prices)
    
    def check_balance_consistency(self, positions: Dict, current_prices: Optional[Dict] = None) -> Dict:
        """НОВЫЙ метод проверки консистентности расчетов баланса"""
        try:
            # Получаем баланс двумя способами
            balance_main = self.get_current_balance(positions, current_prices)
            balance_alt = self.get_current_balance_v2(positions, current_prices)
            
            # Вычисляем разницу
            difference = balance_main - balance_alt
            difference_percent = (difference / balance_main * 100) if balance_main != 0 else 0
            
            # Определяем критичность разницы
            is_consistent = abs(difference) < 10.0  # Допускаем разницу до $10
            consistency_level = "GOOD" if abs(difference) < 1.0 else "WARNING" if abs(difference) < 10.0 else "CRITICAL"
            
            consistency_info = {
                'is_consistent': is_consistent,
                'balance_main': balance_main,
                'balance_alternative': balance_alt,
                'difference': difference,
                'difference_percent': difference_percent,
                'consistency_level': consistency_level,
                'timestamp': logger.handlers[0].formatter.formatTime(logger.makeRecord('test', 0, '', 0, '', (), None)) if logger.handlers else str(datetime.now())
            }
            
            if not is_consistent:
                logger.warning(f"[CONSISTENCY] Обнаружена несогласованность баланса:")
                logger.warning(f"   Основной метод: ${balance_main:,.2f}")
                logger.warning(f"   Альтернативный: ${balance_alt:,.2f}")
                logger.warning(f"   Разница: ${difference:+.2f} ({difference_percent:+.3f}%)")
                logger.warning(f"   Уровень: {consistency_level}")
            else:
                logger.debug(f"[CONSISTENCY] Расчеты баланса согласованы (разница: ${difference:+.2f})")
            
            return consistency_info
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка проверки консистентности: {e}")
            return {
                'is_consistent': False,
                'error': str(e),
                'consistency_level': 'ERROR'
            }
    
    def can_open_new_position(self, positions: Dict) -> Tuple[bool, str]:
        """Проверка возможности открытия новой позиции с улучшенной логикой"""
        # Проверка доступного баланса
        if self.available_balance < self.position_size_usd:
            logger.warning(f"[BLOCK] Недостаточно средств: доступно ${self.available_balance:.2f}, "
                          f"нужно ${self.position_size_usd:.2f}")
            return False, "insufficient_balance"
        
        # Проверка лимита экспозиции
        current_invested = self.get_invested_capital(positions)
        would_be_invested = current_invested + self.position_size_usd
        
        if would_be_invested > self.max_exposure_usd:
            logger.warning(f"[BLOCK] Превышен лимит экспозиции: текущая ${current_invested:.2f} + "
                          f"новая ${self.position_size_usd:.2f} = ${would_be_invested:.2f} > "
                          f"лимит ${self.max_exposure_usd:.2f}")
            return False, "exposure_limit"
        
        # НОВОЕ: Проверка общего состояния баланса
        try:
            consistency = self.check_balance_consistency(positions)
            if not consistency.get('is_consistent', True) and consistency.get('consistency_level') == 'CRITICAL':
                logger.warning(f"[BLOCK] Критическая ошибка консистентности баланса")
                return False, "balance_inconsistency"
        except Exception as e:
            logger.debug(f"[DEBUG] Не удалось проверить консистентность: {e}")
        
        logger.debug(f"[OK] Можно открыть позицию: доступно ${self.available_balance:.2f}, "
                    f"экспозиция будет ${would_be_invested:.2f}/{self.max_exposure_usd:.2f}")
        return True, "ok"
    
    def reserve_funds(self, amount: float) -> bool:
        """Резервирует средства для новой позиции с логированием операции"""
        if self.available_balance >= amount:
            old_balance = self.available_balance
            self.available_balance -= amount
            
            # НОВОЕ: Записываем операцию для отладки
            self.balance_operations.append({
                'type': 'reserve',
                'amount': amount,
                'old_balance': old_balance,
                'new_balance': self.available_balance,
                'timestamp': datetime.now()
            })
            
            logger.info(f"[BALANCE] Средства зарезервированы: ${old_balance:.2f} → ${self.available_balance:.2f} "
                       f"(резерв ${amount:.2f})")
            return True
        
        logger.error(f"[ERROR] Не удалось зарезервировать ${amount:.2f}, доступно ${self.available_balance:.2f}")
        return False
    
    def release_funds(self, amount: float, pnl: float = 0) -> None:
        """Освобождает средства после закрытия позиции с обновленным учетом P&L"""
        old_balance = self.available_balance
        self.available_balance += amount + pnl
        
        # НОВОЕ: Обновляем общий реализованный P&L
        self.total_realized_pnl += pnl
        
        # НОВОЕ: Записываем операцию для отладки
        self.balance_operations.append({
            'type': 'release',
            'amount': amount,
            'pnl': pnl,
            'old_balance': old_balance,
            'new_balance': self.available_balance,
            'total_realized_pnl': self.total_realized_pnl,
            'timestamp': datetime.now()
        })
        
        logger.info(f"[BALANCE] Средства освобождены: ${old_balance:.2f} + ${amount:.2f} + ${pnl:+.2f} = ${self.available_balance:.2f}")
        if pnl != 0:
            logger.info(f"[PNL] Общий реализованный P&L: ${self.total_realized_pnl:+.2f}")
    
    def get_balance_summary(self, positions: Dict, current_prices: Optional[Dict] = None) -> Dict:
        """ИСПРАВЛЕННАЯ сводка по балансу с дополнительной диагностикой"""
        try:
            # Основные расчеты
            invested_capital = self.get_invested_capital(positions)
            unrealized_pnl = self.get_unrealized_pnl(positions, current_prices)
            current_balance = self.get_current_balance(positions, current_prices)
            
            # НОВОЕ: Альтернативные расчеты для проверки
            current_balance_v2 = self.get_current_balance_v2(positions, current_prices)
            balance_difference = current_balance - current_balance_v2
            
            # Рыночная стоимость позиций
            market_value_positions = 0.0
            if current_prices:
                for symbol, position in positions.items():
                    if symbol in current_prices:
                        remaining_quantity = position.get_remaining_quantity()
                        market_value_positions += remaining_quantity * current_prices[symbol]
            
            # Производные метрики
            exposure_percent = (invested_capital / self.initial_balance) * 100 if self.initial_balance > 0 else 0
            balance_change = current_balance - self.initial_balance
            balance_percent = (balance_change / self.initial_balance) * 100 if self.initial_balance > 0 else 0
            
            summary = {
                # Основные значения
                'initial_balance': self.initial_balance,
                'available_balance': self.available_balance,
                'invested_capital': invested_capital,
                'unrealized_pnl': unrealized_pnl,
                'current_balance': current_balance,
                'balance_change': balance_change,
                'balance_percent': balance_percent,
                'exposure_percent': exposure_percent,
                'max_exposure_percent': self.max_exposure_percent,
                'position_size_usd': self.position_size_usd,
                
                # НОВОЕ: Диагностическая информация
                'total_realized_pnl': self.total_realized_pnl,
                'market_value_positions': market_value_positions,
                'current_balance_v2': current_balance_v2,
                'balance_difference': balance_difference,
                
                # Метаданные
                'calculation_timestamp': datetime.now().isoformat(),
                'positions_count': len(positions)
            }
            
            # НОВОЕ: Проверяем консистентность
            if abs(balance_difference) > 1.0:
                logger.warning(f"[SUMMARY] Обнаружена разница в расчетах баланса: ${balance_difference:+.2f}")
                summary['has_balance_issue'] = True
            else:
                summary['has_balance_issue'] = False
            
            return summary
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка создания сводки баланса: {e}", exc_info=True)
            
            # Возвращаем минимальную сводку при ошибке
            return {
                'initial_balance': self.initial_balance,
                'available_balance': self.available_balance,
                'current_balance': self.available_balance,  # Fallback
                'balance_percent': 0.0,
                'error': str(e),
                'has_balance_issue': True
            }
    
    def check_risk_limits(self, positions: Dict) -> Dict:
        """Проверяет соблюдение риск-лимитов с дополнительными проверками"""
        try:
            balance_summary = self.get_balance_summary(positions)
            
            warnings = []
            
            # Проверка экспозиции
            if balance_summary['exposure_percent'] > self.max_exposure_percent * 0.9:
                warnings.append(f"Высокая экспозиция: {balance_summary['exposure_percent']:.1f}%")
            
            # Проверка доступного баланса
            if self.available_balance < self.position_size_usd:
                warnings.append(f"Недостаточно средств для новых позиций")
            
            # Проверка общих потерь
            if balance_summary['balance_percent'] < -10:
                warnings.append(f"Потери превышают 10%: {balance_summary['balance_percent']:.1f}%")
            
            # НОВОЕ: Проверка консистентности баланса
            if balance_summary.get('has_balance_issue', False):
                warnings.append(f"Обнаружена несогласованность в расчетах баланса")
            
            # НОВОЕ: Проверка аномальных значений
            if balance_summary['available_balance'] < 0:
                warnings.append(f"КРИТИЧНО: Отрицательный доступный баланс")
            
            if balance_summary['current_balance'] < self.initial_balance * 0.5:
                warnings.append(f"КРИТИЧНО: Потеря более 50% капитала")
            
            # Определение уровня риска
            if any('КРИТИЧНО' in w for w in warnings):
                risk_level = 'CRITICAL'
            elif len(warnings) > 2:
                risk_level = 'HIGH'
            elif warnings:
                risk_level = 'MEDIUM'
            else:
                risk_level = 'LOW'
            
            return {
                'warnings': warnings,
                'risk_level': risk_level,
                'balance_summary': balance_summary,
                'recommendations': self._get_risk_recommendations(warnings, balance_summary)
            }
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка проверки риск-лимитов: {e}")
            return {
                'warnings': [f"Ошибка проверки рисков: {str(e)}"],
                'risk_level': 'ERROR',
                'balance_summary': {},
                'recommendations': ['Проверить состояние системы']
            }
    
    def _get_risk_recommendations(self, warnings: list, balance_summary: Dict) -> list:
        """Генерирует рекомендации на основе анализа рисков"""
        recommendations = []
        
        if balance_summary.get('exposure_percent', 0) > 80:
            recommendations.append("Снизить экспозицию - закрыть часть позиций")
        
        if balance_summary.get('balance_percent', 0) < -15:
            recommendations.append("Пересмотреть торговую стратегию")
        
        if balance_summary.get('has_balance_issue', False):
            recommendations.append("Проверить логику расчета баланса")
        
        if self.available_balance < self.position_size_usd * 2:
            recommendations.append("Увеличить доступную ликвидность")
        
        if not recommendations:
            recommendations.append("Риски в пределах нормы")
        
        return recommendations
    
    def get_debug_info(self) -> Dict:
        """Возвращает отладочную информацию о состоянии BalanceManager"""
        return {
            'available_balance': self.available_balance,
            'total_realized_pnl': self.total_realized_pnl,
            'recent_operations': self.balance_operations[-10:],  # Последние 10 операций
            'total_operations': len(self.balance_operations),
            'position_size_usd': self.position_size_usd,
            'max_exposure_usd': self.max_exposure_usd,
            'initial_balance': self.initial_balance
        }
    
    def reset_debug_operations(self):
        """Очищает историю операций (для экономии памяти)"""
        operations_count = len(self.balance_operations)
        self.balance_operations = self.balance_operations[-100:]  # Оставляем последние 100
        logger.debug(f"[DEBUG] Очищена история операций: было {operations_count}, осталось {len(self.balance_operations)}")