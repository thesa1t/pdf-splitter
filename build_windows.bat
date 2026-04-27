@echo off
REM Сборка PDF Splitter в полностью самостоятельный .exe:
REM Tesseract OCR (бинарь + DLL + языковые данные) копируется внутрь бандла,
REM конечному пользователю ничего ставить не нужно — только запустить .exe.
REM Использование: build_windows.bat

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set APP_NAME=PDF Splitter

echo ==^> Проверяю Python (нужен для сборки)...
where python >nul 2>&1
if errorlevel 1 (
    echo Python не найден. Установи с https://www.python.org/ и запусти снова.
    pause
    exit /b 1
)

echo ==^> Ищу установленный Tesseract (нужен для сборки, копируется внутрь .exe)...
set "TESS_DIR="
if defined TESSERACT_HOME if exist "%TESSERACT_HOME%\tesseract.exe" set "TESS_DIR=%TESSERACT_HOME%"
if not defined TESS_DIR if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESS_DIR=C:\Program Files\Tesseract-OCR"
if not defined TESS_DIR if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" set "TESS_DIR=C:\Program Files (x86)\Tesseract-OCR"

if not defined TESS_DIR (
    echo.
    echo Tesseract OCR не найден. Скачай UB-Mannheim инсталлятор:
    echo   https://github.com/UB-Mannheim/tesseract/wiki
    echo При установке отметь Russian language data.
    echo Либо задай переменную окружения TESSERACT_HOME.
    echo.
    pause
    exit /b 1
)
echo Использую Tesseract из: %TESS_DIR%

if not exist "%TESS_DIR%\tessdata\rus.traineddata" (
    echo.
    echo Не нашёл %TESS_DIR%\tessdata\rus.traineddata
    echo Переустанови Tesseract с галкой Russian language data.
    echo.
    pause
    exit /b 1
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

echo ==^> Собираю vendored Tesseract (бинарь + DLL + минимум tessdata)...
if exist vendored rmdir /s /q vendored
mkdir vendored\Tesseract-OCR\tessdata

REM Копируем все .exe и .dll из корня Tesseract-OCR (бинарь + рантайм-DLL)
copy /y "%TESS_DIR%\*.exe" vendored\Tesseract-OCR\ >nul
copy /y "%TESS_DIR%\*.dll" vendored\Tesseract-OCR\ >nul

REM tessdata: только нужные языки + служебные конфиги
copy /y "%TESS_DIR%\tessdata\rus.traineddata" vendored\Tesseract-OCR\tessdata\ >nul
if exist "%TESS_DIR%\tessdata\eng.traineddata" copy /y "%TESS_DIR%\tessdata\eng.traineddata" vendored\Tesseract-OCR\tessdata\ >nul
if exist "%TESS_DIR%\tessdata\osd.traineddata" copy /y "%TESS_DIR%\tessdata\osd.traineddata" vendored\Tesseract-OCR\tessdata\ >nul
if exist "%TESS_DIR%\tessdata\configs" xcopy /e /i /q /y "%TESS_DIR%\tessdata\configs" vendored\Tesseract-OCR\tessdata\configs >nul
if exist "%TESS_DIR%\tessdata\tessconfigs" xcopy /e /i /q /y "%TESS_DIR%\tessdata\tessconfigs" vendored\Tesseract-OCR\tessdata\tessconfigs >nul

echo ==^> Собираю приложение через PyInstaller...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "%APP_NAME%.spec" del "%APP_NAME%.spec"

pyinstaller --noconfirm --windowed --clean ^
    --name "%APP_NAME%" ^
    --icon icon.ico ^
    --hidden-import config ^
    --hidden-import pdf_processor ^
    --add-data "vendored\Tesseract-OCR;Tesseract-OCR" ^
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
echo ^> Готово! Приложение полностью самостоятельное — Tesseract внутри.
echo   Приложение:   %INSTALL_DIR%\%APP_NAME%.exe
echo   Ярлык:        %LNK%
echo.
echo Для переноса на рабочий сервер: скопируй папку %INSTALL_DIR% целиком.
echo Запускаю...
start "" "%INSTALL_DIR%\%APP_NAME%.exe"

endlocal
