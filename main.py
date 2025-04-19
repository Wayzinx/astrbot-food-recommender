import os
import sys
import asyncio
import datetime
import uuid
import importlib
import subprocess
import aiohttp
from io import BytesIO
from PIL import Image as PILImage, ImageDraw, ImageFont

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, Image
from astrbot.api import logger

# 导入拆分出去的模块
from .food_utils import get_season, get_weather
from .image_generator import get_food_image
from .recommendation import generate_food_recommendation

# 配置常量
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PLUGIN_DIR, "output")
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
        # 设置输出目录中保留的最大图片数量
        self.max_output_images = self.config.get("max_output_images", 1)  # 从配置中读取，默认为1
        # 清理输出目录中的旧图片
        self._cleanup_old_images()
        # 日志输出配置信息
        logger.info(f"食物推荐插件初始化，配置检查中...")

        # 检查本地doubao_image模块
        try:
            # 使用本地doubao_image模块
            from .doubao_image import generate_image
            logger.info("成功导入本地doubao_image模块，将启用AI图像生成功能")
        except ImportError:
            logger.warning("未找到本地doubao_image模块，将使用备选方法获取图片")
        except Exception as e:
            logger.error(f"检查本地doubao_image模块时出错: {e}")

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

    # 添加智能食物推荐命令处理
    @filter.command("吃什么")
    @filter.command("吃点什么")
    @filter.command("吃啥好")
    @filter.command("吃啥")
    @filter.command("今天吃啥")
    @filter.command("eat")
    @filter.command("food")
    @filter.command("早餐吃啥")
    @filter.command("早上吃啥")
    @filter.command("中餐吃啥")
    @filter.command("午餐吃啥")
    @filter.command("晚餐吃啥")
    @filter.command("晚上吃啥")
    @filter.command("甜点推荐")
    @filter.command("想吃甜的")
    @filter.command("饿了")
    @filter.command("好饿")
    @filter.command("肚子饿")
    async def smart_food_recommendation(self, event: AstrMessageEvent, *args):
        """智能食物推荐处理函数，根据用户输入自动判断餐点类型和回复风格"""
        text = event.message_str.lower()
        # 保存用户文本，供后续处理使用
        self.last_user_text = text
        meal_type = None
        loading_message = None
        response_prefix = "我为你推荐："

        # 判断餐点类型
        if any(keyword in text for keyword in ["早餐", "早上", "早饭"]):
            meal_type = "早餐"
            loading_message = "正在为你推荐早餐..."
            response_prefix = "早餐可以吃："
        elif any(keyword in text for keyword in ["午餐", "中午", "午饭", "中饭", "中餐"]):
            meal_type = "中餐"
            loading_message = "正在为你推荐午餐..."
            response_prefix = "中午可以吃："
        elif any(keyword in text for keyword in ["晚餐", "晚上", "晚饭"]):
            meal_type = "晚餐"
            loading_message = "正在为你推荐晚餐..."
            response_prefix = "晚餐可以尝试："
        elif any(keyword in text for keyword in ["甜点", "甜食", "甜"]):
            meal_type = "甜点"
            loading_message = "正在为你推荐甜点..."
            response_prefix = "推荐这样的甜点："
        elif any(keyword in text for keyword in ["面", "面条", "挂面"]):
            meal_type = "面食"
            loading_message = "正在为你推荐面食..."
            response_prefix = "推荐这样的面食："
        elif any(keyword in text for keyword in ["快餐", "汉堡", "披萨"]):
            meal_type = "快餐"
            loading_message = "正在为你推荐快餐..."
            response_prefix = "推荐这样的快餐："
        elif "饿" in text:
            loading_message = "正在为你推荐美食..."
            response_prefix = "你饿了啊？我推荐你吃："

        # 发送加载消息（如果有）
        if loading_message:
            yield event.chain_result([Plain(text=loading_message)])

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
            Plain(text=f"{response_prefix}{recommendation['food']}\n\n"),
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

    # 处理时间相关的食物询问
    @filter.command("中午", "午饭")
    async def lunch_question(self, event: AstrMessageEvent, *args):
        """处理午餐相关问题"""
        text = event.message_str
        if any(q in text for q in ["吃", "吃什么", "吃啥", "推荐"]):
            await self.smart_food_recommendation(event, *args)

    @filter.command("晚上", "晚饭")
    async def dinner_question(self, event: AstrMessageEvent, *args):
        """处理晚餐相关问题"""
        text = event.message_str
        if any(q in text for q in ["吃", "吃什么", "吃啥", "推荐"]):
            await self.smart_food_recommendation(event, *args)

    @filter.command("早上", "早饭", "早餐")
    async def breakfast_question(self, event: AstrMessageEvent, *args):
        """处理早餐相关问题"""
        text = event.message_str
        if any(q in text for q in ["吃", "吃什么", "吃啥", "推荐"]):
            await self.smart_food_recommendation(event, *args)

    @filter.command("换一个")
    @filter.command("再来一个")
    @filter.command("不喜欢")
    @filter.command("其他推荐")
    @filter.command("换个推荐")
    async def change_recommendation(self, event: AstrMessageEvent, *args):
        """换一个推荐"""
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

                # 构建回复
                message_chain = [
                    Plain(text=f"换一个推荐：{recommendation['food']}\n\n"),
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

                # 返回新推荐
                yield event.chain_result(message_chain)
                return

        # 如果没有之前的推荐记录或已过期，提示用户
        yield event.plain_result("抱歉，我不记得之前给你推荐了什么。请先告诉我你想吃什么类型的食物？")

    @filter.llm_tool(name="recommend_food")
    async def llm_recommend_food(self, event, meal_type: str = None):
        '''根据当前时间、天气等因素推荐美食

        Args:
            meal_type(string): 用餐类型，可选值：早餐、中餐、晚餐，不提供则根据当前时间推荐
        '''
        # 生成推荐
        recommendation = await generate_food_recommendation(meal_type, self)

        # 记录本次推荐，用于"换一个"功能
        user_id = self._get_user_id(event) if hasattr(self, '_get_user_id') else "llm_user"
        self.last_recommendations[user_id] = {
            'meal_type': meal_type,
            'food': recommendation['food'],
            'timestamp': datetime.datetime.now()
        }

        # 构建返回消息
        if hasattr(event, 'chain_result'):
            # 如果是消息事件，返回消息链
            message_chain = [
                Plain(text=f"我为你推荐：{recommendation['food']}\n\n"),
                Plain(text=f"{recommendation['reason']}\n\n"),
                Plain(text=f"{recommendation['description']}")
            ]

            # 如果有图片，添加图片
            if recommendation['image_path'] and os.path.exists(recommendation['image_path']):
                message_chain.append(Image(file=recommendation['image_path']))

            return event.chain_result(message_chain)
        else:
            # 如果是其他类型，返回纯文本
            result = f"我为你推荐：{recommendation['food']}\n\n"
            result += f"{recommendation['reason']}\n\n"
            result += f"{recommendation['description']}\n\n"
            result += "（图片不可在文本模式中显示）"
            return result

    # 通用文生图功能
    @filter.command("生成图片", "画图", "文生图")
    async def generate_image_command(self, event: AstrMessageEvent, prompt: str):
        """通用文生图功能，可生成任何类型的图片"""
        # 使用@doubao_test模块生成图片
        yield event.chain_result([Plain(text=f"正在使用AI生成图片，请稍候...")])

        # 从配置中获取API密钥
        access_key = self.config.get("doubao_access_key", "")
        secret_key = self.config.get("doubao_secret_key", "")

        # 记录日志
        if "doubao_access_key" not in self.config or "doubao_secret_key" not in self.config:
            logger.info("使用默认API密钥生成图片")

        # 生成图片
        image_path = await self._generate_image_with_doubao(prompt, access_key, secret_key)

        if image_path:
            yield event.chain_result([
                Plain(text=f"已生成图片：\n"),
                Image(file=image_path)
            ])
        else:
            yield event.chain_result([Plain(text=f"AI生成图片失败，请稍后再试。")])

    # 美食图片生成功能（兼容旧命令）
    @filter.command("生成美食图", "画美食")
    async def generate_food_image(self, event: AstrMessageEvent, food_name: str):
        """生成美食图片（兼容旧命令）"""
        # 构建美食提示词
        prompt = f"高质量、写实风格的美食照片，特写镜头，\"{food_name}\"，美食摄影，精美摆盘，专业灯光，鲜艳色彩，美味可口的外观，食物特写"

        # 使用通用文生图功能
        yield event.chain_result([Plain(text=f"正在使用AI生成\"{food_name}\"的美食图片，请稍候...")])

        # 从配置中获取API密钥
        access_key = self.config.get("doubao_access_key", "")
        secret_key = self.config.get("doubao_secret_key", "")

        # 记录日志
        if "doubao_access_key" not in self.config or "doubao_secret_key" not in self.config:
            logger.info("使用默认API密钥生成图片")

        # 生成图片
        image_path = await self._generate_image_with_doubao(prompt, access_key, secret_key)

        if image_path:
            yield event.chain_result([
                Plain(text=f"已生成\"{food_name}\"的美食图片：\n"),
                Image(file=image_path)
            ])
        else:
            yield event.chain_result([Plain(text=f"AI生成\"{food_name}\"的图片失败，请稍后再试。")])

    # 内部方法，使用本地doubao_image模块生成图片
    async def _generate_image_with_doubao(self, prompt, access_key, secret_key):
        """使用本地doubao_image模块生成图片

        Args:
            prompt: 提示词
            access_key: API访问密钥
            secret_key: API密钥

        Returns:
            str: 生成的图片路径，如果失败则返回None
        """
        # 检查API密钥
        if not access_key or not secret_key:
            logger.warning("缺少API密钥，无法生成图片")
            return None

        try:
            # 使用本地doubao_image模块
            from .doubao_image import generate_image

            # 输出调试信息
            logger.info(f"开始生成图片，提示词: {prompt[:30]}...")
            logger.info(f"API密钥长度: {len(access_key)}, {len(secret_key)}")

            # 生成图片
            result = generate_image(access_key, secret_key, prompt)

            # 检查结果
            if result.get("code") == 10000:
                # 成功生成图片
                image_url = result["data"]["image_urls"][0]
                logger.info(f"成功生成图片，获取URL: {image_url[:30]}...")

                # 下载图片
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url) as response:
                            if response.status == 200:
                                img_data = await response.read()
                                # 使用UUID生成唯一文件名
                                local_path = os.path.join(OUTPUT_DIR, f"image_{uuid.uuid4().hex[:8]}.jpg")
                                with open(local_path, "wb") as f:
                                    f.write(img_data)
                                # 记录临时图片
                                self.temp_images.add(local_path)
                                # 清理旧图片
                                self._cleanup_old_images()
                                logger.info(f"图片已保存到: {local_path}")
                                return local_path
                except Exception as e:
                    logger.error(f"下载生成的图片失败: {e}")
            else:
                logger.error(f"生成图片失败，错误码: {result.get('code')}, 消息: {result.get('message')}")
        except Exception as e:
            logger.error(f"生成图片失败: {e}")

        return None

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

    def cleanup(self):
        """清理临时文件"""
        try:
            # 清理临时图片
            for img_path in self.temp_images:
                try:
                    if os.path.exists(img_path):
                        os.unlink(img_path)
                        logger.info(f"已删除临时图片: {img_path}")
                except Exception as e:
                    logger.error(f"删除临时图片失败: {e}")
        except Exception as e:
            logger.error(f"清理临时文件时出错: {e}")
