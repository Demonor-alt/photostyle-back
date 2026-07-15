import logging  # 引入logging用于统一日志输出
import os  # 引入os用于读取环境变量
from logging.handlers import TimedRotatingFileHandler  # 引入按时间滚动的日志处理器
from pathlib import Path  # 引入Path用于处理日志文件路径

from dotenv import load_dotenv  # 引入dotenv用于加载环境变量


load_dotenv()  # 在工具模块初始化时加载环境变量

DEBUG_ENABLED = os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}  # 读取调试开关
LOG_DIR = Path(os.getenv("LOG_DIR", Path(__file__).resolve().parents[2] / "logs"))  # 读取日志目录
LOG_DIR.mkdir(parents=True, exist_ok=True)  # 确保日志目录存在
LOG_LEVEL_NAME = os.getenv("LOG_LEVEL", "INFO").strip().upper()  # 读取日志级别名称
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)  # 将日志级别名称转换为数值级别
LOG_KEEP_DAYS = int(os.getenv("LOG_KEEP_DAYS", "7"))  # 读取日志保留天数
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 读取单个日志文件最大字节数

logger = logging.getLogger("photostyle")  # 创建应用日志器
if not logger.handlers:  # 如果日志器尚未配置
    logger.setLevel(logging.DEBUG if DEBUG_ENABLED else LOG_LEVEL)  # 根据DEBUG和日志级别配置日志器
    file_handler = TimedRotatingFileHandler(  # 创建按天滚动的文件日志处理器
        LOG_DIR / "app.log",  # 指定日志文件路径
        when="midnight",  # 按午夜切分日志
        interval=1,  # 每1天切分一次
        backupCount=LOG_KEEP_DAYS,  # 保留最近N天日志
        encoding="utf-8",  # 设置文件编码
        utc=False,  # 使用本地时间切分
    )  # 按天滚动处理器结束
    file_handler.maxBytes = LOG_MAX_BYTES  # 保留最大字节配置供调试参考
    file_handler.setLevel(logging.DEBUG if DEBUG_ENABLED else LOG_LEVEL)  # 设置文件日志级别
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))  # 设置日志格式
    logger.addHandler(file_handler)  # 挂载文件处理器
    if DEBUG_ENABLED:  # 如果启用调试模式
        console_handler = logging.StreamHandler()  # 创建控制台处理器
        console_handler.setLevel(logging.DEBUG)  # 设置控制台日志级别
        console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))  # 设置控制台格式
        logger.addHandler(console_handler)  # 挂载控制台处理器
