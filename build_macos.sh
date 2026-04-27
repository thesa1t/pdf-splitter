#!/usr/bin/env bash
# Сборка PDF Splitter в полностью самостоятельный .app:
# Tesseract OCR (бинарь + dylibs + языковые данные rus/eng/osd) встраивается внутрь бандла,
# конечному пользователю ничего ставить не нужно — только запустить .app.
# Использование: ./build_macos.sh

set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="PDF Splitter"
BUNDLE_ID="com.salt.pdfsplitter"

echo "==> Проверяю Python 3..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 не найден. Установи с https://www.python.org/ и запусти снова."
    exit 1
fi

echo "==> Проверяю Homebrew (нужен для сборки — НЕ для конечного пользователя)..."
if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew не установлен. Установи с https://brew.sh и запусти снова."
    exit 1
fi

echo "==> Проверяю Tesseract (для сборки)..."
if ! command -v tesseract >/dev/null 2>&1; then
    brew install tesseract tesseract-lang
fi

echo "==> Проверяю dylibbundler..."
if ! command -v dylibbundler >/dev/null 2>&1; then
    brew install dylibbundler
fi

echo "==> Создаю виртуальное окружение .venv..."
python3 -m venv .venv
source .venv/bin/activate

echo "==> Устанавливаю зависимости..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt pyinstaller

echo "==> Генерирую иконки..."
python build_app.py

echo "==> Собираю vendored Tesseract..."
TESS_BIN="$(command -v tesseract)"
TESS_REAL="$(readlink -f "$TESS_BIN" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$TESS_BIN")"

# Ищем tessdata: сначала рядом с brew prefix, потом стандартные пути
TESS_DATA=""
for D in \
    "$(brew --prefix 2>/dev/null)/share/tessdata" \
    "$(brew --prefix tesseract 2>/dev/null)/share/tessdata" \
    "/opt/homebrew/share/tessdata" \
    "/usr/local/share/tessdata"; do
    if [ -f "$D/rus.traineddata" ]; then
        TESS_DATA="$D"
        break
    fi
done
if [ -z "$TESS_DATA" ]; then
    echo "Не нашёл rus.traineddata. Поставь: brew install tesseract-lang"
    exit 1
fi

rm -rf vendored
mkdir -p vendored/tessdata vendored/libs
cp "$TESS_REAL" vendored/tesseract
chmod +w vendored/tesseract
cp "$TESS_DATA/rus.traineddata" vendored/tessdata/
cp "$TESS_DATA/eng.traineddata" vendored/tessdata/ 2>/dev/null || true
cp "$TESS_DATA/osd.traineddata" vendored/tessdata/ 2>/dev/null || true

echo "==> Бандлю dylibs (dylibbundler переписывает пути на @executable_path/libs/)..."
dylibbundler -od -b -x vendored/tesseract -d vendored/libs/ -p '@executable_path/libs/'

echo "==> Собираю приложение через PyInstaller..."
rm -rf build dist "$APP_NAME.spec"
pyinstaller --noconfirm --windowed --clean \
    --name "$APP_NAME" \
    --icon icon.icns \
    --osx-bundle-identifier "$BUNDLE_ID" \
    --hidden-import config \
    --hidden-import pdf_processor \
    --add-binary "vendored/tesseract:." \
    --add-binary "vendored/libs:libs" \
    --add-data "vendored/tessdata:tessdata" \
    main.py

APP_PATH="dist/$APP_NAME.app"
if [ ! -d "$APP_PATH" ]; then
    echo "Сборка не удалась — $APP_PATH не создан."
    exit 1
fi

echo "==> Копирую в /Applications..."
rm -rf "/Applications/$APP_NAME.app"
cp -R "$APP_PATH" "/Applications/"

echo "==> Создаю ярлык на рабочем столе..."
DESKTOP_LINK="$HOME/Desktop/$APP_NAME.app"
rm -f "$DESKTOP_LINK"
ln -s "/Applications/$APP_NAME.app" "$DESKTOP_LINK"

echo ""
echo "✓ Готово! Приложение полностью самостоятельное — Tesseract внутри."
echo "  Приложение:   /Applications/$APP_NAME.app"
echo "  Ярлык:        ~/Desktop/$APP_NAME.app"
echo ""
echo "Запускаю..."
open -a "/Applications/$APP_NAME.app"
