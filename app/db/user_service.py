import json  # 引入JSON模块用于序列化与反序列化
import os  # 引入环境变量模块

from passlib.context import CryptContext  # 引入密码哈希工具

from app.db.connection import create_mysql_connection  # 引入数据库连接工厂
from app.db.mysql_repo import MySQLUserRepository  # 引入用户仓储


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # 使用bcrypt保存密码哈希


def _get_repository():  # 获取用户仓储
    connection = create_mysql_connection()  # 创建MySQL连接
    return MySQLUserRepository(connection)  # 返回用户仓储实例


def _default_password() -> str:  # 读取默认测试密码
    return os.getenv("DEFAULT_LOGIN_PASSWORD", "123456")  # 允许本地开发使用默认密码


def _password_byte_length(password: str) -> int:  # 计算密码的UTF-8字节长度
    return len(password.encode("utf-8"))


def _validate_password(password: str) -> None:  # 统一校验密码约束
    if not password:
        raise ValueError("密码不能为空")
    if _password_byte_length(password) > 72:
        raise ValueError("密码过长：bcrypt 只支持最多 72 字节，请缩短密码或使用更短的内容")


def hash_password(password: str) -> str:  # 生成密码哈希
    _validate_password(password)
    return _pwd_context.hash(password)  # 使用bcrypt加密


def verify_password(password: str, password_hash: str) -> bool:  # 校验密码
    _validate_password(password)
    return _pwd_context.verify(password, password_hash)  # 返回校验结果


def ensure_user(username: str, password: str | None = None) -> dict:  # 确保用户存在
    repository = _get_repository()  # 获取仓储
    repository.ensure_schema()  # 确保表结构存在
    user = repository.get_by_username(username)  # 查询用户
    if user is not None:  # 如果用户已存在
        return user  # 直接返回
    plain_password = password or _default_password()  # 使用默认密码或传入密码
    user_id = repository.create(username=username, password_hash=hash_password(plain_password))  # 创建用户
    return repository.get_by_id(user_id)  # 返回新创建用户


def login_user(username: str, password: str) -> dict:  # 登录校验
    repository = _get_repository()  # 获取仓储
    repository.ensure_schema()  # 确保表结构存在
    user = repository.get_by_username(username)  # 根据用户名查用户
    if user is None:  # 如果用户不存在
        raise ValueError("用户名或密码错误")  # 统一返回错误信息
    try:
        if not verify_password(password, user["password_hash"]):  # 如果密码不正确
            raise ValueError("用户名或密码错误")  # 统一返回错误信息
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    return user  # 返回用户信息


def get_user_profile(username: str) -> dict:  # 获取用户资料
    repository = _get_repository()  # 获取仓储
    repository.ensure_schema()  # 确保表结构存在
    user = repository.get_by_username(username)  # 查询用户
    if user is None:  # 如果用户不存在
        raise ValueError("用户不存在")  # 直接报错
    return user  # 返回用户资料


def upsert_user_photo(username: str, photo_path: str, photo_mime_type: str | None = None, face_analysis: dict | None = None) -> dict:  # 保存或更新用户照片
    repository = _get_repository()  # 获取仓储
    repository.ensure_schema()  # 确保表结构存在
    user = repository.get_by_username(username)  # 查询用户
    if user is None:  # 如果用户不存在
        raise ValueError("用户不存在")  # 直接报错
    repository.update_photo(
        username=username,
        photo_path=photo_path,
        photo_mime_type=photo_mime_type,
        face_analysis=json.dumps(face_analysis, ensure_ascii=False) if face_analysis is not None else None,
    )  # 更新照片信息
    return repository.get_by_username(username)  # 返回最新用户信息


def update_user_profile(username: str, *, new_username: str | None = None, password: str | None = None, photo_path: str | None = None, photo_mime_type: str | None = None, face_analysis: dict | None = None) -> dict:  # 更新用户资料
    repository = _get_repository()  # 获取仓储
    repository.ensure_schema()  # 确保表结构存在
    user = repository.get_by_username(username)  # 查询用户
    if user is None:  # 如果用户不存在
        raise ValueError("用户不存在")  # 直接报错
    updated_username = new_username or username  # 使用新用户名或原用户名
    if new_username and new_username != username:  # 如果需要修改用户名
        existing = repository.get_by_username(new_username)  # 检查目标用户名
        if existing is not None:  # 如果已存在
            raise ValueError("用户名已存在")  # 提示冲突
    repository.update_profile(
        username=username,
        new_username=updated_username,
        password_hash=hash_password(password) if password else None,
        photo_path=photo_path,
        photo_mime_type=photo_mime_type,
        face_analysis=json.dumps(face_analysis, ensure_ascii=False) if face_analysis is not None else None,
    )  # 更新资料
    return repository.get_by_username(updated_username)  # 返回最新用户信息


def get_user_photo_payload(username: str) -> dict | None:  # 获取用户照片数据
    repository = _get_repository()  # 获取仓储
    repository.ensure_schema()  # 确保表结构存在
    return repository.get_photo_payload(username)  # 返回照片载荷
