import base64  # 引入base64用于把本地图片转换为可传输的字符串
import json  # 引入json用于复制默认结构
import mimetypes  # 引入mimetypes用于推断图片类型
import os  # 引入os用于读取环境变量
from pathlib import Path  # 引入Path用于处理本地图片路径
from typing import Any

import dashscope  # 引入DashScope SDK用于调用Qwen多模态接口
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from app.services.llm.qwen_client import get_api_key, get_qwen_response_message
from app.utils.runtime import logger  # 引入统一日志器

dashscope.base_http_api_url = os.getenv("DASHSCOPE_API_URL")  # 设置DashScope基础API地址
QWEN_FACE_MODEL = os.getenv("QWEN_FACE_MODEL")

_SIMPLE_ANALYSIS_TEMPLATE: dict = {
    "脸型": "鹅蛋脸",
    "线条感": "适中",
    "五官量感": "中",
    "面部对比度": "中",
    "眼睛": {
        "眼型": "杏眼",
        "眼神": "清亮",
        "卧蚕": "无",
        "眼尾": "平直",
    },
    "眉毛": {
        "眉型": "平眉",
        "浓淡": "适中",
        "眉峰": "平缓",
        "是否断眉": "否",
    },
    "鼻子": {
        "鼻型": "高挺",
        "鼻翼": "适中",
    },
    "嘴巴": {
        "唇型": "适中",
        "唇形": "自然",
        "嘴角": "平直",
        "牙齿": "整齐",
    },
    "耳朵": {
        "大小": "适中",
        "贴合度": "贴合",
    },
    "肤色": "自然肤色",
    "肤质": "细腻",
    "气质": "知性",
    "风格向量": {
        "清新自然": 0,
        "甜美少女": 0,
        "轻熟气质": 0,
        "酷感中性": 0,
        "成熟性感": 0,
    },
}

_SIMPLE_ANALYSIS_ENUMS = {
    "脸型": {"鹅蛋脸", "圆脸", "方脸", "长脸", "菱形脸", "心形脸"},
    "线条感": {"柔和", "适中", "锐利"},
    "五官量感": {"轻", "中", "重"},
    "面部对比度": {"低", "中", "高"},
    "眼睛": {
        "眼型": {"杏眼", "丹凤眼", "圆眼", "细长眼"},
        "眼神": {"清亮", "柔和", "疏离", "有神"},
        "卧蚕": {"有", "无"},
        "眼尾": {"上扬", "平直", "下垂"},
    },
    "眉毛": {
        "眉型": {"剑眉", "柳叶眉", "平眉", "弯眉"},
        "浓淡": {"浓", "适中", "淡"},
        "眉峰": {"明显", "平缓"},
        "是否断眉": {"是", "否"},
    },
    "鼻子": {
        "鼻型": {"高挺", "扁平", "鹰钩", "蒜头"},
        "鼻翼": {"窄", "适中", "宽"},
    },
    "嘴巴": {
        "唇型": {"薄唇", "适中", "厚唇"},
        "唇形": {"M型", "自然"},
        "嘴角": {"上扬", "平直", "下垂"},
        "牙齿": {"整齐", "不整齐", "有虎牙"},
    },
    "耳朵": {
        "大小": {"小", "适中", "大"},
        "贴合度": {"贴合", "外扩"},
    },
    "肤色": {"冷白", "暖白", "自然肤色", "偏黄", "偏黑"},
    "肤质": {"细腻", "一般", "粗糙", "有瑕疵"},
    "气质": {"清纯", "甜美", "知性", "冷感", "成熟", "文艺", "元气"},
    "风格向量": {"清新自然", "甜美少女", "轻熟气质", "酷感中性", "成熟性感"},
}


class FaceAnalysisOutput(BaseModel):
    description: str = Field(default="")
    skin: str = Field(default="")
    facial_sense: str = Field(default="")
    face_shape: str = Field(default="")
    facial_features: list[str] = Field(default_factory=list)
    proportions: list[str] = Field(default_factory=list)
    style_keywords: list[str] = Field(default_factory=list)
    has_face: bool = Field(default=True)
    simple_analysis: dict[str, Any] = Field(default_factory=dict)


