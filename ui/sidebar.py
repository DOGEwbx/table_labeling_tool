# table_labeling_tool/ui/sidebar.py
import streamlit as st
from datetime import datetime
from pathlib import Path
from core.config_manager import (
    load_api_configs, save_api_configs,
    load_task_configs, save_task_configs, save_current_task_config,
    check_data_file_exists
)
from core.data_handler import load_data_from_path # 用于随任务配置重新加载数据
from ui.ui_utils import refresh_task_form, refresh_data_editor # 用于刷新UI视图

def display_sidebar():
    """显示侧边栏UI元素，用于API和任务配置。"""
    with st.sidebar:
        st.header("⚙️ API 调用配置")

        api_configs_on_disk = load_api_configs()
        config_names = list(api_configs_on_disk.keys())
        current_selection_label = "当前会话中的配置"
        options = [current_selection_label] + config_names
        
        selected_config_name = st.selectbox(
            "选择或管理API配置",
            options=options,
            help="选择一个已保存的API配置，或管理当前在会话中的配置。"
        )

        if selected_config_name != current_selection_label and selected_config_name in api_configs_on_disk:
            if st.button(f"🔄 加载选中配置: {selected_config_name}", key=f"load_api_{selected_config_name}"):
                st.session_state.api_config = api_configs_on_disk[selected_config_name].copy()
                st.success(f"已加载API配置: {selected_config_name}")
                st.rerun()

        current_api_conf = st.session_state.setdefault('api_config', {
            'api_key': '', 'base_url': '[https://api.openai.com/v1](https://api.openai.com/v1)',
            'model_name': 'gpt-3.5-turbo', 'temperature': 0.05, 'max_tokens': 1500
        })

        api_key_val = st.text_input("API Key", value=current_api_conf.get('api_key', ''), type="password")
        base_url_val = st.text_input("Base URL", value=current_api_conf.get('base_url', '[https://api.openai.com/v1](https://api.openai.com/v1)'))
        model_name_val = st.text_input("模型名称", value=current_api_conf.get('model_name', 'gpt-3.5-turbo'))
        temperature_val = st.slider("Temperature", 0.0, 2.0, float(current_api_conf.get('temperature', 0.05)), 0.01)
        max_tokens_val = st.number_input("最大Token数 (响应)", 50, 16384, int(current_api_conf.get('max_tokens', 1500)), 50)

        # 实时更新会话中的API配置
        st.session_state.api_config.update({
            'api_key': api_key_val, 'base_url': base_url_val, 'model_name': model_name_val,
            'temperature': temperature_val, 'max_tokens': max_tokens_val
        })
        
        config_tag_to_save = st.text_input("为此API配置命名以便永久保存", placeholder="例如：MyGPT4-Config").strip()
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("💾 保存此API配置到磁盘", key="save_api_disk"):
                if config_tag_to_save:
                    if config_tag_to_save == current_selection_label:
                        st.warning(f"'{current_selection_label}' 是保留名称，请输入其他名称。")
                    else:
                        api_configs_on_disk[config_tag_to_save] = st.session_state.api_config.copy()
                        save_api_configs(api_configs_on_disk)
                        st.success(f"API配置已永久保存为: {config_tag_to_save}")
                        st.rerun() # 更新选择框
                else:
                    st.warning("请输入配置名称。")
        with col_s2:
            if selected_config_name != current_selection_label and selected_config_name in api_configs_on_disk:
                if st.button(f"🗑️ 删除已存配置: {selected_config_name}", key=f"delete_api_disk_{selected_config_name}"):
                    confirm_key = f'confirm_delete_api_{selected_config_name}'
                    if st.session_state.get(confirm_key, False):
                        del api_configs_on_disk[selected_config_name]
                        save_api_configs(api_configs_on_disk)
                        st.success(f"已删除API配置: {selected_config_name}")
                        st.session_state[confirm_key] = False
                        st.rerun()
                    else:
                        st.session_state[confirm_key] = True
                        st.warning(f"再次点击确认删除 '{selected_config_name}'。")
        st.divider()

        st.header("🔧 执行参数配置")
        st.session_state.concurrent_workers = st.slider("并发线程数", 1, 20, st.session_state.get('concurrent_workers', 4))
        st.session_state.retry_attempts = st.slider("失败重试次数", 0, 5, st.session_state.get('retry_attempts', 3))
        st.session_state.request_delay = st.slider("请求间隔(秒)", 0.0, 5.0, st.session_state.get('request_delay', 0.2), 0.1)
        st.divider()

        st.header("📋 任务流程管理")
        task_configs_on_disk = load_task_configs()
        current_task_name_input = st.text_input("当前任务流程命名（用于保存）", placeholder="例如：项目评估流程v1").strip()

        if st.button("💾 保存当前完整任务流程", key="save_full_task_flow"):
            if current_task_name_input:
                if not st.session_state.get('labeling_tasks'):
                    st.error("请先在“2. 定义打标任务”标签页中定义至少一个打标任务。")
                else:
                    try:
                        current_data_file_path = st.session_state.get('current_data_path')
                        save_current_task_config(current_task_name_input, current_data_file_path)
                        st.success(f"任务流程配置 '{current_task_name_input}' 已保存！")
                        st.rerun() # 更新下面的列表
                    except Exception as e:
                        st.error(f"保存任务流程失败: {str(e)}")
            else:
                st.error("请输入任务流程名称。")

        if task_configs_on_disk:
            st.subheader("📂 加载历史任务流程")
            sorted_task_names = sorted(
                list(task_configs_on_disk.keys()),
                key=lambda k: task_configs_on_disk[k].get('created_time', '0'),
                reverse=True
            )
            selected_hist_task_name = st.selectbox("选择历史任务流程", [""] + sorted_task_names, format_func=lambda x: x if x else "请选择...")

            if selected_hist_task_name and selected_hist_task_name in task_configs_on_disk:
                task_to_load = task_configs_on_disk[selected_hist_task_name]
                created_time_str = task_to_load.get('created_time', '未知')
                try:
                    created_dt = datetime.fromisoformat(created_time_str).strftime('%Y-%m-%d %H:%M')
                except:
                    created_dt = '未知'
                
                st.markdown(f"""
                **配置详情:**
                - **创建时间:** {created_dt}
                - **打标任务数:** {len(task_to_load.get('labeling_tasks', []))}
                """)
                data_path = task_to_load.get('data_path')
                can_load_data = False
                if data_path:
                    if check_data_file_exists(data_path):
                        st.success(f"✅ 数据文件存在: `{Path(data_path).name}`")
                        can_load_data = True
                    else:
                        st.warning(f"⚠️ 数据文件路径已记录但文件当前不存在: `{data_path}`")
                else:
                    st.info("ℹ️ 此任务流程未关联特定数据文件路径。")

                col_l1, col_l2 = st.columns(2)
                with col_l1:
                    if st.button(f"🔄 加载此流程 ({selected_hist_task_name})", key=f"load_hist_task_{selected_hist_task_name}"):
                        try:
                            st.session_state.api_config = task_to_load.get('api_config', st.session_state.api_config)
                            st.session_state.labeling_tasks = task_to_load.get('labeling_tasks', [])
                            st.session_state.generated_prompt_template = task_to_load.get('generated_prompt_template', task_to_load.get('generated_prompt', '')) # 兼容旧名
                            st.session_state.final_user_prompt = task_to_load.get('final_user_prompt', task_to_load.get('processed_prompt', '')) # 兼容旧名
                            st.session_state.concurrent_workers = task_to_load.get('concurrent_workers', st.session_state.concurrent_workers)
                            st.session_state.retry_attempts = task_to_load.get('retry_attempts', st.session_state.retry_attempts)
                            st.session_state.request_delay = task_to_load.get('request_delay', st.session_state.request_delay)
                            
                            st.session_state.df = None # 清除旧数据
                            st.session_state.current_data_path = None
                            if can_load_data and data_path:
                                df_loaded = load_data_from_path(data_path)
                                if df_loaded is not None:
                                    st.session_state.df = df_loaded
                                    st.session_state.current_data_path = data_path
                                    st.session_state._uploaded_file_name_for_download_ = Path(data_path).name # 用于下载时预设文件名
                                    st.success(f"数据文件 '{Path(data_path).name}' 已加载。")
                                else:
                                    st.error(f"尝试加载 '{Path(data_path).name}' 失败。请在“数据加载”页手动操作。")
                            
                            st.success(f"任务流程 '{selected_hist_task_name}' 加载成功！")
                            refresh_task_form()
                            refresh_data_editor()
                            st.rerun()
                        except Exception as e:
                            st.error(f"加载任务流程失败: {str(e)}")
                with col_l2:
                    if st.button(f"🗑️ 删除此流程", key=f"delete_hist_task_{selected_hist_task_name}"):
                        confirm_key_task = f'confirm_delete_task_flow_{selected_hist_task_name}'
                        if st.session_state.get(confirm_key_task, False):
                            del task_configs_on_disk[selected_hist_task_name]
                            save_task_configs(task_configs_on_disk)
                            st.success(f"已删除任务流程: {selected_hist_task_name}")
                            st.session_state[confirm_key_task] = False
                            st.rerun()
                        else:
                            st.session_state[confirm_key_task] = True
                            st.warning(f"再次点击确认删除任务流程 '{selected_hist_task_name}'。")