@echo off
chcp 65001 >nul
setlocal
title Termius 简体中文补丁 - 还原

set "TERMIUS=%LOCALAPPDATA%\Programs\Termius"
set "PATCHDIR=%~dp0"
set "BACKUP=%TERMIUS%\_cn_patch\backup"

echo ==================================================
echo    Termius 简体中文补丁 · 还原
echo ==================================================
echo.

tasklist /FI "IMAGENAME eq Termius.exe" 2>nul | find /I "Termius.exe" >nul
if not errorlevel 1 (
    echo [提示] Termius 正在运行，请先完全退出后重试。
    pause
    exit /b 1
)

if not exist "%BACKUP%\app.asar.orig" (
    echo [错误] 找不到备份：%BACKUP%\app.asar.orig
    echo 也可以把 Termius.zip 里的 resources\app.asar 解压覆盖回去。
    pause
    exit /b 1
)

echo [1/2] 恢复原始 app.asar ...
copy /Y "%BACKUP%\app.asar.orig" "%TERMIUS%\resources\app.asar" >nul
if errorlevel 1 (
    echo [错误] 恢复失败。
    pause
    exit /b 1
)

echo [2/2] 恢复 exe 中的完整性校验值 ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PATCHDIR%patch_exe.ps1" -Mode restore -PatchJson "%PATCHDIR%patch.json" -ExePath "%TERMIUS%\Termius.exe"
if errorlevel 1 (
    echo [错误] exe 校验值恢复失败，请用 Termius.zip 覆盖 Termius.exe。
    pause
    exit /b 1
)

echo.
echo [完成] 已还原为原版。
echo.
pause
