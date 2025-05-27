# table_labeling_tool/core/data_handler.py
import pandas as pd
import json
import io
from pathlib import Path
from typing import Optional
import streamlit as st
import uuid # For generating unique filenames

# --- 新增：定义上传数据持久化的目录 ---
# 这会创建在 .streamlit_labeling_configs 文件夹内部
PERSISTED_DATA_DIR = Path(".streamlit_labeling_configs") / "persisted_user_data"
PERSISTED_DATA_DIR.mkdir(parents=True, exist_ok=True) # 启动时确保目录存在

@st.cache_data
def load_data_from_uploaded_file(file_content: bytes, file_name: str) -> Optional[pd.DataFrame]:
    # ... (此函数不变) ...
    try:
        file_ext = file_name.split('.')[-1].lower()
        df = None
        if file_ext == 'csv':
            for encoding in ['utf-8', 'gbk', 'gb2312', 'latin1']: 
                try:
                    df = pd.read_csv(io.StringIO(file_content.decode(encoding)))
                    break
                except UnicodeDecodeError:
                    continue
            if df is None: 
                df = pd.read_csv(io.BytesIO(file_content))
        elif file_ext in ['xlsx', 'xls']:
            df = pd.read_excel(io.BytesIO(file_content))
        elif file_ext == 'parquet':
            df = pd.read_parquet(io.BytesIO(file_content))
        elif file_ext == 'jsonl':
            lines = file_content.decode('utf-8').strip().split('\n')
            data = [json.loads(line) for line in lines if line.strip()]
            df = pd.DataFrame(data)
        else:
            st.error(f"不支持的文件格式: {file_ext}")
            return None
        return df
    except Exception as e:
        st.error(f"加载数据文件 '{file_name}' 失败: {str(e)}")
        return None

@st.cache_data
def load_data_from_path(file_path: str) -> Optional[pd.DataFrame]:
    # ... (此函数不变) ...
    try:
        path = Path(file_path)
        if not path.exists():
            st.error(f"文件路径不存在: {file_path}")
            return None

        file_ext = path.suffix.lower().lstrip('.')
        df = None
        if file_ext == 'csv':
            for encoding in ['utf-8', 'gbk', 'gb2312', 'latin1']:
                try:
                    df = pd.read_csv(path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if df is None: 
                 df = pd.read_csv(path)
        elif file_ext in ['xlsx', 'xls']:
            df = pd.read_excel(path)
        elif file_ext == 'parquet':
            df = pd.read_parquet(path)
        elif file_ext == 'jsonl':
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            data = [json.loads(line.strip()) for line in lines if line.strip()]
            df = pd.DataFrame(data)
        else:
            st.error(f"不支持的文件格式: {file_ext} (路径: {file_path})")
            return None
        return df
    except Exception as e:
        st.error(f"从路径 '{file_path}' 加载数据失败: {str(e)}")
        return None

def save_dataframe_to_bytes(df: pd.DataFrame, format_type: str) -> bytes:
    # ... (此函数不变) ...
    output = io.BytesIO()
    try:
        if format_type == 'csv':
            csv_string = df.to_csv(index=False, encoding='utf-8-sig')
            output.write(csv_string.encode('utf-8-sig'))
        elif format_type == 'xlsx':
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
        elif format_type == 'parquet':
            df.to_parquet(output, index=False)
        elif format_type == 'jsonl':
            jsonl_string = '\n'.join([row.to_json(force_ascii=False) for _, row in df.iterrows()])
            output.write(jsonl_string.encode('utf-8'))
        else:
            st.error(f"不支持的保存格式: {format_type}")
            return b""
        return output.getvalue()
    except Exception as e:
        st.error(f"保存DataFrame到 {format_type} 格式时出错: {str(e)}")
        return b""

# --- 新增函数：持久化DataFrame到服务器 ---
def persist_dataframe_on_server(df: pd.DataFrame, original_filename: str) -> Optional[str]:
    """
    将给定的DataFrame保存到服务器上的PERSISTED_DATA_DIR目录。
    返回保存文件的绝对路径，如果失败则返回None。
    """
    if df is None:
        st.error("无法持久化空的DataFrame。")
        return None
    if not original_filename: # 需要原始文件名来确定扩展名和基本名
        original_filename = f"persisted_data_{uuid.uuid4().hex[:8]}.parquet" # 默认文件名
        st.warning(f"未提供原始文件名，将使用默认名称: {original_filename}")


    try:
        # 从原始文件名中提取基本名称和扩展名
        p_original_filename = Path(original_filename)
        base_name = p_original_filename.stem
        original_ext = p_original_filename.suffix.lower()

        # 确定保存格式，优先使用Parquet以保证数据类型和效率
        # 如果原始扩展名是已知的表格格式，可以考虑保留，否则用Parquet
        if original_ext in ['.csv', '.xlsx', '.parquet']:
            save_ext = original_ext
        else:
            save_ext = '.parquet' # 默认保存为Parquet

        # 创建一个唯一的文件名以避免冲突
        unique_id = uuid.uuid4().hex[:8]
        new_filename = f"{base_name}_{unique_id}{save_ext}"
        save_path = PERSISTED_DATA_DIR / new_filename

        # 根据确定的扩展名保存文件
        if save_ext == '.parquet':
            df.to_parquet(save_path, index=False)
        elif save_ext == '.csv':
            df.to_csv(save_path, index=False, encoding='utf-8-sig')
        elif save_ext == '.xlsx':
            with pd.ExcelWriter(save_path, engine='openpyxl') as writer: # type: ignore
                df.to_excel(writer, index=False)
        
        st.info(f"数据副本已保存到服务器路径: {save_path.resolve()}")
        return str(save_path.resolve()) # 返回新保存文件的绝对路径

    except Exception as e:
        st.error(f"持久化数据 '{original_filename}' 到服务器时失败: {e}")
        return None