# MailGuard 实验三：基于内容的电子邮件过滤系统

## 1. 文件说明

- `server.py`：SMTP 邮件服务器，负责接收邮件、过滤邮件、保存邮件。
- `client.py`：Streamlit 邮箱客户端，负责登录、写邮件、查看收件箱/垃圾箱/拦截箱。
- `train_model.py`：朴素贝叶斯模型训练脚本，使用 TREC06C 数据集生成 `model.pkl`。
- `smtp_users.json`：默认邮箱账号。
- `requirements.txt`：依赖库。

## 2. 安装依赖

```bash
pip install -r requirements.txt
```

## 3. 训练模型

如果已经有 TREC06C 数据集，运行：

```bash
python train_model.py --data-dir "D:\AAA-learn\信息过滤系统课程设计\实验三\trec06c"
```

运行后会生成：

```text
model.pkl
model.metrics.json
```

如果暂时没有模型，也可以直接启动服务端，系统会使用关键词规则兜底，保证演示流程可运行。

## 4. 启动 SMTP 服务端

```bash
python server.py
```

成功后会看到：

```text
MailGuard SMTP server listening on 0.0.0.0:2525
```

## 5. 启动邮箱系统

在服务器电脑运行：

```bash
streamlit run client.py --server.address 0.0.0.0 --server.port 8501
```

两台电脑浏览器访问：

```text
http://服务器IP:8501
```

## 6. 默认账号

```text
sender@bupt.edu.cn / 123456
receiver@bupt.edu.cn / 123456
admin@bupt.edu.cn / 123456
```

## 7. 演示流程

1. 电脑 A 登录 `sender@bupt.edu.cn`
2. 电脑 B 登录 `receiver@bupt.edu.cn`
3. 电脑 A 发送正常邮件：

```text
主题：实验验收通知
正文：明天下午三点在实验室进行课程设计验收，请携带笔记本电脑并准备演示材料。
```

4. 电脑 B 查看收件箱，邮件进入 `inbox`。
5. 电脑 A 发送垃圾邮件：

```text
主题：中奖通知
正文：恭喜你获得百万大奖，请点击链接领取奖金，并提供银行卡账号、密码和验证码。
```

6. 电脑 B 查看垃圾箱或拦截箱，邮件进入 `spam` 或 `blocked`。
7. 查看“服务端日志”，说明服务端完成了识别、监控、处理和拦截。

## 8. 注意事项

- 发送邮件严格使用 SMTP 协议。
- 客户端不判断垃圾邮件，分类发生在 `server.py` 的 DATA 阶段。
- 如果其他电脑无法访问，请检查 Windows 防火墙是否放行 2525 和 8501 端口。
