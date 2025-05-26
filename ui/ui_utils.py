# table_labeling_tool/ui/ui_utils.py
import streamlit as st
from core.config_manager import load_api_configs # 避免循环导入，仅用于初始化

def refresh_data_editor():
    """增加数据编辑器的key以强制刷新。"""
    st.session_state.data_editor_key = st.session_state.get('data_editor_key', 0) + 1

def refresh_task_form():
    """增加任务表单的key以强制刷新并清空输入。"""
    st.session_state.task_form_key = st.session_state.get('task_form_key', 0) + 1

def init_session_state():
    """初始化会话状态变量（如果它们不存在）。"""

    # --- 核心数据和配置 ---
    if 'df' not in st.session_state:
        st.session_state.df = None
    if 'current_data_path' not in st.session_state: # 存储从历史任务加载的数据路径
        st.session_state.current_data_path = None
    # 用于从上传文件名生成下载文件名
    if '_uploaded_file_name_for_download_' not in st.session_state:
        st.session_state._uploaded_file_name_for_download_ = None


    # --- API配置 ---
    if 'api_config' not in st.session_state:
        api_configs_on_disk = load_api_configs()
        # 尝试加载名为 'default' 的API配置，否则使用硬编码的默认值
        if api_configs_on_disk and 'default' in api_configs_on_disk:
            st.session_state.api_config = api_configs_on_disk['default'].copy()
        else: # 后备默认值
            st.session_state.api_config = {
                'api_key': '',
                'base_url': '[https://api.openai.com/v1](https://api.openai.com/v1)',
                'model_name': 'gpt-3.5-turbo',
                'temperature': 0.05,
                'max_tokens': 1500
            }

    # --- 任务定义 & Prompt生成 ---
    if 'labeling_tasks' not in st.session_state: # 打标任务定义列表
        st.session_state.labeling_tasks = []
    if 'generated_prompt_template' not in st.session_state: # AI生成的JSON模板 (原 generated_prompt)
        st.session_state.generated_prompt_template = ""
    if 'final_user_prompt' not in st.session_state: # 发送给LLM处理每行数据的Prompt (原 processed_prompt)
        st.session_state.final_user_prompt = ""

    # --- 标注过程控制 & 结果 ---
    if 'labeling_progress' not in st.session_state:
        st.session_state.labeling_progress = {
            'is_running': False,    # 是否正在运行
            'completed': 0,         # 已完成数量
            'total': 0,             # 总数量
            'results': {},          # 存储 {行索引: {success: bool, result: dict/None, error: str/None}}
            'is_test_run': False    # 标记是否为测试运行
        }

    # --- 执行参数 ---
    if 'concurrent_workers' not in st.session_state:
        st.session_state.concurrent_workers = 4
    if 'retry_attempts' not in st.session_state:
        st.session_state.retry_attempts = 3
    if 'request_delay' not in st.session_state:
        st.session_state.request_delay = 0.2 # 秒

    # --- UI元素刷新用的Key ---
    if 'data_editor_key' not in st.session_state:
        st.session_state.data_editor_key = 0
    if 'task_form_key' not in st.session_state: # 用于“添加任务”表单
        st.session_state.task_form_key = 0