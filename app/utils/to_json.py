"""将Pydantic模型转换为JSON可序列化的格式"""
def to_jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    return value