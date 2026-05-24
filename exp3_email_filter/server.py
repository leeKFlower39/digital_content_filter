# server.py
from flask import Flask, request, jsonify
import pickle
import jieba
import math

app = Flask(__name__)

# 1. 服务器启动时，将训练好的模型加载到内存中
print("正在加载贝叶斯模型，请稍候...")
try:
    with open('model.pkl', 'rb') as f:
        model_data = pickle.load(f)
        
    log_p_spam = model_data['log_p_spam']
    log_p_ham = model_data['log_p_ham']
    log_p_word_spam = model_data['log_p_word_spam']
    log_p_word_ham = model_data['log_p_word_ham']
    
    # 提取未见词的平滑默认值
    default_log_p_spam = math.log(1 / (model_data['spam_total_words'] + model_data['vocab_size']))
    default_log_p_ham = math.log(1 / (model_data['ham_total_words'] + model_data['vocab_size']))
    print("✅ 模型加载成功！邮件过滤网关已启动。")
except FileNotFoundError:
    print("❌ 找不到 model.pkl，请确保你已经运行了训练脚本。")

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    text = data.get("content", "")
    
    if not text.strip():
        return jsonify({"label": "Ham", "confidence": 0.0})

    # 2. 对收到的新邮件进行分词处理
    words = jieba.lcut(text)
    valid_words = [w for w in words if len(w) >= 2 and not w.isdigit()]
    
    # 3. 贝叶斯概率计算
    score_spam = log_p_spam
    score_ham = log_p_ham
    
    for w in valid_words:
        score_spam += log_p_word_spam.get(w, default_log_p_spam)
        score_ham += log_p_word_ham.get(w, default_log_p_ham)
        
    
    # 4. 计算置信度百分比 (使用 Sigmoid 函数将对数差值映射到 0~1 之间)
    diff = score_spam - score_ham
    try:
        diff = max(min(diff, 500), -500)
        prob_spam = 1 / (1 + math.exp(-diff))
    except OverflowError:
        prob_spam = 1.0 if diff > 0 else 0.0

    is_spam = prob_spam > 0.95
        
    confidence = prob_spam if is_spam else (1 - prob_spam)

    # 5. 返回判定结果给前端客户端
    return jsonify({
        "label": "Spam" if is_spam else "Ham",
        "confidence": confidence
    })

if __name__ == "__main__":
    # 启动 Flask 服务器，监听 5000 端口
    app.run(host='127.0.0.1', port=5000)