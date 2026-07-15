import os  # 引入环境变量模块

try:  # 尝试导入MySQL连接库
    import pymysql  # type: ignore[import-not-found]  # 引入PyMySQL用于连接MySQL
except Exception:  # 如果当前环境未安装依赖
    pymysql = None  # 将连接库置空，便于启动时直接报错


def _get_bool_env(name: str, default: bool = False) -> bool:  # 从环境变量读取布尔值
    value = os.getenv(name)  # 读取字符串值
    if value is None:  # 如果未设置
        return default  # 返回默认值
    return value.strip().lower() in {"1", "true", "yes", "on"}  # 规范为布尔值


def get_mysql_config() -> dict:  # 获取MySQL配置
    return {  # 返回完整配置字典
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),  # 数据库主机
        "port": int(os.getenv("MYSQL_PORT", "3306")),  # 数据库端口
        "user": os.getenv("MYSQL_USER", "root"),  # 数据库用户名
        "password": os.getenv("MYSQL_PASSWORD", ""),  # 数据库密码
        "database": os.getenv("MYSQL_DATABASE", "photostyle"),  # 数据库名称
        "connect_timeout": int(os.getenv("MYSQL_CONNECT_TIMEOUT", "5")),  # 连接超时
        "pool_enabled": _get_bool_env("MYSQL_POOL_ENABLED", False),  # 是否启用连接池
    }  # 配置字典结束


def create_mysql_connection():  # 创建MySQL连接
    if pymysql is None:  # 如果依赖不可用
        raise RuntimeError("缺少 pymysql 依赖，请先安装后再连接本地 MySQL")  # 直接失败，避免悄悄回退到SQLite
    config = get_mysql_config()  # 获取数据库配置
    try:  # 尝试连接MySQL
        return pymysql.connect(  # 创建连接对象
            host=config["host"],  # 设置主机
            port=config["port"],  # 设置端口
            user=config["user"],  # 设置用户名
            password=config["password"],  # 设置密码
            database=config["database"],  # 设置数据库
            charset="utf8mb4",  # 设置字符集
            autocommit=False,  # 关闭自动提交
            connect_timeout=config["connect_timeout"],  # 设置超时
        )
    except Exception as exc:
        raise ConnectionError(
            f"无法连接到本地 MySQL，请检查 MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DATABASE：{exc}"
        ) from exc
