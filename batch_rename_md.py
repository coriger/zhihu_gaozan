import os
from utils.util import get_valid_filename

def batch_rename_md_files(md_dir='md'):
    files = os.listdir(md_dir)
    for f in files:
        if f.endswith('.md'):
            # 先去掉最后的问号（全角或半角）
            name_wo_ext = f[:-3]
            if name_wo_ext.endswith('？') or name_wo_ext.endswith('?'):
                name_wo_ext = name_wo_ext.rstrip('？?')
            # 再将所有问号替换为下划线
            new_name = name_wo_ext.replace('？', '_').replace('?', '_') + '.md'
            if new_name != f:
                os.rename(os.path.join(md_dir, f), os.path.join(md_dir, new_name))
                print(f'Renamed: {f} -> {new_name}')

if __name__ == '__main__':
    batch_rename_md_files()
