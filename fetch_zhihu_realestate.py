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
import psutil

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
        browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled', '--start-minimized'])
        context = browser.new_context()
        cookies = load_cookies_from_txt(cookies_path)
        if cookies:
            context.add_cookies(cookies)
        page = context.new_page()
        time.sleep(1)
        def minimize_latest_chrome_window():
            import psutil
            from pywinauto import Desktop
            chrome_procs = [p for p in psutil.process_iter(['name', 'pid', 'create_time']) if p.info.get('name') and 'chrome' in p.info.get('name').lower()]
            if not chrome_procs:
                return
            latest_proc = max(chrome_procs, key=lambda p: p.info.get('create_time', 0))
            target_pid = latest_proc.info['pid']
            for w in Desktop(backend='uia').windows():
                try:
                    if w.process_id() == target_pid:
                        w.minimize()
                except Exception:
                    continue
        try:
            minimize_latest_chrome_window()
        except Exception as e:
            print('窗口最小化失败:', e)
        page.goto(url, timeout=60000)
        # 判断是否为大V回答列表页
        dav_pattern = re.compile(r'/people/[^/]+/answers/?$')
        is_dav = bool(dav_pattern.search(url))
        if is_dav:
            page.wait_for_selector('div.List-item', timeout=15000)
            dav_question_ids = set()
            last_questions_snapshot = None
            unchanged_start_time = None
            for _ in range(120):
                page.mouse.wheel(0, 8000)
                time.sleep(0.1)
                page.mouse.wheel(0, -3200)
                time.sleep(0.1)
                page.mouse.wheel(0, 4800)
                time.sleep(0.1)
                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')
                current_questions_snapshot = set()
                for ans_div in soup.select('div.List-item'):
                    url_meta = None
                    for meta in ans_div.select('meta[itemprop="url"]'):
                        if meta.find_parent(class_='ContentItem-meta') is None:
                            url_meta = meta
                            break
                    answer_url = url_meta['content'] if url_meta and url_meta.has_attr('content') else ''
                    m = re.search(r'/question/(\d+)', answer_url)
                    if m:
                        current_questions_snapshot.add(m.group(1))
                # 新增：问题数超过200或页面10秒无变化即停止
                if len(current_questions_snapshot) >= 200:
                    print(f'大V页面已加载{len(current_questions_snapshot)}个问题，自动结束抓取')
                    break
                if last_questions_snapshot == current_questions_snapshot:
                    if unchanged_start_time is None:
                        unchanged_start_time = time.time()
                    elif time.time() - unchanged_start_time > 10:
                        print('大V页面10秒无新问题变化，自动结束抓取')
                        break
                else:
                    last_questions_snapshot = current_questions_snapshot.copy()
                    unchanged_start_time = None
            # 批量点击所有“阅读全文”按钮
            print('批量点击所有“阅读全文”按钮...')
            try:
                btns = page.query_selector_all('.Button.ContentItem-more')
                for b in btns:
                    if b.is_visible():
                        try:
                            b.click()
                            time.sleep(0.15)
                        except Exception:
                            continue
                time.sleep(1.5)
            except Exception as e:
                print(f'批量展开全文异常: {e}')
            # 重新解析所有答案内容
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            answers = []
            author_name = None
            name_tag = soup.select_one('span.ProfileHeader-name')
            if name_tag:
                author_name = name_tag.text.strip()
            else:
                author_name = '大V用户'
            for ans_div in soup.select('div.List-item'):
                try:
                    upvote_meta = ans_div.select_one('meta[itemprop="upvoteCount"]')
                    vote = int(upvote_meta['content']) if upvote_meta and upvote_meta.has_attr('content') else 0
                    content_tag = ans_div.select_one('div.RichContent-inner')
                    content_html = str(content_tag) if content_tag else ''
                    # 去除文字超链
                    content_html = re.sub(r'<a[^>]+>([^<]+)</a>', r'\1', content_html)
                    url_meta = None
                    for meta in ans_div.select('meta[itemprop="url"]'):
                        if meta.find_parent(class_='ContentItem-meta') is None:
                            url_meta = meta
                            break
                    answer_url = url_meta['content'] if url_meta and url_meta.has_attr('content') else ''
                    q_title_meta = ans_div.select_one('.ContentItem-title meta[itemprop="name"]')
                    question_title = q_title_meta['content'].strip() if q_title_meta and q_title_meta.has_attr('content') else ''
                    answers.append({'author': author_name, 'voteup_count': vote, 'content': content_html, 'url': answer_url, 'question_title': question_title})
                except Exception:
                    continue
            answers.sort(key=lambda x: x['voteup_count'], reverse=True)
            browser.close()
            return author_name, answers
        else:
            # 普通问题页逻辑（原有）
            page.wait_for_selector('h1.QuestionHeader-title', timeout=15000)
            answers = []
            answer_ids = set()
            for _ in range(60):
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
                            time.sleep(0.2)
                        else:
                            break
                except Exception:
                    pass
                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')
                new_low_vote = 0
                current_answers_snapshot = []
                for ans_div in soup.select('div.List-item'):
                    try:
                        upvote_meta = ans_div.select_one('meta[itemprop="upvoteCount"]')
                        vote = int(upvote_meta['content']) if upvote_meta and upvote_meta.has_attr('content') else 0
                        content_tag = ans_div.select_one('div.RichContent-inner')
                        content_html = str(content_tag) if content_tag else ''
                        ans_id = hash(content_html)
                        current_answers_snapshot.append(ans_id)
                        if ans_id in answer_ids:
                            continue
                        answer_ids.add(ans_id)
                        url_meta = None
                        for meta in ans_div.select('meta[itemprop="url"]'):
                            if meta.find_parent(class_='ContentItem-meta') is None:
                                url_meta = meta
                                break
                        answer_url = url_meta['content'] if url_meta and url_meta.has_attr('content') else ''
                        question_title = None
                        q_title_meta = ans_div.select_one('meta[itemprop="name"]')
                        if q_title_meta and q_title_meta.has_attr('content'):
                            question_title = q_title_meta['content'].strip()
                        else:
                            q_title_tag = ans_div.select_one('a.QuestionItem-title, h2.QuestionItem-title, h2.QuestionItem-title-text')
                            if q_title_tag:
                                question_title = q_title_tag.text.strip()
                            else:
                                m = re.search(r'/question/\d+/([^/?#]+)', answer_url)
                                if m:
                                    question_title = m.group(1).replace('-', ' ')
                        if vote >= min_vote:
                            answers.append({'author': '匿名用户', 'voteup_count': vote, 'content': content_html, 'url': answer_url, 'question_title': question_title or ''})
                            new_low_vote = 0
                        else:
                            new_low_vote += 1
                    except Exception as e:
                        continue
                if new_low_vote >= 3:
                    print(f'连续{new_low_vote}个新答案低于{min_vote}赞，提前停止滚动加载')
                    break
            answers.sort(key=lambda x: x['voteup_count'], reverse=True)
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
        vote = ans.get('voteup_count', 0)
        content_html = ans.get('content', '')
        question_title = ans.get('question_title', '')
        content_md = md(content_html, heading_style='ATX')
        content_md = re.sub(r'(?<!\!)\[([^\]]+)\]\([^\)]+\)', r'\1', content_md)
        content_md = re.sub(r'!\[]\(data:image/[^)]+\)', '', content_md)
        content_md = re.sub(r'!\[文本\]\([^)]+\)', '', content_md)
        content_md = re.sub(r'\n{3,}', '\n\n', content_md)
        content_md = re.sub(r'^(#{1,6})([^#\n])', r'-\2', content_md, flags=re.MULTILINE)
        content_md = re.sub(r'^(\s*)(---|\*\*\*|___)(\s*)$', '', content_md, flags=re.MULTILINE)
        link_line = f'\n[查看原答案]({answer_url})\n' if answer_url else ''
        block = f'## 问题{idx} | {question_title} | 赞同：{vote}\n{link_line}\n{content_md}'
        answer_blocks.append(block.strip())
        idx += 1
    if answer_blocks:
        md_lines.append(('\n\n---\n\n').join(answer_blocks))
    try:
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(md_lines).strip() + '\n')
        print(f'Saved: {save_path}')
    except Exception as e:
        print(f'保存失败: {save_path}, 异常: {e}')
    return save_path

