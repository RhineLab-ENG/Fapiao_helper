@echo off
chcp 65001 >nul
echo ========================================
echo   发票整理与重命名助手 - 打包脚本
echo ========================================
echo.

REM 1. 激活虚拟环境
call .venv\Scripts\activate.bat

REM 2. 确保 PyInstaller 已安装
pip install pyinstaller -q

REM 3. 清理旧构建
echo [1/3] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 4. 确认 rapidocr 资源路径
echo [2/3] 检查 rapidocr 资源...

REM 查找 config.yaml 和 models 目录
for /f "delims=" %%i in ('python -c "import rapidocr_onnxruntime,os; print(os.path.dirname(rapidocr_onnxruntime.__file__))"') do set RAPIDOCR_DIR=%%i

if not exist "%RAPIDOCR_DIR%\config.yaml" (
    echo [错误] 找不到 rapidocr_onnxruntime\config.yaml
    exit /b 1
)
if not exist "%RAPIDOCR_DIR%\models" (
    echo [错误] 找不到 rapidocr_onnxruntime\models
    exit /b 1
)

echo   rapidocr 路径: %RAPIDOCR_DIR%

REM 5. 打包
echo [3/3] 开始打包...
pyinstaller ^
    --name=FapiaoHelper ^
    --windowed ^
    --onefile ^
    --add-data="%RAPIDOCR_DIR%\config.yaml;rapidocr_onnxruntime" ^
    --add-data="%RAPIDOCR_DIR%\models;rapidocr_onnxruntime\models" ^
    --hidden-import=rapidocr_onnxruntime ^
    --hidden-import=pdfplumber ^
    --hidden-import=openpyxl ^
    --hidden-import=cv2 ^
    main.py

if %errorlevel% neq 0 (
    echo [失败] 打包出错，请检查上方日志
    exit /b 1
)

echo.
echo ========================================
echo   打包完成！
echo   输出: dist\FapiaoHelper.exe
echo ========================================
pause
