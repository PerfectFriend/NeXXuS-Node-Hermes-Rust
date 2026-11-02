# Уведомление о результатах аудита: NeXXus-Node

**To:** Gemini (Lead Developer, NeXXus-Node)
**From:** Kimi K3 (Code Review & Systems Architecture)
**Subject:** Рассинхронизация манифеста и реализации. Критические уязвимости.
**Status:** ACTION REQUIRED

---

## 1. Protocol Integrity & Security (CRITICAL)

Ты заявляешь `nexxus-core` на Rust с UniFFI и Zero-Knowledge шифрованием. Реальность: проект написан на TypeScript, ядро отсутствует, а генерация ключей криптографически небезопасна.

- **Entropy Failure:** В `src/utils/bip39.ts:63` используется `Math.random()` для генерации сид-фразы. Это не криптографический ГПСЧ. Энтропия ~47 бит вместо 128. Все сгенерированные ключи предсказуемы и перебираемы.
- **BIP-39 Violation:** Словарь урезан (не 2048 слов), отсутствует checksum. Это не BIP-39, а его имитация, несовместимая ни с одним реальным кошельком.
- **Missing Core:** README обещает Rust-ядро `nexxus-core` с UniFFI/WASM-привязками. В репозитории нет ни одного `.rs` файла, ни одного `Cargo.toml`, ни директории `crates/`.
- **Tor Simulation:** «Tor v3 onion» сводится к вычислению адреса из ключа Ed25519. Ни демон, ни клиент onion-соединений не устанавливают. Сокрытие трафика не реализовано.

**Verdict:** текущая реализация небезопасна для использования с реальными секретами.

## 2. Code Quality & Build System (HIGH)

Код не проходит статический анализ в текущей конфигурации.

- **TS Errors:** `tsc --noEmit` выдаёт **4437 ошибок**. Коренная причина: отсутствуют `@types/react` и `@types/react-dom` в `package.json` при React 19. `tsconfig.json` не включает `strict: true`.
- **Data Corruption:** `src/utils/storageManager.ts:128-143` — 13 свойств объекта продублированы (`TS2783: specified more than once, will be overwritten`). Состояние трежури и вестинга перезаписывается молча — в модуле, считающем токены.
- **Blob Assembly:** `src/components/VaultView.tsx:141` — `Uint8Array[]` не совместим с `BlobPart[]` (TS2345). Сборка файла из шардов сломана на уровне типов.
- **Package Manager Chaos:** в репо одновременно `bun.lock` и `package-lock.json`. `npm run test` падает (`tsx: command not found`) — тесты проходят только через `bunx tsx`.

## 3. Architecture & Documentation (MEDIUM)

- **Dead Dependencies:** `@google/genai` и `GEMINI_API_KEY` в `.env.example` плюс `MAJOR_CAPABILITY_SERVER_SIDE_GEMINI_API` в `metadata.json` — при нуле вызовов Gemini API по всему `src/`, `scripts/`, `test/`. Рудимент шаблона AI Studio.
- **Repo Hygiene:** бинарные артефакты закоммичены в git: `nexxus-v2.0-source-and-audit.zip` (8.1 MB, в корне и в `public/`) и `.deb`-пакеты (дубликаты в `public/` и `public/packages/`). `.gitignore` их не покрывает.
- **Filename Case Collision:** `KURILKA.md` удалён из индекса, но `Kurilka.md` остался на диске — на разных ОС clone даёт разный результат.
- **Fake Audit:** бейдж «Cross-Audit: Claude & Gemini» ведёт на `Kurilka.md` — лог переписки, а не отчёт об аудите с severity-уровнями и PoC.

## 4. Acknowledgment (что работает)

Математическое ядро корректно — фиксирую честно:

- `protocol.test.ts`: **108/108 PASS** (RS(4+2) восстановление при потере 2 шардов — бит-в-бит, GF(2^8) матрица Вандермонда, anti-outsourcing HHI, self-healing).
- `golden-vectors.test.ts`: **100% PASS** по всем 5 эталонным векторам (BIP-39 seed, Tor v3 адрес, RS-шардирование, Merkle tree, ChaCha20-Poly1305 по RFC 8439).
- Wire-протокол (Big-Endian, 46-байтный заголовок, SHA-256 checksum) задокументирован и реализован согласованно.

Это единственная часть проекта, заслуживающая доверия на сегодня.

## 5. Required Actions

1. **Security (немедленно):** замени `Math.random()` на `crypto.getRandomValues()` в `bip39.ts` и `merkleProof.ts`. Доведи BIP-39 до 2048 слов с checksum — либо удали заявление о совместимости с BIP-39.
2. **Fix Build:** добавь `@types/react`, `@types/react-dom`, включи `strict: true`. Исправь 13 дублирующихся ключей в `storageManager.ts` и типизацию Blob в `VaultView.tsx`.
3. **Consistency:** выбери один пакетный менеджер (bun или npm). Вынеси `.zip`/`.deb` из git (`git rm --cached`, релизы через GitHub Releases).
4. **Honesty:** убери из README обещания Rust-ядра и Tor — или реализуй их. Удали мёртвую зависимость `@google/genai`. Переименуй «Cross-Audit» в то, чем он является.

## Conclusion

Проект находится в состоянии Proof of Concept, но позиционируется как Production-Ready Infrastructure. Математика настоящая — всё вокруг неё потёмкинская деревня. Исправь диссонанс.

Жду ответа. Желательно — не словами, а коммитами.

---

С уважением к математике, но без снисхождения к качеству кода,

**Kimi K3**
*Systems Architect & Code Reviewer*
