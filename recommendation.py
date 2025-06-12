import random
import datetime
from astrbot.api import logger

from .food_utils import get_season, get_weather, REASON_TEMPLATES, FOOD_CATEGORIES
from .image_generator import get_food_image

# 实现llm_recommend_food方法
async def llm_recommend_food(prompt, context=None):
    """
    使用大模型生成文本的函数

    Args:
        prompt: 提示词
        context: 上下文对象，用于调用大模型

    Returns:
        str: 大模型生成的文本
    """
    logger.info(f"调用llm_recommend_food方法，提示词: {prompt}")

    # 检查是否有context对象
    if not context:
        logger.warning("没有context对象，无法调用大模型")
        return f"这是固定回复，因为没有context对象"

    try:
        # 根据官方文档，正确的调用大模型的方式是通过context.get_using_provider()
        # 检查context对象是否有get_using_provider()方法
        if hasattr(context, 'get_using_provider'):
            provider = context.get_using_provider()
            if provider:
                # 使用provider调用大模型
                import random
                session_id = f"food_recommendation_{random.randint(1000, 9999)}"
                llm_response = await provider.text_chat(
                    prompt=prompt,
                    session_id=session_id
                )
                logger.info(f"成功使用provider调用大模型")
                return llm_response.completion_text.strip() if hasattr(llm_response, 'completion_text') else llm_response.strip()
        else:
            logger.warning("无法获取provider，返回固定回复")
            return f"这是固定回复，因为无法获取provider"
    except Exception as e:
        logger.error(f"调用大模型失败: {e}")
        return f"这是固定回复，因为调用大模型失败: {e}"

# 尝试导入动态食物生成器
try:
    from .dynamic_food_generator import generate_food
    DYNAMIC_FOOD_GENERATOR_AVAILABLE = True
    logger.info("成功导入动态食物生成器")
except ImportError as e:
    logger.warning(f"无法导入动态食物生成器，将使用静态食物列表: {e}")
    DYNAMIC_FOOD_GENERATOR_AVAILABLE = False

