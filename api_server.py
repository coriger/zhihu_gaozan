from flask import Flask, request, jsonify, send_from_directory
import os
import time

from flask_cors import CORS
app = Flask(__name__)
CORS(app)

@app.route('/add_zhihu_question', methods=['POST'])
def add_zhihu_question():
    data = request.get_json(force=True)
    title = data.get('title', '').strip()
    url = data.get('url', '').strip()
    category = data.get('category', '').strip()
    if not (title and url and category):
        return jsonify({'success': False, 'msg': '参数缺失'}), 400
    
    folder = os.path.join('md', '问题库')
    os.makedirs(folder, exist_ok=True)
    md_path = os.path.join(folder, f'Question_{category}.md')
    line = f'{title}\t{url}\n'
    # 检查是否已存在
    if os.path.exists(md_path):
        with open(md_path, 'r', encoding='utf-8') as f:
            if any(url in l for l in f):
                return jsonify({'success': True, 'msg': '已存在'}), 200
    with open(md_path, 'a', encoding='utf-8') as f:
        f.write(line)
    return jsonify({'success': True, 'msg': '已写入'})

@app.route('/list_md_tree', methods=['GET'])
def list_md_tree():
    def build_tree(root):
        tree = {
            'name': os.path.basename(root),
            'type': 'dir',
            'children': [],
            'mtime': os.path.getmtime(root) if os.path.exists(root) else None
        }
        try:
            for entry in sorted(os.listdir(root)):
                path = os.path.join(root, entry)
                if os.path.isdir(path):
                    tree['children'].append(build_tree(path))
                elif entry.endswith('.md'):
                    tree['children'].append({
                        'name': entry,
                        'type': 'file',
                        'mtime': os.path.getmtime(path) if os.path.exists(path) else None
                    })
        except Exception as e:
            tree['error'] = str(e)
        return tree
    root = os.path.join('md')
    tree = build_tree(root)
    return jsonify({'success': True, 'tree': tree})

@app.route('/get_md_file', methods=['GET'])
def get_md_file():
    rel_path = request.args.get('path', '').strip()
    if not rel_path or '..' in rel_path or rel_path.startswith('/'):
        return jsonify({'success': False, 'msg': '非法路径'}), 400
    abs_path = os.path.join('md', rel_path)
    if not os.path.isfile(abs_path):
        return jsonify({'success': False, 'msg': '文件不存在'}), 404
    with open(abs_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({'success': True, 'content': content})

@app.route('/upload_json', methods=['POST'])
def upload_json():
    if 'file' not in request.files:
        return jsonify({'success': False, 'msg': '未找到文件'}), 400
    file = request.files['file']
    if not file or not file.filename.endswith('.json'):
        return jsonify({'success': False, 'msg': '文件格式错误'}), 400
    date_str = time.strftime('%Y%m%d_%H%M%S')
    save_dir = os.path.join('model')
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f'model_{date_str}.json')
    file.save(save_path)
    return jsonify({'success': True, 'msg': '上传成功', 'filename': os.path.basename(save_path)})

@app.route('/list_backups', methods=['GET'])
def list_backups():
    backup_dir = os.path.join('model')
    if not os.path.exists(backup_dir):
        return jsonify({'success': True, 'files': []})
    files = [f for f in os.listdir(backup_dir) if f.endswith('.json')]
    files.sort(reverse=True)
    file_list = []
    for f in files:
        size_bytes = os.path.getsize(os.path.join(backup_dir, f))
        size_kb = round(size_bytes / 1024, 2)
        file_list.append({'filename': f, 'size_kb': size_kb})
    return jsonify({'success': True, 'files': file_list})

@app.route('/download_json', methods=['GET'])
def download_json():
    filename = request.args.get('filename', '').strip()
    if not filename or not filename.endswith('.json'):
        return jsonify({'success': False, 'msg': '文件名错误'}), 400
    file_dir = os.path.join('model')
    file_path = os.path.join(file_dir, filename)
    if not os.path.isfile(file_path):
        return jsonify({'success': False, 'msg': '文件不存在'}), 404
    return send_from_directory(file_dir, filename, as_attachment=True)

@app.route('/get_json_content', methods=['GET'])
def get_json_content():
    filename = request.args.get('filename', '').strip()
    if not filename or not filename.endswith('.json'):
        return jsonify({'success': False, 'msg': '文件名错误'}), 400
    file_dir = os.path.join('model')
    file_path = os.path.join(file_dir, filename)
    if not os.path.isfile(file_path):
        return jsonify({'success': False, 'msg': '文件不存在'}), 404
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({'success': True, 'content': content})

@app.route('/overwrite_json', methods=['POST'])
def overwrite_json():
    import json
    file_dir = os.path.join('model')
    if not os.path.exists(file_dir):
        return jsonify({'success': False, 'msg': 'model目录不存在'}), 400
    files = [f for f in os.listdir(file_dir) if f.endswith('.json')]
    if not files:
        return jsonify({'success': False, 'msg': '没有可覆盖的json文件'}), 404
    files.sort(reverse=True)
    latest_file = files[0]
    latest_path = os.path.join(file_dir, latest_file)
    # 获取提交的json内容
    if 'file' not in request.files:
        return jsonify({'success': False, 'msg': '未找到文件'}), 400
    file = request.files['file']
    if not file or not file.filename.endswith('.json'):
        return jsonify({'success': False, 'msg': '文件格式错误'}), 400
    new_content = file.read().decode('utf-8')
    with open(latest_path, 'r', encoding='utf-8') as f:
        old_content = f.read()
    if new_content.strip() == old_content.strip():
        return jsonify({'success': True, 'msg': '内容未变化，无需覆盖', 'filename': latest_file})
    # 新内容必须比原文件大
    if len(new_content.encode('utf-8')) <= len(old_content.encode('utf-8')):
        return jsonify({'success': False, 'msg': '新内容未超过原文件大小，禁止覆盖'}), 400
    # 文件名改为当前时间
    date_str = time.strftime('%Y%m%d_%H%M%S')
    new_filename = f'model_{date_str}.json'
    new_path = os.path.join(file_dir, new_filename)
    with open(new_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    # 删除旧文件
    try:
        os.remove(latest_path)
    except Exception:
        pass
    return jsonify({'success': True, 'msg': '已覆盖', 'filename': new_filename})

if __name__ == '__main__':
    app.run(port=5001, debug=True)
