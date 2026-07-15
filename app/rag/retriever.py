import json  # 引入JSON模块用于读取种子数据
from pathlib import Path  # 引入Path用于处理文件路径

from app.models import SuggestRequest  # 引入请求模型


def _load_seed_items() -> list:  # 加载种子条目
    data_path = Path(__file__).resolve().parents[2] / "rag_seed_data.json"  # 定位种子数据文件路径
    if not data_path.exists():  # 如果种子文件不存在
        raise FileNotFoundError(f"知识库种子文件不存在: {data_path}")  # 直接暴露文件问题
    with data_path.open("r", encoding="utf-8") as file:  # 以UTF-8打开文件
        return json.load(file)  # 返回种子数据


def retrieve_context(payload: SuggestRequest, parsed_input: dict | None = None, image_analysis: dict | None = None) -> dict:  # 根据请求检索上下文
    items = _load_seed_items()  # 读取知识库种子数据
    outfit = []  # 初始化穿搭结果
    makeup = []  # 初始化妆容结果
    poses = []  # 初始化姿势结果
    scene_tips = []  # 初始化场景技巧结果
    parsed_input = parsed_input or {}  # 如果没有解析输入则使用空字典
    image_analysis = image_analysis or {}  # 如果没有图片分析则使用空字典
    for item in items:  # 遍历种子条目
        category = item.get("category")  # 获取类别
        style = item.get("style")  # 获取风格
        location = item.get("location")  # 获取地点
        time = item.get("time")  # 获取时间
        weather = item.get("weather")  # 获取天气
        face_angle = item.get("face_angle")  # 获取脸部角度
        pose_type = item.get("pose_type")  # 获取姿势类型
        style_match = not style or style == payload.style  # 判断风格是否匹配
        location_match = not location or location == payload.location  # 判断地点是否匹配
        time_match = not time or time == payload.time  # 判断时间是否匹配
        weather_match = not weather or weather == payload.weather  # 判断天气是否匹配
        if not (style_match and location_match and time_match and weather_match):  # 如果基础条件不匹配则跳过
            continue  # 跳过当前条目
        if category == "穿搭规则":  # 如果是穿搭规则
            outfit.append(item.get("content", ""))  # 收集穿搭内容
        if category == "妆容建议":  # 如果是妆容建议
            if not face_angle or face_angle in payload.face_tags:  # 如果角度匹配或未指定
                makeup.append(item.get("content", ""))  # 收集妆容内容
        if category == "姿势模板":  # 如果是姿势模板
            if not pose_type or pose_type in payload.pose_tags:  # 如果姿势类型匹配或未指定
                poses.append(item.get("content", ""))  # 收集姿势内容
        if category == "场景拍照技巧":  # 如果是场景拍照技巧
            scene_tips.append(item.get("content", ""))  # 收集场景技巧
    if image_analysis.get("description"):  # 如果存在Qwen人物描述
        scene_tips.insert(0, f"人物分析：{image_analysis['description']}")  # 把人物描述放入场景技巧前面
    if image_analysis.get("face_shape"):  # 如果存在脸型特点
        scene_tips.insert(0, f"脸型特点：{image_analysis['face_shape']}")  # 把脸型特点放入场景技巧前面
    if image_analysis.get("facial_features"):  # 如果存在五官特点
        scene_tips.insert(0, f"五官特点：{'；'.join(image_analysis['facial_features'])}")  # 把五官特点放入场景技巧前面
    if image_analysis.get("proportions"):  # 如果存在比例特点
        scene_tips.insert(0, f"比例特点：{'；'.join(image_analysis['proportions'])}")  # 把比例特点放入场景技巧前面
    if parsed_input.get("face_tags"):  # 如果有用户选择的人脸标签
        makeup.extend([f"用户偏好角度：{tag}" for tag in parsed_input["face_tags"]])  # 把偏好角度加入妆容辅助信息
    if image_analysis.get("style_keywords"):  # 如果存在风格关键词
        scene_tips.extend([f"风格提示：{tag}" for tag in image_analysis["style_keywords"]])  # 加入风格关键词
    return {  # 返回检索结果
        "outfit": outfit[:3],  # 限制穿搭数量
        "makeup": makeup[:3],  # 限制妆容数量
        "poses": poses[:3],  # 限制姿势数量
        "scene_tips": scene_tips[:2],  # 限制场景技巧数量
    }  # 检索结果结束
