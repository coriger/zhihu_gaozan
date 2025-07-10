import io
import os
import shutil
import logging
from datetime import datetime
from flask import Flask, request, render_template, send_file, jsonify
from main_zhihu import ZhihuParser
from main_csdn import CsdnParser
from main_weixin import WeixinParser
from main_juejin import JuejinParser
from flask_cors import CORS
from utils.util import get_valid_filename

import json
import zipfile
import time

if not os.path.exists('./logs'):
    os.makedirs('./logs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='./logs/app.log',
    filemode='a'
)
logger = logging.getLogger('web_app')

# 控制台日志输出
import sys
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)
logger.propagate = True

app = Flask(__name__)
CORS(app)

fix_cookies = "Hm_lvt_df16839cf44aeee94fb85ae1d3c1e17b=1750600402; Hm_lpvt_df16839cf44aeee94fb85ae1d3c1e17b=1750600402; SESSIONID=G9uhAADGkiKLDiukSwJtrsJkSWZhAkPpEvgtlQBBhGV; JOID=VlAQC05HK5jxSv0MREoGyxKfRBdcIBXlmAm8dwEQcaKJIqxqPS91-ZVH_AxESzni4gxqVPj8qt9O1hFIh4x_bMw=; osd=Ul8XB0tDJJ_9T_kDQ0YDzx2YSBJYLxLpnQ2zcA0Vda2OLqluMih5_JFI-wBBTzbl7gluW__wr9tB0R1Ng4N4YMk=; _xsrf=phda5pXGa1MKjASe91FwrZZGhtA05mGV; _zap=5c117f66-613b-4cb4-9d44-79f583d670b4; d_c0=NbPTFbxqfhqPTsaLa3gge3snl9wGBktotO8=|1747940295; HMACCOUNT=4526F4C76E0774FB; DATE=1747940296506; __snaker__id=Ethz4N4NAXd7Jmwz; cmci9xde=U2FsdGVkX184/O+tYpNyfrlUjbpcJvopwJoM+kOLZhsTVPMhLJ7ngI/44IcIy23i+SketmGFC9SvNEM2SFH2Nw==; pmck9xge=U2FsdGVkX19nL8TrXdyzvLQTsYSS215BxRUwy7EGyzA=; crystal=U2FsdGVkX1+jz+5sRO9vF9O6dPu55A3tWeqwwjXT0rwg1MwEwpDtK0mg6e+Lns9oFDMnYFGUeCM5C3WVo/SPrlsDPbnrq/8uvn/llB9wGQ5gx/MORpB2MYwO0HIBGLqi4rDvmOZJ3eFD7SwI3Vtm0Ol+t4IDmDKTNg8+t5sJEScTmMzczEu0roooSoDzYsVMlS7IYwksn2F6lF5M8wdEQuNVGW17K2wvHWRd9rnAe2UsoLzfW4jEb++hHtIxNcdM; assva6=U2FsdGVkX19bZcHyYgoL15qkRy3LH6Lc35vrLcOigpc=; assva5=U2FsdGVkX1+bC1VJbRjFdbjDhvZ2WSBsrNSynkmrUjAViPqv770Ec+tIVEU+xuuDPaWA+Kkows6KGb8n4w8NeA==; vmce9xdq=U2FsdGVkX1/PyOwnlLUdpVqTrkujGeJnNnYfcwwxUIcgfE+jZFu3Ex59MZ1miAuNp5N63FsFKOxJBNkZIuttFFpRHSdFtAuCelwQs82CnL4OlIRsXwyjNlfRUjb9dLmsQDAGarx/CK/2/DLgy95zCg7qExQXFO0vtmV+GTyKh5c=; q_c1=cd09c77351464255b68785b7ab425ca8|1747940393000|1747940393000; _ga=GA1.2.1649157437.1748481939; edu_user_uuid=edu-v1|8fafbaa4-af72-4f05-9e31-10c044f42de2; Hm_lvt_98beee57fd2ef70ccdd5ca52b9740c49=1749559155; _tea_utm_cache_586864={%22utm_source%22:%22zhihu%22%2C%22utm_medium%22:%22organic%22%2C%22utm_content%22:%22search_hot%22}; z_c0=2|1:0|10:1750582725|4:z_c0|80:MS4xd0NJa0FBQUFBQUFtQUFBQVlBSlZUY1VUUldudHdKM3k2WWJaY3p4UmMtT0VpUkk1MEZSbTV3PT0=|73aa20c8dda58f6e36d652173d9982b40fb7f1d1ed00d1b40d007d5165460d03; SESSIONID=k3pdBMvHVV7uePjtBIDVX8MxAkSw2I39M5rnMpklOKR; JOID=U1oUB0_hRDudd0YzSOViaXin9iNRiXRO-TAIRgWyEQ_tEhNaPyRzXvBxRjVNox0gKxEUoCj6NY4SPBgUPNAFJko=; osd=VFAdAE_mTjKad0E5QeJibnKu8SNWg31J-TcCTwKyFgXkFRNdNS10Xvd7TzJNpBcpLBETqiH9NYkYNR8UO9oMIUo=; tst=r; __zse_ck=004_HBPSTJj50O/mm8m/ZnOen2qcIEkA2rvjWg8nCB4Y7zuZ/2Jo=Tb9DSdOIrSCFKmWFvO47m7xiOuh8ckGHoH2kTWND4hNPeaZ7rflx2ucO1zmmx2cSS8ZZ1XwMXDsaNbD-kKy1kBEVmauHuJ48jErpf03SmCBExf8GDdILiDV7qqXaOFxTP2e/KFki+riq3L1+M1qMvHu5KWMcz4iqJFAAwG0QP97+Ez49ItGALkOeYMWtP9S0fGrk+aKKofdP2DBk; gdxidpyhxdE=SpxosHNkJHeegOcDwY%2BKSm66vj8KAoS6qNv8jXoH391nRuM39fVw5IIU7l%5CqtbQKiCtHGn%2F4OEiviMs8IUVScV4DzqPlJZ7mA%2ByjmjpO%5CBO%2BN68s%5CIhClG1ZLs7froW8XSGL537GiN8NRK%2FsqVezClGB8HPyKGTLSHZ%5Corj2t8rjr1ax%3A1751211965500; sec_token=e3948308cf075ffe61a242089efad8ef; captcha_session_v2=XwDGdev8YD8sIQTrILddrztRpk7XOeETC0AQq3wvVC5UTSkdKrWaDnUi5kAS9BKz; captcha_ticket_v2=eyJ2YWxpZGF0ZSI6IkNOMzFfNG0qbUNWLmNIRkJoUHd0WG96Zi5hUzhiR2JpckxDZDB5Ym1UZmxHcWd4M01fZGdvSVBlbExOQnhRaTVLd0NXWFBLY2JyR0VQdXIuVkV3Vm5VYnV1Qy4uTWNfdkZnUHBCdkUwU3RsWVhmWGFKZ1lKTm5XayplWFpGaVZZSm1WQV9HZWVEV0lRYjBZTip3bS44OG14bW0wVUR3YTROaUNpMlQ5RWdJYlN2ZUdLZjFoZkh1UmlUX3BlMDl0Wnc0V1JGY2s1UVJZbmdYNlJYQVJXdmlaVmFabjNELjZEKmZzZHNLYi5tbEZ3NEVTeUpycTBKSmRzclNFeGFfZkppa2NKaFcuZFNHZWtNVmRWbUl6Lkdkd0kzcmwyTUdrVkxIbk1qRkNqMEoqTCptSG1BdllWbWZGSEF5QXI2dmRfbXBHeTB0OCpzNkp4Y3ZEQktnUFhab3NmenFUUFE0OTVROERKSndEdFgwX01BY3BOMFFCY2xkMjNzS1VQek1YaE0wZ3NBVypHUTg0aVBqKjAudkF1eUEueTJOaXdBRzl1U21ObHNqeUJoYy44NVFkRGFWa2hEc1NsS0xGeVRWMCpRTllsRjNpLk50VFhudWIucHVzVCpLMTZ4Z0dmRnZEUWFKNnU1MllnWHRWWEIybjNiYjA2cWkxOXNaOTRJNVoyYlM1ODNDYzZLNFk3N192X2lfMSJ9; BEC=6ff32b60f55255af78892ba1e551063a; Hm_lpvt_98beee57fd2ef70ccdd5ca52b9740c49=1751211832"

