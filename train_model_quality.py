"""
ФИНАЛЬНАЯ РАБОЧАЯ ВЕРСИЯ - без проблем с ансамблем
Обучает качественные модели за 3-5 минут
"""
import pandas as pd
import numpy as np
import glob
import lightgbm as lgb
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
from sklearn.preprocessing import RobustScaler
import joblib
import logging
import os
import warnings
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
from ta.momentum import RSIIndicator, StochasticOscillator, WilliamsRIndicator
from ta.trend import ADXIndicator, CCIIndicator
from ta.volatility import AverageTrueRange
from ta.volume import AccDistIndexIndicator, ChaikinMoneyFlowIndicator
from datetime import datetime
import json
from tqdm import tqdm

warnings.filterwarnings('ignore')

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('FinalModelTrainer')

# ФИНАЛЬНАЯ КОНФИГУРАЦИЯ
CONFIG = {
    'MODEL_DIR': 'trained_models',
    'DATA_DIR': 'historical_data',
    'REPORTS_DIR': 'model_reports',
    'TEST_SIZE': 0.15,
    'VAL_SIZE': 0.15,
    'RANDOM_STATE': 42,
    'USE_SAMPLE': True,          
    'SAMPLE_SIZE': 80000,        
    'TOP_FEATURES': 35
}

# Создание директорий
for dir_name in [CONFIG['MODEL_DIR'], CONFIG['REPORTS_DIR']]:
    os.makedirs(dir_name, exist_ok=True)

class FinalFeatureEngineering:
    """Финальная версия генерации признаков"""
    
    def add_essential_indicators(self, df):
        """Добавление самых важных технических индикаторов"""
        try:
            logger.info("Генерация ключевых технических индикаторов...")
            
            # Momentum индикаторы
            df['rsi'] = RSIIndicator(df['close'], window=14).rsi()
            df['stoch_k'] = StochasticOscillator(df['high'], df['low'], df['close']).stoch()
            df['williams_r'] = WilliamsRIndicator(df['high'], df['low'], df['close']).williams_r()
            
            # Trend индикаторы
            df['adx'] = ADXIndicator(df['high'], df['low'], df['close']).adx()
            df['cci'] = CCIIndicator(df['high'], df['low'], df['close']).cci()
            
            # Volatility
            df['atr'] = AverageTrueRange(df['high'], df['low'], df['close']).average_true_range()
            
            # Volume
            df['adi'] = AccDistIndexIndicator(df['high'], df['low'], df['close'], df['volume']).acc_dist_index()
            df['cmf'] = ChaikinMoneyFlowIndicator(df['high'], df['low'], df['close'], df['volume']).chaikin_money_flow()
            
            return df
        except Exception as e:
            logger.error(f"Ошибка добавления технических индикаторов: {str(e)}")
            return df
    
    def add_statistical_features(self, df):
        """Добавление статистических признаков"""
        try:
            logger.info("Генерация статистических признаков...")
            
            for window in [5, 20, 50]:
                df[f'close_mean_{window}'] = df['close'].rolling(window).mean()
                df[f'close_std_{window}'] = df['close'].rolling(window).std()
                df[f'close_rank_{window}'] = df['close'].rolling(window).rank(pct=True)
                df[f'close_position_{window}'] = (df['close'] - df['close'].rolling(window).min()) / (
                    df['close'].rolling(window).max() - df['close'].rolling(window).min()
                )
            
            return df
        except Exception as e:
            logger.error(f"Ошибка добавления статистических признаков: {str(e)}")
            return df
    
    def add_price_action_features(self, df):
        """Добавление признаков ценового действия"""
        try:
            logger.info("Генерация признаков ценового действия...")
            
            for lag in [1, 3, 5, 10]:
                df[f'momentum_{lag}'] = df['close'].pct_change(lag)
                df[f'volume_momentum_{lag}'] = df['volume'].pct_change(lag)
            
            df['body_size'] = abs(df['close'] - df['open']) / df['close']
            df['upper_shadow'] = (df['high'] - np.maximum(df['close'], df['open'])) / df['close']
            df['lower_shadow'] = (np.minimum(df['close'], df['open']) - df['low']) / df['close']
            df['hl_spread'] = (df['high'] - df['low']) / df['close']
            df['volume_price_trend'] = df['volume'] * df['momentum_1']
            
            return df
        except Exception as e:
            logger.error(f"Ошибка добавления ценовых признаков: {str(e)}")
            return df
    
    def process_dataframe(self, df):
        """Обработка DataFrame"""
        logger.info("Генерация оптимизированных признаков...")
        
        if 'timestamp' in df.columns:
            df = df.set_index('timestamp')
            df.index = pd.to_datetime(df.index)
        
        df = self.add_essential_indicators(df)
        df = self.add_statistical_features(df)
        df = self.add_price_action_features(df)
        
        df = df.reset_index()
        logger.info(f"Создано {len(df.columns)} признаков")
        return df

