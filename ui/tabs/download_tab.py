# table_labeling_tool/ui/tabs/download_tab.py
import streamlit as st
import pandas as pd
import time
from pathlib import Path
from core.data_handler import save_dataframe_to_bytes

def display_download_tab():
    """显示下载已标注数据的UI。"""
    st.header("📥 5. 下载与总结")

    original_df = st.session_state.get('df')
    if original_df is None:
        st.warning("原始数据尚未加载。请先在“1. 数据加载与编辑”页面加载数据。")
        return

    labeling_results_map = st.session_state.get('labeling_progress', {}).get('results', {})
    if not labeling_results_map:
        st.info("尚未执行任何标注任务，或标注未产生结果。请先在“4. 执行AI标注”页面运行。")
        return

    try:
        result_df = original_df.copy()
        defined_output_cols_set = set()
        for task_def in st.session_state.get('labeling_tasks', []):
            out_col = task_def.get('output_column')
            if out_col:
                defined_output_cols_set.add(out_col)
                if task_def.get('need_reason', False):
                    defined_output_cols_set.add(f"{out_col}_理由")
        
        for col_n in defined_output_cols_set:
            if col_n not in result_df.columns:
                result_df[col_n] = pd.NA

        for original_row_idx, proc_output in labeling_results_map.items():
            if original_row_idx not in result_df.index:
                st.warning(f"结果中的行索引 {original_row_idx} 在原始数据中未找到，跳过。")
                continue

            if proc_output.get('success') and isinstance(proc_output.get('result'), dict):
                llm_json_output = proc_output['result']
                for task_key, labeled_val in llm_json_output.items():
                    if task_key in result_df.columns:
                        if isinstance(labeled_val, dict): # {value, reason} 结构
                            result_df.loc[original_row_idx, task_key] = labeled_val.get('value', pd.NA)
                            reason_col = f"{task_key}_理由"
                            if reason_col in result_df.columns:
                                result_df.loc[original_row_idx, reason_col] = labeled_val.get('reason', pd.NA)
                        else: #直接值
                            result_df.loc[original_row_idx, task_key] = labeled_val
            else: # 标注失败或结果格式错误
                err_msg_short = f"错误: {proc_output.get('error', '未知错误')[:60]}"
                for col_n_fill_err in defined_output_cols_set:
                     if pd.isna(result_df.loc[original_row_idx, col_n_fill_err]): # 仅填充尚未被成功任务填充的列
                        result_df.loc[original_row_idx, col_n_fill_err] = err_msg_short
        
        st.subheader("标注结果预览 (最后10行)")
        st.dataframe(result_df.tail(10), use_container_width=True)

        st.subheader("下载选项")
        dl_fmt = st.selectbox("选择下载格式", ['xlsx', 'csv', 'parquet', 'jsonl'], key="final_dl_fmt")
        
        ts = time.strftime("%Y%m%d_%H%M%S")
        fn_stem_dl = "labeled_output"
        # 使用之前保存的上传文件名（如果存在）作为基础
        orig_fn = st.session_state.get('_uploaded_file_name_for_download_')
        if orig_fn: fn_stem_dl = Path(orig_fn).stem + "_labeled"
        
        final_fn_dl = f"{fn_stem_dl}_{ts}.{dl_fmt}"
        file_bytes_dl = save_dataframe_to_bytes(result_df, dl_fmt)

        if file_bytes_dl:
            st.download_button(
                f"📥 下载标注结果 ({dl_fmt.upper()})", file_bytes_dl, final_fn_dl,
                type="primary", key="dl_final_btn"
            )
        else: st.error(f"无法生成 {dl_fmt.upper()} 文件供下载。")

        st.subheader("标注统计总结")
        total_df_rows = len(original_df)
        processed_c = len(labeling_results_map)
        successful_c = sum(1 for res in labeling_results_map.values() if res.get('success'))
        success_r = (successful_c / processed_c * 100) if processed_c > 0 else 0

        stat_cols_dl = st.columns(4)
        stat_cols_dl[0].metric("原始数据总行数", total_df_rows)
        stat_cols_dl[1].metric("已尝试标注行数", processed_c)
        stat_cols_dl[2].metric("成功标注行数", successful_c)
        stat_cols_dl[3].metric("标注成功率", f"{success_r:.1f}%")

    except Exception as e:
        st.error(f"准备下载数据或统计时发生错误: {e}")
        st.exception(e)