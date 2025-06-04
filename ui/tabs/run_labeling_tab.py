# table_labeling_tool/ui/tabs/run_labeling_tab.py
import streamlit as st
import pandas as pd
import concurrent.futures
import time
import json # 用于显示结果
from core.openai_caller import process_single_row
from core.utils import extract_placeholder_columns_from_final_prompt

def display_run_labeling_tab():
    """Displays the UI for running test and full labeling processes."""
    st.header("🏷️ 4. 执行AI标注")

    final_prompt = st.session_state.get('final_user_prompt', "").strip()
    current_df = st.session_state.get('df')
    api_key_present = st.session_state.get('api_config', {}).get('api_key')

    # --- Pre-requisite checks ---
    if not final_prompt:
        st.warning("最终用户Prompt尚未生成或为空。请先在“3. 生成AI指令”页面完成。")
        return
    if current_df is None or current_df.empty:
        st.warning("数据尚未加载或为空。请先在“1. 数据加载与编辑”页面加载。")
        return
    if not api_key_present:
        st.warning("API密钥尚未配置。请在侧边栏设置。")
        return

    # Use the (now improved) extract_placeholder_columns_from_final_prompt
    placeholders = extract_placeholder_columns_from_final_prompt(final_prompt)
    if not placeholders:
         st.error("❌ 最终用户Prompt中未找到任何数据占位符 (如 `{列名}`)。无法执行标注。请返回“生成Prompt”页面修改。")
         return
    missing_cols = [ph for ph in placeholders if ph not in current_df.columns]
    if missing_cols:
        st.error(f"❌ **列名不匹配:** Prompt中的占位符 `{', '.join(missing_cols)}` 在数据中找不到。\n请修改Prompt或检查数据列名。")
        return
    st.success(f"✅ Prompt中的占位符 `{', '.join(placeholders)}` 均已在数据列中找到。可以开始标注。")

    # --- Test Labeling Section ---
    st.subheader("🔬 试标注") 

    col_sample_method, col_num_rows = st.columns([1,1])
    with col_sample_method:
        test_sample_method = st.radio(
            "选择试标注方式:",
            options=["前 N 行", "随机 N 行"],
            index=0, 
            key="test_sample_method_radio",
            horizontal=True, 
        )
    
    df_len = len(current_df) if current_df is not None else 0

    with col_num_rows:
        num_test_rows_default = min(5, df_len) if df_len > 0 else 1
        num_test_rows_max = min(20, df_len) if df_len > 0 else 1 # Max 20 for test
        
        num_test_rows = st.number_input(
            "选择试标注的行数 (N):", 
            min_value=1, 
            max_value=num_test_rows_max, 
            value=num_test_rows_default, 
            step=1, 
            key="num_test_rows_input_v2", # Changed key to avoid conflicts if old one was used
            disabled=(df_len == 0) 
        )

    if st.button(f"执行试标注", key="run_test_labeling_btn", disabled=(df_len == 0)):
        if st.session_state.get('labeling_progress', {}).get('is_running'):
            st.error("已有标注任务进行中，请等待完成或检查是否有未处理的错误。")
        else:
            if test_sample_method == "前 N 行":
                test_df = current_df.head(num_test_rows)
            elif test_sample_method == "随机 N 行":
                sample_n = min(num_test_rows, df_len) 
                if sample_n > 0 :
                    test_df = current_df.sample(n=sample_n, random_state=None) # random_state=None 每次都随机
                else:
                    test_df = pd.DataFrame() # 如果可采样数为0，则为空DataFrame
            else: # 默认或意外情况
                test_df = current_df.head(num_test_rows)

            if test_df.empty:
                st.info("无数据可供试标注（可能是原数据为空，或选择的行数为0）。")
            else:
                st.session_state.labeling_progress = {
                    'is_running': True, 
                    'completed': 0,
                    'total': len(test_df), 
                    'results': {}, 
                    'is_test_run': True
                }
                
                st.info(f"开始对 {len(test_df)} 条数据（方式：{test_sample_method}）进行试标注...")
                progress_bar_test = st.progress(0)
                progress_text_test = st.empty() 
                results_container = st.container() 
                results_container.markdown("---") 

                # Get ordered_keys for process_single_row
                ordered_keys = st.session_state.get('ordered_input_cols_for_prompt', [])
                if not ordered_keys:
                    st.error("错误：未能获取用于Prompt的有序输入列列表 (ordered_input_cols_for_prompt)。请确保在“生成AI指令”步骤中已正确生成。")
                    st.session_state.labeling_progress['is_running'] = False # Stop the process
                    return # Stop execution

                try:
                    for original_idx, row_series in test_df.iterrows():
                        row_dict = row_series.to_dict()
                        
                        # Pass ordered_keys to process_single_row
                        actual_idx, result_data = process_single_row(
                            (original_idx, row_dict), 
                            final_prompt, 
                            st.session_state.api_config,
                            ordered_keys, # Pass the ordered list of column names
                            st.session_state.retry_attempts, 
                            st.session_state.request_delay
                        )
                        
                        st.session_state.labeling_progress['results'][actual_idx] = result_data
                        st.session_state.labeling_progress['completed'] += 1
                        
                        completed_count = st.session_state.labeling_progress['completed']
                        total_count = st.session_state.labeling_progress['total']
                        
                        progress_percentage = completed_count / total_count if total_count > 0 else 0
                        progress_bar_test.progress(progress_percentage)
                        progress_text_test.text(f"试标注进度: {completed_count}/{total_count} 条已处理")

                        with results_container:
                            current_display_count = st.session_state.labeling_progress['completed']
                            st.markdown(f"##### 处理结果 {current_display_count} (原始行索引: {actual_idx})")
                            
                            prompt_sent_display = result_data.get("prompt_sent")
                            if prompt_sent_display:
                                with st.expander(f"查看发送给模型的完整Prompt (原始行索引: {actual_idx})", expanded=False):
                                    st.code(prompt_sent_display, language='text', line_numbers=False)
                            else:
                                st.caption(f"未能为行 {actual_idx} 生成或获取发送的Prompt。")

                            if result_data.get('success'):
                                st.markdown("###### 模型返回的解析后结果:")
                                st.json(result_data.get('result'))
                            else:
                                st.error(f"处理错误 (原始行索引: {actual_idx}): {result_data.get('error')}")
                                raw_response_display = result_data.get("raw_response")
                                if raw_response_display:
                                    with st.expander(f"查看原始响应 (原始行索引: {actual_idx} - 通常在JSON解析失败时)", expanded=False):
                                        st.code(raw_response_display, language='text', line_numbers=False)
                            st.markdown("---") 
                    
                    progress_text_test.text(f"试标注完成: {st.session_state.labeling_progress['completed']}/{st.session_state.labeling_progress['total']} 条已处理。")
                    st.success("试标注完成！")

                except Exception as e:
                    st.error(f"试标注过程中发生意外错误: {e}")
                finally:
                    st.session_state.labeling_progress['is_running'] = False
    
    # --- Full Data Labeling Section ---
    st.divider()
    st.subheader("🚀 全量数据标注")
    if st.button("开始全量标注所有数据", type="primary", key="run_full_labeling_btn"):
        if st.session_state.get('labeling_progress', {}).get('is_running'):
            st.error("已有标注任务进行中，请等待完成。")
        else:
            total_rows = len(current_df) if current_df is not None else 0
            if total_rows == 0: 
                st.info("无数据可标注。")
                return

            st.session_state.labeling_progress = {
                'is_running': True, 
                'completed': 0, 
                'total': total_rows,
                'results': {}, 
                'is_test_run': False 
            }
            st.info(f"开始对全部 {total_rows} 条数据进行标注... 这可能需要一些时间。")
            progress_bar_full = st.progress(0, text="0% 完成")
            status_text_full = st.empty()
            start_time = time.time()
            
            data_for_exec = [(idx, row.to_dict()) for idx, row in current_df.iterrows()]
            
            workers = st.session_state.concurrent_workers
            api_conf = st.session_state.api_config.copy()
            retries = st.session_state.retry_attempts
            delay = st.session_state.request_delay

            # Get ordered_keys for process_single_row to be used by threads
            ordered_keys = st.session_state.get('ordered_input_cols_for_prompt', [])
            if not ordered_keys:
                st.error("错误：未能获取用于Prompt的有序输入列列表 (ordered_input_cols_for_prompt)。请确保在“生成AI指令”步骤中已正确生成。")
                st.session_state.labeling_progress['is_running'] = False # Stop the process
                return # Stop execution

            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                    # Pass ordered_keys to process_single_row in executor.submit
                    future_to_idx_map = {
                        executor.submit(process_single_row, item, final_prompt, api_conf, ordered_keys, retries, delay): item[0]
                        for item in data_for_exec
                    }
                    for future in concurrent.futures.as_completed(future_to_idx_map):
                        original_idx = future_to_idx_map[future]
                        try:
                            returned_idx, result_data = future.result()
                            st.session_state.labeling_progress['results'][returned_idx] = result_data
                        except Exception as exc:
                            st.session_state.labeling_progress['results'][original_idx] = {
                                'success': False, 'result': None, 'error': f"任务执行失败 (Future): {exc}",
                                'prompt_sent': "获取失败，因任务在发送前出错或Future本身出错", 'raw_response': None
                            }
                        finally:
                            st.session_state.labeling_progress['completed'] += 1
                            prog = st.session_state.labeling_progress['completed'] / total_rows if total_rows > 0 else 0
                            el_time = time.time() - start_time
                            avg_t = el_time / st.session_state.labeling_progress['completed'] if st.session_state.labeling_progress['completed'] > 0 else 0
                            eta = (total_rows - st.session_state.labeling_progress['completed']) * avg_t if avg_t > 0 else 0
                            progress_bar_full.progress(prog, text=f"{prog*100:.0f}% ({st.session_state.labeling_progress['completed']}/{total_rows})")
                            if status_text_full: 
                                status_text_full.text(f"已处理: {st.session_state.labeling_progress['completed']}/{total_rows}. 耗时: {el_time:.1f}s. 平均: {avg_t:.2f}s/条. 预计剩余: {eta:.0f}s.")
                st.success("全量标注完成！")
            except Exception as e:
                st.error(f"全量标注过程中发生严重错误: {e}")
            finally:
                st.session_state.labeling_progress['is_running'] = False
                if status_text_full: 
                    status_text_full.empty()

    # --- Display Stats and Errors ---
    current_prog = st.session_state.get('labeling_progress', {})
    if current_prog and current_prog.get('completed', 0) > 0 and not current_prog.get('is_running'):
        st.subheader("最新标注运行统计") 
        
        valid_results = {k: v for k, v in current_prog.get('results', {}).items() if v is not None}
        total_actually_processed_in_results = len(valid_results)
        
        if total_actually_processed_in_results > 0:
            run_type_str = "试标注" if current_prog.get('is_test_run') else "全量标注"
            total_for_this_run = current_prog.get('total', 0) 
            success_c = sum(1 for res_d in valid_results.values() if res_d.get('success'))
            error_c = total_actually_processed_in_results - success_c

            st.metric(f"{run_type_str} - 处理并记录结果的行数", f"{total_actually_processed_in_results} / {total_for_this_run}")
            m_c1, m_c2 = st.columns(2)
            m_c1.metric("成功", success_c)
            m_c2.metric("失败", error_c, delta=str(error_c) if error_c > 0 else "0", delta_color="inverse" if error_c > 0 else "normal")

            if error_c > 0:
                with st.expander(f"⚠️ 查看 {error_c} 条失败详情 (基于原始行索引)", expanded=False):
                    err_df_data = [{"原始行索引": orig_idx, "错误信息": res_d.get('error', '未知')}
                                   for orig_idx, res_d in valid_results.items() if not res_d.get('success')]
                    if err_df_data: st.dataframe(pd.DataFrame(err_df_data), use_container_width=True)
        else:
            st.caption("当前运行未记录有效结果用于统计。")

    current_prog = st.session_state.get('labeling_progress', {})
    if current_prog and current_prog.get('completed', 0) > 0 and not current_prog.get('is_running'):
        if current_prog.get('results'): 
            st.success("🎉 标注任务已执行！")
            st.info("下一步：请前往 **📥 5. 下载与总结** 标签页，预览、统计并下载包含标注结果的数据。")
            st.markdown("---")