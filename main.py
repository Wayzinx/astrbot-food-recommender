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

@register("food_recommender", "wayzinx", "美食推荐工具 - 根据时间、天气等因素随机推荐美食", "1.0.1")
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
        # 记录最近的推荐历史，用于去重
        self.recent_foods = {}
        # 待显示的图片信息
        self.pending_images = {}
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
            'timestamp': datetime.datetime.now(),
            'city': city  # 记录城市信息
        }

        # 初始化并更新历史推荐列表
        if user_id not in self.recent_foods:
            self.recent_foods[user_id] = []
        self.recent_foods[user_id].append(recommendation['food'])
        if len(self.recent_foods[user_id]) > 5:
            self.recent_foods[user_id] = self.recent_foods[user_id][-5:]

        # 准备图片信息（如果有的话）
        if recommendation['image_path'] and os.path.exists(recommendation['image_path']):
            # 将图片信息存储到待显示列表中
            result_text = f"我为你推荐：{recommendation['food']}\n\n{recommendation['reason']}\n\n{recommendation['description']}"
            self.pending_images[user_id] = {
                'text': result_text,
                'image_path': recommendation['image_path']
            }
            # 返回带图片提示的文本
            return f"{result_text}\n\n[图片已生成，正在显示...]"
        else:
            # 没有图片，直接返回文本
            result_text = f"我为你推荐：{recommendation['food']}\n\n{recommendation['reason']}\n\n{recommendation['description']}"
            return result_text

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
    async def food_command_handler(self, event, text: str = None, command_type: str = None, city: str = None):
        '''食物推荐插件的统一命令处理函数

        处理各种食物相关的命令，包括食物推荐、换一个推荐、图片生成等。

        Args:
            text(string): 用户输入的文本，如果为None则使用事件中的消息
            command_type(string): 命令类型，如果为None则自动检测
            city(string): 城市名称，用于获取当地天气信息，可选参数
        '''
        # 导入必要的模块
        from .recommendation import generate_food_recommendation
        # 添加调试日志
        logger.info(f"food_command_handler 被调用，参数: text={text}, command_type={command_type}, city={city}")

        # 获取消息文本
        if text is None:
            # 尝试从事件中获取消息
            if hasattr(event, 'message_str') and event.message_str:
                text = event.message_str
            else:
                # 如果无法获取消息，返回错误提示
                logger.warning("无法获取消息文本")
                return "无法获取消息文本，请提供文本参数"

        # 转换为小写
        text = text.lower()
        logger.info(f"处理的文本: {text}")

        # 如果没有指定命令类型，自动检测
        if command_type is None:
            command_type = self._get_command_type(text)
            logger.info(f"自动检测的命令类型: {command_type}")
        else:
            logger.info(f"指定的命令类型: {command_type}")

        # 标准化命令类型
        if command_type in ["推荐", "recommend"]:
            command_type = "food_recommendation"
        elif command_type in ["换一个推荐", "change_recommendation"]:
            command_type = "change_recommendation"

        logger.info(f"最终使用的命令类型: {command_type}")

        # 处理不同类型的命令
        if command_type == "food_recommendation":
            # 保存用户文本，供后续处理使用
            self.last_user_text = text

            # 保存城市信息到context中，供generate_food_recommendation使用
            if city:
                self.user_specified_city = city

            # 使用辅助方法检测餐点类型
            meal_type = self._detect_meal_type(text)

            # 生成推荐
            recommendation = await generate_food_recommendation(meal_type, self)
            logger.info(f"生成推荐成功: {recommendation['food']}")

            # 记录本次推荐，用于"换一个"功能
            user_id = self._get_user_id(event)
            self.last_recommendations[user_id] = {
                'meal_type': meal_type,
                'food': recommendation['food'],
                'timestamp': datetime.datetime.now(),
                'city': city  # 记录城市信息
            }

            # 返回文本结果
            result_text = f"我为你推荐：{recommendation['food']}\n\n{recommendation['reason']}\n\n{recommendation['description']}"
            return result_text

        elif command_type == "change_recommendation":
            # 处理换一个推荐命令
            logger.info("处理换一个推荐命令")
            user_id = self._get_user_id(event)
            logger.info(f"用户ID: {user_id}")

            if user_id in self.last_recommendations:
                last_rec = self.last_recommendations[user_id]
                logger.info(f"找到上次推荐记录: {last_rec}")

                # 检查最后推荐是否在24小时内
                time_diff = datetime.datetime.now() - last_rec['timestamp']
                if time_diff.total_seconds() < 86400:  # 24小时 = 86400秒
                    # 获取上次推荐的餐点类型
                    meal_type = last_rec['meal_type']
                    last_food = last_rec['food']
                    logger.info(f"上次推荐: {last_food}, 餐点类型: {meal_type}")

                    # 如果指定了新城市，使用新城市；否则使用上次的城市
                    if city:
                        self.user_specified_city = city
                        current_city = city
                        logger.info(f"使用新指定的城市: {city}")
                    else:
                        current_city = last_rec.get('city', None)
                        if current_city:
                            self.user_specified_city = current_city
                            logger.info(f"使用上次的城市: {current_city}")

                    # 初始化历史推荐列表（用于更好的去重）
                    if user_id not in self.recent_foods:
                        self.recent_foods[user_id] = []

                    # 添加当前食物到历史列表
                    if last_food not in self.recent_foods[user_id]:
                        self.recent_foods[user_id].append(last_food)

                    # 只保留最近5个推荐用于去重
                    if len(self.recent_foods[user_id]) > 5:
                        self.recent_foods[user_id] = self.recent_foods[user_id][-5:]

                    logger.info(f"当前历史推荐列表: {self.recent_foods[user_id]}")

                    # 生成新的推荐，避免与最近推荐的相同
                    for attempt in range(10):  # 尝试最多10次以获取不同的推荐
                        recommendation = await generate_food_recommendation(meal_type, self)
                        if recommendation['food'] not in self.recent_foods[user_id]:
                            logger.info(f"第{attempt+1}次尝试成功，推荐: {recommendation['food']}")
                            break
                        logger.info(f"第{attempt+1}次尝试，推荐的{recommendation['food']}与历史重复，重新生成")

                    # 更新最后推荐记录
                    self.last_recommendations[user_id] = {
                        'meal_type': meal_type,
                        'food': recommendation['food'],
                        'timestamp': datetime.datetime.now(),
                        'city': current_city
                    }

                    # 添加新推荐到历史列表
                    self.recent_foods[user_id].append(recommendation['food'])
                    if len(self.recent_foods[user_id]) > 5:
                        self.recent_foods[user_id] = self.recent_foods[user_id][-5:]

                    # 构建回复文本
                    city_text = f"（{current_city}）" if current_city else ""
                    response_text = f"换一个推荐{city_text}：{recommendation['food']}\n\n{recommendation['reason']}\n\n{recommendation['description']}"

                    # 准备图片信息（如果有的话）
                    if recommendation['image_path'] and os.path.exists(recommendation['image_path']):
                        # 将图片信息存储到待显示列表中
                        self.pending_images[user_id] = {
                            'text': response_text,
                            'image_path': recommendation['image_path']
                        }
                        # 返回带图片提示的文本
                        logger.info(f"换一个推荐成功（含图片）: {response_text[:50]}...")
                        return f"{response_text}\n\n[图片已生成，正在显示...]"
                    else:
                        logger.info(f"换一个推荐成功: {response_text[:50]}...")
                        return response_text
                else:
                    logger.info("上次推荐已过期（超过24小时）")
            else:
                logger.info("没有找到上次推荐记录")

            # 如果没有之前的推荐记录或已过期，提示用户
            return "抱歉，我不记得之前给你推荐了什么。请先告诉我你想吃什么类型的食物？"

        elif command_type == "food_image":
            # 处理美食图片生成命令
            # 提取食物名称
            food_name = self._extract_food_name(text)
            if not food_name:
                return "请指定要生成图片的食物名称，例如：生成美食图 红烧肉"

            # 构建美食提示词
            prompt = f"高质量、写实风格的美食照片，特写镜头，\"{food_name}\"，美食摄影，精美摆盘，专业灯光，鲜艳色彩，美味可口的外观，食物特写"

            # 生成图片
            from .image_generator import generate_food_image
            image_path = await generate_food_image(
                food_name=None,
                prompt=prompt,
                context=self,
                output_dir=self.OUTPUT_DIR,
                width=1024,
                height=1024
            )

            if image_path:
                # 将图片信息存储到待显示列表中
                user_id = self._get_user_id(event)
                result_text = f"已为您生成{food_name}的美食图片"
                self.pending_images[user_id] = {
                    'text': result_text,
                    'image_path': image_path
                }
                return f"{result_text}\n\n[图片已生成，正在显示...]"
            else:
                return "AI生成图片失败，请稍后再试。"

        elif command_type == "image_generation":
            # 处理通用图片生成命令
            # 提取提示词
            prompt = self._extract_prompt(text)
            if not prompt:
                return "请指定要生成图片的提示词，例如：生成图片 小猫在沙发上睡觉"

            # 生成图片
            from .image_generator import generate_food_image
            image_path = await generate_food_image(
                food_name=None,
                prompt=prompt,
                context=self,
                output_dir=self.OUTPUT_DIR,
                width=1024,
                height=1024
            )

            if image_path:
                # 将图片信息存储到待显示列表中
                user_id = self._get_user_id(event)
                result_text = f"已根据您的提示词生成图片"
                self.pending_images[user_id] = {
                    'text': result_text,
                    'image_path': image_path
                }
                return f"{result_text}\n\n[图片已生成，正在显示...]"
            else:
                return "AI生成图片失败，请稍后再试。"

        else:
            # 如果无法识别命令类型，返回提示
            logger.warning(f"无法识别的命令类型: {command_type}, 原始文本: {text}")
            return "抱歉，我无法理解您的命令。请尝试使用“吃什么”、“生成美食图”等命令。"

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
            return "API密钥配置缺失，无法生成图片。"

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
            # 将图片信息存储到待显示列表中
            user_id = self._get_user_id(event)
            result_text = f"已生成图片：{prompt}"
            self.pending_images[user_id] = {
                'text': result_text,
                'image_path': image_path
            }
            return f"{result_text}\n\n[图片已生成，正在显示...]"
        else:
            return "AI生成图片失败，请稍后再试。"

    # 添加消息处理器来处理图片显示
    async def handle(self, event):
        """处理消息事件，主要用于显示图片"""
        # 检查是否有待显示的图片
        user_id = self._get_user_id(event)
        if hasattr(self, 'pending_images') and user_id in self.pending_images:
            image_info = self.pending_images[user_id]

            # 构建包含图片的消息链
            message_chain = [
                Plain(text=image_info['text'])
            ]

            if image_info['image_path'] and os.path.exists(image_info['image_path']):
                message_chain.append(Image(file=image_info['image_path']))

                # 清理旧图片
                self._cleanup_old_images()

                # 如果是临时图片，延迟删除
                if image_info['image_path'] in self.temp_images:
                    async def delayed_delete(path, delay=10):
                        await asyncio.sleep(delay)
                        try:
                            if os.path.exists(path):
                                os.unlink(path)
                                logger.info(f"已删除临时图片: {path}")
                                self.temp_images.discard(path)
                        except Exception as e:
                            logger.error(f"删除临时图片失败 {path}: {e}")

                    asyncio.create_task(delayed_delete(image_info['image_path']))

            # 清除待显示的图片信息
            del self.pending_images[user_id]

            # 发送消息
            return message_chain

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