def create_zip_from_directory(directory, zip_path):
    """从给定目录创建ZIP文件"""
    supported_extensions = ['.md', '.jpg', '.png', '.gif', '.mp4', '.txt']
    log_files = ['zhihu_download.log', 'weixin_download.log', 'csdn_download.log',]

    try:
        with zipfile.ZipFile(zip_path, "w") as zf:
            for root, _, files in os.walk(directory):
                for file in files:
                    if any(file.endswith(ext) for ext in supported_extensions) or file in log_files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, directory)
                        zf.write(file_path, arcname)
        return True
    except Exception as e:
        logger.error(f"Error creating zip file: {str(e)}")
        return False


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        cookies = request.form["cookies"]
        cookies = fix_cookies
        url_text = request.form["url"]
        website = request.form["website"].lower()
        keep_logs = request.form.get("keep_logs") == "on"

        parser_map = {
            "csdn": (CsdnParser(keep_logs=keep_logs), "csdn"),
            "zhihu": (ZhihuParser(cookies, keep_logs=keep_logs), "zhihu"),
            "weixin": (WeixinParser(keep_logs=keep_logs), "weixin"),
            "juejin": (JuejinParser(keep_logs=keep_logs), "juejin")
        }

        try:
            parser, _ = parser_map[website]
        except KeyError:
            logger.warning(f"Unsupported website: {website}")
            return "Unsupported website", 400

        # 目标目录
        target_dir = r"F:\原子库\原子库\07-知乎"
        os.makedirs(target_dir, exist_ok=True)

        # 支持多行URL
        url_list = [line.strip() for line in url_text.splitlines() if line.strip()]
        results = []
        for url in url_list:
            try:
                markdown_title = parser.judge_type(url)
                logger.info(f"Successfully processed {url}, title: {markdown_title}")
                # 查找生成的文件夹（与md同名或parser输出目录）
                # 假设parser.output_dir为当前处理的输出目录
                # 文件夹名通常与md文件名一致
                folder_name = markdown_title if os.path.isdir(os.path.join(parser.output_dir, markdown_title)) else None
                if not folder_name:
                    # 兼容只有md文件的情况
                    folder_name = None
                    for file in os.listdir(parser.output_dir):
                        if file.endswith('.md'):
                            name = os.path.splitext(file)[0]
                            if os.path.isdir(os.path.join(parser.output_dir, name)):
                                folder_name = name
                                break
                if folder_name:
                    src_folder = os.path.join(parser.output_dir, folder_name)
                    dst_folder = os.path.join(target_dir, folder_name)
                    if os.path.exists(dst_folder):
                        shutil.rmtree(dst_folder)
                    shutil.move(src_folder, dst_folder)
                    results.append(f"成功: {url} → {dst_folder}")
                else:
                    # 只移动md文件
                    for file in os.listdir(parser.output_dir):
                        if file.endswith('.md'):
                            src = os.path.join(parser.output_dir, file)
                            dst = os.path.join(target_dir, file)
                            shutil.move(src, dst)
                    results.append(f"成功: {url} (仅md文件)")
            except Exception as e:
                logger.error(f"Error processing {website} URL {url}: {str(e)}")
                results.append(f"失败: {url}，错误: {str(e)}")
        return render_template("index.html", result_msg="<br>".join(results))

    return render_template("index.html")


