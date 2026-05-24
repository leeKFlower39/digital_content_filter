# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

MailGuard — 基于内容的电子邮件过滤系统（课程设计）。自定义 SMTP 服务端接收邮件，使用朴素贝叶斯模型进行垃圾邮件分类，Streamlit 客户端提供 Web 邮箱界面。

## 启动命令

```bash
# 训练模型（需要 TREC06C 数据集）
python train_model.py --data-dir "D:\path\to\trec06c"

# 启动 SMTP 服务端（默认 0.0.0.0:2525）
python server.py

# 启动 Web 客户端（默认 0.0.0.0:8501）
streamlit run client.py --server.address 0.0.0.0 --server.port 8501
```

依赖：`streamlit`, `scikit-learn`（实际未使用）, `jieba`（可选）, `tqdm`（可选）。无 requirements.txt，按需 pip install。

## 架构

**三组件架构，通过文件系统和 SMTP 协议耦合：**

- `server.py` — 自建 SMTP 服务端（`socketserver.ThreadingTCPServer`），实现 EHLO/AUTH(PLAIN+LOGIN)/MAIL/RCPT/DATA/QUIT 完整流程。在 DATA 阶段解析邮件、调用分类器，根据概率三档处理：`<70%` → inbox，`70%-90%` → spam，`>=90%` → 拒收（不保存）。邮件以 `.eml` 文件存储在 `mailboxes/{user}/inbox|spam/`。
- `client.py` — Streamlit 单页应用，侧边栏切换"写邮件"和"邮箱"两个视图。使用 `smtplib.SMTP` 通过服务端发送邮件；直接读取 `mailboxes/` 目录展示收件箱/垃圾箱。每 3 秒自动轮询刷新邮箱列表。
- `train_model.py` — 读取 TREC06C 数据集（`full/index` 索引文件 + `data/` 邮件目录），训练多项式朴素贝叶斯（拉普拉斯平滑），输出 `model.pkl` 和 `model.metrics.json`。

**分类器设计：**
- 优先加载 `model.pkl`（包含先验对数概率 + 每个词的条件对数概率）
- 模型缺失时降级为 `SPAM_KEYWORDS` 硬编码关键词加权打分
- 中文分词优先用 jieba，不可用时退化为正则提取连续汉字/英文

**用户系统：**
- `smtp_users.json` 明文存储邮箱和密码
- 用户注册/登录由客户端直接读写该 JSON 文件
- 服务端 AUTH 时查同一文件校验密码

## 关键环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MAILGUARD_SMTP_HOST` | `0.0.0.0` | SMTP 监听地址 |
| `MAILGUARD_SMTP_PORT` | `2525` | SMTP 监听端口 |
| `MAILGUARD_SPAM_THRESHOLD` | `0.70` | 垃圾邮件阈值 |
| `MAILGUARD_BLOCK_THRESHOLD` | `0.90` | 拒收阈值 |
| `MAILGUARD_CLIENT_SMTP_HOST` | `127.0.0.1` | 客户端连接的服务端地址 |
| `MAILGUARD_CLIENT_SMTP_PORT` | `2525` | 客户端连接的服务端端口 |
| `MAILGUARD_MAX_MAIL_SIZE` | `10485760` | 单封邮件最大字节数 |
| `MAILGUARD_TREC06C_DIR` | `./trec06c` | 训练数据目录 |
