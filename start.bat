@echo off
setlocal EnableDelayedExpansion

REM 一键启动：自动创建虚拟环境、安装依赖、启动服务
REM
REM 用法:
REM   start.bat          开发模式（热重载）
REM   start.bat --prod   生产模式（无热重载）
REM   set PORT=9000 && start.bat

cd /d "%~dp0"
set "ROOT_DIR=%CD%"
set "VENV_DIR=%ROOT_DIR%\.venv"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PIP=%VENV_DIR%\Scripts\pip.exe"
set "UVICORN=%VENV_DIR%\Scripts\uvicorn.exe"

if not defined PORT set "PORT=8081"
set "MODE=dev"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--prod" (
  set "MODE=prod"
  shift
  goto parse_args
)
if /i "%~1"=="-h" goto show_help
if /i "%~1"=="--help" goto show_help
call :error "未知参数: %~1（使用 --help 查看帮助）"
exit /b 1

:show_help
echo 企业知识库 Demo — 一键启动
echo.
echo 用法:
echo   start.bat          开发模式（默认，支持热重载）
echo   start.bat --prod   生产模式
echo   set PORT=9000 ^&^& start.bat  指定端口（默认 8081）
echo.
echo 环境变量:
echo   PORT   服务端口，默认 8081
exit /b 0

:args_done

call :info "项目目录: %ROOT_DIR%"

call :require_python
if errorlevel 1 exit /b 1

call :ensure_venv
if errorlevel 1 exit /b 1

call :ensure_env_file
call :ensure_dependencies
if errorlevel 1 exit /b 1

call :ensure_data_dirs

findstr /C:"sk-your-key" "%ROOT_DIR%\.env" >nul 2>&1
if not errorlevel 1 (
  call :warn "检测到 .env 中仍为示例 API Key，问答功能可能不可用"
  call :warn "请编辑 .env 填入 DEEPSEEK_API_KEY，或配置 Ollama 本地模型"
)

call :info "启动服务 → http://localhost:%PORT%"
call :info "按 Ctrl+C 停止"

if /i "%MODE%"=="prod" (
  "%UVICORN%" app.main:app --host 0.0.0.0 --port %PORT%
) else (
  "%UVICORN%" app.main:app --reload --host 0.0.0.0 --port %PORT%
)
exit /b %errorlevel%

REM ---------- helpers ----------

:info
echo [INFO] %~1
exit /b 0

:warn
echo [WARN] %~1
exit /b 0

:error
echo [ERROR] %~1 1>&2
exit /b 0

:require_python
where python >nul 2>&1
if not errorlevel 1 (
  set "PY_CMD=python"
  exit /b 0
)
where py >nul 2>&1
if not errorlevel 1 (
  set "PY_CMD=py -3"
  exit /b 0
)
call :error "未找到 Python，请先安装 Python 3.10+（https://www.python.org/downloads/）"
exit /b 1

:ensure_venv
if exist "%PYTHON%" exit /b 0
call :info "创建虚拟环境..."
%PY_CMD% -m venv "%VENV_DIR%"
if errorlevel 1 (
  call :error "创建虚拟环境失败"
  exit /b 1
)
exit /b 0

:ensure_env_file
if exist "%ROOT_DIR%\.env" exit /b 0
call :info "复制 .env.example → .env"
copy /Y "%ROOT_DIR%\.env.example" "%ROOT_DIR%\.env" >nul
call :warn "请编辑 .env 填入 API Key（DeepSeek 或 Ollama）"
exit /b 0

:ensure_dependencies
set "MARKER=%VENV_DIR%\.deps-installed"
if exist "%MARKER%" exit /b 0
call :info "安装 Python 依赖（首次较慢）..."
"%PIP%" install -r "%ROOT_DIR%\requirements.txt"
if errorlevel 1 (
  call :error "依赖安装失败"
  exit /b 1
)
type nul > "%MARKER%"
exit /b 0

:ensure_data_dirs
if not exist "%ROOT_DIR%\data\chroma" mkdir "%ROOT_DIR%\data\chroma"
if not exist "%ROOT_DIR%\data\uploads" mkdir "%ROOT_DIR%\data\uploads"
exit /b 0
