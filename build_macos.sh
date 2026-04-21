#!/usr/bin/env bash
# Сборка PDF Splitter в .app, установка в /Applications и ярлык на Desktop.
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

echo "==> Проверяю Tesseract..."
if ! command -v tesseract >/dev/null 2>&1; then
    echo "Tesseract не найден. Устанавливаю через Homebrew..."
    if ! command -v brew >/dev/null 2>&1; then
        echo "Homebrew не установлен. Установи с https://brew.sh и запусти снова."
        exit 1
    fi
    brew install tesseract tesseract-lang
fi

echo "==> Создаю виртуальное окружение .venv..."
python3 -m venv .venv
source .venv/bin/activate

echo "==> Устанавливаю зависимости..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt pyinstaller

echo "==> Генерирую иконки..."
python build_app.py

echo "==> Собираю приложение через PyInstaller..."
rm -rf build dist
pyinstaller --noconfirm --windowed --clean \
    --name "$APP_NAME" \
    --icon icon.icns \
    --osx-bundle-identifier "$BUNDLE_ID" \
    --hidden-import config \
    --hidden-import pdf_processor \
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
echo "✓ Готово!"
echo "  Приложение:   /Applications/$APP_NAME.app"
echo "  Ярлык:        ~/Desktop/$APP_NAME.app"
echo ""
echo "Запускаю..."
open -a "/Applications/$APP_NAME.app"
