from app.schemas.base import BaseSchema  # 引入公共Schema基类
from typing import List, Optional  # 引入类型标注用于描述字段结构

from app.schemas.dto.history_dto import HistoryRecord

# /suggest 接口数据
class SuggestApiData(BaseSchema):
    suggestions: Optional[str] = None
    outfit: Optional[List[str]] = None
    makeup: Optional[List[str]] = None
    poses: Optional[List[str]] = None
    summary: Optional[str] = None
    history: Optional[dict] = None

# /history的get接口数据
class HistoryListResponse(BaseSchema):
    items: List[HistoryRecord]

# /db/status 接口数据
class DatabaseStatusResponse(BaseSchema):
    connected: bool  # 是否已连接
    message: str  # 状态信息