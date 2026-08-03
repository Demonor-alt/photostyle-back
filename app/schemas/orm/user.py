from datetime import datetime
from pydantic import Field

from app.schemas.base import BaseSchema

class FacePartAnalysis(BaseSchema):  # 定义单个五官部位的分析模型，例如眼睛、眉毛、鼻子、嘴巴、耳朵。
    class Config(BaseSchema.Config):  # 继承公共 Schema 配置，并补充本模型自己的配置。
        extra = "allow"  # 五官细节字段目前不固定，允许模型返回更多描述性字段。
        populate_by_name = True  # 允许用英文属性名或中文 alias 两种方式构造模型。



class SkinTemperament(BaseSchema): # 定义皮肤气质分析模型，对应用户 skin_temperament JSON 字段。
    skin_tone: str | None = Field(default=None, alias="肤色")  # 肤色分析，JSON 中使用中文键“肤色”。
    skin_texture: str | None = Field(default=None, alias="肤质")  # 肤质分析，JSON 中使用中文键“肤质”。
    temperament: str | None = Field(default=None, alias="气质")  # 整体气质分析，JSON 中使用中文键“气质”。
    class Config(BaseSchema.Config):  # 继承公共 Schema 配置，并补充本模型自己的配置。
        populate_by_name = True  # 允许用英文属性名或中文 alias 两种方式构造模型。


class FacialFeatures(BaseSchema):  # 定义五官特征分析模型，对应用户 facial_features JSON 字段。
    eyes: FacePartAnalysis | None = Field(default=None, alias="眼睛")  # 眼睛细节分析，JSON 中使用中文键“眼睛”。
    eyebrows: FacePartAnalysis | None = Field(default=None, alias="眉毛")  # 眉毛细节分析，JSON 中使用中文键“眉毛”。
    nose: FacePartAnalysis | None = Field(default=None, alias="鼻子")  # 鼻子细节分析，JSON 中使用中文键“鼻子”。
    mouth: FacePartAnalysis | None = Field(default=None, alias="嘴巴")  # 嘴巴细节分析，JSON 中使用中文键“嘴巴”。
    ears: FacePartAnalysis | None = Field(default=None, alias="耳朵")  # 耳朵细节分析，JSON 中使用中文键“耳朵”。
    class Config(BaseSchema.Config):  # 继承公共 Schema 配置，并补充本模型自己的配置。
        populate_by_name = True  # 允许用英文属性名或中文 alias 两种方式构造模型。


class SimpleFaceAnalysis(BaseSchema):  # 定义简化人脸分析模型，对应用户 simple_analysis JSON 字段。
    face_shape: str | None = Field(default=None, alias="脸型")  # 脸型分析，JSON 中使用中文键“脸型”。
    line_sense: str | None = Field(default=None, alias="线条感")  # 面部线条感分析，JSON 中使用中文键“线条感”。
    feature_volume: str | None = Field(default=None, alias="五官量感")  # 五官量感分析，JSON 中使用中文键“五官量感”。
    facial_contrast: str | None = Field(default=None, alias="面部对比度")  # 面部对比度分析，JSON 中使用中文键“面部对比度”。
    skin_temperament: SkinTemperament | None = Field(default=None, alias="皮肤与气质")  # 皮肤气质分析，JSON 中使用中文键“皮肤气质”。
    facial_features: FacialFeatures | None = Field(default=None, alias="五官特征")  # 五官特征分析，JSON 中使用中文键“五官特征”。

    class Config(BaseSchema.Config):  # 继承公共 Schema 配置，并补充本模型自己的配置。
        populate_by_name = True  # 允许用英文属性名或中文 alias 两种方式构造模型。


class FaceAnalysis(BaseSchema):  # 定义完整人脸分析模型，对应用户 face_analysis JSON 字段。
    skin: str | None = None # 皮肤类型
    has_face: bool | None = None # 是否有人脸
    face_shape: str | None = None # 脸型
    facial_sense: str | None = None # 五官量感与整体感觉
    description: str | None = None # 整体外貌描述
    proportions: list[str] = Field(default_factory=list) # 面部比例分析列表
    style_keywords: list[str] = Field(default_factory=list) # 风格关键词
    facial_features: list[str] = Field(default_factory=list) # 五官特征描述列表
    simple_analysis: SimpleFaceAnalysis | None = None # 简化人脸分析

class User(BaseSchema):
    id: int
    username: str
    password_hash: str
    photo_path: str | None = None
    photo_mime_type: str | None = None
    face_analysis: FaceAnalysis | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