_FACE_ANALYSIS_PARSER = PydanticOutputParser(pydantic_object=FaceAnalysisOutput)


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                text_parts.append(str(item["text"]))
        return "\n".join(text_parts)
    return str(content)


def _build_image_payload(image_path: str | None, image_mime_type: str | None = None) -> dict | None:  # 构建Qwen图片输入
    if not image_path:  # 如果没有图片路径则直接返回空
        return None  # 表示当前没有可识别图片
    if image_path.startswith("http://") or image_path.startswith("https://"):  # 如果是公网图片地址
        return {"image": image_path}  # 直接按URL传给Qwen
    local_path = Path(image_path)  # 将字符串转换成本地路径对象
    if not local_path.exists():  # 如果本地文件不存在
        return None  # 返回空，让上层走兜底逻辑
    mime_type, _ = mimetypes.guess_type(str(local_path))  # 推断文件类型
    mime_type = image_mime_type or mime_type or "image/jpeg"  # 优先使用调用方传入类型，推断失败则默认按JPEG处理
    encoded = base64.b64encode(local_path.read_bytes()).decode("utf-8")  # 读取图片并转为Base64字符串
    return {"image": f"data:{mime_type};base64,{encoded}"}  # 按DashScope可识别格式返回



def _normalize_list(value: object) -> list[str]:  # 将任意值规范为字符串列表
    if isinstance(value, list):  # 如果本来就是列表
        return [str(item).strip() for item in value if str(item).strip()]  # 转换并过滤空值
    if isinstance(value, str):  # 如果是字符串
        parts = [part.strip() for part in value.replace("，", ",").split(",")]  # 按中英文逗号切分
        return [part for part in parts if part]  # 过滤空项
    return []  # 其他类型直接返回空列表


def _clamp_score(value: object) -> float:  # 将风格向量规范到0到1之间
    try:
        score = float(value)
    except Exception:
        return 0.0
    if score < 0:
        return 0.0
    if score > 1:
        return 1.0
    return round(score, 2)


def _normalize_simple_analysis(value: object) -> dict:  # 规范化simple_analysis为固定模板
    normalized = json.loads(json.dumps(_SIMPLE_ANALYSIS_TEMPLATE, ensure_ascii=False))
    if not isinstance(value, dict):
        return normalized

    def pick(path: list[str], candidate: object) -> None:
        target = normalized
        enum_target = _SIMPLE_ANALYSIS_ENUMS
        for key in path[:-1]:
            target = target[key]
            enum_target = enum_target[key]
        leaf = path[-1]
        if leaf == "风格向量":
            if isinstance(candidate, dict):
                for style_key in target:
                    target[style_key] = _clamp_score(candidate.get(style_key, target[style_key]))
            return
        if isinstance(candidate, str) and candidate in enum_target[leaf]:
            target[leaf] = candidate
        elif isinstance(candidate, dict):
            for sub_key, choices in enum_target[leaf].items():
                sub_value = candidate.get(sub_key)
                if isinstance(sub_value, str) and sub_value in choices:
                    target[leaf][sub_key] = sub_value
                elif sub_key == "风格向量" and isinstance(sub_value, dict):
                    for style_key in target[leaf]:
                        target[leaf][style_key] = _clamp_score(sub_value.get(style_key, target[leaf][style_key]))

    for key in ["脸型", "线条感", "五官量感", "面部对比度", "肤色", "肤质", "气质"]:
        if isinstance(value.get(key), str) and value[key] in _SIMPLE_ANALYSIS_ENUMS[key]:
            normalized[key] = value[key]

    for section in ["眼睛", "眉毛", "鼻子", "嘴巴", "耳朵"]:
        if isinstance(value.get(section), dict):
            pick([section], value[section])

    if isinstance(value.get("风格向量"), dict):
        normalized["风格向量"] = {k: _clamp_score(v) for k, v in value["风格向量"].items() if k in normalized["风格向量"]}
        for style_key in normalized["风格向量"]:
            normalized["风格向量"][style_key] = _clamp_score(value["风格向量"].get(style_key, normalized["风格向量"][style_key]))

    return normalized


