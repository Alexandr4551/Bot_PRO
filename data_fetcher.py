import aiohttp
import pandas as pd
import numpy as np
import asyncio
import logging
import time
import os
from datetime import datetime, timedelta, timezone
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from ta.volume import VolumeWeightedAveragePrice, OnBalanceVolumeIndicator
from ta.trend import MACD
from sklearn.preprocessing import StandardScaler
import json
import pytz

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("data_fetcher.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('DataFetcher')
logger.setLevel(logging.INFO)

# Конфигурация
CONFIG = {
    "SYMBOLS": ['BTCUSDT', 'ETHUSDT'],
    "TIMEFRAMES": [15, 30, 60],
    "DATA_DIR": 'historical_data',
    "MAX_RETRIES": 5,
    "REQUEST_INTERVAL": 0.3,
    "FEATURE_CONFIG": {
        "rsi_window": 14,
        "bb_window": 20,
        "vwap_window": 20,
        "obv_window": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "atr_window": 14,
        "target_threshold": 0.005  # 0.5% для определения движения
    }
}

os.makedirs(CONFIG["DATA_DIR"], exist_ok=True)

class EnhancedDataFetcher:
    BASE_URL = "https://api.bybit.com"
    
    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.last_request_time = 0
        self.request_interval = CONFIG["REQUEST_INTERVAL"]
        self.data_quality_report = []
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()
        # Сохраняем отчет о качестве данных
        report_file = f"{CONFIG['DATA_DIR']}/data_quality_report_{datetime.now().strftime('%Y%m%d')}.json"
        try:
            with open(report_file, "w") as f:
                json.dump(self.data_quality_report, f, indent=2, default=self.json_serializer)
        except Exception as e:
            logger.error(f"Ошибка сохранения отчета: {str(e)}")
    
    def json_serializer(self, obj):
        """Кастомный сериализатор для numpy типов"""
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
    
    async def _rate_limited_request(self, method, endpoint, **kwargs):
        # Улучшенный механизм повторных попыток
        retries = 0
        max_retries = CONFIG["MAX_RETRIES"]
        
        while retries <= max_retries:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.request_interval:
                await asyncio.sleep(self.request_interval - elapsed)
            
            self.last_request_time = time.time()
            url = f"{self.BASE_URL}{endpoint}"
            
            try:
                async with self.session.request(
                    method, url, 
                    timeout=aiohttp.ClientTimeout(total=15),
                    **kwargs
                ) as response:
                    if response.status == 429:
                        retry_after = int(response.headers.get('Retry-After', 5))
                        logger.warning(f"Rate limit exceeded. Retrying after {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        continue
                        
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                logger.warning(f"Сетевая ошибка ({retries}/{max_retries}): {str(e)}")
                if retries >= max_retries:
                    logger.error(f"Не удалось выполнить запрос после {max_retries} попыток")
                    return None
                retries += 1
                await asyncio.sleep(2 ** retries)  # Экспоненциальная задержка
            except Exception as e:
                logger.error(f"Критическая ошибка: {str(e)}")
                return None
        return None
    
    async def fetch_ohlcv(self, symbol: str, interval: int, start_time: int = None, end_time: int = None, limit: int = 1000) -> pd.DataFrame:
        """Получение исторических данных OHLCV с улучшенной обработкой"""
        endpoint = "/v5/market/kline"
        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        if start_time:
            params["start"] = start_time
        if end_time:
            params["end"] = end_time
        
        data = await self._rate_limited_request("GET", endpoint, params=params)
        
        if not data:
            logger.error(f"Пустой ответ для {symbol}-{interval}мин")
            return pd.DataFrame()
        
        if 'retCode' in data and data['retCode'] != 0:
            error_msg = data.get('retMsg', 'Неизвестная ошибка API')
            logger.error(f"API ошибка {symbol}-{interval}мин: {error_msg}")
            return pd.DataFrame()
        
        if not data.get('result') or not data['result'].get('list'):
            logger.warning(f"Нет данных для {symbol}-{interval}мин")
            return pd.DataFrame()
        
        try:
            # Обработка разных форматов ответа
            columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']
            if len(data['result']['list'][0]) > len(columns):
                columns.append('extra')
            
            df = pd.DataFrame(data['result']['list'], columns=columns)
            df = df.drop(columns=['extra'], errors='ignore')
            
            # Конвертация типов
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'turnover']
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
            df['timestamp'] = pd.to_datetime(df['timestamp'].astype('int64'), unit='ms')
            
            # Приведение к UTC
            df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
            
            df['symbol'] = symbol
            df['timeframe'] = f"{interval}min"
            
            return df.sort_values('timestamp').reset_index(drop=True)
        except Exception as e:
            logger.exception(f"Ошибка обработки данных для {symbol}-{interval}мин: {str(e)}")
            return pd.DataFrame()
    
    async def fetch_ohlcv_period(self, symbol: str, interval: int, days: int) -> pd.DataFrame:
        """Улучшенный сбор данных с проверкой качества"""
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=days)
        current_end = int(end_dt.timestamp() * 1000)
        start_ts = int(start_dt.timestamp() * 1000)
        
        all_dfs = []
        retry_count = 0
        
        logger.info(f"Начало загрузки {symbol}-{interval}мин за {days} дней ({start_dt} - {end_dt})")
        
        while current_end > start_ts and retry_count < CONFIG["MAX_RETRIES"]:
            df = await self.fetch_ohlcv(
                symbol=symbol,
                interval=interval,
                end_time=current_end,
                limit=1000
            )
            
            if df.empty:
                retry_count += 1
                logger.warning(f"Пустые данные ({retry_count}/{CONFIG['MAX_RETRIES']}), повтор через 5 сек...")
                await asyncio.sleep(5)
                continue
            
            retry_count = 0
            
            min_ts = df['timestamp'].min()
            min_ts_ms = int(min_ts.timestamp() * 1000)
            
            if min_ts_ms < start_ts:
                df = df[df['timestamp'] >= pd.Timestamp(start_ts, unit='ms', tz='UTC')]
                all_dfs.append(df)
                break
            
            all_dfs.append(df)
            current_end = min_ts_ms - 1
            
            # Прогресс
            progress = (1 - (current_end - start_ts) / (end_dt.timestamp()*1000 - start_ts)) * 100
            logger.info(f"{symbol}-{interval}мин: загружено {len(df)} свечей, прогресс: {progress:.1f}%")
            
            await asyncio.sleep(self.request_interval)
        
        if not all_dfs:
            logger.error(f"Не удалось загрузить данные для {symbol}-{interval}мин")
            return pd.DataFrame()
        
        full_df = pd.concat(all_dfs).sort_values('timestamp').reset_index(drop=True)
        
        # Проверка качества данных
        quality = self.check_data_quality(full_df, symbol, interval)
        self.data_quality_report.append(quality)
        logger.info(f"Качество данных {symbol}-{interval}мин: "
                    f"Пропуски: {quality['missing']}%, Дубликаты: {quality['duplicates']}, "
                    f"Полнота: {quality['completeness']}%")
        
        return full_df
    
    def check_data_quality(self, df, symbol, interval):
        """Расширенная проверка качества данных"""
        if df.empty:
            return {
                "symbol": symbol,
                "interval": interval,
                "status": "EMPTY",
                "missing": 100,
                "duplicates": 0,
                "completeness": 0
            }
        
        # Проверка пропущенных временных меток
        expected_freq = f"{interval}min"
        full_range = pd.date_range(
            start=df['timestamp'].min(), 
            end=df['timestamp'].max(), 
            freq=expected_freq
        )
        missing = len(full_range) - len(df)
        missing_percent = (missing / len(full_range)) * 100 if len(full_range) > 0 else 0
        
        # Проверка дубликатов
        duplicates = df.duplicated(subset=['timestamp']).sum()
        
        # Проверка полноты данных
        completeness = 100 - missing_percent
        
        return {
            "symbol": symbol,
            "interval": interval,
            "status": "OK" if completeness > 98 else "WARNING",
            "start_date": df['timestamp'].min().strftime('%Y-%m-%d %H:%M:%S%z'),
            "end_date": df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S%z'),
            "rows": int(len(df)),
            "expected_rows": int(len(full_range)),
            "missing": round(missing_percent, 2),
            "duplicates": int(duplicates),
            "completeness": round(completeness, 2),
            "zero_volume": int((df['volume'] == 0).sum()),
            "null_values": {k: int(v) for k, v in df.isnull().sum().items()}
        }
    
    async def fetch_multiple(self, symbols, timeframes, days=30):
        """Параллельный сбор данных"""
        tasks = []
        for symbol in symbols:
            for tf in timeframes:
                logger.info(f"Добавлена задача: {symbol}-{tf}мин за {days} дней")
                tasks.append(self.fetch_and_process(symbol, tf, days))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid_results = []
        
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Ошибка в задаче: {str(res)}")
            elif not res.empty:
                valid_results.append(res)
        
        return pd.concat(valid_results) if valid_results else pd.DataFrame()
    
    async def fetch_and_process(self, symbol, tf, days):
        """Обработка одного набора данных"""
        logger.info(f"Запуск загрузки: {symbol}-{tf}мин")
        
        try:
            df = await self.fetch_ohlcv_period(symbol, tf, days)
            if df.empty:
                logger.warning(f"Пустые данные для {symbol}-{tf}мин")
                return pd.DataFrame()
            
            # Генерация фичей
            df = self.generate_features(df, tf)
            
            if df.empty:
                logger.warning(f"После генерации фичей данные пусты для {symbol}-{tf}мин")
                return pd.DataFrame()
            
            # Сохранение данных
            filename_prefix = f"{CONFIG['DATA_DIR']}/{symbol}_{tf}min_{days}days_{datetime.now().strftime('%Y%m%d')}"
            
            # Parquet
            parquet_filename = f"{filename_prefix}.parquet"
            df.to_parquet(parquet_filename)
            logger.info(f"Сохранено {len(df)} свечей в {parquet_filename}")
            
            # Даты
            txt_filename = f"{filename_prefix}_dates.txt"
            self.save_dates_to_txt(df, txt_filename)
            
            # Метаданные
            meta_filename = f"{filename_prefix}_meta.json"
            self.save_metadata(df, meta_filename)
            
            return df
        except Exception as e:
            logger.exception(f"Ошибка обработки {symbol}-{tf}мин: {str(e)}")
            return pd.DataFrame()
    
    def save_dates_to_txt(self, df, filename):
        """Сохранение списка дат"""
        if df.empty:
            return
        
        dates = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S %Z')
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Список свечей: {len(df)}\n")
            f.write(f"Первая свеча: {dates.iloc[0]}\n")
            f.write(f"Последняя свеча: {dates.iloc[-1]}\n")
            f.write("=" * 50 + "\n")
            for date_str in dates:
                f.write(f"{date_str}\n")
        logger.info(f"Список дат сохранён в {filename}")
    
    def save_metadata(self, df, filename):
        """Сохранение метаданных о данных"""
        if df.empty:
            return
        
        metadata = {
            "symbol": df['symbol'].iloc[0],
            "timeframe": df['timeframe'].iloc[0],
            "start_date": df['timestamp'].min().strftime('%Y-%m-%d %H:%M:%S%z'),
            "end_date": df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S%z'),
            "rows": int(len(df)),
            "columns": list(df.columns),
            "features": list(set(df.columns) - {'timestamp', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume'}),
            "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S%z'),
            "config": CONFIG["FEATURE_CONFIG"]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, default=self.json_serializer)
        
        logger.info(f"Метаданные сохранены в {filename}")
    
    def generate_features(self, df, timeframe):
        """Улучшенная генерация фичей для ML с учетом таймфрейма"""
        if df.empty or len(df) < 100:
            logger.warning(f"Недостаточно данных для генерации фичей: {len(df)} строк")
            return df
        
        try:
            # Основные преобразования
            df['returns'] = df['close'].pct_change()
            df['volatility'] = df['returns'].rolling(20).std()
            df['high_low_spread'] = (df['high'] - df['low']) / df['open']
            
            # 1. Momentum индикаторы
            df['rsi'] = RSIIndicator(df['close'], window=CONFIG["FEATURE_CONFIG"]["rsi_window"]).rsi()
            
            # 2. Volatility индикаторы
            bb = BollingerBands(df['close'], window=CONFIG["FEATURE_CONFIG"]["bb_window"])
            df['bb_upper'] = bb.bollinger_hband()
            df['bb_middle'] = bb.bollinger_mavg()
            df['bb_lower'] = bb.bollinger_lband()
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            
            # 3. Volume индикаторы
            df['vwap'] = VolumeWeightedAveragePrice(
                high=df['high'],
                low=df['low'],
                close=df['close'],
                volume=df['volume'],
                window=CONFIG["FEATURE_CONFIG"]["vwap_window"]
            ).volume_weighted_average_price()
            
            df['obv'] = OnBalanceVolumeIndicator(
                close=df['close'],
                volume=df['volume']
            ).on_balance_volume()
            
            # 4. Трендовые индикаторы
            df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
            df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
            df['ema_ratio'] = df['ema_20'] / df['ema_50']
            
            # 5. MACD с обработкой ошибок
            try:
                macd = MACD(
                    close=df['close'],
                    window_slow=CONFIG["FEATURE_CONFIG"]["macd_slow"],
                    window_fast=CONFIG["FEATURE_CONFIG"]["macd_fast"],
                    window_sign=CONFIG["FEATURE_CONFIG"]["macd_signal"]
                )
                df['macd'] = macd.macd()
                df['macd_signal'] = macd.macd_signal()
                df['macd_diff'] = macd.macd_diff()
            except Exception as e:
                logger.error(f"Ошибка генерации MACD: {str(e)}")
            
            # 6. Циклические фичи
            df['hour'] = df['timestamp'].dt.hour
            df['day_of_week'] = df['timestamp'].dt.dayofweek
            df['month'] = df['timestamp'].dt.month
            
            # 7. Ценовые действия
            df['body_size'] = (df['close'] - df['open']) / df['open']
            df['upper_shadow'] = (df['high'] - np.maximum(df['close'], df['open'])) / df['open']
            df['lower_shadow'] = (np.minimum(df['close'], df['open']) - df['low']) / df['open']
            
            # 8. Целевые переменные с учетом таймфрейма
            if timeframe == 15:
                horizon = 4  # Для 15-минутного таймфрейма - 4 периода (1 час)
                df['price_change_1h'] = df['close'].pct_change(horizon).shift(-horizon)
                df['price_change_4h'] = df['close'].pct_change(16).shift(-16)  # 4 часа
            elif timeframe == 30:
                horizon = 2  # Для 30-минутного - 2 периода (1 час)
                df['price_change_1h'] = df['close'].pct_change(horizon).shift(-horizon)
                df['price_change_4h'] = df['close'].pct_change(8).shift(-8)  # 4 часа
            else:  # 60 минут
                horizon = 1  # Для 60-минутного - 1 период (1 час)
                df['price_change_1h'] = df['close'].pct_change(horizon).shift(-horizon)
                df['price_change_4h'] = df['close'].pct_change(4).shift(-4)  # 4 часа
            
            # Используем price_change_1h для классификации
            threshold = CONFIG["FEATURE_CONFIG"]["target_threshold"]
            conditions = [
                df['price_change_1h'] > threshold,
                df['price_change_1h'] < -threshold,
                (df['price_change_1h'] >= -threshold) & 
                (df['price_change_1h'] <= threshold)
            ]
            choices = [2, 0, 1]  # 2: рост, 1: боковик, 0: падение
            df['target_class'] = np.select(conditions, choices, default=1)
            
            # Удаляем временные колонки и NaN
            price_change_cols = [col for col in df.columns if 'price_change_' in col]
            df = df.drop(columns=price_change_cols)
            df = df.dropna()
            
            # Нормализация
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            exclude_cols = {'target_class', 'symbol', 'timeframe', 'hour', 'day_of_week', 'month'}
            numeric_cols = [col for col in numeric_cols if col not in exclude_cols]
            
            if numeric_cols:
                scaler = StandardScaler()
                df[numeric_cols] = scaler.fit_transform(df[numeric_cols])
            
            return df
        except Exception as e:
            logger.exception(f"Ошибка генерации фичей: {str(e)}")
            return df

async def main():
    logger.info("Запуск улучшенного сбора данных для торговой модели")
    start_time = time.time()
    
    async with EnhancedDataFetcher() as fetcher:
        await fetcher.fetch_multiple(
            symbols=CONFIG["SYMBOLS"],
            timeframes=CONFIG["TIMEFRAMES"],
            days=730  # 2 года данных
        )
    
    duration = time.time() - start_time
    logger.info(f"Сбор данных завершен за {duration:.2f} секунд")

if __name__ == "__main__":
    asyncio.run(main())