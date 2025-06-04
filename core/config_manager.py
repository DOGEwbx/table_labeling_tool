# table_labeling_tool/core/config_manager.py
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import streamlit as st # 用于 st.session_state 和 st.error

# Configuration directory and file paths
CONFIG_DIR = Path(".streamlit_labeling_configs")
API_CONFIG_FILE = CONFIG_DIR / "api_configs.json"
TASK_CONFIG_FILE = CONFIG_DIR / "task_configs.json"

# Create config directory if it doesn't exist
CONFIG_DIR.mkdir(exist_ok=True)

def load_api_configs() -> Dict[str, Any]:
    """加载API配置"""
    if API_CONFIG_FILE.exists():
        try:
            with open(API_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            st.error(f"解析API配置文件失败: {API_CONFIG_FILE}。将返回空配置。")
            return {}
        except Exception as e:
            st.error(f"加载API配置时发生未知错误: {e}。将返回空配置。")
            return {}
    return {}

def save_api_configs(configs: Dict[str, Any]):
    """保存API配置"""
    try:
        with open(API_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(configs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"保存API配置失败: {e}")

def load_task_configs() -> Dict[str, Any]:
    """加载任务配置"""
    if TASK_CONFIG_FILE.exists():
        try:
            with open(TASK_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            st.error(f"解析任务配置文件失败: {TASK_CONFIG_FILE}。将返回空配置。")
            return {}
        except Exception as e:
            st.error(f"加载任务配置时发生未知错误: {e}。将返回空配置。")
            return {}
    return {}

def save_task_configs(configs: Dict[str, Any]):
    """保存任务配置"""
    try:
        with open(TASK_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(configs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"保存任务配置失败: {e}")

def save_current_task_config(name: str, data_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    保存当前任务配置 (从 st.session_state 获取数据)。
    """
    task_configs = load_task_configs()

    api_config = st.session_state.get('api_config', {})
    labeling_tasks = st.session_state.get('labeling_tasks', [])
    generated_prompt_template = st.session_state.get('generated_prompt_template', "")
    final_user_prompt = st.session_state.get('final_user_prompt', "")
    concurrent_workers = st.session_state.get('concurrent_workers', 4)
    retry_attempts = st.session_state.get('retry_attempts', 3)
    request_delay = st.session_state.get('request_delay', 0.2)
    ordered_input_cols = st.session_state.get('ordered_input_cols_for_prompt', [])

    config = {
        'name': name,
        'created_time': datetime.now().isoformat(),
        'api_config': api_config.copy() if isinstance(api_config, dict) else {},
        'labeling_tasks': labeling_tasks.copy() if isinstance(labeling_tasks, list) else [],
        'generated_prompt_template': generated_prompt_template,
        'final_user_prompt': final_user_prompt,
        'data_path': data_path,
        'concurrent_workers': concurrent_workers,
        'retry_attempts': retry_attempts,
        'request_delay': request_delay,
        'ordered_input_cols_for_prompt': ordered_input_cols 
    }

    task_configs[name] = config
    save_task_configs(task_configs)
    return config

def load_task_config(name: str) -> Optional[Dict[str, Any]]:
    """加载指定的任务配置"""
    task_configs = load_task_configs()
    return task_configs.get(name)

def check_data_file_exists(file_path: Optional[str]) -> bool:
    """检查数据文件是否存在"""
    if not file_path:
        return False
    return Path(file_path).exists()