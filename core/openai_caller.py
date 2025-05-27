# table_labeling_tool/core/openai_caller.py
import time
import json
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd # 用于 pd.isna
from openai import OpenAI, APIConnectionError, RateLimitError, AuthenticationError, NotFoundError, BadRequestError, APIError
import streamlit as st # 用于 st.error

def call_openai_api(client: OpenAI, messages: List[Dict[str, str]], config: Dict[str, Any]) -> str:
    """
    调用OpenAI Chat Completion API，并处理常见API错误。
    """
    try:
        response = client.chat.completions.create(
            model=config.get('model_name', 'gpt-3.5-turbo'),
            messages=messages,
            temperature=config.get('temperature', 0.05),
            max_tokens=config.get('max_tokens', 1500),
            stream=False,
        )
        return response.choices[0].message.content
    except AuthenticationError as e:
        st.error(f"OpenAI API认证失败: {e}。请检查您的API密钥和组织设置。")
        raise
    except PermissionError as e: # 通常映射到403 Forbidden
        st.error(f"OpenAI API权限错误: {e}。您可能没有权限访问此模型或资源。")
        raise
    except RateLimitError as e:
        st.error(f"OpenAI API速率限制已超出: {e}。请稍后重试或检查您的用量限制。")
        raise
    except APIConnectionError as e:
        st.error(f"OpenAI API连接错误: {e}。无法连接到OpenAI，请检查网络和API状态。")
        raise
    except NotFoundError as e: # 通常是模型名称无效
        st.error(f"OpenAI API未找到错误: {e}。通常表示指定的模型不正确或不可用。")
        raise
    except BadRequestError as e: # 通常是Prompt问题或超出上下文长度
        st.error(f"OpenAI API错误请求: {e}。可能是请求格式无效、Prompt问题（如过长）或其他参数错误。")
        raise
    except APIError as e: # OpenAI API的通用错误
        st.error(f"OpenAI API发生错误: {e}。OpenAI API发生意外错误。")
        raise
    except Exception as e: # 其他意外错误
        st.error(f"OpenAI API调用期间发生意外错误: {e}")
        raise


def generate_labeling_prompt_template(tasks: List[Dict[str, Any]], api_config: Dict[str, Any]) -> str:
    """
    生成一个Prompt模板，供AI用于创建实际的数据标注Prompt。
    """
    if not tasks:
        return ""

    task_descriptions = []
    for i, task in enumerate(tasks, 1):
        input_cols = "、".join(task.get('input_columns', []))
        output_col = task.get('output_column', 'UnknownOutput')
        requirement = task.get('requirement', '未指定需求。')
        need_reason = task.get('need_reason', False)

        task_desc = f"""
任务{i}：
- 输入列：{input_cols}
- 输出列：{output_col}
- 需求：{requirement}
- 是否需要理由：{'是' if need_reason else '否'}"""
        task_descriptions.append(task_desc)

    prompt_generation_request = f"""
你是一个专业的数据标注prompt生成助手。请根据以下打标任务需求，生成一个用于数据标注的prompt模板。

打标任务：
{''.join(task_descriptions)}

要求：
1. 生成的prompt应该使用JSON格式输出，方便程序解析。
2. 输出的JSON结构应该包含所有需要的输出列。
3. 如果需要输出理由，请在JSON中包含相应的理由字段。
4. prompt应该清晰、具体，能够指导AI准确完成标注任务。
5. 输出的json应该只有一个key 'prompts', 其值为一个list of dict，每个dict代表一个任务prompt，结构为
   {{
     "task": "....", // 任务名称, 对应打标任务中的输出列名
     "prompt": "..."  // 针对该任务的具体指令
   }},
6. 输入信息会后续拼接到最终用户prompt中，因此在你生成的模板中不需要体现具体输入信息，
   只需要在 "prompt" 字段的指令中清晰说明如何使用即将提供的数据字段即可。

请直接输出可用的JSON格式的prompt模板，不要包含其他解释文字、代码块标记或markdown格式。
确保输出的是一个单一的、合法的JSON对象。
例如:
{{
  "prompts": [
    {{
      "task": "输出列A",
      "prompt": "根据输入列X和Y，判断Z，并给出结论。"
    }},
    {{
      "task": "输出列B",
      "prompt": "分析输入列P，提取关键信息Q。"
    }}
  ]
}}
"""
    try:
        client = OpenAI(
            api_key=api_config.get('api_key'),
            base_url=api_config.get('base_url')
        )
        messages = [
            {"role": "system", "content": "你是一个专业的prompt工程师，擅长生成高质量的数据标注prompt的JSON模板。"},
            {"role": "user", "content": prompt_generation_request}
        ]
        generated_template = call_openai_api(client, messages, api_config)
        return generated_template.strip()
    except Exception:
        # 错误已由 call_openai_api 记录
        return ""


