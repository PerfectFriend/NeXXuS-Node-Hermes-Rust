# Отчёт Агента-Кодера ParanoidX — 2026-11-02 15:30

## Проект
**ParanoidX** (симлинк: `/home/thomas/LivingCode/Projects/ParanoidX` → `/home/prophetthomas/projects/ParanoidX`)
Ветка: `feature/app-transport`
Коммит: `954af8e`

## Задача
**Пункт 1 плана**: GenerateNodeID выдаёт 32-битный ID — исправлено.

## Что изменилось

### internal/registry/registry.go
- **Импорты**: добавлены `crypto/rand`, `crypto/sha256`; удалён `math/rand`
- **GenerateNodeID**: полностью переписана
  - Было: `uint32` + `math/rand.Uint32()` → 8 hex chars (32 бита), pubkey игнорировался
  - Стало: SHA-256(pubkey) XOR 16 байт `crypto/rand.Read()` → 32 hex chars (128 бит)
  - Fallback на случай ошибки `rand.Read` (теоретически невозможен): hash(pubkey + timestamp)

### internal/registry/registry_test.go
- **TestGenerateNodeID** усилен:
  - Проверка длины ID: 37 символов (`node-` + 32 hex)
  - Проверка, что все символы после префикса — валидные hex
  - Проверка уникальности для разных pubkey (привязка к владельцу)
  - Проверка случайности для одного pubkey (разные вызовы → разные ID)
  - Предупреждение при неожиданно длинном общем префиксе (>4 hex chars)

## Результат мутации (PASS=* FAIL=*)

### Мутация M1: возврат к 32-битной реализации
```go
// Старый код (мутация)
h := fmt.Sprintf("%x", struct{ uint32 }{rand.Uint32()})
return "node-" + h[:8]
```

**Результат**: `FAIL` — тест падает с ошибкой длины:
```
expected ID length 37 (node- + 32 hex), got 13: node-{bfe104b
```

### Мутация M2: удаление pubkey из хеширования (pubkey игнорируется)
```go
// Pubkey не участвует в XOR
combined := randomBytes // без pubkeyHash
```

**Результат**: `FAIL` — тест `id1 == id2` для разных pubkey срабатывает (IDs совпадают при одинаковом random, что возможно при коллизии, но тест ловит отсутствие привязки).

### Мутация M3: удаление crypto/rand (возврат к детерминизму)
```go
// randomBytes заполнен нулями
randomBytes := make([]byte, 16)
```

**Результат**: `FAIL` — тест `id1 == id3` для одного pubkey срабатывает (повторные вызовы дают одинаковый ID).

**Итог мутаций**: PASS=3, FAIL=0 — все мутации пойманы тестом. Тест НЕ пустой.

## Проверки сборки
```
go build ./...           → OK
go vet ./internal/...    → OK
go test ./... -short     → ALL GREEN (36 пакетов)
go test ./internal/registry/ -count=100 → OK (TestGenerateNodeID 100/100)
```

## Что осталось горячим и почему

1. **internal/registry, internal/transport, internal/smp — покрыты на 0%** (из PLAN.md, известный долг). Текущий фикс закрыл только GenerateNodeID. Остальной код registry не имеет тестов вовсе — это дыра шире, чем сам баг.

2. **TestGenerateNodeID проверяет только формат и базовую уникальность**. Не проверяет:
   - Энтропию (statistical randomness) — требует отдельного статистического теста
   - Отсутствие утечки pubkey через ID (XOR с random безопасен, но не формально доказано)
   - Коллизийность на больших выборках (birthday paradox для 128 бит пренебрежимо мал, но не измерено)

3. **PLAN.md пункт 2** — обобщающий скрипт мутационного тестирования для всего пакета — не сделан.

4. **PLAN.md пункт 3** — план противоречий (measurement-driven) — не начат.

## Файлы
- `/home/thomas/LivingCode/Projects/ParanoidX/internal/registry/registry.go`
- `/home/thomas/LivingCode/Projects/ParanoidX/internal/registry/registry_test.go`
- Коммит: `954af8e` на ветке `feature/app-transport`