class QuestionsFileHandler(FileSystemEventHandler):
    def __init__(self, file_path, process_func, observer=None):
        super().__init__()
        self.file_path = file_path
        self.process_func = process_func
        self.lock = threading.Lock()
        self.last_content = None
        self.observer = observer  # 新增：保存observer引用

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
    # 获取当前observer和handler
    global questions_handler, questions_observer
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
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
            if (question, url) in processed_set:
                print(f'问题已处理过，直接标记：{question} ({url})')
                new_lines.append(line.rstrip() + f' {processed_marker}\n')
                updated = True
                break
            print(f'抓取: {question} ({url})')
            try:
                title, answers = fetch_zhihu_answers_by_browser(url, min_vote=50, cookies_path=cookies_path)
                if answers:
                    save_answers_md_browser(title, answers)
                    new_lines.append(line.rstrip() + f' {processed_marker}\n')
                else:
                    print(f'无高赞答案: {url}')
                    new_lines.append(line.rstrip() + f' {processed_marker}\n')
            except Exception as e:
                print(f'抓取异常: {e}')
                new_lines.append(line)
            updated = True
            break
        else:
            new_lines.append(line)
    if updated:
        # 写回前关闭监听
        if 'questions_observer' in globals() and 'questions_handler' in globals():
            try:
                questions_observer.unschedule(questions_handler)
            except Exception as e:
                print(f'关闭监听异常: {e}')
        with open(input_file, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print('已写回 Questions.md，等待下次变动或继续处理...')
        # 写回后恢复监听
        if 'questions_observer' in globals() and 'questions_handler' in globals():
            try:
                questions_observer.schedule(questions_handler, path=os.path.dirname(input_file), recursive=False)
            except Exception as e:
                print(f'恢复监听异常: {e}')

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

# 全局文件锁字典
file_locks = {}
file_locks_lock = threading.Lock()

def get_file_lock(file_path):
    with file_locks_lock:
        if file_path not in file_locks:
            file_locks[file_path] = threading.Lock()
        return file_locks[file_path]

def process_topic_md(md_path, topic_name, out_dir):
    processed_marker = '【已处理】'
    if not os.path.exists(md_path):
        print(f'未找到 {md_path}')
        return
    file_lock = get_file_lock(md_path)
    with file_lock:
        # 读取当前所有行，找到第一个未处理的
        with open(md_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        processed_ids = set()
        for line in lines:
            if '\t' in line and processed_marker in line:
                question, url = line.strip().split('\t', 1)
                url = url.replace(processed_marker, '').strip()
                qid = get_question_id(url)
                if qid:
                    processed_ids.add(qid)
        # 找到第一个未处理的行内容
        target_line = None
        for line in lines:
            if '\t' in line and processed_marker not in line:
                target_line = line.rstrip('\n')
                break
        if not target_line:
            return  # 没有未处理的
        # 处理目标行
        question, url = target_line.strip().split('\t', 1)
        qid = get_question_id(url)
        updated_line = None
        # 新增：交易类别点赞数阈值降低到15
        min_vote = 15 if topic_name == '交易' else 50
        if qid and qid in processed_ids:
            print(f'问题已处理过（ID去重），直接标记：{question} ({url})')
            updated_line = target_line + f' {processed_marker}\n'
        else:
            print(f'抓取: {question} ({url})')
            try:
                title, answers = fetch_zhihu_answers_by_browser(url, min_vote=min_vote, cookies_path="cookies.txt")
                if answers:
                    save_answers_md_browser(title, answers, out_dir=out_dir)
                    updated_line = target_line + f' {processed_marker}\n'
                else:
                    print(f'无高赞答案: {url}')
                    updated_line = target_line + f' {processed_marker}\n'
            except Exception as e:
                print(f'抓取异常: {e}')
                updated_line = target_line + '\n'
        # 写回前重新读取文件，精确查找并更新该行
        with open(md_path, 'r', encoding='utf-8') as f:
            latest_lines = f.readlines()
        for idx, line in enumerate(latest_lines):
            if line.rstrip('\n') == target_line:
                latest_lines[idx] = updated_line
                break
        with open(md_path, 'w', encoding='utf-8') as f:
            f.writelines(latest_lines)
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
