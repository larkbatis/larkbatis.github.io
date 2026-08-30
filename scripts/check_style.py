#!/usr/bin/env python3
"""Style gate for the docs corpus. See STYLE.md.

Catches the two failure modes a Markdown linter and the vietnamese-tech-writing
validator both miss:

  * the em-dash tic in the English source (the corpus started at 1.05 per 100
    words, one every other sentence),
  * novel metaphor calques in the Vietnamese, which are not dictionary entries
    and so are invisible to the skill's glossary-driven rules.

Exit 1 on any violation. Prose only: fenced code blocks are stripped first.
"""

import glob
import re
import sys

DASH_BUDGET = 0.30  # em dashes per 100 words of prose

# Metaphors that were carried over from English word for word. Each was found in
# the corpus; the replacement is the one STYLE.md fixes on.
CALQUES = {
    "thứ chịu lực": "bắt buộc, không phải cho đẹp",
    "tấm gương phản chiếu": "làm ngược lại",
    "nổ ra": "nhánh được chọn",
    "nhiễm độc": "đã bị đánh dấu hỏng",
    "khoác áo": "đội lốt",
    "nhún vai": "(bỏ hẳn)",
    "đường thất bại": "nhánh xử lý lỗi",
}

# Terms translated further than a Vietnamese engineer would translate them.
OVER_TRANSLATED = {
    "phân giải": "resolve / xác định",
    "văn bản SQL": "câu SQL",
    "chỗ nối": "chèn thẳng vào SQL",
    "lực lượng": "số phần tử",
    "canh gác": "chỉ nối khi điều kiện đúng",
    "lớp bọc": "kiểu bọc",
    "biểu diễn trung gian": "IR",
    "đường ống": "pipeline",
}

# Tone marks: kiểu mới is the house style, and the corpus is already consistent.
OLD_TONE = ["hòa", "thủy", "khóa", "tùy", "hủy", "xóa"]


def prose(path):
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`]*`", "", text)
    return text


def main():
    problems = []

    en = sorted(f for f in glob.glob("docs/**/*.md", recursive=True)
                if not f.endswith(".vi.md"))
    vi = sorted(glob.glob("docs/**/*.vi.md", recursive=True))

    total_d = total_w = 0
    for f in en + vi:
        body = prose(f)
        d, w = body.count("—"), len(body.split())
        total_d += d
        total_w += w
        if w and d / w * 100 > DASH_BUDGET:
            problems.append(
                f"{f}: {d} em dashes in {w} words "
                f"({d / w * 100:.2f}/100, budget {DASH_BUDGET})")

    for f in vi:
        body = prose(f)
        low = body.lower()
        for bad, good in CALQUES.items():
            if bad.lower() in low:
                problems.append(f"{f}: calque '{bad}' -> '{good}'")
        for bad, good in OVER_TRANSLATED.items():
            if bad.lower() in low:
                problems.append(f"{f}: over-translated '{bad}' -> '{good}'")
        for bad in OLD_TONE:
            if re.search(rf"\b{bad}\b", low):
                problems.append(f"{f}: tone-mark style '{bad}' (house style is kiểu mới)")

    if total_w:
        print(f"em dashes: {total_d} in {total_w} words "
              f"= {total_d / total_w * 100:.2f}/100 words")
    print(f"{len(en)} EN + {len(vi)} VI pages checked")

    if problems:
        print()
        for p in problems:
            print(f"  {p}")
        print(f"\n{len(problems)} problem(s)")
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
