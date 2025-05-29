# table_labeling_tool/ui/tabs/prompt_gen_tab.py
import streamlit as st
from core.openai_caller import generate_labeling_prompt_template
from core.utils import parse_ai_generated_prompt_template, extract_placeholder_columns_from_final_prompt

def display_prompt_generation_tab():
    """显示生成和编辑AI Prompt模板的UI。"""
    st.header("📝 3. 生成AI指令 (Prompt)")

    labeling_tasks = st.session_state.get('labeling_tasks', [])
    api_config = st.session_state.get('api_config', {})

    if not labeling_tasks:
        st.warning("请先在“2. 定义打标任务”页面定义至少一个打标任务。")
        return
    if not api_config.get('api_key'):
        st.warning("请先在侧边栏配置API密钥才能生成Prompt模板。")
        return
    # 数据加载不是生成模板的硬性要求，但对于校验占位符是必要的
    if st.session_state.get('df') is None:
        st.info("提示：数据尚未加载。加载数据后可在此页面校验Prompt中的列名。")

    col_act1, col_act2 = st.columns(2)
    with col_act1:
        if st.button("🤖 向AI请求生成Prompt模板", type="primary", help="使用当前定义的打标任务，让AI生成一个JSON格式的Prompt指令模板。"):
            with st.spinner("正在向AI请求生成Prompt模板... 请稍候..."):
                try:
                    ai_json_template = generate_labeling_prompt_template(labeling_tasks, api_config)
                    if ai_json_template:
                        st.session_state.generated_prompt_template = ai_json_template
                        st.success("AI成功生成了Prompt模板！请在下方查看和编辑。")
                        # 立即尝试解析并构建最终用户Prompt
                        st.session_state.final_user_prompt = parse_ai_generated_prompt_template(
                            ai_json_template, labeling_tasks
                        )
                        st.info("已尝试根据新模板构建最终用户Prompt，请检查下方预览。")
                    else:
                        st.error("AI未能生成Prompt模板，或返回为空。请检查API配置和错误信息（若有）。")
                except Exception as e:
                    st.error(f"生成Prompt模板时发生错误: {e}")
    with col_act2:
        if st.button("🗑️ 清空当前模板和预览", help="清除下方编辑框和最终用户Prompt预览。"):
            st.session_state.generated_prompt_template = ""
            st.session_state.final_user_prompt = ""
            st.success("Prompt模板和预览已清空。")

    st.subheader("步骤 1: AI生成的Prompt模板 (JSON格式)")
    st.caption("这是AI根据您的任务需求生成的JSON模板。您可以直接编辑此JSON。它指导如何为每个任务构建具体指令。")
    edited_template = st.text_area(
        "编辑AI生成的JSON Prompt模板:",
        value=st.session_state.get('generated_prompt_template', ""),
        height=350,
        key="json_template_editor",
        help="修改此JSON模板。修改后，下方的“最终用户Prompt预览”会自动更新。"
    )

    if edited_template != st.session_state.get('generated_prompt_template'):
        st.session_state.generated_prompt_template = edited_template
        if edited_template.strip():
            st.session_state.final_user_prompt = parse_ai_generated_prompt_template(
                edited_template, labeling_tasks
            )
            st.info("JSON模板已修改，最终用户Prompt预览已更新。")
        else:
            st.session_state.final_user_prompt = "" # 清空预览

    st.divider()
    st.subheader("步骤 2: 最终用户Prompt预览")
    final_prompt_preview = st.session_state.get('final_user_prompt', "")

    if not final_prompt_preview:
        st.info("此处将显示根据上方JSON模板构建的、将发送给AI进行每行数据标注的最终Prompt。它会包含数据占位符如 `{列名}`。")
    else:
        st.caption("这是根据上方JSON模板和您的任务定义构建的最终Prompt。占位符（如 `{列名}`）将在执行标注时被实际数据替换。")
        with st.expander("👁️ 点击查看/隐藏最终用户Prompt预览", expanded=True):
            st.code(final_prompt_preview, language="markdown")

        if st.session_state.get('df') is not None:
            st.subheader("✔️ Prompt占位符校验 (对照已加载数据)")
            df_cols = list(st.session_state.df.columns)
            placeholders = extract_placeholder_columns_from_final_prompt(final_prompt_preview)
            
            if not placeholders:
                st.warning("在最终用户Prompt预览中未检测到任何数据占位符 (例如 `{列名}`). 请确保您的Prompt模板能正确生成包含数据引用的指令。")
            else:
                missing, valid = [], []
                for ph in placeholders:
                    (valid if ph in df_cols else missing).append(ph)
                
                if valid:
                    st.markdown("**找到并匹配到数据列的占位符:**")
                    for vp in valid: st.markdown(f"- `{{{vp}}}` ✅ (对应数据列: **{vp}**)")
                if missing:
                    st.error("⚠️ **警告：以下占位符在最终用户Prompt中找到，但在当前加载的数据列中不存在:**")
                    for mp in missing: st.markdown(f"- `{{{mp}}}` ❌ (数据中无此列)")
                    st.info("请检查您的数据列名或修改Prompt模板，确保所有占位符都能正确匹配。")
                elif valid and not missing:
                    st.success("🎉 所有在最终用户Prompt中检测到的占位符都能在当前数据列中找到！")
        else:
            st.info("数据尚未加载，无法校验Prompt中的占位符与数据列是否匹配。")

    # --- 新增：引导到下一步 ---
    if st.session_state.get('final_user_prompt', "").strip():
        st.success("🎉 AI指令 (Prompt) 已成功生成并可供预览！")
        st.info("下一步：请前往 **🏷️ 4. 执行AI标注** 标签页，使用此Prompt进行试标注或全量标注。")
        st.markdown("---") # 可选的分隔线
    elif st.session_state.get('labeling_tasks') and st.session_state.get('api_config', {}).get('api_key'):
        # 如果任务已定义且API key已配置，但Prompt未生成，可以提醒用户生成
        if not st.session_state.get('generated_prompt_template', "").strip():
            st.caption("👆 请点击上方的“🤖 向AI请求生成Prompt模板”按钮，或在编辑框中手动输入模板。")