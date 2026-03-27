"""
EndNote 参考文献自动补全工具 — 计算机/AI 领域专用
使用方式:
  python main.py --input my_library.ris --output fixed.ris --dry-run
  python main.py --input my_library.ris --output fixed.ris
"""
import argparse
import time
import sys
from pathlib import Path

import pandas as pd
import xml.etree.ElementTree as ET

from detector import find_incomplete
from searcher import search_paper
from merger import merge_record, build_diff_row


def load_endnote_xml(path):
    tree = ET.parse(path)
    root = tree.getroot()
    records = []
    for rec in root.findall(".//record"):
        r = {}
        # 标题
        title = rec.findtext(".//title/style") or rec.findtext(".//title")
        if title:
            r["title"] = title.strip()
        # 作者
        authors = [a.findtext("style") or a.text or ""
                   for a in rec.findall(".//contributors/authors/author")]
        if authors:
            r["authors"] = [a.strip() for a in authors if a.strip()]
        # 年份
        year = rec.findtext(".//dates/year/style") or rec.findtext(".//dates/year")
        if year:
            r["year"] = year.strip()
        # 期刊/会议名称(EndNote中期刊在periodical下，会议等一般在titles/secondary-title下)
        journal = rec.findtext(".//periodical/full-title/style") or \
                  rec.findtext(".//periodical/full-title") or \
                  rec.findtext(".//titles/secondary-title/style") or \
                  rec.findtext(".//titles/secondary-title")
        if journal:
            r["journal_name"] = journal.strip()
        # DOI
        doi = rec.findtext(".//electronic-resource-num/style") or \
              rec.findtext(".//electronic-resource-num")
        if doi:
            r["doi"] = doi.strip()
        # 卷/页
        r["volume"] = rec.findtext(".//volume/style") or rec.findtext(".//volume") or ""
        r["start_page"] = rec.findtext(".//pages/style") or rec.findtext(".//pages") or ""
        r["_xml_rec"] = rec  # 保留原始节点，写回时用
        records.append(r)
    return records, tree


def _set_xml_node_text(rec_node, path, text):
    parts = path.split("/")
    curr = rec_node
    for p in parts:
        nxt = curr.find(p)
        if nxt is None:
            nxt = ET.SubElement(curr, p)
        curr = nxt
    style = curr.find("style")
    if style is not None:
        style.text = str(text)
    else:
        style = ET.SubElement(curr, "style", face="normal", font="default", size="100%")
        style.text = str(text)


def update_xml_record(node, original, merged):
    for key, val in merged.items():
        if val == original.get(key) or not val:
            continue
        if key == "year":
            _set_xml_node_text(node, "dates/year", val)
        elif key == "journal_name":
            # 智能判断引用类型，EndNote里 17 代表期刊，其他(如 10, 47)通常用 secondary-title 存会议名
            ref_type = node.findtext("ref-type")
            if ref_type == "17" or node.find("periodical") is not None:
                _set_xml_node_text(node, "periodical/full-title", val)
            else:
                _set_xml_node_text(node, "titles/secondary-title", val)
        elif key == "volume":
            _set_xml_node_text(node, "volume", val)
        elif key in ["start_page", "pages"]:
            page_val = val
            if merged.get("end_page"):
                page_val = f"{val}-{merged['end_page']}"
            _set_xml_node_text(node, "pages", page_val)
        elif key == "doi":
            _set_xml_node_text(node, "electronic-resource-num", val)
        elif key == "url":
            _set_xml_node_text(node, "urls/related-urls/url", val)
        elif key == "authors":
            contrib = node.find("contributors")
            if contrib is None: contrib = ET.SubElement(node, "contributors")
            auths = contrib.find("authors")
            if auths is None: auths = ET.SubElement(contrib, "authors")
            else: auths.clear()
            for a in val:
                author_node = ET.SubElement(auths, "author")
                style = ET.SubElement(author_node, "style", face="normal", font="default", size="100%")
                style.text = a


def main():
    parser = argparse.ArgumentParser(description="自动补全 EndNote XML 文件中缺失的字段")
    parser.add_argument("--input",  required=True, help="输入 .xml 文件路径")
    parser.add_argument("--output", required=True, help="输出 .xml 文件路径")
    parser.add_argument("--dry-run", action="store_true",
                        help="只生成报告，不写入文件")
    parser.add_argument("--min-score", type=float, default=90.0,
                        help="标题相似度阈值（默认 90）")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="每次 API 请求间隔秒数（默认 0.5）")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[错误] 找不到输入文件: {input_path}")
        sys.exit(1)

    print(f"📖 读取文件: {input_path}")
    try:
        records, tree = load_endnote_xml(str(input_path))
    except Exception as e:
        print(f"[错误] 解析 XML 失败: {e}")
        sys.exit(1)
    print(f"   共 {len(records)} 条记录")

    incomplete = find_incomplete(records)
    print(f"🔍 检测到 {len(incomplete)} 条记录有字段缺失\n")

    if not incomplete:
        print("✅ 所有记录字段完整，无需修复！")
        return

    updated_records = list(records)  # shallow copy
    diff_rows = []

    for idx, (rec_idx, record, missing_fields) in enumerate(incomplete):
        title = record.get("title") or record.get("primary_title") or ""
        if not title:
            print(f"[{idx+1}/{len(incomplete)}] 跳过（无标题）: record #{rec_idx}")
            diff_rows.append(build_diff_row(rec_idx, record, None, missing_fields, "跳过-无标题"))
            continue

        print(f"[{idx+1}/{len(incomplete)}] 搜索: {title[:60]}...")
        print(f"   缺失字段: {', '.join(missing_fields)}")

        result = search_paper(title, missing_fields, min_score=args.min_score)
        time.sleep(args.delay)

        if result is None:
            print(f"   ⚠ 未找到可信结果（相似度 < {args.min_score}%）")
            diff_rows.append(build_diff_row(rec_idx, record, None, missing_fields, "未找到"))
            continue

        source, score, found_data = result
        merged = merge_record(record, found_data)
        
        # 计算真正因为原本缺失而被成功补全的字段
        actually_filled = [k for k in found_data.keys() if record.get(k) != merged.get(k)]
        print(f"   ✓ 命中 [{source}] 相似度={score:.1f}%  实际补全: {actually_filled}")

        updated_records[rec_idx] = merged
        update_xml_record(merged["_xml_rec"], record, merged)
        diff_rows.append(build_diff_row(rec_idx, record, found_data, missing_fields,
                                        f"已补全({source},{score:.0f}%)"))

    # 保存报告
    report_path = input_path.with_name("fix_report.csv")
    df = pd.DataFrame(diff_rows)
    df.to_csv(report_path, index=False, encoding="utf-8-sig")
    print(f"\n📊 报告已保存: {report_path}")

    if args.dry_run:
        print("🔵 dry-run 模式，不写入输出文件。")
        _print_summary(diff_rows)
        return

    out_path = Path(args.output)
    tree.write(str(out_path), encoding="utf-8", xml_declaration=True)
    print(f"💾 已写入: {out_path}")
    _print_summary(diff_rows)


def _print_summary(rows):
    total   = len(rows)
    fixed   = sum(1 for r in rows if r["状态"].startswith("已补全"))
    skipped = sum(1 for r in rows if "跳过" in r["状态"])
    missed  = total - fixed - skipped
    print(f"\n===== 汇总 =====")
    print(f"  需要补全: {total}")
    print(f"  成功补全: {fixed}")
    print(f"  未找到  : {missed}")
    print(f"  跳过    : {skipped}")


if __name__ == "__main__":
    main()
