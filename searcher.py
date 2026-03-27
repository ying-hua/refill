"""
CS/AI 专用 API 搜索器
优先级: Semantic Scholar → DBLP → arXiv → CrossRef
"""
import re
import time
import urllib.parse
from typing import Optional, Tuple, Dict, Any, List

import requests
from thefuzz import fuzz

HEADERS = {"User-Agent": "EndNoteFixer/1.0 (mailto:your@email.com)"}
TIMEOUT = 10


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def _clean_title(title: str) -> str:
    """去除 HTML 标签和多余空格"""
    title = re.sub(r"<[^>]+>", "", title)
    return " ".join(title.split())


def _similarity(a: str, b: str) -> float:
    return fuzz.token_sort_ratio(a.lower(), b.lower())


def _safe_get(url: str, params: dict = None) -> Optional[dict]:
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"   [请求错误] {e}")
    return None


# ──────────────────────────────────────────────
# Semantic Scholar（首选，CS/AI 覆盖最全）
# ──────────────────────────────────────────────

def _parse_semantic_scholar(item: dict) -> Dict[str, Any]:
    data = {}
    if item.get("authors"):
        data["authors"] = [a.get("name", "") for a in item["authors"]]
    if item.get("year"):
        data["year"] = str(item["year"])
    venue = item.get("venue") or item.get("journal", {}).get("name", "")
    if venue:
        data["journal_name"] = venue
    if item.get("volume"):
        data["volume"] = str(item["volume"])
    pages = item.get("pages") or ""
    if pages and "-" in pages:
        parts = pages.split("-")
        data["start_page"] = parts[0].strip()
        data["end_page"] = parts[-1].strip()
    elif pages:
        data["start_page"] = pages
    doi = item.get("externalIds", {}).get("DOI", "")
    if doi:
        data["doi"] = doi
    arxiv = item.get("externalIds", {}).get("ArXiv", "")
    if arxiv:
        data["url"] = f"https://arxiv.org/abs/{arxiv}"
    return data


def search_semantic_scholar(title: str, min_score: float) -> Optional[Tuple[str, float, Dict]]:
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": title,
        "limit": 3,
        "fields": "title,authors,year,venue,journal,volume,pages,externalIds",
    }
    data = _safe_get(url, params)
    if not data:
        return None
    for item in data.get("data", []):
        found_title = _clean_title(item.get("title", ""))
        score = _similarity(title, found_title)
        if score >= min_score:
            return ("SemanticScholar", score, _parse_semantic_scholar(item))
    return None


# ──────────────────────────────────────────────
# DBLP（CS 会议/期刊最权威）
# ──────────────────────────────────────────────

def _parse_dblp(hit: dict) -> Dict[str, Any]:
    info = hit.get("info", {})
    data = {}
    authors_raw = info.get("authors", {}).get("author", [])
    if isinstance(authors_raw, dict):
        authors_raw = [authors_raw]
    if authors_raw:
        data["authors"] = [a.get("text", "") for a in authors_raw]
    if info.get("year"):
        data["year"] = str(info["year"])
    venue = info.get("venue", "")
    if venue:
        data["journal_name"] = venue
    if info.get("volume"):
        data["volume"] = str(info["volume"])
    pages = info.get("pages", "")
    if pages and "-" in pages:
        parts = pages.split("-")
        data["start_page"] = parts[0].strip()
        data["end_page"] = parts[-1].strip()
    elif pages:
        data["start_page"] = pages
    doi = info.get("doi", "")
    if doi:
        data["doi"] = doi
    ee = info.get("ee", "")
    if isinstance(ee, list):
        ee = ee[0] if ee else ""
    if ee:
        data["url"] = ee
    return data


def search_dblp(title: str, min_score: float) -> Optional[Tuple[str, float, Dict]]:
    url = "https://dblp.org/search/publ/api"
    params = {"q": title, "format": "json", "h": 3}
    data = _safe_get(url, params)
    if not data:
        return None
    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    for hit in hits:
        found_title = _clean_title(hit.get("info", {}).get("title", ""))
        score = _similarity(title, found_title)
        if score >= min_score:
            return ("DBLP", score, _parse_dblp(hit))
    return None


