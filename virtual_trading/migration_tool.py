# migration_tool.py
"""
Инструмент миграции от virtual_traider.py к модульному virtual_trading V2

Помогает:
1. Проанализировать существующий код
2. Конвертировать данные из старого формата 
3. Настроить новую систему
4. Проверить совместимость
"""

import os
import json
import shutil
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any

class VirtualTraderMigrationTool:
    """Инструмент миграции виртуального трейдера"""
    
    def __init__(self):
        self.old_file = "virtual_traider.py"
        self.old_results_dir = "virtual_trader_results"
        self.new_results_dir = "virtual_trading_results_v2"
        self.backup_dir = f"migration_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print("[MIGRATION] Инструмент миграции Virtual Trader V1 → V2")
        print("="*60)
    
    def analyze_current_setup(self) -> Dict[str, Any]:
        """Анализ текущей настройки"""
        print("\n[ANALYZE] Анализ текущей настройки...")
        
        analysis = {
            'old_file_exists': os.path.exists(self.old_file),
            'old_results_exist': os.path.exists(self.old_results_dir),
            'new_system_installed': self._check_new_system(),
            'config_compatibility': self._check_config_compatibility(),
            'data_to_migrate': [],
            'potential_issues': []
        }
        
        # Проверка старого файла
        if analysis['old_file_exists']:
            file_size = os.path.getsize(self.old_file)
            print(f"✓ Найден старый файл: {self.old_file} ({file_size} байт)")
            analysis['old_file_size'] = file_size
        else:
            print(f"✗ Старый файл не найден: {self.old_file}")
            analysis['potential_issues'].append("Старый файл virtual_traider.py не найден")
        
        # Проверка результатов
        if analysis['old_results_exist']:
            old_files = os.listdir(self.old_results_dir)
            print(f"✓ Найдена папка результатов: {self.old_results_dir} ({len(old_files)} файлов)")
            analysis['old_results_count'] = len(old_files)
            analysis['data_to_migrate'].extend(old_files)
        else:
            print(f"- Папка старых результатов не найдена: {self.old_results_dir}")
        
        # Проверка новой системы
        if analysis['new_system_installed']:
            print("✓ Новая модульная система установлена")
        else:
            print("✗ Новая модульная система не найдена")
            analysis['potential_issues'].append("Модульная система virtual_trading не установлена")
        
        return analysis
    
    def _check_new_system(self) -> bool:
        """Проверка установки новой системы"""
        required_paths = [
            "virtual_trading/__init__.py",
            "virtual_trading/core/virtual_trader_v2.py",
            "virtual_trading/services/balance_manager.py",
            "virtual_trading/models/position.py"
        ]
        
        return all(os.path.exists(path) for path in required_paths)
    
    def _check_config_compatibility(self) -> bool:
        """Проверка совместимости конфигурации"""
        try:
            # Проверяем существующую конфигурацию
            import config
            required_attrs = ['ANTISPAM_CONFIG', 'ML_CONFIG', 'SYMBOLS', 'INTERVAL_SEC']
            return all(hasattr(config, attr) for attr in required_attrs)
        except ImportError:
            return False
    
    def create_backup(self) -> bool:
        """Создание резервной копии"""
        print(f"\n[BACKUP] Создание резервной копии в {self.backup_dir}...")
        
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
            
            # Копируем старый файл
            if os.path.exists(self.old_file):
                shutil.copy2(self.old_file, self.backup_dir)
                print(f"✓ Скопирован: {self.old_file}")
            
            # Копируем результаты
            if os.path.exists(self.old_results_dir):
                backup_results = os.path.join(self.backup_dir, "old_results")
                shutil.copytree(self.old_results_dir, backup_results)
                print(f"✓ Скопированы результаты: {self.old_results_dir}")
            
            # Создаем информационный файл
            backup_info = {
                'migration_date': datetime.now().isoformat(),
                'original_file': self.old_file,
                'original_results': self.old_results_dir,
                'migration_tool_version': '2.0',
                'notes': 'Backup created before migration to modular virtual_trading V2'
            }
            
            with open(os.path.join(self.backup_dir, 'migration_info.json'), 'w') as f:
                json.dump(backup_info, f, indent=2)
            
            print(f"✓ Резервная копия создана: {self.backup_dir}")
            return True
            
        except Exception as e:
            print(f"✗ Ошибка создания резервной копии: {e}")
            return False
    
    def migrate_data(self) -> bool:
        """Миграция данных"""
        print(f"\n[MIGRATE] Миграция данных...")
        
        try:
            # Создаем новую папку результатов
            os.makedirs(self.new_results_dir, exist_ok=True)
            
            # Мигрируем старые результаты
            if os.path.exists(self.old_results_dir):
                migrated_count = 0
                
                for filename in os.listdir(self.old_results_dir):
                    old_path = os.path.join(self.old_results_dir, filename)
                    
                    if filename.endswith('.json'):
                        # Конвертируем JSON файлы
                        new_filename = f"migrated_{filename}"
                        new_path = os.path.join(self.new_results_dir, new_filename)
                        
                        if self._convert_json_file(old_path, new_path):
                            migrated_count += 1
                            print(f"✓ Конвертирован: {filename} → {new_filename}")
                    
                    elif filename.endswith('.txt'):
                        # Копируем текстовые отчеты как есть
                        new_filename = f"legacy_{filename}"
                        new_path = os.path.join(self.new_results_dir, new_filename)
                        shutil.copy2(old_path, new_path)
                        migrated_count += 1
                        print(f"✓ Скопирован: {filename} → {new_filename}")
                
                print(f"✓ Мигрировано файлов: {migrated_count}")
            
            # Создаем файл инструкций
            self._create_migration_instructions()
            
            return True
            
        except Exception as e:
            print(f"✗ Ошибка миграции данных: {e}")
            return False
    
    def _convert_json_file(self, old_path: str, new_path: str) -> bool:
        """Конвертация JSON файла в новый формат"""
        try:
            with open(old_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
            
            # Добавляем метаданные миграции
            new_data = {
                'migration_info': {
                    'migrated_from': old_path,
                    'migration_date': datetime.now().isoformat(),
                    'original_format': 'virtual_traider_v1',
                    'new_format': 'virtual_trading_v2'
                },
                'legacy_data': old_data
            }
            
            with open(new_path, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"✗ Ошибка конвертации {old_path}: {e}")
            return False
    
    def _create_migration_instructions(self):
        """Создание файла с инструкциями"""
        instructions = """# ИНСТРУКЦИИ ПО МИГРАЦИИ VIRTUAL TRADER V1 → V2

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
"""
        
        instructions_file = os.path.join(self.new_results_dir, 'MIGRATION_INSTRUCTIONS.md')
        with open(instructions_file, 'w', encoding='utf-8') as f:
            f.write(instructions)
        
        print(f"✓ Создан файл инструкций: {instructions_file}")
    
    def test_new_system(self) -> bool:
        """Тест новой системы"""
        print(f"\n[TEST] Тестирование новой системы...")
        
        try:
            # Пытаемся импортировать новую систему
            from virtual_trading import VirtualTraderV2
            print("✓ Импорт virtual_trading успешен")
            
            # Создаем экземпляр
            trader = VirtualTraderV2(
                initial_balance=1000.0,  # тестовый баланс
                position_size_percent=2.0,
                max_exposure_percent=10.0
            )
            print("✓ Создание экземпляра VirtualTraderV2 успешно")
            
            # Тестируем основные методы
            stats = trader.calculate_statistics()
            print("✓ Расчет статистики работает")
            
            balance_summary = trader.get_balance_summary()
            print("✓ Получение сводки баланса работает")
            
            print("✓ Все тесты пройдены успешно!")
            return True
            
        except Exception as e:
            print(f"✗ Ошибка тестирования: {e}")
            return False
    
    def run_migration(self) -> bool:
        """Запуск полной миграции"""
        print("ЗАПУСК МИГРАЦИИ VIRTUAL TRADER V1 → V2")
        print("="*50)
        
        # 1. Анализ
        analysis = self.analyze_current_setup()
        
        if analysis['potential_issues']:
            print(f"\n⚠️  ВНИМАНИЕ! Обнаружены проблемы:")
            for issue in analysis['potential_issues']:
                print(f"   - {issue}")
            
            answer = input("\nПродолжить миграцию? (y/N): ")
            if answer.lower() != 'y':
                print("Миграция отменена")
                return False
        
        # 2. Резервная копия
        if not self.create_backup():
            print("✗ Не удалось создать резервную копию")
            return False
        
        # 3. Миграция данных
        if not self.migrate_data():
            print("✗ Не удалось мигрировать данные")
            return False
        
        # 4. Тестирование
        if not self.test_new_system():
            print("✗ Новая система не прошла тесты")
            return False
        
        # 5. Финальные инструкции
        print("\n" + "="*50)
        print("🎉 МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print("="*50)
        print()
        print("СЛЕДУЮЩИЕ ШАГИ:")
        print("1. Обновите импорты в main.py:")
        print("   from virtual_trading import VirtualTraderV2")
        print()
        print("2. Обновите создание трейдера:")
        print("   virtual_trader = VirtualTraderV2(...)")
        print()
        print("3. Проверьте integration_example_main.py для примера")
        print()
        print(f"4. Результаты сохранены в: {self.new_results_dir}/")
        print(f"5. Резервная копия в: {self.backup_dir}/")
        print()
        print("Миграция завершена! 🚀")
        
        return True

def main():
    """Главная функция миграции"""
    print("Virtual Trader Migration Tool V1 → V2")
    print("Инструмент миграции виртуального трейдера")
    print()
    
    migration_tool = VirtualTraderMigrationTool()
    
    print("Выберите действие:")
    print("1. Анализ текущей настройки")
    print("2. Полная миграция")
    print("3. Только тест новой системы")
    print("4. Создать только резервную копию")
    
    choice = input("\nВведите номер (1-4): ").strip()
    
    if choice == '1':
        analysis = migration_tool.analyze_current_setup()
        print(f"\nРезультат анализа: {json.dumps(analysis, indent=2, ensure_ascii=False)}")
        
    elif choice == '2':
        migration_tool.run_migration()
        
    elif choice == '3':
        migration_tool.test_new_system()
        
    elif choice == '4':
        migration_tool.create_backup()
        
    else:
        print("Неверный выбор")

if __name__ == "__main__":
    main()