import streamlit as st
import jieba
import time
import pandas as pd
from datetime import datetime
import requests

# --- 页面配置 ---
st.set_page_config(page_title="邮件过滤模拟系统", layout="wide")

# --- 模拟后端分类逻辑 (实际中应由成员B提供API地址) ---
def mock_server_predict(text):
    # 【修改这里】不再是假逻辑，而是通过网络请求成员 B 的服务器
    try:
        response = requests.post(
            "http://127.0.0.1:5000/predict", 
            json={"content": text}
        )
        res_data = response.json()
        is_spam = (res_data['label'] == "Spam")
        confidence = res_data['confidence']
        return is_spam, confidence
    except:
        # 如果服务器没开，报错提示
        st.error("无法连接到邮件服务器网关，请确保 server.py 已启动")
        return False, 0.0

# --- 侧边栏：系统状态与统计 ---
with st.sidebar:
    st.title("🛡️ 过滤网关监控")
    st.info("系统状态：运行中")
    st.metric(label="当前过滤算法", value="Naive Bayes")
    st.divider()
    
    st.subheader("📊 历史拦截统计")
    if 'history' not in st.session_state:
        st.session_state.history = []
    
    total = len(st.session_state.history)
    spams = sum(1 for x in st.session_state.history if x['result'] == '垃圾邮件')
    st.write(f"已处理邮件总数: {total}")
    st.progress(spams/total if total > 0 else 0, text=f"拦截率: {spams}")

# --- 主界面 ---
st.title("✉️ 邮件发送模拟客户端")
st.markdown("这是实验三的前端展示部分，模拟用户发送邮件并经过服务器网关过滤的过程。")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("编写邮件")
    sample_options = {
        "自定义内容": "",
        "正常：关于下周开会的通知": "各位同事，下周一下午两点在会议室开会，请准时参加。",
        "正常：论文草稿请查收": "老师您好，这是我修改后的实验报告，请您有空指导。",
        "垃圾：澳门首家线上赌场": "恭喜发财！澳门首家线上赌场上线啦，点击链接领取1000元红包！",
        "垃圾：正规发票代开": "长期代开各类正规发票，点数低，保真，需要请联系。"
    }
    
    selected_sample = st.selectbox("选择快速填充样本：", options=list(sample_options.keys()))
    
    email_text = st.text_area(
        "邮件正文：", 
        value=sample_options[selected_sample],
        height=250, 
        placeholder="请输入邮件内容..."
    )
    
    if st.button("🚀 发送邮件", use_container_width=True):
        if not email_text.strip():
            st.warning("内容不能为空！")
        else:
            with st.status("正在通过服务器网关分析内容...", expanded=True) as status:
                st.write("正在连接邮件服务器...")
                is_spam, confidence = mock_server_predict(email_text)
                st.write(f"正在运行贝叶斯分类算法 (置信度: {confidence:.2f})...")
                time.sleep(0.3)
                status.update(label="分析完成！", state="complete", expanded=False)
            
            # 展示结果
            if is_spam:
                st.error(f"❌ **邮件被拦截！** 系统判定为：**垃圾邮件** (置信度: {confidence*100:.1f}%)")
                res_type = "垃圾邮件"
            else:
                st.success(f"✅ **邮件已送达！** 系统判定为：**正常邮件** (置信度: {(1-confidence)*100:.1f}%)")
                res_type = "正常邮件"
            
            # 记录历史
            st.session_state.history.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "content": email_text[:20] + "...",
                "result": res_type
            })

with col2:
    st.subheader("📑 服务器实时日志")
    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history).iloc[::-1] # 最新在最前
        st.table(df)
    else:
        st.write("暂无处理记录")

st.divider()
st.caption("数字内容过滤课程设计 - 实验三小组演示系统")
