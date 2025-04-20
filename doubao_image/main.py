import json
from datetime import datetime, timezone
import hashlib
import hmac
import requests

# 使用AstrBot的日志系统
from astrbot.api import logger

method = 'POST'
host = 'visual.volcengineapi.com'
endpoint = 'https://visual.volcengineapi.com'

def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

def getSignatureKey(key, dateStamp, regionName, serviceName):
    kDate = sign(key.encode('utf-8'), dateStamp)
    kRegion = sign(kDate, regionName)
    kService = sign(kRegion, serviceName)
    kSigning = sign(kService, 'request')
    return kSigning

def formatQuery(parameters):
    request_parameters_init = ''
    for key in sorted(parameters):
        request_parameters_init += key + '=' + parameters[key] + '&'
    request_parameters = request_parameters_init[:-1]
    return request_parameters

def signV4Request(access_key, secret_key, service, req_query, req_body, region="cn-north-1"):
    if access_key is None or secret_key is None:
        logger.error('No access key is available.')
        return None

    t = datetime.now(timezone.utc)
    current_date = t.strftime('%Y%m%dT%H%M%SZ')
    datestamp = t.strftime('%Y%m%d')  # Date w/o time, used in credential scope
    canonical_uri = '/'
    canonical_querystring = req_query
    signed_headers = 'content-type;host;x-content-sha256;x-date'
    payload_hash = hashlib.sha256(req_body.encode('utf-8')).hexdigest()
    content_type = 'application/json'
    canonical_headers = 'content-type:' + content_type + '\n' + 'host:' + host + \
        '\n' + 'x-content-sha256:' + payload_hash + \
        '\n' + 'x-date:' + current_date + '\n'
    canonical_request = method + '\n' + canonical_uri + '\n' + canonical_querystring + \
        '\n' + canonical_headers + '\n' + signed_headers + '\n' + payload_hash
    logger.info("Canonical request:")
    logger.info(canonical_request)
    algorithm = 'HMAC-SHA256'
    credential_scope = datestamp + '/' + region + '/' + service + '/' + 'request'
    string_to_sign = algorithm + '\n' + current_date + '\n' + credential_scope + '\n' + hashlib.sha256(
        canonical_request.encode('utf-8')).hexdigest()
    logger.info("String to sign:")
    logger.info(string_to_sign)
    signing_key = getSignatureKey(secret_key, datestamp, region, service)
    signature = hmac.new(signing_key, (string_to_sign).encode(
        'utf-8'), hashlib.sha256).hexdigest()
    logger.info("Signature:")
    logger.info(signature)

    authorization_header = algorithm + ' ' + 'Credential=' + access_key + '/' + \
        credential_scope + ', ' + 'SignedHeaders=' + \
        signed_headers + ', ' + 'Signature=' + signature
    headers = {'X-Date': current_date,
               'Authorization': authorization_header,
               'X-Content-Sha256': payload_hash,
               'Content-Type': content_type
               }

    # ************* SEND THE REQUEST *************
    request_url = endpoint + '?' + canonical_querystring

    logger.info('\nBEGIN REQUEST++++++++++++++++++++++++++++++++++++')
    logger.info('Request URL = ' + request_url)
    try:
        r = requests.post(request_url, headers=headers, data=req_body)
    except Exception as err:
        logger.error(f'error occurred: {err}')
        raise
    else:
        logger.info('\nRESPONSE++++++++++++++++++++++++++++++++++++')
        logger.info(f'Response code: {r.status_code}\n')
        # 使用 replace 方法将 \u0026 替换为 &
        resp_str = r.text.replace("\\u0026", "&")
        logger.info(f'Response body: {resp_str}\n')
        return r.json()


def generate_image(access_key, secret_key, prompt, width=1024, height=1024, model="high_aes_general_v21_L", schedule_conf="general_v20_9B_pe", region="cn-north-1", service="cv"):
    """
    生成图片的函数

    Args:
        access_key: 火山引擎API的访问密钥
        secret_key: 火山引擎API的密钥
        prompt: 图片生成提示词
        width: 图片宽度，默认1024
        height: 图片高度，默认1024
        model: 模型名称，默认为high_aes_general_v21_L
        schedule_conf: 调度配置，默认为general_v20_9B_pe
        region: 区域，默认为cn-north-1
        service: 服务名称，默认为cv

    Returns:
        dict: API返回的JSON结果
    """
    # 请求Query，按照接口文档中填入即可
    query_params = {
        'Action': 'CVProcess',
        'Version': '2022-08-31',
    }
    formatted_query = formatQuery(query_params)

    # 请求Body，按照接口文档中填入即可
    body_params = {
        "req_key": model,
        "prompt": prompt,
        "width": width,
        "height": height,
        "use_pre_llm": True,
        "use_sr": True,
        "return_url": True,
        "schedule_conf": schedule_conf,
        "logo_info": {
            "add_logo": False
        }
    }
    formatted_body = json.dumps(body_params)

    return signV4Request(access_key, secret_key, service, formatted_query, formatted_body, region)
