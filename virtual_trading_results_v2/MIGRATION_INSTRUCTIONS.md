# ИНСТРУКЦИИ ПО МИГРАЦИИ VIRTUAL TRADER V1 → V2

## ЧТО ИЗМЕНИЛОСЬ:

### 1. Структура проекта:
БЫЛО:
- virtual_traider.py (один большой файл ~900 строк)

СТАЛО:
- virtual_trading/ (модульная структура)
  ├── models/          # Модели данных
  ├── services/        # Бизнес-логика  
  ├── core/           # Основной оркестратор
  └── config.py       # Конфигурация

### 2. Импорты в main.py:
БЫЛО:
```python
from virtual_traider import VirtualTraider
virtual_trader = VirtualTraider(initial_balance=10000, position_size_percent=2.0)
```

СТАЛО:
```python
from virtual_trading import VirtualTraderV2
virtual_trader = VirtualTraderV2(
    initial_balance=10000.0,
    position_size_percent=2.0,
    max_exposure_percent=20.0  # новый параметр
)
```

### 3. API совместимость:
Все методы остались такими же:
- virtual_trader.open_virtual_position(signal)
- virtual_trader.check_position_exits(api)
- virtual_trader.log_status(api, engine)  
- virtual_trader.save_results()
- virtual_trader.print_final_report()

### 4. Новые возможности:
✓ Модульная архитектура (легче поддерживать)
✓ Улучшенная статистика и аналитика
✓ Поддержка timing системы из коробки
✓ Лучшее управление рисками и экспозицией
✓ Детальные отчеты и экспорт данных

## СЛЕДУЮЩИЕ ШАГИ:

1. Убедитесь что все файлы virtual_trading/ установлены
2. Обновите импорты в main.py (см. integration_example_main.py)
3. Протестируйте новую систему
4. При необходимости настройте virtual_trading/config.py
5. Старые данные сохранены в папке результатов с префиксом "migrated_"

## ОТКАТ (если нужно):
Резервная копия старой системы сохранена в папке migration_backup_*
Для отката скопируйте файлы обратно.

## ПОДДЕРЖКА:
Если возникли проблемы с миграцией, проверьте:
- Логи в virtual_trading_results_v2/
- Конфигурацию в virtual_trading/config.py
- Совместимость с существующими системами в config/
