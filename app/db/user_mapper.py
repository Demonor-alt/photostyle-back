"""用户服务层 - 使用 ORM"""
import os
from passlib.context import CryptContext
from app.db.models.user import User as UserModel
from app.db.database import SessionLocal
from app.schemas.dto.user_dto import UpsertUserPhotoRequest, UpdateUserProfileRequest
from app.schemas.orm.user import User

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


def ensure_user(username: str, password: str | None = None) -> User:
    """确保用户存在"""
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.username == username).first()
        if user:
            return User.model_validate(user)
        
        plain_password = password or _default_password()
        new_user = UserModel(
            username=username,
            password_hash=hash_password(plain_password)
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return User.model_validate(new_user)
    finally:
        db.close()


def login_user(username: str, password: str) -> User:
    """登录校验"""
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.username == username).first()
        if not user:
            raise ValueError("用户名或密码错误")
        
        try:
            if not verify_password(password, user.password_hash):
                raise ValueError("用户名或密码错误")
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        
        return User.model_validate(user)
    finally:
        db.close()


def get_user_profile_by_id(user_id: int) -> User:
    """根据用户ID获取用户资料"""
    db = SessionLocal()  # 创建数据库会话
    try:  # 开始查询
        user = db.query(UserModel).filter(UserModel.id == user_id).first()  # 按ID查找用户
        if not user:  # 如果用户不存在
            raise ValueError("用户不存在")  # 直接抛出异常
        return User.model_validate(user)  # 返回用户Schema
    finally:  # 无论如何都关闭会话
        db.close()  # 关闭数据库会话


def upsert_user_photo_by_id(payload: UpsertUserPhotoRequest) -> User:
    """根据用户ID保存或更新用户照片"""
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == payload.user_id).first()
        if not user:
            raise ValueError("用户不存在")
        
        user.photo_path = payload.photo_path
        user.photo_mime_type = payload.photo_mime_type
        user.face_analysis = payload.face_analysis
        user.simple_analysis = payload.simple_analysis
        
        db.commit()
        db.refresh(user)
        return User.model_validate(user)
    finally:
        db.close()
        

def update_user_profile_by_id(payload: UpdateUserProfileRequest) -> User:
    """根据用户ID更新用户资料"""
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == payload.user_id).first()
        if not user:
            raise ValueError("用户不存在")
        
        original_username = user.username
        if payload.new_username and payload.new_username != original_username:
            user.username = payload.new_username
        if payload.password:
            user.password_hash = hash_password(payload.password)
        if payload.photo_path is not None:
            user.photo_path = payload.photo_path
        if payload.photo_mime_type is not None:
            user.photo_mime_type = payload.photo_mime_type
        if payload.face_analysis is not None:
            user.face_analysis = payload.face_analysis
        if payload.simple_analysis is not None:
            user.simple_analysis = payload.simple_analysis
        
        db.commit()
        db.refresh(user)
        return User.model_validate(user)
    finally:
        db.close()
