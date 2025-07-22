# virtual_trading/services/balance_manager.py
"""
Сервис управления балансом и экспозицией
Интегрируется с существующей конфигурацией из config/
"""

import logging
from typing import Dict, Tuple, Optional

# Используем существующую конфигурацию
from config import ANTISPAM_CONFIG

logger = logging.getLogger('VirtualTrader.BalanceManager')

class BalanceManager:
    """Управляет балансом и экспозицией виртуального трейдера"""
    
    def __init__(self, initial_balance: float, position_size_percent: float, max_exposure_percent: float):
        self.initial_balance = initial_balance
        self.available_balance = initial_balance
        self.position_size_percent = position_size_percent
        self.position_size_usd = initial_balance * (position_size_percent / 100)
        self.max_exposure_percent = max_exposure_percent
        self.max_exposure_usd = initial_balance * (max_exposure_percent / 100)
        
        logger.info(f"[INIT] BalanceManager инициализирован:")
        logger.info(f"   Начальный баланс: ${self.initial_balance:,.2f}")
        logger.info(f"   Размер позиции: {self.position_size_percent}% (${self.position_size_usd:,.0f})")
        logger.info(f"   Максимальная экспозиция: {self.max_exposure_percent}% (${self.max_exposure_usd:,.0f})")
    
    def get_invested_capital(self, positions: Dict) -> float:
        """Расчет инвестированного капитала с учетом частичных закрытий"""
        total_invested = 0
        for position in positions.values():
            remaining_percent = position.get_remaining_percent()
            
            if remaining_percent > 0:
                total_invested += self.position_size_usd * (remaining_percent / 100)
        
        logger.debug(f"[BALANCE] Инвестированный капитал: ${total_invested:,.2f}")
        return total_invested
    
    def get_unrealized_pnl(self, positions: Dict, current_prices: Optional[Dict] = None) -> float:
        """Расчет нереализованной прибыли/убытка"""
        if not current_prices:
            logger.debug("[BALANCE] Текущие цены не предоставлены, нереализованный P&L = 0")
            return 0.0
            
        total_unrealized_pnl = 0.0
        
        for symbol, position in positions.items():
            if symbol not in current_prices:
                logger.debug(f"[BALANCE] Нет текущей цены для {symbol}")
                continue
                
            current_price = current_prices[symbol]
            remaining_quantity = position.get_remaining_quantity()
            
            if remaining_quantity <= 0:
                logger.debug(f"[BALANCE] {symbol}: позиция полностью закрыта")
                continue
                
            if position.direction == 'buy':
                unrealized_pnl = remaining_quantity * (current_price - position.entry_price)
            else:
                unrealized_pnl = remaining_quantity * (position.entry_price - current_price)
            
            logger.debug(f"[BALANCE] {symbol}: нереализ. P&L ${unrealized_pnl:+.2f} "
                        f"(цена ${current_price:.5f}, вход ${position.entry_price:.5f}, "
                        f"остаток {remaining_quantity:.6f})")
            
            total_unrealized_pnl += unrealized_pnl
            
        logger.debug(f"[BALANCE] Общий нереализованный P&L: ${total_unrealized_pnl:+,.2f}")
        return total_unrealized_pnl
    
    def get_current_balance(self, positions: Dict, current_prices: Optional[Dict] = None) -> float:
        """Расчет текущего баланса"""
        invested_capital = self.get_invested_capital(positions)
        unrealized_pnl = self.get_unrealized_pnl(positions, current_prices)
        total_balance = self.available_balance + invested_capital + unrealized_pnl
        
        logger.debug(f"[BALANCE] Компоненты баланса: доступно ${self.available_balance:,.2f} + "
                    f"инвестировано ${invested_capital:,.2f} + нереализ. ${unrealized_pnl:+,.2f} = "
                    f"итого ${total_balance:,.2f}")
        
        return total_balance
    
    def can_open_new_position(self, positions: Dict) -> Tuple[bool, str]:
        """Проверка возможности открытия новой позиции"""
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
        
        logger.debug(f"[OK] Можно открыть позицию: доступно ${self.available_balance:.2f}, "
                    f"экспозиция будет ${would_be_invested:.2f}/{self.max_exposure_usd:.2f}")
        return True, "ok"
    
    def reserve_funds(self, amount: float) -> bool:
        """Резервирует средства для новой позиции"""
        if self.available_balance >= amount:
            old_balance = self.available_balance
            self.available_balance -= amount
            logger.info(f"[BALANCE] Баланс изменен: ${old_balance:.2f} → ${self.available_balance:.2f} "
                       f"(резерв ${amount:.2f})")
            return True
        
        logger.error(f"[ERROR] Не удалось зарезервировать ${amount:.2f}, доступно ${self.available_balance:.2f}")
        return False
    
    def release_funds(self, amount: float, pnl: float = 0) -> None:
        """Освобождает средства после закрытия позиции"""
        old_balance = self.available_balance
        self.available_balance += amount + pnl
        logger.info(f"[BALANCE] Баланс обновлен: ${old_balance:.2f} + ${amount:.2f} + ${pnl:+.2f} = ${self.available_balance:.2f}")
    
    def get_balance_summary(self, positions: Dict, current_prices: Optional[Dict] = None) -> Dict:
        """Возвращает сводку по балансу для отображения"""
        invested_capital = self.get_invested_capital(positions)
        unrealized_pnl = self.get_unrealized_pnl(positions, current_prices)
        current_balance = self.get_current_balance(positions, current_prices)
        
        exposure_percent = (invested_capital / self.initial_balance) * 100
        balance_change = current_balance - self.initial_balance
        balance_percent = (balance_change / self.initial_balance) * 100
        
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
            'position_size_usd': self.position_size_usd
        }
    
    def check_risk_limits(self, positions: Dict) -> Dict:
        """Проверяет соблюдение риск-лимитов"""
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
        
        return {
            'warnings': warnings,
            'risk_level': 'HIGH' if len(warnings) > 1 else 'MEDIUM' if warnings else 'LOW',
            'balance_summary': balance_summary
        }