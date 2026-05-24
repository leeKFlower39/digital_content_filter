import os
import time
import random
import requests
from bs4 import BeautifulSoup

# 1. 基础伪装：请求头伪装，带上完整 User-Agent 和 Cookie 模拟已登录的浏览器行为
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://movie.douban.com/',
    'Cookie': 'bid=LLlwe8O1ry0; ap_v=0,6.0; __utmc=30149280; __utma=30149280.1624550979.1778825812.1778825812.1778828994.2; __utmz=30149280.1778828994.2.2.utmcsr=baidu|utmccn=(organic)|utmcmd=organic; __utma=223695111.1884619881.1778829008.1778829008.1778829008.1; __utmb=223695111.0.10.1778829008; __utmc=223695111; __utmz=223695111.1778829008.1.1.utmcsr=sec.douban.com|utmccn=(referral)|utmcmd=referral|utmcct=/; _pk_ref.100001.4cf6=%5B%22%22%2C%22%22%2C1778829008%2C%22https%3A%2F%2Fsec.douban.com%2F%22%5D; _pk_id.100001.4cf6=e042cba25994c233.1778829008.; _pk_ses.100001.4cf6=1; ll="108288"; _vwo_uuid_v2=DEA9184EBA48B3825C1357766F45E4C02|b90622961f1d2bd3f54d41372686f9cf; __yadk_uid=kq79W14Yor9pIZpsdCfH3HHZJ5rBkTc4; __utmb=30149280.2.10.1778828994; dbsawcv1=MTc3ODgzMDg2M0BkYTAxMGRlZmNjYTg0NzNhYTJhOTc3NzZmMTViZTQxMDRmZWVhZjllZGQ5MDExZWVlN2M1NmY1NDFmZWQ1OTBkQGEwOGI1NTliMjdiN2FkMThAYTJhYTEyZGYxMzQ4'
}

# 设定本地持久化存储的目录
SAVE_DIR = "downloaded_pages"

def setup_env():
    """初始化存储目录"""
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

def get_url_list(filename):
    """获取 URL 列表：要求能够自动获取URL列表文本文件中的所有页面 [cite: 271]"""
    if not os.path.exists(filename):
        print(f"错误: 找不到文件 {filename}。请先创建该文件并填入URL。")
        return []
    
    with open(filename, 'r', encoding='utf-8') as f:
        # 去除空白行和换行符
        urls = [line.strip() for line in f if line.strip()]
    return urls

def download_and_save(url, index):
    """下载文件并进行本地持久化存储 [cite: 250, 255]"""
    try:
        print(f"正在获取: {url}")
        # 向目标URL发送 HTTP GET 请求 
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        # 检查返回状态码是否异常（如403, 404等） [cite: 284]
        response.raise_for_status()

        # 编码问题处理：主动设置 response.encoding 属性防止乱码 
        response.encoding = response.apparent_encoding

        # 利用 BeautifulSoup 解析 HTML 
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 尝试获取网页标题作为文件名，若无标题则使用序号命名 [cite: 256]
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            # 过滤掉文件名中不允许的特殊字符
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
        else:
            safe_title = f"page_{index}"
            
        if not safe_title:
            safe_title = f"page_{index}"

        # 将下载到的内容保存到本地计算机的指定目录中 [cite: 255]
        file_path = os.path.join(SAVE_DIR, f"{safe_title}.html")
        
        # 以指定的文件名和扩展名打开本地文件，并写入内容 [cite: 257]
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
            
        print(f"成功保存至: {file_path}")

    except requests.exceptions.RequestException as e:
        print(f"请求失败 {url}: {e}")
    except Exception as e:
        print(f"处理 {url} 时发生未知错误: {e}")

def main():
    setup_env()
    
    # 1. 确定你要大规模爬取的电影 ID（例如《肖申克的救赎》是 1292052）
    movie_id = "1292052" 
    
    # 2. 构造豆瓣短评的翻页模版
    # start 参数代表从第几条开始，每页通常 20 条 [cite: 318]
    base_url = "https://movie.douban.com/subject/{}/comments?start={}&limit=20&status=P&sort=new_score"
    
    # 3. 设定爬取页数（例如爬取前 10 页，即 200 条数据）
    max_pages = 10 
    urls = [base_url.format(movie_id, page * 20) for page in range(max_pages)]
    
    print(f"准备进行大规模爬取，目标电影 ID: {movie_id}，共计 {len(urls)} 页。")
    
    for i, url in enumerate(urls, 1):
        # 执行下载与保存 [cite: 250, 255]
        download_and_save(url, i)
        
        # 4. 关键：大规模爬取必须严格控制频率，防止 IP 被封 [cite: 287, 311]
        if i < len(urls):
            # 建议将延时跨度拉大（例如 3 到 8 秒），模拟真人翻页速度 [cite: 311]
            delay = random.uniform(3, 8) 
            print(f"进度: {i}/{len(urls)} | 随机休眠 {delay:.2f} 秒...")
            time.sleep(delay)

    print("\n请在 downloaded_pages 文件夹中查看结果。")

if __name__ == '__main__':
    main()