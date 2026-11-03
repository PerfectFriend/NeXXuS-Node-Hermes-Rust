# Super-Supervisor отчёт
Время: 2026-11-04 00:25:17

## 🔴 Проблемы с кронами кодеров
- LV-coder-superguard: крон на паузе (enabled=false)
- LV-coder-elemental-life: крон на паузе (enabled=false)
- LV-coder-elemental-life: last_status=delivery_failed, ошибка=live adapter send failed: flood_control:353.0; live adapter delivery to telegram:-1004431090317:252 failed: flood_control:353.0; standalone send to telegram:-1004431090317:252 timed out after 60s (the send may still be in flight)
- LV-coder-cybertarot: крон на паузе (enabled=false)
- LV-coder-cybertarot: last_status=error, ошибка=Script exited with code 75
stdout:
Цепочка: ['nvidia/nemotron-3-ultra-550b-a55b', 'nvidia/nemotron-3.5-lightning-30b-a3b', 'mistralai/mistral-large-4-1t-a52b'] | бюджет 13800s
Attempt 1/3: model=nvidia/nemotron-3-ultra-550b-a55b, provider=nvidia, timeout=3900s
Running (timeout 3900s, skills=—): hermes -p default -z <prompt> --model nvidia/nemotron-3-ultra-550b-a55b --provider nvidia

Unknown remote outcome; inspect before retry.
⛔ Неизвестный/частичный исход или ошибка запуска: повтор модели и запуск следующей роли остановлены.
- LV-coder-cybertarot: failure_streak=5
- LV-coder-elemental-life-2: крон на паузе (enabled=false)
- LV-coder-elemental-life-2: last_status=error, ошибка=Script exited with code 75
stdout:
Цепочка: ['nvidia/nemotron-3-ultra-550b-a55b', 'nvidia/nemotron-3.5-lightning-30b-a3b', 'mistralai/mistral-large-4-1t-a52b'] | бюджет 13800s
Attempt 1/3: model=nvidia/nemotron-3-ultra-550b-a55b, provider=nvidia, timeout=3900s
Running (timeout 3900s, skills=—): hermes -p default -z <prompt> --model nvidia/nemotron-3-ultra-550b-a55b --provider nvidia

Unknown remote outcome; inspect before retry.
⛔ Неизвестный/частичный исход или ошибка запуска: повтор модели и запуск следующей роли остановлены.
- LV-coder-elemental-life-2: failure_streak=1

## 🔴 Uncommitted-изменения в проектах
- superguard: uncommitted-изменения:
M PLAN.md
 M assets/sounds/alarm_sting.wav
 M assets/sounds/ambient_loop.wav
 M assets/sounds/boot_chime.wav
 M assets/sounds/test.wav
 M superguard_core.py
 M tests/test_core_band_12501.py
 M tests/test_core_limits.py
?? assets/brand/OmniWatch_banner_1920.png
?? assets/brand/OmniWatch_icon_1024.png
?? assets/brand/OmniWatch_icon_512.png
?? assets/brand/OmniWatch_promo_1200.png
?? assets/brand/OmniWatch_promo_1200_alert.png
?? assets/brand/OmniWatch_square_1024.png
?? assets/brand/OmniWatch_stor
- elemental-life: uncommitted-изменения:
M elemental-life-app
- cybertarot: uncommitted-изменения:
M PLAN.md
 M README.md
 M art/generate_cards.py
 M art/nightly_art.py
 M art/nightly_cron.sh
 M art/pipeline.sh
 M art/postprocess.py
 M art/upscale_cards.py
 M art/upscale_simple.py
 M src/App.tsx
 M src/__tests__/defects.red.test.ts
 M src/components/CollectionTab.tsx
 M src/components/OracleTab.tsx
 M src/data/game.ts
 M src/hooks/useTarot.ts
 M src/services/interpret.ts
 M src/services/magicWell.ts
 M src/services/ollama.ts
 M src/types/index.ts
 D vite.config.d.ts
 D vite.config.js
 M vites

## Вердикты Владыки: не найдено недавних вердиктов в journal.md

## ℹ️ ГОРЯЧИХ проектов нет — релиз не требуется

---
Super-Supervisor завершён. Следующая проверка через 1 час.