def process_single_row(
    row_data_tuple: Tuple[int, Dict[str, Any]],
    final_prompt_template: str,
    api_config: Dict[str, Any],
    retry_attempts: int = 3,
    request_delay: float = 0.2
) -> Tuple[int, Dict[str, Any]]:
    """
    使用OpenAI API处理单行数据。
    返回:
        包含 (行索引, 结果字典) 的元组。
        结果字典包含键 "success" (bool), "result" (解析后的JSON或None),
        "error" (错误信息字符串或None), "prompt_sent" (发送给API的完整Prompt),
        "raw_response" (API原始响应文本，主要用于JSON解析失败时)。
    """
    row_idx, row_dict = row_data_tuple
    filled_prompt: Optional[str] = None # 初始化，确保在所有路径中都可能被赋值或为None
    cleaned_response: Optional[str] = None # 初始化原始响应

    try:
        safe_row_values = {}
        for key, value in row_dict.items():
            if pd.isna(value) or value is None:
                safe_row_values[key] = ""
            else:
                safe_row_values[key] = str(value)

        filled_prompt = final_prompt_template.format(**safe_row_values) # 在此赋值

        client = OpenAI(
            api_key=api_config.get('api_key'),
            base_url=api_config.get('base_url')
        )
        messages = [
            {"role": "system", "content": "你是一个专业的数据标注助手。请严格按照JSON格式返回结果。不要添加任何解释性文字或markdown代码块标记。"},
            {"role": "user", "content": filled_prompt}
        ]

        for attempt in range(retry_attempts):
            try:
                api_response_content = call_openai_api(client, messages, api_config)
                cleaned_response = api_response_content.strip() # 赋值原始响应

                # 清理响应：移除潜在的markdown代码块
                temp_cleaned_response = cleaned_response 
                if temp_cleaned_response.startswith("```json"):
                    temp_cleaned_response = temp_cleaned_response[7:]
                elif temp_cleaned_response.startswith("```"):
                     temp_cleaned_response = temp_cleaned_response[3:]
                if temp_cleaned_response.endswith("```"):
                    temp_cleaned_response = temp_cleaned_response[:-3]
                
                # 使用处理过的版本进行解析
                parsed_result = json.loads(temp_cleaned_response.strip())
                time.sleep(request_delay)
                return row_idx, {
                    "success": True, "result": parsed_result, "error": None,
                    "prompt_sent": filled_prompt, "raw_response": cleaned_response # 包含原始未经二次处理的cleaned_response
                }

            except json.JSONDecodeError as je:
                if attempt == retry_attempts - 1:
                    error_msg = f"JSON解析失败 ({retry_attempts}次尝试后): {je}。" # 原始响应将在raw_response中提供
                    return row_idx, {
                        "success": False, "result": None, "error": error_msg,
                        "prompt_sent": filled_prompt, "raw_response": cleaned_response
                    }
                time.sleep(1 + attempt * 0.5)

            except Exception as e: # 处理 call_openai_api 中的错误或其他问题
                if attempt == retry_attempts - 1:
                    error_msg = f"API调用或处理失败 ({retry_attempts}次尝试后): {e}"
                    return row_idx, {
                        "success": False, "result": None, "error": error_msg,
                        "prompt_sent": filled_prompt, "raw_response": cleaned_response # 即使API调用失败，也尝试记录原始响应（如果捕获到的话）
                    }
                time.sleep(1 + attempt * 0.5)
        
        # 如果重试次数耗尽仍未成功
        return row_idx, {
            "success": False, "result": None, "error": f"已耗尽 {retry_attempts} 次重试但未成功。",
            "prompt_sent": filled_prompt, "raw_response": cleaned_response
        }

    except KeyError as ke: # .format()时占位符缺失
        error_msg = f"处理失败: Prompt格式化错误 - 键 '{ke}' 缺失。请确保Prompt中的所有占位符与数据列名匹配。"
        return row_idx, {
            "success": False, "result": None, "error": error_msg,
            "prompt_sent": None, "raw_response": None # Prompt构建失败
        }
    except Exception as e:
        error_msg = f"处理失败 (未知错误): {e}"
        return row_idx, {
            "success": False, "result": None, "error": error_msg,
            "prompt_sent": filled_prompt, # filled_prompt可能已生成或为None
            "raw_response": None
        }