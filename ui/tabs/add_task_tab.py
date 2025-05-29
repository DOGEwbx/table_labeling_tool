# table_labeling_tool/ui/tabs/add_task_tab.py
import streamlit as st
import time
from ui.ui_utils import refresh_task_form

def display_add_task_tab():
    """显示添加和管理打标任务定义的UI。"""
    st.header("🎯 2. 定义打标任务")

    if st.session_state.get('df') is None:
        st.warning("请先在“1. 数据加载与编辑”页面上传或加载数据，以便选择输入列。")
        return

    df_columns = list(st.session_state.df.columns) if st.session_state.df is not None else []
    st.info(f"当前数据: {len(st.session_state.df)}行, {len(df_columns)}列。" if st.session_state.df is not None else "无数据加载。")

    form_key = f"add_task_form_{st.session_state.get('task_form_key', 0)}"
    with st.form(key=form_key):
        st.subheader("定义新的打标任务")
        input_cols = st.multiselect("选择输入列 (用于此任务)", options=df_columns, help="选择数据中哪些列将作为此标注任务的输入信息。")
        output_col_name = st.text_input("新输出列的名称", placeholder="例如：情感分析结果", help="为此标注任务生成的结果指定一个新的列名。").strip()
        task_requirement = st.text_area("详细打标需求/指令", placeholder="例如：判断文本情感是积极、消极还是中性。", height=100, help="清晰描述此任务的要求。")
        need_reason_cb = st.checkbox("要求AI提供判断理由", help="勾选后，AI会被要求为每个标注结果提供理由，会额外生成理由列。")
        
        submitted = st.form_submit_button("➕ 添加此任务到列表")
        if submitted:
            error_occured = False
            if not input_cols:
                st.error("请至少选择一个输入列。")
                error_occured = True
            if not output_col_name:
                st.error("请输入输出列的名称。")
                error_occured = True
            elif output_col_name in df_columns or any(t.get('output_column') == output_col_name for t in st.session_state.get('labeling_tasks', [])):
                st.error(f"输出列名 '{output_col_name}' 已存在于原始数据或已添加的任务中。请使用唯一的名称。")
                error_occured = True
            if not task_requirement:
                st.error("请填写打标需求。")
                error_occured = True
            
            if not error_occured:
                new_task = {
                    'input_columns': input_cols,
                    'output_column': output_col_name,
                    'requirement': task_requirement,
                    'need_reason': need_reason_cb,
                    'id': f"task_{int(time.time() * 1000)}_{len(st.session_state.get('labeling_tasks', []))}" # 保证唯一性
                }
                st.session_state.setdefault('labeling_tasks', []).append(new_task)
                st.success(f"打标任务 '{output_col_name}' 已添加到列表！")
                refresh_task_form()
                st.rerun()

    st.divider()
    if st.session_state.get('labeling_tasks'):
        st.subheader("已定义的打标任务列表")
        tasks_list = st.session_state.labeling_tasks
        if not tasks_list:
             st.info("尚未添加任何打标任务。")
        else:
            for i, task in enumerate(tasks_list):
                with st.expander(f"任务 {i+1}: 输出到 '{task.get('output_column', 'N/A')}'", expanded=True):
                    st.markdown(f"**输入列:** `{', '.join(task.get('input_columns', []))}`")
                    st.markdown(f"**输出列名:** `{task.get('output_column')}`")
                    st.markdown(f"**打标需求:**")
                    st.caption(task.get('requirement'))
                    st.markdown(f"**是否需要理由:** {'是' if task.get('need_reason') else '否'}")
                    if st.button("🗑️ 删除此任务", key=f"delete_defined_task_{task.get('id', i)}"):
                        st.session_state.labeling_tasks.pop(i)
                        st.success(f"任务 '{task.get('output_column')}' 已删除。")
                        st.rerun()
    else:
        st.info("尚未添加任何打标任务。请使用上方表单添加。")

    # --- 新增：引导到下一步 ---
    if st.session_state.get('labeling_tasks'):
        num_tasks = len(st.session_state.labeling_tasks)
        st.success(f"🎉 您已定义 {num_tasks} 个打标任务！")
        st.info("下一步：请前往 **📝 3. 生成AI指令 (Prompt)** 标签页，为这些任务创建AI指令模板。")
        st.markdown("---") # 可选的分隔线