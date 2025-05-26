# table_labeling_tool/ui/tabs/run_labeling_tab.py
import streamlit as st
import pandas as pd
import concurrent.futures
import time
import json # 用于显示结果
from core.openai_caller import process_single_row
from core.utils import extract_placeholder_columns_from_final_prompt

def display_run_labeling_tab():
    """显示运行测试和完整标注过程的UI。"""
    st.header("🏷️ 4. 执行AI标注")

    final_prompt = st.session_state.get('final_user_prompt', "").strip()
    current_df = st.session_state.get('df')
    api_key_present = st.session_state.get('api_config', {}).get('api_key')

    if not final_prompt:
        st.warning("最终用户Prompt尚未生成或为空。请先在“3. 生成AI指令”页面完成。")
        return
    if current_df is None or current_df.empty:
        st.warning("数据尚未加载或为空。请先在“1. 数据加载与编辑”页面加载。")
        return
    if not api_key_present:
        st.warning("API密钥尚未配置。请在侧边栏设置。")
        return

    placeholders = extract_placeholder_columns_from_final_prompt(final_prompt)
    if not placeholders:
         st.error("❌ 最终用户Prompt中未找到任何数据占位符 (如 `{列名}`)。无法执行标注。请返回“生成Prompt”页面修改。")
         return
    missing_cols = [ph for ph in placeholders if ph not in current_df.columns]
    if missing_cols:
        st.error(f"❌ **列名不匹配:** Prompt中的占位符 `{', '.join(missing_cols)}` 在数据中找不到。\n请修改Prompt或检查数据列名。")
        return
    st.success(f"✅ Prompt中的占位符 `{', '.join(placeholders)}` 均已在数据列中找到。可以开始标注。")

    st.subheader("🔬 试标注 (前N条数据)")
    num_test_rows = st.number_input("选择试标注的行数", min_value=1, max_value=min(20, len(current_df)), value=min(5, len(current_df)), step=1, key="num_test_rows_input")

    if st.button(f"执行试标注 (前 {num_test_rows} 条)", key="run_test_labeling_btn"):
        if st.session_state.get('labeling_progress', {}).get('is_running'):
            st.error("已有标注任务进行中，请等待完成。")
        else:
            test_df = current_df.head(num_test_rows)
            if test_df.empty:
                st.info("无数据可供试标注。")
            else:
                st.session_state.labeling_progress = {
                    'is_running': True, 'completed': 0, 'total': len(test_df),
                    'results': {}, 'is_test_run': True
                }
                st.info(f"开始对前 {len(test_df)} 条数据进行试标注...")
                progress_bar_test = st.progress(0)
                results_expander_test = st.expander("试标注结果详情 (实时更新)", expanded=True)
                
                test_results_sync = {} # Store results synchronously for display order
                for original_idx, row_series in test_df.iterrows():
                    row_dict = row_series.to_dict()
                    actual_idx, result_data = process_single_row(
                        (original_idx, row_dict), final_prompt, st.session_state.api_config,
                        st.session_state.retry_attempts, st.session_state.request_delay
                    )
                    st.session_state.labeling_progress['results'][actual_idx] = result_data
                    test_results_sync[actual_idx] = result_data # For ordered display
                    st.session_state.labeling_progress['completed'] += 1
                    progress_bar_test.progress(st.session_state.labeling_progress['completed'] / len(test_df))

                    with results_expander_test:
                        st.markdown(f"--- \n**原始行索引 {actual_idx} (显示行号 {test_df.index.get_loc(actual_idx) + 1}):**")
                        if result_data['success']:
                            st.json(result_data['result'])
                        else:
                            st.error(f"错误: {result_data['error']}")
                
                st.success("试标注完成！")
                st.session_state.labeling_progress['is_running'] = False

    st.divider()
    st.subheader("🚀 全量数据标注")
    if st.button("开始全量标注所有数据", type="primary", key="run_full_labeling_btn"):
        if st.session_state.get('labeling_progress', {}).get('is_running'):
            st.error("已有标注任务进行中，请等待完成。")
        else:
            total_rows = len(current_df)
            if total_rows == 0: st.info("无数据可标注。"); return

            st.session_state.labeling_progress = {
                'is_running': True, 'completed': 0, 'total': total_rows,
                'results': {}, 'is_test_run': False
            }
            st.info(f"开始对全部 {total_rows} 条数据进行标注... 这可能需要一些时间。")
            progress_bar_full = st.progress(0, text="0% 完成")
            status_text_full = st.empty()
            start_time = time.time()
            
            data_for_exec = [(idx, row.to_dict()) for idx, row in current_df.iterrows()]
            
            # 从会话状态一次性获取配置
            workers = st.session_state.concurrent_workers
            api_conf = st.session_state.api_config.copy()
            retries = st.session_state.retry_attempts
            delay = st.session_state.request_delay

            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                    future_to_idx_map = {
                        executor.submit(process_single_row, item, final_prompt, api_conf, retries, delay): item[0]
                        for item in data_for_exec
                    }
                    for future in concurrent.futures.as_completed(future_to_idx_map):
                        original_idx = future_to_idx_map[future]
                        try:
                            returned_idx, result_data = future.result()
                            st.session_state.labeling_progress['results'][returned_idx] = result_data # 使用返回的索引
                        except Exception as exc:
                            st.session_state.labeling_progress['results'][original_idx] = { # 出错时用原始索引
                                'success': False, 'result': None, 'error': f"任务执行失败: {exc}"}
                        finally:
                            st.session_state.labeling_progress['completed'] += 1
                            prog = st.session_state.labeling_progress['completed'] / total_rows
                            el_time = time.time() - start_time
                            avg_t = el_time / st.session_state.labeling_progress['completed'] if st.session_state.labeling_progress['completed'] > 0 else 0
                            eta = (total_rows - st.session_state.labeling_progress['completed']) * avg_t if avg_t > 0 else 0
                            progress_bar_full.progress(prog, text=f"{prog*100:.0f}% ({st.session_state.labeling_progress['completed']}/{total_rows})")
                            status_text_full.text(f"已处理: {st.session_state.labeling_progress['completed']}/{total_rows}. 耗时: {el_time:.1f}s. 平均: {avg_t:.2f}s/条. 预计剩余: {eta:.0f}s.")
                st.success("全量标注完成！")
            except Exception as e:
                st.error(f"全量标注过程中发生严重错误: {e}")
            finally:
                st.session_state.labeling_progress['is_running'] = False
                status_text_full.empty()

    current_prog = st.session_state.get('labeling_progress', {})
    if current_prog and current_prog.get('completed', 0) > 0:
        st.subheader("最新标注运行统计")
        total_proc = current_prog.get('completed', 0)
        total_att = current_prog.get('total', 0)
        run_type_str = "试标注" if current_prog.get('is_test_run') else "全量标注"
        success_c = sum(1 for res_d in current_prog.get('results', {}).values() if res_d.get('success'))
        error_c = total_proc - success_c

        st.metric(f"{run_type_str} - 已处理行数", f"{total_proc} / {total_att}")
        m_c1, m_c2 = st.columns(2)
        m_c1.metric("成功", success_c)
        m_c2.metric("失败", error_c, delta=str(error_c) if error_c > 0 else "0", delta_color="inverse" if error_c > 0 else "normal")

        if error_c > 0:
            with st.expander(f"⚠️ 查看 {error_c} 条失败详情 (基于原始行索引)", expanded=False):
                err_df_data = [{"原始行索引": orig_idx, "错误信息": res_d.get('error', '未知')}
                               for orig_idx, res_d in current_prog.get('results', {}).items() if not res_d.get('success')]
                if err_df_data: st.dataframe(pd.DataFrame(err_df_data), use_container_width=True)