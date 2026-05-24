import os
import time
import random
import requests
from bs4 import BeautifulSoup

# 1. 基础伪装：请求头伪装，带上完整 User-Agent 模拟浏览器行为，必要时可加上cookie模拟已登录的浏览器行为
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
}

# 设定本地持久化存储的目录
SAVE_DIR = "downloaded_pages"

def setup_env():
    """初始化存储目录"""
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

def get_url_list(filename):
    """获取 URL 列表：要求能够自动获取URL列表文本文件中的所有页面"""
    if not os.path.exists(filename):
        print(f"错误: 找不到文件 {filename}。请先创建该文件并填入URL。")
        return []
    
    with open(filename, 'r', encoding='utf-8') as f:
        # 去除空白行和换行符
        urls = [line.strip() for line in f if line.strip()]
    return urls

def download_and_save(url, index):
    """下载文件并进行本地持久化存储"""
    try:
        print(f"正在获取: {url}")
        # 向目标URL发送 HTTP GET 请求 
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        # 检查返回状态码是否异常（如403, 404等）
        response.raise_for_status()

        # 编码问题处理：主动设置 response.encoding 属性防止乱码 
        response.encoding = response.apparent_encoding

        # 利用 BeautifulSoup 解析 HTML 
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 尝试获取网页标题作为文件名，若无标题则使用序号命名
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            # 过滤掉文件名中不允许的特殊字符
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
        else:
            safe_title = f"page_{index}"
            
        if not safe_title:
            safe_title = f"page_{index}"

        # 将下载到的内容保存到本地计算机的指定目录中
        file_path = os.path.join(SAVE_DIR, f"{safe_title}.html")
        
        # 以指定的文件名和扩展名打开本地文件，并写入内容
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
            
        print(f"成功保存至: {file_path}")

    except requests.exceptions.RequestException as e:
        print(f"请求失败 {url}: {e}")
    except Exception as e:
        print(f"处理 {url} 时发生未知错误: {e}")

def main():
    setup_env()
    
    # 获取当前 spider.py 脚本所在的绝对目录路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 将目录路径和文件名拼接成完整的绝对路径
    url_file = os.path.join(current_dir, 'urls.txt')
    
    urls = get_url_list(url_file)
    
    if not urls:
        print("URL列表为空或文件不存在，程序退出。")
        return
        
    print(f"共加载了 {len(urls)} 个URL待处理。")
    
    for i, url in enumerate(urls, 1):
        download_and_save(url, i)
        
        if i < len(urls):
            # IP 控制：控制请求频率，加随机延时 [cite: 309, 310]
            delay = random.uniform(0.5, 2)
            print(f"随机休眠 {delay:.2f} 秒以防止触发反爬机制...")
            time.sleep(delay)

if __name__ == '__main__':
    main()