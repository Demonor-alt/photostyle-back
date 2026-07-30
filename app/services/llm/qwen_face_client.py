import base64  # 引入base64用于把本地图片转换为可传输的字符串
import mimetypes  # 引入mimetypes用于推断图片类型
import os  # 引入os用于读取环境变量
from pathlib import Path  # 引入Path用于处理本地图片路径

import dashscope  # 引入DashScope SDK用于调用Qwen多模态接口
from langchain_core.output_parsers import PydanticOutputParser  # 引入Pydantic输出解析器

from app.services.llm.qwen_client import get_api_key, get_qwen_response_content  # 引入统一的Qwen鉴权和响应文本提取方法
from app.utils.runtime import logger  # 引入统一日志器
from app.schemas.llm import FaceAnalysisOutput  # 引入人脸分析输出模型
from app.config.enums.face_analysis import SIMPLE_ANALYSIS_ENUMS  # 引入人脸分析枚举

dashscope.base_http_api_url = os.getenv("DASHSCOPE_API_URL")  # 设置DashScope基础API地址
QWEN_FACE_MODEL = os.getenv("QWEN_FACE_MODEL")  # 读取人脸分析模型名称

_FACE_ANALYSIS_PARSER = PydanticOutputParser(pydantic_object=FaceAnalysisOutput)


def _build_simple_analysis_enum_text(enums: dict[str, object]) -> str:  # 将简化分析枚举递归展开为提示词文本
    lines: list[str] = []  # 收集每一层枚举描述
    for key, value in enums.items():  # 遍历当前层级
        if isinstance(value, dict):  # 如果是子结构，继续递归展开
            child_text = _build_simple_analysis_enum_text(value)  # 生成子结构文本
            lines.append(f'"{key}":{{{child_text}}}')  # 拼接当前层级
        else:  # 如果是枚举集合
            options = ",".join(f'"{item}"' for item in sorted(value))  # 排序后生成稳定输出
            lines.append(f'"{key}":[{options}]')  # 拼接枚举数组
    return ",".join(lines)  # 返回当前层级的JSON片段


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
        "simple_analysis结构如下：基础结构包含脸型、线条感、五官量感、面部对比度；五官特征包含眼睛、眉毛、鼻子、嘴巴、耳朵；皮肤与气质包含肤色、肤质、气质。"
        "其中基础字段和子字段必须选择一个最匹配的枚举值。"
        f"枚举如下：{{{_build_simple_analysis_enum_text(SIMPLE_ANALYSIS_ENUMS)}}}"
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
            result_format="message",  # 结果格式为message
        )  # 调用结束

        logger.info("qwen.analyze.raw_response=%s", response)  # 记录原始响应到日志
        content = get_qwen_response_content(response)  # 统一判断响应并提取 message.content 文本
        if content is None:  # 如果响应失败或结构异常
            raise ValueError(f"Qwen 调用失败，response={response}")  # 暴露调用失败
        parsed = _FACE_ANALYSIS_PARSER.parse(content)  # 使用LangChain解析并映射到Pydantic模型
    except Exception as exc:  # 如果调用或解析前步骤失败
        raise RuntimeError(f"Qwen 图片分析调用失败: {exc}") from exc  # 统一包装为可读错误
    has_face = parsed.has_face  # 提取是否有人脸
    if not has_face:  # 如果图片中没有可识别的人脸
        raise ValueError("图片未检测到人脸")  # 直接返回给前端的统一错误提示
    result = {  # 返回标准化结果
        "description": parsed.description.strip(),  # 人物整体描述
        "skin": parsed.skin.strip(),  # 肤色特点
        "facial_sense": parsed.facial_sense.strip(),  # 五官量感
        "face_shape": parsed.face_shape.strip(),  # 脸型特点
        "facial_features": _normalize_list(parsed.facial_features),  # 五官特点
        "proportions": _normalize_list(parsed.proportions),  # 比例特点
        "style_keywords": _normalize_list(parsed.style_keywords),  # 风格关键词
        "has_face": has_face,  # 是否有人脸
        "simple_analysis": parsed.simple_analysis,  # 简化分析
        "raw": content,  # 原始模型输出
    }  # 返回结果结束
    logger.info("qwen.analyze.output=%s", result)  # 记录结构化结果到日志
    return result  # 返回结果结束
