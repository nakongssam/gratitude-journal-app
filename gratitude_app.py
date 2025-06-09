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
