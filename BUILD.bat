@echo off
setlocal
title MoM Toolbox - Build
cd /d "%~dp0"

set "BUILD_PY=%~dp0.venv_build\Scripts\python.exe"
set "FFMPEG_URL=https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip"
set "FFMPEG_SHA256=60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba"

echo ============================================================
echo  MoM Toolbox - building Setup.exe and Portable.zip
echo ============================================================

echo.
echo [1/6] Preparing a clean build environment (Python 3.12)...
if not exist "%BUILD_PY%" (
    py -3.12 -m venv "%~dp0.venv_build"
    if errorlevel 1 (
        echo Python 3.12 not found via the py launcher - trying "python"...
        python -m venv "%~dp0.venv_build"
        if errorlevel 1 goto :fail
    )
)

echo.
echo [2/6] Installing packages (hash-verified)...
"%BUILD_PY%" -m pip install --require-hashes -r "%~dp0requirements-lock.txt"
if errorlevel 1 goto :fail

echo.
echo [3/6] Getting ffmpeg...
if not exist "%~dp0ffmpeg\ffmpeg.exe" (
    curl -L -o "%TEMP%\mom_ffmpeg.zip" "%FFMPEG_URL%"
    if errorlevel 1 goto :fail
    powershell -NoProfile -Command "if ((Get-FileHash -LiteralPath '%TEMP%\mom_ffmpeg.zip' -Algorithm SHA256).Hash -ne '%FFMPEG_SHA256%') { exit 1 }"
    if errorlevel 1 (
        echo ERROR: ffmpeg download failed the checksum check.
        goto :fail
    )
    if exist "%TEMP%\mom_ffmpeg_x" rmdir /s /q "%TEMP%\mom_ffmpeg_x"
    mkdir "%TEMP%\mom_ffmpeg_x"
    tar -xf "%TEMP%\mom_ffmpeg.zip" -C "%TEMP%\mom_ffmpeg_x"
    if errorlevel 1 goto :fail
    mkdir "%~dp0ffmpeg" 2>nul
    for /d %%D in ("%TEMP%\mom_ffmpeg_x\ffmpeg-*") do (
        copy /y "%%D\bin\ffmpeg.exe" "%~dp0ffmpeg\" >nul
        copy /y "%%D\bin\ffprobe.exe" "%~dp0ffmpeg\" >nul
    )
)
if not exist "%~dp0ffmpeg\ffprobe.exe" goto :fail

echo.
echo [4/6] Building MoM_Toolbox.exe (this takes several minutes)...
if exist "%~dp0dist\MoM_Toolbox" rmdir /s /q "%~dp0dist\MoM_Toolbox"
"%BUILD_PY%" -m PyInstaller --noconfirm --clean MoM_Toolbox.spec
if errorlevel 1 goto :fail
xcopy /e /i /y "%~dp0ffmpeg" "%~dp0dist\MoM_Toolbox\ffmpeg" >nul

echo.
echo [5/6] Creating portable zip...
mkdir "%~dp0release" 2>nul
if exist "%~dp0release\MoM_Toolbox_Portable.zip" del /q "%~dp0release\MoM_Toolbox_Portable.zip"
tar -a -c -f "%~dp0release\MoM_Toolbox_Portable.zip" -C "%~dp0dist" MoM_Toolbox
if errorlevel 1 goto :fail

echo.
echo [6/6] Creating Setup.exe installer...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo Inno Setup not found - installing it with winget...
    winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
    if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
    if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
)
if not defined ISCC (
    echo.
    echo Could not install Inno Setup automatically.
    echo Install it from https://jrsoftware.org/isdl.php and run BUILD.bat again.
    echo The portable zip is already ready in the release folder.
    goto :fail
)
"%ISCC%" "%~dp0installer.iss"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  DONE - see the release folder
echo ============================================================
start "" explorer "%~dp0release"
pause
exit /b 0

:fail
echo.
echo ============================================================
echo  BUILD FAILED - see the messages above.
echo ============================================================
pause
exit /b 1
