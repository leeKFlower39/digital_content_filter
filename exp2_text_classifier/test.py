import jieba
import joblib
from sklearn.metrics import accuracy_score, classification_report

def load_stopwords(path):
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
    """保持与训练脚本严格一致的普适性清洗逻辑"""
    words = jieba.lcut(text)
    neg_words = {'不', '没', '无', '非', '未', '没有', '不值', '不值得', '毫无'}
    universal_modifiers = {'极其', '完全', '简直', '纯粹', '及其', '非常', '特别', '糟糕', '垃圾', '恶心', '失败', '极差'}
    
    new_words = []
    skip_next = False
    
    for i in range(len(words)):
        if skip_next:
            skip_next = False
            continue
        word = words[i]
        
        if word in neg_words and i + 1 < len(words):
            next_word = words[i+1]
            if next_word not in stopwords and len(next_word.strip()) > 1:
                new_words.append(f"NOT_{next_word}")
                skip_next = True
            else:
                new_words.append(word)
        elif word not in stopwords and len(word.strip()) > 1:
            new_words.append(word)
            if word in universal_modifiers:
                new_words.extend([word] * 2) 
    return " ".join(new_words)

def run_test():
    print("🚀 正在启动具备通用泛化能力的跨领域测试评估...")
    stopwords = load_stopwords("stopwords.txt")
    vectorizer = joblib.load('tfidf_model.pkl')
    clf = joblib.load('nb_model.pkl')

    y_true = [1] * 100 + [0] * 100
    y_pred = []
    
    with open("test.txt", "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
        for i, line in enumerate(lines[:200]):
            clean_text = preprocess_general(line, stopwords)
            X_vec = vectorizer.transform([clean_text])
            res = clf.predict(X_vec)[0]
            y_pred.append(res)
            
            label = "正面" if res == 1 else "负面"
            print(f"L{i+1:03}: {line[:20]}... | 逻辑转换: [{clean_text}] -> 【{label}】")

    print("\n" + "="*30 + " 普适性分类性能报告 " + "="*30)
    print(f"最终真实准确率: {accuracy_score(y_true, y_pred) * 100:.2f}%")
    print(classification_report(y_true, y_pred, target_names=['负面', '正面']))

if __name__ == "__main__":
    run_test()