# -*- coding: utf-8 -*-
"""
MailGuard 模型训练脚本
功能：
1. 读取 TREC06C 邮件数据集
2. 训练中文垃圾邮件朴素贝叶斯分类模型
3. 输出 Accuracy、Precision、Recall、F1
4. 保存 model.pkl，供 server.py 使用

运行方式一：
    python train_model.py --data-dir "D:\\path\\to\\trec06c"

运行方式二，通过环境变量：
    set MAILGUARD_TREC06C_DIR=D:\\path\\to\\trec06c
    python train_model.py

TREC06C 典型结构：
    trec06c/
        full/index
        data/000/000
        data/000/001
        ...
"""

import argparse
import json
import math
import os
import pickle
import random
import re
from collections import Counter, defaultdict
from pathlib import Path


try:
    import jieba
except ImportError:
    jieba = None


try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = os.environ.get(
    "MAILGUARD_TREC06C_DIR",
    str(BASE_DIR / "trec06c"),
)
DEFAULT_MODEL_OUTPUT = BASE_DIR / "model.pkl"

RANDOM_SEED = 42
TRAIN_RATIO = 0.8
MIN_WORD_LEN = 2


def read_email_content(file_path):
    """
    TREC06C 邮件编码不统一，这里多编码尝试并忽略坏字符，保证训练不中断。
    """
    file_path = Path(file_path)

    encodings = ["gb18030", "gbk", "utf-8", "gb2312", "latin1"]
    content = ""

    for enc in encodings:
        try:
            content = file_path.read_text(encoding=enc, errors="ignore")
            break
        except Exception:
            continue

    content = re.sub(r"(?is)<script.*?>.*?</script>", " ", content)
    content = re.sub(r"(?is)<style.*?>.*?</style>", " ", content)
    content = re.sub(r"(?is)<[^>]+>", " ", content)
    content = re.sub(r"[^\w\u4e00-\u9fa5]+", " ", content)
    content = re.sub(r"\s+", " ", content).strip().lower()
    return content


def tokenize(text):
    if not text:
        return []

    if jieba:
        words = jieba.lcut(text)
    else:
        words = re.findall(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z]{2,}|\d+[a-zA-Z]+", text)

    return [
        word.strip().lower()
        for word in words
        if len(word.strip()) >= MIN_WORD_LEN and not word.strip().isdigit()
    ]


def normalize_label(label):
    label = label.strip().lower()
    if label in {"spam", "1", "junk", "bad"}:
        return "spam"
    return "ham"


def resolve_data_path(data_dir, rel_path):
    """
    index 中常见路径：
        ../data/000/000
        ./data/000/000
        data/000/000
    统一转换到 data_dir/data/xxx。
    """
    rel_path = rel_path.strip().replace("\\", "/")

    while rel_path.startswith("../"):
        rel_path = rel_path[3:]

    if rel_path.startswith("./"):
        rel_path = rel_path[2:]

    if rel_path.startswith("data/"):
        return data_dir / rel_path

    return data_dir / rel_path


def load_dataset(data_dir):
    data_dir = Path(data_dir)
    index_file = data_dir / "full" / "index"

    if not index_file.exists():
        raise FileNotFoundError(f"找不到索引文件：{index_file}")

    dataset = []
    print(f"正在解析索引文件：{index_file}")

    with index_file.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) < 2:
                print(f"跳过格式异常行 {line_no}: {line}")
                continue

            label = normalize_label(parts[0])
            rel_path = parts[1]
            abs_path = resolve_data_path(data_dir, rel_path)

            if abs_path.exists():
                dataset.append((label, abs_path))
            else:
                # 有些数据集路径会出现 ../data，而实际在 full/../data
                alt_path = (data_dir / "full" / rel_path).resolve()
                if alt_path.exists():
                    dataset.append((label, alt_path))
                else:
                    print(f"邮件文件不存在，已跳过：{abs_path}")

    if not dataset:
        raise RuntimeError("没有读取到任何邮件，请检查 TREC06C 路径。")

    label_counter = Counter(label for label, _ in dataset)
    print(f"共读取 {len(dataset)} 封邮件：spam={label_counter.get('spam', 0)}，ham={label_counter.get('ham', 0)}")
    return dataset


