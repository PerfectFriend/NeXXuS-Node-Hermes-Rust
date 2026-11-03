# Отчёт кодера ProphetThomas — ParanoidX

Дата: 2026-10-04
Ветка: feature/app-transport
Коммиты цикла: 6909ddd (защита), 0db16b7 (мутационный гейт)

## Что менял

Одна задача из PLAN.md: стабильность идентичности узла при повторных
announce/restart.

`registry.GenerateNodeID` брал 8 байт из `crypto/rand` и 8 байт из
`SHA-256(pubkey)`. Соль на каждый вызов означала, что один и тот же
публичный ключ после рестарта получал новый ID — реестр получал вторую
строку вместо обновления первой. Заменено на детерминированный
domain-separated `SHA-256(pubkey)`:

    const nodeIDDigestDomain = "paranoidx:registry:node-id:v1:"
    const nodeIDEntropyBytes = 16

    func GenerateNodeID(pubkey string) string {
        digest := sha256.Sum256([]byte(nodeIDDigestDomain + pubkey))
        return "node-" + hex.EncodeToString(digest[:nodeIDEntropyBytes])
    }

Домен-разделитель нужен, чтобы один и тот же ключ, скормленный в другие
системы с SHA-256, не подменял идентичность узла.

Файл: internal/registry/registry.go. Тесты — семь функций в
internal/registry/registry_test.go (формат, длина, charset, стабильность,
различие по ключам, golden vectors, domain separation).

## Доказательство мутацией

Новый гейт: scripts/mut-nodeid-derivation.sh (131 строка, commit 0db16b7).
Правила гейта, зафиксированные в скрипте:

- мутация считается применённой только при подтверждённом `git diff`
  и маркере MUTATION_ACTIVE в исходнике;
- защита считается пойманной только при `--- FAIL:` или `panic:`;
- ошибка компиляции (`build failed`, `syntax error`, `undefined:`,
  `cannot use`, `declared and not used`) обнаружением НЕ считается —
  иначе сломанный мутатор рисует зелёный балласт.

Прогон `bash scripts/mut-nodeid-derivation.sh`:

    === SANITY: чистый код обязан быть зелёным
      зелёный

    === МУТАЦИЯ: соль на каждый вызов
      diff подтверждён / маркер MUTATION_ACTIVE на месте
      ПОЙМАНА: --- FAIL: TestGenerateNodeIDStableAcrossCalls

    === МУТАЦИЯ: убран домен-разделитель
      ПОЙМАНА: --- FAIL: TestGenerateNodeIDGoldenVectors

    === МУТАЦИЯ: тело сужено до 8 байт
      ПОЙМАНА: --- FAIL: TestGenerateNodeIDLengthAndCharset

    === МУТАЦИЯ: убран префикс node-
      ПОЙМАНА: --- FAIL: TestGenerateNodeID

    === МУТАЦИЯ: верхний регистр hex
      ПОЙМАНА: --- FAIL: TestGenerateNodeIDLengthAndCharset

    ИТОГ: PASS=5 FAIL=0

Первый прогон был недействителен: классификатор считал строку
`FAIL ParanoidX/internal/registry` ошибкой сборки и пометил все пять мутаций
как BUILD-ERROR. Причина найдена, условие сужено до реальных сообщений
компилятора, прогон повторён. Плохой результат не выдавался за доказательство.

Отдельно измерено (probe_restart.go), а не предположено:

    crypto/rand+salt : node-6cd3c5c1b8b46b8d4b5343b88b9879c9
                       node-96be8d3f9f59348f4b5343b88b9879c9
      same across two calls: false
    sha256(domain+key): node-b26c3fa04eba5d02816c08f37b1d648f
                       node-b26c3fa04eba5d02816c08f37b1d648f
      same across two calls: true
    registry rows after two announces of one key: 2 (want 1)

## Сборка на этой машине

    go build ./...        BUILD_OK
    go vet ./internal/... VET_OK
    go test ./... -short  все пакеты ok, ни одного FAIL/panic

## Что осталось горячим и почему

1. ГОРЯЧЕЕ: `registry.GenerateNodeID` не вызывается продуктовым кодом.
   Поиск вне `_test.go` нашёл только определение и комментарий. В
   cmd/ParanoidX/main.go:1065 node ID выводится как
   `fmt.Sprintf("%x", sha256.Sum256([]byte(*dataDir)))[:16]` — то есть
   идентичность узла привязана к пути данных, а не к публичному ключу.
   Переезд на другой каталог = новая личность. Моя правка пока защищает
   контракт функции, но не подключает её. Не трогал: подключение меняет
   поведение рантайма и это отдельная задача с отдельным измерением.

2. ГОРЯЧЕЕ: расхождение веток. GitHub-ветка feature/app-transport на
   d245ab0 содержит salt-вариант GenerateNodeID и свой гейт
   scripts/mut-nodeid-test.sh (145 строк). Моя ветка — d6b7260 + 6909ddd +
   0db16b7. Это две разные защиты от одной находки; их нельзя молча
   слить. Push в origin отклонён (`remote unpack failed: unable to create
   temporary object directory`), push в GitHub до fetch был non-fast-forward.
   Fast-forward после fetch НЕ выполнен: это решение Инквизитора, не моё.

3. ГОРЯЧЕЕ: детерминированный ID из публичного ключа теперь предсказуем.
   Это осознанный размен: стабильность личности против невозможности
   подобрать ID перебором. Если где-то ID используется как секрет или как
   граница доверия — нужна отдельная проверка. Не проверял, потому что
   следы использования ведут в main.go, куда я не вносил правок.

4. Проверено и НЕ является проблемой: репозиторий DarkPushkin/ParanoidX-Node
   — форк PerfectFriend/ParanoidX-Node, default branch master.

## Ограничения среды

Физический проект /home/prophetthomas/projects/ParanoidX принадлежит
prophetthomas, мой uid=1000(thomas): запись в него невозможна, sudo требует
интерактивной аутентификации. Работа велась в клоне
/home/thomas/.hermes/cache/scratch/px_work/ParanoidX-r2. Коммиты 6909ddd и
0db16b7 физически лежат там, а не в симлинковом пути.