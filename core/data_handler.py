# table_labeling_tool/core/data_handler.py
import pandas as pd
import json
import io
from pathlib import Path
from typing import Optional

import streamlit as st # 用于 st.cache_data 和 st.error

@st.cache_data # 使用 Streamlit 的缓存机制
def load_data_from_uploaded_file(file_content: bytes, file_name: str) -> Optional[pd.DataFrame]:
    """从上传文件的内容和名称加载数据。"""
    try:
        file_ext = file_name.split('.')[-1].lower()
        df = None
        if file_ext == 'csv':
            for encoding in ['utf-8', 'gbk', 'gb2312', 'latin1']: # 尝试多种常用编码
                try:
                    df = pd.read_csv(io.StringIO(file_content.decode(encoding)))
                    break
                except UnicodeDecodeError:
                    continue
            if df is None: # 如果所有解码失败，尝试直接用BytesIO
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
    """从指定文件路径加载数据。"""
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
            if df is None: # Fallback
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
    """将DataFrame保存为指定格式的字节流。"""
    output = io.BytesIO()
    try:
        if format_type == 'csv':
            # 使用 utf-8-sig 编码以确保Excel正确识别UTF-8 CSV中的非英文字符
            csv_string = df.to_csv(index=False, encoding='utf-8-sig')
            output.write(csv_string.encode('utf-8-sig'))
        elif format_type == 'xlsx':
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
        elif format_type == 'parquet':
            df.to_parquet(output, index=False)
        elif format_type == 'jsonl':
            # 确保非ASCII字符正确处理
            jsonl_string = '\n'.join([row.to_json(force_ascii=False) for _, row in df.iterrows()])
            output.write(jsonl_string.encode('utf-8'))
        else:
            st.error(f"不支持的保存格式: {format_type}")
            return b""
        return output.getvalue()
    except Exception as e:
        st.error(f"保存DataFrame到 {format_type} 格式时出错: {str(e)}")
        return b""