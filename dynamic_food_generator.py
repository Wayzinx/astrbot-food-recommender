import random
import logging
from astrbot.api import logger

# 一些备用的食物列表，当LLM不可用时使用
BACKUP_FOODS = {
    "早餐": [
        "豆浆油条", "煎饼果子", "馄饨", "包子", "饺子", "茶叶蛋", "小米粥", "八宝粥",
        "烧饼", "肉夹馍", "手抓饼", "生煎包", "麻球", "三明治", "鸡蛋饼", "馒头", "茶鸡蛋"
    ],
    "中餐": [
        "红烧肉", "回锅肉", "宫保鸡丁", "麻婆豆腐", "水煮鱼", "东坡肉", "糖醋排骨",
        "鱼香肉丝", "西红柿炒鸡蛋", "小龙虾", "火锅", "酸菜鱼", "北京烤鸭", "清蒸鲈鱼",
        "葱爆羊肉", "辣子鸡", "酸辣土豆丝", "蒜蓉西兰花", "红烧排骨", "红烧猪蹄"
    ],
    "晚餐": [
        "红烧肉", "回锅肉", "宫保鸡丁", "麻婆豆腐", "水煮鱼", "东坡肉", "糖醋排骨",
        "鱼香肉丝", "西红柿炒鸡蛋", "小龙虾", "火锅", "酸菜鱼", "北京烤鸭", "清蒸鲈鱼",
        "葱爆羊肉", "辣子鸡", "酸辣土豆丝", "蒜蓉西兰花", "红烧排骨", "红烧猪蹄"
    ],
    "快餐": [
        "汉堡", "炸鸡", "披萨", "薯条", "热狗", "墨西哥卷饼", "寿司", "炒面", "盖浇饭",
        "麻辣烫", "煎饼果子", "肉夹馍", "米线", "串串香", "烤肉饭", "卤肉饭", "土豆饼",
        "鸡肉卷"
    ],
    "面食": [
        "重庆小面", "担担面", "阳春面", "牛肉面", "刀削面", "兰州拉面", "热干面", "炸酱面",
        "麻辣面", "海鲜面", "打卤面", "酸辣面", "葱油拌面", "鸡汤面", "肉丝面", "榨菜肉丝面"
    ],
    "甜点": [
        "冰淇淋", "蛋糕", "巧克力", "饼干", "奶茶", "果冻", "布丁", "芝士蛋糕", "蛋挞",
        "豆花", "豆腐脑", "凉粉", "杨枝甘露", "西米露", "绿豆沙", "红豆沙冰", "芒果捞"
    ]
}

async def generate_food(meal_type=None, weather=None, temperature=None, season=None, user_text=None, context=None):
    """
    动态生成食物推荐

    Args:
        meal_type: 餐点类型（早餐、中餐、晚餐等）
        weather: 天气情况
        temperature: 温度
        season: 季节
        user_text: 用户输入的文本
        context: 上下文对象，用于调用LLM

    Returns:
        str: 推荐的食物名称
    """
    # 检查是否可以使用LLM
    can_use_llm = context

    if not can_use_llm:
        # 如果无法使用LLM，使用备选方法
        logger.info(f"无法使用LLM，使用备选方法")
        if meal_type and meal_type in BACKUP_FOODS:
            return random.choice(BACKUP_FOODS[meal_type])
        else:
            # 从所有食物中随机选择
            all_foods = []
            for foods in BACKUP_FOODS.values():
                all_foods.extend(foods)
            return random.choice(all_foods)

    try:
        # 构建提示词
        prompt = "请推荐一道适合现在吃的美食，只返回美食名称，不要有任何其他文字。"

        # 添加餐点类型信息
        if meal_type:
            prompt += f"\n考虑这是{meal_type}时段。"

        # 添加天气信息
        if weather and temperature:
            prompt += f"\n当前天气：{weather}，温度：{temperature}°C。"

        # 添加季节信息
        if season:
            prompt += f"\n当前季节：{season}。"

        # 添加用户文本中可能包含的偏好
        if user_text:
            # 提取可能的食物偏好关键词
            preferences = []
            if "辣" in user_text:
                preferences.append("辣")
            if "甜" in user_text:
                preferences.append("甜")
            if "酸" in user_text:
                preferences.append("酸")
            if "咸" in user_text:
                preferences.append("咸")
            if "素" in user_text or "蔬菜" in user_text:
                preferences.append("素食")
            if "肉" in user_text:
                preferences.append("肉类")
            if "海鲜" in user_text or "鱼" in user_text:
                preferences.append("海鲜")

            if preferences:
                prompt += f"\n考虑以下偏好：{', '.join(preferences)}。"

        # 使用context调用LLM生成食物推荐
        food = ""

        # 尝试使用context.llm_recommend_food方法
        if hasattr(context, 'llm_recommend_food'):
            try:
                # 我们应该使用context.get_using_provider()来调用大模型
                # 而不是使用context.llm_recommend_food方法
                # 所以这里直接跳过，使用下面的get_using_provider方法
                raise Exception("跳过llm_recommend_food方法，使用get_using_provider方法")
            except Exception as e:
                logger.error(f"使用context.llm_recommend_food生成食物失败: {e}")

        # 如果使用context.llm_recommend_food失败，尝试使用context.get_using_provider()
        if not food and hasattr(context, 'get_using_provider') and callable(getattr(context, 'get_using_provider')):
            try:
                provider = context.get_using_provider()
                if provider:
                    session_id = f"food_recommendation_{random.randint(1000, 9999)}"
                    llm_response = await provider.text_chat(
                        prompt=prompt,
                        session_id=session_id
                    )
                    logger.info(f"成功使用context.get_using_provider()调用大模型")
                    food = llm_response.completion_text.strip() if hasattr(llm_response, 'completion_text') else llm_response.strip()
                else:
                    logger.warning(f"无法获取provider，跳过")
            except Exception as e:
                logger.error(f"使用context.get_using_provider()生成食物失败: {e}")

        # 如果两种方法都失败，使用备选方法
        if not food:
            logger.error(f"所有LLM方法都失败，使用备选方法")
            if meal_type and meal_type in BACKUP_FOODS:
                return random.choice(BACKUP_FOODS[meal_type])
            else:
                # 从所有食物中随机选择
                all_foods = []
                for foods in BACKUP_FOODS.values():
                    all_foods.extend(foods)
                return random.choice(all_foods)

        # 如果返回的内容太长，可能不是单纯的食物名称，进行处理
        if len(food) > 20:
            # 尝试提取第一个句子或短语
            sentences = food.split('。')[0].split('，')[0].split('、')[0]
            food = sentences.strip()

        logger.info(f"LLM生成的食物推荐: {food}")
        return food

    except Exception as e:
        logger.error(f"动态生成食物失败: {e}")
        # 出错时使用备选方法
        if meal_type and meal_type in BACKUP_FOODS:
            return random.choice(BACKUP_FOODS[meal_type])
        else:
            # 从所有食物中随机选择
            all_foods = []
            for foods in BACKUP_FOODS.values():
                all_foods.extend(foods)
            return random.choice(all_foods)
