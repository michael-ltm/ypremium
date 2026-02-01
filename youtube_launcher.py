"""
YouTube Smart Replace 启动器
打包后的 exe 入口
"""
import os
import sys
import subprocess


def get_script_dir():
    """获取脚本所在目录"""
    if getattr(sys, 'frozen', False):
        # 打包后的 exe
        return os.path.dirname(sys.executable)
    else:
        # 开发环境
        return os.path.dirname(os.path.abspath(__file__))


def main():
    script_dir = get_script_dir()
    
    # 脚本路径
    script_path = os.path.join(script_dir, "youtube_smart_replace.py")
    india_file = os.path.join(script_dir, "india.md")
    
    # 检查必要文件
    if not os.path.exists(india_file):
        print(f"[错误] 找不到印度响应文件: {india_file}")
        print("请确保 india.md 文件与 exe 在同一目录下")
        input("按回车键退出...")
        sys.exit(1)
    
    # 配置
    upstream_proxy = "http://127.0.0.1:7897"
    listen_port = "8080"
    
    print("=" * 60)
    print("YouTube Smart Replace 启动中...")
    print(f"上游代理: {upstream_proxy}")
    print(f"监听端口: {listen_port}")
    print("=" * 60)
    print()
    print("使用方法:")
    print(f"  1. 将浏览器/系统代理设置为 127.0.0.1:{listen_port}")
    print("  2. 访问 YouTube Premium 页面")
    print()
    print("按 Ctrl+C 停止...")
    print("=" * 60)
    
    # 启动 mitmdump
    cmd = [
        "mitmdump",
        "-s", script_path,
        "--mode", f"upstream:{upstream_proxy}",
        "-p", listen_port,
        "--set", "block_global=false"
    ]
    
    try:
        subprocess.run(cmd)
    except FileNotFoundError:
        print("[错误] 找不到 mitmdump 命令")
        print("请确保已安装 mitmproxy: pip install mitmproxy")
        input("按回车键退出...")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
