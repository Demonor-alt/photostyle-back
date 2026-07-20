import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量（必须在其他导入之前）
root_dir = Path(__file__).parent.parent
env_path = root_dir / ".env"
load_dotenv(dotenv_path=env_path)

# 将项目根目录添加到 Python 路径
sys.path.insert(0, str(root_dir))

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError  # 请求校验异常
from fastapi.middleware.cors import CORSMiddleware  # 跨域请求
from fastapi.responses import JSONResponse  # JSON响应

from app.api.user import router as user_router  # 用户路由
from app.api.history import router as history_router  # 历史记录路由
from app.utils.runtime import DEBUG_ENABLED, LOG_KEEP_DAYS, LOG_LEVEL_NAME, LOG_MAX_BYTES, logger  # 日志
from app.db import init_db  # 数据库初始化


app = FastAPI(title="PhotoStyle AI Assistant", version="0.1.0")  # 创建FastAPI应用实例并设置标题与版本

# 初始化数据库表结构
init_db()
app.add_middleware(  # 注册CORS中间件
    CORSMiddleware,  # 使用FastAPI官方CORS中间件
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # 允许前端Vite开发地址
    allow_credentials=True,  # 允许携带凭据
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有请求头
)  # CORS配置结束
app.include_router(user_router, prefix="/api")  # 挂载用户API路由
app.include_router(history_router, prefix="/api")  # 挂载历史记录API路由


def _error_payload(exc: Exception, path: str, detail: str | None = None) -> dict:  # 构造统一错误响应体
    payload = {"success": False, "error": {"type": exc.__class__.__name__, "message": str(exc), "path": path}}  # 构造基础错误结构
    if detail is not None:  # 如果有附加细节
        payload["error"]["detail"] = detail  # 写入附加细节
    return payload  # 返回统一错误结构


def _configure_external_observability() -> None:  # 配置链路追踪与调试基础设施
    langchain_tracing = os.getenv("LANGCHAIN_TRACING_V2", "false").strip().lower() in {"1", "true", "yes", "on"}  # 读取LangSmith追踪开关
    if langchain_tracing:  # 如果启用了链路追踪
        logger.info("LangSmith tracing 已启用，LANGCHAIN_TRACING_V2=%s", os.getenv("LANGCHAIN_TRACING_V2"))  # 记录追踪状态
        logger.info("LANGCHAIN_PROJECT=%s", os.getenv("LANGCHAIN_PROJECT", "photostyle"))  # 记录项目名
        logger.info("LANGCHAIN_API_KEY=%s", "已配置" if os.getenv("LANGCHAIN_API_KEY") else "未配置")  # 记录密钥状态
    if DEBUG_ENABLED:  # 如果启用了调试模式
        logger.debug("DEBUG 模式已启用，后端日志将输出到文件和控制台")  # 记录调试状态
        logger.debug("日志级别=%s, 单文件上限=%s 字节, 保留天数=%s", LOG_LEVEL_NAME, LOG_MAX_BYTES, LOG_KEEP_DAYS)  # 记录日志切分配置


_configure_external_observability()  # 启动时配置可观测性


@app.exception_handler(ValueError)  # 处理业务校验和调用异常
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:  # 返回统一JSON错误结构
    logger.exception("ValueError on %s", request.url.path, exc_info=exc)  # 写入异常日志
    return JSONResponse(status_code=400, content=_error_payload(exc, str(request.url.path)))  # 返回详细错误


@app.exception_handler(RuntimeError)  # 处理运行时异常
async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:  # 返回统一JSON错误结构
    logger.exception("RuntimeError on %s", request.url.path, exc_info=exc)  # 写入异常日志
    return JSONResponse(status_code=500, content=_error_payload(exc, str(request.url.path)))  # 返回详细错误


@app.exception_handler(RequestValidationError)  # 处理请求参数校验异常
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:  # 返回统一JSON错误结构
    logger.warning("ValidationError on %s: %s", request.url.path, exc.errors())  # 写入校验日志
    return JSONResponse(status_code=422, content={"success": False, "error": {"type": "RequestValidationError", "message": "请求参数校验失败", "details": exc.errors(), "path": str(request.url.path)}})  # 返回详细错误


@app.exception_handler(Exception)  # 处理所有未预期异常
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:  # 返回统一JSON错误结构
    logger.exception("Unexpected error on %s", request.url.path, exc_info=exc)  # 写入异常日志
    return JSONResponse(status_code=500, content=_error_payload(exc, str(request.url.path)))  # 返回详细错误


@app.get("/")  # 定义健康检查接口
async def root() -> dict:  # 声明根路径返回字典
    return {"message": "PhotoStyle AI Assistant backend is running."}  # 返回服务运行状态


if __name__ == "__main__":  # 如果作为主程序运行
    import uvicorn  # 引入uvicorn服务器
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)  # 启动服务器，支持热重载
