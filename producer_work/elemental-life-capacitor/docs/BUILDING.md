# Сборка и запуск проекта elemental-life-capacitor

## Предварительные требования

- Node.js (v18+)
- npm или yarn
- Android Studio и Android SDK (для сборки APK)
- Java JDK (v11+)
- Capacitor CLI (устанавливается как зависимость проекта)

## Установка зависимостей

```bash
npm install
```

## Запуск в режиме разработки (веб)

```bash
npm run dev
```

Откроется приложение в браузере по адресу http://localhost:5173

## Сборка веб-версии для producción

```bash
npm run build
```

Собранные файлы будут находиться в директории `dist`.

## Добавление платформы Android

Если платформа Android еще не добавлена:

```bash
npx cap add android
```

Синхронизация веб-ресурсов с нативным проектом:

```bash
npx cap copy android
# или
npx cap sync android
```

## Открытие проекта в Android Studio

```bash
npx cap open android
```

## Сборка APK (debug)

В Android Studio выберите **Build > Build Bundle(s) / APK(s) > Build APK(s)**,
или выполните в терминале:

```bash
cd android
./gradlew assembleDebug
```

Готовый APK будет расположен по пути:
`android/app/build/outputs/apk/debug/app-debug.apk`

## Установка APK на устройство

Убедитесь, что устройство подключено и включена отладка по USB:

```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

## Запуск приложения на устройстве

После установки приложение появится в списке приложений.
Запустите его и предоставьте необходимые разрешения (если потребуются).

## Полный цикл сборки и установки одной командой

```bash
npm run build && npx cap sync android && cd android && ./gradlew assembleDebug && adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Примечания

- При изменении веб-кода всегда выполняйте `npm run build` и `npx cap copy android` перед сборкой нативного проекта.
- Для релиз-сборки замените `assembleDebug` на `assembleRelease`.
- Перед релиз-сборкой обейте версию в `capacitor.config.json` и в `android/app/build.gradle` при необходимости.
- Для тестирования на эмуляторе запустите AVD через Android Studio и выполните `adb install` как обычно.