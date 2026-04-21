@echo off
REM Сборка PDF Splitter в .exe + ярлык на рабочем столе.
REM Использование: build_windows.bat

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set APP_NAME=PDF Splitter

echo ==^> Проверяю Python...
where python >nul 2>&1
if errorlevel 1 (
    echo Python не найден. Установи с https://www.python.org/ и запусти снова.
    pause
    exit /b 1
)

echo ==^> Проверяю Tesseract...
where tesseract >nul 2>&1
if errorlevel 1 (
    if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
        echo.
        echo Tesseract OCR не установлен.
        echo Скачай установщик с: https://github.com/UB-Mannheim/tesseract/wiki
        echo и во время установки отметь Russian language data.
        echo.
        pause
        exit /b 1
    )
)

echo ==^> Создаю виртуальное окружение .venv...
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

echo ==^> Устанавливаю зависимости...
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt pyinstaller

echo ==^> Генерирую иконки...
python build_app.py

echo ==^> Собираю приложение через PyInstaller...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

pyinstaller --noconfirm --windowed --clean ^
    --name "%APP_NAME%" ^
    --icon icon.ico ^
    --hidden-import config ^
    --hidden-import pdf_processor ^
    main.py

set "EXE_DIR=%~dp0dist\%APP_NAME%"
set "EXE_PATH=%EXE_DIR%\%APP_NAME%.exe"

if not exist "%EXE_PATH%" (
    echo Сборка не удалась — %EXE_PATH% не создан.
    pause
    exit /b 1
)

echo ==^> Копирую в %LOCALAPPDATA%\Programs\%APP_NAME%...
set "INSTALL_DIR=%LOCALAPPDATA%\Programs\%APP_NAME%"
if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%"
xcopy /e /i /q "%EXE_DIR%" "%INSTALL_DIR%" >nul

echo ==^> Создаю ярлык на рабочем столе...
set "LNK=%USERPROFILE%\Desktop\%APP_NAME%.lnk"
powershell -NoProfile -Command "$s = (New-Object -COM WScript.Shell).CreateShortcut('%LNK%'); $s.TargetPath='%INSTALL_DIR%\%APP_NAME%.exe'; $s.WorkingDirectory='%INSTALL_DIR%'; $s.IconLocation='%INSTALL_DIR%\%APP_NAME%.exe'; $s.Save()"

echo.
echo ^> Готово!
echo   Приложение:   %INSTALL_DIR%\%APP_NAME%.exe
echo   Ярлык:        %LNK%
echo.
echo Запускаю...
start "" "%INSTALL_DIR%\%APP_NAME%.exe"

endlocal
