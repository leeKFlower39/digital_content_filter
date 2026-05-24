import jieba
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

def load_stopwords(path):
    """通用停用词加载"""
    stopwords = set()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(',')
                for p in parts:
                    if p.strip(): stopwords.add(p.strip())
    except: pass
    return stopwords

def preprocess_general(text, stopwords):
    """
    具备普遍性的通用预处理逻辑：
    1. 仅捕获广泛意义上的中文否定翻转语义。
    2. 仅对跨行业全通用的绝对核心修饰词进行提权，绝不包含任何特定领域的实体名词。
    """
    words = jieba.lcut(text)
    
    # 全行业通用的标准否定词
    neg_words = {'不', '没', '无', '非', '未', '没有', '不值', '不值得', '毫无'}
    
    # 跨领域通用的绝对核心倾向性副词与形容词（不含任何如“剧本”或“画面”的名词）
    universal_modifiers = {'极其', '完全', '简直', '纯粹', '及其', '非常', '特别', '糟糕', '垃圾', '恶心', '失败', '极差'}
    
    new_words = []
    skip_next = False
    
    for i in range(len(words)):
        if skip_next:
            skip_next = False
            continue
        word = words[i]
        
        # 1. 否定词翻转（普遍语法规则）
        if word in neg_words and i + 1 < len(words):
            next_word = words[i+1]
            if next_word not in stopwords and len(next_word.strip()) > 1:
                new_words.append(f"NOT_{next_word}")
                skip_next = True
            else:
                new_words.append(word)
                
        # 2. 常规文本清洗
        elif word not in stopwords and len(word.strip()) > 1:
            new_words.append(word)
            # 普适性提权：仅针对全行业绝对中性的强烈程度词进行概率强调
            if word in universal_modifiers:
                new_words.extend([word] * 2) 
                
    return " ".join(new_words)

def train_model():
    stopwords = load_stopwords("stopwords.txt")
    
    train_texts, y_train = [], []
    # 纯粹读取你通过爬虫抓取的原生原始数据
    for file, label in [("train_pos.txt", 1), ("train_neg.txt", 0)]:
        with open(file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    train_texts.append(preprocess_general(line.strip(), stopwords))
                    y_train.append(label)

    # 响应 PPT 核心要求：通过调整 VSM 的 DF 阈值，依靠统计学过滤高频和低频噪音
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 3),   # 允许贝叶斯算法自动捕捉短语级的上下文依赖
        max_df=0.6,           # 超过 60% 文档出现的词视为无倾向性的“领域通用中性噪音”自动过滤
        min_df=2,             # 出现次数少于 2 次的错别字或极端生僻词自动过滤
        sublinear_tf=True
    )
    
    X_train_vec = vectorizer.fit_transform(train_texts)

    # 部署多项式朴素贝叶