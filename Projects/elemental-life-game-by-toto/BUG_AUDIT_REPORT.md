# HOT
# BUG AUDIT REPORT — ELEMENTAL LIFE GAME BY ToTo

**Path:** `c:\Temp\elemental-life-game-by-toto`  
**Date:** 2026-07-17  
**Scope:** read-only audit (no code changes)  
**Verdict:** playable prototype / AI Studio dump with serious product, architecture, and integrity issues. **Recommended: rewrite core cleanly; delete ~40–50% of current code.**

---

## 1. Executive summary

| Aspect | Assessment |
|--------|------------|
| Product intent | Hexagonal ecosystem cellular automata (Earth/Water/Vapor/Fire/Grass/Ashes) |
| Origin | Google AI Studio template (`README`, `metadata.json`, secrets plugin for Gemini) |
| Core sim quality | Medium — ideas OK, rules incomplete vs UI, performance naïve |
| UI quality | Over-decorated single-file Compose; hard to maintain |
| Integrity | **Critical** — fake Tor/SimpleX UI + fake purchase |
| Build readiness | **Weak** — no Gradle Wrapper, identity/package chaos, broken tests |
| Test quality | Near-zero; several tests **already wrong** vs current strings/IDs |
| Rewrite worth | **High** — not “fix in place”; salvage model rules + hex rendering ideas |

### Size (Kotlin sources)

| File | Lines | Role |
|------|------:|------|
| `SimulationDashboard.kt` | 1677 | God UI |
| `SimpleXChatScreen.kt` | 1237 | **Fake** messenger / Tor cosplay |
| `HexGrid.kt` | 639 | Grid + rules + presets |
| `HexFieldCanvas.kt` | 336 | Hex canvas + gestures |
| `SimulationViewModel.kt` | 267 | State / sim loop |
| Others (theme, db, model, Main) | ~300 | glue |
| Tests | ~134 | mostly template |
| **Total `.kt`** | **~4556** | |

Roughly **~27% of app code** is a fake SimpleX/Tor chat unrelated to the game.

---

## 2. Architecture map (as-is)

```
MainActivity
  └── SimulationDashboard  (UI + monetization + hidden chat entry)
        ├── HexFieldCanvas (draw + paint + pinch zoom)
        ├── SimulationViewModel
        │     ├── HexGrid.computeNextStep(SimRules)
        │     ├── Room SavedPresetDao
        │     └── SharedPreferences is_premium
        └── SimpleXChatScreen  [hidden 7-tap green button]
              └── CameraX QR cosplay (no real scan pipeline)
```

**Layers missing:** domain pure model, use-cases, repository interface, navigation graph, billing abstraction, real networking (and none is needed for the game).

---

## 3. Findings by severity

### 🔴 CRITICAL

#### C1. Deceptive “SimpleX / Tor Onion” feature
- **Where:** `SimpleXChatScreen.kt`, entry via 7 taps on green “TAP” in Adjust dialog (`SimulationDashboard.kt` ~L121–134).
- **What:** Simulated bootstrap, hardcoded fake hops (`185.220.101.4`, `109.163.234.33`), fake DH/SOCKS tests, pretends “Zero-Metadata”, “Delivered (Onion)”.
- **Reality:** No Tor, no SimpleX, no network, no crypto. Pure UI theatre with `delay()`.
- **Impact:** User deception / trust & store policy risk if shipped; brand/trademark risk (SimpleX).
- **Fix:** **Delete the entire screen** and all entry points. Do not ship cosplay privacy apps.

#### C2. Fake monetization presented as purchase
- **Where:** `SimulationDashboard.kt` buy dialog ~L1490–1550; `SimulationViewModel.unlockPremium`.
- **What:** Button **"1-TAP SIMULATE PURCHASE ($1.99)"** calls `unlockPremium(true)` with no Play Billing. Codes `toto|elemental|pro|premium|free` unlock instantly. Flag stored in plain `SharedPreferences("elemental_life_prefs")`.
- **Impact:** Fraudulent UX if marketed as paid; trivial bypass (`adb` / prefs edit).
- **Fix:** Either remove PRO gate entirely, or integrate **Play Billing** + server/receipt validation. Never label a free toggle as purchase.

---

### 🟠 HIGH

#### H1. Camera API without manifest permission
- **Where:** `SimpleXChatScreen.kt` uses `Manifest.permission.CAMERA` + CameraX; `AndroidManifest.xml` has **no** `<uses-permission android:name="android.permission.CAMERA"/>`.
- **Impact:** Permission request / preview fails or behaves inconsistently; Play Console policy incomplete if permission added later without justification.
- **Fix:** Delete fake scanner (preferred) or declare permission + purpose string + real barcode pipeline.

#### H2. Broken identity / packaging
| Field | Value |
|-------|--------|
| `namespace` | `com.example` |
| `applicationId` | `com.aistudio.hexlife.uxgwhq` |
| `rootProject.name` | `My Application` |
| Theme name | `MyApplicationTheme` |
| `strings.xml` app_name | `ELEMENTAL LIFE GAME BY ToTo` |
- **Impact:** Confused publishing, collision risk with `com.example`, unprofessional store listing.
- **Fix:** Single package e.g. `com.toto.elementallife` everywhere.

