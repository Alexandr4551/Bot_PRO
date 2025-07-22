# core/bybit_api.py
"""
API клиент для Bybit Futures с улучшенной точностью цен
"""

import aiohttp
import pandas as pd
import asyncio
import time
import logging

from config import PRICE_PRECISION

logger = logging.getLogger(__name__)

class BybitFuturesAPI:
    """API клиент для Bybit Futures"""
    
    BASE_URL = "https://api.bybit.com"
    
    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.last_request_time = 0
        self.request_interval = 0.1
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()
    
    async def _rate_limited_request(self, method, endpoint, **kwargs):
        """Запрос с ограничением частоты"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_interval:
            await asyncio.sleep(self.request_interval - elapsed)
        
        self.last_request_time = time.time()
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Ошибка запроса: {str(e)}")
            return None
    
    def _format_price(self, price):
        """Форматирование цены с повышенной точностью"""
        try:
            # Округляем до 5 знаков после запятой
            return round(float(price), 5)
        except:
            return float(price)
    
    async def get_ohlcv(self, symbol: str, interval: int, limit: int = 500) -> pd.DataFrame:
        """Получение исторических данных OHLCV с улучшенной точностью"""
        endpoint = "/v5/market/kline"
        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        data = await self._rate_limited_request("GET", endpoint, params=params)
        
        if not data or 'retCode' in data and data['retCode'] != 0:
            error_msg = data.get('retMsg', 'Неизвестная ошибка API') if data else 'Нет данных'
            logger.error(f"Ошибка получения OHLCV для {symbol}: {error_msg}")
            return pd.DataFrame()
        
        if 'result' in data and 'list' in data['result']:
            df = pd.DataFrame(
                data['result']['list'],
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']
            )
            
            # Конвертация с повышенной точностью
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'turnover']
            for col in numeric_cols:
                if col in ['open', 'high', 'low', 'close']:
                    # Для цен используем повышенную точность
                    df[col] = df[col].apply(lambda x: self._format_price(x))
                else:
                    # Для объемов оставляем как есть
                    df[col] = pd.to_numeric(df[col])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'].astype('int64'), unit='ms')
            return df.sort_values('timestamp').reset_index(drop=True)
        
        return pd.DataFrame()
    
    async def get_current_price(self, symbol: str) -> float:
        """Получение текущей цены с повышенной точностью"""
        endpoint = "/v5/market/tickers"
        params = {"category": "linear", "symbol": symbol}
        
        data = await self._rate_limited_request("GET", endpoint, params=params)
        
        if data and 'result' in data and 'list' in data['result'] and data['result']['list']:
            price = data['result']['list'][0]['lastPrice']
            return self._format_price(price)
        return 0.0
    
    async def get_orderbook(self, symbol: str, limit: int = 25):
        """Получение стакана заявок (опционально для будущего использования)"""
        endpoint = "/v5/market/orderbook"
        params = {
            "category": "linear", 
            "symbol": symbol,
            "limit": limit
        }
        
        data = await self._rate_limited_request("GET", endpoint, params=params)
        
        if data and 'result' in data:
            return data['result']
        return None
    
    async def get_symbol_info(self, symbol: str):
        """Получение информации о символе (опционально)"""
        endpoint = "/v5/market/instruments-info"
        params = {
            "category": "linear",
            "symbol": symbol
        }
        
        data = await self._rate_limited_request("GET", endpoint, params=params)
        
        if data and 'result' in data and 'list' in data['result']:
            return data['result']['list'][0] if data['result']['list'] else None
        return None