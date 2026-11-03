# Отчёт кодера ParanoidX — 2026-11-03 20:16 CET

## Проект
ParanoidX (симлинк `/home/thomas/LivingCode/Projects/ParanoidX` → `/home/prophetthomas/projects/ParanoidX`,
файлы физически в `/home/prophetthomas/projects/ParanoidX`).
Ветка: `feature/app-transport`, коммит `71e3bbb`.

## Задача (одна, из плана п.3)
Закрыть вакуумные мутации в `internal/apptransport`: `Keyring.Register` вызывал
`RandomSecret(rand.Reader)` и `NewSalt(rand.Reader)` напрямую, поэтому их
проверки ошибок были недостижимы в тестах — мутатор не ловил
`keyring.go:remove-error-check#1/#2` (было `PASS=51 FAIL=10` в apptransport).

## Что менял
1. `internal/apptransport/keyring.go`:
   - Добавлено инжектируемое поле `Keyring.randSrc io.Reader` (nil → `crypto/rand.Reader`,
     публичное API не меняется, по правилу пакета как у `NewSalt`/`RandomSecret`).
   - `Register` использует `k.randSrc` вместо жёсткого `rand.Reader`, sodass error-пути
     стали достижимы в тесте.
2. `internal/apptransport/keyring_test.go`:
   - `failOnceReader` — падает на 1-м чтении, успешно на 2-м (изолирует проверку после `RandomSecret`).
   - `TestKeyringRegisterRandomSecretError` — ловит `keyring.go:remove-error-check#1`.
   - `TestKeyringRegisterNewSaltError` — ловит `keyring.go:remove-error-check#2`.
3. `internal/apptransport/apptransport_test.go`:
   - Удалены два замещающих `t.Skip` (`TestKeyringRegisterRandomSecretError`,
     `TestKeyringRegisterNewSaltError`) — заменены настоящими ловящими тестами
     (прецедент коммита `5fbd6a7` bridge).

## Результат мутационного тестирования
```
go run ./scripts/mutagen -pkg ./internal/apptransport
PASS=53  FAIL=8   (было PASS=51  FAIL=10)
```
Все три `keyring.go:remove-error-check` (#0, #1, #2) — PASS. Мутация проверки ошибок
в `Register` теперь поймана обеими ветками.

## Что осталось горячим и pourquoi
Оставшиеся 8 FAIL — документированные компромиссы по правилу 3 ("не чинить то, что не сломано"
/ не рефакторить API ради тестов), не поддающиеся исправлению без изменения типов или публичного API:
- `crypto.go:invert-comparison#0` — мутатор режет текст doc-комментария, не код (ложное срабатывание).
- `crypto.go:remove-error-check#0/#1` — `chacha20poly1305.NewX` в Seal/Open: защитные, ключевой размер валидируется до вызова.
- `envelope.go:remove-error-check#0/#1` — `json.Marshal` в `signatureFor`: все поля базовых типов, никогда не падает.
- `transport.go:remove-error-check#1` — SOCKS5 `dialer.Dial` в `dialSOCKS5`: нужен живой прокси, интеграционная территория.
- `transport.go:remove-error-check#2` — `json.Marshal` в `WriteEnvelope`: защитный, базовые типы.
- `types.go:remove-error-check#0` — `normalizeConfig`: паттерн `short var decl` не поддается мутатору.

## Проверка (гейт шага 5)
- `go build ./...` — exit 0
- `go vet ./internal/...` — clean
- `go test ./... -short` — все пакеты зелёные (exit 0)

## Отправка
Отчёт отправлен Инквизитору (Telegram, chat_id=-1004431090317, thread=252) curl'ом.
Заметка оставлена в журнале Agents с `[TRIGGER_AUDITOR] paranoidx`.
