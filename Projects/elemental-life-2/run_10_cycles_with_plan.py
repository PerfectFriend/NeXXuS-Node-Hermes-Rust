# HOT
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from elemental_life_2_core import ElementalLife2Engine
import subprocess

engine = ElementalLife2Engine()  # initial state

# Read plan items
with open('PLAN.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()
# The plan items are lines 4 to 13 (0-indexed: 3 to 12) because the first three lines are:
# 1|# HOT
# 2|# План развития проекта elemental-life-2
# 3|
# 4|1. Улучшить отслеживание состояния в ядре проекта.
# ... until line 13: "10. Добавить командный интерфейс для запуска движка."

plan_items = []
for line in lines[3:13]:  # lines 4 to 13 (inclusive) -> 10 items
    # Remove the leading number and dot and space
    item = line.strip()
    if item.startswith(tuple(str(i) for i in range(1,11))):
        # Remove the leading "X. "
        item = item.split('. ', 1)[1]
    plan_items.append(item)

# Now we have 10 plan items.

# Create or clear EVOLUTION_LOG.md
with open('EVOLUTION_LOG.md', 'w', encoding='utf-8') as f:
    f.write('# Журнал эволюции для проекта elemental-life-2\n\n')

for i, item in enumerate(plan_items, start=1):
    # Log the plan item we are working on
    with open('EVOLUTION_LOG.md', 'a', encoding='utf-8') as f:
        f.write(f'## Цикл {i}\n')
        f.write(f'**Пункт плана:** {item}\n\n')

    # Run evolution step
    result = engine.evolve()
    if result['status'] != 'success':
        print(f"Warning: evolution step {i} returned {result['status']}")
        # We can break or continue, but let's continue and note in log
        with open('EVOLUTION_LOG.md', 'a', encoding='utf-8') as f:
            f.write(f'**Результат эволюции:** Ошибка - {result["message"]}\n\n')
    else:
        with open('EVOLUTION_LOG.md', 'a', encoding='utf-8') as f:
            f.write(f'**Результат эволюции:** Успешно - {result["message"]} (subcycle: {result["subcycle"]})\n\n')

    # Run tests
    test_result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/', '-v'], 
                                 capture_output=True, text=True)
    if test_result.returncode != 0:
        print(f"Tests failed at cycle {i}")
        with open('EVOLUTION_LOG.md', 'a', encoding='utf-8') as f:
            f.write('**Тесты:** Не прошли\n```\n')
            f.write(test_result.stdout)
            if test_result.stderr:
                f.write('\nSTDERR:\n' + test_result.stderr)
            f.write('\n```\n\n')
    else:
        with open('EVOLUTION_LOG.md', 'a', encoding='utf-8') as f:
            f.write('**Тесты:** Прошли\n\n')

    # Save state after each cycle (optional)
    engine.save_state(f'engine_state_cycle_{i}.json')

# Final state
with open('EVOLUTION_LOG.md', 'a', encoding='utf-8') as f:
    f.write(f'## Итоговое состояние\n')
    f.write(f'- Цикл: {engine.state.cycle}\n')
    f.write(f'- Подцикл: {engine.state.subcycle}\n')
    f.write(f'- Статус: {engine.state.status}\n')
    f.write(f'- Версия: {engine.state.version}\n')
    f.write(f'- Метрики: {engine.state.metrics}\n')
    f.write(f'- Время: {engine.state.timestamp}\n')
    f.write(f'- Длина истории: {len(engine.state_history)}\n')

print("Completed 10 cycles.")