#### H3. Tests contradict the product (will fail)
- `ExampleRobolectricTest`: expects `"Hexagonal Game of Life"` — actual string is `"ELEMENTAL LIFE GAME BY ToTo"`.
- `ExampleInstrumentedTest`: expects package `"com.example"` — `applicationId` is `com.aistudio.hexlife.uxgwhq` (instrumented package is applicationId).
- Unit tests for rules are minimal and fragile (stochastic / incomplete isolation of side effects).
- **Fix:** Align assertions; add deterministic pure-function tests for `computeNextStep`.

#### H4. No Gradle Wrapper
- No `gradlew` / `gradle/wrapper/*` in tree.
- **Impact:** Non-reproducible builds; depends on host Gradle/AGP install. AGP **9.1.1** + Kotlin **2.2.10** need a matching toolchain.
- **Fix:** Generate wrapper; pin versions; document JDK (11+ / project may need higher for AGP 9).

#### H5. Dependency / secrets dead weight vs product
- Secrets plugin + `.env` **GEMINI_API_KEY** — **no Kotlin usage** of Gemini/Firebase AI (commented `firebase-ai`).
- Runtime deps pulled: **CameraX ×4, Retrofit, OkHttp, Moshi, Firebase BOM, Accompanist permissions** — core game uses Room + Compose + coroutines only.
- **Impact:** Larger APK, attack surface, slower builds, KSP for Moshi unused by domain models.
- **Fix:** Strip to Compose + lifecycle + Room (if presets kept).

#### H6. KSP / Kotlin version skew (build risk)
- `kotlin = 2.2.10`, `googleDevtoolsKsp = 2.3.5` — KSP major/minor usually must track Kotlin compiler version.
- **Impact:** Potential compile failures on clean machines.
- **Fix:** Align KSP to Kotlin (e.g. `2.2.10-1.0.x` per Google matrix).

---

### 🟡 MEDIUM

#### M1. SimRules UI lies: half the knobs do nothing
**Used in `HexGrid.computeNextStep`:**
- `grassGrowChance`, `grassTranspireChance`, `vaporDriftChance`, `waterClumpChance`, `lakeAggregationChance`

**Defined + exposed in UI but NEVER read by sim:**
- `fireSpreadChance`
- `fireExtinguishChance`
- `fireBurnoutChance`
- `grassDieNoWaterChance`
- `vaporCondenseChance`

Fire/water/grass transitions are largely **deterministic** (`grassCount == 6` → fire; fire+water → earth/vapor), ignoring the chance sliders.

- **Impact:** Broken player agency; “sandbox physics PRO” feature is hollow.
- **Fix:** Wire every rule field into the engine **or** remove from UI.

#### M2. God composables / unmaintainable UI
- `SimulationDashboard.kt` ~1677 lines: layout, fullscreen, monetization, presets, rules sliders, hidden chat, snackbars.
- `SimpleXChatScreen.kt` ~1237 lines of disposable code.
- **Fix:** Split into feature modules/composables: `TopBar`, `StatusCard`, `BrushBar`, `PresetStrip`, `RulesSheet`, `BillingDialog`. Use Navigation.

#### M3. HexGrid mutability footgun
```kotlin
var cells: IntArray = ...
    private set
```
Caller can still mutate `grid.cells[i] = ...` because array is mutable. ViewModel clones on paint — good — but any leak of reference is unsafe.
- **Fix:** Prefer immutable snapshots or defensive copy on expose; or `IntArray` private + copy on read.

#### M4. Simulation performance (45×45 ≈ 2025 cells)
Per generation, per cell: neighbor list allocations, multiple `filter`/`map`/`count`, random, then global water-conservation pass that **filters + shuffles all cells**.
- Canvas: new `Path` + gradients **per cell per frame**.
- **Impact:** Jank on mid devices at high speed / large grids.
- **Fix:** Flat neighbor index cache; reuse buffers; draw with solid colors first; optional dirty rects; move step off main if needed (already in VM scope — OK).

#### M5. Water “conservation” layer fights local rules
Post-pass force-matches WATER+VAPOR count by randomly flipping cells to VAPOR/EARTH.
- **Impact:** Visually random rain/deserts; hard to reason about ecology; can undo careful local interactions.
- **Fix:** Make conservation optional, or redesign rules so mass is conserved locally.

#### M6. Premium gating incomplete / inconsistent product surface
- Painting blocked if not premium (`paintCell` early return).
- Many presets gated in UI; free presets exist.
- Rules editor still partially available depending on paths — product rules unclear.
- Unlock is free-sim anyway (C2).

#### M7. Room without migrations strategy
`fallbackToDestructiveMigration()` + `exportSchema = false` — OK for toy, bad if users save presets long-term.
- Presets store CSV of ints — OK for small grids; no validation of cell value range on load.

