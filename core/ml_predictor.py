# core/ml_predictor.py
"""
ML модель для предсказания движения цен
"""

import pandas as pd
import numpy as np
import joblib
import glob
import os
import logging
from datetime import datetime
from ta.momentum import RSIIndicator, StochasticOscillator, WilliamsRIndicator
from ta.trend import ADXIndicator, CCIIndicator
from ta.volatility import AverageTrueRange
from ta.volume import AccDistIndexIndicator, ChaikinMoneyFlowIndicator

from config import ML_CONFIG

logger = logging.getLogger(__name__)

class MLPredictor:
    """Класс для работы с обученной ML моделью"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.selected_features = None
        self.model_loaded = False
        self.last_prediction = None
        
    def load_model(self):
        """Загрузка обученной модели"""
        try:
            model_patterns = [
                f"{ML_CONFIG['MODEL_PATH']}/final_*_model_*.pkl",
                f"{ML_CONFIG['MODEL_PATH']}/quality_*_model_*.pkl",
                f"{ML_CONFIG['MODEL_PATH']}/advanced_*_model_*.pkl"
            ]
            
            all_models = []
            for pattern in model_patterns:
                all_models.extend(glob.glob(pattern))
            
            if not all_models:
                logger.warning("ML модели не найдены, используется только теханализ")
                return False
            
            latest_model = max(all_models, key=os.path.getctime)
            logger.info(f"Загрузка ML модели: {os.path.basename(latest_model)}")
            
            model_package = joblib.load(latest_model)
            
            if isinstance(model_package, dict):
                self.model = model_package['model']
                self.scaler = model_package.get('scaler')
                self.selected_features = model_package.get('selected_features')
                model_type = model_package.get('model_type', 'unknown')
            else:
                self.model = model_package
                model_type = 'legacy'
            
            self.model_loaded = True
            logger.info(f"ML модель {model_type.upper()} загружена успешно")
            logger.info(f"Ожидается {len(self.selected_features)} признаков" if self.selected_features else "Признаки: автоопределение")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки ML модели: {str(e)}")
            return False
    
    def generate_features(self, df):
        """Генерация признаков идентично обучению"""
        try:
            if len(df) < 50:
                logger.warning("Недостаточно данных для генерации ML признаков")
                return None
            
            # Создаем копию для работы
            df_work = df.copy()
            
            # Устанавливаем timestamp как индекс
            if 'timestamp' in df_work.columns:
                df_work = df_work.set_index('timestamp')
                df_work.index = pd.to_datetime(df_work.index)
            
            # Проверяем наличие необходимых колонок
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df_work.columns:
                    logger.error(f"Отсутствует колонка {col}")
                    return None
            
            # Технические индикаторы с обработкой ошибок
            try:
                df_work['rsi'] = RSIIndicator(df_work['close'], window=14).rsi()
            except:
                df_work['rsi'] = 50.0
                
            try:
                df_work['stoch_k'] = StochasticOscillator(df_work['high'], df_work['low'], df_work['close']).stoch()
            except:
                df_work['stoch_k'] = 50.0
                
            try:
                df_work['williams_r'] = WilliamsRIndicator(df_work['high'], df_work['low'], df_work['close']).williams_r()
            except:
                df_work['williams_r'] = -50.0
                
            try:
                df_work['adx'] = ADXIndicator(df_work['high'], df_work['low'], df_work['close']).adx()
            except:
                df_work['adx'] = 25.0
                
            try:
                df_work['cci'] = CCIIndicator(df_work['high'], df_work['low'], df_work['close']).cci()
            except:
                df_work['cci'] = 0.0
                
            try:
                df_work['atr'] = AverageTrueRange(df_work['high'], df_work['low'], df_work['close']).average_true_range()
            except:
                df_work['atr'] = df_work['close'] * 0.02
                
            try:
                df_work['adi'] = AccDistIndexIndicator(df_work['high'], df_work['low'], df_work['close'], df_work['volume']).acc_dist_index()
            except:
                df_work['adi'] = 0.0
                
            try:
                df_work['cmf'] = ChaikinMoneyFlowIndicator(df_work['high'], df_work['low'], df_work['close'], df_work['volume']).chaikin_money_flow()
            except:
                df_work['cmf'] = 0.0
            
            # Статистические признаки
            for window in [5, 20, 50]:
                try:
                    df_work[f'close_mean_{window}'] = df_work['close'].rolling(window, min_periods=1).mean()
                    df_work[f'close_std_{window}'] = df_work['close'].rolling(window, min_periods=1).std()
                    df_work[f'close_rank_{window}'] = df_work['close'].rolling(window, min_periods=1).rank(pct=True)
                    
                    rolling_min = df_work['close'].rolling(window, min_periods=1).min()
                    rolling_max = df_work['close'].rolling(window, min_periods=1).max()
                    df_work[f'close_position_{window}'] = (df_work['close'] - rolling_min) / (rolling_max - rolling_min + 1e-8)
                except:
                    df_work[f'close_mean_{window}'] = df_work['close']
                    df_work[f'close_std_{window}'] = 0.0
                    df_work[f'close_rank_{window}'] = 0.5
                    df_work[f'close_position_{window}'] = 0.5
            
            # Ценовые признаки
            for lag in [1, 3, 5, 10]:
                try:
                    df_work[f'momentum_{lag}'] = df_work['close'].pct_change(lag)
                    df_work[f'volume_momentum_{lag}'] = df_work['volume'].pct_change(lag)
                except:
                    df_work[f'momentum_{lag}'] = 0.0
                    df_work[f'volume_momentum_{lag}'] = 0.0
            
            # Дополнительные признаки
            try:
                df_work['body_size'] = abs(df_work['close'] - df_work['open']) / (df_work['close'] + 1e-8)
                df_work['upper_shadow'] = (df_work['high'] - np.maximum(df_work['close'], df_work['open'])) / (df_work['close'] + 1e-8)
                df_work['lower_shadow'] = (np.minimum(df_work['close'], df_work['open']) - df_work['low']) / (df_work['close'] + 1e-8)
                df_work['hl_spread'] = (df_work['high'] - df_work['low']) / (df_work['close'] + 1e-8)
                df_work['volume_price_trend'] = df_work['volume'] * df_work['momentum_1']
            except:
                df_work['body_size'] = 0.01
                df_work['upper_shadow'] = 0.0
                df_work['lower_shadow'] = 0.0
                df_work['hl_spread'] = 0.02
                df_work['volume_price_trend'] = 0.0
            
            # Возвращаем с timestamp как колонка
            df_work = df_work.reset_index()
            
            return df_work
            
        except Exception as e:
            logger.error(f"Ошибка генерации ML признаков: {str(e)}")
            return None
    
    def prepare_features_for_prediction(self, df):
        """Подготовка признаков для предсказания"""
        try:
            # Удаляем служебные колонки
            exclude_cols = ['timestamp', 'symbol', 'timeframe', 'turnover', 'target_class', 'target_quality', 'target_simple', 'target_final']
            available_cols = [col for col in df.columns if col not in exclude_cols and df[col].dtype in ['float64', 'int64']]
            
            if self.selected_features:
                # Используем точно те же признаки, что были при обучении
                available_features = [f for f in self.selected_features if f in available_cols]
                
                if len(available_features) < len(self.selected_features) * 0.7:
                    logger.warning(f"Доступно только {len(available_features)} из {len(self.selected_features)} признаков")
                
                X = df[available_features].copy()
                
                # Добавляем отсутствующие признаки как нули
                missing_features = [f for f in self.selected_features if f not in available_features]
                for missing_feature in missing_features:
                    X[missing_feature] = 0.0
                
                # Переупорядочиваем в правильном порядке
                X = X[self.selected_features]
            else:
                # Автоматический выбор первых 35 числовых признаков
                X = df[available_cols[:35]].copy()
            
            # Обработка NaN и inf
            X = X.replace([np.inf, -np.inf], 0.0)
            X = X.fillna(0.0)
            
            # Масштабирование
            if self.scaler:
                try:
                    X_scaled = self.scaler.transform(X)
                    X = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)
                except Exception as e:
                    logger.warning(f"Ошибка масштабирования: {e}")
            
            return X.iloc[-1:].values
            
        except Exception as e:
            logger.error(f"Ошибка подготовки признаков: {str(e)}")
            return None
    
    def predict(self, df):
        """Генерация ML предсказания"""
        if not self.model_loaded:
            return None
        
        try:
            # Генерация признаков
            df_features = self.generate_features(df.copy())
            if df_features is None:
                return None
            
            # Подготовка для предсказания
            X = self.prepare_features_for_prediction(df_features)
            if X is None:
                return None
            
            # Предсказание
            y_pred = self.model.predict(X)[0]
            
            # Уверенность
            if hasattr(self.model, 'predict_proba'):
                y_proba = self.model.predict_proba(X)[0]
                confidence = np.max(y_proba)
            else:
                confidence = 0.6
            
            # Интерпретация классов
            class_names = {0: "Падение", 1: "Боковик", 2: "Рост"}
            prediction_name = class_names.get(y_pred, f"Класс {y_pred}")
            
            # Торговое направление
            if y_pred == 2 and confidence > ML_CONFIG['CONFIDENCE_THRESHOLD']:
                direction = 'buy'
            elif y_pred == 0 and confidence > ML_CONFIG['CONFIDENCE_THRESHOLD']:
                direction = 'sell'
            else:
                direction = None
            
            result = {
                'prediction': int(y_pred),
                'prediction_name': prediction_name,
                'confidence': float(confidence),
                'direction': direction,
                'timestamp': datetime.now()
            }
            
            self.last_prediction = result
            return result
            
        except Exception as e:
            logger.error(f"Ошибка ML предсказания: {str(e)}")
            return None