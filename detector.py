"""
检测 RIS 记录中哪些字段缺失
CS/AI 领域关注的核心字段：
  - 作者、年份、标题（必须）
  - 期刊/会议名、卷号、页码（常缺）
  - DOI（强烈建议有）
"""
from typing import List, Tuple, Dict, Any

# RIS 字段名映射（rispy 使用的 key）
REQUIRED_FIELDS = {
    "authors":        "作者",
    "year":           "年份",
    "title":          "标题",
}

IMPORTANT_FIELDS = {
    "journal_name":   "期刊/会议名",
    "secondary_title":"期刊/会议名(备用)",
    "volume":         "卷号",
    "start_page":     "起始页",
    "end_page":       "结束页",
    "doi":            "DOI",
}

# 有任意一个就算"有标题"
TITLE_KEYS = ["title", "primary_title", "translated_title"]


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def _has_journal(record: Dict) -> bool:
    """期刊名和会议名用不同 key，任一有值即算完整"""
    for key in ("journal_name", "secondary_title", "alternate_title1",
                "alternate_title2", "publisher"):
        if not _is_empty(record.get(key)):
            return True
    return False


def _has_pages(record: Dict) -> bool:
    return (not _is_empty(record.get("start_page")) or
            not _is_empty(record.get("pages")))


def get_missing_fields(record: Dict) -> List[str]:
    missing = []

    # 必须字段
    for key, label in REQUIRED_FIELDS.items():
        if _is_empty(record.get(key)):
            missing.append(key)

    # 期刊/会议
    if not _has_journal(record):
        missing.append("journal_name")

    # 卷号
    if _is_empty(record.get("volume")) and _is_empty(record.get("number")):
        missing.append("volume")

    # 页码
    if not _has_pages(record):
        missing.append("start_page")

    # DOI
    if _is_empty(record.get("doi")):
        missing.append("doi")

    return missing


def find_incomplete(
    records: List[Dict[str, Any]]
) -> List[Tuple[int, Dict, List[str]]]:
    """
    返回 [(index_in_list, record, [missing_field_keys]), ...]
    只有标题存在才处理（否则没法搜索）
    """
    result = []
    for i, rec in enumerate(records):
        has_title = any(not _is_empty(rec.get(k)) for k in TITLE_KEYS)
        if not has_title:
            continue
        missing = get_missing_fields(rec)
        if missing:
            result.append((i, rec, missing))
    return result
