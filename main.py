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

import rispy
import pandas as pd

from detector import find_incomplete
from searcher import search_paper
from merger import merge_record, build_diff_row


def main():
    parser = argparse.ArgumentParser(description="自动补全 EndNote RIS 文件中缺失的字段")
    parser.add_argument("--input",  required=True, help="输入 .ris 文件路径")
    parser.add_argument("--output", required=True, help="输出 .ris 文件路径")
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
    with open(input_path, encoding="utf-8") as f:
        records = rispy.load(f)
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
        print(f"   ✓ 命中 [{source}] 相似度={score:.1f}%  补全: {list(found_data.keys())}")

        merged = merge_record(record, found_data)
        updated_records[rec_idx] = merged
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
    with open(out_path, "w", encoding="utf-8") as f:
        rispy.dump(updated_records, f)
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
