# table_labeling_tool/core/openai_caller.py
import time
import json
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd # 用于 pd.isna
from openai import OpenAI, APIConnectionError, RateLimitError, AuthenticationError, NotFoundError, BadRequestError, APIError
import streamlit as st # 用于 st.error
import re # For re.escape and re.sub

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
    except PermissionError as e: 
        st.error(f"OpenAI API权限错误: {e}。您可能没有权限访问此模型或资源。")
        raise
    except RateLimitError as e:
        st.error(f"OpenAI API速率限制已超出: {e}。请稍后重试或检查您的用量限制。")
        raise
    except APIConnectionError as e:
        st.error(f"OpenAI API连接错误: {e}。无法连接到OpenAI，请检查网络和API状态。")
        raise
    except NotFoundError as e: 
        st.error(f"OpenAI API未找到错误: {e}。通常表示指定的模型不正确或不可用。")
        raise
    except BadRequestError as e: 
        st.error(f"OpenAI API错误请求: {e}。可能是请求格式无效、Prompt问题（如过长）或其他参数错误。")
        raise
    except APIError as e: 
        st.error(f"OpenAI API发生错误: {e}。OpenAI API发生意外错误。")
        raise
    except Exception as e: 
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
        input_cols_str = "、".join(task.get('input_columns', []))
        output_col = task.get('output_column', 'UnknownOutput')
        requirement = task.get('requirement', '未指定需求。')
        need_reason = task.get('need_reason', False)

        task_desc = f"""
任务{i}：
- 输入列：{input_cols_str}
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
        return ""


def process_single_row(
    row_data_tuple: Tuple[int, Dict[str, Any]],
    final_prompt_template: str, # This is the prompt with {col_name} style placeholders
    api_config: Dict[str, Any],
    ordered_keys_for_prompt: List[str], # New argument for ordered column names
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
    filled_prompt: Optional[str] = None 
    cleaned_response: Optional[str] = None 

    try:
        # ---- MODIFIED: Prepare for indexed formatting ----
        if not ordered_keys_for_prompt:
            # This case should ideally be prevented by checks in run_labeling_tab.py
            error_msg = "处理失败: Prompt格式化所需的有序输入列列表 (ordered_keys_for_prompt) 为空。"
            return row_idx, {
                "success": False, "result": None, "error": error_msg,
                "prompt_sent": None, "raw_response": None
            }

        # Prepare ordered values from row_dict, ensuring they are strings
        ordered_string_values = []
        for col_key in ordered_keys_for_prompt:
            value = row_dict.get(col_key) # Get raw value from original row_dict
            if pd.isna(value) or value is None:
                ordered_string_values.append("")
            else:
                ordered_string_values.append(str(value))

        # Transform the final_prompt_template to use indexed placeholders {0}, {1}, etc.
        indexed_template_str = final_prompt_template
        for i, col_name_key in enumerate(ordered_keys_for_prompt):
            # Escape the column name in case it contains regex special characters
            escaped_col_name = re.escape(col_name_key)
            # Replace "{col_name}" with "{i}"
            indexed_template_str = re.sub(r'\{' + escaped_col_name + r'\}', f'{{{i}}}', indexed_template_str)
        
        filled_prompt = indexed_template_str.format(*ordered_string_values)
        # ---- END MODIFIED ----

        client = OpenAI(
            api_key=api_config.get('api_key'),
            base_url=api_config.get('base_url')
        )
        messages = [
            {"role": "system", "content": "你是一个专业的数据标注助手。请严格按照JSON格式返回结果。不要添加任何解释性文字或markdown代码块标记。"},
            {"role": "user", "content": filled_prompt} # Use the new filled_prompt
        ]

        for attempt in range(retry_attempts + 1): # +1 to make retry_attempts actually be the number of retries
            try:
                api_response_content = call_openai_api(client, messages, api_config)
                cleaned_response = api_response_content.strip() 

                temp_cleaned_response = cleaned_response 
                if temp_cleaned_response.startswith("```json"):
                    temp_cleaned_response = temp_cleaned_response[7:]
                elif temp_cleaned_response.startswith("```"):
                     temp_cleaned_response = temp_cleaned_response[3:]
                if temp_cleaned_response.endswith("```"):
                    temp_cleaned_response = temp_cleaned_response[:-3]
                
                parsed_result = json.loads(temp_cleaned_response.strip())
                if request_delay > 0: time.sleep(request_delay) # Apply delay only on success before next call
                return row_idx, {
                    "success": True, "result": parsed_result, "error": None,
                    "prompt_sent": filled_prompt, "raw_response": cleaned_response 
                }

            except json.JSONDecodeError as je:
                if attempt == retry_attempts: # Last attempt failed
                    error_msg = f"JSON解析失败 ({retry_attempts + 1}次尝试后): {je}。"
                    return row_idx, {
                        "success": False, "result": None, "error": error_msg,
                        "prompt_sent": filled_prompt, "raw_response": cleaned_response
                    }
                time.sleep(1 + attempt * 0.5) # Wait before retrying

            except Exception as e: 
                if attempt == retry_attempts: # Last attempt failed
                    error_msg = f"API调用或处理失败 ({retry_attempts + 1}次尝试后): {e}"
                    return row_idx, {
                        "success": False, "result": None, "error": error_msg,
                        "prompt_sent": filled_prompt, "raw_response": cleaned_response 
                    }
                time.sleep(1 + attempt * 0.5) # Wait before retrying
        
        # Fallback if loop finishes without returning (should not happen with retry_attempts + 1 logic)
        return row_idx, {
            "success": False, "result": None, "error": f"已耗尽 {retry_attempts + 1} 次重试但未成功。",
            "prompt_sent": filled_prompt, "raw_response": cleaned_response
        }

    except IndexError as ie: # New potential error with .format(*args)
        error_msg = f"处理失败: Prompt格式化索引错误 - {ie}。可能是Prompt中的索引超出了提供的数据值范围。"
        return row_idx, {
            "success": False, "result": None, "error": error_msg,
            "prompt_sent": filled_prompt, # filled_prompt might be partially formed or the template
            "raw_response": None
        }
    except KeyError as ke: 
        error_msg = f"处理失败: Prompt格式化错误 - 键 '{ke}' 缺失 (这通常不应发生在使用有序键之后)。请检查ordered_keys_for_prompt。"
        return row_idx, {
            "success": False, "result": None, "error": error_msg,
            "prompt_sent": None, "raw_response": None
        }
    except Exception as e:
        error_msg = f"处理失败 (未知错误): {e}"
        return row_idx, {
            "success": False, "result": None, "error": error_msg,
            "prompt_sent": filled_prompt, 
            "raw_response": None
        }