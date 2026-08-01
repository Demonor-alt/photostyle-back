"""独立生成与导入 Semantic Anchor Library 锚点的脚本。""" 

# 整体流程：先生成，再人工确认，最后导入 Milvus。
# 1. generate：调用模型生成锚点，保存到 scripts 本地 JSON 文件。python scripts\init_semantic_anchor.py generate
# 2. 人工确认/修改 JSON 文件。
# 3. import：从确认后的 JSON 文件加载锚点并写入 Milvus。python scripts\init_semantic_anchor.py import
from __future__ import annotations  # 保持类型和语法兼容性。

import argparse  # 用于解析命令行参数。
import json  # 用于读写 JSON 文件与解析模型输出。
import logging  # 用于脚本日志输出。
import os  # 用于读取环境变量。
import sys  # 用于把后端根目录加入模块搜索路径。
from datetime import datetime, timezone  # 用于记录带时区的生成时间。
from pathlib import Path  # 用于处理文件路径。
from typing import Any  # 用于标注任意类型。

import dashscope  # 用于调用通义千问等大模型接口。
import yaml  # 用于读取语义轴配置文件。
from dashscope import Generation  # 用于发起文本生成请求。
from dotenv import load_dotenv  # 用于脚本独立运行时加载 back/.env。
from langchain_core.output_parsers import PydanticOutputParser  # 用于清洗 LLM 输出并解析为 Pydantic 模型。
from pydantic import BaseModel, Field, RootModel  # 用于定义 LLM 输出结构并做字段映射。
from app.config.constants import QWEN_SEMANTIC_ANCHOR_MODEL # 引入语义锚点生成模型名称

# 允许从任意目录直接运行脚本时，也能导入 app 包并读取 back/.env。
BACKEND_ROOT = Path(__file__).resolve().parents[1]  # 定位后端根目录，便于拼接配置与输出文件路径。
if str(BACKEND_ROOT) not in sys.path:  # 避免重复插入模块搜索路径。
    sys.path.insert(0, str(BACKEND_ROOT))  # 确保 from app... 能解析到 back/app。
load_dotenv(BACKEND_ROOT / ".env")  # 显式加载后端 .env，不依赖当前工作目录。
DEFAULT_CONFIG_PATH = BACKEND_ROOT / "scripts" / "semantic_axes.yaml"  # 默认语义轴配置文件路径。
DEFAULT_OUTPUT_PATH = BACKEND_ROOT / "scripts" / "semantic_anchors.generated.json"  # 默认生成结果保存路径。
DEFAULT_SAMPLES_PER_AXIS = 15  # 每个语义轴默认生成的样本数量。
REQUIRED_EXPRESSION_TYPES = ["用户喜欢表达", "用户拒绝表达", "口语表达", "隐含表达", "场景表达"]  # 约束模型输出的表达类型集合。

logger = logging.getLogger("init_semantic_anchor")  # 创建脚本专用日志器。
dashscope.base_http_api_url = os.getenv("DASHSCOPE_API_URL") # 指定 DashScope API 地址。



class GeneratedAnchor(BaseModel):
    """LLM 生成的单条语义锚点结构。"""  # 通过 Pydantic 约束并承接模型输出字段。

    text: str = Field(description="用户表达文本")  # 用户自然语言表达内容。
    axis_name: str = Field(description="语义轴名称")  # 当前锚点所属语义轴。
    value: float = Field(description="-1 到 1 之间的语义轴取值")  # LLM 输出的原始轴值。
    category: str = Field(description="表达类型分类")  # 表达所属类型。


class GeneratedAnchorList(RootModel[list[GeneratedAnchor]]):
    """LLM 生成的语义锚点数组结构。"""  # 使用 RootModel 让 JSON 数组直接映射为 Pydantic 模型。


ANCHOR_OUTPUT_PARSER = PydanticOutputParser(pydantic_object=GeneratedAnchorList)  # 复用 LangChain 解析器完成清洗与模型映射。

def setup_logging() -> None:
    """初始化脚本日志格式。"""  # 配置全局日志输出样式。
    logging.basicConfig(  # 初始化 logging 基础配置。
        level=os.getenv("LOG_LEVEL", "INFO").upper(),  # 从环境变量读取日志级别，默认 INFO。
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  # 设置日志显示格式。
    )  # 结束日志基础配置。