# ──────────────────────────────────────────────
# arXiv（预印本，AI 领域必备）
# ──────────────────────────────────────────────

def _parse_arxiv(entry: dict) -> Dict[str, Any]:
    data = {}
    authors = entry.get("author", [])
    if isinstance(authors, dict):
        authors = [authors]
    if authors:
        data["authors"] = [a.get("name", "") for a in authors]
    published = entry.get("published", "")
    if published:
        data["year"] = published[:4]
    data["journal_name"] = "arXiv"
    arxiv_id = entry.get("id", "").split("/abs/")[-1]
    if arxiv_id:
        data["url"] = f"https://arxiv.org/abs/{arxiv_id}"
        data["doi"] = f"10.48550/arXiv.{arxiv_id}"
    return data


def search_arxiv(title: str, min_score: float) -> Optional[Tuple[str, float, Dict]]:
    import xml.etree.ElementTree as ET
    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"ti:{urllib.parse.quote(title)}",
        "max_results": 3,
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        root = ET.fromstring(r.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            found_title = _clean_title(entry.findtext("atom:title", "", ns))
            score = _similarity(title, found_title)
            if score >= min_score:
                entry_dict = {
                    "author": [{"name": a.findtext("atom:name", "", ns)}
                               for a in entry.findall("atom:author", ns)],
                    "published": entry.findtext("atom:published", "", ns),
                    "id": entry.findtext("atom:id", "", ns),
                }
                return ("arXiv", score, _parse_arxiv(entry_dict))
    except Exception as e:
        print(f"   [arXiv 错误] {e}")
    return None


# ──────────────────────────────────────────────
# CrossRef（兜底，通用）
# ──────────────────────────────────────────────

def _parse_crossref(item: dict) -> Dict[str, Any]:
    data = {}
    authors_raw = item.get("author", [])
    if authors_raw:
        data["authors"] = [
            f"{a.get('family', '')} {a.get('given', '')}".strip()
            for a in authors_raw
        ]
    date_parts = item.get("published", {}).get("date-parts", [[]])
    if date_parts and date_parts[0]:
        data["year"] = str(date_parts[0][0])
    container = item.get("container-title", [])
    if container:
        data["journal_name"] = container[0]
    if item.get("volume"):
        data["volume"] = str(item["volume"])
    page = item.get("page", "")
    if page and "-" in page:
        parts = page.split("-")
        data["start_page"] = parts[0].strip()
        data["end_page"] = parts[-1].strip()
    elif page:
        data["start_page"] = page
    if item.get("DOI"):
        data["doi"] = item["DOI"]
    return data


def search_crossref(title: str, min_score: float) -> Optional[Tuple[str, float, Dict]]:
    url = "https://api.crossref.org/works"
    params = {"query.title": title, "rows": 3, "select": "title,author,published,container-title,volume,page,DOI"}
    data = _safe_get(url, params)
    if not data:
        return None
    for item in data.get("message", {}).get("items", []):
        titles = item.get("title", [])
        if not titles:
            continue
        found_title = _clean_title(titles[0])
        score = _similarity(title, found_title)
        if score >= min_score:
            return ("CrossRef", score, _parse_crossref(item))
    return None


# ──────────────────────────────────────────────
# 主搜索入口（按优先级依次尝试）
# ──────────────────────────────────────────────

SEARCH_CHAIN = [
    search_semantic_scholar,
    search_dblp,
    search_arxiv,
    search_crossref,
]


def search_paper(
    title: str,
    missing_fields: List[str],
    min_score: float = 90.0,
) -> Optional[Tuple[str, float, Dict]]:
    """
    按优先级搜索，返回第一个相似度达标的结果。
    返回 (来源名, 相似度, {字段: 值}) 或 None
    """
    for fn in SEARCH_CHAIN:
        result = fn(title, min_score)
        time.sleep(0.2)  # 各 API 内部小间隔
        if result:
            return result
    return None
