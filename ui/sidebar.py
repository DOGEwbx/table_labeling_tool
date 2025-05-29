# table_labeling_tool/ui/sidebar.py
import streamlit as st
from datetime import datetime
from pathlib import Path

from core.config_manager import (
    load_api_configs, save_api_configs,
    load_task_configs, save_task_configs, save_current_task_config,
    check_data_file_exists
)
# 导入新的持久化函数和数据加载函数
from core.data_handler import load_data_from_path, persist_dataframe_on_server
from ui.ui_utils import refresh_task_form, refresh_data_editor

def display_sidebar():
    """显示侧边栏UI元素，用于API和任务配置。"""
    with st.sidebar:
        st.title("🛠️ 工具配置")

        # --- Section 1: 任务流程管理 (默认展开) ---
        with st.expander("📋 任务流程管理", expanded=True):
            st.subheader("保存当前任务流程")
            current_task_name_input = st.text_input(
                "当前任务流程命名",
                placeholder="例如：项目评估流程v1",
                key="sidebar_task_name_input"
            ).strip()

            # 条件化显示“持久化数据”选项
            show_persist_data_option = False
            if st.session_state.get('df') is not None and st.session_state.get('current_data_path') is None:
                # 仅当数据已加载且不是从现有路径加载时（即通过上传加载）
                show_persist_data_option = True
            
            persist_data_checkbox = False # 初始化
            if show_persist_data_option:
                persist_data_checkbox = st.checkbox(
                    "同时保存当前已上传数据的副本?",
                    value=False, # 默认不勾选
                    help="如果勾选，当前通过“文件上传”加载的数据将被保存到服务器的一个副本，并将该副本路径与此任务流程关联。否则，此任务流程将不关联特定数据文件路径（除非数据本身是从路径加载的）。",
                    key="sidebar_persist_data_checkbox"
                )

            if st.button("💾 保存当前完整任务流程", key="sidebar_save_flow_btn"):
                if not current_task_name_input:
                    st.error("请输入任务流程名称。")
                elif not st.session_state.get('labeling_tasks'):
                    st.error("请先在“2. 定义打标任务”标签页中定义至少一个打标任务。")
                else:
                    data_path_to_save = st.session_state.get('current_data_path') # 默认使用已有的路径

                    if show_persist_data_option and persist_data_checkbox:
                        # 用户选择持久化上传的数据
                        current_df = st.session_state.get('df')
                        original_file_name_for_persist = st.session_state.get('_uploaded_file_name_for_download_')

                        if current_df is not None and original_file_name_for_persist is not None:
                            saved_server_path = persist_dataframe_on_server(current_df, original_file_name_for_persist)
                            if saved_server_path:
                                data_path_to_save = saved_server_path
                                # 更新会话中的current_data_path，以便UI能立即反映这个新路径
                                st.session_state.current_data_path = saved_server_path 
                                st.success(f"上传的数据副本已保存到服务器，并与此流程关联。")
                            else:
                                st.error("尝试保存上传数据副本失败。此任务流程将不关联特定数据路径。")
                                data_path_to_save = None # 确保如果持久化失败，不保存错误的路径
                        else:
                            st.warning("无法找到要持久化的数据或原始文件名。任务流程将不关联特定数据路径。")
                            data_path_to_save = None
                    
                    try:
                        save_current_task_config(current_task_name_input, data_path_to_save)
                        st.success(f"任务流程配置 '{current_task_name_input}' 已保存！")
                        st.rerun() # 刷新侧边栏列表
                    except Exception as e:
                        st.error(f"保存任务流程配置失败: {str(e)}")
            
            st.divider()
            st.subheader("加载历史任务流程")
            task_configs_on_disk = load_task_configs()
            if not task_configs_on_disk:
                st.caption("尚无已保存的任务流程。")
            else:
                sorted_task_names = sorted(
                    list(task_configs_on_disk.keys()),
                    key=lambda k: task_configs_on_disk[k].get('created_time', '0'),
                    reverse=True
                )
                selected_hist_task_name = st.selectbox(
                    "选择历史任务流程", 
                    [""] + sorted_task_names, 
                    format_func=lambda x: x if x else "请选择...",
                    key="sidebar_select_hist_task"
                )

                if selected_hist_task_name and selected_hist_task_name in task_configs_on_disk:
                    task_to_load = task_configs_on_disk[selected_hist_task_name]
                    created_time_str = task_to_load.get('created_time', '未知')
                    try:
                        created_dt = datetime.fromisoformat(created_time_str).strftime('%Y-%m-%d %H:%M')
                    except:
                        created_dt = '未知日期格式'
                    
                    st.markdown(f"""
                    **配置详情:**
                    - **创建时间:** {created_dt}
                    - **打标任务数:** {len(task_to_load.get('labeling_tasks', []))}
                    """)
                    
                    data_path_from_config = task_to_load.get('data_path')
                    can_load_data_from_path = False
                    if data_path_from_config:
                        if check_data_file_exists(data_path_from_config):
                            st.success(f"✅ 数据文件路径已关联: `{Path(data_path_from_config).name}` (文件存在)")
                            can_load_data_from_path = True
                        else:
                            st.warning(f"⚠️ 数据文件路径已关联: `{data_path_from_config}` (但文件当前不存在或不可访问)")
                    else:
                        st.info("ℹ️ 此任务流程未明确关联特定数据文件路径。")

                    col_l1, col_l2 = st.columns(2)
                    with col_l1:
                        if st.button(f"🔄 加载此流程", key=f"sidebar_load_task_btn_{selected_hist_task_name}"):
                            try:
                                st.session_state.api_config = task_to_load.get('api_config', st.session_state.api_config)
                                st.session_state.labeling_tasks = task_to_load.get('labeling_tasks', [])
                                st.session_state.generated_prompt_template = task_to_load.get('generated_prompt_template', task_to_load.get('generated_prompt', '')) 
                                st.session_state.final_user_prompt = task_to_load.get('final_user_prompt', task_to_load.get('processed_prompt', ''))
                                st.session_state.concurrent_workers = task_to_load.get('concurrent_workers', st.session_state.concurrent_workers)
                                st.session_state.retry_attempts = task_to_load.get('retry_attempts', st.session_state.retry_attempts)
                                st.session_state.request_delay = task_to_load.get('request_delay', st.session_state.request_delay)
                                
                                st.session_state.df = None 
                                st.session_state.current_data_path = None
                                st.session_state._uploaded_file_name_for_download_ = None
                                if 'last_uploaded_file_details' in st.session_state: # 重置文件上传状态
                                    del st.session_state.last_uploaded_file_details

                                if can_load_data_from_path and data_path_from_config:
                                    df_loaded = load_data_from_path(data_path_from_config)
                                    if df_loaded is not None:
                                        st.session_state.df = df_loaded
                                        st.session_state.current_data_path = data_path_from_config
                                        st.session_state._uploaded_file_name_for_download_ = Path(data_path_from_config).name
                                        st.success(f"数据文件 '{Path(data_path_from_config).name}' 已成功加载。")
                                    else:
                                        st.error(f"尝试从路径 '{Path(data_path_from_config).name}' 加载数据失败。请在“数据加载”页手动操作。")
                                
                                st.success(f"任务流程 '{selected_hist_task_name}' 加载成功！")
                                refresh_task_form()
                                refresh_data_editor()
                                st.rerun()
                            except Exception as e:
                                st.error(f"加载任务流程 '{selected_hist_task_name}' 失败: {str(e)}")
                    with col_l2:
                        if st.button(f"🗑️ 删除此流程", key=f"sidebar_delete_task_btn_{selected_hist_task_name}", type="secondary"):
                            confirm_key_task_del = f'confirm_delete_task_flow_{selected_hist_task_name}'
                            if st.session_state.get(confirm_key_task_del, False):
                                del task_configs_on_disk[selected_hist_task_name]
                                save_task_configs(task_configs_on_disk)
                                st.success(f"已删除任务流程: {selected_hist_task_name}")
                                st.session_state[confirm_key_task_del] = False
                                st.rerun()
                            else:
                                st.session_state[confirm_key_task_del] = True
                                st.warning(f"再次点击确认删除任务流程 '{selected_hist_task_name}'。")
        
        # --- Section 2: API 调用配置 ---
        with st.expander("🔑 API 调用配置", expanded=False):
            api_configs_on_disk = load_api_configs()
            config_names = list(api_configs_on_disk.keys())
            current_selection_label = "当前会话中的配置"
            options = [current_selection_label] + config_names
            
            selected_api_config_name = st.selectbox(
                "选择或管理API配置",
                options=options,
                help="选择一个已保存的API配置，或管理当前在会话中的配置。",
                key="sidebar_select_api_config"
            )

            if selected_api_config_name != current_selection_label and selected_api_config_name in api_configs_on_disk:
                if st.button(f"🔄 加载选中API配置: {selected_api_config_name}", key=f"sidebar_load_api_btn_{selected_api_config_name}"):
                    st.session_state.api_config = api_configs_on_disk[selected_api_config_name].copy()
                    st.success(f"已加载API配置: {selected_api_config_name}")
                    st.rerun()

            current_api_conf = st.session_state.setdefault('api_config', {
                'api_key': '', 'base_url': 'https://api.deepseek.com',
                'model_name': 'deepseek-chat', 'temperature': 0.05, 'max_tokens': 1500
            })

            api_key_val = st.text_input("API Key", value=current_api_conf.get('api_key', ''), type="password", key="sidebar_api_key")
            base_url_val = st.text_input("Base URL", value=current_api_conf.get('base_url', 'https://api.deepseek.com'), key="sidebar_base_url")
            model_name_val = st.text_input("模型名称", value=current_api_conf.get('model_name', 'deepseek-chat'), key="sidebar_model_name")
            temperature_val = st.slider("Temperature", 0.0, 2.0, float(current_api_conf.get('temperature', 0.05)), 0.01, key="sidebar_temperature")
            max_tokens_val = st.number_input("最大Token数 (响应)", 50, 32000, int(current_api_conf.get('max_tokens', 1500)), 50, key="sidebar_max_tokens") # Increased max_tokens limit

            st.session_state.api_config.update({
                'api_key': api_key_val, 'base_url': base_url_val, 'model_name': model_name_val,
                'temperature': temperature_val, 'max_tokens': max_tokens_val
            })
            
            api_config_tag_to_save = st.text_input("为此API配置命名以便永久保存", placeholder="例如：MyGPT4-Config", key="sidebar_api_config_tag").strip()
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                if st.button("💾 保存此API配置到磁盘", key="sidebar_save_api_disk_btn"):
                    if api_config_tag_to_save:
                        if api_config_tag_to_save == current_selection_label:
                            st.warning(f"'{current_selection_label}' 是保留名称，请输入其他名称。")
                        else:
                            api_configs_on_disk[api_config_tag_to_save] = st.session_state.api_config.copy()
                            save_api_configs(api_configs_on_disk)
                            st.success(f"API配置已永久保存为: {api_config_tag_to_save}")
                            st.rerun() 
                    else:
                        st.warning("请输入配置名称。")
            with col_s2:
                if selected_api_config_name != current_selection_label and selected_api_config_name in api_configs_on_disk:
                    if st.button(f"🗑️ 删除已存API配置: {selected_api_config_name}", key=f"sidebar_delete_api_disk_btn_{selected_api_config_name}", type="secondary"):
                        confirm_key_api_del = f'confirm_delete_api_{selected_api_config_name}'
                        if st.session_state.get(confirm_key_api_del, False):
                            del api_configs_on_disk[selected_api_config_name]
                            save_api_configs(api_configs_on_disk)
                            st.success(f"已删除API配置: {selected_api_config_name}")
                            st.session_state[confirm_key_api_del] = False
                            st.rerun()
                        else:
                            st.session_state[confirm_key_api_del] = True
                            st.warning(f"再次点击确认删除API配置 '{selected_api_config_name}'。")
        
        # --- Section 3: 执行参数配置 ---
        with st.expander("⚙️ 执行参数配置", expanded=False):
            st.session_state.concurrent_workers = st.slider(
                "并发线程数", 1, 20, 
                st.session_state.get('concurrent_workers', 4), 
                key="sidebar_workers"
            )
            st.session_state.retry_attempts = st.slider(
                "失败重试次数", 0, 5, 
                st.session_state.get('retry_attempts', 3), 
                key="sidebar_retries"
            )
            st.session_state.request_delay = st.slider(
                "请求间隔(秒)", 0.0, 5.0, 
                st.session_state.get('request_delay', 0.2), 0.1, 
                key="sidebar_delay"
            )