class FinalModelTrainer:
    """Финальная система обучения моделей"""
    
    def __init__(self):
        self.models = {}
        self.scaler = None
        self.feature_engineering = FinalFeatureEngineering()
        
    def load_and_prepare_data(self, symbols=None, timeframes=None):
        """Загрузка и подготовка данных"""
        logger.info("Загрузка данных...")
        
        file_pattern = f"{CONFIG['DATA_DIR']}/*.parquet"
        files = glob.glob(file_pattern)
        
        if not files:
            raise FileNotFoundError(f"Нет данных в {CONFIG['DATA_DIR']}")
        
        dfs = []
        for file in tqdm(files, desc="Загрузка файлов"):
            if symbols or timeframes:
                filename = os.path.basename(file)
                parts = filename.split('_')
                symbol = parts[0]
                timeframe = parts[1].replace('min', '')
                
                if symbols and symbol not in symbols:
                    continue
                if timeframes and timeframe not in [str(tf) for tf in timeframes]:
                    continue
            
            df = pd.read_parquet(file)
            df = self.feature_engineering.process_dataframe(df)
            dfs.append(df)
            logger.info(f"Загружен {file} ({len(df)} строк)")
        
        full_df = pd.concat(dfs, ignore_index=True)
        
        if CONFIG['USE_SAMPLE'] and len(full_df) > CONFIG['SAMPLE_SIZE']:
            logger.info(f"Семплирование с {len(full_df)} до {CONFIG['SAMPLE_SIZE']} строк...")
            full_df = full_df.sample(n=CONFIG['SAMPLE_SIZE'], random_state=CONFIG['RANDOM_STATE'])
        
        logger.info(f"Финальный размер датасета: {len(full_df)} строк")
        return self.prepare_features(full_df)
    
    def prepare_features(self, df):
        """Подготовка признаков"""
        logger.info("Подготовка признаков...")
        df = self.create_target(df)
        
        drop_cols = ['timestamp', 'symbol', 'timeframe', 'turnover', 'target_class']
        df = df.drop(columns=[col for col in drop_cols if col in df.columns])
        
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.dropna()
        
        X = df.drop(columns=['target_final'])
        y = df['target_final']
        
        class_ratio = y.value_counts(normalize=True)
        logger.info(f"Распределение классов: {class_ratio.to_dict()}")
        
        return X, y
    
    def create_target(self, df):
        """Создание целевой переменной"""
        logger.info("Создание качественной целевой переменной...")
        
        df['price_change_15m'] = df['close'].pct_change(1).shift(-1)
        df['price_change_1h'] = df['close'].pct_change(4).shift(-4)
        df['price_change_4h'] = df['close'].pct_change(16).shift(-16)
        
        df['volatility_1h'] = df['close'].rolling(4).std()
        base_threshold = 0.003
        df['dynamic_threshold'] = base_threshold * (1 + df['volatility_1h'].fillna(0))
        
        conditions = [
            (df['price_change_15m'] > df['dynamic_threshold']) & 
            (df['price_change_1h'] > df['dynamic_threshold']) & 
            (df['price_change_4h'] > 0),
            
            (df['price_change_1h'] > df['dynamic_threshold']) & 
            (df['price_change_4h'] > -df['dynamic_threshold']),
            
            (df['price_change_15m'] < -df['dynamic_threshold']) & 
            (df['price_change_1h'] < -df['dynamic_threshold']) & 
            (df['price_change_4h'] < 0),
        ]
        
        choices = [2, 1, 0]
        df['target_final'] = np.select(conditions, choices, default=1)
        
        temp_cols = ['price_change_15m', 'price_change_1h', 'price_change_4h', 'volatility_1h', 'dynamic_threshold']
        df = df.drop(columns=temp_cols)
        
        return df
    
    def split_data_time_series(self, X, y):
        """Разделение данных с учетом временных рядов"""
        train_size = int(len(X) * (1 - CONFIG['TEST_SIZE'] - CONFIG['VAL_SIZE']))
        val_size = int(len(X) * CONFIG['VAL_SIZE'])
        
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]
        X_val = X.iloc[train_size:train_size + val_size]
        y_val = y.iloc[train_size:train_size + val_size]
        X_test = X.iloc[train_size + val_size:]
        y_test = y.iloc[train_size + val_size:]
        
        logger.info(f"Размеры выборок: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")
        return X_train, X_val, X_test, y_train, y_val, y_test
    
    def feature_selection(self, X_train, y_train, X_val, X_test):
        """Отбор признаков"""
        logger.info("Продвинутый отбор признаков...")
        
        n_features = min(CONFIG['TOP_FEATURES'], X_train.shape[1] // 2)
        
        selector1 = SelectKBest(f_classif, k=n_features)
        selector2 = SelectKBest(mutual_info_classif, k=n_features)
        
        selector1.fit(X_train, y_train)
        selector2.fit(X_train, y_train)
        
        selected_features = set()
        selected_features.update(X_train.columns[selector1.get_support()])
        selected_features.update(X_train.columns[selector2.get_support()])
        
        selected_features = list(selected_features)
        logger.info(f"Отобрано {len(selected_features)} признаков")
        
        return (X_train[selected_features], 
                X_val[selected_features], 
                X_test[selected_features],
                selected_features)
    
    def train_individual_models(self, X_train, y_train, X_val, y_val):
        """Обучение отдельных моделей без ансамбля"""
        logger.info("Обучение отдельных высококачественных моделей...")
        
        # LightGBM модель
        lgb_model = lgb.LGBMClassifier(
            objective='multiclass',
            num_class=len(np.unique(y_train)),
            metric='multi_logloss',
            boosting_type='gbdt',
            num_leaves=50,
            learning_rate=0.1,
            feature_fraction=0.8,
            bagging_fraction=0.8,
            bagging_freq=5,
            min_child_samples=20,
            reg_alpha=0.1,
            reg_lambda=1.0,
            n_estimators=500,
            verbose=-1,
            random_state=CONFIG['RANDOM_STATE']
        )
        
        # XGBoost модель БЕЗ early_stopping_rounds в конструкторе
        xgb_model = xgb.XGBClassifier(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=CONFIG['RANDOM_STATE']
        )
        
        # Обучение LightGBM
        logger.info("Обучение LightGBM...")
        lgb_model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(stopping_rounds=50)]
        )
        
        # Обучение XGBoost с early_stopping в fit()
        logger.info("Обучение XGBoost...")
        
        # Создаем временную модель с early_stopping для обучения
        xgb_temp = xgb.XGBClassifier(
            n_estimators=1000,  # Больше для early stopping
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=CONFIG['RANDOM_STATE']
        )
        
        # Обучаем с early stopping
        xgb_temp.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=50,
            verbose=False
        )
        
        # Создаем финальную XGBoost модель с оптимальным количеством итераций
        xgb_model = xgb.XGBClassifier(
            n_estimators=xgb_temp.best_iteration + 1,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=CONFIG['RANDOM_STATE']
        )
        
        # Финальное обучение XGBoost
        xgb_model.fit(X_train, y_train)
        
        # Сохранение моделей
        self.models = {
            'lgb': lgb_model,
            'xgb': xgb_model
        }
        
        # Оценка на валидации
        lgb_score = accuracy_score(y_val, lgb_model.predict(X_val))
        xgb_score = accuracy_score(y_val, xgb_model.predict(X_val))
        
        logger.info(f"LightGBM validation accuracy: {lgb_score:.4f}")
        logger.info(f"XGBoost validation accuracy: {xgb_score:.4f}")
        
        # Возвращаем лучшую модель
        if lgb_score >= xgb_score:
            logger.info("LightGBM выбрана как лучшая модель")
            return lgb_model
        else:
            logger.info("XGBoost выбрана как лучшая модель")
            return xgb_model
    
    def evaluate_models(self, X_test, y_test):
        """Оценка моделей"""
        logger.info("Комплексная оценка моделей...")
        results = {}
        
        for name, model in self.models.items():
            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test) if hasattr(model, 'predict_proba') else None
            
            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred, average='weighted'),
                'recall': recall_score(y_test, y_pred, average='weighted'),
                'f1': f1_score(y_test, y_pred, average='weighted')
            }
            
            if y_pred_proba is not None:
                max_proba = np.max(y_pred_proba, axis=1)
                high_confidence_mask = max_proba > 0.7
                
                if np.sum(high_confidence_mask) > 0:
                    metrics['high_confidence_accuracy'] = accuracy_score(
                        y_test[high_confidence_mask], 
                        y_pred[high_confidence_mask]
                    )
                    metrics['high_confidence_samples'] = np.sum(high_confidence_mask)
                else:
                    metrics['high_confidence_accuracy'] = 0.0
                    metrics['high_confidence_samples'] = 0
            
            results[name] = metrics
            
            logger.info(f"\n📊 {name.upper()} Results:")
            for metric, value in metrics.items():
                if isinstance(value, float):
                    logger.info(f"  {metric.replace('_', ' ').title()}: {value:.4f}")
                else:
                    logger.info(f"  {metric.replace('_', ' ').title()}: {value}")
        
        return results
    
    def save_models(self, X_test, y_test, selected_features):
        """Сохранение моделей"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for name, model in self.models.items():
            model_path = f"{CONFIG['MODEL_DIR']}/final_{name}_model_{timestamp}.pkl"
            
            model_package = {
                'model': model,
                'scaler': self.scaler,
                'selected_features': selected_features,
                'config': CONFIG,
                'timestamp': timestamp,
                'model_type': name
            }
            
            joblib.dump(model_package, model_path)
            logger.info(f"Сохранена модель: {model_path}")
        
        results = self.evaluate_models(X_test, y_test)
        
        results_path = f"{CONFIG['REPORTS_DIR']}/final_results_{timestamp}.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Результаты сохранены: {results_path}")
        return results

def main():
    """Основная функция обучения"""
    start_time = datetime.now()
    logger.info("🚀 Запуск ФИНАЛЬНОЙ системы обучения моделей")
    logger.info(f"Время начала: {start_time}")
    
    try:
        trainer = FinalModelTrainer()
        
        # 1. Загрузка и подготовка данных
        X, y = trainer.load_and_prepare_data(
            symbols=['BTCUSDT', 'ETHUSDT'], 
            timeframes=[15, 30]
        )
        
        # 2. Разделение данных
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.split_data_time_series(X, y)
        
        # 3. Отбор признаков
        X_train, X_val, X_test, selected_features = trainer.feature_selection(
            X_train, y_train, X_val, X_test
        )
        
        # 4. Масштабирование
        logger.info("Масштабирование признаков...")
        scaler = RobustScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        X_test_scaled = scaler.transform(X_test)
        
        trainer.scaler = scaler
        
        X_train = pd.DataFrame(X_train_scaled, columns=selected_features)
        X_val = pd.DataFrame(X_val_scaled, columns=selected_features)
        X_test = pd.DataFrame(X_test_scaled, columns=selected_features)
        
        # 5. Обучение моделей
        best_model = trainer.train_individual_models(X_train, y_train, X_val, y_val)
        
        # 6. Сохранение результатов
        results = trainer.save_models(X_test, y_test, selected_features)
        
        # Финальный отчет
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info("\n" + "="*70)
        logger.info("🎉 ФИНАЛЬНОЕ ОБУЧЕНИЕ ЗАВЕРШЕНО УСПЕШНО!")
        logger.info(f"⏱️  Время обучения: {duration}")
        logger.info(f"🏆 Лучшая модель: {max(results.items(), key=lambda x: x[1]['accuracy'])[0]}")
        logger.info(f"🎯 Лучшая точность: {max([r['accuracy'] for r in results.values()]):.4f}")
        logger.info("="*70)
        
        print("\n📋 ФИНАЛЬНЫЙ ОТЧЕТ:")
        print(f"📊 Размер данных: {len(X)} строк")
        print(f"🔧 Признаков использовано: {len(selected_features)}")
        print(f"⏱️  Время обучения: {duration}")
        print("\n🏆 РЕЗУЛЬТАТЫ МОДЕЛЕЙ:")
        for name, metrics in results.items():
            print(f"  {name.upper()}: Accuracy = {metrics['accuracy']:.4f}, F1 = {metrics['f1']:.4f}")
        
        print(f"\n💾 Модели сохранены в: {CONFIG['MODEL_DIR']}/")
        print(f"📄 Отчеты сохранены в: {CONFIG['REPORTS_DIR']}/")
        print("\n✅ Система готова к тестированию!")
        print("\nДля тестирования запустите: python test_trained_model.py")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в процессе обучения: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()