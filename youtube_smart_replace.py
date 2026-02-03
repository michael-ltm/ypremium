"""
YouTube India 智能部分替换脚本 - 用于 mitmproxy
保留用户特定的动态数据，只替换关键内容

用法：
    mitmdump -s youtube_smart_replace.py --mode upstream:http://127.0.0.1:7897
"""

import json
import re
import copy
import os
import sys
from mitmproxy import http, ctx


def get_base_dir():
    """获取基础目录（支持打包后运行）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


# 印度成功响应文件路径（相对于脚本目录）
INDIA_RESPONSE_FILE = os.path.join(get_base_dir(), "india.md")

class YouTubeSmartReplace:
    """智能部分替换 YouTube Premium 页面响应"""

    def __init__(self):
        ctx.log.info("=" * 60)
        ctx.log.info("YouTube Smart Replacer 已启动 (部分替换模式)")
        ctx.log.info("=" * 60)
        
        # 加载印度成功响应
        self.india_data = None
        try:
            with open(INDIA_RESPONSE_FILE, 'r', encoding='utf-8') as f:
                self.india_data = json.loads(f.read())
                ctx.log.info(f"[成功] 已加载印度响应模板")
        except Exception as e:
            ctx.log.error(f"[错误] 加载印度响应失败: {str(e)}")

    def request(self, flow: http.HTTPFlow) -> None:
        """修改请求参数"""
        if "youtube.com" not in flow.request.host:
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

    def modify_request_body(self, flow: http.HTTPFlow) -> None:
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
                    
                    # 删除可能暴露位置的数据
                    for key in ["locationInfo", "visitorData"]:
                        if key in client:
                            del client[key]
                    
                    modified = True

                if "user" in context:
                    if "locationInfo" in context["user"]:
                        del context["user"]["locationInfo"]

            if modified:
                flow.request.content = json.dumps(data, separators=(',', ':')).encode('utf-8')
                ctx.log.info(f"[请求] hl: {original_hl} -> en-IN")

        except Exception as e:
            ctx.log.error(f"[错误] 修改请求失败: {str(e)}")

    def response(self, flow: http.HTTPFlow) -> None:
        """处理响应"""
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

    def log_payment_request(self, flow: http.HTTPFlow) -> None:
        """记录支付请求用于调试"""
        try:
            ctx.log.info(f"[支付API] {flow.request.method} {flow.request.host}{flow.request.path}")
            base_dir = get_base_dir()
            if flow.request.content:
                with open(os.path.join(base_dir, "debug_payment_request.txt"), 'w', encoding='utf-8') as f:
                    f.write(f"URL: {flow.request.url}\n\n")
                    f.write(f"Headers:\n{dict(flow.request.headers)}\n\n")
                    f.write(f"Body:\n{flow.request.content.decode('utf-8', errors='ignore')}")
            if flow.response.content:
                with open(os.path.join(base_dir, "debug_payment.json"), 'w', encoding='utf-8') as f:
                    f.write(flow.response.content.decode('utf-8', errors='ignore'))
        except Exception as e:
            ctx.log.error(f"[错误] 记录支付信息失败: {e}")

    def smart_replace_browse(self, flow: http.HTTPFlow) -> None:
        """智能部分替换 browse 响应"""
        if not self.india_data:
            ctx.log.error("[错误] 印度响应模板未加载")
            return

        try:
            if not flow.request.content:
                return
                
            req_data = json.loads(flow.request.content.decode('utf-8'))
            browse_id = req_data.get("browseId", "")
            
            if browse_id != "SPunlimited":
                return
                
            original_content = flow.response.content.decode('utf-8')
            
            # 检测是否需要替换（支持多语言错误页面）
            error_indicators = [
                "couldn't verify", "could not verify",
                "no hemos podido verificar",
                "无法验证", "無法驗證",
                "確認できません",
                "Centro de Ayuda", "Help Center",
            ]
            
            has_error = any(indicator.lower() in original_content.lower() for indicator in error_indicators)
            has_purchase_options = "lpOfferCard" in original_content or "premiumPurchaseButton" in original_content
            
            if not has_error and has_purchase_options:
                ctx.log.info("[跳过] 响应正常，无需替换")
                return
            
            ctx.log.info(f"[检测到] 需要替换 (错误页面={has_error}, 有购买选项={has_purchase_options})")
            
            # 解析原始响应
            original_data = json.loads(original_content)
            
            # 创建合并后的响应
            merged = self.merge_responses(original_data, self.india_data)
            
            if merged:
                result = json.dumps(merged, separators=(',', ':'), ensure_ascii=False)
                flow.response.content = result.encode('utf-8')
                flow.response.headers["Content-Length"] = str(len(result))
                ctx.log.info(f"[成功] 智能替换完成！保留了用户动态数据")
                
                # 保存调试信息
                with open(os.path.join(get_base_dir(), "debug_merged.json"), 'w', encoding='utf-8') as f:
                    json.dump(merged, f, indent=2, ensure_ascii=False)
                ctx.log.info("[调试] 已保存合并后的响应到 debug_merged.json")
            else:
                ctx.log.error("[错误] 合并响应失败")
                
        except Exception as e:
            ctx.log.error(f"[错误] 智能替换失败: {str(e)}")

    def merge_responses(self, original: dict, template: dict) -> dict:
        """
        智能合并响应：
        - 保留原始响应的用户特定数据
        - 使用模板的内容部分
        """
        try:
            # 深拷贝模板作为基础
            merged = copy.deepcopy(template)
            
            # === 1. 保留 responseContext 中的用户特定数据 ===
            if "responseContext" in original and "responseContext" in merged:
                orig_ctx = original["responseContext"]
                merged_ctx = merged["responseContext"]
                
                # 保留 mainAppWebResponseContext（包含 datasyncId, trackingParam 等）
                if "mainAppWebResponseContext" in orig_ctx:
                    merged_ctx["mainAppWebResponseContext"] = orig_ctx["mainAppWebResponseContext"]
                    ctx.log.info("[保留] mainAppWebResponseContext (datasyncId, trackingParam)")
                
                # 保留 serviceTrackingParams 中的某些参数
                if "serviceTrackingParams" in orig_ctx:
                    # 保留原始的 tracking 参数
                    merged_ctx["serviceTrackingParams"] = orig_ctx["serviceTrackingParams"]
                    ctx.log.info("[保留] serviceTrackingParams")
            
            # === 2. 保留 topbar 中的用户信息 ===
            if "topbar" in original:
                merged["topbar"] = original["topbar"]
                ctx.log.info("[保留] topbar (用户头像等)")
            
            # === 3. 替换 contents 为印度模板（核心：价格和订阅选项）===
            # 这是关键部分，使用模板的 contents
            if "contents" in template:
                # 深度合并：尝试保留原始响应中的某些动态 ID
                self.update_tracking_params_in_contents(merged["contents"], original)
                ctx.log.info("[替换] contents (使用印度价格)")
            
            # === 4. 处理特殊字段 ===
            # 保留原始响应中的 frameworkUpdates（如果存在）
            if "frameworkUpdates" in original:
                merged["frameworkUpdates"] = original["frameworkUpdates"]
                ctx.log.info("[保留] frameworkUpdates")
            
            return merged
            
        except Exception as e:
            ctx.log.error(f"[错误] 合并响应失败: {str(e)}")
            return None

    def update_tracking_params_in_contents(self, contents: dict, original: dict) -> None:
        """
        尝试更新 contents 中的某些动态参数
        这是一个递归函数，会遍历所有嵌套对象
        """
        try:
            # 提取原始响应中的一些关键 tracking ID
            original_str = json.dumps(original)
            
            # 查找原始响应中的 encrypted_pageid
            encrypted_pageid_match = re.search(r'"encrypted_pageid"\s*,\s*"value"\s*:\s*"([^"]+)"', original_str)
            if encrypted_pageid_match:
                orig_pageid = encrypted_pageid_match.group(1)
                # 在合并后的响应中替换
                contents_str = json.dumps(contents)
                if "encrypted_pageid" in contents_str:
                    # 这里我们保留模板的 pageid，因为它可能与价格数据相关
                    pass
            
        except Exception as e:
            ctx.log.error(f"[警告] 更新 tracking 参数失败: {str(e)}")

    def modify_country_in_response(self, flow: http.HTTPFlow) -> None:
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


addons = [YouTubeSmartReplace()]
