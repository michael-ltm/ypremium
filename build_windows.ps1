# YouTube Smart Replace - Windows x64 打包脚本 (PowerShell)
# 在 Windows PowerShell 中运行此脚本

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "YouTube Smart Replace - Windows x64 打包脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python 已安装: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[错误] 未找到 Python，请先安装 Python 3.8+" -ForegroundColor Red
    exit 1
}

# 安装依赖
Write-Host ""
Write-Host "[1/3] 安装依赖..." -ForegroundColor Yellow
pip install pyinstaller mitmproxy --quiet --upgrade

# 打包（独立版本，包含所有依赖）
Write-Host "[2/3] 开始打包 (x64)..." -ForegroundColor Yellow
pyinstaller --onefile `
    --name "YouTubeSmartReplace" `
    --console `
    --clean `
    --noconfirm `
    --hidden-import=mitmproxy `
    --hidden-import=mitmproxy.tools `
    --hidden-import=mitmproxy.tools.dump `
    --hidden-import=mitmproxy.options `
    --hidden-import=mitmproxy.net `
    --hidden-import=mitmproxy.proxy `
    --collect-all mitmproxy `
    youtube_standalone.py

# 复制必要文件
Write-Host "[3/3] 复制必要文件..." -ForegroundColor Yellow
if (!(Test-Path "dist")) { New-Item -ItemType Directory -Path "dist" | Out-Null }
Copy-Item -Path "india.md" -Destination "dist\" -Force

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "打包完成！" -ForegroundColor Green
Write-Host ""
Write-Host "输出目录: dist\" -ForegroundColor White
Write-Host "文件列表:" -ForegroundColor White
Write-Host "  - YouTubeSmartReplace.exe  (主程序，已包含所有依赖)" -ForegroundColor White
Write-Host "  - india.md                 (印度响应模板)" -ForegroundColor White
Write-Host ""
Write-Host "使用方法:" -ForegroundColor Cyan
Write-Host "  1. 将 dist 目录下的所有文件复制到目标位置" -ForegroundColor White
Write-Host "  2. 确保本地代理 (Clash/V2Ray) 运行在 127.0.0.1:7897" -ForegroundColor White
Write-Host "  3. 双击运行 YouTubeSmartReplace.exe" -ForegroundColor White
Write-Host "  4. 将浏览器代理设置为 127.0.0.1:8080" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Read-Host "按回车键退出"
