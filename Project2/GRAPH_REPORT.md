# Граф знаний Project2 — отчёт

Сгенерировано кодом: `python3 -m p2_graph graph-report`.
Не редактировать руками — файл перезаписывается целиком.

Порог `min_shared = 2` (минимум общих значимых слов для ребра).

## Корпус

- файлов памяти: 2
- записей всего: 190
- мусорных (topic=Unknown/пустое): 6 {"topic == 'Unknown'": 6}
- дубликатов на объединённом корпусе: 84
- записей после очистки: 100

## Граф

- узлов: 100
- рёбер: 18
- типы рёбер: {'token_overlap': 18}
- плотность: 0.003636
- компонент связности: 89, крупнейшая 5
- изолированных узлов: 83
- средняя степень: 0.36

## Подавленные неразличающие ключи

Ключ, покрывающий больше половины узлов, структуры не даёт и подавляется.

| тип | ключ | узлов | доля |
| --- | --- | --- | --- |
| shares_tag | `textbook` | 100 | 1.0 |
| shares_tag | `learned` | 100 | 1.0 |
| same_category | `Textbook` | 100 | 1.0 |

## Чувствительность к порогу

| min_shared | рёбер | плотность | компонент | крупнейшая | изолированных |
| --- | --- | --- | --- | --- | --- |
| 1 | 529 | 0.106869 | 26 | 54 | 19 |
| 2 | 18 | 0.003636 | 89 | 5 | 83 |
| 3 | 12 | 0.002424 | 94 | 5 | 91 |
| 4 | 10 | 0.00202 | 96 | 5 | 95 |
| 5 | 6 | 0.001212 | 97 | 4 | 96 |

Порог 1 даёт 529 рёбер и 26 компонент, но это шум: одно общее слово склеивает несвязанные темы. Порог 2 — рабочий компромисс (18 рёбер, 89 компонент).

## Топ по центральности

| # | узел | тема | степень | relevance | score |
| --- | --- | --- | --- | --- | --- |
| 1 | t52f8ecc84193 | The Art of Computer Programming, Vol. 1: Fundamental Algorithms | 4 | 0.9 | 3.8 |
| 2 | tffd42371befa | The Art of Computer Programming, Vol. 2: Seminumerical Algorithms | 4 | 0.9 | 3.8 |
| 3 | t1b0749300fc3 | The Art of Computer Programming, Vol. 3: Sorting and Searching | 4 | 0.9 | 3.8 |
| 4 | t50a51de23c3d | The Art of Computer Programming, Vol. 4A: Combinatorial Algorithms | 4 | 0.9 | 3.8 |
| 5 | tc40e026239d6 | The Art of Computer Programming, Vol. 4B: Combinatorial Algorithms | 4 | 0.9 | 3.8 |
| 6 | te06e42271882 | Design Systems as Code (lib.pen / Penpot components) | 3 | 0.9 | 2.85 |
| 7 | t61042db02475 | AI-Assisted Design-to-Code Workflows | 2 | 0.9 | 1.9 |
| 8 | t9c198cdc2afb | pen.dev — Design in IDE, Land in Code | 2 | 0.9 | 1.9 |
| 9 | t7cf85cc07606 | Graph Engineering Fundamentals | 1 | 0.9 | 0.95 |
| 10 | t36f8dcbffa77 | Graphthulhu / Engraph Deep Dive | 1 | 0.9 | 0.95 |
| 11 | t81801b5b4f91 | Loop vs Graph vs Harness Engineering | 1 | 0.9 | 0.95 |
| 12 | t62cceac3f634 | MoneyPrinterTurbo — AI Short Video Generation | 1 | 0.9 | 0.95 |

## Что из этого следует

Крупнейшая компонента (5 узла): «The Art of Computer Programming, Vol. 3: Sorting and Searching», «The Art of Computer Programming, Vol. 4A: Combinatorial Algorithms», «The Art of Computer Programming, Vol. 1: Fundamental Algorithms» и ещё 2. Эти темы связаны общими значимыми словами — настоящая связь, а не метаданные.
Изолированных узлов 83 из 100 (83%). Остальное держится на перечисленных компонентах.
Подавлено неразличающих ключей: 3 (`shares_tag`, `shares_tag`, `same_category`). Ключ, покрывающий больше половины узлов, — константа, а не структура: он соединил бы все узлы попарно.
Держат структуру: {'token_overlap': 18}. Если в будущем `professor_sync.py` начнёт различать теги и категории по темам, добавятся и остальные типы рёбер.
Мусор — 6 записей (6% корпуса), причина: {"topic == 'Unknown'": 6}. Это меньше, чем вырожденность метаданных.
Данные не изменялись: отчёт только читает. Правка памяти — отдельная команда `dedupe --fix`, и только по явному решению.
