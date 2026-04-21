# PDF Splitter

Разделяет многостраничные PDF по настраиваемым паттернам: вытаскивает из каждой страницы нужные данные (например, ФИО и сумму) и сохраняет её как отдельный файл по вашему шаблону имени. Работает с текстовыми PDF и сканами (через Tesseract OCR).

---

## Установка — готовые сборки (рекомендовано)

### macOS

1. Скачай `PDF-Splitter-macOS.dmg` со страницы [Releases](../../releases/latest).
2. Открой `.dmg` и перетащи «PDF Splitter» в папку `Applications`.
3. При первом запуске: правый клик → «Открыть» (macOS просит разрешить неподписанное приложение).
4. Установи Tesseract OCR (нужен для сканов):
   ```bash
   brew install tesseract tesseract-lang
   ```

### Windows

1. Скачай `PDF-Splitter-Windows.zip` со страницы [Releases](../../releases/latest).
2. Распакуй архив в любую папку (например, `C:\Program Files\PDF Splitter\`).
3. Дважды щёлкни `PDF Splitter.exe` (правый клик → «Отправить → Рабочий стол (создать ярлык)» для ярлыка).
4. Установи Tesseract OCR: [UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki) (при установке отметь «Russian»).

---

## Установка — сборка из исходников

Если хочешь собрать сам (получишь свежую версию + ярлык на рабочем столе автоматически):

### macOS
```bash
git clone https://github.com/<user>/pdf-splitter.git
cd pdf-splitter
./build_macos.sh
```
Скрипт установит зависимости, соберёт `.app`, положит в `/Applications` и создаст ярлык на рабочем столе.

### Windows
```batch
git clone https://github.com/<user>/pdf-splitter.git
cd pdf-splitter
build_windows.bat
```
То же самое для Windows: `.exe` + ярлык на рабочем столе.

---

## Использование

1. **Шаблон** (сверху): выбери подходящий паттерн из списка или нажми **«Настроить шаблоны…»**, чтобы добавить свой.
2. **Обзор…** рядом с «Исходные PDF» — выбери файлы или папку.
   - На macOS нативный диалог поддерживает и файлы, и папки.
   - На Windows диалог выбирает файлы; путь к папке можно вписать в поле вручную.
3. **Папка для сохранения** подставится автоматически (`…/Результат`), можно поменять.
4. **Разделить PDF** — запускает обработку.

### Настройка шаблонов

В редакторе шаблонов (**«Настроить шаблоны…»**) доступно:

- **Регулярка** с именованными группами `(?P<name>...)` — оттуда извлекаются данные.
- **Имя файла** и **Подпапка** — шаблоны вида `{name|cap} {surname|cap}.pdf` или `пп{amount}`. Слэш в подпапке = вложенные папки.
- **Фильтры**: `|cap` (capitalize), `|upper`, `|lower`, `|title`. Плюс подстановка `{page}` — номер страницы.
- **DPI и потоки** — чем больше потоков, тем быстрее OCR; DPI 200 — оптимальный баланс скорости и точности.

Пример паттерна для платёжных поручений (по умолчанию):
```
Regex:      гражданин[ауе]\s+(?P<name>[А-ЯЁа-яё]+)\s+(?P<surname>[А-ЯЁа-яё]+)\s+[Сс]умма\s+(?P<amount>\d+)
Имя файла:  пп{amount}_{name|cap} {surname|cap}.pdf
Подпапка:   пп{amount}
```

Шаблоны хранятся в:
- macOS: `~/Library/Application Support/PDFSplitter/config.json`
- Windows: `%APPDATA%\PDFSplitter\config.json`

---

## Релиз (для мейнтейнера)

Чтобы выпустить новую версию:

```bash
git tag v2.0.0
git push origin v2.0.0
```

GitHub Actions ([.github/workflows/release.yml](.github/workflows/release.yml)) автоматически соберёт macOS + Windows и прикрепит к Release.

---

## Структура проекта

```
main.py              — GUI (Tkinter)
pdf_processor.py     — разбиение PDF + OCR (параллельный ThreadPool)
config.py            — загрузка/сохранение шаблонов
build_app.py         — генерация иконок (.icns / .ico)
build_macos.sh       — локальная сборка для macOS
build_windows.bat    — локальная сборка для Windows
requirements.txt     — зависимости Python
.github/workflows/   — CI-сборка релизов
```

## Требования

- Python 3.10+
- Tesseract OCR (с русским языковым пакетом) — только если у вас сканированные PDF без текстового слоя
