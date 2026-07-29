"""用户画像更新服务。"""  # 模块说明：负责把分析结果写入用户画像。
from __future__ import annotations  # 启用前向引用类型注解。

from app.utils.runtime import logger
from typing import Any  # 用于表示任意类型。

from app.db.database import SessionLocal  # 引入数据库会话工厂。
from app.models.user_profile import DEFAULT_SEMANTIC_AXES, UserProfile, default_semantic_axes  # 引入用户画像模型与默认语义轴。

# 评分只能影响指定语义轴，避免评分被错误扩散到无关画像维度。  # 控制评分影响范围。
RATING_AXIS_SCOPE = {  # 定义评分字段到语义轴的约束映射。
    "makeup_rating": {"makeup_intensity"},  # 妆容评分影响妆容强度。
    "outfit_rating": {"color_saturation", "accessory_level"},  # 穿搭评分影响色彩饱和度和配饰程度。
    "pose_rating": {"pose_staged", "body_openness"},  # 姿势评分影响摆拍感和身体开放度。
}  # 映射定义结束。

# 评分字段和输出字段的对应关系，用于构建成功模式和避雷模式。  # 记录输出模式字段映射。
RATING_OUTPUT_SCOPE = {  # 定义评分字段对应的输出字段。
    "makeup_rating": ["makeup"],  # 妆容评分对应 makeup 输出。
    "outfit_rating": ["color"],  # 穿搭评分对应 color 输出。
    "pose_rating": ["pose"],  # 姿势评分对应 pose 输出。
}  # 映射定义结束。


def _clamp(value: Any, min_value: float, max_value: float, default: float = 0.0) -> float:  # 将数值限制在区间内。
    """将数值限制在指定区间内。"""  # 说明函数作用。
    try:  # 尝试把值转成浮点数。
        number = float(value)  # 执行转换。
    except Exception:  # 任何异常都用默认值。
        number = default  # 使用默认值。
    if number < min_value:  # 如果小于下限。
        return min_value  # 返回下限。
    if number > max_value:  # 如果大于上限。
        return max_value  # 返回上限。
    return round(number, 4)  # 保留 4 位小数。


def _normalize_score(value: Any) -> int | None:  # 规范评分值。
    """将评分规范为整数，无法解析时返回 None。"""  # 说明函数作用。
    if value is None:  # 如果值为空。
        return None  # 返回空。
    try:  # 尝试转换为整数。
        return int(value)  # 返回整数评分。
    except Exception:  # 转换失败。
        return None  # 返回空值。


def _normalize_patterns(value: Any) -> list[str]:  # 规范模式列表。
    """将模式列表规范为字符串列表。"""  # 说明函数作用。
    if not isinstance(value, list):  # 如果不是列表。
        return []  # 返回空列表。
    return [str(item).strip() for item in value if str(item).strip()]  # 清理空白并过滤空字符串。


def _append_unique(existing: Any, additions: list[str], max_items: int = 100) -> list[str]:  # 追加并去重。
    """追加模式并去重，保留原有顺序。"""  # 说明会保持顺序。
    result = _normalize_patterns(existing)  # 先规范已有内容。
    seen = set(result)  # 用集合记录已存在项。
    for item in additions:  # 遍历新增项。
        item = str(item).strip()  # 清理字符串。
        if item and item not in seen:  # 如果是新内容且非空。
            result.append(item)  # 追加到结果中。
            seen.add(item)  # 记录到集合。
    return result[-max_items:]  # 仅保留最后最多 max_items 条。


def _get_or_create_profile(db, user_id: int) -> UserProfile:  # 获取或创建用户画像。
    """获取用户画像，不存在时创建默认画像。"""  # 说明函数行为。
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()  # 查询已有画像。
    if profile:  # 如果找到了画像。
        return profile  # 直接返回。
    profile = UserProfile(  # 构造新画像对象。
        user_id=user_id,  # 设置用户 ID。
        semantic_axes=default_semantic_axes(),  # 初始化默认语义轴。
        success_patterns=[],  # 初始化成功模式为空。
        avoid_patterns=[],  # 初始化避雷模式为空。
    )  # 新画像对象创建结束。
    db.add(profile)  # 添加到会话。
    db.flush()  # 刷新以便获取数据库状态。
    return profile  # 返回新建画像。


def _score_all_success(history_scores: dict[str, Any]) -> bool:  # 判断是否全部高分。
    """判断三项评分是否均达到成功模式标准。"""  # 说明函数用途。
    return all(_normalize_score(history_scores.get(key)) is not None and _normalize_score(history_scores.get(key)) >= 4 for key in RATING_AXIS_SCOPE)  # 三项评分都至少为 4。


def _axis_allowed_by_scores(axis_name: str, history_scores: dict[str, Any]) -> bool:  # 检查轴是否允许更新。
    """根据评分字段限制 axis_update 的作用范围。"""  # 说明限制逻辑。
    related_rating_keys = [rating_key for rating_key, axes in RATING_AXIS_SCOPE.items() if axis_name in axes]  # 找出关联评分字段。
    if not related_rating_keys:  # 如果该轴不受评分约束。
        return True  # 允许更新。
    return any(_normalize_score(history_scores.get(rating_key)) is not None for rating_key in related_rating_keys)  # 只要有关联评分存在即可允许。


