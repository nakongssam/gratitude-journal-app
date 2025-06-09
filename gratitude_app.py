import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd
import openai
import plotly.express as px
from streamlit_calendar import calendar

# 🎯 OpenAI API Key (보안 적용)
openai.api_key = st.secrets["general"]["OPENAI_API_KEY"]

# 🎯 DB 연결 및 초기화
def init_db():
    conn = sqlite3.connect('gratitude_journal.db', check_same_thread=False)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'student'
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            student_id INTEGER,
            entry_number INTEGER,
            target TEXT,
            content TEXT,
            shared INTEGER DEFAULT 0,
            ai_feedback TEXT,
            FOREIGN KEY(student_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    return conn, c

conn, c = init_db()

# 🎯 유틸리티 함수
def check_login(username, password):
    c.execute("SELECT id, role FROM users WHERE username = ? AND password = ?", (username, password))
    return c.fetchone()

def register_user(username, password, role="student"):
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def generate_feedback(content):
    if not content.strip():
        return ""
    prompt = f"'{content}' 이 감사 내용에 대해 학생을 따뜻하게 격려하는 피드백 한 문장 생성."
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.7
        )
        return response.choices[0].message['content'].strip()
    except:
        return "AI 피드백 생성 실패"

# 🎯 Streamlit 기본 세팅
st.set_page_config(page_title="AI 감사일기", page_icon="📘", layout="wide")
st.markdown("<h1 style='text-align:center; color:#4682B4;'>💙 AI 기반 감사일기 시스템 💙</h1>", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.session_state.user = None

# 🎯 로그인 & 회원가입 화면
if st.session_state.user is None:
    tab_login, tab_register = st.tabs(["🔑 로그인", "📝 회원가입"])
    
    with tab_login:
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")
        if st.button("로그인"):
            result = check_login(username, password)
            if result:
                st.session_state.user = {"id": result[0], "username": username, "role": result[1]}
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    
    with tab_register:
        new_username = st.text_input("새 아이디")
        new_password = st.text_input("새 비밀번호", type="password")
        role_option = st.selectbox("역할 선택", ["student", "teacher"])
        if st.button("회원가입"):
            if register_user(new_username, new_password, role_option):
                st.success("회원가입 성공!")
            else:
                st.error("이미 존재하는 아이디입니다.")

# 🎯 로그인 이후 메인 화면
else:
    st.sidebar.write(f"👋 {st.session_state.user['username']}님 ({st.session_state.user['role']})")
    if st.sidebar.button("로그아웃"):
        st.session_state.user = None
        st.rerun()

    # 🎯 학생 화면
    if st.session_state.user['role'] == "student":

        tab_write, tab_calendar, tab_stats = st.tabs(["🌸 감사일기 작성", "📅 감사일기 캘린더", "📊 작성 통계"])

        with tab_write:
            st.subheader("오늘의 감사일기 작성")
            today = datetime.now().strftime("%Y-%m-%d")
            entries = []

        with st.form("gratitude_form"):
            for i in range(1, 4):
                col1, col2 = st.columns([1, 3])
                with col1:
                    target = st.text_input(f"감사 대상 {i}", key=f"target_{i}")
                with col2:
                    content = st.text_input(f"감사 내용 {i}", key=f"content_{i}")
                entries.append((target.strip(), content.strip()))
            share_option = st.checkbox("익명으로 공유")
            submitted = st.form_submit_button("저장하기")

                
                if submitted:
                    for idx, (target, content) in enumerate(entries, start=1):
                        if target or content:
                            ai_feedback = generate_feedback(content)
                            c.execute('''
                                INSERT INTO journal (date, student_id, entry_number, target, content, shared, ai_feedback)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (today, st.session_state.user['id'], idx, target, content, int(share_option), ai_feedback))
                    conn.commit()
                    st.success("감사일기 저장 완료!")

        with tab_calendar:
            st.subheader("📅 나의 감사일기 캘린더")
            c.execute('SELECT DISTINCT date FROM journal WHERE student_id = ?', (st.session_state.user['id'],))
            dates = [row[0] for row in c.fetchall()]
            events = [{"title": "작성 완료", "start": d} for d in dates]
            calendar(events=events, options={"initialView": "dayGridMonth", "locale": "ko"})

            sel_date = st.date_input("상세 보기 날짜 선택")
            sel_date_str = sel_date.strftime("%Y-%m-%d")
            c.execute('SELECT target, content, ai_feedback FROM journal WHERE student_id = ? AND date = ?', (st.session_state.user['id'], sel_date_str))
            results = c.fetchall()
            if results:
                for idx, (target, content, feedback) in enumerate(results, start=1):
                    st.markdown(f"**{idx}. {target}**: {content}")
                    st.markdown(f"🌟 AI 피드백: {feedback}")
            else:
                st.info("해당 날짜에는 작성 기록이 없습니다.")

        with tab_stats:
            st.subheader("📊 작성 통계")
            c.execute('SELECT COUNT(DISTINCT date) FROM journal WHERE student_id = ?', (st.session_state.user['id'],))
            total_days = c.fetchone()[0]
            st.metric("총 작성일 수", total_days)

            c.execute('SELECT COUNT(*) FROM journal WHERE student_id = ?', (st.session_state.user['id'],))
            total_entries = c.fetchone()[0]
            st.metric("총 작성 항목 수", total_entries)

    # 🎯 관리자 화면 (교사)
    else:
        st.subheader("📊 전체 학생 감사일기 관리")

        c.execute('SELECT u.username, COUNT(DISTINCT j.date) FROM users u LEFT JOIN journal j ON u.id = j.student_id WHERE u.role="student" GROUP BY u.id')
        data = c.fetchall()
        df_stats = pd.DataFrame(data, columns=["학생", "작성일 수"])
        st.dataframe(df_stats)

        selected_student = st.selectbox("학생 선택", ["전체 보기"] + list(df_stats["학생"]))

        if selected_student == "전체 보기":
            c.execute('''
                SELECT u.username, j.date, j.target, j.content, j.ai_feedback
                FROM journal j
                JOIN users u ON j.student_id = u.id
                ORDER BY j.date DESC
            ''')
        else:
            c.execute('''
                SELECT u.username, j.date, j.target, j.content, j.ai_feedback
                FROM journal j
                JOIN users u ON j.student_id = u.id
                WHERE u.username = ?
                ORDER BY j.date DESC
            ''', (selected_student,))
            
        rows = c.fetchall()
        df = pd.DataFrame(rows, columns=["학생", "날짜", "대상", "내용", "AI 피드백"])
        st.dataframe(df)

        st.download_button("📥 CSV 다운로드", data=df.to_csv(index=False), file_name="gratitude_journal.csv", mime="text/csv")
