@echo off
chcp 65001 >nul
setlocal
title Termius 简体中文补丁 - 安装

set "TERMIUS=%LOCALAPPDATA%\Programs\Termius"
set "PATCHDIR=%~dp0"
set "BACKUP=%PATCHDIR%backup"

echo ==================================================
echo    Termius 简体中文补丁 · 安装
echo ==================================================
echo.

if not exist "%TERMIUS%\Termius.exe" (
    echo [错误] 未找到 Termius：%TERMIUS%
    echo 请编辑本脚本开头的 TERMIUS 变量，改成实际安装路径。
    pause
    exit /b 1
)
if not exist "%PATCHDIR%app.asar" (
    echo [错误] 缺少 app.asar，请确认补丁包已完整解压。
    pause
    exit /b 1
)
if not exist "%PATCHDIR%patch.json" (
    echo [错误] 缺少 patch.json。
    pause
    exit /b 1
)

tasklist /FI "IMAGENAME eq Termius.exe" 2>nul | find /I "Termius.exe" >nul
if not errorlevel 1 (
    echo [提示] Termius 正在运行，请先完全退出（含托盘图标）后重试。
    pause
    exit /b 1
)

if not exist "%BACKUP%" mkdir "%BACKUP%" >nul 2>&1
if not exist "%BACKUP%\app.asar.orig" (
    echo [1/3] 备份原始 app.asar ...
    copy /Y "%TERMIUS%\resources\app.asar" "%BACKUP%\app.asar.orig" >nul
    if errorlevel 1 (
        echo [错误] 备份失败，已中止。
        pause
        exit /b 1
    )
) else (
    echo [1/3] 已有备份，跳过。
)

echo [2/3] 应用汉化后的 app.asar ...
copy /Y "%PATCHDIR%app.asar" "%TERMIUS%\resources\app.asar" >nul
if errorlevel 1 (
    echo [错误] 复制失败，已中止。可运行 还原补丁.bat 回滚。
    pause
    exit /b 1
)

echo [3/3] 更新 exe 中的完整性校验值 ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PATCHDIR%patch_exe.ps1" -Mode install -PatchJson "%PATCHDIR%patch.json" -ExePath "%TERMIUS%\Termius.exe"
if errorlevel 1 (
    echo [错误] exe 修补失败，请运行 还原补丁.bat 回滚。
    pause
    exit /b 1
)

echo.
echo [完成] 补丁已安装，现在可以启动 Termius。
echo        如需还原，运行同目录下的 还原补丁.bat。
echo.
pause
