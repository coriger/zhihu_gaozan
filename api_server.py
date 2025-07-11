from flask import Flask, request, jsonify
import os

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

if __name__ == '__main__':
    app.run(port=5001, debug=True)
