"""
合并原始记录与 API 返回数据，生成 diff 报告
"""
from typing import Dict, Any, Optional, List


# 只补全这些字段，不覆盖已有值
FILLABLE_FIELDS = [
    "authors", "year", "journal_name", "secondary_title",
    "volume", "start_page", "end_page", "pages", "doi", "url",
]


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def merge_record(original: Dict, found: Dict) -> Dict:
    """
    将 found 中的字段补入 original，只填空字段，不覆盖已有内容
    """
    merged = dict(original)

    # 检查目标是否已有任何形式的页码信息
    has_any_pages = not _is_empty(merged.get("start_page")) or 
                    not _is_empty(merged.get("end_page")) or 
                    not _is_empty(merged.get("pages"))

    for key, value in found.items():
        # 如果已经存在某个类型的页码了，就跳过所有其他类型的页码的补全
        if has_any_pages and key in ["start_page", "end_page", "pages"]:
            continue
            
        if key in FILLABLE_FIELDS and _is_empty(merged.get(key)):
            merged[key] = value
            
    return merged


def build_diff_row(
    rec_idx: int,
    original: Dict,
    found: Optional[Dict],
    missing_fields: List[str],
    status: str,
) -> Dict:
    title = (original.get("title") or
             original.get("primary_title") or
             original.get("translated_title") or "（无标题）")

    row = {
        "序号": rec_idx + 1,
        "标题": title[:80],
        "缺失字段": ", ".join(missing_fields),
        "状态": status,
    }

    if found:
        row["补全_作者"] = "; ".join(found.get("authors", [])) if found.get("authors") else ""
        row["补全_年份"] = found.get("year", "")
        row["补全_期刊会议"] = found.get("journal_name", "")
        row["补全_卷号"] = found.get("volume", "")
        row["补全_页码"] = f"{found.get('start_page','')}-{found.get('end_page','')}".strip("-")
        row["补全_DOI"] = found.get("doi", "")
        row["补全_URL"] = found.get("url", "")
    else:
        for col in ["补全_作者", "补全_年份", "补全_期刊会议", "补全_卷号", "补全_页码", "补全_DOI", "补全_URL"]:
            row[col] = ""

    return row
