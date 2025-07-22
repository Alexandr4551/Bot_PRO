# virtual_trading/services/balance_manager.py
"""
PRODUCTION-READY Balance Manager V3.0
Простая, надежная логика баланса без избыточной сложности
"""

import logging
from typing import Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger('VirtualTrader.BalanceManager')

class BalanceManager:
    """Production-ready управление балансом виртуального трейдера"""
    
    def __init__(self, initial_balance: float, position_size_percent: float, max_exposure_percent: float):
        # Основные параметры
        self.initial_balance = initial_balance
        self.available_balance = initial_balance
        self.position_size_percent = position_size_percent
        self.position_size_usd = initial_balance * (position_size_percent / 100)
        self.max_exposure_percent = max_exposure_percent
        self.max_exposure_usd = initial_balance * (max_exposure_percent / 100)
        
        # Операции с балансом
        self.total_invested = 0.0  # Сколько средств инвестировано
        self.total_realized_pnl = 0.0  # Общий реализованный P&L
        
        logger.info(f"[INIT] BalanceManager V3.0 инициализирован")
        logger.info(f"   Баланс: ${self.initial_balance:,.0f} | Позиция: {self.position_size_percent}% | Лимит: {self.max_exposure_percent}%")
    
    def get_invested_capital(self, positions: Dict) -> float:
        """Простой расчет инвестированного капитала"""
        total_invested = 0.0
        
        for position in positions.values():
            remaining_percent = position.get_remaining_percent()
            if remaining_percent > 0:
                invested_amount = self.position_size_usd * (remaining_percent / 100)
                total_invested += invested_amount
        
        return total_invested
    
    def get_unrealized_pnl(self, positions: Dict, current_prices: Optional[Dict] = None) -> float:
        """Простой расчет нереализованного P&L"""
        if not current_prices:
            return 0.0
        
        total_unrealized = 0.0
        
        for symbol, position in positions.items():
            if symbol not in current_prices:
                continue
            
            current_price = current_prices[symbol]
            remaining_quantity = position.get_remaining_quantity()
            
            if remaining_quantity <= 0:
                continue
            
            # Простой расчет P&L
            if position.direction == 'buy':
                pnl = remaining_quantity * (current_price - position.entry_price)
            else:
                pnl = remaining_quantity * (position.entry_price - current_price)
            
            total_unrealized += pnl
        
        return total_unrealized
    
    def get_current_balance(self, positions: Dict, current_prices: Optional[Dict] = None) -> float:
        """ЕДИНСТВЕННЫЙ метод расчета текущего баланса"""
        invested_capital = self.get_invested_capital(positions)
        unrealized_pnl = self.get_unrealized_pnl(positions, current_prices)
        
        # Простая формула: доступный + инвестированный + нереализованный
        total_balance = self.available_balance + invested_capital + unrealized_pnl
        
        return total_balance
    
    def can_open_new_position(self, positions: Dict) -> Tuple[bool, str]:
        """Проверка возможности открытия позиции"""
        # Проверка доступного баланса
        if self.available_balance < self.position_size_usd:
            return False, "insufficient_balance"
        
        # Проверка лимита экспозиции
        current_invested = self.get_invested_capital(positions)
        would_be_invested = current_invested + self.position_size_usd
        
        if would_be_invested > self.max_exposure_usd:
            return False, "exposure_limit"
        
        return True, "ok"
    
    def reserve_funds(self, amount: float) -> bool:
        """Резервирует средства для новой позиции"""
        if self.available_balance >= amount:
            self.available_balance -= amount
            self.total_invested += amount
            
            logger.debug(f"[RESERVE] ${amount:.0f} зарезервировано, доступно: ${self.available_balance:.0f}")
            return True
        
        return False
    
    def release_funds(self, amount: float, pnl: float = 0) -> None:
        """Освобождает средства после закрытия позиции"""
        self.available_balance += amount + pnl
        self.total_invested -= amount
        self.total_realized_pnl += pnl
        
        logger.debug(f"[RELEASE] ${amount:.0f} + P&L ${pnl:+.0f} = ${amount + pnl:.0f}, доступно: ${self.available_balance:.0f}")
    
    def get_balance_summary(self, positions: Dict, current_prices: Optional[Dict] = None) -> Dict:
        """Простая сводка баланса"""
        invested_capital = self.get_invested_capital(positions)
        unrealized_pnl = self.get_unrealized_pnl(positions, current_prices)
        current_balance = self.get_current_balance(positions, current_prices)
        
        balance_change = current_balance - self.initial_balance
        balance_percent = (balance_change / self.initial_balance) * 100 if self.initial_balance > 0 else 0
        exposure_percent = (invested_capital / self.initial_balance) * 100 if self.initial_balance > 0 else 0
        
        return {
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
            'total_realized_pnl': self.total_realized_pnl
        }
    
    def check_risk_limits(self, positions: Dict) -> Dict:
        """Простая проверка рисков"""
        balance_summary = self.get_balance_summary(positions)
        warnings = []
        
        # Проверка экспозиции
        if balance_summary['exposure_percent'] > self.max_exposure_percent * 0.9:
            warnings.append(f"Высокая экспозиция: {balance_summary['exposure_percent']:.1f}%")
        
        # Проверка баланса
        if self.available_balance < self.position_size_usd:
            warnings.append("Недостаточно средств для новых позиций")
        
        # Проверка потерь
        if balance_summary['balance_percent'] < -20:
            warnings.append(f"Критические потери: {balance_summary['balance_percent']:.1f}%")
        
        risk_level = 'CRITICAL' if any('Критические' in w for w in warnings) else \
                    'HIGH' if len(warnings) > 1 else \
                    'MEDIUM' if warnings else 'LOW'
        
        return {
            'warnings': warnings,
            'risk_level': risk_level,
            'balance_summary': balance_summary
        }
    
    def validate_state(self) -> Dict:
        """Простая валидация состояния"""
        issues = []
        
        # Базовые проверки
        if self.available_balance < 0:
            issues.append("Отрицательный доступный баланс")
        
        if self.total_invested < 0:
            issues.append("Отрицательный инвестированный капитал")
        
        # Проверка суммы
        theoretical_total = self.initial_balance + self.total_realized_pnl
        actual_total = self.available_balance + self.total_invested
        
        if abs(theoretical_total - actual_total) > 1.0:  # Допуск $1
            issues.append(f"Несоответствие баланса: теория ${theoretical_total:.2f} vs факт ${actual_total:.2f}")
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'available_balance': self.available_balance,
            'total_invested': self.total_invested,
            'total_realized_pnl': self.total_realized_pnl
        }