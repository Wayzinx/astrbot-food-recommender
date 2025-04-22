import json
import time
import hmac
import hashlib
import base64
import urllib.parse
import aiohttp
from astrbot.api import logger

async def generate_image(access_key, secret_key, prompt, width=1024, height=1024, model="high_aes_general_v21_L", schedule_conf="general_v20_9B_pe", region="cn-north-1", service="cv"):
    """
    使用豆包API生成图片

    Args:
        access_key: API访问密钥
        secret_key: API密钥
        prompt: 提示词
        width: 图片宽度
        height: 图片高度
        model: 模型名称
        schedule_conf: 调度配置
        region: 区域
        service: 服务名称

    Returns:
        dict: 包含生成结果的字典
    """
    try:
        # 构建请求URL
        host = "open.volcengineapi.com"
        request_uri = "/v2/aigc/image/txt2img"
        url = f"https://{host}{request_uri}"

        # 构建请求参数
        params = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "model": model,
            "schedule_conf": schedule_conf
        }

        # 构建请求头
        headers = {
            "Content-Type": "application/json",
            "Host": host
        }

        # 获取当前时间戳
        timestamp = int(time.time())
        date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(timestamp))

        # 构建规范请求
        canonical_request = "POST\n"
        canonical_request += request_uri + "\n"
        canonical_request += "\n"  # 查询字符串为空

        # 添加规范头
        canonical_headers = f"content-type:application/json\nhost:{host}\n"
        canonical_request += canonical_headers + "\n"

        # 添加签名头
        signed_headers = "content-type;host"
        canonical_request += signed_headers + "\n"

        # 添加请求体哈希
        payload = json.dumps(params)
        payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        canonical_request += payload_hash

        # 构建签名字符串
        algorithm = "HMAC-SHA256"
        credential_scope = f"{date}/{region}/{service}/request"
        string_to_sign = f"{algorithm}\n{date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

        # 计算签名
        k_date = hmac.new(f"VOLCENGINE2/{secret_key}/{date}/{region}/{service}/request".encode('utf-8'),
                         date.encode('utf-8'), hashlib.sha256).digest()
        signature = hmac.new(k_date, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        # 构建授权头
        authorization = f"{algorithm} Credential={access_key}/{date}/{region}/{service}/request, SignedHeaders={signed_headers}, Signature={signature}"
        headers["Authorization"] = authorization
        headers["X-Date"] = date

        # 使用aiohttp异步发送请求
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=payload, timeout=30) as response:
                # 解析响应
                result = await response.json()

                # 检查响应状态
                if response.status != 200:
                    response_text = await response.text()
                    logger.error(f"API请求失败，状态码: {response.status}, 响应: {response_text}")
                    return {"code": -1, "message": f"API请求失败，状态码: {response.status}", "data": None}

                # 检查API响应
                if "ResponseMetadata" in result and "Error" in result["ResponseMetadata"]:
                    error = result["ResponseMetadata"]["Error"]
                    logger.error(f"API返回错误: {error}")
                    return {"code": -1, "message": f"API返回错误: {error}", "data": None}

                # 提取图片URL
                if "Result" in result and "Images" in result["Result"] and len(result["Result"]["Images"]) > 0:
                    image_urls = [img["Url"] for img in result["Result"]["Images"]]
                    return {"code": 10000, "message": "成功", "data": {"image_urls": image_urls}}
                else:
                    logger.error(f"API响应中未找到图片URL: {result}")
                    return {"code": -1, "message": "API响应中未找到图片URL", "data": None}

    except Exception as e:
        logger.error(f"生成图片时出错: {e}")
        return {"code": -1, "message": f"生成图片时出错: {e}", "data": None}
