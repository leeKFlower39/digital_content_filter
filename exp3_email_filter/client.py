# -*- coding: utf-8 -*-
"""
MailGuard 邮箱客户端
功能：
1. 登录 / 注册邮箱用户
2. 使用 smtplib.SMTP 严格通过 SMTP 协议发送邮件
3. 查看服务端保存的收件箱、垃圾箱
4. 显示服务端写入的垃圾概率和处理状态
"""

import email
import html
import json
import os
import re
import smtplib
from datetime import datetime
from email.header import decode_header
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default
from email.utils import formatdate, make_msgid, parseaddr
from pathlib import Path

import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
USER_FILE = BASE_DIR / "smtp_users.json"
MAILBOX_DIR = BASE_DIR / "mailboxes"

DEFAULT_SMTP_HOST = os.environ.get("MAILGUARD_CLIENT_SMTP_HOST", "127.0.0.1")
DEFAULT_SMTP_PORT = int(os.environ.get("MAILGUARD_CLIENT_SMTP_PORT", "2525"))

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$"


# =========================
# 页面样式
# =========================

st.set_page_config(
    page_title="MailGuard",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)

auto_fragment = getattr(st, "fragment", lambda **_: (lambda func: func))

st.markdown(
    """
    <style>
        :root {
            --app-bg: #f3f6fb;
            --mail-blue: #2563eb;
            --mail-blue-hover: #1d4ed8;
            --ink: #111827;
            --muted: #4b5563;
            --weak: #6b7280;
            --panel: #ffffff;
            --line: #d9e2ef;
            --input-line: #c8d3e3;
            --green: #047857;
            --amber: #b45309;
            --red: #b91c1c;
            --purple: #6b7280;
            --shadow: 0 6px 18px rgba(17, 24, 39, .06);
        }

        .stApp {
            background: var(--app-bg) !important;
            color: var(--ink) !important;
            font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif !important;
        }

        [data-testid="stHeader"] {
            background: rgba(243, 246, 251, .92) !important;
            backdrop-filter: blur(6px) !important;
        }

        [data-testid="stToolbar"] {
            background: transparent !important;
        }

        .block-container {
            max-width: 1040px;
            padding-top: 1.1rem;
            padding-bottom: 2.5rem;
            color: var(--ink) !important;
        }

        .stApp,
        .stApp p,
        .stApp span,
        .stApp label,
        .stApp div,
        .stApp li,
        .stApp td,
        .stApp th {
            color: var(--ink) !important;
        }

        .stCaptionContainer,
        .stCaptionContainer *,
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] *,
        [data-testid="stMarkdownContainer"] small,
        [data-testid="stMarkdownContainer"] .caption {
            color: var(--muted) !important;
        }

        .main .block-container,
        section.main .block-container {
            background: transparent !important;
        }

        [data-testid="stSidebar"] {
            background: var(--panel) !important;
            border-right: 1px solid var(--line) !important;
            box-shadow: 2px 0 14px rgba(17, 24, 39, .04) !important;
        }

        [data-testid="stSidebar"] > div {
            background: var(--panel) !important;
        }

        [data-testid="stSidebar"],
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div,
        [data-testid="stSidebar"] button,
        [data-testid="stSidebar"] section {
            color: var(--ink) !important;
        }

        [data-testid="stSidebar"] code {
            color: var(--ink) !important;
            background: #eef2f7 !important;
            border: 1px solid var(--line) !important;
        }

        [data-testid="stSidebar"] hr {
            border-color: var(--line) !important;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label {
            background: var(--panel) !important;
            border-radius: 8px !important;
            padding: .55rem .65rem !important;
            margin-bottom: .25rem !important;
            border-left: 3px solid transparent !important;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label:hover {
            background: #eff6ff !important;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
            background: #eff6ff !important;
            border-left-color: var(--mail-blue) !important;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p,
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) span {
            color: var(--mail-blue) !important;
            font-weight: 700 !important;
        }

        .account-card {
            display: flex;
            align-items: center;
            gap: .75rem;
            padding: .85rem;
            margin: .8rem 0 1rem;
            background: #f8fafc !important;
            border: 1px solid var(--line) !important;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(17, 24, 39, .035);
        }

        .account-avatar {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 0 0 auto;
            background: #dbeafe !important;
            color: var(--mail-blue) !important;
            font-weight: 800;
            font-size: 1rem;
        }

        .account-title {
            color: var(--muted) !important;
            font-size: .78rem;
            line-height: 1.2;
            margin-bottom: .15rem;
        }

        .account-email {
            color: var(--ink) !important;
            font-size: .84rem;
            font-weight: 700;
            line-height: 1.35;
            overflow-wrap: anywhere;
        }

        .mail-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: .9rem 1rem;
            margin-bottom: .9rem;
            background: var(--panel) !important;
            border: 1px solid var(--line) !important;
            border-radius: 8px;
            color: var(--ink) !important;
            box-shadow: var(--shadow) !important;
        }

        .mail-topbar h1 {
            margin: 0;
            color: var(--ink) !important;
            font-size: 1.25rem;
            font-weight: 700;
        }

        .mail-topbar p {
            margin: .2rem 0 0;
            color: var(--muted) !important;
            font-size: .9rem;
        }

        .mail-status {
            padding: .38rem .65rem;
            border-radius: 999px;
            background: #eef2ff !important;
            border: 1px solid #c7d2fe !important;
            color: #3730a3 !important;
            white-space: nowrap;
            font-size: .82rem;
        }

        .auth-shell {
            max-width: 450px;
            margin: 7vh auto 0;
            background: var(--panel) !important;
            border: 1px solid var(--line) !important;
            border-radius: 10px;
            box-shadow: var(--shadow) !important;
            overflow: hidden;
        }

        .auth-brand {
            padding: 1rem 1.2rem;
            background: var(--mail-blue) !important;
        }

        .auth-brand h1 {
            color: #ffffff !important;
            margin: 0;
            font-size: 1.65rem;
        }

        .auth-brand p {
            color: rgba(255, 255, 255, .84) !important;
            margin: .35rem 0 0;
        }

        .auth-form {
            padding: 1.1rem 1.2rem 1.25rem;
            background: var(--panel) !important;
        }

        .compose-shell {
            max-width: 820px;
        }

        [data-testid="stForm"],
        [data-testid="stForm"] > div {
            background: var(--panel) !important;
            border-color: var(--line) !important;
            color: var(--ink) !important;
            border-radius: 10px !important;
            box-shadow: var(--shadow) !important;
        }

        [data-testid="stForm"] {
            padding: 1.05rem 1.1rem !important;
            max-width: 820px !important;
        }

        .mailbox-shell {
            max-width: 980px;
        }

        .metric-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .6rem;
            margin-bottom: .8rem;
        }

        .metric-card {
            padding: .68rem .78rem;
            background: var(--panel) !important;
            border: 1px solid var(--line) !important;
            border-left: 4px solid var(--mail-blue);
            border-radius: 8px;
            box-shadow: var(--shadow) !important;
        }

        .metric-card:nth-child(2) {
            border-left-color: var(--amber);
        }

        .metric-card:nth-child(3) {
            border-left-color: var(--red);
        }

        .metric-card:nth-child(4) {
            border-left-color: var(--purple);
        }

        .metric-card span {
            display: block;
            color: var(--muted) !important;
            font-size: .78rem;
        }

        .metric-card strong {
            display: block;
            margin-top: .15rem;
            font-size: 1.32rem;
            line-height: 1.15;
            color: var(--ink) !important;
        }

        div[data-testid="stExpander"] {
            margin-bottom: .35rem;
            background: var(--panel) !important;
            border: 1px solid var(--line) !important;
            border-radius: 6px;
            box-shadow: var(--shadow) !important;
            color: var(--ink) !important;
        }

        div[data-testid="stExpander"] details {
            background: var(--panel) !important;
            color: var(--ink) !important;
        }

        div[data-testid="stExpander"] summary {
            background: var(--panel) !important;
            color: var(--ink) !important;
        }

        div[data-testid="stExpander"] summary:hover {
            background: #f8fafc !important;
        }

        div[data-testid="stExpander"] details summary p,
        div[data-testid="stExpander"] details summary span,
        div[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {
            color: var(--ink) !important;
            font-size: .95rem !important;
            font-weight: 600 !important;
        }

        .mail-detail-wrap {
            max-width: 780px;
            margin: 0 auto;
            padding: 14px 16px 16px;
        }

        .mail-list-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            width: 100%;
        }

        .mail-list-title .mail-subject {
            color: var(--ink) !important;
            font-size: .98rem;
            font-weight: 700;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .mail-list-title .mail-time {
            color: var(--muted) !important;
            font-size: .84rem;
            font-weight: 500;
            white-space: nowrap;
        }

        .message-meta {
            display: grid;
            grid-template-columns: 80px minmax(0, 1fr);
            gap: .35rem .75rem;
            padding: .4rem 0 .9rem;
            margin-bottom: .9rem;
            color: var(--muted) !important;
            font-size: .92rem;
            border-bottom: 1px solid var(--line);
        }

        .message-meta strong {
            color: var(--ink) !important;
            font-weight: 700;
            overflow-wrap: anywhere;
        }

        .message-meta span {
            color: var(--muted) !important;
            font-weight: 600;
        }

        .message-meta-compact {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px 14px;
            padding: 12px 14px;
            margin: 6px 0 12px;
            background: #f8fafc !important;
            border: 1px solid var(--line) !important;
            border-radius: 10px;
            font-size: .9rem;
        }

        .message-meta-compact span {
            color: var(--muted) !important;
            font-weight: 600;
        }

        .message-meta-compact strong {
            color: var(--ink) !important;
            font-weight: 700;
            overflow-wrap: anywhere;
        }

        .mail-body-title {
            margin: 4px 0 8px;
            color: var(--muted) !important;
            font-size: .88rem;
            font-weight: 700;
        }

        .mail-body-card {
            background: #ffffff !important;
            border: 1px solid var(--line) !important;
            border-radius: 10px;
            padding: 18px 20px;
            min-height: 140px;
            color: var(--ink) !important;
            font-size: 1.05rem;
            line-height: 1.8;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
        }

        @media (max-width: 760px) {
            .message-meta-compact {
                grid-template-columns: 1fr;
            }

            .mail-list-title {
                display: block;
            }

            .mail-list-title .mail-time {
                display: block;
                margin-top: .2rem;
            }
        }

        input,
        textarea,
        select,
        [data-baseweb="input"] input,
        [data-baseweb="textarea"] textarea,
        [data-baseweb="select"] > div,
        [data-baseweb="select"] input,
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stNumberInput"] input,
        [data-testid="stSelectbox"] div,
        [data-testid="stSelectbox"] input {
            background: #ffffff !important;
            color: var(--ink) !important;
            border-color: var(--input-line) !important;
            caret-color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
        }

        input::placeholder,
        textarea::placeholder,
        [data-baseweb="input"] input::placeholder,
        [data-baseweb="textarea"] textarea::placeholder,
        [data-testid="stTextInput"] input::placeholder,
        [data-testid="stTextArea"] textarea::placeholder {
            color: var(--weak) !important;
            opacity: 1 !important;
            -webkit-text-fill-color: var(--weak) !important;
        }

        [data-baseweb="input"] > div,
        [data-baseweb="textarea"] > div,
        [data-baseweb="select"] > div,
        [data-testid="stTextInput"] > div,
        [data-testid="stTextArea"] > div,
        [data-testid="stNumberInput"] > div,
        [data-testid="stSelectbox"] > div {
            background: #ffffff !important;
            color: var(--ink) !important;
            border-color: var(--input-line) !important;
        }

        [data-testid="stSelectbox"] {
            max-width: 820px !important;
        }

        [data-baseweb="popover"],
        [data-baseweb="menu"],
        [role="listbox"],
        [role="option"] {
            background: #ffffff !important;
            color: var(--ink) !important;
        }

        [role="option"]:hover,
        [role="option"][aria-selected="true"] {
            background: #eff6ff !important;
            color: var(--ink) !important;
        }

        .stButton > button,
        button[kind="primary"],
        button[kind="secondary"],
        button[data-testid="baseButton-primary"],
        button[data-testid="baseButton-secondary"],
        [data-testid="stFormSubmitButton"] button {
            background: var(--mail-blue) !important;
            color: #ffffff !important;
            border: 1px solid var(--mail-blue) !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
        }

        .stButton > button *,
        button[kind="primary"] *,
        button[kind="secondary"] *,
        button[data-testid="baseButton-primary"] *,
        button[data-testid="baseButton-secondary"] *,
        [data-testid="stFormSubmitButton"] button * {
            color: #ffffff !important;
        }

        .stButton > button:hover,
        button[kind="primary"]:hover,
        button[kind="secondary"]:hover,
        button[data-testid="baseButton-primary"]:hover,
        button[data-testid="baseButton-secondary"]:hover,
        [data-testid="stFormSubmitButton"] button:hover {
            background: var(--mail-blue-hover) !important;
            border-color: var(--mail-blue-hover) !important;
            color: #ffffff !important;
        }

        [data-testid="stSidebar"] .stButton > button {
            background: #ffffff !important;
            color: var(--red) !important;
            border: 1px solid #fecaca !important;
        }

        [data-testid="stSidebar"] .stButton > button * {
            color: var(--red) !important;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            background: #fef2f2 !important;
            border-color: #fca5a5 !important;
            color: var(--red) !important;
        }

        [data-testid="stTabs"] {
            background: transparent !important;
            color: var(--ink) !important;
        }

        [data-testid="stTabs"] button,
        [data-testid="stTabs"] button p {
            color: var(--ink) !important;
            font-weight: 700 !important;
        }

        [data-testid="stTabs"] [aria-selected="true"],
        [data-testid="stTabs"] [aria-selected="true"] p {
            color: var(--mail-blue) !important;
        }

        [data-testid="stAlert"] {
            background: var(--panel) !important;
            border: 1px solid var(--line) !important;
            color: var(--ink) !important;
        }

        [data-testid="stAlert"] * {
            color: var(--ink) !important;
        }

        .risk-clean {
            color: var(--green) !important;
            font-weight: 700;
        }

        .risk-spam {
            color: var(--amber) !important;
            font-weight: 700;
        }

        .risk-blocked {
            color: var(--red) !important;
            font-weight: 700;
        }

        @media (max-width: 760px) {
            .metric-grid {
                grid-template-columns: 1fr;
            }

            .mail-topbar {
                display: block;
            }

            .mail-status {
                display: inline-block;
                margin-top: .7rem;
            }

            .message-meta {
                grid-template-columns: 72px minmax(0, 1fr);
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================
# 工具函数
# =========================

def init_session_state():
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("user_email", "")
    st.session_state.setdefault("smtp_host", DEFAULT_SMTP_HOST)
    st.session_state.setdefault("smtp_port", DEFAULT_SMTP_PORT)
    st.session_state.setdefault("mail_search", "")
    st.session_state.setdefault("mail_status_filter", "全部")


def is_valid_email(value):
    return bool(re.match(EMAIL_REGEX, (value or "").strip()))


def safe_mailbox_name(email_addr):
    return email_addr.lower().replace("@", "_at_").replace(".", "_")


def ensure_user_mailboxes(email_addr):
    user_dir = MAILBOX_DIR / safe_mailbox_name(email_addr)
    for folder in ("inbox", "spam"):
        (user_dir / folder).mkdir(parents=True, exist_ok=True)


def load_users():
    if not USER_FILE.exists():
        return {}

    try:
        data = json.loads(USER_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k).strip(): str(v) for k, v in data.items()}
    except Exception:
        pass

    return {}


def list_local_users():
    current = st.session_state.user_email.lower()
    return [
        email_addr
        for email_addr in sorted(load_users())
        if email_addr.lower() != current
    ]


def save_users(users):
    USER_FILE.write_text(
        json.dumps(users, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def authenticate(email_addr, password):
    users = load_users()
    for user_email, user_password in users.items():
        if user_email.lower() == email_addr.lower() and user_password == password:
            ensure_user_mailboxes(user_email)
            return True
    return False


def register_user(email_addr, password):
    users = load_users()

    if any(user.lower() == email_addr.lower() for user in users):
        return False

    users[email_addr] = password
    save_users(users)
    ensure_user_mailboxes(email_addr)
    return True


def decode_mime_header(value):
    if not value:
        return ""

    decoded = []
    try:
        for part, charset in decode_header(str(value)):
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="ignore"))
            else:
                decoded.append(str(part))
        return "".join(decoded)
    except Exception:
        return str(value)


def strip_html(text):
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text or "")
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_email_message(raw_bytes):
    try:
        return BytesParser(policy=default).parsebytes(raw_bytes)
    except Exception:
        return email.message_from_bytes(raw_bytes)


def extract_text_content(message):
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


def parse_spam_probability(value):
    try:
        return float(str(value or "0").replace("%", "").strip())
    except Exception:
        return 0.0


def risk_class(probability, status):
    value = parse_spam_probability(probability)
    if status == "error" or value >= 90:
        return "risk-blocked"
    if status == "spam" or value >= 70:
        return "risk-spam"
    return "risk-clean"


def should_hide_message(item):
    sender = str(item.get("sender", "") or "").strip()
    subject = str(item.get("subject", "") or "")
    content = str(item.get("content", "") or "")
    status = str(item.get("status", "") or "").strip().lower()

    text = f"{sender} {subject} {content}".lower()
    compact_text = text.replace(" ", "")

    if not sender or sender in {"未知发件人", "解析失败"}:
        return True
    if status == "error":
        return True
    if "未知发件人" in text:
        return True
    if "sender发给receiver" in compact_text:
        return True
    return False


def read_mailbox(folder):
    user_dir = MAILBOX_DIR / safe_mailbox_name(st.session_state.user_email) / folder
    if not user_dir.exists():
        return []

    emails = []

    for message_path in sorted(user_dir.glob("*.eml"), key=lambda path: path.stat().st_mtime):
        try:
            raw_bytes = message_path.read_bytes()
            message = parse_email_message(raw_bytes)

            sender = parseaddr(str(message.get("From", "")))[1] or str(message.get("From", "")) or "未知发件人"
            recipient = parseaddr(str(message.get("To", "")))[1] or str(message.get("To", "")) or "-"
            subject = decode_mime_header(message.get("Subject", "")) or "无主题"
            content = extract_text_content(message)

            probability = str(message.get("X-MailGuard-Spam-Probability", "0.0%"))
            status = str(message.get("X-MailGuard-Status", "clean"))
            delivery_folder = str(message.get("X-MailGuard-Delivery-Folder", folder))

            sent_time = str(message.get("Date", ""))
            if not sent_time:
                sent_time = datetime.fromtimestamp(message_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

            emails.append(
                {
                    "sender": sender,
                    "recipient": recipient,
                    "subject": subject,
                    "content": content,
                    "spam_prob": probability,
                    "status": status,
                    "folder": delivery_folder,
                    "time": sent_time,
                    "path": str(message_path),
                }
            )
        except Exception as exc:
            emails.append(
                {
                    "sender": "解析失败",
                    "recipient": "-",
                    "subject": message_path.name,
                    "content": f"邮件解析失败：{exc}",
                    "spam_prob": "0.0%",
                    "status": "error",
                    "folder": folder,
                    "time": datetime.fromtimestamp(message_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "path": str(message_path),
                }
            )

    return [item for item in emails if not should_hide_message(item)]


def send_by_smtp(recipient_email, subject, body):
    sender = st.session_state.user_email
    password = load_users().get(sender)

    message = EmailMessage()
    message.set_content(body, subtype="plain", charset="utf-8")
    message["Subject"] = subject.strip() or "无主题"
    message["From"] = sender
    message["To"] = recipient_email
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain="mailguard.local")

    with smtplib.SMTP(st.session_state.smtp_host, int(st.session_state.smtp_port), timeout=10) as smtp:
        smtp.ehlo()
        if password:
            smtp.login(sender, password)
        smtp.send_message(message)


def status_label(status):
    status_map = {
        "clean": "正常",
        "spam": "垃圾",
        "error": "解析异常",
    }
    return status_map.get(status, status or "-")


def folder_label(folder):
    folder_map = {
        "inbox": "收件箱",
        "spam": "垃圾箱",
    }
    return folder_map.get(folder, folder or "-")


def filter_emails(emails, keyword, status_filter):
    keyword = (keyword or "").strip().lower()
    filtered = []

    for item in emails:
        status = item.get("status") or ""
        if status_filter != "全部" and status_label(status) != status_filter:
            continue

        haystack = " ".join(
            str(item.get(field, ""))
            for field in ("sender", "recipient", "subject", "content", "spam_prob", "time")
        ).lower()
        if keyword and keyword not in haystack:
            continue

        filtered.append(item)

    return filtered


def open_mail_header(title, subtitle, status=None):
    status_html = ""
    if status:
        status_html = f'<div class="mail-status">{html.escape(status)}</div>'

    st.markdown(
        f"""
        <div class="mail-topbar">
            <div>
                <h1>{html.escape(title)}</h1>
                <p>{html.escape(subtitle)}</p>
            </div>
            {status_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================
# 页面渲染
# =========================

def render_login_page():
    st.markdown(
        """
        <div class="auth-shell">
            <div class="auth-brand">
                <h1>MailGuard</h1>
                <p>基于内容识别的电子邮件过滤系统</p>
            </div>
            <div class="auth-form">
        """,
        unsafe_allow_html=True,
    )

    mode = st.radio(
        "账户操作",
        ["登录", "注册"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if mode == "注册":
        with st.form("register_form"):
            email_input = st.text_input("邮箱地址", placeholder="student@bupt.edu.cn")
            password_input = st.text_input("密码", type="password")
            submit_reg = st.form_submit_button("创建账户", use_container_width=True)

        if submit_reg:
            email_addr = email_input.strip()
            if not is_valid_email(email_addr):
                st.error("请输入有效的邮箱地址。")
            elif not password_input:
                st.error("请输入密码。")
            elif register_user(email_addr, password_input):
                st.success("注册成功，可以直接登录使用。")
            else:
                st.error("该邮箱已存在。")

    else:
        with st.form("login_form"):
            email_input = st.text_input("邮箱地址", placeholder="name@example.com")
            password_input = st.text_input("密码", type="password")
            submit_login = st.form_submit_button("进入邮箱", type="primary", use_container_width=True)

        if submit_login:
            email_addr = email_input.strip()
            if not is_valid_email(email_addr):
                st.error("请输入有效的邮箱地址。")
            elif authenticate(email_addr, password_input):
                st.session_state.logged_in = True
                st.session_state.user_email = email_addr
                st.rerun()
            else:
                st.error("邮箱或密码错误。")

    st.markdown("</div></div>", unsafe_allow_html=True)


def render_sidebar():
    with st.sidebar:
        st.markdown("### MailGuard")
        st.caption("基于内容的邮件过滤系统")

        email_addr = st.session_state.user_email or "未登录"
        avatar_text = "邮"
        if email_addr and email_addr != "未登录":
            avatar_text = email_addr[0].upper()

        st.markdown(
            f"""
            <div class="account-card">
                <div class="account-avatar">{html.escape(avatar_text)}</div>
                <div>
                    <div class="account-title">当前账户</div>
                    <div class="account-email">{html.escape(email_addr)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

        menu_selection = st.radio(
            "功能菜单",
            ["写邮件", "邮箱"],
            label_visibility="collapsed",
        )

        st.divider()
        if st.button("退出登录", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.rerun()

    return menu_selection


def render_compose_page():
    open_mail_header(
        "写邮件",
        "发送后的邮件会自动完成识别、分类与投递。",
    )

    st.markdown('<div class="compose-shell">', unsafe_allow_html=True)

    with st.form("compose_form", clear_on_submit=True):
        recipient_email = st.text_input(
            "收件人",
            placeholder="name@example.com",
        )
        subject = st.text_input("主题", placeholder="请输入邮件主题")
        email_text = st.text_area("正文", height=320, placeholder="请输入邮件正文")
        submit_send = st.form_submit_button("发送邮件", type="primary", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if not submit_send:
        return

    recipient = recipient_email.strip()
    body = email_text.strip()

    if not is_valid_email(recipient):
        st.error("请输入有效的收件人邮箱地址。")
        return

    if not body:
        st.error("邮件正文不能为空。")
        return

    try:
        send_by_smtp(recipient, subject, body)
        st.success("邮件已发送。服务端会自动完成识别、分类与投递。")
    except smtplib.SMTPRecipientsRefused:
        st.error("收件人不是本系统中的有效邮箱。")
    except smtplib.SMTPAuthenticationError:
        st.error("SMTP 认证失败，请检查账号密码。")
    except ConnectionRefusedError:
        st.error("无法连接邮件发送服务，请检查服务地址和端口。")
    except (OSError, smtplib.SMTPException) as exc:
        st.error(f"投递失败：{exc}")


def render_email_list(emails, empty_text):
    emails = [item for item in emails if not should_hide_message(item)]

    if not emails:
        st.info(empty_text)
        return

    for item in reversed(emails):
        recipient = item.get("recipient") or "-"
        subject = item.get("subject") or "无主题"
        content = item.get("content") or ""
        sent_time = item.get("time") or "-"

        title = f"{subject}    {sent_time}"

        with st.expander(title):
            st.markdown(
                f"""
                <div class="mail-detail-wrap">
                    <div class="mail-list-title">
                        <span class="mail-subject">主题：{html.escape(subject)}</span>
                        <span class="mail-time">{html.escape(sent_time)}</span>
                    </div>
                    <div class="message-meta-compact">
                        <div><span>收件人：</span><strong>{html.escape(recipient)}</strong></div>
                        <div><span>主题：</span><strong>{html.escape(subject)}</strong></div>
                        <div><span>时间：</span><strong>{html.escape(sent_time)}</strong></div>
                    </div>
                    <div class="mail-body-title">邮件内容</div>
                    <div class="mail-body-card">{html.escape(content)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_mailbox_page():
    open_mail_header(
        "邮箱",
        "邮件已按服务端识别结果自动归入收件箱和垃圾箱。",
        f"更新于 {datetime.now().strftime('%H:%M:%S')}",
    )

    st.markdown('<div class="mailbox-shell">', unsafe_allow_html=True)

    @auto_fragment(run_every=3)
    def poll_mailbox_fragment():
        inbox_emails = read_mailbox("inbox")
        spam_emails = read_mailbox("spam")
        total = len(inbox_emails) + len(spam_emails)

        st.markdown(
            f"""
            <div class="metric-grid">
                <div class="metric-card"><span>正常收件箱</span><strong>{len(inbox_emails)}</strong></div>
                <div class="metric-card"><span>垃圾箱</span><strong>{len(spam_emails)}</strong></div>
                <div class="metric-card"><span>全部邮件</span><strong>{total}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_inbox, tab_spam = st.tabs(["收件箱 inbox", "垃圾箱 spam"])

        with tab_inbox:
            render_email_list(inbox_emails, "收件箱暂无邮件。")

        with tab_spam:
            render_email_list(spam_emails, "垃圾箱暂无邮件。")

    poll_mailbox_fragment()

    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# 主程序
# =========================

init_session_state()

if not st.session_state.logged_in:
    render_login_page()
else:
    selected_page = render_sidebar()

    if selected_page == "写邮件":
        render_compose_page()
    else:
        render_mailbox_page()
