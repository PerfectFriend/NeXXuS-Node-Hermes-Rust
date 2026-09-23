# HOT
# Статус Living Code Protocol — Исправления и следующие шаги

**Дата:** 2026-08-15  
**Цикл:** Auto-calculated from 2021-01-01 epoch  
**Статус:** Telegram gateway настроен, требуется рестарт

---

## ✅ Что сделано в этой сессии

1. **Telegram Gateway настроен:**
   - Токен: Cathedral bot (8883516682:AAH0Vuc8LvKjwWUUFxJUL8WWvqen7sc-HMg)
   - Группа: -1004431090317 (t.me/c/4431090317)
   - Топик для отчётов: 252
   - Конфиг записан в `~/.hermes/.env`

2. **Скилл `send-document-to-bot` обновлён:**
   - Правило: только MEDIA: вложения
   - Правило: только русский язык
   - Конфиг токена/чат/топик зафиксирован в скилле

3. **Отчёт протокола отправлен** как документ в группу в топик 252

---

## ⚠️ Требует рестарта Gateway

**Hermes gateway должен быть перезапущен** чтобы подхватить новые настройки:
- `TELEGRAM_HOME_CHANNEL=-1004431090317`
- `TELEGRAM_CRON_THREAD_ID=252`
- `TELEGRAM_HOME_CHANNEL_THREAD_ID=252`

Команда для рестарта (вне процесса gateway):
```bash
systemctl --user restart hermes-gateway.service
```
Или:
```bash
pkill -f "hermes_cli.main gateway run" && sleep 2 && hermes gateway run &
```

До рестарта cron deliveries будут идти в старый чат (143293811) без топика.

---

## 🔴 Критичные фиксы (Next Session)

| # | Проблема | Файл(ы) | Статус |
|---|----------|---------|--------|
| 1 | Windows пути `C:/LivingCode` → `/home/thomas/LivingCode` | Все `.py` в `.hermes/scripts/` | ❌ Не начато |
| 2 | Отсутствует `evolution_elemental_life_2_cron.py` | `.hermes/scripts/` | ❌ Не начато |
| 3 | Model drift в key rotation cron jobs | Hermes cron config | ❌ Не начато |
| 4 | Super-Supervisor (1h post-verification) | Новый скрипт | ❌ Не начато |
| 5 | CompleteProjects миграция FROZEN | `filter_overlord.py` | ❌ Не начато |

---

## 📊 Метрики проекта

| Компонент | Статус |
|-----------|--------|
| Evolution Engine | ✅ Работает |
| 4 Cron Jobs | ✅ Зарегистрированы |
| Filter Overlord | ✅ Реализован |
| Model Registry | ✅ Работает |
| Extinction Check | ✅ Реализован |
| Telegram Gateway | ⚠️ Конфиг обновлён, нужен рестарт |
| CompleteProjects Migration | ❌ Не реализовано |
| Super-Supervisor | ❌ Не реализован |

---

## 🎯 План на следующий цикл

1. **Рестарт gateway** (вручную пользователем)
2. **Фикс путей** — массовый реплейс `C:/LivingCode` → `/home/thomas/LivingCode`
3. **Создание wrapper'а** для elemental-life-2
4. **Запуск тестового цикла** end-to-end
5. **Внедрение CompleteProjects migration** в Filter Overlord

---

*Авто-сгенерировано Hermes Agent*  
*Скилл: send-document-to-bot v1.0*