@app.route("/get-cookies")
def get_cookies():
    return render_template("howToGetCookies.html")


@app.route("/api/logs", methods=["GET"])
def get_logs():
    """API endpoint to retrieve logs"""
    log_type = request.args.get('type', 'app')

    log_files = {
        'zhihu': './logs/zhihu_download.log',
        'csdn': './logs/csdn_download.log',
        'weixin': './logs/weixin_download.log',
        'juejin': './logs/juejin_download.log',
    }

    if log_type not in log_files:
        return jsonify({"error": "Invalid log type"}), 400

    log_path = log_files[log_type]
    if not os.path.exists(log_path):
        return jsonify({"logs": f"Log file {log_path} not found"}), 404

    try:
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

        for encoding in encodings:
            try:
                with open(log_path, 'r', encoding=encoding, errors='replace') as f:
                    lines = f.readlines()
                    return jsonify({"logs": ''.join(lines)})
            except UnicodeDecodeError:
                continue

        with open(log_path, 'rb') as f:
            binary_content = f.read()
            text_content = binary_content.decode('utf-8', errors='replace')
            return jsonify({"logs": text_content})

    except Exception as e:
        logger.error(f"Error reading log file {log_path}: {str(e)}")
        return jsonify({"error": f"Failed to read log file: {str(e)}"}), 500