def load_semantic_axes(config_path: Path) -> list[dict[str, str]]:
    """读取 semantic_axes.yaml，脚本不写死任何 axis。"""  # 读取并标准化语义轴配置。
    if not config_path.exists():  # 判断配置文件是否存在。
        raise FileNotFoundError(f"语义轴配置文件不存在: {config_path}")  # 文件不存在时直接报错。

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}  # 读取 YAML 内容并转换为 Python 对象。
    axes = payload.get("semantic_axes", []) if isinstance(payload, dict) else []  # 提取 semantic_axes 列表。

    if not isinstance(axes, list) or not axes:  # 校验语义轴列表是否有效。
        raise ValueError("semantic_axes.yaml 必须包含非空 semantic_axes 列表")  # 配置格式不合法时抛错。

    normalized: list[dict[str, str]] = []  # 创建标准化后的语义轴列表。
    for item in axes:  # 遍历每个语义轴配置项。
        if not isinstance(item, dict):  # 判断单个配置项是否为对象。
            raise ValueError("semantic_axes.yaml 中每个语义轴配置都必须是对象")  # 格式错误时抛出异常。
        axis_name = str(item.get("axis_name", "")).strip()  # 读取并清洗 axis_name。
        if not axis_name:  # 判断 axis_name 是否为空。
            raise ValueError("semantic_axes.yaml 中存在缺少 axis_name 的配置项")  # axis_name 缺失时抛出异常。
        normalized.append(  # 将标准化后的轴配置加入结果列表。
            {  # 构造标准化字典。
                "axis_name": axis_name,  # 保存轴名称。
                "label": str(item.get("label", axis_name)).strip() or axis_name,  # 保存标签，缺省时回退到 axis_name。
                "description": str(item.get("description", "")).strip(),  # 保存描述信息。
            }  # 字典结束。
        )  # 结束追加操作。
    return normalized  # 返回标准化后的语义轴列表。


def generate_axis_anchors(axis: dict[str, str]) -> list[dict[str, Any]]:
    """调用 LLM 为单个语义轴生成语义锚点样本。"""  # 为某个语义轴生成本地候选锚点。
    api_key = os.getenv("DASHSCOPE_API_KEY")  # 读取 DashScope API Key。
    if not api_key:  # 判断 API Key 是否配置。
        raise ValueError("未配置 DASHSCOPE_API_KEY，无法生成 Semantic Anchor Library 锚点")  # 未配置时停止执行。

    axis_name = axis["axis_name"]  # 取出语义轴名称。
    label = axis.get("label", axis_name)  # 取出语义轴标签。
    description = axis.get("description", "")  # 取出语义轴描述。
    prompt = {  # 组装给模型的提示词结构。
        "task": "为全局 Semantic Anchor Library 生成中文用户表达语义锚点。",  # 说明任务目标。
        "axis": {"axis_name": axis_name, "label": label, "description": description},  # 说明当前语义轴信息。
        "requirements": {  # 说明生成要求。
            "count": DEFAULT_SAMPLES_PER_AXIS,  # 每个轴的数量。
            "expression_types": REQUIRED_EXPRESSION_TYPES,  # 约束可用的表达类型。
            "value_range": "-1 到 1，负数表示拒绝/降低该语义轴，正数表示喜欢/增强该语义轴，0 表示中性或不明显。",  # 约束数值语义。
            "output": "只输出 JSON 数组，不要 Markdown，不要解释。每项字段必须包含 text、axis_name、value、category。",  # 强制模型输出格式。
            "category_hint": "category 必须从 expression_types 中选择。",  # 提供类别和方向提示。
            "format_instructions": ANCHOR_OUTPUT_PARSER.get_format_instructions(),  # 注入 LangChain 解析器生成的 Pydantic 格式说明。
        },  # requirements 结束。
        "example": {"text": "我不喜欢网红浓妆", "axis_name": "makeup_intensity", "value": -0.6, "category": "用户拒绝表达"},  # 给模型一个参考示例。
    }  # prompt 构造结束。
    logger.info("开始生成语义锚点 axis=%s", axis_name,)  # 记录生成开始日志。
    response = Generation.call(  # 调用大模型生成接口。
        api_key=api_key,  # 传入 API Key。
        model=QWEN_SEMANTIC_ANCHOR_MODEL,  # 指定模型名称，默认 qwen3.7-max。
        messages=[  # 构造对话消息列表。
            {"role": "system", "content": "你是语义检索知识库初始化助手。"},  # 系统提示，强调输出结果将由解析器接管。
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},  # 用户提示，传入 prompt JSON。
        ],  # 消息列表结束。
        result_format="message",  # 指定返回格式为 message。
    )  # 接口调用结束。
    raw_text = response.output.choices[0].message.content  # 提取模型返回文本。
    generated = _parse_generated_anchors(raw_text)  # 使用 LangChain Output Parser 解析为 Pydantic 模型。

    anchors: list[dict[str, Any]] = []  # 保存过滤后的锚点。
    used_texts: set[str] = set()  # 用于去重文本内容。
    for item in generated:  # 遍历模型生成的候选项。
        normalized = _normalize_anchor(item, axis_name, fallback_category="LLM生成表达")  # 标准化锚点。
        if normalized is None or normalized["text"] in used_texts:  # 过滤空项和重复项。
            continue  # 跳过无效数据。
        used_texts.add(normalized["text"])  # 记录已使用文本。
        anchors.append(normalized)  # 保存有效锚点。

    if len(anchors) < DEFAULT_SAMPLES_PER_AXIS:  # 判断生成数量是否达标。
        raise ValueError(f"axis={axis_name} 生成样本不足，期望 {DEFAULT_SAMPLES_PER_AXIS} 条，实际 {len(anchors)} 条")  # 数量不足时抛错。
    logger.info("语义锚点生成完成 axis=%s count=%s", axis_name, len(anchors))  # 记录生成完成日志。
    return anchors[:DEFAULT_SAMPLES_PER_AXIS]  # 返回限定数量的锚点。

