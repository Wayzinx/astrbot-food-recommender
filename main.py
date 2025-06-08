import os
import asyncio
import datetime
import json

from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, Image
from astrbot.api import logger, llm_tool

# 导入拆分出去的模块
from .recommendation import generate_food_recommendation

# 获取当前文件的绝对路径
current_file_path = os.path.abspath(__file__)
# 获取当前文件所在目录的绝对路径
current_directory = os.path.dirname(current_file_path)
# 定义输出目录
OUTPUT_DIR = os.path.join(current_directory, "output")
# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

@register("food_recommender", "wayzinx", "美食推荐工具 - 根据时间、天气等因素随机推荐美食", "1.0.0")
class FoodRecommenderPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        # 创建输出目录
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        # 保存配置
        self.config = config or {}
        # 跟踪临时图片，以便能在使用后删除
        self.temp_images = set()
        # 记录上一次的推荐信息，用于"换一个"功能
        self.last_recommendations = {}
        # 添加OUTPUT_DIR到context，以便其他模块使用
        self.OUTPUT_DIR = OUTPUT_DIR

        # 初始化配置
        self._init_config()

        # 清理输出目录中的旧图片
        self._cleanup_old_images()

    def _init_config(self):
        """初始化配置"""
        logger.info("食物推荐插件初始化，配置检查中...")

        # 尝试从配置文件加载配置
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "config", "food_recommender_config.json")
            if os.path.exists(config_path):
                # 使用 utf-8-sig 编码来处理带有 BOM 的 UTF-8 文件
                with open(config_path, 'r', encoding='utf-8-sig') as f:
                    file_config = json.load(f)
                    if not hasattr(self, 'config') or not self.config:
                        self.config = {}
                    # 将文件配置合并到当前配置
                    for key, value in file_config.items():
                        self.config[key] = value
                    logger.info(f"从文件加载配置成功: {config_path}")
        except Exception as e:
            logger.error(f"从文件加载配置失败: {e}")

        # 设置默认值
        # 设置输出目录中保留的最大图片数量
        self.max_output_images = self.config.get("max_output_images", 1)  # 从配置中读取，默认为1

        # 设置火山引擎相关配置
        if "volcengine_model" not in self.config:
            self.config["volcengine_model"] = "high_aes_general_v21_L"

        if "schedule_conf" not in self.config:
            self.config["schedule_conf"] = "general_v20_9B_pe"

        if "region" not in self.config:
            self.config["region"] = "cn-north-1"

        if "service" not in self.config:
            self.config["service"] = "cv"

        # 检查API密钥
        if "volcengine_ak" not in self.config or not self.config["volcengine_ak"]:
            logger.warning("未配置火山引擎AccessKey，请在_conf_schema.json中添加volcengine_ak")
        else:
            logger.info("火山引擎AccessKey配置成功")

        if "volcengine_sk" not in self.config or not self.config["volcengine_sk"]:
            logger.warning("未配置火山引擎SecretKey，请在_conf_schema.json中添加volcengine_sk")
        else:
            logger.info("火山引擎SecretKey配置成功")

        # 从配置中读取关键词
        self.food_recommendation_keywords = self.config.get("food_recommendation_keywords", "吃什么,吃点什么,吃啥好,吃啥,今天吃啥,eat,food,早餐吃啥,早上吃啥,中餐吃啥,午餐吃啥,晚餐吃啥,晚上吃啥,甜点推荐,想吃甜的,饿了,好饿,肚子饿").split(",")
        self.meal_time_keywords = self.config.get("meal_time_keywords", "中午,午饭,晚上,晚饭,早上,早饭,早餐").split(",")
        self.change_recommendation_keywords = self.config.get("change_recommendation_keywords", "换一个,再来一个,不喜欢,其他推荐,换个推荐").split(",")
        self.food_image_keywords = self.config.get("food_image_keywords", "生成美食图,画美食").split(",")
        self.image_generation_keywords = self.config.get("image_generation_keywords", "生成图片,画图,文生图").split(",")

        logger.info(f"食物推荐插件配置初始化完成")

    async def initialize(self):
        """插件初始化，注册函数调用工具"""
        # 激活LLM工具
        self.context.activate_llm_tool("recommend_food")
        self.context.activate_llm_tool("food_command_handler")
        self.context.activate_llm_tool("generate_image")

    def _cleanup_old_images(self):
        """清理输出目录中的旧图片，只保留最新的几张"""
        try:
            # 获取输出目录中的所有图片文件
            image_files = []

            # 确保输出目录存在
            if not os.path.exists(OUTPUT_DIR):
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                logger.info(f"创建输出目录: {OUTPUT_DIR}")
                return  # 如果目录是新创建的，则没有图片需要清理

            # 获取所有图片文件
            for file in os.listdir(OUTPUT_DIR):
                file_path = os.path.join(OUTPUT_DIR, file)
                if os.path.isfile(file_path) and file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    # 获取文件的修改时间（比创建时间更可靠）
                    mod_time = os.path.getmtime(file_path)
                    image_files.append((file_path, mod_time))

            # 打印调试信息
            logger.info(f"发现 {len(image_files)} 张图片在输出目录中")

            # 按修改时间排序，最新的文件在前面
            image_files.sort(key=lambda x: x[1], reverse=True)

            # 如果图片数量超过最大限制，删除旧图片
            if len(image_files) > self.max_output_images:
                # 打印调试信息
                logger.info(f"图片数量 ({len(image_files)}) 超过最大限制 ({self.max_output_images})，开始清理...")

                # 保留最新的几张图片，删除其余的
                for file_path, _ in image_files[self.max_output_images:]:
                    try:
                        # 确保文件存在且不在使用中
                        if os.path.exists(file_path) and file_path not in self.temp_images:
                            os.remove(file_path)
                            logger.info(f"删除旧图片: {file_path}")
                        elif file_path in self.temp_images:
                            logger.info(f"跳过正在使用的图片: {file_path}")
                    except Exception as e:
                        logger.error(f"删除旧图片失败 {file_path}: {e}")

            # 再次获取当前图片数量
            current_images = [f for f in os.listdir(OUTPUT_DIR)
                             if os.path.isfile(os.path.join(OUTPUT_DIR, f)) and
                             f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]

            logger.info(f"输出目录清理完成，当前保留 {len(current_images)} 张图片")
        except Exception as e:
            logger.error(f"清理旧图片时出错: {e}")

    @llm_tool(name="recommend_food")
    async def recommend_food(self, event, meal_type: str = None, city: str = None):
        '''根据当前时间、天气等因素推荐美食

        Args:
            meal_type(string): 用餐类型，可选值：早餐、中餐、晚餐，不提供则根据当前时间推荐
            city(string): 城市名称，用于获取当地天气信息，可选参数
        '''
        # 发送等待消息
        yield event.chain_result([Plain(text=f"正在为你推荐{meal_type or '美食'}，请稍候...")])

        # 保存城市信息到context中，供generate_food_recommendation使用
        if city:
            self.user_specified_city = city

        # 生成推荐
        recommendation = await generate_food_recommendation(meal_type, self)

        # 记录本次推荐，用于"换一个"功能
        user_id = self._get_user_id(event)
        self.last_recommendations[user_id] = {
            'meal_type': meal_type,
            'food': recommendation['food'],
            'timestamp': datetime.datetime.now()
        }

        # 构建消息链
        message_chain = [
            Plain(text=f"我为你推荐：{recommendation['food']}\n\n"),
            Plain(text=f"{recommendation['reason']}\n\n"),
            Plain(text=f"{recommendation['description']}")
        ]

        # 如果有图片，添加图片
        if recommendation['image_path'] and os.path.exists(recommendation['image_path']):
            message_chain.append(Image(file=recommendation['image_path']))

            # 清理旧图片，只保留最新的几张
            self._cleanup_old_images()

            # 如果是临时图片，延迟删除
            if recommendation['image_path'] in self.temp_images:
                async def delayed_delete(path, delay=10):
                    await asyncio.sleep(delay)
                    try:
                        if os.path.exists(path):
                            os.unlink(path)
                            logger.info(f"已删除临时图片: {path}")
                            self.temp_images.discard(path)
                    except Exception as e:
                        logger.error(f"删除临时图片失败 {path}: {e}")

                asyncio.create_task(delayed_delete(recommendation['image_path']))

        # 返回推荐
        yield event.chain_result(message_chain)

    # 食物类型关键词映射
    MEAL_TYPE_KEYWORDS = {
        "早餐": ["早餐", "早上", "早饭"],
        "中餐": ["午餐", "中午", "午饭", "中饭", "中餐"],
        "晚餐": ["晚餐", "晚上", "晚饭"],
        "甜点": ["甜点", "甜食", "甜"],
        "面食": ["面", "面条", "挂面"],
        "快餐": ["快餐", "汉堡", "披萨"]
    }

    # 从文本中检测餐点类型
    def _detect_meal_type(self, text):
        """从文本中检测餐点类型"""
        for meal_type, keywords in self.MEAL_TYPE_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return meal_type
        return None

    # 判断是否是食物相关问题
    def _is_food_question(self, text):
        """判断是否是食物相关问题"""
        food_question_keywords = ["吃", "吃什么", "吃啥", "推荐"]
        return any(keyword in text for keyword in food_question_keywords)

    # 判断命令类型
    def _get_command_type(self, text):
        """判断命令类型"""
        # 检查是否是食物推荐命令
        for cmd in self.food_recommendation_keywords:
            if cmd in text:
                return "food_recommendation"

        # 检查是否是时间相关命令
        for cmd in self.meal_time_keywords:
            if cmd in text and self._is_food_question(text):
                return "food_recommendation"

        # 检查是否是换一个推荐命令
        for cmd in self.change_recommendation_keywords:
            if cmd in text:
                return "change_recommendation"

        # 检查是否是美食图片生成命令
        for cmd in self.food_image_keywords:
            if cmd in text:
                return "food_image"

        # 检查是否是通用图片生成命令
        for cmd in self.image_generation_keywords:
            if cmd in text:
                return "image_generation"

        return None

    # 统一的命令处理函数
    @llm_tool(name="food_command_handler")
    async def food_command_handler(self, event, text: str = None, command_type: str = None):
        '''食物推荐插件的统一命令处理函数

        处理各种食物相关的命令，包括食物推荐、换一个推荐、图片生成等。

        Args:
            text(string): 用户输入的文本，如果为None则使用事件中的消息
            command_type(string): 命令类型，如果为None则自动检测
        '''
        # 获取消息文本
        if text is None:
            # 尝试从事件中获取消息
            if hasattr(event, 'message_str') and event.message_str:
                text = event.message_str
            else:
                # 如果无法获取消息，返回错误提示
                yield event.chain_result([Plain(text="无法获取消息文本，请提供文本参数")])
                return

        # 转换为小写
        text = text.lower()

        # 如果没有指定命令类型，自动检测
        if command_type is None:
            command_type = self._get_command_type(text)

        # 定义chain_result方法
        event.chain_result = lambda components: components

        # 处理不同类型的命令
        if command_type == "food_recommendation":
            # 保存用户文本，供后续处理使用
            self.last_user_text = text

            # 使用辅助方法检测餐点类型
            meal_type = self._detect_meal_type(text)

            # 使用recommend_food方法生成推荐
            async for result in self.recommend_food(event, meal_type):
                yield result

        elif command_type == "change_recommendation":
            # 处理换一个推荐命令
            user_id = self._get_user_id(event)

            if user_id in self.last_recommendations:
                last_rec = self.last_recommendations[user_id]
                # 检查最后推荐是否在24小时内
                time_diff = datetime.datetime.now() - last_rec['timestamp']
                if time_diff.total_seconds() < 86400:  # 24小时 = 86400秒
                    # 获取上次推荐的餐点类型
                    meal_type = last_rec['meal_type']
                    last_food = last_rec['food']

                    # 生成新的推荐，避免与上次相同
                    from .recommendation import generate_food_recommendation
                    for _ in range(5):  # 尝试最多5次以获取不同的推荐
                        recommendation = await generate_food_recommendation(meal_type, self)
                        if recommendation['food'] != last_food:
                            break

                    # 更新最后推荐记录
                    self.last_recommendations[user_id] = {
                        'meal_type': meal_type,
                        'food': recommendation['food'],
                        'timestamp': datetime.datetime.now()
                    }

                    # 构建回复文本
                    response_text = f"\u6362\u4e00\u4e2a\u63a8\u8350\uff1a{recommendation['food']}\n\n{recommendation['reason']}\n\n{recommendation['description']}"

                    # 如果有图片，添加图片
                    if recommendation['image_path'] and os.path.exists(recommendation['image_path']):
                        # 清理旧图片，只保留最新的几张
                        self._cleanup_old_images()

                        # 构建消息链
                        message_chain = [
                            Plain(text=response_text)
                        ]

                        # 添加图片
                        message_chain.append(Image(file=recommendation['image_path']))

                        # 返回推荐
                        yield event.chain_result(message_chain)
                        return
                    else:
                        # 如果没有图片，只返回文本
                        yield event.chain_result([Plain(text=response_text)])
                        return

            # 如果没有之前的推荐记录或已过期，提示用户
            yield event.chain_result([Plain(text="抱歉，我不记得之前给你推荐了什么。请先告诉我你想吃什么类型的食物？")])
            return

        elif command_type == "food_image":
            # 处理美食图片生成命令
            # 提取食物名称
            food_name = self._extract_food_name(text)
            if not food_name:
                yield event.chain_result([Plain(text="请指定要生成图片的食物名称，例如：生成美食图 红烧肉")])
                return

            # 构建美食提示词
            prompt = f"高质量、写实风格的美食照片，特写镜头，\"{food_name}\"，美食摄影，精美摆盘，专业灯光，鲜艳色彩，美味可口的外观，食物特写"

            # 使用generate_image方法生成图片
            async for result in self.generate_image(event, prompt):
                yield result

        elif command_type == "image_generation":
            # 处理通用图片生成命令
            # 提取提示词
            prompt = self._extract_prompt(text)
            if not prompt:
                yield event.chain_result([Plain(text="请指定要生成图片的提示词，例如：生成图片 小猫在沙发上睡觉")])
                return

            # 使用generate_image方法生成图片
            async for result in self.generate_image(event, prompt):
                yield result

        else:
            # 如果无法识别命令类型，返回提示
            yield event.chain_result([Plain(text="抱歉，我无法理解您的命令。请尝试使用“吃什么”、“生成美食图”等命令。")])
            return

    # 已在food_command_handler中实现换一个推荐的功能，此方法不再使用

    @llm_tool(name="generate_image")
    async def generate_image(self, event, prompt: str, img_width: int = None, img_height: int = None):
        '''AI绘画，根据用户输入的提示词生成图片。

        Args:
            prompt(string): 图片生成提示词，可以是中文或英文。如果是中文，会自动处理。
            img_width(number): AI绘画生成的图片宽度。可选参数，默认为1024。
            img_height(number): AI绘画生成的图片高度。可选参数，默认为1024。
        '''
        # 设置默认尺寸
        width = img_width or 1024
        height = img_height or 1024

        # 从配置中获取API密钥
        access_key = self.config.get("volcengine_ak", "")
        secret_key = self.config.get("volcengine_sk", "")

        # 检查API密钥
        if not access_key or not secret_key:
            logger.warning("缺少API密钥配置，请在_conf_schema.json中添加volcengine_ak和volcengine_sk")
            yield event.chain_result([Plain(text=f"API密钥配置缺失，无法生成图片。")])
            return

        # 发送等待消息
        yield event.chain_result([Plain(text=f"正在生成图片，请稍候...")])

        # 使用image_generator模块生成图片
        from .image_generator import generate_food_image
        image_path = await generate_food_image(
            food_name=None,  # 不指定食物名称，使用通用提示词
            prompt=prompt,
            context=self,
            output_dir=self.OUTPUT_DIR,
            width=width,
            height=height
        )

        if image_path:
            yield event.chain_result([
                Plain(text=f"已生成图片：\n"),
                Image(file=image_path)
            ])
        else:
            yield event.chain_result([Plain(text=f"AI生成图片失败，请稍后再试。")])

    # 消息处理器不再需要，因为我们使用LLM工具来处理命令

    async def terminate(self):
        # 退出时清理临时文件
        try:
            # 清理所有记录的临时图片
            for img_path in self.temp_images:
                try:
                    if os.path.isfile(img_path) and os.path.exists(img_path):
                        os.unlink(img_path)
                        logger.info(f"已删除临时图片: {img_path}")
                except Exception as e:
                    logger.error(f"清理临时图片失败 {img_path}: {e}")

            # 清理输出目录中的文件，只保留最新的几张
            self._cleanup_old_images()
        except Exception as e:
            logger.error(f"清理过程出错: {e}")

    def _get_user_id(self, event):
        """从事件中获取用户ID"""
        try:
            # 尝试从不同类型的事件中获取用户ID
            if hasattr(event, 'user_id'):
                return event.user_id
            elif hasattr(event, 'sender') and hasattr(event.sender, 'user_id'):
                return event.sender.user_id
            elif hasattr(event, 'sender_id'):
                return event.sender_id
            else:
                # 如果无法获取用户ID，使用一个默认值
                return "default_user"
        except:
            return "default_user"

    def _extract_food_name(self, text):
        """从文本中提取食物名称"""
        # 先检查是否包含美食图片生成关键词
        for keyword in self.food_image_keywords:
            if keyword in text:
                # 如果包含关键词，提取关键词后面的内容作为食物名称
                parts = text.split(keyword, 1)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
        return None

    def _extract_prompt(self, text):
        """从文本中提取图片生成提示词"""
        # 先检查是否包含图片生成关键词
        for keyword in self.image_generation_keywords:
            if keyword in text:
                # 如果包含关键词，提取关键词后面的内容作为提示词
                parts = text.split(keyword, 1)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
        return None
