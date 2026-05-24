# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

数字内容过滤课程设计，共四个实验，按依赖关系依次实现：

1. **exp1_crawler** — Web 信息获取（网络爬虫），为后续实验准备文本语料
2. **exp2_text_classifier** — 文本倾向理解（中文分词 + 向量空间模型 + 朴素贝叶斯分类），是算法核心
3. **exp3_email_filter** — 基于内容的垃圾邮件/正常邮件二分类，复用实验二的分类器
4. **exp4_sms_filter** — 基于内容的不良短信/正常短信二分类，需在安卓模拟器中演示

四个实验的完整规格文档位于仓库根目录的 `数字内容过滤课程设计_四个实验说明_Agent版.md`。

## 技术栈

- 语言：Python 3
- 推荐库：`requests` + `BeautifulSoup`（爬虫）、`jieba`（中文分词）、`scikit-learn`（向量化和分类）
- 实验二核心算法：朴素贝叶斯（Naïve Bayes），使用 TF-IDF 向量化，需支持拉普拉斯平滑和特征阈值调整
- 实验四终端演示：Android Studio + 安卓模拟器（Kotlin/Java），或简化为 PC 端模拟界面

## 架构约定

- 公共模块抽取到 `common/`（文本预处理、TF-IDF 向量化、朴素贝叶斯分类器、评估指标）
- 每个实验的目录结构参考规格文档第 6 节
- 数据集中存放于 `data/` 目录，按实验分子目录
- 实验三邮件流架构：本地邮件客户端（Thunderbird/Foxmail/Outlook）→ SMTP 发信 → 远程 Linux 服务器 Postfix 接收 → 自定义 Python 邮件过滤器（解析主题+正文，调用分类器判 spam/ham）→ ham 继续投递，spam 隔离/标记 → 本地邮件客户端通过 IMAP 收取过滤后的邮件
- 实验四可用安卓模拟器 + 手动输入短信文本演示，不需要真实读取手机短信权限

## 语言

所有对话、文档和代码注释使用中文。
