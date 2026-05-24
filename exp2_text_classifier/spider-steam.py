import requests
import urllib.parse
import time
import os

# 配置本地代理
PROXIES = {
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890"
}

# 目标：选取三个评价基数极大的游戏
# 1091500: 赛博朋克 2077
# 730: Counter-Strike 2
# 271590: Grand Theft Auto V
APP_IDS = ["1091500", "730", "271590"]

# 为了达到总计3000条的目标，3个游戏每个各抓取1000条
TARGET_COUNT_PER_GAME = 1000
# 字数限制
MAX_LENGTH = 50

def fetch_steam_reviews(app_id, review_type, filename):
    """
    根据指定类型和游戏ID抓取 Steam 评测并追加保存
    :param app_id: 游戏 APP_ID
    :param review_type: 'positive' (好评) 或 'negative' (差评)
    :param filename: 保存的文件名
    """
    # Steam API 的初始游标为 "*"
    cursor = "*"
    count = 0
    
    print(f"\n--- 开始抓取游戏 {app_id} 的 {review_type.upper()} 数据 ---")
    
    # 使用追加模式 "a"，让不同游戏的数据可以写入同一个文件
    with open(filename, "a", encoding="utf-8") as f:
        while count < TARGET_COUNT_PER_GAME:
            # 游标中可能包含特殊字符（如 + 号），必须进行 URL 编码
            encoded_cursor = urllib.parse.quote(cursor)
            
            # 构建 API 请求：指定语言为简中，每次拉取 100 条
            url = (f"https://store.steampowered.com/appreviews/{app_id}"
                   f"?json=1&language=schinese&filter=recent"
                   f"&num_per_page=100&review_type={review_type}&cursor={encoded_cursor}")
            
            try:
                response = requests.get(url, proxies=PROXIES, timeout=10)
                data = response.json()
            except Exception as e:
                print(f"网络请求异常: {e}，等待重试...")
                time.sleep(3)
                continue
                
            if data.get("success") != 1:
                print("API 返回异常状态，终止当前任务。")
                break
                
            reviews = data.get("reviews", [])
            if not reviews:
                print("游标到达尽头，没有更多数据。")
                break
                
            for review in reviews:
                if count >= TARGET_COUNT_PER_GAME:
                    break
                    
                # 提取正文，并清除换行符，保证一行一条数据
                content = review.get("review", "").replace("\n", " ").replace("\r", "").strip()
                
                # 【核心修改点】过滤掉内容为空，且字数必须 <= 50 字
                if content and len(content) <= MAX_LENGTH:
                    f.write(content + "\n")
                    count += 1
            
            print(f"游戏 {app_id} - 当前进度: {count} / {TARGET_COUNT_PER_GAME}")
            
            # 获取下一页游标
            next_cursor = data.get("cursor")
            if not next_cursor or next_cursor == cursor:
                print("游标未更新，遍历结束。")
                break
                
            cursor = next_cursor
            
            # 礼貌性延时，避免给服务器造成压力
            time.sleep(2)

def main():
    pos_file = "train_pos.txt"
    neg_file = "train_neg.txt"
    
    # 在运行前如果文件已存在则先删除，避免重复运行导致数据叠加超出3000条
    if os.path.exists(pos_file):
        os.remove(pos_file)
    if os.path.exists(neg_file):
        os.remove(neg_file)

    # 遍历三个游戏
    for app_id in APP_IDS:
        # 1. 抓取好评存入 train_pos.txt
        fetch_steam_reviews(app_id, "positive", pos_file)
        
        # 2. 抓取差评存入 train_neg.txt
        fetch_steam_reviews(app_id, "negative", neg_file)
    
    print("\n任务完成，请检查当前目录下的 train_pos.txt 和 train_neg.txt 文件。")

if __name__ == "__main__":
    main()