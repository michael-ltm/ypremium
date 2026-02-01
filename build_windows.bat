@echo off
chcp 65001 >nul
echo ============================================================
echo YouTube Smart Replace - Windows x64 打包脚本
echo ============================================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 安装依赖
echo [1/3] 安装依赖...
pip install pyinstaller mitmproxy --quiet --upgrade

REM 打包（独立版本，包含所有依赖）
echo [2/3] 开始打包 (x64)...
pyinstaller --onefile ^
    --name "YouTubeSmartReplace" ^
    --console ^
    --clean ^
    --noconfirm ^
    --hidden-import=mitmproxy ^
    --hidden-import=mitmproxy.tools ^
    --hidden-import=mitmproxy.tools.dump ^
    --hidden-import=mitmproxy.options ^
    --hidden-import=mitmproxy.net ^
    --hidden-import=mitmproxy.proxy ^
    --collect-all mitmproxy ^
    youtube_standalone.py

REM 复制必要文件
echo [3/3] 复制必要文件...
if not exist "dist" mkdir dist
copy /Y india.md dist\

echo.
echo ============================================================
echo 打包完成！
echo.
echo 输出目录: dist\
echo 文件列表:
echo   - YouTubeSmartReplace.exe  (主程序，已包含所有依赖)
echo   - india.md                 (印度响应模板)
echo.
echo 使用方法:
echo   1. 将 dist 目录下的所有文件复制到目标位置
echo   2. 确保本地代理 (Clash/V2Ray) 运行在 127.0.0.1:7897
echo   3. 双击运行 YouTubeSmartReplace.exe
echo   4. 将浏览器代理设置为 127.0.0.1:8080
echo ============================================================
pause
