# Отчёт кодера ParanoidX — ProphetThomas

## Дата и слот
2026-11-03, слот кодера ParanoidX (Living Code Protocol).

## Проект и расположение файлов
- Рабочий каталог (симлинк): `/home/thomas/LivingCode/Projects/ParanoidX`
- Физические файлы: `/home/prophetthomas/projects/ParanoidX`
- Ветка: `feature/app-transport`
- Коммит: `5a4376e transport: Register возвращает ошибки для пустого и дублирующего имени, error-пути покрыты тестами`

## Взятая задача (одна, из плана)
План противоречий, приоритет #2: `internal/transport` — написать настоящие тесты логики транспорта, а не только констант. Закрыть найденные мутационным тестированием дыры в error-путях.

## Что изменилось
### `internal/transport/transport.go` (уже в рабочем дереве, включён в коммит)
`Hub.Register(name)` теперь валидирует вход:
- пустое имя → `fmt.Errorf("name required")`
- дублирующееся имя → `fmt.Errorf("app already exists: %s", name)`

Раньше `Register` никогда не возвращала ошибку, из-за чего protect-блок `if err != nil` после `h.Register` в `api.go:RegisterHandler` был мёртвым кодом (мутация `api.go:remove-error-check#0` не ловилась — журнал 00:21 от 2026-11-03). Теперь ошибка достижима и защита наблюдаема.

### `internal/transport/transport_test.go` (новые тесты, включены в коммит)
- `TestRegisterHandler_Error` — переписан: проверяет не только статус, но и тело ответа при регистрации дубля имени. Ожидается ключ `error` и не `ok=true`. Ловит мутацию `api.go:remove-error-check#0`: без protect-блока `app` будет nil и `app.ID` паникует на nil.
- `TestRegister_EmptyName` — `h.Register("")` должен вернуть ошибку.
- `TestRegister_DuplicateName` — повторная регистрация того же имени должна вернуть ошибку.

## Проверка кода
- `go build ./...` — OK
- `go vet ./internal/...` — OK
- `go test ./... -short` — все пакеты зелёные (включая `internal/transport`)

## Результат мутационного тестирования
Запуск: `go run scripts/mutagen/main.go -pkg ./internal/transport`

```
Total mutations attempted: 27
PASS=25 FAIL=2
```
(PASS = мутация поймана тестом, защита работает; FAIL = тест вакуусен, мутация не замечена.)

Ключевой результат:
- `api.go:remove-error-check#0` — **PASS** (была мёртвым кодом, теперь поймана тестом `TestRegisterHandler_Error`).

Остальные 2 FAIL — известные компромиссы, не новые дыры:
1. `transfer.go:remove-error-check#2` — `sendMsg json.Marshal`: защитная проверка на структуру из базовых типов, по дизайну не падает на валидных данных. Нет наблюдаемого эффекта раннего возврата.
2. `transport.go:remove-error-check#2` — `webhookPush json.Marshal`: то же, тихий возврат без HTTP-вызова, нужен мок http.Client для наблюдения.

Принято как известный компромисс — не рефакторить API ради тестов (схожая оценка давалась в журнале 00:21).

## Что осталось горячим и почему
- Два 방어ственных `json.Marshal` проверки в `transfer.go` и `transport.go` (выше) — тест не может их уронить, потому что по дизайну ошибка на базовых типах не наступает. Оставлены как задокументированные компромиссы, а не чинятся кодом под тест (правило 2: правим причину, а не симптом; здесь причины нет — структура не изменится без изменения типов).
- `internal/bot/nodeapi.go` — в рабочем дереве была stray-мутация `if false { // MUT: removed error check` (игнорирование `io.ReadAll` error). Откачана к HEAD, не входила в задачу, не коммитилась.

## Инквизитору
Отчёт отправлен в Telegram (чат -1004431090317, топик 252) curl'ём по адресу из инструкции.

[TRIGGER_AUDITOR] paranoidx
