import re

def insert_new_line(soup, element, num_breaks):
    """
    在指定位置插入换行符
    """
    for _ in range(num_breaks):
        new_line = soup.new_tag('br')
        element.insert_after(new_line)


def get_article_date(soup, name):
    """
    从页面中提取文章日期
    """
    date_element = soup.select_one(name)
    if date_element:
        match = re.search(r"\d{4}-\d{2}-\d{2}", date_element.get_text())
        if match:
            return match.group().replace('-', '')
    return "Unknown"


def get_article_date_csdn(date_element):
    """
    从页面中提取文章日期
    """
    match = re.search(r"\d{4}-\d{2}-\d{2}", date_element.get_text())
    if match:
        return match.group().replace('-', '')
    return "Unknown"


def get_article_date_weixin(date_element):
    """
    从页面中提取文章日期
    """
    for script in date_element:
        # 获取 JavaScript 代码
        js_code = script.string
        if js_code:
            # 尝试提取 createTime
            match = re.search(r"\d{4}-\d{2}-\d{2}", js_code)
            if match:
                return match.group().replace('-', '')
    return "Unknown"


def download_image(url, save_path, session):
    """
    从指定url下载图片并保存到本地
    """
    if url.startswith("data:image/"):
        # 如果链接以 "data:" 开头，则直接写入数据到文件
        with open(save_path, "wb") as f:
            f.write(url.split(",", 1)[1].encode("utf-8"))
    else:
        response = session.get(url)
        with open(save_path, "wb") as f:
            f.write(response.content)


def download_video(url, save_path, session):
    """
    从指定url下载视频并保存到本地
    """
    response = session.get(url)
    with open(save_path, "wb") as f:
        f.write(response.content)


def get_valid_filename(s):
    """
    将字符串转换为有效的文件名，去除 Windows 不允许的字符
    """
    s = str(s).strip().replace(' ', '_')
    # Windows 文件名非法字符: \\/:*?"<>|
    s = re.sub(r'[\\/:*?"<>|]', '', s)
    # 还可以进一步去除其他不可见字符
    s = re.sub(r'[\x00-\x1f]', '', s)
    # 防止全为空
    return s or 'untitled'
