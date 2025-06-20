import os

def check_md_files_for_question_mark(md_dir='md'):
    files = os.listdir(md_dir)
    for f in files:
        if '?' in f or '？' in f:
            print(f'含问号文件: {f}')

if __name__ == '__main__':
    check_md_files_for_question_mark()