def _normalize_axis_updates(axis_updates: Any, history_scores: dict[str, Any]) -> list[dict[str, Any]]:  # 规范轴更新列表。
    """过滤并规范 axis_updates，确保只更新已知语义轴。"""  # 说明函数用途。
    if not isinstance(axis_updates, list):  # 如果不是列表。
        return []  # 返回空列表。

    normalized: list[dict[str, Any]] = []  # 初始化规范化结果。
    valid_axes = set(DEFAULT_SEMANTIC_AXES.keys())  # 取所有合法语义轴。
    for item in axis_updates:  # 遍历每条更新。
        if not isinstance(item, dict):  # 非字典项忽略。
            continue  # 跳过。
        axis_name = str(item.get("axis_name", "")).strip()  # 读取轴名称并清理。
        if axis_name not in valid_axes:  # 如果不是合法轴。
            continue  # 跳过。
        if not _axis_allowed_by_scores(axis_name, history_scores):  # 如果该轴不允许被当前评分影响。
            logger.info("user_profile.axis_update.skipped axis=%s reason=rating_scope_missing", axis_name)  # 记录跳过原因。
            continue  # 跳过。
        normalized.append(  # 追加规范结果。
            {  # 单条规范记录。
                "axis_name": axis_name,  # 轴名称。
                "value": _clamp(item.get("value"), -1.0, 1.0),  # 轴值限制在 -1 到 1。
                "confidence": _clamp(item.get("confidence"), 0.0, 1.0),  # 置信度限制在 0 到 1。
                "reason": str(item.get("reason", "")).strip(),  # 原因文本清理。
            }  # 单条记录结束。
        )  # 追加结束。
    return normalized  # 返回规范化更新列表。


def _apply_axis_updates(old_axes: Any, axis_updates: list[dict[str, Any]]) -> dict[str, float]:  # 应用语义轴更新。
    """按 new = old*(1-confidence) + value*confidence 更新语义轴。"""  # 说明更新公式。
    axes = default_semantic_axes()  # 先加载默认语义轴。
    if isinstance(old_axes, dict):  # 如果已有旧画像。
        for axis_name in axes:  # 遍历所有轴。
            axes[axis_name] = _clamp(old_axes.get(axis_name, axes[axis_name]), -1.0, 1.0)  # 用旧值覆盖默认值并限制范围。

    for update in axis_updates:  # 遍历每个更新项。
        axis_name = update["axis_name"]  # 读取轴名称。
        confidence = update["confidence"]  # 读取置信度。
        old_value = _clamp(axes.get(axis_name), -1.0, 1.0)  # 读取当前值。
        update_value = update["value"]  # 读取更新值。
        axes[axis_name] = _clamp(old_value * (1 - confidence) + update_value * confidence, -1.0, 1.0)  # 按权重融合新旧值。
        logger.info(  # 记录轴更新日志。
            "user_profile.axis_updated axis=%s old=%s update=%s confidence=%s new=%s",  # 日志模板。
            axis_name,  # 轴名称。
            old_value,  # 旧值。
            update_value,  # 更新值。
            confidence,  # 置信度。
            axes[axis_name],  # 新值。
        )  # 日志记录结束。
    return axes  # 返回更新后的语义轴。


def _pick_output_values(output_data: dict[str, Any], keys: list[str]) -> dict[str, Any]:  # 提取输出字段。
    """从输出结果中提取指定字段。"""  # 说明函数用途。
    return {key: output_data.get(key) for key in keys if output_data.get(key) is not None}  # 只保留非空字段。


def _build_base_pattern(input_data: dict[str, Any], output_data: dict[str, Any]) -> dict[str, Any]:  # 构建基础模式结构。
    """构建模式基础信息，只提取需要的输入输出字段。"""  # 说明只保留关键字段。
    return {  # 返回基础结构。
        "style": input_data.get("style"),  # 输入风格。
        "location": input_data.get("location"),  # 输入场景。
        "output": {  # 输出摘要。
            "color": output_data.get("color"),  # 输出颜色。
            "makeup": output_data.get("makeup"),  # 输出妆容。
            "pose": output_data.get("pose"),  # 输出姿势。
        },  # 输出摘要结束。
    }  # 基础结构结束。


def _build_success_patterns(input_data: dict[str, Any], output_data: dict[str, Any], history_scores: dict[str, Any]) -> list[str]:  # 构建成功模式。
    """三项评分均 >=4 时追加成功模式。"""  # 说明触发条件。
    if not _score_all_success(history_scores):  # 如果不是全高分。
        return []  # 不生成成功模式。
    pattern = _build_base_pattern(input_data, output_data)  # 构造基础模式。
    return [f"成功模式:{pattern}"]  # 返回成功模式文本。


