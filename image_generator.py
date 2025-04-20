import os
import uuid
import aiohttp
from astrbot.api import logger

async def generate_food_image(food_name, prompt=None, context=None, output_dir=None, width=1024, height=1024):
    """
    使用AI生成食物图片

    Args:
        food_name: 食物名称
        prompt: 自定义提示词，如果为None则使用默认提示词
        context: 上下文对象，用于获取配置和记录临时图片
        output_dir: 输出目录，如果为None则使用context中的OUTPUT_DIR
        width: 图片宽度，默认为1024
        height: 图片高度，默认为1024

    Returns:
        str: 生成的图片路径，如果失败则返回None
    """
    # 确保输出目录存在
    if output_dir is None:
        if hasattr(context, 'OUTPUT_DIR'):
            output_dir = context.OUTPUT_DIR
        else:
            # 使用当前目录下的output目录
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(output_dir, exist_ok=True)

    # 构建默认提示词
    if prompt is None:
        prompt = f"高质量、写实风格的美食照片，特写镜头，\"{food_name}\"，美食摄影，精美摆盘，专业灯光，鲜艳色彩，美味可口的外观，食物特写"

    logger.info(f"开始生成食物图片: {food_name}")

    # 获取API密钥
    access_key = ""
    secret_key = ""

    # 从配置中读取API密钥
    if context and hasattr(context, 'config'):
        try:
            access_key = context.config.get("volcengine_ak", "")
            secret_key = context.config.get("volcengine_sk", "")

            if access_key and secret_key:
                logger.info("使用配置文件中的API密钥")
            else:
                logger.warning("未配置API密钥，无法生成图片")
                return None
        except Exception as e:
            logger.error(f"从配置中读取API密钥失败: {e}")
            return None
    else:
        logger.warning("无法获取配置，无法生成图片")
        return None

    # 生成图片
    try:
        # 导入doubao_image模块
        try:
            from .doubao_image import generate_image

            # 获取模型和配置
            model = context.config.get("volcengine_model", "high_aes_general_v21_L") if context and hasattr(context, 'config') else "high_aes_general_v21_L"
            schedule_conf = context.config.get("schedule_conf", "general_v20_9B_pe") if context and hasattr(context, 'config') else "general_v20_9B_pe"
            region = context.config.get("region", "cn-north-1") if context and hasattr(context, 'config') else "cn-north-1"
            service = context.config.get("service", "cv") if context and hasattr(context, 'config') else "cv"

            # 调用API生成图片
            result = generate_image(
                access_key,
                secret_key,
                prompt,
                width=width,
                height=height,
                model=model,
                schedule_conf=schedule_conf,
                region=region,
                service=service
            )

            # 检查结果
            if result.get("code") == 10000:
                # 成功生成图片
                image_url = result["data"]["image_urls"][0]
                logger.info(f"成功生成图片URL: {image_url}")

                # 下载图片
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url) as response:
                            if response.status == 200:
                                img_data = await response.read()
                                local_path = os.path.join(output_dir, f"{food_name}_{uuid.uuid4().hex[:8]}.jpg")

                                with open(local_path, "wb") as f:
                                    f.write(img_data)

                                # 记录临时图片
                                if context and hasattr(context, 'temp_images'):
                                    context.temp_images.add(local_path)
                                    # 清理旧图片
                                    if hasattr(context, '_cleanup_old_images'):
                                        context._cleanup_old_images()

                                logger.info(f"已下载生成的图片到: {local_path}")
                                return local_path
                except Exception as e:
                    logger.error(f"下载生成的图片失败: {e}")
            else:
                logger.error(f"生成图片失败，错误码: {result.get('code')}, 消息: {result.get('message')}")
        except ImportError:
            logger.error("未找到doubao_image模块，无法生成图片")
        except Exception as e:
            logger.error(f"生成图片失败: {e}")
    except Exception as e:
        logger.error(f"生成图片过程中出错: {e}")

    return None

# 为了向后兼容，保留原来的函数名
async def get_food_image(food_name, output_dir, default_img_dir=None, context=None, width=1024, height=1024):
    """
    获取食物图片（向后兼容的函数）

    Args:
        food_name: 食物名称
        output_dir: 输出目录
        default_img_dir: 默认图片目录（不再使用）
        context: 上下文对象
        width: 图片宽度，默认为1024
        height: 图片高度，默认为1024

    Returns:
        str: 生成的图片路径，如果失败则返回None
    """
    # default_img_dir 参数不再使用，仅为了兼容旧版本的调用
    return await generate_food_image(food_name, context=context, output_dir=output_dir, width=width, height=height)
