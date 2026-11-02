# TS type-check baseline

Дата: 2026-11-02

После добавления @types/react + @types/react-dom в devDependencies и переустановки node_modules:

```
$ tsc --noEmit
errors: 0
```

Аудит Kimi K3 (AUDIT_LETTER_FROM_KIMI_K3.md §2) фиксировал **4437 ошибок** до фикса типов.
Гейт включён в CI (.github/workflows/ci.yml, Фаза 8). Цель — не увеличивать счётчик; TS-ядро демонтируется в Фазе 8.
