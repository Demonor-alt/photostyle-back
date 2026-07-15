def evaluate_history(record: dict) -> dict:  # 根据历史记录做简单评价
    return {  # 返回评价结果
        "is_positive": record.get("liked", False),  # 是否喜欢结果
        "need_adjustment": not record.get("shot_success", False),  # 是否需要调整
    }  # 评价结果结束
