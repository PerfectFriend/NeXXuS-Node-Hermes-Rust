# Отчёт Кодера — ParanoidX, пункт 1 плана: GenerateNodeID

Слот: 2026-10-04 06:57 · ProphetThomas, чёрный кот Кафедрала
Задача: `PLAN.md` п.1 — «GenerateNodeID: 32-bit ID, flaky test on Cathedral» (одна задача, не десять)

## 1. Что менял

Ветка `feature/app-transport`, два коммита в форке `DarkPushkin/ParanoidX-Node`:

**7dea49d — `internal/registry/registry.go` + `internal/registry/nodeid_test.go`**

`GenerateNodeID(pubkey)` переписан: 32-битный `math/rand` с паникующим срезом заменён на 128-битное тело — 8 байт соли из `crypto/rand` + первые 8 байт `SHA-256(pubkey)`, вывод `node-` + 32 hex-символа.

* **Причина flaky (измерено, не предположено).** `fmt.Sprintf("%x", struct{uint32}{v})` печатает фигурные скобки, а длина hex зависит от значения: при `v < 2^20` строка короче, и безусловный срез `h[:8]` выходит за границу. Воспроизведено на живом репозитории: `go test ./internal/registry/ -run TestGenerateNodeID -count=5000` → паника `slice bounds out of range [:8] with length 7` (`registry.go:322`). Оценка «2^28» из старой заметки в журнале — неверная; эмпирический порог `2^20`.
* **32 бита — коллизии.** При ~10 тыс. узлов парадокс дней рождения делает совпадение почти гарантированным.
* **`pubkey` принимался и не использовался.** Теперь входит в формирование ID — привязка к владельцу ключа без раскрытия ключа.
* **Опечатка плана:** «128 бит (16 hex)» арифметически неверно; 128 бит = 32 hex. Реализовано по заголовку «128-bit».
* **Отказ `crypto/rand`** → возвращается `""`: регистрация со слабой солью хуже, чем без ID. Поведение закреплено тестом.
* **Импорты:** убраны `math/rand` и `fmt` (стали неиспользуемыми), добавлены `crypto/rand`, `crypto/sha256`, `encoding/hex`.
* Предсуществующие отличия от `gofmt` в `registry.go`/`registry_test.go` не трогал: они не относятся к задаче, новый код отформатирован.

**d245ab0 — `scripts/mut-nodeid-test.sh`**, harness мутационного тестирования контракта (проверка применения мутации через `git diff` + маркер в файле; ошибка компиляции не считается поимкой).

## 2. Почему форк и PR, а не коммит в репозиторий

Сессия `thomas` (uid 1000) не имеет прав записи в физический репозиторий `/home/prophetthomas/projects/ParanoidX` (владелец uid 1001), `sudo` недоступен. Учётная запись `DarkPushkin` на `PerfectFriend/ParanoidX-Node` имеет `pull:true, push:false`. Поэтому: клон форка `DarkPushkin/ParanoidX-Node` в `/home/thomas/.hermes/cache/scratch/px-nodeid`, синхронизирован с `upstream/feature/app-transport` на `d6b7260`; коммиты запушены в форк; открыт **PR #1** в `PerfectFriend/ParanoidX-Node` (base `feature/app-transport`): https://github.com/PerfectFriend/ParanoidX-Node/pull/1 — `state=OPEN, mergeable=MERGEABLE, commits=2` (проверено `gh pr view`).

Физический репозиторий не изменён. Владелец мержит PR или забирает из форка.

## 3. Тест (TDD: RED → GREEN → мутация)

* **RED зафиксирован до фикса:** новые тесты против старой реализации падают — `Format` видит `"node-{265a3db"` (13 символов, фигурные скобки), `KeyBinding` — слишком короткий ID, `Uniqueness` — сама flaky-паника.
* **Контракт закреплён литералами, а не константами реализации** (урок слота 10-03: тест, сверяющийся с внутренней константой, остаётся зелёным при сужении ID):
  * `TestGenerateNodeIDFormat` — 37 символов, `node-` + 32 hex;
  * `TestGenerateNodeIDKeyBinding` — последние 8 байт == `SHA-256(pubkey)[:8]`, known-answer считается внутри теста, а не импортируется из production-кода;
  * `TestGenerateNodeIDSalt` — два выпуска одного ключа дают разные ID;
  * `TestGenerateNodeIDUniqueness` — 200 000 выпусков без коллизий (при 32 битах — гарантированная коллизия);
  * `TestGenerateNodeIDEmptyKey` — пустой ключ не роняет функцию.

## 4. Мутация (гейт правила 1) — `PASS=*** FAIL=0`

| Мутация | Что сломано | Кто поймал |
|---|---|---|
| M1: тело 32 бита | ID короче контракта | `TestGenerateNodeIDFormat` |
| M2: ключ не привязан | хвост ID — нули вместо отпечатка | `TestGenerateNodeIDKeyBinding` |
| M3: без соли | один ключ → один ID | `TestGenerateNodeIDSalt` |
| M4: возврат исходной реализации | формат сломан | `TestGenerateNodeIDFormat` |

Все четыре пойманы утверждениями тестов, не ошибками компиляции. Применение каждой мутации проверено явно (урок слота 10-04: первая попытка мутировала одну копию, а тесты шли на другой — молчаливый зелёный результат). До мутаций — зелёный baseline, после откатов — зелёное дерево.

## 5. Гейты

* `go build ./...` — ok
* `go vet ./internal/...` — ok
* `go test ./... -short` — **0 FAIL** по всему дереву
* `go test ./internal/registry/ -count=100` — ноль падений (гейт из плана)
* `bash scripts/mut-nodeid-test.sh` — `PASS=*** FAIL=0`

## 6. Что осталось горячим и почему

1. **У `GenerateNodeID` нет вызывающего кода в дереве** (проверено grep по `GenerateNodeID` и `node-`: только сам файл и тест). План чинит контракт мёртвой пока функции — фикс доказывает функцию, а не систему. Вопрос Профессору: это верная цель, или вызов живёт вне дерева (Peer-нода, приложение)?
2. **Модель доступа** — второй слот подряд уходит на «не могу закоммитить». Просьба: либо дать кодеру права записи в собственный проект, либо объявить форк `DarkPushkin/ParanoidX-Node` канонической рабочей копией.
3. **Арифметика плана** — если протокол уже начал ожидать 16-hex ID, переход на 32 hex breaking; вызовов в дереве нет, риск для этого репозитория нулевой, но перед мержем стоит подтвердить.
4. **Harness узкоспециализированный.** Пункт плана про обобщение мутационного тестирования открыт: `mut-nodeid-test.sh` — прототип с готовыми паттернами «проверь применение» и «ошибка компиляции не защита».

## 7. Расположение

* Проект по симлинку: `/home/thomas/LivingCode/Projects/ParanoidX`
* Физически: `/home/prophetthomas/projects/ParanoidX` (владелец uid 1001, не изменён)
* Рабочий клон с изменениями: `/home/thomas/.hermes/cache/scratch/px-nodeid` (`feature/app-transport` @ `d245ab0`)
* PR: https://github.com/PerfectFriend/ParanoidX-Node/pull/1