def _parse_generated_anchors(raw_text: str) -> list[dict[str, Any]]:
    """使用 LangChain Output Parser 解析 LLM 返回的锚点数组。"""  # 由 LangChain 负责清洗文本、提取 JSON 并映射到 Pydantic 模型。
    try:  # 尝试通过 LangChain 内置解析器处理模型输出。
        parsed = ANCHOR_OUTPUT_PARSER.parse(raw_text)  # 解析器会自动处理常见 Markdown 包裹和 JSON 提取。
    except Exception as exc:  # 将解析异常转换为更贴近脚本语义的错误。
        raise ValueError(f"LLM 返回内容无法解析为语义锚点 JSON 数组: {exc}") from exc  # 保留原始异常便于排查。

    return [anchor.model_dump() for anchor in parsed.root]  # 将 Pydantic 模型转换为后续规范化流程使用的字典。


def _normalize_axis_value(value: Any) -> float:
    """将 LLM 生成的 value 规范到 -1 到 1。"""  # 将模型数值限制在合法区间内。
    try:  # 尝试把输入转换成浮点数。
        number = float(value)  # 将值转换为浮点数。
    except Exception:  # 如果转换失败则使用默认值。
        return 0.0  # 转换失败时返回中性值。
    if number < -1:  # 判断是否小于最小值。
        return -1.0  # 小于最小值时截断到 -1。
    if number > 1:  # 判断是否大于最大值。
        return 1.0  # 大于最大值时截断到 1。
    return round(number, 3)  # 保留三位小数并返回。


def _normalize_anchor(anchor: dict[str, Any], axis_name: str, fallback_category: str) -> dict[str, Any] | None:
    """规范单条语义锚点，过滤结构异常的数据。"""  # 清洗单条锚点并统一字段格式。
    text = str(anchor.get("text", "")).strip()  # 读取锚点文本并去空白。
    if not text:  # 判断文本是否为空。
        return None  # 空文本直接丢弃。

    generated_axis_name = str(anchor.get("axis_name", axis_name)).strip() or axis_name  # 读取模型返回的 axis_name。
    if generated_axis_name != axis_name:  # 如果模型返回的 axis_name 与当前轴不一致。
        generated_axis_name = axis_name  # 强制修正为当前轴名称。

    category = str(anchor.get("category", fallback_category)).strip() or fallback_category  # 读取类别并设定兜底值。
    return {  # 返回标准化后的锚点对象。
        "text": text,  # 保存文本内容。
        "axis_name": generated_axis_name,  # 保存轴名称。
        "axis_value": _normalize_axis_value(anchor.get("value", anchor.get("axis_value", 0))),  # 保存标准化后的轴值。
        "category": category,  # 保存类别。
    }  # 字典结束。

def generate_anchor_file(config_path: Path) -> None:
    """生成锚点文件到 scripts 本地，等待人工确认后再导入 Milvus。"""  # 将所有轴的锚点写入本地文件。
    axes = load_semantic_axes(config_path)  # 读取语义轴配置。
    logger.info("读取语义轴配置完成 path=%s axis_count=%s", config_path, len(axes))  # 记录配置读取结果。

    anchors: list[dict[str, Any]] = []  # 创建总锚点列表。
    for axis in axes:  # 遍历每个语义轴。
        anchors.extend(generate_axis_anchors(axis))  # 追加当前轴生成的锚点。

    payload = {  # 组装输出文件内容。
        "generated_at": datetime.now(timezone.utc).isoformat(),  # 记录生成时间。
        "config_path": str(config_path),  # 记录配置文件路径。
        "samples_per_axis": DEFAULT_SAMPLES_PER_AXIS,  # 记录每轴样本数。
        "anchor_count": len(anchors),  # 记录锚点总数。
        "anchors": anchors,  # 记录锚点列表。
    }  # payload 结束。
    DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)  # 确保输出目录存在。
    DEFAULT_OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")  # 将锚点写入 JSON 文件。
    logger.info("锚点已保存到本地文件 path=%s count=%s，请人工确认后再执行 import", DEFAULT_OUTPUT_PATH, len(anchors))  # 提示用户进行人工确认。