def _build_low_score_avoid_patterns(input_data: dict[str, Any], output_data: dict[str, Any], history_scores: dict[str, Any]) -> list[str]:  # 构建低分避雷模式。
    """任意评分 <=2 时，根据低分项追加避雷模式。"""  # 说明触发条件。
    patterns: list[str] = []  # 初始化避雷模式列表。
    base = {"style": input_data.get("style"), "location": input_data.get("location")}  # 构造基础上下文。
    for rating_key, output_keys in RATING_OUTPUT_SCOPE.items():  # 遍历评分与输出映射。
        score = _normalize_score(history_scores.get(rating_key))  # 读取评分。
        if score is None or score > 2:  # 如果不是低分。
            continue  # 跳过。
        output_slice = _pick_output_values(output_data, output_keys)  # 提取相关输出字段。
        patterns.append(f"避雷模式:{rating_key}={score}, context={base}, output={output_slice}")  # 生成避雷模式文本。
    return patterns  # 返回避雷模式列表。


def update_user_profile(  # 更新用户画像主入口。
    *,  # 强制关键字参数。
    user_id: int,  # 用户 ID。
    axis_updates: list[dict[str, Any]] | None = None,  # 语义轴更新。
    history_scores: dict[str, Any] | None = None,  # 历史评分。
    history_profile: dict[str, Any] | None = None,  # 历史画像。
    input_data: dict[str, Any] | None = None,  # 输入数据。
    output_data: dict[str, Any] | None = None,  # 输出数据。
    avoid_patterns: list[str] | None = None,  # 避雷模式。
    success_patterns: list[str] | None = None,  # 成功模式。
) -> dict[str, Any]:  # 返回更新后的画像字典。
    """更新用户画像数据库记录，不处理 RabbitMQ，也不调用 LLM。"""  # 说明该函数只做落库。
    history_scores = history_scores or {}  # 确保历史评分是字典。
    input_data = input_data or {}  # 确保输入数据是字典。
    output_data = output_data or {}  # 确保输出数据是字典。
    history_profile = history_profile or {}  # 确保历史画像是字典。

    normalized_updates = _normalize_axis_updates(axis_updates or [], history_scores)  # 规范轴更新。
    llm_avoid_patterns = _normalize_patterns(avoid_patterns)  # 规范 LLM 传入的避雷模式。
    llm_success_patterns = _normalize_patterns(success_patterns)  # 规范 LLM 传入的成功模式。
    generated_success_patterns = _build_success_patterns(input_data, output_data, history_scores)  # 生成成功模式。
    generated_avoid_patterns = _build_low_score_avoid_patterns(input_data, output_data, history_scores)  # 生成避雷模式。

    db = SessionLocal()  # 创建数据库会话。
    try:  # 开始数据库操作。
        profile = _get_or_create_profile(db, int(user_id))  # 获取或创建用户画像。
        old_axes = profile.semantic_axes or history_profile.get("semantic_axes") or {}  # 选择旧语义轴数据来源。
        profile.semantic_axes = _apply_axis_updates(old_axes, normalized_updates)  # 应用轴更新。
        profile.success_patterns = _append_unique(  # 更新成功模式。
            profile.success_patterns,  # 现有成功模式。
            llm_success_patterns + generated_success_patterns,  # 合并新模式。
        )  # 成功模式更新结束。
        profile.avoid_patterns = _append_unique(  # 更新避雷模式。
            profile.avoid_patterns,  # 现有避雷模式。
            llm_avoid_patterns + generated_avoid_patterns,  # 合并新模式。
        )  # 避雷模式更新结束。
        db.commit()  # 提交事务。
        db.refresh(profile)  # 刷新对象状态。
        result = profile.to_dict()  # 转为字典结果。
        logger.info("user_profile.updated user_id=%s result=%s", user_id, result)  # 记录更新结果。
        return result  # 返回结果。
    except Exception:  # 捕获所有异常。
        db.rollback()  # 回滚事务。
        logger.exception("user_profile.update_failed user_id=%s", user_id)  # 记录异常日志。
        raise  # 继续向上抛出异常。
    finally:  # 无论成功失败都执行。
        db.close()  # 关闭数据库会话。


def update_user_profile_from_analysis(payload: dict[str, Any]) -> dict[str, Any]:  # 兼容分析结果字典入口。
    """兼容偏好分析结果字典的更新入口。"""  # 说明函数用途。
    return update_user_profile(  # 调用主更新函数。
        user_id=int(payload["user_id"]),  # 读取用户 ID。
        axis_updates=payload.get("axis_updates"),  # 读取轴更新。
        history_scores=payload.get("history_scores"),  # 读取历史评分。
        history_profile=payload.get("history_profile"),  # 读取历史画像。
        input_data=payload.get("input_data"),  # 读取输入数据。
        output_data=payload.get("output_data"),  # 读取输出数据。
        avoid_patterns=payload.get("avoid_patterns"),  # 读取避雷模式。
        success_patterns=payload.get("success_patterns"),  # 读取成功模式。
    )  # 返回更新结果。
