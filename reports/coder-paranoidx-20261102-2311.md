# Отчёт кодера ParanoidX — 2026-11-02 23:11 CET

## Задача
**Пункт 3.1 плана противоречий**: добавить тест для error path в `GenerateNodeID` (инъекция rand source) — приоритет 1 из замеров мутационного тестирования.

## Что изменилось в коде

### 1. `internal/registry/registry.go`
- `GenerateNodeID(pubkey string, randSrc io.Reader)` — добавлен параметр `randSrc` для инъекции источника случайности (по умолчанию `crypto/rand.Reader`)
- Ошибка проверки переписана из `if _, err := randSrc.Read(...); err != nil` в `_, err := randSrc.Read(...); if err != nil` — чтобы паттерн мутационного тестера `if err != nil {` её ловил
- Добавлен импорт `"io"`

### 2. `internal/registry/registry_test.go`
- `TestGenerateNodeID` — обновлены вызовы: `GenerateNodeID("pk1", nil)`
- **Новый тест** `TestGenerateNodeIDFallback`:
  - Использует `errorReader`, который всегда возвращает ошибку
  - Проверяет, что fallback-путь срабатывает: два вызова с одним pubkey дают **разные** ID (благодаря timestamp в fallback)
  - Если error check убрать (мутация) — `randomBytes` остаются нулями, ID становятся детерминированными и одинаковыми → тест падает
- Добавлен тип `errorReader` реализующий `io.Reader`

## Результат мутационного тестирования

```
go run scripts/mutagen/main.go -pkg ./internal/registry -test "TestGenerateNodeID|TestGenerateNodeIDFallback" -v
```

**До изменений**: PASS=7 FAIL=1 (пустая проверка ошибки в GenerateNodeID не тестировалась)

**После изменений**:
```
PASS=8 FAIL=1
PASS  registry.go:invert-comparison#0
PASS  registry.go:invert-comparison#1
PASS  registry.go:invert-comparison#2
FAIL  registry.go:remove-error-check#0  (PingLatency — предсуществующий, не в плане)
PASS  registry.go:remove-error-check#1  (SelectBestNodes)
PASS  registry.go:remove-error-check#2  (GenerateNodeID — ТЕПЕРЬ ПОЙМАН!)
PASS  registry.go:remove-function-call#0
PASS  registry.go:remove-function-call#1
PASS  registry.go:remove-function-call#2
```

**Главный результат**: мутация `remove-error-check#2` (снятие проверки ошибки в `GenerateNodeID`) **поймана тестом** — PASS.

Оставшийся FAIL (#0) — это `PingLatency` (line 282), не входит в приоритеты пункта 3.1 плана.

## Проверки

```
go test ./internal/registry/... -v          # 23 теста PASS
go test ./... -short                        # все пакеты PASS
go build ./... && go vet ./internal/...     # clean
```

## Коммит
`888008d` — "feat(registry): add test for GenerateNodeID fallback path with rand source injection"

## Что осталось горячим и почему

1. **`internal/transport`** — 27 мутаций, PASS=21 FAIL=6. Тесты покрывают только константы/структуры, логика транспорта не защищена. Пункт 3.2 плана.
2. **`internal/apptransport`** — 61 мутация, PASS=49 FAIL=12. Заявленные 6 мутаций не охватывают все дыры. Пункт 3.3 плана.
3. **`PingLatency` error check** — предсуществующий FAIL в mutation testing (remove-error-check#0). Не в приоритетах текущего пункта плана.

## Следующий шаг
Перейти к пункту 3.2: написать настоящие тесты логики транспорта в `internal/transport`.

---

Проект по симлинку: `/home/thomas/LivingCode/Projects/ParanoidX` → `/home/prophetthomas/projects/ParanoidX`
Файлы физически лежат в `/home/prophetthomas/projects/ParanoidX/internal/registry/`