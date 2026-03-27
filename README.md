# EndNote 参考文献自动补全工具（计算机/AI 领域）

## 快速开始

```bash
pip install -r requirements.txt
python main.py --input my_library.xml --output fixed.xml --dry-run
```

dry-run 后查看 fix_report.csv，确认无误再正式写入：

```bash
python main.py --input my_library.xml --output fixed.xml
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input` | 必填 | 输入 .xml 文件 |
| `--output` | 必填 | 输出 .xml 文件 |
| `--dry-run` | 关 | 只生成报告，不写入文件 |
| `--min-score` | 90 | 标题相似度阈值（0-100） |
| `--delay` | 0.5 | API 请求间隔秒数 |

## API 优先级（CS/AI 专用）

1. **Semantic Scholar** — AI/ML 覆盖最全，字段最丰富
2. **DBLP** — CS 顶会/期刊（CVPR、NeurIPS、ICML、ICLR 等）最权威
3. **arXiv** — 预印本，最新 AI 论文必备
4. **CrossRef** — 通用兜底

## 从 EndNote 导出 XML

`File → Export → 格式选 XML`

## 导回 EndNote

`File → Import → File → Format: EndNote Generated XML → Import Option: Update existing references`

## 输出的 fix_report.csv 说明

| 列 | 说明 |
|----|------|
| 序号 | 在 RIS 文件中的位置 |
| 标题 | 论文标题（截断到80字符）|
| 缺失字段 | 检测到缺失的字段名 |
| 状态 | 已补全/未找到/跳过 |
| 补全_* | API 找到的各字段值 |
