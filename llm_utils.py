import random
from astrbot.api import logger

async def call_llm(context, prompt, session_id_prefix="food"):
    """
    统一的LLM调用函数，简化LLM调用逻辑
    
    Args:
        context: 上下文对象，用于调用LLM
        prompt: 提示词
        session_id_prefix: 会话ID前缀，用于区分不同的调用
        
    Returns:
        str: LLM生成的文本，如果调用失败则返回None
    """
    if not context:
        logger.warning("无法调用LLM：context对象为空")
        return None
        
    try:
        # 使用context.get_using_provider()方法调用LLM
        if hasattr(context, 'get_using_provider') and callable(getattr(context, 'get_using_provider')):
            provider = context.get_using_provider()
            if provider:
                # 生成随机会话ID
                session_id = f"{session_id_prefix}_{random.randint(1000, 9999)}"
                
                # 调用LLM
                llm_response = await provider.text_chat(
                    prompt=prompt,
                    session_id=session_id
                )
                
                # 提取响应文本
                response_text = llm_response.completion_text.strip() if hasattr(llm_response, 'completion_text') else llm_response.strip()
                logger.info(f"成功调用LLM，生成文本: {response_text[:30]}...")
                return response_text
            else:
                logger.warning("无法获取LLM provider")
                return None
        else:
            logger.warning("context对象不支持get_using_provider方法")
            return None
    except Exception as e:
        logger.error(f"调用LLM失败: {e}")
        return None
