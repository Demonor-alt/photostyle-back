import json  # 引入JSON模块用于读取种子数据
from pathlib import Path  # 引入Path用于处理文件路径


def load_seed_data() -> list:  # 加载RAG种子数据
    data_path = Path(__file__).resolve().parents[2] / "rag_seed_data.json"  # 定位种子数据文件路径
    with data_path.open("r", encoding="utf-8") as file:  # 以UTF-8打开文件
        return json.load(file)  # 读取并返回JSON内容
