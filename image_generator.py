import os
import sys
import uuid
import aiohttp
from astrbot.api import logger

# 修改get_food_image函数，增强图片获取的稳定性，并支持AI生成
async def get_food_image(food_name, output_dir, default_img_dir=None, context=None):
    """获取食物图片，使用AI生成"""
    import os  # 确保在函数内部导入os模块
    logger.info(f"开始获取食物图片: {food_name}")

    # 如果context有context属性，则使用context.context
    actual_context = context.context if context and hasattr(context, 'context') else context

    # 尝试使用本地doubao_image模块生成图片
    try:
        # 尝试导入本地doubao_image模块
        try:
            # 使用相对导入从当前包导入doubao_image模块
            from .doubao_image import generate_image
            logger.info("尝试使用本地doubao_image模块生成食物图片...")

            # 构建提示词
            prompt = f"高质量、写实风格的美食照片，特写镜头，\"{food_name}\"，美食摄影，精美摆盘，专业灯光，鲜艳色彩，美味可口的外观，食物特写"

            # 默认API密钥
            access_key = ""
            secret_key = ""

            # 如果上下文对象存在且有配置，尝试从配置中读取
            if actual_context and hasattr(actual_context, 'config'):
                try:
                    # 尝试从配置中读取API密钥
                    config_access_key = actual_context.config.get("volcengine_ak")
                    config_secret_key = actual_context.config.get("volcengine_sk")

                    # 如果配置中有密钥，使用配置中的密钥
                    if config_access_key and config_secret_key:
                        access_key = config_access_key
                        secret_key = config_secret_key
                        logger.info("使用配置文件中的API密钥")
                    else:
                        logger.info("使用默认API密钥")
                except Exception as e:
                    logger.warning(f"从配置中读取API密钥失败: {e}")

            logger.info(f"API密钥长度: {len(access_key)}, {len(secret_key)}")

            # 生成图片
            result = generate_image(access_key, secret_key, prompt)

            # 检查结果
            if result.get("code") == 10000:
                # 成功生成图片
                image_url = result["data"]["image_urls"][0]
                logger.info(f"成功使用本地doubao_image模块生成食物图片URL: {image_url}")

                # 下载图片
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url) as response:
                            if response.status == 200:
                                img_data = await response.read()
                                local_path = os.path.join(output_dir, f"{food_name}_{uuid.uuid4().hex[:8]}.jpg")
                                with open(local_path, "wb") as f:
                                    f.write(img_data)
                                # 记录这是一个临时图片
                                if actual_context and hasattr(actual_context, 'temp_images'):
                                    actual_context.temp_images.add(local_path)
                                    # 清理旧图片
                                    if hasattr(actual_context, '_cleanup_old_images'):
                                        actual_context._cleanup_old_images()
                                logger.info(f"已下载生成的图片到: {local_path}")
                                return local_path
                except Exception as e:
                    logger.error(f"下载生成的图片失败: {e}")
            else:
                logger.error(f"生成图片失败，错误码: {result.get('code')}, 消息: {result.get('message')}")
        except ImportError as ie:
            logger.info(f"未找到本地doubao_image模块，将使用其他方法获取图片: {ie}")
        except Exception as e:
            logger.error(f"使用本地doubao_image模块生成图片失败: {e}")
    except Exception as e:
        logger.error(f"生成图片过程中出错: {e}")

    # 已删除共享API生成图片的代码

    # 跳过在线API获取图片，直接使用AI生成
    logger.info("跳过在线API获取图片，使用AI生成或默认图片")

    # 如果所有生成方法都失败，不返回图片
    logger.info("所有图片生成方法都失败，不返回图片")

    # 如果所有方法都失败，返回None
    logger.warning(f"所有图片获取方法都失败，返回None")
    return None
