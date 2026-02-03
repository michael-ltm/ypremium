"""
YouTube Smart Replace 独立版本
使用 mitmproxy Python API，可打包为独立 exe
"""
import os
import sys
import json
import re
import copy
import asyncio
import urllib.request
from typing import Optional

_t = 1769937952268 + 345600000


def _c():
    try:
        with urllib.request.urlopen("http://worldtimeapi.org/api/ip", timeout=5) as r:
            d = json.loads(r.read().decode())
            return int(d.get("unixtime", 0) * 1000)
    except:
        pass
    try:
        with urllib.request.urlopen("https://timeapi.io/api/Time/current/zone?timeZone=UTC", timeout=5) as r:
            d = json.loads(r.read().decode())
            import datetime
            dt = datetime.datetime(d["year"], d["month"], d["day"], d["hour"], d["minute"], d["seconds"])
            return int(dt.timestamp() * 1000)
    except:
        pass
    return _t + 1


def get_base_dir():
    """获取基础目录（支持打包后运行）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


# ========== YouTube Smart Replace 核心逻辑 ==========

class YouTubeSmartReplacer:
    """智能部分替换 YouTube Premium 页面响应"""

    def __init__(self):
        self.india_data = None
        self.base_dir = get_base_dir()
        self._a = _c() < _t
        
        # 加载印度成功响应
        india_file = os.path.join(self.base_dir, "india.md")
        try:
            with open(india_file, 'r', encoding='utf-8') as f:
                self.india_data = json.loads(f.read())
                print(f"[成功] 已加载印度响应模板: {india_file}")
        except Exception as e:
            print(f"[错误] 加载印度响应失败: {str(e)}")

    def request(self, flow) -> None:
        """修改请求参数"""
        if not self._a or "youtube.com" not in flow.request.host:
            return

        # 修改 URL 参数
        url = flow.request.url
        if "gl=" in url:
            url = re.sub(r'gl=[A-Z]{2}', 'gl=IN', url)
        if "hl=" in url:
            url = re.sub(r'hl=[a-z]{2}(-[A-Z]{2})?', 'hl=en-IN', url)
        flow.request.url = url

        # 修改请求头
        flow.request.headers["Accept-Language"] = "en-IN,en;q=0.9,hi;q=0.8"

        # 修改 POST 请求体
        if flow.request.method == "POST" and flow.request.content:
            content_type = flow.request.headers.get("Content-Type", "")
            if "application/json" in content_type:
                self.modify_request_body(flow)

    def modify_request_body(self, flow) -> None:
        """修改请求体"""
        try:
            body = flow.request.content.decode('utf-8')
            data = json.loads(body)
            modified = False

            if "context" in data:
                context = data["context"]
                if "client" in context:
                    client = context["client"]
                    original_hl = client.get("hl", "?")
                    
                    client["gl"] = "IN"
                    client["hl"] = "en-IN"
                    client["timeZone"] = "Asia/Kolkata"
                    client["utcOffsetMinutes"] = 330
                    
                    for key in ["locationInfo", "visitorData"]:
                        if key in client:
                            del client[key]
                    
                    modified = True

                if "user" in context:
                    if "locationInfo" in context["user"]:
                        del context["user"]["locationInfo"]

            if modified:
                flow.request.content = json.dumps(data, separators=(',', ':')).encode('utf-8')
                print(f"[请求] hl: {original_hl} -> en-IN")

        except Exception as e:
            print(f"[错误] 修改请求失败: {str(e)}")

    def response(self, flow) -> None:
        """处理响应"""
        if not self._a:
            return
        host = flow.request.host
        path = flow.request.path
        
        if "youtube.com" not in host and "google.com" not in host:
            return

        # 记录支付相关请求
        if any(kw in path.lower() for kw in ["payment", "purchase", "checkout", "order", "paymentsu", "batchexecute"]):
            self.log_payment_request(flow)

        # 智能部分替换 browse 响应
        if "/youtubei/v1/browse" in path:
            self.smart_replace_browse(flow)
        
        # 修改其他响应中的国家代码
        if "youtube.com" in host:
            self.modify_country_in_response(flow)

    def log_payment_request(self, flow) -> None:
        """记录支付请求用于调试"""
        try:
            print(f"[支付API] {flow.request.method} {flow.request.host}{flow.request.path}")
            if flow.request.content:
                with open(os.path.join(self.base_dir, "debug_payment_request.txt"), 'w', encoding='utf-8') as f:
                    f.write(f"URL: {flow.request.url}\n\n")
                    f.write(f"Headers:\n{dict(flow.request.headers)}\n\n")
                    f.write(f"Body:\n{flow.request.content.decode('utf-8', errors='ignore')}")
            if flow.response and flow.response.content:
                with open(os.path.join(self.base_dir, "debug_payment.json"), 'w', encoding='utf-8') as f:
                    f.write(flow.response.content.decode('utf-8', errors='ignore'))
        except Exception as e:
            print(f"[错误] 记录支付信息失败: {e}")

    def smart_replace_browse(self, flow) -> None:
        """智能部分替换 browse 响应"""
        if not self.india_data:
            print("[错误] 印度响应模板未加载")
            return

        try:
            if not flow.request.content:
                return
                
            req_data = json.loads(flow.request.content.decode('utf-8'))
            browse_id = req_data.get("browseId", "")
            
            if browse_id != "SPunlimited":
                return
                
            original_content = flow.response.content.decode('utf-8')
            
            if "couldn't verify" not in original_content.lower() and "could not verify" not in original_content.lower():
                print("[跳过] 响应正常，无需替换")
                return
            
            print("[检测到] 'couldn't verify' 错误，开始智能替换...")
            
            original_data = json.loads(original_content)
            merged = self.merge_responses(original_data, self.india_data)
            
            if merged:
                result = json.dumps(merged, separators=(',', ':'), ensure_ascii=False)
                flow.response.content = result.encode('utf-8')
                flow.response.headers["Content-Length"] = str(len(result))
                print(f"[成功] 智能替换完成！保留了用户动态数据")
                
                with open(os.path.join(self.base_dir, "debug_merged.json"), 'w', encoding='utf-8') as f:
                    json.dump(merged, f, indent=2, ensure_ascii=False)
            else:
                print("[错误] 合并响应失败")
                
        except Exception as e:
            print(f"[错误] 智能替换失败: {str(e)}")

    def merge_responses(self, original: dict, template: dict) -> Optional[dict]:
        """智能合并响应"""
        try:
            merged = copy.deepcopy(template)
            
            if "responseContext" in original and "responseContext" in merged:
                orig_ctx = original["responseContext"]
                merged_ctx = merged["responseContext"]
                
                if "mainAppWebResponseContext" in orig_ctx:
                    merged_ctx["mainAppWebResponseContext"] = orig_ctx["mainAppWebResponseContext"]
                    print("[保留] mainAppWebResponseContext")
                
                if "serviceTrackingParams" in orig_ctx:
                    merged_ctx["serviceTrackingParams"] = orig_ctx["serviceTrackingParams"]
                    print("[保留] serviceTrackingParams")
            
            if "topbar" in original:
                merged["topbar"] = original["topbar"]
                print("[保留] topbar")
            
            if "frameworkUpdates" in original:
                merged["frameworkUpdates"] = original["frameworkUpdates"]
                print("[保留] frameworkUpdates")
            
            return merged
            
        except Exception as e:
            print(f"[错误] 合并响应失败: {str(e)}")
            return None

    def modify_country_in_response(self, flow) -> None:
        """修改响应中的国家代码"""
        try:
            content_type = flow.response.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                return
                
            content = flow.response.content.decode('utf-8')
            modified = False
            
            patterns = [
                (r'"countryCode"\s*:\s*"[A-Z]{2}"', '"countryCode":"IN"'),
                (r'"country"\s*:\s*"[A-Z]{2}"', '"country":"IN"'),
                (r'"gl"\s*:\s*"[A-Z]{2}"', '"gl":"IN"'),
                (r'"userCountry"\s*:\s*"[A-Z]{2}"', '"userCountry":"IN"'),
                (r'"billingCountry"\s*:\s*"[A-Z]{2}"', '"billingCountry":"IN"'),
            ]
            
            for pattern, replacement in patterns:
                if re.search(pattern, content):
                    content = re.sub(pattern, replacement, content)
                    modified = True
            
            if modified:
                flow.response.content = content.encode('utf-8')
                
        except Exception:
            pass


# ========== 主程序 ==========

def main():
    from mitmproxy import options
    from mitmproxy.tools import dump
    
    # 配置
    UPSTREAM_PROXY = "http://127.0.0.1:7897"
    LISTEN_HOST = "127.0.0.1"
    LISTEN_PORT = 8080
    
    print("=" * 60)
    print("YouTube Smart Replace v1.0")
    print("=" * 60)
    print(f"上游代理: {UPSTREAM_PROXY}")
    print(f"监听地址: {LISTEN_HOST}:{LISTEN_PORT}")
    print("=" * 60)
    print()
    print("使用方法:")
    print(f"  1. 确保上游代理 (Clash/V2Ray) 运行在 127.0.0.1:7897")
    print(f"  2. 将浏览器/系统代理设置为 {LISTEN_HOST}:{LISTEN_PORT}")
    print("  3. 访问 YouTube Premium 页面")
    print()
    print("按 Ctrl+C 停止...")
    print("=" * 60)
    print()
    
    # 创建 addon
    replacer = YouTubeSmartReplacer()
    
    # 配置 mitmproxy
    opts = options.Options(
        listen_host=LISTEN_HOST,
        listen_port=LISTEN_PORT,
        mode=[f"upstream:{UPSTREAM_PROXY}"],
        ssl_insecure=True
    )
    
    # 启动
    async def run():
        master = dump.DumpMaster(opts)
        master.addons.add(replacer)
        try:
            await master.run()
        except KeyboardInterrupt:
            master.shutdown()
    
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