def analyze_image(image_path: str | None, image_mime_type: str | None = None) -> dict:  # 调用Qwen分析图片并提取人物特征
    image_payload = _build_image_payload(image_path, image_mime_type=image_mime_type)  # 构建图片输入
    if image_payload is None:  # 如果没有有效图片
        raise ValueError(f"没有可用图片输入，image_path={image_path}")  # 直接暴露图片输入问题
    prompt = (  # 构建严格JSON提示词
        "请严格只返回JSON，不要输出任何解释、代码块、Markdown或多余文本。"
        f"请遵循以下格式要求：{_FACE_ANALYSIS_PARSER.get_format_instructions()}"
        "JSON字段必须包含description、skin、facial_sense、face_shape、facial_features、proportions、style_keywords、has_face、simple_analysis。"
        "description是对人物整体长相特点的简短中文描述。"
        "skin是肤色特点的简短中文描述，例如冷皮/暖皮/中性皮，以及肤质瑕疵。"
        "facial_sense是五官量感的简短中文描述。"
        "face_shape是脸型或脸部轮廓特点的简短中文描述，例如圆脸/方脸/长脸。"
        "facial_features是数组，描述五官特点，例如眼睛、鼻子、嘴巴、眉骨、下颌等，注意眉峰位置/眉尾走向，眼型，唇厚薄。"
        "proportions是数组，描述脸部或人物比例特点，例如三庭五眼、头身比、五官分布等。"
        "style_keywords是数组，提炼适合后续穿搭和拍照的风格关键词。"
        "has_face是布尔值，只有图片中明确存在可识别的人脸时才返回true，否则返回false。"
        "simple_analysis必须是严格结构化JSON对象，字段固定且只能从给定枚举中选择，不能生成新类别，不要重复description内容。"
        "simple_analysis结构如下：基础结构包含脸型、线条感、五官量感、面部对比度；五官特征包含眼睛、眉毛、鼻子、嘴巴、耳朵；皮肤与气质包含肤色、肤质、气质；风格向量包含清新自然、甜美少女、轻熟气质、酷感中性、成熟性感。"
        "其中基础字段和子字段必须选择一个最匹配的枚举值，风格向量每个值范围为0到1。"
        "枚举如下："
        "{\"脸型\":[\"鹅蛋脸\",\"圆脸\",\"方脸\",\"长脸\",\"菱形脸\",\"心形脸\"],\"线条感\":[\"柔和\",\"适中\",\"锐利\"],\"五官量感\":[\"轻\",\"中\",\"重\"],\"面部对比度\":[\"低\",\"中\",\"高\"],"
        "\"眼睛\":{\"眼型\":[\"杏眼\",\"丹凤眼\",\"圆眼\",\"细长眼\"],\"眼神\":[\"清亮\",\"柔和\",\"疏离\",\"有神\"],\"卧蚕\":[\"有\",\"无\"],\"眼尾\":[\"上扬\",\"平直\",\"下垂\"]},"
        "\"眉毛\":{\"眉型\":[\"剑眉\",\"柳叶眉\",\"平眉\",\"弯眉\"],\"浓淡\":[\"浓\",\"适中\",\"淡\"],\"眉峰\":[\"明显\",\"平缓\"],\"是否断眉\":[\"是\",\"否\"]},"
        "\"鼻子\":{\"鼻型\":[\"高挺\",\"扁平\",\"鹰钩\",\"蒜头\"],\"鼻翼\":[\"窄\",\"适中\",\"宽\"]},"
        "\"嘴巴\":{\"唇型\":[\"薄唇\",\"适中\",\"厚唇\"],\"唇形\":[\"M型\",\"自然\"],\"嘴角\":[\"上扬\",\"平直\",\"下垂\"],\"牙齿\":[\"整齐\",\"不整齐\",\"有虎牙\"]},"
        "\"耳朵\":{\"大小\":[\"小\",\"适中\",\"大\"],\"贴合度\":[\"贴合\",\"外扩\"]},"
        "\"肤色\":[\"冷白\",\"暖白\",\"自然肤色\",\"偏黄\",\"偏黑\"],\"肤质\":[\"细腻\",\"一般\",\"粗糙\",\"有瑕疵\"],\"气质\":[\"清纯\",\"甜美\",\"知性\",\"冷感\",\"成熟\",\"文艺\",\"元气\"],"
        "\"风格向量\":{\"清新自然\":0~1,\"甜美少女\":0~1,\"轻熟气质\":0~1,\"酷感中性\":0~1,\"成熟性感\":0~1}}"
        "如果无法判断，请使用最接近的默认值或0。"
    )  # 设定分析提示词
    messages = [  # 构建多模态消息
        {  # 构造用户消息
            "role": "user",  # 指定角色为用户
            "content": [image_payload, {"text": prompt}],  # 同时传递图片和文本要求
        }  # 用户消息结束
    ]  # 消息列表结束
    try:  # 捕获调用过程中的全部异常
        logger.info("qwen.analyze.calling model=%s image_path=%s", "QWEN_FACE_MODEL", image_path)  # 记录调用开始
        
        response = dashscope.MultiModalConversation.call(  # 调用Qwen多模态能力
            api_key=get_api_key(),  # 传入DashScope密钥
            model=QWEN_FACE_MODEL,  # 指定Qwen模型
            messages=messages,  # 传入消息列表
        )  # 调用结束

        logger.info("qwen.analyze.raw_response=%s", response)  # 记录原始响应到日志
        message = get_qwen_response_message(response)  # 统一判断Qwen响应并提取message
        if message is None:  # 如果响应失败或结构异常
            raise ValueError(f"Qwen 调用失败，response={response}")  # 暴露调用失败
        content = _message_text(message)  # 提取模型返回的文本内容
        parsed = _FACE_ANALYSIS_PARSER.parse(content)  # 使用LangChain解析并映射到Pydantic模型
    except Exception as exc:  # 如果调用或解析前步骤失败
        raise RuntimeError(f"Qwen 图片分析调用失败: {exc}") from exc  # 统一包装为可读错误
    has_face = parsed.has_face  # 提取是否有人脸
    if not has_face:  # 如果图片中没有可识别的人脸
        raise ValueError("图片未检测到人脸")  # 直接返回给前端的统一错误提示
    description = parsed.description.strip()  # 提取整体描述
    skin = parsed.skin.strip()  # 提取肤色特点
    facial_sense = parsed.facial_sense.strip()  # 提取五官量感
    face_shape = parsed.face_shape.strip()  # 提取脸型特点
    facial_features = _normalize_list(parsed.facial_features)  # 提取五官特点
    proportions = _normalize_list(parsed.proportions)  # 提取比例特点
    style_keywords = _normalize_list(parsed.style_keywords)  # 提取风格关键词
    simple_analysis = _normalize_simple_analysis(parsed.simple_analysis)  # 提取并规范化简化分析
    result = {  # 返回标准化结果
        "description": description,  # 人物整体描述
        "skin": skin,  # 肤色特点
        "facial_sense": facial_sense,  # 五官量感
        "face_shape": face_shape,  # 脸型特点
        "facial_features": facial_features,  # 五官特点
        "proportions": proportions,  # 比例特点
        "style_keywords": style_keywords,  # 风格关键词
        "has_face": has_face,  # 是否有人脸
        "simple_analysis": simple_analysis,  # 简化分析
        "raw": content,  # 原始模型输出
    }  # 返回结果结束
    logger.info("qwen.analyze.output=%s", result)  # 记录结构化结果到日志
    return result  # 返回结果结束
