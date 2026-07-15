def build_query(structured_input: dict) -> str:  # 基于结构化输入生成检索查询
    parts = [structured_input.get("style"), structured_input.get("location"), structured_input.get("time"), structured_input.get("weather")]  # 组合检索条件
    filtered = [item for item in parts if item]  # 过滤空值
    return " | ".join(filtered)  # 拼接为检索语句