def train_model(train_set):
    spam_word_counts = defaultdict(int)
    ham_word_counts = defaultdict(int)

    spam_total_words = 0
    ham_total_words = 0
    spam_docs = 0
    ham_docs = 0
    vocab = set()

    print("\n正在提取特征并训练朴素贝叶斯模型...")

    for label, path in tqdm(train_set, desc="训练进度"):
        content = read_email_content(path)
        words = tokenize(content)

        if not words:
            continue

        if label == "spam":
            spam_docs += 1
            for word in words:
                spam_word_counts[word] += 1
                spam_total_words += 1
                vocab.add(word)
        else:
            ham_docs += 1
            for word in words:
                ham_word_counts[word] += 1
                ham_total_words += 1
                vocab.add(word)

    if spam_docs == 0 or ham_docs == 0:
        raise RuntimeError("训练集中 spam 或 ham 数量为 0，无法训练二分类模型。")

    vocab_size = len(vocab)
    p_spam = spam_docs / (spam_docs + ham_docs)

    print("\n正在预计算拉普拉斯平滑后的对数概率...")

    log_p_word_spam = {}
    log_p_word_ham = {}

    for word in tqdm(vocab, desc="概率计算"):
        prob_spam = (spam_word_counts[word] + 1) / (spam_total_words + vocab_size)
        prob_ham = (ham_word_counts[word] + 1) / (ham_total_words + vocab_size)

        log_p_word_spam[word] = math.log(prob_spam)
        log_p_word_ham[word] = math.log(prob_ham)

    model_data = {
        "log_p_spam": math.log(p_spam),
        "log_p_ham": math.log(1 - p_spam),
        "log_p_word_spam": log_p_word_spam,
        "log_p_word_ham": log_p_word_ham,
        "vocab_size": vocab_size,
        "spam_total_words": spam_total_words,
        "ham_total_words": ham_total_words,
        "spam_docs": spam_docs,
        "ham_docs": ham_docs,
    }

    print(f"训练完成：spam_docs={spam_docs}, ham_docs={ham_docs}, vocab_size={vocab_size}")
    return model_data


def predict(model_data, content):
    words = tokenize(content)
    if not words:
        return "ham", 0.0

    score_spam = model_data["log_p_spam"]
    score_ham = model_data["log_p_ham"]

    vocab_size = max(model_data["vocab_size"], 1)
    spam_total_words = max(model_data["spam_total_words"], 1)
    ham_total_words = max(model_data["ham_total_words"], 1)

    default_log_p_spam = math.log(1 / (spam_total_words + vocab_size))
    default_log_p_ham = math.log(1 / (ham_total_words + vocab_size))

    log_p_word_spam = model_data["log_p_word_spam"]
    log_p_word_ham = model_data["log_p_word_ham"]

    for word in words:
        score_spam += log_p_word_spam.get(word, default_log_p_spam)
        score_ham += log_p_word_ham.get(word, default_log_p_ham)

    diff = max(min(score_spam - score_ham, 500), -500)
    probability = 1 / (1 + math.exp(-diff))
    label = "spam" if score_spam > score_ham else "ham"
    return label, probability


def evaluate_model(model_data, validation_set):
    print("\n正在使用验证集评估模型效果...")

    TP = FP = TN = FN = 0

    for label, path in tqdm(validation_set, desc="验证进度"):
        content = read_email_content(path)
        predict_label, _ = predict(model_data, content)

        if predict_label == "spam" and label == "spam":
            TP += 1
        elif predict_label == "spam" and label == "ham":
            FP += 1
        elif predict_label == "ham" and label == "ham":
            TN += 1
        elif predict_label == "ham" and label == "spam":
            FN += 1

    total = TP + FP + TN + FN
    accuracy = (TP + TN) / total if total else 0
    precision = TP / (TP + FP) if (TP + FP) else 0
    recall = TP / (TP + FN) if (TP + FN) else 0
    f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

    print("\n" + "=" * 46)
    print("模型性能评估报告")
    print("=" * 46)
    print(f"总验证样本数:        {total}")
    print(f"TP 垃圾判垃圾:       {TP}")
    print(f"FP 正常被误杀:       {FP}")
    print(f"TN 正常判正常:       {TN}")
    print(f"FN 垃圾漏判正常:     {FN}")
    print("-" * 46)
    print(f"准确率 Accuracy:     {accuracy * 100:.2f}%")
    print(f"精确率 Precision:    {precision * 100:.2f}%")
    print(f"召回率 Recall:       {recall * 100:.2f}%")
    print(f"F1-Measure:          {f1_score * 100:.2f}%")
    print("=" * 46)

    return {
        "total": total,
        "TP": TP,
        "FP": FP,
        "TN": TN,
        "FN": FN,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
    }


def train_and_evaluate(data_dir, model_output, train_ratio=TRAIN_RATIO):
    dataset = load_dataset(data_dir)

    random.seed(RANDOM_SEED)
    random.shuffle(dataset)

    split_idx = int(len(dataset) * train_ratio)
    train_set = dataset[:split_idx]
    validation_set = dataset[split_idx:]

    print(f"划分数据集：训练集 {len(train_set)} 封，验证集 {len(validation_set)} 封。")

    model_data = train_model(train_set)
    metrics = evaluate_model(model_data, validation_set)

    model_output = Path(model_output)
    with model_output.open("wb") as f:
        pickle.dump(model_data, f)

    print(f"\n模型已保存：{model_output}")

    metrics_file = model_output.with_suffix(".metrics.json")
    metrics_file.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"评估指标已保存：{metrics_file}")


def parse_args():
    parser = argparse.ArgumentParser(description="MailGuard 朴素贝叶斯垃圾邮件模型训练脚本")
    parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        help="TREC06C 数据集根目录，例如 D:\\...\\trec06c",
    )
    parser.add_argument(
        "--model-output",
        default=str(DEFAULT_MODEL_OUTPUT),
        help="模型输出路径，默认当前目录 model.pkl",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=TRAIN_RATIO,
        help="训练集比例，默认 0.8",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train_and_evaluate(
        data_dir=args.data_dir,
        model_output=args.model_output,
        train_ratio=args.train_ratio,
    )
