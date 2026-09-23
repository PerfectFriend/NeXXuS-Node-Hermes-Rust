# beellama.cpp + kvarn KV-cache — оптимизация llama-server

## Что это
Fork llama.cpp (beellama.cpp) добавляет:
- **KVarN** — variance-normalized KV‑cache квантование с независимой точностью для K и V кэшей (типы kvarn2…kvarn8).
- **KV cache precision tail** — хранение недавних токенов в F16/BF16, остальное квантуется, объединено через FlashAttention.
- Стандартные низко‑битные типы (q2_0, q3_0, q6_0 и т.д.).
- Адаптивное speculative decoding, защита от reasoning‑loop и др.

## Почему важно для нас
Наш стек: llama.cpp b10470 + deepseek-coder-v2-16b Q4_0 GGUF на AMD Radeon 780M (Vulkan/RADV).  
Цель — ускорить inference и увеличить контекст без потери качества, особенно для:
- Hermes (локальный LLM для ревью кода).
- GodModePolyBot (анализ промптов, генерация стратегий).
- Возможные будущие агенты ParanoidX.

KVarN позволяет получить **точность близкую к q5/q6 при памяти q4/q5**, а precision tail сохраняет качество для длинных контекстов.

## Сравнение с upstream llama.cpp
| Параметр | llama.cpp (стандарт) | beellama.cpp + KVarN |
|----------|----------------------|----------------------|
| Точность KV‑cache | q4_0/q4_0 | kvarn5/kvarn4 (пример) |
| Размер KV‑cache | ~100% (bf16 baseline) | ~36‑42% bf16 эквивалент (с tail 1024) |
| Скорость генерации | базовая | +10‑30% за счёт лучшей квантизации и speculative decoding |
| Макс. контекст (при фикс. VRAM) | ограничен точностью | увеличивается за счёт меньшего веса на бит |
| Поддержка asymmetric K/V | нет | да (например kvarn5/kvarn4) |

## Практические рекомендации для нашего стека
1. **Соберите beellama.cpp** из upstream (https://github.com/Anbeeld/beellama.cpp) с теми же флагами, что и наш llama-server (Vulkan, AVX2 и т.д.).
2. **Выбор кэша** для deepseek-coder-v2-16b Q4_0:
   - Начальная точка: `--cache-type-k kvarn4 --cache-type-v kvarn4 --kv-tail-tokens 1024` (balanced).
   - Если нужно больше точности: `kvarn5/kvarn5` или `kvarn6/kvarn6` (увеличит память, но уменьшит KLD).
   - Для экономии VRAM: `kvarn5/kvarn4` (как в reddit‑посте) — даёт q5‑like K, q4‑like V.
3. **Контекст и batch**:
   - `--ctx-size 65536` (наш текущий лимит) → можно увеличить до 80‑100к при использовании KVarN + tail.
   - `--batch-size 1024`, `--ubatch-size 256` — хороший старт для промптов средней длины.
4. **Speculative decoding** (если модель поддерживает MTP):
   - `--spec-type draft-mtp --spec-draft-n-max 2` — ускоряет генерацию без потери качества.
5. **FlashAttention** обязателен: `--flash-attn on`.
6. **Треды**: подобрать под CPU (у нас Ryzen 7 7800X3D? уточнить) — например `--threads 7 --threads-batch 8`.
7. **Мониторинг**: добавить в `llama-server-start.sh` вывод метрик (`--metrics`) и логировать в `~/.hermes/logs/llama-server.log`.

## Пример команды для Hermes (оптимизированной под 16GB VRAM аналог)
```bash
/home/thomas/llama-b10470/llama-server \
  -m /home/thomas/deepseek-coder-v2-16b-Q4_0.gguf \
  --port 8081 \
  --host 127.0.0.1 \
  --n-gpu-layers 99 \
  --batch-size 1024 \
  --ubatch-size 256 \
  --flash-attn on \
  --spec-type draft-mtp \
  --spec-draft-n-max 2 \
  --cache-type-k kvarn5 \
  --cache-type-v kvarn4 \
  --kv-tail-tokens 1024 \
  --ctx-size 65536 \
  --fit-ctx 65536 \
  --jinja \
  --chat-template-kwargs "{\\\"preserve_thinking\\\": true, \\\"reasoning_effort\\\":\\\"medium\\\"}" \
  --threads 7 \
  --threads-batch 8 \
  --metrics \
  --verbosity 3
```
> Примечание: для чистого CPU‑режима можно уменьшить `n-gpu-layers` и положиться на KVarN‑экономию.

## Ожидаемый выигрыш
- **Сокращение VRAM** под KV‑cache на 40‑50% относительно bf16 baseline → больше места для контекста или слоёв на GPU.
- **Увеличение скорости** генерации на 10‑25% за счёт лучшей квантизации и speculative decoding.
- **Расширение контекста** до 80‑100к токенов при той же VRAM (полезно для анализа больших логов, кода баз).
- **Сохранение качества** благодаря precision tail и asymmetric KVarN (близко к q5/q6).

## Выводы
beellama.cpp + KVarN — это зрелая оптимизация, которая уже даёт measurable выигрыши на consumer‑GPU. Для нашего стека (AMD 780M, llama.cpp b10470) стоит:
- собрать fork,
- протестироватьпараметры KVarN (kvarn5/kvarn4 + tail 1024) на реальных промптах Hermes,
- сравнить скорость и perplexity с текущей конфигурацией,
- при положительном результате внедрить в `llama-server-start.sh` и обновить документацию.

Интеграция даст нам более быстрый локальный LLM для ревью кода и агентов без необходимости апгрейда железа.