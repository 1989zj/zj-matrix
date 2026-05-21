#!/usr/bin/env python3
"""Count Chinese characters (CJK + Chinese punctuation) in one or more files.

Counts CJK Unified Ideographs AND Chinese punctuation marks, matching
the "字数" convention used by Chinese web novel platforms (起点/晋江/etc).

Usage:
    python3 count-chinese-chars.py file1.md [file2.md ...]

Output:
    File path -> Chinese character count (includes Chinese punctuation)

For word count verification of web novel chapters. Target range varies
by user request (commonly 2400-2600, 2000-2200, or 3000-3200).
"""
import re
import sys


def count_chinese(text: str) -> int:
    """Count CJK Unified Ideographs plus Chinese punctuation — matches "字数" convention."""
    cjk = re.findall(r'[\u4e00-\u9fff]', text)
    punct = re.findall(r'[\u3000-\u303f\uff00-\uffef]', text)
    return len(cjk) + len(punct)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 count-chinese-chars.py <file.md> [file2.md ...]")
        sys.exit(1)

    total = 0
    for path in sys.argv[1:]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            count = count_chinese(content)
            total += count
            # Short form for single file
            if len(sys.argv) == 2:
                print(count)
            else:
                print(f"{count:>5}  {path}")
        except FileNotFoundError:
            print(f"ERROR: File not found: {path}", file=sys.stderr)
            sys.exit(1)

    if len(sys.argv) > 2:
        print(f"{'-----':>5}")
        print(f"{total:>5}  total")


if __name__ == '__main__':
    main()
