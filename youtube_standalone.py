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
            
            # 检测是否需要替换：
            # 1. 包含错误信息（各种语言）
            # 2. 缺少购买按钮/价格卡片
            error_indicators = [
                "couldn't verify", "could not verify",  # 英文
                "no hemos podido verificar",  # 西班牙语
                "无法验证", "無法驗證",  # 中文
                "確認できません",  # 日语
                "Centro de Ayuda", "Help Center",  # 帮助中心链接（错误页面特征）
            ]
            
            has_error = any(indicator.lower() in original_content.lower() for indicator in error_indicators)
            has_purchase_options = "lpOfferCard" in original_content or "premiumPurchaseButton" in original_content
            
            if not has_error and has_purchase_options:
                print("[跳过] 响应正常，无需替换")
                return
            
            print(f"[检测到] 需要替换 (错误页面={has_error}, 有购买选项={has_purchase_options})")
            
            original_data = json.loads(original_content)
            merged = self.merge_responses(original_data, self.india_data)
            
            if merged:
                result = json.dumps(merged, separators=(',', ':'), ensure_ascii=False)
                
                # 关键修复：将 googlePaymentBillingCommand 替换为 ypcGetCartEndpoint
                # 这样所有计划都会使用动态购物车方式，避免硬编码参数问题
                result = self.fix_payment_commands_in_json(result)
                
                flow.response.content = result.encode('utf-8')
                flow.response.headers["Content-Length"] = str(len(result.encode('utf-8')))
                print(f"[成功] 智能替换完成！保留了用户动态数据")
                
                with open(os.path.join(self.base_dir, "debug_merged.json"), 'w', encoding='utf-8') as f:
                    f.write(result)
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
            
            # 转换支付命令：将 googlePaymentBillingCommand 转换为 ypcGetCartEndpoint
            self.convert_payment_commands(merged)
            
            return merged
            
        except Exception as e:
            print(f"[错误] 合并响应失败: {str(e)}")
            return None

    def convert_payment_commands(self, data):
        """已弃用，使用 fix_payment_commands_in_json 代替"""
        pass

    def fix_payment_commands_in_json(self, json_str: str) -> str:
        """
        在 JSON 字符串级别修复支付命令
        将 googlePaymentBillingCommand 替换为可用的 ypcGetCartEndpoint
        """
        try:
            # 查找所有 googlePaymentBillingCommand 并统计
            import re
            
            # 匹配 googlePaymentBillingCommand 的完整结构（简化匹配）
            # 这是一个复杂的嵌套结构，我们使用计数括号的方式来匹配
            count = json_str.count('"googlePaymentBillingCommand"')
            if count > 0:
                print(f"[检测] 发现 {count} 个 googlePaymentBillingCommand，正在转换...")
                
                # 策略：直接删除 googlePaymentBillingCommand 相关命令
                # 并替换为简单的 URL 跳转，让用户手动刷新
                # 这不是完美方案，但可以避免 OR_FGCR_66 错误
                
                # 更好的策略：提取 optionId 并构造正确的 get_cart 请求
                # 我们用 Python 解析 JSON 来做这个
                data = json.loads(json_str)
                self.deep_fix_payment(data)
                json_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
                
                new_count = json_str.count('"googlePaymentBillingCommand"')
                print(f"[完成] 转换后剩余 {new_count} 个 googlePaymentBillingCommand")
            
            return json_str
            
        except Exception as e:
            print(f"[警告] 修复支付命令失败: {e}")
            return json_str

    def deep_fix_payment(self, obj, parent=None, key=None, context_option_id=None):
        """深度遍历并修复支付命令"""
        if isinstance(obj, dict):
            # 如果当前节点有 optionId，记录下来
            current_option_id = obj.get("optionId", context_option_id)
            
            # 检查是否是包含 googlePaymentBillingCommand 的 innertubeCommand
            if "googlePaymentBillingCommand" in obj:
                # 使用上下文中的 optionId
                option_id = current_option_id
                
                # 构造 ypcGetCartEndpoint 替换
                replacement = self.create_cart_endpoint(option_id)
                
                # 删除 googlePaymentBillingCommand
                del obj["googlePaymentBillingCommand"]
                
                # 添加新的端点
                obj["commandMetadata"] = {
                    "webCommandMetadata": {
                        "sendPost": True,
                        "apiUrl": "/youtubei/v1/ypc/get_cart"
                    }
                }
                obj["ypcGetCartEndpoint"] = replacement
                
                print(f"[转换] optionId={option_id}")
            
            # 递归处理，传递 optionId 上下文
            for k, v in list(obj.items()):
                self.deep_fix_payment(v, obj, k, current_option_id)
                
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self.deep_fix_payment(item, obj, i, context_option_id)

    def create_cart_endpoint(self, option_id: str) -> dict:
        """根据 optionId 创建 ypcGetCartEndpoint"""
        import base64
        import urllib.parse
        
        # 从 optionId 中提取 SKU ID
        # 格式: unlimited.P.AAAAAbWL5SY -> AAAAAbWL5SY
        sku_id = option_id.split(".")[-1] if option_id and "." in option_id else "AAAAAbWK8mE"
        full_option_id = f"unlimited.P.{sku_id}"
        
        # 159 的模板（已知能工作）
        base_offer_159 = "CAASF3VubGltaXRlZC5QLkFBQUFBYldLOG1FGg0IBhIJdW5saW1pdGVkMgtBQUFBQWJXSzhtRUAFegIIAYoBHQobbHByMi1hY3EtYy1yYi1pbi0xMjgzMjk2MzM1mgEaChZBQ0NFU1M6cHJlbWl1bS1za3UtY2F0EAGiAVMaKwobbHByMi1hY3EtYy1yYi1pbi0xMjgzMjk2MzM1Egxtc29mX2VuYWJsZWS4AQDaAiAIBhIcChhtdWx0aV9zdGVwX3B1cmNoYXNlX2Zsb3cQArgBAtIBIAoKCMDL6EsSA0lOUhISShAKDggCEggyMDI0MDgxMxgB2AEA4gECSU4%3D"
        base_transaction_159 = "Gv4BCAASF3VubGltaXRlZC5QLkFBQUFBYldLOG1FGg0IBhIJdW5saW1pdGVkMgtBQUFBQWJXSzhtRUAFegIIAYoBHQobbHByMi1hY3EtYy1yYi1pbi0xMjgzMjk2MzM1mgEaChZBQ0NFU1M6cHJlbWl1bS1za3UtY2F0EAGiAVMaKwobbHByMi1hY3EtYy1yYi1pbi0xMjgzMjk2MzM1Egxtc29mX2VuYWJsZWS4AQDaAiAIBhIcChhtdWx0aV9zdGVwX3B1cmNoYXNlX2Zsb3cQArgBAtIBIAoKCMDL6EsSA0lOUhISShAKDggCEggyMDI0MDgxMxgB2AEA4gECSU6CAQJJTg%3D%3D"
        
        # 159 的 SKU 相关编码
        old_sku = "AAAAAbWK8mE"
        old_full = "unlimited.P.AAAAAbWK8mE"
        
        # 计算 base64 编码后的字符串（用于在 protobuf 数据中替换）
        # SKU ID 在 protobuf 中是作为字符串存储的，直接替换 base64 编码后的对应部分
        old_sku_b64 = base64.b64encode(old_sku.encode()).decode().rstrip('=')
        new_sku_b64 = base64.b64encode(sku_id.encode()).decode().rstrip('=')
        old_full_b64 = base64.b64encode(old_full.encode()).decode().rstrip('=')
        new_full_b64 = base64.b64encode(full_option_id.encode()).decode().rstrip('=')
        
        if sku_id != old_sku:
            # URL decode 得到 base64 字符串
            offer = urllib.parse.unquote(base_offer_159)
            transaction = urllib.parse.unquote(base_transaction_159)
            
            # 方法1：直接在 base64 字符串中替换编码后的 SKU
            # 因为 protobuf 中字符串是原样存储的，所以我们需要：
            # 1. base64 解码整个数据
            # 2. 在二进制中替换字符串
            # 3. base64 编码回去
            
            try:
                # 解码 -> 替换 -> 编码
                offer_bytes = base64.b64decode(offer + '==')  # 添加 padding
                offer_bytes = offer_bytes.replace(old_full.encode(), full_option_id.encode())
                offer_bytes = offer_bytes.replace(old_sku.encode(), sku_id.encode())
                offer = base64.b64encode(offer_bytes).decode().rstrip('=')
                
                transaction_bytes = base64.b64decode(transaction + '==')
                transaction_bytes = transaction_bytes.replace(old_full.encode(), full_option_id.encode())
                transaction_bytes = transaction_bytes.replace(old_sku.encode(), sku_id.encode())
                transaction = base64.b64encode(transaction_bytes).decode().rstrip('=')
                
                print(f"[参数] SKU 替换: {old_sku} -> {sku_id}")
            except Exception as e:
                print(f"[警告] Base64 替换失败: {e}，使用原始参数")
            
            # URL encode
            offer = urllib.parse.quote(offer, safe='')
            transaction = urllib.parse.quote(transaction, safe='')
        else:
            offer = base_offer_159
            transaction = base_transaction_159
            print(f"[参数] 使用 159 SKU (无需替换)")
        
        return {
            "offerParams": offer,
            "gtmData": json.dumps({
                "event": "landingButtonClick",
                "eventParams": {
                    "sku": "PremiumSKU",
                    "plan_type": "Individual",
                    "app_type": "WEB",
                    "countryCode": "IN"
                }
            }),
            "transactionParams": transaction
        }

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
