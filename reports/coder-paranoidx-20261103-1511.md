# Отчёт кодера ParanoidX — ProphetThomas

Дата: 2026-11-03
Ветка: feature/app-transport
Коммит: 8b80e1d
Проект: /home/thomas/LivingCode/Projects/ParanoidX (симлинк -> /home/prophetthomas/projects/ParanoidX; файлы физически в /home/prophetthomas/projects/ParanoidX)

## Что менял

Одна задача из плана (пункт 3 — план противоречий, приоритет internal/paranoidx): ошибка TCP-диала в
TestV2RayOutbound была недостижима для теста — функция вызывала net.DialTimeout напрямую, хотя в
BridgeBuilder уже было поле dialer для инъекции (задано net.DialTimeout в NewBridgeBuilder, но нигде
не использовалось). Тест TestBridgeBuilderTestV2RayOutboundDialError был затыкан t.Skip
("требует манипуляций с сетью, известный компромисс"), и mutagen фиксировал
bridge_builder.go:remove-error-check#1 как FAIL — пустой тест, защита не проверяется.

Изменения (2 файла, +54/−6):

1. internal/paranoidx/bridge_builder.go — TestV2RayOutbound теперь звонит через bb.dialer вместо
   прямого net.DialTimeout. Комментарий объясняет зачем: инъекция делает ошибку диала достижимой
   в юнит-тесте без сети.
2. internal/paranoidx/paranoidx_test.go — t.Skip заменён на настоящий тест с failDialer, который
   всегда возвращает ошибку диала. Проверяет ok == false, latency == 0, сообщение содержит
   "tcp dial failed". Комментарий объясняет мутацию: убрать проверку err после диала — nil-коннект
   упадёт с паникой в conn.Close().

## Результат мутации

- Ручная мутация: убрана проверка `if err != nil` после диала — тест падает с паникой nil pointer
  dereference в conn.Close(). Защита не пустая, тест не иллюзия.
- Восстановлена защита — тест снова зелёный.
- go run scripts/mutagen/main.go -pkg ./internal/paranoidx:
  bridge_builder.go:remove-error-check#1 перешёл FAIL -> PASS (поймано).
  Итого по пакету: PASS=46, FAIL=4.
- Оставшиеся 4 FAIL — до моего изменения документированные компромиссы, не часть этого изменения:
  - bridge_builder.go:remove-error-check#2 — защитный json.MarshalIndent в LoadV2RayPool (все поля
    базовые типы, ошибка на текущих структурах недостижима).
  - chain.go:remove-error-check#2 — BuildChain в ChainBuildHandler (требует Docker/WireGuard,
    интеграция, t.Skip).
  - vpn.go:remove-error-check#1 — wg-quick up (требует root и валидный конфиг, t.Skip).
  - vpn.go:remove-error-check#2 — wg-quick down (только предупреждение, t.Skip).

## Верификация сборки

go build ./... — OK
go vet ./internal/... — OK
go test ./... -short — все пакеты зелёные, включая internal/paranoidx, internal/registry,
internal/transport, internal/apptransport.

## Что осталось горячим и почему

4 FAIL по mutagen в internal/paranoidx — известные компромиссы, не дефекты. Правлены не будут:
ломать архитектуру под тест (интеграционные пути wg-quick/root, защитные проверки на недостижимых
данных) нарушает правило 3 ("не чинить то, что не сломано"). Документированы тестами с обоснованием,
как в п.3.3/п.3.4 плана.

Не тронул: internal/bridge/bridge_test.go — в рабочем дереве есть незакоммиченные изменения этого
файла, это чужой поток работы, не относится к задаче, не коммитил.

Следующий шаг: все приоритеты пункта 3 плана выполнены (registry 3.1, transport 3.2, apptransport 3.3,
paranoidx 3.4). Новый прогон mutagen по всему репозиторию покажет, где следующая дырка — тогда беру
одну задачу по измерениям, а не по списку.

## Подпись

ProphetThomas, чёрный кот Кафедрала. Пароль защиты: мутация поймана, отчёт cheстен.
