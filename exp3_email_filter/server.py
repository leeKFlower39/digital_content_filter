# -*- coding: utf-8 -*-
"""
MailGuard SMTP 服务端
功能：
1. 按照 SMTP 命令流程接收邮件：EHLO/HELO、AUTH、MAIL FROM、RCPT TO、DATA、QUIT
2. 服务端解析邮件主题和正文
3. 使用朴素贝叶斯模型 model.pkl 判断垃圾概率
4. 根据垃圾概率将正常邮件保存到 inbox、垃圾邮件保存到 spam，高危垃圾邮件直接拒收


默认监听：
    0.0.0.0:2525
"""

import email
import json
import logging
import math
import os
import pickle
import re
import socketserver
import threading
import time
import uuid
from base64 import b64decode
from email.header import decode_header
from email.parser import BytesParser
from email.policy import default
from email.utils import parseaddr
from pathlib import Path


try:
    import jieba
except ImportError:
    jieba = None


# =========================
# 基础配置
# =========================

BASE_DIR = Path(__file__).resolve().parent
SMTP_HOST = os.environ.get("MAILGUARD_SMTP_HOST", "0.0.0.0")
SMTP_PORT = int(os.environ.get("MAILGUARD_SMTP_PORT", "2525"))

USER_FILE = BASE_DIR / "smtp_users.json"
MAILBOX_DIR = BASE_DIR / "mailboxes"
MODEL_FILE = BASE_DIR / "model.pkl"

MAX_MAIL_SIZE = int(os.environ.get("MAILGUARD_MAX_MAIL_SIZE", str(10 * 1024 * 1024)))

# 三档处理阈值：
# < 0.70：正常邮件
# 0.70 - 0.90：垃圾邮件，进入 spam
# >= 0.90：高危垃圾邮件，拒收
SPAM_THRESHOLD = float(os.environ.get("MAILGUARD_SPAM_THRESHOLD", "0.70"))
BLOCK_THRESHOLD = float(os.environ.get("MAILGUARD_BLOCK_THRESHOLD", "0.90"))

mailbox_lock = threading.RLock()
user_lock = threading.RLock()


# =========================
# 初始化与日志
# =========================

def setup_logging():
    logger = logging.getLogger("MailGuardSMTP")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    logger.addHandler(console_handler)
    return logger


logger = setup_logging()


def safe_mailbox_name(email_addr):
    return email_addr.lower().replace("@", "_at_").replace(".", "_")


def ensure_user_mailboxes(email_addr):
    user_dir = MAILBOX_DIR / safe_mailbox_name(email_addr)
    for folder in ("inbox", "spam"):
        (user_dir / folder).mkdir(parents=True, exist_ok=True)


