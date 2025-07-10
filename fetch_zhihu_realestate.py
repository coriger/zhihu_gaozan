# 使用 Playwright 自动化浏览器抓取知乎高赞答案，绕过 API 反爬虫
import asyncio
from playwright.sync_api import sync_playwright
import time
import os
import re
from bs4 import BeautifulSoup
from utils.util import get_valid_filename
from markdownify import markdownify as md
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import queue

def get_question_id(url):
    m = re.search(r'/question/(\d+)', url)
    return m.group(1) if m else None

def load_cookies_from_txt(cookies_path):
    # 读取 cookies.txt 并转为 Playwright cookies 格式
    cookies = []
    if not os.path.exists(cookies_path):
        return cookies
    with open(cookies_path, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                parts = line.strip().split(';')
                for part in parts:
                    if '=' in part:
                        k, v = part.strip().split('=', 1)
                        cookies.append({'name': k, 'value': v, 'domain': '.zhihu.com', 'path': '/'})
    return cookies

def fetch_zhihu_answers_by_browser(url, min_vote=50, max_answers=10, cookies_path='cookies.txt'):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
        context = browser.new_context()
        cookies = load_cookies_from_txt(cookies_path)
        if cookies:
            context.add_cookies(cookies)
        page = context.new_page()
        page.goto(url, timeout=60000)
        try:
            # 先等待问题标题，判断是否进入了问题页
            page.wait_for_selector('h1.QuestionHeader-title', timeout=15000)
        except Exception as e:
            html = page.content()
            print(f'Exception: {e}')
            print('页面内容片段如下:')
            print(html[:1000])
            if '登录知乎' in html or '验证码' in html:
                print('页面被重定向到登录页或出现验证码，请检查 cookies.txt 是否为有效知乎登录 cookies')
            else:
                print('未检测到问题标题，页面结构异常')
            browser.close()
            return '知乎高赞答案', []
        answers = []
        answer_ids = set()
        stop_low_vote_count = 0
        for _ in range(60):
            # 模拟真实用户：下-上-下滚动
            page.mouse.wheel(0, 2000)
            time.sleep(0.5)
            page.mouse.wheel(0, -800)
            time.sleep(0.3)
            page.mouse.wheel(0, 1200)
            time.sleep(0.5)
            try:
                while True:
                    more_btn = page.query_selector('button.QuestionAnswers-answersMore, button:has-text("更多回答")')
                    if more_btn and more_btn.is_visible():
                        more_btn.click()
                        time.sleep(1.2)
                    else:
                        break
            except Exception:
                pass
            # 检查新加载答案
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            new_low_vote = 0
            for ans_div in soup.select('div.List-item'):
                try:
                    upvote_meta = ans_div.select_one('meta[itemprop="upvoteCount"]')
                    vote = int(upvote_meta['content']) if upvote_meta and upvote_meta.has_attr('content') else 0
                    # 用答案内容唯一性做去重
                    content_tag = ans_div.select_one('div.RichContent-inner')
                    content_html = str(content_tag) if content_tag else ''
                    ans_id = hash(content_html)
                    if ans_id in answer_ids:
                        continue
                    answer_ids.add(ans_id)
                    # 跳过 .ContentItem-meta 下的 meta[itemprop="url"]
                    url_meta = None
                    for meta in ans_div.select('meta[itemprop="url"]'):
                        if meta.find_parent(class_='ContentItem-meta') is None:
                            url_meta = meta
                            break
                    answer_url = url_meta['content'] if url_meta and url_meta.has_attr('content') else ''
                    if vote >= min_vote:
                        author_meta = ans_div.select_one('meta[itemprop="name"]')
                        author = author_meta['content'] if author_meta and author_meta.has_attr('content') else '匿名用户'
                        answers.append({'author': author, 'voteup_count': vote, 'content': content_html, 'url': answer_url})
                        new_low_vote = 0  # 只统计连续低赞
                    else:
                        new_low_vote += 1
                except Exception as e:
                    continue
            if new_low_vote >= 3:
                print(f'连续{new_low_vote}个新答案低于{min_vote}赞，提前停止滚动加载')
                break
        # 按点赞数降序排序
        answers.sort(key=lambda x: x['voteup_count'], reverse=True)
        # 获取问题标题
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        title_tag = soup.select_one('h1.QuestionHeader-title')
        title = title_tag.text.strip() if title_tag else '知乎高赞答案'
        browser.close()
        return title, answers

def save_answers_md_browser(title, answers, out_dir='md/房地产'):
    if not answers:
        return None
    filename = get_valid_filename(title) + '.md'
    os.makedirs(out_dir, exist_ok=True)
    save_path = os.path.join(out_dir, filename)
    md_lines = [f'# {title}']
    import re
    url_set = set()
    answer_blocks = []
    idx = 1
    for ans in answers:
        answer_url = ans.get('url', '')
        if answer_url and answer_url in url_set:
            continue
        url_set.add(answer_url)
        author = ans.get('author', '匿名用户')
        vote = ans.get('voteup_count', 0)
        content_html = ans.get('content', '')
        content_md = md(content_html, heading_style='ATX')
        # 去除 data:image/svg+xml;utf8... 这类图片和所有 data:image/xxx;base64... 的图片
        content_md = re.sub(r'!\[]\(data:image/[^)]+\)', '', content_md)
        # 去除“文本”这类无意义的图片alt文本
        content_md = re.sub(r'!\[文本\]\([^)]+\)', '', content_md)
        # 去除多余空行
        content_md = re.sub(r'\n{3,}', '\n\n', content_md)
        content_md = re.sub(r'^(#{1,6})([^#\n])', r'-\2', content_md, flags=re.MULTILINE)
        link_line = f'\n[查看原答案]({answer_url})\n' if answer_url else ''
        block = f'## 答案{idx} | 作者：{author} | 赞同：{vote}\n{link_line}\n{content_md}'
        answer_blocks.append(block.strip())
        idx += 1
    if answer_blocks:
        md_lines.append(('\n\n---\n\n').join(answer_blocks))
    with open(save_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(md_lines).strip() + '\n')
    print(f'Saved: {save_path}')
    return save_path

class QuestionsFileHandler(FileSystemEventHandler):
    def __init__(self, file_path, process_func):
        super().__init__()
        self.file_path = file_path
        self.process_func = process_func
        self.lock = threading.Lock()
        self.last_content = None

    def on_modified(self, event):
        if event.src_path.replace('\\', '/') == os.path.abspath(self.file_path).replace('\\', '/'):  # 兼容windows路径
            with self.lock:
                try:
                    with open(self.file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if content != self.last_content:
                        self.last_content = content
                        print('检测到 Questions.md 变动，开始处理...')
                        self.process_func()
                except Exception as e:
                    print(f'监听处理异常: {e}')

def process_questions_md():
    input_file = 'md/房地产/Questions.md'
    cookies_path = 'cookies.txt'
    processed_marker = '【已处理】'
    if not os.path.exists(input_file):
        print(f'未找到 {input_file}')
        return
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # 收集所有已处理过的问题（用问题标题和链接做唯一性标识）
    processed_set = set()
    for line in lines:
        if '\t' in line and processed_marker in line:
            question, url = line.strip().split('\t', 1)
            url = url.replace(processed_marker, '').strip()
            processed_set.add((question, url))
    new_lines = []
    updated = False
    for line in lines:
        if '\t' in line and processed_marker not in line:
            question, url = line.strip().split('\t', 1)
            # 检查是否已处理过同样的问题
            if (question, url) in processed_set:
                print(f'问题已处理过，直接标记：{question} ({url})')
                new_lines.append(line.rstrip() + f' {processed_marker}\n')
                updated = True
                break  # 只处理一个，处理完等下次触发
            print(f'抓取: {question} ({url})')
            try:
                title, answers = fetch_zhihu_answers_by_browser(url, min_vote=50, cookies_path=cookies_path)
                if answers:
                    save_answers_md_browser(title, answers)
                    new_lines.append(line.rstrip() + f' {processed_marker}\n')
                else:
                    print(f'无高赞答案: {url}')
                    new_lines.append(line)
            except Exception as e:
                print(f'抓取异常: {e}')
                new_lines.append(line)
            updated = True
            break  # 只处理一个，处理完等下次触发
        else:
            new_lines.append(line)
    if updated:
        with open(input_file, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print('已写回 Questions.md，等待下次变动或继续处理...')

class TopicFileHandler(FileSystemEventHandler):
    def __init__(self, topic_md_path, topic_name, out_dir):
        super().__init__()
        self.topic_md_path = os.path.abspath(topic_md_path)
        self.topic_name = topic_name
        self.out_dir = out_dir
        self.lock = threading.Lock()

    def _handle_event(self, event, event_type):
        print(f'[DEBUG] 事件: {event_type}, src_path={event.src_path}, 监听目标={self.topic_md_path}', flush=True)
        try:
            if os.path.exists(event.src_path) and os.path.exists(self.topic_md_path):
                same = os.path.samefile(event.src_path, self.topic_md_path)
            else:
                same = False
        except Exception as e:
            print(f'[DEBUG] samefile判断异常: {e}', flush=True)
            same = False
        if same:
            with self.lock:
                try:
                    print(f'[监听] 文件{event_type}: {event.src_path}', flush=True)
                    time.sleep(0.3)
                    process_topic_md(self.topic_md_path, self.topic_name, self.out_dir)
                except Exception as e:
                    print(f'监听处理异常: {e}', flush=True)

    def on_modified(self, event):
        self._handle_event(event, '被修改')
    def on_created(self, event):
        self._handle_event(event, '被创建')
    def on_moved(self, event):
        self._handle_event(event, '被移动')
    def on_closed(self, event):
        self._handle_event(event, '被关闭')

def process_topic_md(md_path, topic_name, out_dir):
    processed_marker = '【已处理】'
    if not os.path.exists(md_path):
        print(f'未找到 {md_path}')
        return
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # 用知乎问题ID做唯一性去重
    processed_ids = set()
    for line in lines:
        if '\t' in line and processed_marker in line:
            question, url = line.strip().split('\t', 1)
            url = url.replace(processed_marker, '').strip()
            qid = get_question_id(url)
            if qid:
                processed_ids.add(qid)
    new_lines = []
    updated = False
    for line in lines:
        if '\t' in line and processed_marker not in line:
            question, url = line.strip().split('\t', 1)
            qid = get_question_id(url)
            if qid and qid in processed_ids:
                print(f'问题已处理过（ID去重），直接标记：{question} ({url})')
                new_lines.append(line.rstrip() + f' {processed_marker}\n')
                updated = True
                break
            print(f'抓取: {question} ({url})')
            try:
                title, answers = fetch_zhihu_answers_by_browser(url, min_vote=50, cookies_path="cookies.txt")
                if answers:
                    save_answers_md_browser(title, answers, out_dir=out_dir)
                    new_lines.append(line.rstrip() + f' {processed_marker}\n')
                else:
                    print(f'无高赞答案: {url}')
                    new_lines.append(line)
            except Exception as e:
                print(f'抓取异常: {e}')
                new_lines.append(line)
            updated = True
            break
        else:
            new_lines.append(line)
    if updated:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f'已写回 {md_path}，等待下次变动或继续处理...')

def ensure_topic_folder(topic_name):
    out_dir = os.path.join('md', topic_name)
    os.makedirs(out_dir, exist_ok=True)
    return out_dir

def scan_and_watch_topics():
    question_lib_dir = os.path.join('md', '问题库')
    observer = Observer()
    handler_map = {}
    print('扫描并监听md/问题库下所有话题...')
    # 启动时先主动处理所有已有话题文档中的未处理问题
    for fname in os.listdir(question_lib_dir):
        if fname.startswith('Question_') and fname.endswith('.md'):
            topic_name = fname[len('Question_'):-3]
            topic_md_path = os.path.join(question_lib_dir, fname)
            out_dir = ensure_topic_folder(topic_name)
            # 启动时主动处理一次
            process_topic_md(topic_md_path, topic_name, out_dir)
            handler = TopicFileHandler(topic_md_path, topic_name, out_dir)
            observer.schedule(handler, path=question_lib_dir, recursive=False)
            handler_map[topic_md_path] = handler
            print(f'已监听: {topic_md_path} -> 导出目录: {out_dir}')
    observer.start()
    print('已启动所有话题监听，等待变动...')
    try:
        while True:
            # 检查是否有新话题文件加入
            for fname in os.listdir(question_lib_dir):
                if fname.startswith('Question_') and fname.endswith('.md'):
                    topic_name = fname[len('Question_'):-3]
                    topic_md_path = os.path.join(question_lib_dir, fname)
                    if topic_md_path not in handler_map:
                        out_dir = ensure_topic_folder(topic_name)
                        # 新增话题也要先处理一次
                        process_topic_md(topic_md_path, topic_name, out_dir)
                        handler = TopicFileHandler(topic_md_path, topic_name, out_dir)
                        observer.schedule(handler, path=question_lib_dir, recursive=False)
                        handler_map[topic_md_path] = handler
                        print(f'新增监听: {topic_md_path} -> 导出目录: {out_dir}')
            time.sleep(3)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    scan_and_watch_topics()
