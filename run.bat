@echo off
REM ============================================================
REM  一键启动脚本 (Windows)
REM  功能：1) 构建前端  2) 启动后端 Flask 服务
REM  使用：双击本文件，或在 cmd 中执行 run.bat
REM ============================================================

setlocal
cd /d "%~dp0"

echo ============================================================
echo  📚  图书推荐系统 - 一键启动
echo ============================================================

REM 1. 构建前端
echo.
echo [1/2] 正在构建前端 (Vue 3 + Vite)...
python build_frontend.py
if errorlevel 1 (
    echo.
    echo ❌ 前端构建失败，详见上面日志
    pause
    exit /b 1
)

REM 2. 启动后端
echo.
echo [2/2] 正在启动后端服务 (Flask)
echo.
echo ============================================================
echo  ✅ 服务启动完成！
echo.
echo     前端 + 后端:   http://localhost:5000
echo     健康检查:       http://localhost:5000/api/health
echo.
echo     停止服务:       按 Ctrl + C
echo ============================================================
echo.

cd /d "%~dp0\backend"
python app.py

endlocal
