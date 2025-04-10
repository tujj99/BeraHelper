@echo off
setlocal enabledelayedexpansion

rem ============================================================================
rem Configuration
rem ============================================================================
set SCRIPT_FILE=BeraHelper.py
set OUTPUT_NAME=BeraHelper
set ICON_FILE=bera.ico
set CONFIG_FILE=bera_helper_config.json
set TOKEN_LIST_FILE=coingecko.list
set UPX_DIR=upx
set SPEC_FILE=%OUTPUT_NAME%.spec
set PYTHON_EXE="h:\anaconda3\envs\code1\python.exe"
set UPX_VERSION=4.2.4
set UPX_DOWNLOAD_URL=https://github.com/upx/upx/releases/download/v%UPX_VERSION%/upx-%UPX_VERSION%-win64.zip

rem ============================================================================
rem Script Directory
rem ============================================================================
cd /d "%~dp0"
echo Current directory: %cd%

rem ============================================================================
rem Check/Setup UPX - SIMPLIFIED
rem ============================================================================
set UPX_OPTION=

rem 检查UPX是否已经存在
if exist "%UPX_DIR%\upx.exe" (
    echo UPX found at %UPX_DIR%\upx.exe
    set UPX_OPTION=--upx-dir="%UPX_DIR%"
    goto :upx_check_done
)

rem 创建UPX目录（如果不存在）
if not exist "%UPX_DIR%" (
    echo Creating UPX directory...
    mkdir "%UPX_DIR%"
)

rem 检查是否有PowerShell可用
where powershell >nul 2>nul
if errorlevel 1 (
    echo WARNING: PowerShell is not available. Cannot download UPX.
    goto :upx_check_done
)

rem 下载UPX
echo UPX not found. Downloading from %UPX_DOWNLOAD_URL%...
powershell -Command "Invoke-WebRequest -Uri '%UPX_DOWNLOAD_URL%' -OutFile 'upx.zip'"
if errorlevel 1 (
    echo ERROR: Failed to download UPX.
    goto :upx_check_done
)

rem 解压UPX
echo Extracting UPX...
powershell -Command "Expand-Archive -Path 'upx.zip' -DestinationPath '%UPX_DIR%' -Force"
if errorlevel 1 (
    echo ERROR: Failed to extract UPX.
    if exist upx.zip del upx.zip
    goto :upx_check_done
)

rem 移动UPX到目标目录
for /f "delims=" %%f in ('dir /b /s "%UPX_DIR%\upx.exe"') do (
    echo Moving %%f to %UPX_DIR%\upx.exe
    move "%%f" "%UPX_DIR%\upx.exe" >nul
)

rem 清理下载文件
if exist upx.zip del upx.zip

rem 完成UPX设置
if exist "%UPX_DIR%\upx.exe" (
    echo UPX setup completed successfully.
    set UPX_OPTION=--upx-dir="%UPX_DIR%"
) else (
    echo WARNING: UPX setup failed.
)

:upx_check_done

rem ============================================================================
rem Cleanup Previous Build
rem ============================================================================
echo Cleaning previous build artifacts...
if exist build ( echo Removing build directory... & rd /s /q build )
if exist dist ( echo Removing dist directory... & rd /s /q dist )
if exist "%SPEC_FILE%" ( echo Removing spec file... & del /q "%SPEC_FILE%" )
echo Cleanup complete.

rem ============================================================================
rem Run PyInstaller
rem ============================================================================
echo Starting PyInstaller build...
if not exist %PYTHON_EXE% ( echo ERROR: Python executable not found at %PYTHON_EXE% & goto :error )
if not exist "%SCRIPT_FILE%" ( echo ERROR: Script file not found: %SCRIPT_FILE% & goto :error )
if not exist "%ICON_FILE%" ( echo WARNING: Icon file not found: %ICON_FILE%. Building without icon. & set ICON_OPTION= ) else ( echo Icon found. & set ICON_OPTION=--icon="%ICON_FILE%" )

echo Running PyInstaller...
%PYTHON_EXE% -m PyInstaller ^
    --name %OUTPUT_NAME% ^
    --onefile ^
    --windowed ^
    %ICON_OPTION% ^
    --add-data "%ICON_FILE%";"." ^
    --add-data "%CONFIG_FILE%";"." ^
    --add-data "%TOKEN_LIST_FILE%";"." ^
    %UPX_OPTION% ^
    --clean ^
    --log-level=INFO ^
    --noconfirm ^
    %SCRIPT_FILE%

if errorlevel 1 ( echo *** PyInstaller build FAILED! *** & goto :error )
echo PyInstaller build completed successfully.

rem ============================================================================
rem Completion
rem ============================================================================
echo Build process finished. The executable is in the 'dist' directory.
goto :eof

:error
echo An error occurred during the build process.
pause
exit /b 1

:eof
endlocal
echo Script finished.
rem pause