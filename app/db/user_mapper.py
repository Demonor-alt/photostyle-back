"""用户服务层 - 使用 ORM"""
import os
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.db.models.user import User
from app.db.database import SessionLocal

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _default_password() -> str:
    """读取默认测试密码"""
    return os.getenv("DEFAULT_LOGIN_PASSWORD", "123456")


def _password_byte_length(password: str) -> int:
    """计算密码的UTF-8字节长度"""
    return len(password.encode("utf-8"))


def _validate_password(password: str) -> None:
    """统一校验密码约束"""
    if not password:
        raise ValueError("密码不能为空")
    if _password_byte_length(password) > 72:
        raise ValueError("密码过长：bcrypt 只支持最多 72 字节，请缩短密码或使用更短的内容")


def hash_password(password: str) -> str:
    """生成密码哈希"""
    _validate_password(password)
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码"""
    _validate_password(password)
    return _pwd_context.verify(password, password_hash)


def ensure_user(username: str, password: str | None = None) -> dict:
    """确保用户存在"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            return user.to_dict()
        
        plain_password = password or _default_password()
        new_user = User(
            username=username,
            password_hash=hash_password(plain_password)
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user.to_dict()
    finally:
        db.close()


def login_user(username: str, password: str) -> dict:
    """登录校验"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError("用户名或密码错误")
        
        try:
            if not verify_password(password, user.password_hash):
                raise ValueError("用户名或密码错误")
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        
        return user.to_dict()
    finally:
        db.close()


def get_user_profile(username: str) -> dict:
    """获取用户资料"""
    db = SessionLocal()  # 创建数据库会话
    try:  # 开始查询
        user = db.query(User).filter(User.username == username).first()  # 按用户名查找用户
        if not user:  # 如果用户不存在
            raise ValueError("用户不存在")  # 直接抛出异常
        return user.to_dict()  # 返回用户字典
    finally:  # 无论如何都关闭会话
        db.close()  # 关闭数据库会话


def get_user_profile_by_id(user_id: int) -> dict:
    """根据用户ID获取用户资料"""
    db = SessionLocal()  # 创建数据库会话
    try:  # 开始查询
        user = db.query(User).filter(User.id == user_id).first()  # 按ID查找用户
        if not user:  # 如果用户不存在
            raise ValueError("用户不存在")  # 直接抛出异常
        return user.to_dict()  # 返回用户字典
    finally:  # 无论如何都关闭会话
        db.close()  # 关闭数据库会话


def upsert_user_photo(username: str, photo_path: str, photo_mime_type: str | None = None, face_analysis: dict | None = None, simple_analysis: dict | None = None) -> dict:
    """保存或更新用户照片"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError("用户不存在")
        
        user.photo_path = photo_path
        user.photo_mime_type = photo_mime_type
        user.face_analysis = face_analysis
        user.simple_analysis = simple_analysis
        
        db.commit()
        db.refresh(user)
        return user.to_dict()
    finally:
        db.close()


def update_user_profile(
    username: str, 
    *, 
    new_username: str | None = None, 
    password: str | None = None, 
    photo_path: str | None = None, 
    photo_mime_type: str | None = None, 
    face_analysis: dict | None = None,
    simple_analysis: dict | None = None
) -> dict:
    """更新用户资料"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError("用户不存在")
        
        if new_username and new_username != username:
            existing = db.query(User).filter(User.username == new_username).first()
            if existing:
                raise ValueError("用户名已存在")
            user.username = new_username
        
        if password:
            user.password_hash = hash_password(password)
        if photo_path is not None:
            user.photo_path = photo_path
        if photo_mime_type is not None:
            user.photo_mime_type = photo_mime_type
        if face_analysis is not None:
            user.face_analysis = face_analysis
        if simple_analysis is not None:
            user.simple_analysis = simple_analysis
        
        db.commit()
        db.refresh(user)
        return user.to_dict()
    finally:
        db.close()


def get_user_photo_payload(username: str) -> dict | None:
    """获取用户照片数据"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        return {
            "photo_path": user.photo_path,
            "photo_mime_type": user.photo_mime_type,
            "face_analysis": user.face_analysis,
            "simple_analysis": user.simple_analysis
        }
    finally:
        db.close()
