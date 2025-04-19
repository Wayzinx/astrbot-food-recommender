import datetime
import random
import aiohttp
from astrbot.api import logger

# 食物列表，分为不同类别
FOOD_CATEGORIES = {
    "中餐": [
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
    "早餐": [
        "豆浆油条", "煎饼果子", "馄饨", "包子", "饺子", "茶叶蛋", "小米粥", "八宝粥",
        "烧饼", "肉夹馍", "手抓饼", "生煎包", "麻球", "三明治", "鸡蛋饼", "馒头", "茶鸡蛋"
    ],
    "甜点": [
        "冰淇淋", "蛋糕", "巧克力", "饼干", "奶茶", "果冻", "布丁", "芝士蛋糕", "蛋挞",
        "豆花", "豆腐脑", "凉粉", "杨枝甘露", "西米露", "绿豆沙", "红豆沙冰", "芒果捞"
    ]
}

# 推荐理由模板 - 使用动态生成替代
REASON_TEMPLATES = [
    "今天{date}，{city_text}{temperature}°C的{weather}天气下，来一份{food}绝对是明智之选！",
    "{city_text}{season}的{time_of_day}，{temperature}°C{weather}天气，来一份{food}正合适！",
    "{city_text}现在{weather}，{temperature}°C，尝尝{food}会让你的{time_of_day}更美好！"
]

# 食物描述模板 - 使用动态生成替代
FOOD_DESCRIPTIONS = {}

# 季节映射
def get_season():
    month = datetime.datetime.now().month
    if month in [12, 1, 2]:
        return "冬季"
    elif month in [3, 4, 5]:
        return "春季"
    elif month in [6, 7, 8]:
        return "夏季"
    else:
        return "秋季"

# 中国主要城市列表，用于从用户文本中识别城市
CHINA_CITIES = [
    "北京", "上海", "广州", "深圳", "成都", "重庆", "杭州", "武汉", "西安", "南京",
    "天津", "苏州", "郑州", "长沙", "青岛", "沈阳", "宁波", "东莞", "无锡", "大连",
    "厦门", "福州", "济南", "合肥", "昆明", "哈尔滨", "佛山", "长春", "温州", "石家庄",
    "南宁", "常州", "泉州", "南昌", "贵阳", "太原", "烟台", "嘉兴", "南通", "金华",
    "珠海", "惠州", "徐州", "海口", "乌鲁木齐", "绍兴", "中山", "台州", "兰州"
]

# 获取天气信息的函数
async def get_weather(user_text=None):
    try:
        # 默认城市为上海或北京
        city = random.choice(["上海", "北京"])

        # 如果提供了用户文本，尝试从中识别城市
        if user_text:
            for c in CHINA_CITIES:
                if c in user_text:
                    city = c
                    logger.info(f"从用户文本中识别到城市: {city}")
                    break

        # 使用wttr.in API获取指定城市的天气
        url = f"https://wttr.in/{city}?format=j1"
        logger.info(f"获取城市 {city} 的天气信息")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    current = data.get("current_condition", [{}])[0]
                    temp_c = current.get("temp_C", "20")
                    weather_desc = current.get("weatherDesc", [{"value": "晴朗"}])[0].get("value", "晴朗")
                    return {
                        "temperature": temp_c,
                        "weather": weather_desc,
                        "city": city
                    }
                else:
                    # 如果API请求失败，返回默认值
                    logger.warning(f"获取 {city} 天气失败，状态码: {response.status}")
                    return {"temperature": "20", "weather": "晴朗", "city": city}
    except Exception as e:
        logger.error(f"获取天气信息失败: {e}")
        # 出错时返回默认值
        return {"temperature": "20", "weather": "晴朗", "city": city if 'city' in locals() else "上海"}