def ensure_user_store():
    with user_lock:
        if not USER_FILE.exists():
            USER_FILE.write_text(
                json.dumps({}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        users = load_users()
        for email_addr in users:
            ensure_user_mailboxes(email_addr)


def load_users():
    with user_lock:
        if not USER_FILE.exists():
            return {}

        try:
            data = json.loads(USER_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k).strip(): str(v) for k, v in data.items()}
            return {}
        except Exception as exc:
            logger.error("读取用户文件失败：%s", exc)
            return {}


def save_users(users):
    with user_lock:
        USER_FILE.write_text(
            json.dumps(users, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def is_local_user(address):
    if not address:
        return False
    users = load_users()
    return address.lower() in {user.lower() for user in users}


def get_password(address):
    if not address:
        return None

    users = load_users()
    for email_addr, password in users.items():
        if email_addr.lower() == address.lower():
            return password
    return None


# =========================
# 模型加载与文本分类
# =========================

def load_model():
    if not MODEL_FILE.exists():
        logger.warning("未找到 model.pkl，将启用关键词兜底规则。建议先运行 train_model.py。")
        return None

    try:
        with MODEL_FILE.open("rb") as file:
            model = pickle.load(file)

        required_keys = {
            "log_p_spam",
            "log_p_ham",
            "log_p_word_spam",
            "log_p_word_ham",
            "vocab_size",
            "spam_total_words",
            "ham_total_words",
        }
        if not required_keys.issubset(set(model.keys())):
            logger.warning("model.pkl 字段不完整，将启用关键词兜底规则。")
            return None

        logger.info("垃圾邮件分类模型加载成功：%s", MODEL_FILE)
        return model
    except Exception as exc:
        logger.error("加载 model.pkl 失败：%s，将启用关键词兜底规则。", exc)
        return None


MODEL_DATA = load_model()


SPAM_KEYWORDS = {
    "中奖": 0.18,
    "大奖": 0.16,
    "百万": 0.16,
    "返利": 0.14,
    "优惠": 0.10,
    "促销": 0.10,
    "免费": 0.12,
    "贷款": 0.14,
    "发票": 0.12,
    "博彩": 0.20,
    "赌场": 0.20,
    "投注": 0.18,
    "点击": 0.12,
    "链接": 0.08,
    "验证码": 0.12,
    "银行卡": 0.18,
    "加微信": 0.16,
    "私聊": 0.10,
    "代理": 0.10,
    "投资": 0.10,
    "高收益": 0.18,
    "http": 0.12,
    "www": 0.10,
    "领取": 0.12,
    "转账": 0.12,
    "账号": 0.08,
    "密码": 0.12,
}


def decode_mime_header(value):
    if not value:
        return ""

    decoded_parts = []
    try:
        for part, charset in decode_header(str(value)):
            if isinstance(part, bytes):
                decoded_parts.append(part.decode(charset or "utf-8", errors="ignore"))
            else:
                decoded_parts.append(str(part))
    except Exception:
        return str(value)

    return "".join(decoded_parts)


def strip_html(text):
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&quot;", " ", text)
    return text


def parse_email_message(raw_email_bytes):
    try:
        return BytesParser(policy=default).parsebytes(raw_email_bytes)
    except Exception:
        return email.message_from_bytes(raw_email_bytes)


def extract_text_content(message):
    """
    优先提取 text/plain；没有纯文本时，退化提取 text/html 并去标签。
    """
    plain_parts = []
    html_parts = []

    if message.is_multipart():
        for part in message.walk():
            content_disposition = str(part.get("Content-Disposition", "")).lower()
            if "attachment" in content_disposition:
                continue

            content_type = part.get_content_type()
            try:
                content = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                charset = part.get_content_charset() or "utf-8"
                content = payload.decode(charset, errors="ignore")

            if content_type == "text/plain":
                plain_parts.append(str(content))
            elif content_type == "text/html":
                html_parts.append(strip_html(str(content)))

        if plain_parts:
            return "\n".join(plain_parts)
        return "\n".join(html_parts)

    try:
        content = message.get_content()
    except Exception:
        payload = message.get_payload(decode=True)
        if payload:
            charset = message.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="ignore")
        else:
            content = str(message.get_payload() or "")

    if message.get_content_type() == "text/html":
        return strip_html(str(content))
    return str(content)


def normalize_text(text):
    text = strip_html(text or "")
    text = text.lower()
    text = re.sub(r"[^\w\u4e00-\u9fa5]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text):
    text = normalize_text(text)
    if not text:
        return []

    if jieba:
        words = jieba.lcut(text)
        return [word.strip().lower() for word in words if len(word.strip()) >= 2 and not word.strip().isdigit()]

    return re.findall(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z]{2,}|\d+[a-zA-Z]+", text)


def keyword_fallback_probability(text):
    """
    当没有 model.pkl 时使用关键词兜底。
    """
    text = normalize_text(text)
    score = 0.05

    for word, weight in SPAM_KEYWORDS.items():
        if word.lower() in text:
            score += weight

    url_count = len(re.findall(r"(https?://|www\.)", text))
    score += min(url_count * 0.10, 0.25)

    digit_count = len(re.findall(r"\d", text))
    if digit_count >= 10:
        score += 0.08

    if len(text) < 10:
        score += 0.04

    return max(0.0, min(score, 0.98))


def predict_spam_probability(text):
    """
    返回垃圾邮件概率，范围 0.0 - 1.0。
    优先使用 model.pkl，模型不存在时使用关键词兜底。
    """
    if not MODEL_DATA:
        return keyword_fallback_probability(text)

    words = tokenize(text)
    if not words:
        return 0.0

    score_spam = MODEL_DATA["log_p_spam"]
    score_ham = MODEL_DATA["log_p_ham"]

    vocab_size = max(int(MODEL_DATA["vocab_size"]), 1)
    spam_total_words = max(int(MODEL_DATA["spam_total_words"]), 1)
    ham_total_words = max(int(MODEL_DATA["ham_total_words"]), 1)

    default_log_p_spam = math.log(1 / (spam_total_words + vocab_size))
    default_log_p_ham = math.log(1 / (ham_total_words + vocab_size))

    log_p_word_spam = MODEL_DATA["log_p_word_spam"]
    log_p_word_ham = MODEL_DATA["log_p_word_ham"]

    for word in words:
        score_spam += log_p_word_spam.get(word, default_log_p_spam)
        score_ham += log_p_word_ham.get(word, default_log_p_ham)

    diff = max(min(score_spam - score_ham, 500), -500)
    probability = 1 / (1 + math.exp(-diff))
    return max(0.0, min(probability, 1.0))


def decide_folder(probability):
    if probability >= SPAM_THRESHOLD:
        return "spam", "spam"
    return "inbox", "clean"


def add_filter_headers(raw_email_bytes, status, probability, folder):
    headers = (
        "X-MailGuard-Status: {status}\r\n"
        "X-MailGuard-Spam-Probability: {prob:.1f}%\r\n"
        "X-MailGuard-Delivery-Folder: {folder}\r\n"
        "X-MailGuard-Processed-At: {time}\r\n"
    ).format(
        status=status,
        prob=probability * 100,
        folder=folder,
        time=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    return headers.encode("utf-8") + raw_email_bytes


def save_message(raw_email_bytes, recipients, probability, status, folder):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    saved_paths = []

    with mailbox_lock:
        for recipient in recipients:
            ensure_user_mailboxes(recipient)

            user_dir = MAILBOX_DIR / safe_mailbox_name(recipient) / folder
            message_id = f"{timestamp}-{uuid.uuid4().hex}.eml"
            message_path = user_dir / message_id
            message_path.write_bytes(raw_email_bytes)

            meta_path = message_path.with_suffix(".json")
            meta_path.write_text(
                json.dumps(
                    {
                        "recipient": recipient,
                        "folder": folder,
                        "status": status,
                        "spam_probability": f"{probability * 100:.1f}%",
                        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            saved_paths.append(str(message_path))

    return saved_paths


def classify_and_store(raw_email_bytes, recipients):
    message = parse_email_message(raw_email_bytes)

    subject = decode_mime_header(message.get("Subject", "")) or "无主题"
    content = extract_text_content(message)
    combined_text = f"{subject}\n{content}"

    probability = predict_spam_probability(combined_text)

    if probability >= BLOCK_THRESHOLD:
        return {
            "subject": subject,
            "probability": probability,
            "folder": "",
            "status": "rejected",
            "paths": [],
            "rejected": True,
        }

    folder, status = decide_folder(probability)

    stored_email = add_filter_headers(raw_email_bytes, status, probability, folder)
    paths = save_message(stored_email, recipients, probability, status, folder)

    return {
        "subject": subject,
        "probability": probability,
        "folder": folder,
        "status": status,
        "paths": paths,
        "rejected": False,
    }

def parse_smtp_address(argument, prefix):
    """
    解析 SMTP 命令中的地址。

    支持：
        MAIL FROM:<user@example.com>
        MAIL FROM:<user@example.com> size=1234
        RCPT TO:<user@example.com>
    """
    if not argument.upper().startswith(prefix):
        return ""

    value = argument[len(prefix):].strip()

    # 标准 SMTP 地址一般在 < > 中
    match = re.search(r"<([^<>]+)>", value)
    if match:
        return match.group(1).strip()

    # 兼容没有尖括号的情况
    value = value.split()[0].strip()
    _, address = parseaddr(value)
    return address.strip()

# =========================
# SMTP 协议服务端
# =========================

class SMTPHandler(socketserver.StreamRequestHandler):
    timeout = 300

    def setup(self):
        super().setup()
        self.reset_transaction()
        self.authenticated_user = None
        self.client_ip = self.client_address[0] if self.client_address else "-"
        logger.info("客户端连接：%s", self.client_ip)

    def reset_transaction(self):
        self.mail_from = None
        self.rcpt_to = []

    def send_line(self, text):
        self.wfile.write(f"{text}\r\n".encode("utf-8"))
        self.wfile.flush()

    def read_line(self):
        line = self.rfile.readline(8192)
        if not line:
            return ""
        return line.decode("utf-8", errors="ignore").rstrip("\r\n")

    def handle(self):
        self.send_line("220 MailGuard SMTP Server Ready")

        while True:
            line = self.read_line()
            if not line:
                return

            command, _, argument = line.partition(" ")
            command = command.upper().strip()
            argument = argument.strip()

            try:
                if command in {"HELO", "EHLO"}:
                    self.handle_hello(command, argument)
                elif command == "AUTH":
                    self.handle_auth(argument)
                elif command == "MAIL":
                    self.handle_mail(argument)
                elif command == "RCPT":
                    self.handle_rcpt(argument)
                elif command == "DATA":
                    self.handle_data()
                elif command == "RSET":
                    self.reset_transaction()
                    self.send_line("250 OK")
                elif command == "NOOP":
                    self.send_line("250 OK")
                elif command == "VRFY":
                    self.handle_vrfy(argument)
                elif command == "QUIT":
                    self.send_line("221 Bye")
                    return
                else:
                    self.send_line("502 Command not implemented")
            except Exception as exc:
                logger.exception("SMTP 命令处理异常：%s", exc)
                self.send_line("451 Local processing error")

    def handle_hello(self, command, argument):
        if command == "EHLO":
            self.send_line("250-MailGuard")
            self.send_line("250-PIPELINING")
            self.send_line("250-8BITMIME")
            self.send_line(f"250-SIZE {MAX_MAIL_SIZE}")
            self.send_line("250 AUTH PLAIN LOGIN")
        else:
            self.send_line("250 MailGuard")

    def handle_auth(self, argument):
        method, _, initial_response = argument.partition(" ")
        method = method.upper()

        if method == "PLAIN":
            if not initial_response:
                self.send_line("334")
                initial_response = self.read_line()

            try:
                decoded = b64decode(initial_response).decode("utf-8", errors="ignore")
                parts = decoded.split("\x00")
                if len(parts) == 3:
                    _, username, password = parts
                elif len(parts) == 2:
                    username, password = parts
                else:
                    raise ValueError("invalid auth plain format")
            except Exception:
                self.send_line("501 Invalid AUTH PLAIN payload")
                return

            self.finish_auth(username, password)
            return

        if method == "LOGIN":
            self.send_line("334 VXNlcm5hbWU6")
            username_line = self.read_line()
            self.send_line("334 UGFzc3dvcmQ6")
            password_line = self.read_line()

            try:
                username = b64decode(username_line).decode("utf-8", errors="ignore")
                password = b64decode(password_line).decode("utf-8", errors="ignore")
            except Exception:
                self.send_line("501 Invalid AUTH LOGIN payload")
                return

            self.finish_auth(username, password)
            return

        self.send_line("504 Unsupported authentication method")

    def finish_auth(self, username, password):
        expected_password = get_password(username)
        if expected_password and password == expected_password:
            self.authenticated_user = username
            ensure_user_mailboxes(username)
            self.send_line("235 Authentication successful")
            logger.info("SMTP 登录成功：%s from %s", username, self.client_ip)
            return

        self.send_line("535 Authentication failed")
        logger.warning("SMTP 登录失败：%s from %s", username, self.client_ip)

    def handle_mail(self, argument):
        if not self.authenticated_user:
            self.send_line("530 Authentication required")
            return

        address = parse_smtp_address(argument, "FROM:")
        if not address:
            self.send_line("501 Invalid sender address")
            return

        if address.lower() != self.authenticated_user.lower():
            self.send_line("553 Sender does not match authenticated user")
            return

        self.mail_from = address
        self.rcpt_to = []
        self.send_line("250 Sender OK")

    def handle_rcpt(self, argument):
        if not self.mail_from:
            self.send_line("503 MAIL FROM required")
            return

        address = parse_smtp_address(argument, "TO:")
        if not address:
            self.send_line("501 Invalid recipient address")
            return

        if not is_local_user(address):
            self.send_line("550 Recipient is not a local mailbox")
            return

        ensure_user_mailboxes(address)
        self.rcpt_to.append(address)
        self.send_line("250 Recipient OK")

    def handle_vrfy(self, argument):
        _, address = parseaddr(argument)
        if is_local_user(address):
            self.send_line(f"250 {address}")
        else:
            self.send_line("550 User unknown")

    def handle_data(self):
        if not self.mail_from:
            self.send_line("503 MAIL FROM required")
            return

        if not self.rcpt_to:
            self.send_line("503 RCPT TO required")
            return

        self.send_line("354 End data with <CR><LF>.<CR><LF>")

        lines = []
        total_size = 0

        while True:
            raw_line = self.rfile.readline(8192)
            if not raw_line:
                self.send_line("451 Connection closed during DATA")
                return

            if raw_line in {b".\r\n", b".\n"}:
                break

            if raw_line.startswith(b".."):
                raw_line = raw_line[1:]

            total_size += len(raw_line)
            if total_size > MAX_MAIL_SIZE:
                self.send_line("552 Message size exceeds fixed limit")
                self.reset_transaction()
                return

            lines.append(raw_line)

        raw_email_bytes = b"".join(lines)

        try:
            result = classify_and_store(raw_email_bytes, self.rcpt_to)
        except Exception as exc:
            logger.exception("邮件过滤和保存失败：%s", exc)
            self.send_line("451 Local processing error")
            return

        if result.get("rejected"):
            probability_percent = result["probability"] * 100
            logger.warning(
                "高危垃圾邮件已拒收：from=%s to=%s subject=%s probability=%.1f%%",
                self.mail_from,
                ",".join(self.rcpt_to),
                result["subject"],
                probability_percent,
            )
            self.reset_transaction()
            self.send_line(f"554 Message rejected; spam_probability={probability_percent:.1f}%")
            return

        logger.info(
            "邮件处理完成：from=%s to=%s subject=%s status=%s probability=%.1f%% folder=%s files=%d",
            self.mail_from,
            ",".join(self.rcpt_to),
            result["subject"],
            result["status"],
            result["probability"] * 100,
            result["folder"],
            len(result["paths"]),
        )

        smtp_status = result["status"]
        probability_percent = result["probability"] * 100
        self.reset_transaction()
        self.send_line(f"250 OK {smtp_status}; spam_probability={probability_percent:.1f}%")


class ThreadedSMTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def main():
    MAILBOX_DIR.mkdir(parents=True, exist_ok=True)
    ensure_user_store()

    server = ThreadedSMTPServer((SMTP_HOST, SMTP_PORT), SMTPHandler)

    logger.info("MailGuard SMTP server listening on %s:%s", SMTP_HOST, SMTP_PORT)
    logger.info("用户文件：%s", USER_FILE)
    logger.info("邮箱目录：%s", MAILBOX_DIR)
    logger.info("处理阈值：spam >= %.0f%%, reject >= %.0f%%", SPAM_THRESHOLD * 100, BLOCK_THRESHOLD * 100)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("SMTP server stopped by user.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
