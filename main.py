from fastapi import FastAPI  # 引入FastAPI用于构建后端服务
from pydantic import BaseModel  # 引入Pydantic用于定义请求响应模型
from typing import List, Optional  # 引入类型标注用于描述字段结构

app = FastAPI(title="PhotoStyle AI Assistant", version="0.1.0")  # 创建FastAPI应用实例并设置标题与版本


class SuggestRequest(BaseModel):  # 定义拍照建议请求模型
    image_path: Optional[str] = None  # 用户上传图片路径
    style: str  # 用户选择的风格
    location: Optional[str] = None  # 拍照地点
    time: Optional[str] = None  # 拍照时间
    weather: Optional[str] = None  # 拍照天气
    face_tags: List[str] = []  # 人脸标签，可多选
    shot_tags: List[str] = []  # 构图标签，可多选
    pose_tags: List[str] = []  # 姿势标签，可多选


class SuggestResponse(BaseModel):  # 定义拍照建议响应模型
    outfit: List[str]  # 穿搭建议列表
    makeup: List[str]  # 妆容建议列表
    poses: List[str]  # 姿势建议列表
    summary: str  # 整体总结


@app.get("/")  # 定义健康检查接口
async def root() -> dict:  # 声明根路径返回字典
    return {"message": "PhotoStyle AI Assistant backend is running."}  # 返回服务运行状态


@app.post("/api/suggest", response_model=SuggestResponse)  # 定义建议生成接口
async def suggest(payload: SuggestRequest) -> SuggestResponse:  # 接收请求并返回建议
    outfit = [  # 构建穿搭建议
        f"风格以{payload.style}为主，优先选择与场景协调的配色。",  # 根据风格输出建议
        "避免过于复杂的图案，突出人物主体。",  # 通用穿搭建议
    ]  # 穿搭建议结束
    makeup = [  # 构建妆容建议
        "底妆保持清透，增强肤质通透感。",  # 底妆建议
        "眼妆与口红色系保持统一，提升整体氛围感。",  # 妆容协调建议
    ]  # 妆容建议结束
    poses = [  # 构建姿势建议
        "轻微侧身站立，手部自然下垂。",  # 姿势建议1
        "一只手轻扶头发或包包，增强画面层次。",  # 姿势建议2
        "视线偏离镜头，营造自然感。",  # 姿势建议3
    ]  # 姿势建议结束
    summary = f"已根据{payload.style}风格和当前场景生成基础建议。"  # 生成总结说明
    return SuggestResponse(outfit=outfit, makeup=makeup, poses=poses, summary=summary)  # 返回响应对象
