import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd
import openai
from openai import OpenAI
from streamlit_calendar import calendar

# OpenAI API Key (보안 적용, 최신 openai 패키지 방식)
client = OpenAI(api_key=st.secrets["general"]["OPENAI_API_KEY"])

# DB 연결 및 초기화
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
            content TEXT,
            shared INTEGER DEFAULT 0,
            ai_feedback TEXT,
            FOREIGN KEY(student_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    return conn, c

conn, c = init_db()

# 유틸리티 함수
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

# 최신 openai 1.x 대응 GPT-4o 피드백 생성
def generate_positive_feedback(content):
    prompt = (
        f"학생이 작성한 감사일기입니다:\n\n\"{content}\"\n\n"
        f"이 글에서 혹시 부정적 표현이 있다면 긍정적 사고로 전환하도록 도와주고, 학생이 스스로 감사함을 느낄 수 있도록 짧고 따뜻하게 한두 문장으로 피드백을 작성해주세요."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"AI 피드백 생성 실패: {str(e)}"

# Streamlit 기본 세팅
st.set_page_config(page_title="AI 감사일기", page_icon="📘", layout="wide")
st.markdown("<h1 style='text-align:center; color:#4682B4;'>💙 AI 기반 감사일기 시스템 💙</h1>", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.session_state.user = None

# 로그인 & 회원가입 화면
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

# 로그인 이후 메인 화면
else:
    st.sidebar.write(f"👋 {st.session_state.user['username']}님 ({st.session_state.user['role']})")
    if st.sidebar.button("로그아웃"):
        st.session_state.user = None
        st.rerun()

    # 학생 화면
    if st.session_state.user['role'] == "student":

        tab_write, tab_calendar, tab_share, tab_stats = st.tabs(["🌸 감사일기 작성", "📅 감사일기 캘린더", "🌼 공유 감사일기 보기", "📊 작성 통계"])

        # 감사일기 작성 탭
        with tab_write:
            st.subheader("오늘의 감사일기 작성")
            today = datetime.now().strftime("%Y-%m-%d")

            content = st.text_area("오늘 하루 감사했던 일을 자유롭게 작성해보세요.", height=300)

            # AI 피드백 상태 초기화
            if 'ai_feedback' not in st.session_state:
                st.session_state.ai_feedback = ""

            if st.button("AI 피드백 생성하기"):
                if content.strip() == "":
                    st.warning("내용을 먼저 작성해주세요.")
                else:
                    with st.spinner("AI 피드백 생성 중..."):
                        st.session_state.ai_feedback = generate_positive_feedback(content)

            if st.session_state.ai_feedback:
                st.success("🌟 AI 피드백:")
                st.write(st.session_state.ai_feedback)

            share_option = st.checkbox("다른 학생들과 공유하기")
            if st.button("최종 저장하기"):
                if content.strip() == "":
                    st.warning("내용을 먼저 작성해주세요.")
                else:
                    c.execute('''
                        INSERT INTO journal (date, student_id, content, shared, ai_feedback)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (today, st.session_state.user['id'], content.strip(), int(share_option), st.session_state.ai_feedback))
                    conn.commit()
                    st.success("감사일기 저장 완료!")
                    st.session_state.ai_feedback = ""

        # 캘린더 탭 (작성한 날짜 ✅ 표시)
        with tab_calendar:
            st.subheader("📅 나의 감사일기 캘린더")
            c.execute('SELECT DISTINCT date FROM journal WHERE student_id = ?', (st.session_state.user['id'],))
            dates = [row[0] for row in c.fetchall()]
            events = [{"title": "✅ 작성 완료", "start": d} for d in dates]

            calendar(events=events, options={
                "initialView": "dayGridMonth",
                "locale": "ko",
                "height": 500,
                "headerToolbar": {
                    "left": "prev,next today",
                    "center": "title",
                    "right": "dayGridMonth,timeGridWeek"
                }
            })

            sel_date = st.date_input("상세 보기 날짜 선택")
            sel_date_str = sel_date.strftime("%Y-%m-%d")
            c.execute('SELECT content, ai_feedback FROM journal WHERE student_id = ? AND date = ?', (st.session_state.user['id'], sel_date_str))
            results = c.fetchall()
            if results:
                for idx, (content, feedback) in enumerate(results, start=1):
                    st.markdown(f"**내용:** {content}")
                    st.markdown(f"🌟 AI 피드백: {feedback}")
            else:
                st.info("해당 날짜에는 작성 기록이 없습니다.")

        # 공유 감사일기 탭
        with tab_share:
            st.subheader("🌼 다른 학생들의 감사일기")
            c.execute('''
                SELECT u.username, j.date, j.content, j.ai_feedback
                FROM journal j
                JOIN users u ON j.student_id = u.id
                WHERE shared = 1
                ORDER BY j.date DESC
            ''')
            shared_entries = c.fetchall()
            for username, date, content, feedback in shared_entries:
                with st.container():
                    st.markdown(f"🗓 **{date}** / 작성자: {username}")
                    st.markdown(f"💬 {content}")
                    st.markdown(f"🌟 AI 피드백: {feedback}")
                    st.markdown("---")

        # 작성 통계 탭
        with tab_stats:
            st.subheader("📊 작성 통계")
            c.execute('SELECT COUNT(DISTINCT date) FROM journal WHERE student_id = ?', (st.session_state.user['id'],))
            total_days = c.fetchone()[0]
            st.metric("총 작성일 수", total_days)

            c.execute('SELECT COUNT(*) FROM journal WHERE student_id = ?', (st.session_state.user['id'],))
            total_entries = c.fetchone()[0]
            st.metric("총 작성 기록 수", total_entries)

    # 관리자 화면 (교사)
    else:
        st.subheader("📊 전체 학생 감사일기 관리")

        c.execute('SELECT u.username, COUNT(DISTINCT j.date) FROM users u LEFT JOIN journal j ON u.id = j.student_id WHERE u.role="student" GROUP BY u.id')
        data = c.fetchall()
        df_stats = pd.DataFrame(data, columns=["학생", "작성일 수"])
        st.dataframe(df_stats)

        selected_student = st.selectbox("학생 선택", ["전체 보기"] + list(df_stats["학생"]))

        if selected_student == "전체 보기":
            c.execute('''
                SELECT u.username, j.date, j.content, j.ai_feedback
                FROM journal j
                JOIN users u ON j.student_id = u.id
                ORDER BY j.date DESC
            ''')
        else:
            c.execute('''
                SELECT u.username, j.date, j.content, j.ai_feedback
                FROM journal j
                JOIN users u ON j.student_id = u.id
                WHERE u.username = ?
                ORDER BY j.date DESC
            ''', (selected_student,))
            
        rows = c.fetchall()
        df = pd.DataFrame(rows, columns=["학생", "날짜", "내용", "AI 피드백"])
        st.dataframe(df)

        st.download_button("📥 CSV 다운로드", data=df.to_csv(index=False), file_name="gratitude_journal.csv", mime="text/csv")
