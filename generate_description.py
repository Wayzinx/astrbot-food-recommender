import logging
from astrbot.api import logger

# 使用大模型生成食物描述和推荐理由

# 动态生成食物描述的函数
async def generate_food_description(food_name, context=None):
    """使用大模型生成食物描述"""
    # 如果没有context或无法使用大模型，使用预定义的描述模板
    if not context:
        # 使用预定义的描述模板作为备选
        descriptions = [
            f"{food_name}是一道深受大众喜爱的美食，口感独特，风味绝佳。",
            f"{food_name}以其独特的口感和丰富的风味而闻名，是一道不可错过的美食。",
            f"{food_name}的口感鲜嫩可口，风味独特，是一道深受喜爱的美食。",
            f"{food_name}的香气四溢，口感丰富，是一道让人回味无穷的美食。",
            f"{food_name}的风味独特，营养丰富，是一道满足味觉和营养需求的美食。"
        ]

        # 根据食物名称选择一个描述
        import hashlib
        hash_value = int(hashlib.md5(food_name.encode()).hexdigest(), 16)
        description = descriptions[hash_value % len(descriptions)]

        logger.info(f"使用模板为\"{food_name}\"生成描述: {description}")
        return description

    try:
        # 构建提示词
        prompt = f"""请为食物"{food_name}"生成一段简短的描述，包含其特点、口感和鲜明特点。不超过50个字。
只返回描述文本，不要包含其他内容。"""

        # 使用context调用大模型
        try:
            # 尝试使用context.llm_recommend_food方法
            if hasattr(context, 'llm_recommend_food'):
                try:
                    # 我们应该使用context.get_using_provider()来调用大模型
                    # 而不是使用context.llm_recommend_food方法
                    # 所以这里直接跳过，使用下面的get_using_provider方法
                    raise Exception("跳过llm_recommend_food方法，使用get_using_provider方法")
                except Exception as e:
                    logger.error(f"使用context.llm_recommend_food生成食物描述失败: {e}")

            # 如果无法使用context.llm_recommend_food，尝试使用context.get_using_provider()方法
            if hasattr(context, 'get_using_provider') and callable(getattr(context, 'get_using_provider')):
                try:
                    provider = context.get_using_provider()
                    if provider:
                        import random
                        session_id = f"food_description_{random.randint(1000, 9999)}"
                        llm_response = await provider.text_chat(
                            prompt=prompt,
                            session_id=session_id
                        )
                        logger.info(f"成功使用context.get_using_provider()调用大模型")
                        # 提取响应文本
                        description = llm_response.completion_text.strip() if hasattr(llm_response, 'completion_text') else llm_response.strip()
                        return description
                    else:
                        # 如果无法获取provider，使用预定义的模板
                        logger.info(f"无法获取provider，使用预定义的模板")
                except Exception as e:
                    logger.error(f"使用context.get_using_provider()生成食物描述失败: {e}")
            else:
                # 如果无法使用context.get_using_provider()，使用预定义的模板
                logger.info(f"无法使用context.get_using_provider()，使用预定义的模板")
                # 使用预定义的描述模板
                descriptions = [
                    f"{food_name}是一道深受大众喜爱的美食，口感独特，风味绝佳。",
                    f"{food_name}以其独特的口感和丰富的风味而闻名，是一道不可错过的美食。",
                    f"{food_name}的口感鲜嫩可口，风味独特，是一道深受喜爱的美食。",
                    f"{food_name}的香气四溢，口感丰富，是一道让人回味无穷的美食。",
                    f"{food_name}的风味独特，营养丰富，是一道满足味觉和营养需求的美食。"
                ]
                import hashlib
                hash_value = int(hashlib.md5(food_name.encode()).hexdigest(), 16)
                description = descriptions[hash_value % len(descriptions)]
                return description
        except Exception as e:
            logger.error(f"调用大模型失败: {e}")
            # 如果上述方法都失败，返回默认描述
            return f"{food_name}是一道深受大众喜爱的美食，口感独特，风味绝佳。"

        # 如果代码执行到这里，说明上面的所有方法都失败了
        # 使用预定义的描述模板
        descriptions = [
            f"{food_name}是一道深受大众喜爱的美食，口感独特，风味绝佳。",
            f"{food_name}以其独特的口感和丰富的风味而闻名，是一道不可错过的美食。",
            f"{food_name}的口感鲜嫩可口，风味独特，是一道深受喜爱的美食。",
            f"{food_name}的香气四溢，口感丰富，是一道让人回味无穷的美食。",
            f"{food_name}的风味独特，营养丰富，是一道满足味觉和营养需求的美食。"
        ]
        import hashlib
        hash_value = int(hashlib.md5(food_name.encode()).hexdigest(), 16)
        description = descriptions[hash_value % len(descriptions)]
        logger.info(f"所有方法都失败，使用模板为\"{food_name}\"生成描述: {description}")
        return description
    except Exception as e:
        logger.error(f"生成食物描述失败: {e}")
        # 如果生成失败，返回一个通用描述
        return f"{food_name}是一道深受大众喜爱的美食，口感独特，风味绝佳。"