#### M8. Release build not production-ready
- `isMinifyEnabled = false`
- Release signing expects env keystore that may not exist (assembleRelease fails without secrets)
- ProGuard file is empty template

#### M9. AI Studio / README not product docs
README is “Run and deploy your AI Studio app” + remove debug signing line — not how to play or architecture.

---

### 🟢 LOW

| ID | Issue |
|----|--------|
| L1 | Theme still purple `MyApplication` Material template; UI hardcodes colors anyway |
| L2 | `CellState.values()` deprecated → `entries` |
| L3 | `Math.hypot` Java style vs `kotlin.math.hypot` |
| L4 | Magic numbers for grid clamp 10..45, speeds 80..800 |
| L5 | `oneStep` increments generation even when called during play (OK) but no max gen / stats history |
| L6 | Hidden green button labeled “TAP” is anti-UX and leads to C1 |
| L7 | Screenshot test name `GreetingScreenshotTest` leftover from template |
| L8 | No accessibility content descriptions on many decorative controls |

---

## 4. Dependency audit (what the game actually needs)

| Dependency | Used by game? | Recommendation |
|------------|---------------|----------------|
| Compose Material3 / UI | Yes | Keep |
| Lifecycle / ViewModel | Yes | Keep |
| Room | Presets only | Keep if save needed |
| Coroutines | Yes | Keep |
| CameraX | Fake QR only | **Remove** |
| Accompanist permissions | Camera only | **Remove** |
| Retrofit / OkHttp / Moshi | No | **Remove** |
| Firebase BOM | No (AI commented) | **Remove** |
| Secrets + GEMINI | No | **Remove** unless AI feature added |
| Roborazzi / Robolectric | Scaffold tests | Keep after fixing tests |

---

## 5. Test matrix (current)

| Test | Status |
|------|--------|
| `addition_isCorrect` | Passes, useless |
| Water→Grass with 5 grass neighbors | Possibly OK for that branch |
| Earth→Water with 5 water neighbors | Hits early rule `waterCount in 5..6` |
| Robolectric app name | **FAIL** vs current string |
| Instrumented package | **FAIL** vs applicationId |
| Roborazzi canvas screenshot | May pass if env OK |
| Rules / premium / paint / Room | **Missing** |

---

## 6. What is worth keeping

1. **Game concept** — 6-element hex ecology is clear and fun.
2. **`CellState` enum** — clean display metadata (trim Compose Color from pure domain if multiplatform later).
3. **Hex neighbor math (even-r offset)** — correct structure; keep with unit tests.
4. **`HexFieldCanvas` geometry** — radius/spacing/hit-test logic is reusable (refactor perf).
5. **Preset generators** — pretty; move data/config out of giant `when`.
6. **ViewModel loop pattern** — start/pause/speed/oneStep is fine skeleton.

## 7. What to throw away

1. Entire `SimpleXChatScreen.kt` + hidden button + onion snackbars.
2. Fake billing UI (or replace with real Billing).
3. Unused network/camera/Firebase stack.
4. AI Studio README/metadata as product surface (rewrite).
5. Dead SimRules fields or dead UI for them.
6. Monolithic dashboard — rewrite as small composables.

---

## 8. Recommended rewrite plan (if “not precious”)

### Phase A — Product definition (1 day)
- Free sandbox only: no PRO, no chat, no camera.
- Features: play/pause/step, speed, brush, size, presets, optional save, rules that **all work**.

### Phase B — Clean architecture (2–3 days)
```
:app
  ui/          // thin Compose
  presentation // ViewModel
  domain/      // CellState, HexGrid, SimRules, Engine (pure JVM unit-testable)
  data/        // Room presets only
```
- Pure `Engine.step(grid, rules, rng): Grid` with injectable `Random`.
- Snapshot tests for golden grids (fixed seed).

### Phase C — UI (2 days)
- Compact dashboard; extract canvas; Material3 dark theme matching game palette.
- No god-file > ~300 lines.

### Phase D — Build hygiene (0.5 day)
- Gradle wrapper, real applicationId, minify release optional, fix/delete tests, strip deps.

### Optional later
- Real IAP only if needed.
- Gemini “explain ecosystem” if API key — optional, isolated module.

---

## 9. Severity counts

| Severity | Count |
|----------|------:|
| 🔴 CRITICAL | 2 |
| 🟠 HIGH | 6 |
| 🟡 MEDIUM | 9 |
| 🟢 LOW | 8 |
| **Total issues tracked** | **25** |

---

## 10. Bottom line

This is a **creative AI-generated prototype** of a hex ecosystem toy, **polluted** by:

1. a large **fake privacy messenger**,  
2. a **fake paid unlock**,  
3. **template dependency bloat**,  
4. **rules UI disconnected from the engine**,  
5. **broken packaging/tests/build wrapper**.

For learning or a personal toy: salvage `HexGrid` + canvas ideas.  
For a real app or Play release: **rewrite small** (~1–1.5k LOC core) rather than patching 4.5k of god-files and cosplay features.

---

*Report generated by Hermes audit workflow (read-only). No source files modified except this report.*
