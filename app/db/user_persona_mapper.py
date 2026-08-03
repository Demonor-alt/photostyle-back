"""用户人格画像 CRUD 操作封装。"""
from app.db.database import SessionLocal
from app.db.models.user_persona_model import UserPersonaModel, default_semantic_axes
from app.schemas.dto.user_persona_dto import UpsertUserPersonaRequest
from app.schemas.orm.user_persona import UserPersona
from app.utils.to_json import to_jsonable


def get_or_create_user_persona(db, user_id: int) -> UserPersonaModel:
    """获取用户人格画像，不存在时创建默认画像。"""
    persona = db.query(UserPersonaModel).filter(UserPersonaModel.user_id == user_id).first()
    if persona:
        return persona

    persona = UserPersonaModel(
        user_id=user_id,
        semantic_axes=default_semantic_axes(),
    )
    db.add(persona)
    db.flush()
    return persona


def get_user_persona_by_id(user_id: int) -> UserPersona | None:
    """根据用户 ID 获取用户画像。"""
    db = SessionLocal()
    try:
        persona = db.query(UserPersonaModel).filter(UserPersonaModel.user_id == int(user_id)).first()
        if not persona:
            return None
        return UserPersona.model_validate(persona)
    finally:
        db.close()


def update_user_persona_by_id(request: UpsertUserPersonaRequest) -> UserPersona:
    """根据用户 ID 更新或创建用户人格画像。"""
    db = SessionLocal()
    try:
        persona = get_or_create_user_persona(db, int(request.user_id))
        persona.semantic_axes = to_jsonable(request.semantic_axes)
        db.commit()
        db.refresh(persona)
        return UserPersona.model_validate(persona)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