# 生成推荐理由的函数
async def generate_recommendation_reason(food_name, weather, temperature, date, time_of_day, season, city=None, context=None):
    """使用大模型生成推荐理由"""
    # 如果没有context或无法使用大模型，使用预定义的理由模板
    if not context:
        # 基本模板
        city_text = f"在{city}" if city else ""
        basic_reason = f"今天{date}，{city_text}{temperature}°C的{weather}天气下，来一份{food_name}绝对是明智之选！"

        # 根据天气和季节生成不同的推荐理由
        reasons = [
            basic_reason,
            f"{date}的{city_text}{weather}天气，{temperature}°C的温度非常适合品尝{food_name}，给你的味蕾带来惊喜！",
            f"{season}季节{city_text}{temperature}°C的{weather}天气，正是品尝{food_name}的最佳时机，不要错过！",
            f"{city_text}{date}的{weather}天气，{temperature}°C的温度下，{food_name}的美味会加倍提升！",
            f"{time_of_day}时分的{city_text}{weather}天气，配上一份美味的{food_name}，完美的享受！"
        ]

        # 根据食物名称、天气和日期选择一个推荐理由
        import hashlib
        hash_input = f"{food_name}{weather}{date}".encode()
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
        reason = reasons[hash_value % len(reasons)]

        logger.info(f"使用模板为\"{food_name}\"生成推荐理由: {reason}")
        return reason

    try:
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

        # 使用context调用大模型
        try:
            # 尝试使用context.llm_recommend_food方法
            if hasattr(context, 'llm_recommend_food'):
                try:
                    # 我们应该使用context.get_using_provider()来调用大模型
                    # 而不是使用context.llm_recommend_food方法
                    # 所以这里直接跳过，使用下面的get_using_provider方法
                    raise Exception("跳过llm_recommend_food方法，使用get_using_provider方法")
                except Exception as e:
                    logger.error(f"使用context.llm_recommend_food生成推荐理由失败: {e}")

            # 如果无法使用context.llm_recommend_food，尝试使用context.get_using_provider()方法
            if hasattr(context, 'get_using_provider') and callable(getattr(context, 'get_using_provider')):
                try:
                    provider = context.get_using_provider()
                    if provider:
                        import random
                        session_id = f"food_reason_{random.randint(1000, 9999)}"
                        llm_response = await provider.text_chat(
                            prompt=prompt,
                            session_id=session_id
                        )
                        logger.info(f"成功使用context.get_using_provider()调用大模型")
                        # 提取响应文本
                        reason = llm_response.completion_text.strip() if hasattr(llm_response, 'completion_text') else llm_response.strip()
                        return reason
                    else:
                        # 如果无法获取provider，使用预定义的模板
                        logger.info(f"无法获取provider，使用预定义的模板")
                except Exception as e:
                    logger.error(f"使用context.get_using_provider()生成推荐理由失败: {e}")
            else:
                # 如果无法使用context.get_using_provider()，使用预定义的模板
                logger.info(f"无法使用context.get_using_provider()，使用预定义的模板")
                # 使用预定义的理由模板
                # 基本模板
                city_text = f"在{city}" if city else ""
                basic_reason = f"今天{date}，{city_text}{temperature}°C的{weather}天气下，来一份{food_name}绝对是明智之选！"

                # 根据天气和季节生成不同的推荐理由
                reasons = [
                    basic_reason,
                    f"{date}的{city_text}{weather}天气，{temperature}°C的温度非常适合品尝{food_name}，给你的味蕾带来惊喜！",
                    f"{season}季节{city_text}{temperature}°C的{weather}天气，正是品尝{food_name}的最佳时机，不要错过！",
                    f"{city_text}{date}的{weather}天气，{temperature}°C的温度下，{food_name}的美味会加倍提升！",
                    f"{time_of_day}时分的{city_text}{weather}天气，配上一份美味的{food_name}，完美的享受！"
                ]

                import hashlib
                hash_input = f"{food_name}{weather}{date}".encode()
                hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
                reason = reasons[hash_value % len(reasons)]
                return reason
        except Exception as e:
            logger.error(f"调用大模型失败: {e}")
            # 如果上述方法都失败，返回默认理由
            city_text = f"在{city}" if city else ""
            return f"今天{date}，{city_text}{temperature}°C的{weather}天气下，来一份{food_name}绝对是明智之选！"

        # 如果代码执行到这里，说明上面的所有方法都失败了
        # 使用预定义的理由模板
        # 基本模板
        city_text = f"在{city}" if city else ""
        basic_reason = f"今天{date}，{city_text}{temperature}°C的{weather}天气下，来一份{food_name}绝对是明智之选！"

        # 根据天气和季节生成不同的推荐理由
        reasons = [
            basic_reason,
            f"{date}的{city_text}{weather}天气，{temperature}°C的温度非常适合品尝{food_name}，给你的味蕾带来惊喜！",
            f"{season}季节{city_text}{temperature}°C的{weather}天气，正是品尝{food_name}的最佳时机，不要错过！",
            f"{city_text}{date}的{weather}天气，{temperature}°C的温度下，{food_name}的美味会加倍提升！",
            f"{time_of_day}时分的{city_text}{weather}天气，配上一份美味的{food_name}，完美的享受！"
        ]

        import hashlib
        hash_input = f"{food_name}{weather}{date}".encode()
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
        reason = reasons[hash_value % len(reasons)]
        logger.info(f"所有方法都失败，使用模板为\"{food_name}\"生成推荐理由: {reason}")
        return reason
    except Exception as e:
        logger.error(f"生成推荐理由失败: {e}")
        # 如果生成失败，返回一个通用理由
        city_text = f"在{city}" if city else ""
        return f"今天{date}，{city_text}{temperature}°C的{weather}天气下，来一份{food_name}绝对是明智之选！"
