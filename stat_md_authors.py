import os
import re
from collections import Counter

def extract_authors_from_md(md_dir='md'):
    author_counter = Counter()
    for fname in os.listdir(md_dir):
        if fname.endswith('.md'):
            path = os.path.join(md_dir, fname)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    text = f.read()
                # 匹配 **Author:** [作者名] 或 **Author:** 作者名
                authors = re.findall(r'\*\*Author:\*\* \[?([^\]\n]+)\]?\n', text)
                for author in authors:
                    author = author.strip()
                    if author:
                        author_counter[author] += 1
            except Exception as e:
                print(f'Error reading {fname}: {e}')
    return author_counter

def main():
    counter = extract_authors_from_md()
    for author, count in counter.most_common():
        print(f'{author}: {count}')

if __name__ == '__main__':
    main()
