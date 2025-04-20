import hashlib
from astrbot.api import logger
from .llm_utils import call_llm

# 预定义的食物描述模板
DESCRIPTION_TEMPLATES = [
    "{food_name}是一道深受大众喜爱的美食，口感独特，风味绝佳。",
    "{food_name}以其独特的口感和丰富的风味而闻名，是一道不可错过的美食。",
    "{food_name}的口感鲜嫩可口，风味独特，是一道深受喜爱的美食。",
    "{food_name}的香气四溢，口感丰富，是一道让人回味无穷的美食。",
    "{food_name}的风味独特，营养丰富，是一道满足味觉和营养需求的美食。"
]

# 获取模板描述
def get_template_description(food_name):
    """使用预定义模板生成食物描述"""
    hash_value = int(hashlib.md5(food_name.encode()).hexdigest(), 16)
    description = DESCRIPTION_TEMPLATES[hash_value % len(DESCRIPTION_TEMPLATES)].format(food_name=food_name)
    logger.info(f"使用模板为\"{food_name}\"生成描述: {description}")
    return description

# 动态生成食物描述的函数
async def generate_food_description(food_name, context=None):
    """使用大模型生成食物描述"""
    # 构建提示词
    prompt = f"""请为食物"{food_name}"生成一段简短的描述，包含其特点、口感和鲜明特点。不超过50个字。
只返回描述文本，不要包含其他内容。"""

    # 调用LLM
    description = await call_llm(context, prompt, session_id_prefix="food_description")

    # 如果LLM调用失败，使用模板
    if not description:
        return get_template_description(food_name)

    return description

# 预定义的推荐理由模板
REASON_TEMPLATES = [
    "今天{date}，{city_text}{temperature}°C的{weather}天气下，来一份{food_name}绝对是明智之选！",
    "{date}的{city_text}{weather}天气，{temperature}°C的温度非常适合品尝{food_name}，给你的味蕾带来惊喜！",
    "{season}季节{city_text}{temperature}°C的{weather}天气，正是品尝{food_name}的最佳时机，不要错过！",
    "{city_text}{date}的{weather}天气，{temperature}°C的温度下，{food_name}的美味会加倍提升！",
    "{time_of_day}时分的{city_text}{weather}天气，配上一份美味的{food_name}，完美的享受！"
]

# 获取模板推荐理由
def get_template_reason(food_name, weather, temperature, date, time_of_day, season, city=None):
    """使用预定义模板生成推荐理由"""
    city_text = f"在{city}" if city else ""

    # 根据食物名称、天气和日期选择一个推荐理由
    hash_input = f"{food_name}{weather}{date}".encode()
    hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
    template = REASON_TEMPLATES[hash_value % len(REASON_TEMPLATES)]

    # 格式化模板
    reason = template.format(
        food_name=food_name,
        weather=weather,
        temperature=temperature,
        date=date,
        time_of_day=time_of_day,
        season=season,
        city_text=city_text
    )

    logger.info(f"使用模板为\"{food_name}\"生成推荐理由: {reason}")
    return reason

# 生成推荐理由的函数
async def generate_recommendation_reason(food_name, weather, temperature, date, time_of_day, season, city=None, context=None):
    """使用大模型生成推荐理由"""
    # 构建提示词
    prompt = f"""请为食物"{food_name}"生成一段推荐理由，考虑以下因素：
- 天气：{weather}
- 温度：{temperature}°C
- 日期：{date}
- 时间：{time_of_day}
- 季节：{season}"""

    # 如果有城市信息，添加到提示词中
    if city:
        prompt += f"\n- 城市：{city}"

    prompt += "\n\n生成一段简短的推荐理由，不超过50个字。只返回推荐理由文本，不要包含其他内容。"

    # 调用LLM
    reason = await call_llm(context, prompt, session_id_prefix="food_reason")

    # 如果LLM调用失败，使用模板
    if not reason:
        return get_template_reason(food_name, weather, temperature, date, time_of_day, season, city)

    return reason
