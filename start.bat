@echo off
setlocal

rem ============================================================
rem  JobPilot 一键启动：ICP 容器(可选) + FastAPI 后端 + Vite 前端
rem  用法：双击本文件。关闭弹出的两个命令行窗口即停止前后端。
rem  注意：本文件必须保持 ANSI(GBK) 编码 + CRLF 换行，
rem        编辑后请勿另存为 UTF-8，否则 cmd 解析中文会出错。
rem ============================================================

set "BACKEND_DIR=E:\JobPilot\backend"
set "FRONTEND_DIR=E:\JobPilot\frontend"
set "ICP_URL=http://127.0.0.1:16181"
set "API_PORT=8000"
set "WEB_PORT=5173"

echo ============================================
echo   JobPilot 一键启动
echo ============================================

rem ---- 0. 环境自检 ----
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 python，请确认 Python 已安装并加入 PATH
    pause
    exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 npm，请确认 Node.js 已安装并加入 PATH
    pause
    exit /b 1
)

rem ---- 1. ICP 备案反查服务（Docker 容器 ymicp；不可用时自动走 Bing 兜底）----
curl -s --connect-timeout 2 -o nul "%ICP_URL%" >nul 2>&1
if %errorlevel%==0 (
    echo [ICP]  服务已在运行：%ICP_URL%
) else (
    echo [ICP]  未检测到服务，尝试启动容器 ymicp ...
    docker start ymicp >nul 2>&1
    if errorlevel 1 (
        echo [ICP]  启动失败（Docker Desktop 未运行或未安装），本次跳过 ICP 层
    ) else (
        echo [ICP]  容器已启动：%ICP_URL%
    )
)

rem ---- 2. 后端 FastAPI（端口已被监听则视为已在运行，直接复用）----
netstat -ano | findstr /c:"127.0.0.1:%API_PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [后端] 端口 %API_PORT% 已有服务在监听，复用现有实例
) else (
    echo [后端] 启动 FastAPI：http://127.0.0.1:%API_PORT% ...
    start "JobPilot-backend" cmd /k "cd /d %BACKEND_DIR% && set ICP_API_URL=%ICP_URL% && python run.py"
)

rem ---- 3. 前端 Vite dev server ----
netstat -ano | findstr /c:"127.0.0.1:%WEB_PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [前端] 端口 %WEB_PORT% 已有服务在监听，复用现有实例
) else (
    echo [前端] 启动 Vite dev server：http://localhost:%WEB_PORT% ...
    start "JobPilot-frontend" cmd /k "cd /d %FRONTEND_DIR% && npm run dev"
)

rem ---- 4. 轮询等待前端就绪后打开浏览器（最多约 30 秒）----
echo [等待] 服务就绪中 ...
set /a tries=0
:wait_ready
%SystemRoot%\System32\ping.exe -n 3 127.0.0.1 >nul
set /a tries+=1
curl -s --connect-timeout 2 -o nul "http://127.0.0.1:%WEB_PORT%" >nul 2>&1
if not errorlevel 1 (
  curl -s --connect-timeout 2 -o nul "http://127.0.0.1:%API_PORT%/api/boot" >nul 2>&1
  if not errorlevel 1 goto open_browser
)
if %tries% lss 15 goto wait_ready
echo [警告] 前后端 %tries% 次探测后仍未就绪，仍尝试打开浏览器
:open_browser
start "" "http://localhost:%WEB_PORT%"
echo.
echo [完成] 已打开 http://localhost:%WEB_PORT%
echo        停止方式：关闭 JobPilot-backend / JobPilot-frontend 两个命令行窗口
echo        （ICP 容器保持后台运行，不受影响；按任意键关闭本窗口）
pause >nul
endlocal
