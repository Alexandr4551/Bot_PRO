# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a cryptocurrency trading bot system with ML prediction capabilities and virtual trading simulation. The project implements a hybrid approach combining machine learning signals with technical analysis for automated trading on Bybit futures.

## Architecture

### Core Components

- **Trading Engine** (`core/trading_engine.py`): HybridTradingEngineV2 - main trading logic with smart timing
- **ML Predictor** (`core/ml_predictor.py`): Machine learning signal generation using LightGBM/XGBoost
- **Virtual Trading** (`virtual_trading/`): Complete simulation system with modular architecture
- **API Integration** (`core/bybit_api.py`): Bybit futures API wrapper
- **Configuration** (`config/`): Settings, logging, and Telegram configuration

### Virtual Trading System

The virtual trading system uses a modular architecture:
- **Models** (`virtual_trading/models/`): Position and Trade data models
- **Services** (`virtual_trading/services/`): Business logic (BalanceManager, PositionManager, StatisticsCalculator, ReportGenerator)
- **Core** (`virtual_trading/core/`): VirtualTraderV2 orchestrator

### Key Features

- Smart timing entry system with pullback and breakout strategies
- Anti-spam filtering with cooldown mechanisms
- Risk management with exposure limits
- Comprehensive logging and statistics
- Emergency save functionality
- Telegram notifications

### Architecture Patterns

- **Modular Design**: Virtual trading system uses service-oriented architecture
- **Separation of Concerns**: Models (data), Services (business logic), Core (orchestration)
- **Partial Position Management**: Single positions can have multiple partial exits (TP1, TP2, TP3)
- **Statistical Aggregation**: Statistics correctly group partial exits as single trades
- **Emergency Handling**: Graceful shutdown with data preservation
- **WSL Compatibility**: Designed to work in Windows Subsystem for Linux environment

## Common Commands

### Important: WSL Environment Considerations
This project runs in WSL (Windows Subsystem for Linux) with a Windows Python virtual environment. Use the correct Python path for all commands.

### Environment Setup
```bash
# Install dependencies (using Windows Python in WSL)
"./venv2/Scripts/python.exe" -m pip install -r requirements.txt
```

### Running the System
```bash
# Method 1: Using convenience scripts (recommended)
./start_main.sh          # Main trading bot
./start_virtual.sh       # Virtual trader simulation

# Method 2: Direct execution
"./venv2/Scripts/python.exe" main.py
"./venv2/Scripts/python.exe" run_virtual_trader.py
"./venv2/Scripts/python.exe" train_model_quality.py
"./venv2/Scripts/python.exe" test_balance_logic.py

# Method 3: System Python (if dependencies installed)
python3 main.py
python3 run_virtual_trader.py
```

### Development Commands
```bash
# Test statistics fix
"./venv2/Scripts/python.exe" test_statistics_fix.py

# Test balance logic  
"./venv2/Scripts/python.exe" test_balance_logic.py

# Check logs
tail -f logs/trading_bot_$(date +%Y%m%d).log
tail -f logs/virtual_trader_detailed_$(date +%Y%m%d_%H%M%S).log

# Make scripts executable (if needed)
chmod +x start_main.sh start_virtual.sh
```

## Configuration

### Main Settings (`config/settings.py`)
- **SYMBOLS**: List of trading pairs (BTC, ETH, etc.)
- **TIMEFRAMES**: [15, 30] minute intervals
- **ML_CONFIG**: ML model settings and confidence thresholds
- **ANTISPAM_CONFIG**: Cooldown and filtering settings

### Environment Variables
Create `.env` file with:
- Bybit API credentials
- Telegram bot configuration

## Data Structure

### Historical Data (`historical_data/`)
- Parquet files with OHLCV data
- Multiple timeframes (15min, 30min, 60min)
- Metadata and date range files

### Model Storage (`trained_models/`)
- Trained ML models (.pkl files)
- Model metrics and performance data

### Results (`virtual_trading_results_v2/`)
- Trading session statistics
- Emergency saves and backups
- Detailed trading reports

## Development Notes

### Logging
- Structured logging with different levels (detailed, errors, trading)
- Automatic log rotation by date
- Emergency save functionality for crash recovery

### ML Models
- Uses LightGBM and XGBoost ensemble
- Feature engineering with technical indicators
- Time series cross-validation
- Model training takes 3-5 minutes

### Risk Management
- Position size based on percentage of balance
- Maximum exposure limits
- Smart timing to improve entry points
- Anti-spam filtering to prevent overtrading

### Virtual Trading
- Realistic simulation with slippage
- Comprehensive statistics tracking with corrected trade counting logic
- Migration tools for data updates
- Emergency save on interruption

### Statistics System (Recently Fixed)
- **Trade Counting Logic**: Partial exits (TP1, TP2, TP3) are now correctly grouped as one trade
- **Position Grouping**: Uses `symbol + entry_time + direction` as grouping key
- **Correct Metrics**: Win rate, average P&L, and trade counts now reflect actual positions, not partial exits
- **Timing Analysis**: Groups timing data by complete positions rather than individual exits
- **Testing**: Use `test_statistics_fix.py` to verify statistics logic

## File Naming Conventions

- Log files: `trading_bot_YYYYMMDD.log`, `virtual_trader_detailed_YYYYMMDD_HHMMSS.log`
- Model files: `{SYMBOL}_model_YYYYMMDD_HHMMSS.pkl`
- Results: `session_stats_v2.json`, `final_statistics_YYYYMMDD_HHMMSS.json`
- Emergency saves: `emergency_save_HHMMSS.json`

## Integration Points

- **Bybit API**: Real-time price data and order execution
- **Telegram Bot**: Notifications and alerts
- **Technical Analysis**: ta library for indicators
- **ML Framework**: scikit-learn, lightgbm, xgboost
- **Data Processing**: pandas, numpy for data manipulation

## Important Files for Development

### Core Statistics Logic
- `virtual_trading/services/statistics_calculator.py`: **Recently fixed** - now correctly groups partial exits
- `virtual_trading/services/position_manager.py`: Handles position lifecycle and partial exits
- `virtual_trading/models/trade.py`: ClosedTrade model with timing information

### Convenience Scripts
- `start_main.sh`: Launches main trading bot (recommended method)
- `start_virtual.sh`: Launches virtual trader (recommended method)
- `test_statistics_fix.py`: Tests the corrected statistics logic

### Key Configuration
- `config/settings.py`: Main trading parameters and ML configuration
- `requirements.txt`: Python dependencies for WSL environment

## Recent Changes

### Statistics Fix (2024-07-23)
- **Problem**: System counted each partial exit (TP1, TP2, TP3) as separate trades
- **Solution**: Modified `StatisticsCalculator.calculate_trades_statistics()` to group by position
- **Impact**: Trade counts, win rates, and P&L calculations now reflect actual trading positions
- **Verification**: Use `test_statistics_fix.py` to validate the fix

### WSL Environment Setup
- **Issue**: Python path confusion between Windows and Linux paths
- **Solution**: Created convenience scripts and documented correct Python executable paths
- **Usage**: Always use `"./venv2/Scripts/python.exe"` or convenience scripts