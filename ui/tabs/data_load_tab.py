# table_labeling_tool/ui/tabs/data_load_tab.py
import streamlit as st
import pandas as pd
from pathlib import Path
from core.data_handler import load_data_from_uploaded_file, save_dataframe_to_bytes, load_data_from_path
from ui.ui_utils import refresh_data_editor

def display_data_load_tab():
    """显示数据加载、预览和基础编辑的UI。"""
    st.header("📁 1. 数据加载与编辑")

    if st.session_state.get('current_data_path'):
        st.info(f"当前数据文件路径 (来自已加载的任务流程): `{st.session_state.current_data_path}`")
        if st.button("🔄 尝试从该路径重新加载文件"):
            df = load_data_from_path(st.session_state.current_data_path)
            if df is not None:
                st.session_state.df = df
                st.session_state._uploaded_file_name_for_download_ = Path(st.session_state.current_data_path).name
                st.success(f"从路径重新加载数据成功！共 {len(df)} 行，{len(df.columns)} 列。")
                refresh_data_editor()
                st.rerun()
            else:
                st.error("从路径重新加载数据失败。文件可能已移动或损坏。")

    uploaded_file = st.file_uploader(
        "选择或拖放数据文件到此处",
        type=['csv', 'xlsx', 'xls', 'parquet', 'jsonl'],
        help="支持CSV, Excel (XLSX, XLS), Parquet, JSONL。上传新文件将替换当前数据。"
    )

    if uploaded_file is not None:
        file_content = uploaded_file.read()
        # Store filename for later use in download naming
        st.session_state._uploaded_file_name_for_download_ = uploaded_file.name
        df = load_data_from_uploaded_file(file_content, uploaded_file.name)
        if df is not None:
            st.session_state.df = df
            st.session_state.current_data_path = None # 清除路径，因为是新上传的文件
            st.success(f"成功加载数据: '{uploaded_file.name}' ({len(df)}行, {len(df.columns)}列)")
            refresh_data_editor()
            st.rerun() # Rerun to ensure UI updates immediately after new data upload

    df_display = st.session_state.get('df')

    if df_display is not None and isinstance(df_display, pd.DataFrame):
        st.subheader("数据预览与编辑")
        st.caption(f"共 {len(df_display)} 行, {len(df_display.columns)} 列。")

        search_col1, search_col2 = st.columns([3, 1])
        with search_col1:
            search_term = st.text_input("🔍 搜索内容 (不区分大小写)", key="data_search_term").strip()
        with search_col2:
            search_in_column = "全部列" # 默认
            if not df_display.empty:
                search_in_column = st.selectbox("在指定列中搜索", ["全部列"] + list(df_display.columns), key="data_search_column")
        
        active_df_view = df_display.copy()
        if search_term:
            try:
                if search_in_column == "全部列":
                    mask = active_df_view.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
                else:
                    mask = active_df_view[search_in_column].astype(str).str.contains(search_term, case=False, na=False)
                active_df_view = active_df_view[mask]
                st.caption(f"搜索结果: {len(active_df_view)} 行匹配。")
            except Exception as e:
                st.error(f"搜索时出错: {e}")

        st.info("ℹ️ 可直接在下方表格中编辑数据。修改会实时反映。使用表格上方的 +/- 按钮添加/删除行。")
        editor_key = f"data_editor_{st.session_state.get('data_editor_key', 0)}"
        edited_df_view = st.data_editor(
            active_df_view,
            num_rows="dynamic",
            use_container_width=True,
            key=editor_key,
            height=400
        )

        if not active_df_view.equals(edited_df_view):
            if search_term: # 处理搜索时的编辑
                st.warning("在搜索结果中编辑数据：修改将尝试应用回原始数据框。复杂操作（如在搜索视图中添加/删除行）建议清除搜索后进行。")
                try:
                    # 更新原始DataFrame中与过滤视图匹配的行
                    # edited_df_view 的索引可能与 active_df_view（保留原始索引）不同
                    # 我们需要基于 active_df_view 的原始索引来更新 st.session_state.df
                    
                    # 创建一个临时DataFrame，其索引与active_df_view的索引对齐
                    temp_edited_df = edited_df_view.copy()
                    temp_edited_df.index = active_df_view.index[:len(temp_edited_df)]

                    st.session_state.df.update(temp_edited_df)

                    # 处理行数变化 (如果data_editor允许在搜索视图中增删行)
                    # 这部分逻辑比较复杂且易出错，data_editor在搜索视图中增删行行为可能不直观
                    # 简单起见，提示用户清除搜索后操作或依赖data_editor自身行为
                    # if len(edited_df_view) != len(active_df_view):
                    #    pass # 暂不处理搜索视图中的行增删同步到主df

                    st.success("更改已尝试应用到主数据表。")
                    # refresh_data_editor() # 刷新以确保视图一致性
                    # st.rerun() # 立即反映更改

                except Exception as e:
                    st.error(f"更新搜索结果中的数据时出错: {e}。建议清除搜索后重试。")
            else: # 非搜索状态下的编辑
                st.session_state.df = edited_df_view.copy()
                st.success("更改已保存到当前会话数据。")
                # st.rerun() # 如果其他元素依赖行数等，可能需要

        st.divider()
        st.subheader("列操作")
        if not df_display.empty:
            cols_to_delete = st.multiselect("选择要删除的列", options=list(st.session_state.df.columns), key="cols_to_delete_select")
            if cols_to_delete:
                if st.button("🗑️ 删除选中列", key="delete_sel_cols_btn"):
                    confirm_key_cols_del = 'confirm_delete_cols_main_tab'
                    if st.session_state.get(confirm_key_cols_del, False):
                        st.session_state.df = st.session_state.df.drop(columns=cols_to_delete)
                        st.success(f"已删除列: {', '.join(cols_to_delete)}")
                        st.session_state[confirm_key_cols_del] = False
                        refresh_data_editor()
                        st.rerun()
                    else:
                        st.session_state[confirm_key_cols_del] = True
                        st.warning(f"再次点击确认删除列: {', '.join(cols_to_delete)}。")
        else:
            st.caption("无列可操作。")

        st.subheader("下载编辑后数据")
        if not df_display.empty:
            dl_format = st.selectbox("选择下载格式", ['csv', 'xlsx', 'parquet', 'jsonl'], key="dl_edited_format")
            
            fn_stem = "edited_data"
            if st.session_state.get('_uploaded_file_name_for_download_'):
                fn_stem = Path(st.session_state['_uploaded_file_name_for_download_']).stem + "_edited"
            
            file_bytes = save_dataframe_to_bytes(st.session_state.df, dl_format)
            if file_bytes:
                st.download_button(
                    f"📥 下载编辑后数据 ({dl_format.upper()})",
                    file_bytes,
                    f"{fn_stem}.{dl_format}",
                    key="dl_edited_data_btn"
                )
        else:
            st.caption("无数据可下载。")

    elif uploaded_file is None and st.session_state.get('df') is None:
        st.info("请上传一个数据文件开始。")