def cleanup_files(paths):
    """清理指定路径下的文件和目录"""
    for path in paths:
        if os.path.exists(path):
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
            except OSError as e:
                app.logger.error(f"Failed to remove {path}: {e}")


@app.route("/api/zhihu_hot_answers", methods=["POST"])
def zhihu_hot_answers():
    """
    接收知乎问题url，自动滚动下拉（最多30次），抓取点赞数大于50的高赞答案，整合为一个md文件，存到F:\原子库\原子库\07-知乎
    """
    data = request.get_json()
    question_url = data.get('url', '').strip()
    if not question_url or not question_url.startswith('http'):
        return jsonify({'success': False, 'error': '无效的知乎问题链接'}), 400

    cookies = request.form.get('cookies', '') if 'cookies' in request.form else ''
    try:
        import requests
        from bs4 import BeautifulSoup
        import re
        md_lines = []
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'cookie': cookies
        }
        # 提取问题id
        m = re.search(r'/question/(\d+)', question_url)
        if not m:
            return jsonify({'success': False, 'error': '链接格式错误'}), 400
        qid = m.group(1)
        offset = 0
        limit = 20
        max_scroll = 30
        answers = []
        for i in range(max_scroll):
            api = f'https://www.zhihu.com/api/v4/questions/{qid}/answers?include=data[*].is_normal,voteup_count,content,created_time,author.name,url,question.title&limit={limit}&offset={offset}&sort_by=default'
            resp = requests.get(api, headers=headers, timeout=10)
            if resp.status_code != 200:
                break
            data = resp.json()
            for ans in data['data']:
                if ans['voteup_count'] >= 50:
                    answers.append(ans)
            if data.get('paging', {}).get('is_end'):
                break
            offset += limit
            time.sleep(0.5)
        if not answers:
            return jsonify({'success': False, 'error': '未找到高赞答案'}), 200
        # 合并为md
        title = answers[0]['question']['title'] if 'question' in answers[0] else f'知乎高赞答案_{qid}'
        md_lines.append(f'# {title}\n')
        image_dir = os.path.join('md', 'image')
        os.makedirs(image_dir, exist_ok=True)
        for idx, ans in enumerate(answers, 1):
            author = ans['author']['name'] if ans['author'] else '匿名用户'
            vote = ans['voteup_count']
            content_html = ans['content']
            soup = BeautifulSoup(content_html, 'html.parser')
            # 处理图片，下载到md/image下
            for img in soup.find_all('img'):
                img_url = img.get('data-original') or img.get('src')
                if img_url:
                    img_name = os.path.basename(img_url.split('?')[0])
                    img_path = os.path.join(image_dir, img_name)
                    try:
                        if not os.path.exists(img_path):
                            img_data = requests.get(img_url, headers=headers, timeout=10).content
                            with open(img_path, 'wb') as imgf:
                                imgf.write(img_data)
                        img.replace_with(f'![img](image/{img_name})')
                    except Exception:
                        img.replace_with(f'![img]({img_url})')
            content_md = soup.get_text('\n')
            md_lines.append(f'\n---\n\n## 答案{idx} | 作者：{author} | 赞同：{vote}\n\n{content_md}\n')
        filename = f'高赞答案_{qid}.md'
        save_path = os.path.join('md', filename)
        os.makedirs('md', exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route("/api/zhihu_batch_answers", methods=["POST"])
def zhihu_batch_answers():
    """
    接收知乎答案链接列表，批量抓取内容并整合为一个md文件，存到F:\原子库\原子库\07-知乎
    """
    import glob
    data = request.get_json(force=True)
    urls = data.get('urls', [])
    if not urls or not isinstance(urls, list):
        return jsonify({'success': False, 'error': '无效的知乎答案链接列表'}), 400

    try:
        from main_zhihu import ZhihuParser
        parser = ZhihuParser(fix_cookies)
        answer_blocks = []
        generated_files = []
        generated_dirs = set()
        origin_title = '知乎高赞答案批量导出'  # 先设一个默认标题
        for idx, url in enumerate(urls, 1):
            try:
                print(f"处理第{idx}个链接: {url}")
                title, vote_count, temp_origin_title = parser.parse_zhihu_answer(url)
                print(f"解析结果: title={title}, vote_count={vote_count}, temp_origin_title={temp_origin_title}")
                if not title or not vote_count:
                    print(f"解析失败，中断批量导出: {url}")
                    break
                if temp_origin_title:
                    origin_title = temp_origin_title  # 只要有返回就覆盖
                md_filename = f"{title}.md"
                md_filename = get_valid_filename(md_filename)
                print(f"检查md文件是否存在: {md_filename}, os.path.exists={os.path.exists(md_filename)}")
                vote_count_int = int(vote_count) if vote_count is not None else 0
                if os.path.exists(md_filename):
                    with open(md_filename, 'r', encoding='utf-8') as f:
                        md_content = f.read()
                    # 去掉原有标题，直接用 # 赞同数：xxx
                    import re
                    md_content = re.sub(r'^# .+\n?', '', md_content, count=1)
                    block = f"# 赞同数：{vote_count_int}\n\n{md_content.strip()}"
                    answer_blocks.append((vote_count_int, block))
                    generated_files.append(md_filename)
                    print(f"已添加答案块，文件: {md_filename}")
                    if os.path.isdir(title):
                        generated_dirs.add(title)
                        print(f"检测到同名目录: {title}")
                else:
                    print(f"未找到md文件: {md_filename}")
                    answer_blocks.append((0, f"# 赞同数：0\n\n## 未找到md文件: {url}\n"))
            except Exception as e:
                print(f"解析异常: {e}")
        # 按点赞数降序排序
        if not answer_blocks:
            print("没有任何答案块，因前面解析失败，终止导出流程")
            return jsonify({'success': False, 'error': '批量导出失败，所有解析均未成功'}), 200
        print(f"answer_blocks排序前: {[(x[0], str(x[1])[:30]) for x in answer_blocks]}")
        answer_blocks.sort(key=lambda x: x[0], reverse=True)
        print(f"answer_blocks排序后: {[(x[0], str(x[1])[:30]) for x in answer_blocks]}")
        md_lines = [block for _, block in answer_blocks]
        filename = f'{origin_title}.md'
        filename = get_valid_filename(filename)
        # 去掉最后的问号（全角或半角），并将所有问号替换为下划线
        if filename.endswith('？.md') or filename.endswith('?.md'):
            filename = filename[:-4].rstrip('？?') + '.md'
        filename = filename.replace('？', '_').replace('?', '_')
        save_path = os.path.join('md', filename)
        print(f"最终保存文件: {save_path}")
        os.makedirs('md', exist_ok=True)
        print(f"save_path: {save_path}")
        print(f"md_lines类型: {type(md_lines)}, 长度: {len(md_lines)}")
        # if md_lines:
        #     print(f"内容预览: {md_lines}")
        try:
            print(f"开始写入md文件: {save_path}")
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write('\n\n---\n\n'.join(md_lines))
            print(f"md文件写入完成: {save_path}")
        except Exception as e:
            print(f"写入md文件异常: {e}")
        # 清理单个md文件和同名文件夹
        for file in generated_files:
            try:
                print(f"准备删除md文件: {file}")
                os.remove(file)
                print(f"已删除md文件: {file}")
            except Exception as e:
                print(f"删除md文件失败: {file}, 错误: {e}")
        for folder in generated_dirs:
            try:
                if os.path.isdir(folder):
                    print(f"准备删除同名目录: {folder}")
                    import shutil
                    shutil.rmtree(folder)
                    print(f"已删除同名目录: {folder}")
            except Exception as e:
                print(f"删除目录失败: {folder}, 错误: {e}")
        print(f"批量导出流程结束，返回文件: {filename}")
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
