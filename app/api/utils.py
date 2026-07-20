import json  # 引入json用于解析标签数据
import logging  # 引入logging用于记录信息
from pathlib import Path  # 引入Path用于处理临时文件保存路径
from uuid import uuid4  # 引入uuid用于生成临时文件名

from fastapi import UploadFile  # 引入UploadFile类型

logger = logging.getLogger(__name__)  # 创建日志器


def save_upload_file(upload: UploadFile) -> tuple[str, str]:  # 保存上传文件到本地临时目录
    """
    保存上传文件到本地临时目录
    
    Args:
        upload: FastAPI上传文件对象
        
    Returns:
        tuple[str, str]: 返回文件路径和MIME类型
    """
    suffix = Path(upload.filename or "image.jpg").suffix or ".jpg"  # 获取文件后缀
    target_dir = Path(__file__).resolve().parents[2] / "uploads"  # 定位临时目录
    target_dir.mkdir(parents=True, exist_ok=True)  # 如果目录不存在则创建
    target_path = target_dir / f"{uuid4().hex}{suffix}"  # 生成唯一文件名
    content = upload.file.read()  # 读取上传文件内容
    target_path.write_bytes(content)  # 写入本地文件
    mime_type = upload.content_type or "image/jpeg"  # 记录MIME类型
    return str(target_path), mime_type  # 返回文件路径和MIME类型


def parse_tag_list(raw_value: str) -> list[str]:  # 解析前端传来的JSON标签字符串
    """
    解析前端传来的JSON标签字符串
    
    Args:
        raw_value: JSON格式的标签字符串
        
    Returns:
        list[str]: 解析后的标签列表
        
    Raises:
        ValueError: 当解析失败或格式不正确时
    """
    try:  # 尝试正常解析
        value = json.loads(raw_value)  # 将JSON字符串转换为列表
        if isinstance(value, list):  # 如果结果是列表
            return [str(item).strip() for item in value if str(item).strip()]  # 规范成字符串列表
        raise ValueError("标签字段必须是 JSON 数组")  # 直接暴露格式错误
    except Exception as exc:  # 如果解析失败
        raise ValueError(f"标签字段解析失败: {raw_value}") from exc  # 不再静默吞掉异常