def load_anchor_file(anchor_file: Path) -> list[dict[str, Any]]:
    """读取人工确认后的本地锚点文件。"""  # 从本地 JSON 文件加载待导入锚点。
    if not anchor_file.exists():  # 判断输入文件是否存在。
        raise FileNotFoundError(f"锚点文件不存在: {anchor_file}")  # 文件不存在时抛错。

    payload = json.loads(anchor_file.read_text(encoding="utf-8"))  # 读取并解析 JSON 文件。
    anchors = payload.get("anchors") if isinstance(payload, dict) else payload  # 兼容对象包裹形式和数组形式。
    if not isinstance(anchors, list):  # 判断锚点容器是否为列表。
        raise ValueError("锚点文件必须是 JSON 数组，或包含 anchors 数组字段的 JSON 对象")  # 格式不对时抛错。

    normalized: list[dict[str, Any]] = []  # 创建标准化列表。
    for index, item in enumerate(anchors, start=1):  # 逐条读取锚点并保留序号。
        if not isinstance(item, dict):  # 判断每条锚点是否为对象。
            raise ValueError(f"第 {index} 条锚点不是对象")  # 不是对象时抛错。
        axis_name = str(item.get("axis_name", "")).strip()  # 读取 axis_name。
        if not axis_name:  # 判断 axis_name 是否为空。
            raise ValueError(f"第 {index} 条锚点缺少 axis_name")  # 缺少 axis_name 时抛错。
        anchor = _normalize_anchor(item, axis_name, fallback_category="人工确认表达")  # 标准化锚点内容。
        if anchor is None:  # 判断文本是否缺失。
            raise ValueError(f"第 {index} 条锚点缺少 text")  # 缺少 text 时抛错。
        normalized.append(anchor)  # 将标准化后的锚点加入列表。
    return normalized  # 返回可导入的锚点列表。


def import_anchor_file(anchor_file: Path) -> None:
    """从本地锚点文件一次性导入 Milvus。"""  # 将确认后的本地文件写入 Milvus。
    from app.rag.semantic_anchor_milvus_service import insert_anchors  # 延迟导入，避免生成阶段依赖 Milvus 连接。

    anchors = load_anchor_file(anchor_file)  # 读取本地锚点文件。
    for anchor in anchors:  # 遍历每条锚点，仅输出预览日志。
        logger.info(  # 输出即将写入的锚点日志。
            "准备写入锚点 axis=%s value=%s category=%s text=%s",  # 日志模板。
            anchor["axis_name"],  # 语义轴名称。
            anchor["axis_value"],  # 轴值。
            anchor["category"],  # 类别。
            anchor["text"],  # 文本内容。
        )  # 日志调用结束。
    insert_anchors(anchors)  # 一次性批量写入整份锚点文件。
    logger.info("锚点导入完成 file=%s total=%s", anchor_file, len(anchors))  # 输出导入完成日志。


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""  # 处理 generate 和 import 两个子命令。
    parser = argparse.ArgumentParser(description="独立生成或导入 semantic_axis_library 全局语义锚点")  # 创建命令行解析器。
    subparsers = parser.add_subparsers(dest="command", required=True)  # 创建子命令解析器。

    generate_parser = subparsers.add_parser("generate", help="调用模型生成锚点并保存到 scripts 本地 JSON 文件")  # 定义 generate 子命令。
    generate_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="semantic_axes.yaml 配置文件路径")  # 配置文件参数。

    import_parser = subparsers.add_parser("import", help="从人工确认后的本地 JSON 文件导入 Milvus")  # 定义 import 子命令。
    import_parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_PATH, help="人工确认后的锚点 JSON 文件路径")  # 输入文件参数。

    return parser.parse_args()  # 返回解析结果。


def main() -> None:
    """脚本入口。"""  # 脚本主入口函数。
    setup_logging()  # 初始化日志系统。
    args = parse_args()  # 解析命令行参数。

    if args.command == "generate":  # 判断是否执行生成流程。
        generate_anchor_file(args.config)  # 调用生成函数。
        return  # 生成完成后退出。

    if args.command == "import":  # 判断是否执行导入流程。
        import_anchor_file(args.input)  # 调用导入函数。
        return  # 导入完成后退出。

    raise ValueError(f"不支持的命令: {args.command}")  # 理论上不会执行到这里。


if __name__ == "__main__":  # 判断当前文件是否作为主程序运行。
    main()  # 执行主入口函数。
