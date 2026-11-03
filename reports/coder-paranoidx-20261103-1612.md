# Отчёт кодера ParanoidX — feature/app-transport

Дата: 2026-11-03 16:12 CET
Имя: ProphetThomas (чёрный кот Кафедрала)
Проект: /home/thomas/LivingCode/Projects/ParanoidX (симлинк) -> физически /home/prophetthomas/projects/ParanoidX
Ветка: feature/app-transport (коммит 5fbd6a7, опережает origin на 6 коммитов)

## Что менял

Файл: internal/bridge/bridge_test.go (только тесты, исходники не трогались)

Заменены два вакуумных теста, которые mutations не ловили, на реальные, проверяющие error-пути:

1. `TestCmdPOSCreateError` -> `TestCmdPOSCreateMerchantRequired`
   - Было: вызывал `cmdPOS create merchant 100` (валидные аргументы) и проверял только `result != ""`.
     Мутация `commands.go:remove-error-check#0` (проверка ошибки `pm.CreateInvoice` в `cmdPOS`, стр. 88) не ловилась.
   - Стало: `cmdPOS create "" 0` — пустой merchant заставляет `CreateInvoice` вернуть ошибку
     ("merchant required"), `cmdPOS` должен отдать `❌ Failed: ...`. Без проверки ошибки код пошёл бы
     с nil-инвойсом и паникнулся на `inv.ID` — тест упадёт, мутация поймана.

2. `TestBridgeNewCLIBinError` -> `TestBridgeNewCLIBinFallback`
   - Было: `New("/tmp/test")` + проверка `cliBin != ""` — проходил при любом исходе, os.Stat в `New()`
     не проверялся.
   - Стало: подмена `HOME` на пустую временную директорию, где бинарника нет; `New()` обязан откатиться
     на путь по умолчанию и вернуть непустой `cliBin != $HOME/bin/simplex-chat-islan`. Реально проверяет
     ветку отката вместо заведомо проходящей заглушки.

## Результат мутационного тестирования

`go run scripts/mutagen/main.go -pkg ./internal/bridge`

- До правки: PASS=14 FAIL=7
- После правки: PASS=15 FAIL=6

Поймано新的 мутации: `commands.go:remove-error-check#0` (PASS).

Осталось горячими (FAIL=6) — класс «документированных компромиссов», по прецеденту пунктов 3.3/3.4:
- `bridge.go:remove-error-check#0/#1/#2` — проверки ошибок в `wsWrite` (WriteMessage), `StdoutPipe`,
  `StderrPipe` внутри `RunContext`. Требуют живого процесса simplex-chat-island + WebSocket —
  интеграционный уровень, не coberturaбельные в unit-тестах. Оформлены пропусками с обоснованием
  (`TestBridgeRunContext*Error`, `TestBridgeWsWriteError`).
- `doc.go:remove-function-call#0/#1/#2` — ложные срабатывания мутагена на комментариях документации
  (паттерны вида `Run():`, `Send():`), а не на исполняемом коде. Документированы тестом
  `TestDocGoMutationsAreFalsePositives`.

## Верификация

- `go build ./...` — чисто
- `go vet ./internal/...` — чисто
- `go test ./... -short` — все пакеты зелёные (EXIT=0)
- `internal/bridge` тесты проходят, включая новые `TestCmdPOSCreateMerchantRequired` и `TestBridgeNewCLIBinFallback`

## Что осталось горячим и почему

Шесть FAIL-м мутаций в `internal/bridge` — три интеграционные проверки ошибок (`wsWrite`, `StdoutPipe`,
`StderrPipe` в `RunContext`) и три ложных срабатывания в `doc.go`. Их нельзя закрыть Unit-тестами без
инфраструктуры (реальный бинарник simplex-chat-island, 살아 WebSocket). Оставлены как connues compromis
с явными пропусками и обоснованием в комментариях — точно такая же модель, что была зафиксирована в
отчётах пунктов 3.3 (`internal/apptransport`, FAIL=10) и 3.4 (`internal/paranoidx`, FAIL=5). Закрывать
их требует отдельной интеграционной стенда — не текущая задача.

## Коммит

`5fbd6a7` — "feat(bridge): заменить вакуумные тесты error-путей на ловящие мутацию"
(1 файл, +370 строк, только `internal/bridge/bridge_test.go`)

## Отправка

Отправлен Инквизитору через Telegram Bot API (chat_id=-1004431090317, thread=252).
Заметка в журнале оставлена Аудитору с пометкой [TRIGGER_AUDITOR] paranoidx.
Проект по симлинку; файлы физически лежат в /home/prophetthomas/projects/ParanoidX.
