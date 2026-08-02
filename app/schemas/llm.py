from typing import List, Optional  # 引入类型标注用于描述字段结构

from pydantic import Field  # 引入Field用于定义字段默认值
from typing import Any  # 引入Any用于描述任意类型

from .base import BaseSchema  # 引入公共Schema基类
from .dto.semantic_anchor_dto import SemanticAnchorAxisCandidates  # 引入语义轴候选集合 DTO。
from pydantic import BaseModel, Field  # 引入Pydantic模型基类和字段定义



# qwen_suggest_client.py请求
class SuggestRequest(BaseSchema):  # 定义拍照建议请求模型
    username: str  # 当前登录用户名
    style: str  # 用户选择的风格
    location: Optional[str] = None  # 拍照地点
    time: Optional[str] = None  # 拍照时间
    weather: Optional[str] = None  # 拍照天气
    face_tags: List[str] = Field(default_factory=list)  # 人脸标签，可多选
    shot_tags: List[str] = Field(default_factory=list)  # 构图标签，可多选
    pose_tags: List[str] = Field(default_factory=list)  # 姿势标签，可多选
    extra_tags: List[str] = Field(default_factory=list)  # 额外选择项，便于前端一次性上传全部选项
    image_path: Optional[str] = None  # 图片路径
    image_mime_type: Optional[str] = None  # 图片MIME类型
    face_analysis: Optional[dict] = None  # 可选的人脸分析结果，后端会优先从数据库获取

# qwen_suggest_client.py响应
class SuggestResponse(BaseSchema):  # 定义拍照建议响应模型
    reason: Optional[str] = None  # 建议原因
    outfit: Optional[List[str]] = None  # 穿搭建议列表
    makeup: Optional[List[str]] = None  # 妆容建议列表
    poses: Optional[List[str]] = None  # 姿势建议列表
    summary: Optional[str] = None  # 整体总结


# qwen_face_client.py请求
class FaceAnalysisRequest(BaseModel):  # 定义人脸分析输出的数据结构
    description: str = Field(default="")  # 人物整体描述
    skin: str = Field(default="")  # 肤色和肤质描述
    facial_sense: str = Field(default="")  # 五官量感描述
    face_shape: str = Field(default="")  # 脸型描述
    facial_features: list[str] = Field(default_factory=list)  # 五官特点列表
    proportions: list[str] = Field(default_factory=list)  # 比例特点列表
    style_keywords: list[str] = Field(default_factory=list)  # 风格关键词列表
    has_face: bool = Field(default=True)  # 是否存在可识别人脸
    simple_analysis: dict[str, Any] = Field(default_factory=dict)  # 结构化简化分析结果


# qwen_face_client.py响应
class FaceAnalysisRespionse(BaseModel):  # 定义人脸分析响应结构
    description: str = Field(default="")  # 人物整体描述
    skin: str = Field(default="")  # 肤色特点
    facial_sense: str = Field(default="")  # 五官量感
    face_shape: str = Field(default="")  # 脸型特点
    facial_features: list[str] = Field(default_factory=list)  # 五官特点
    proportions: list[str] = Field(default_factory=list)  # 比例特点
    style_keywords: list[str] = Field(default_factory=list)  # 风格关键词
    has_face: bool = Field(default=True)  # 是否有人脸
    simple_analysis: dict[str, Any] = Field(default_factory=dict)  # 简化分析
    raw: str = Field(default="")  # 原始模型输出

# qwen_user_persona_analysis_client.py请求
class UserPersonaAnalysisRequest(BaseModel):  # 定义用户人格画像分析请求结构
    input_data: dict[str, Any] = Field(default_factory=dict)  # 输入数据
    output_data: dict[str, Any] = Field(default_factory=dict)  # 输出数据
    comment: str = Field(default="")  # 用户评论
    makeup_rating: int = Field(default=0)  # 妆容评分
    outfit_rating: int = Field(default=0)  # 穿搭评分
    pose_rating: int = Field(default=0)  # 姿势评分
    old_semantic_axes: Any | None = None  # 旧历史画像
    anchors: SemanticAnchorAxisCandidates | None = None  # 按语义轴聚合后的召回候选


# qwen_user_persona_analysis_client.py响应
class PreferenceAxisUpdateOutput(BaseModel):  # 单条语义轴更新的输出结构
    axis_name: str = Field(default="")  # 语义轴名称
    value: float = Field(default=0.0)  # 大模型判断置信度
    reason: str = Field(default="")  # 判断原因
class PreferenceAnalysisOutput(BaseModel):  # 用户偏好分析的整体输出结构
    axis_updates: list[PreferenceAxisUpdateOutput] = Field(default_factory=list)  # 语义轴更新列表