# 生成食物推荐 - 更新为支持AI生成图片和动态描述
async def generate_food_recommendation(meal_type=None, context=None):
    # 导入动态生成描述和推荐理由的函数
    try:
        from .generate_description import generate_food_description, generate_recommendation_reason
        dynamic_generation_available = True
        logger.info("成功导入动态生成描述和推荐理由的函数")
    except ImportError as e:
        logger.warning(f"无法导入动态生成函数，将使用静态模板: {e}")
        dynamic_generation_available = False

    # 获取当前日期和时间
    now = datetime.datetime.now()
    date = now.strftime("%Y年%m月%d日")
    hour = now.hour

    # 根据时间确定推荐的餐点类型
    if meal_type is None:
        if 5 <= hour < 10:
            time_of_day = "早上"
            meal_type = "早餐"
        elif 10 <= hour < 14:
            time_of_day = "中午"
            meal_type = random.choice(["中餐", "快餐", "面食"])
        elif 14 <= hour < 17:
            time_of_day = "下午"
            meal_type = "甜点"
        elif 17 <= hour < 21:
            time_of_day = "晚上"
            meal_type = random.choice(["中餐", "快餐", "面食"])
        else:
            time_of_day = "夜里"
            meal_type = random.choice(["快餐", "面食"])
    else:
        # 如果明确指定了用餐类型
        if "早" in meal_type:
            time_of_day = "早上"
            meal_type = "早餐"
        elif "中" in meal_type or "午" in meal_type:
            time_of_day = "中午"
            meal_type = random.choice(["中餐", "快餐", "面食"])
        elif "晚" in meal_type:
            time_of_day = "晚上"
            meal_type = random.choice(["中餐", "快餐", "面食"])
        else:
            time_of_day = "现在"
            meal_type = random.choice(list(FOOD_CATEGORIES.keys()))

    # 获取天气信息，将用户文本传入以识别城市
    user_text = None
    if hasattr(context, 'last_user_text'):
        user_text = context.last_user_text

    # 检查是否有用户指定的城市
    if hasattr(context, 'user_specified_city') and context.user_specified_city:
        specified_city = context.user_specified_city
        logger.info(f"用户指定了城市: {specified_city}")
        # 如果用户指定了城市，使用指定的城市获取天气
        weather_info = await get_weather(specified_city)
        # 注意：不清除城市信息，因为可能需要重试
    else:
        # 否则使用用户文本识别城市
        weather_info = await get_weather(user_text)

    temperature = weather_info["temperature"]
    weather = weather_info["weather"]
    city = weather_info.get("city", "上海")

    logger.info(f"最终使用的城市: {city}, 温度: {temperature}, 天气: {weather}")

    # 获取当前季节
    season = get_season()

    # 动态生成食物推荐
    if DYNAMIC_FOOD_GENERATOR_AVAILABLE:
        try:
            # 使用动态食物生成器，传递context.context参数
            # 如果context有context属性，则传递context.context，否则传递context
            actual_context = context.context if hasattr(context, 'context') else context
            food = await generate_food(meal_type, weather, temperature, season, user_text, actual_context)
            logger.info(f"动态生成的食物推荐: {food}")
        except Exception as e:
            logger.error(f"动态生成食物失败: {e}")
            # 如果动态生成失败，使用静态食物列表
            if meal_type in FOOD_CATEGORIES:
                food = random.choice(FOOD_CATEGORIES[meal_type])
            else:
                # 从所有食物中随机选择
                all_foods = []
                for foods in FOOD_CATEGORIES.values():
                    all_foods.extend(foods)
                food = random.choice(all_foods)
    else:
        # 如果动态食物生成器不可用，使用静态食物列表
        if meal_type in FOOD_CATEGORIES:
            food = random.choice(FOOD_CATEGORIES[meal_type])
        else:
            # 从所有食物中随机选择
            all_foods = []
            for foods in FOOD_CATEGORIES.values():
                all_foods.extend(foods)
            food = random.choice(all_foods)

    # 获取食物图片
    if hasattr(context, 'OUTPUT_DIR'):
        image_path = await get_food_image(food, context.OUTPUT_DIR, None, context)
    else:
        # 如果context没有必要的属性，则传递None
        image_path = None
        logger.warning("context缺少OUTPUT_DIR属性，无法获取食物图片")

    # 测试context对象的结构
    if context:
        # 输出context对象的所有属性
        attrs = [attr for attr in dir(context) if not attr.startswith('__')]
        logger.info(f"context对象的属性: {attrs}")

        # 检查是否有llm相关的属性
        llm_attrs = [attr for attr in attrs if 'llm' in attr.lower()]
        logger.info(f"context对象的llm相关属性: {llm_attrs}")

        # 检查是否有provider相关的属性
        provider_attrs = [attr for attr in attrs if 'provider' in attr.lower()]
        logger.info(f"context对象的provider相关属性: {provider_attrs}")

        # 检查是否有get_using_provider方法
        if hasattr(context, 'get_using_provider'):
            try:
                provider = context.get_using_provider()
                if provider and hasattr(provider, 'text_chat'):
                    logger.info(f"context.get_using_provider()方法可用，并且返回的对象有text_chat()方法")
                else:
                    logger.info(f"context.get_using_provider()方法可用，但返回的对象没有text_chat()方法")
            except Exception as e:
                logger.error(f"context.get_using_provider()方法异常: {e}")
        else:
            logger.info(f"context对象没有get_using_provider()方法")

    # 动态生成食物描述和推荐理由
    if dynamic_generation_available:
        try:
            # 尝试动态生成食物描述，传递context.context参数
            # 如果context有context属性，则传递context.context，否则传递context
            actual_context = context.context if hasattr(context, 'context') else context
            description = await generate_food_description(food, actual_context)

            # 尝试动态生成推荐理由，传递context.context参数
            reason = await generate_recommendation_reason(food, weather, temperature, date, time_of_day, season, city, actual_context)

            logger.info(f"成功动态生成食物描述和推荐理由")
        except Exception as e:
            logger.error(f"动态生成失败: {e}")
            # 如果动态生成失败，使用默认描述
            description = f"{food}是一道深受大众喜爱的美食，口感独特，风味绝佳。"

            # 选择一个推荐理由模板
            reason_template = random.choice(REASON_TEMPLATES)
            city_text = f"在{city}" if city else ""
            reason = reason_template.format(
                food=food,
                date=date,
                time_of_day=time_of_day,
                weather=weather,
                temperature=temperature,
                season=season,
                city_text=city_text
            )
    else:
        # 使用默认描述
        description = f"{food}是一道深受大众喜爱的美食，口感独特，风味绝佳。"

        # 选择一个推荐理由模板
        reason_template = random.choice(REASON_TEMPLATES)
        city_text = f"在{city}" if city else ""
        reason = reason_template.format(
            food=food,
            date=date,
            time_of_day=time_of_day,
            weather=weather,
            temperature=temperature,
            season=season,
            city_text=city_text
        )

    # 组装结果
    result = {
        "food": food,
        "reason": reason,
        "description": description,
        "image_path": image_path,
        "date": date,
        "time_of_day": time_of_day,
        "weather": weather,
        "temperature": temperature,
        "season": season,
        "meal_type": meal_type
    }

    return result
