# table_labeling_tool/core/utils.py
import re
import json
from typing import List, Dict, Any, Set, Optional
import streamlit as st # 用于 st.error, st.session_state

# def extract_placeholder_columns_from_final_prompt(prompt_text: str) -> List[str]:
#     """
#     从最终处理后的Prompt字符串中提取占位符列名。
#     占位符应为 {column_name} 格式。
#     """
#     pattern = r'\{([^{}]+)\}' # 匹配 {} 中间不含 {} 的内容
#     matches = re.findall(pattern, prompt_text)
#     cleaned_matches = []
#     for match in matches:
#         cleaned = match.strip()
#         if cleaned and cleaned not in cleaned_matches:
#             cleaned_matches.append(cleaned)
#     return cleaned_matches

def extract_placeholder_columns_from_final_prompt(prompt_text: str) -> List[str]:
    """
    从最终处理后的Prompt字符串中提取占位符列名。
    占位符应为 {column_name} 格式. This version captures content within single curly braces.
    """
    # This regex captures any characters between single curly braces.
    # It's suitable because the JSON example in the prompt uses double curly braces {{ and }}.
    pattern = r'\{([^{}\r\n]+)\}' 
    matches = re.findall(pattern, prompt_text)
    
    cleaned_matches = []
    for match in matches:
        cleaned = match.strip()
        if cleaned and cleaned not in cleaned_matches:
            cleaned_matches.append(cleaned)
    return cleaned_matches

def _build_final_user_prompt_from_template(
    parsed_template_json: Dict[str, Any],
    defined_labeling_tasks: List[Dict[str, Any]]
) -> str:
    """
    辅助函数：根据AI生成的已解析模板和用户定义的打标任务，构建最终面向用户的Prompt。
    此Prompt将用于处理每一行数据。
    """
    all_input_columns: Set[str] = set()
    output_structure_from_tasks: Dict[str, Any] = {}

    # 遍历用户定义的任务，收集输入列并构建输出结构示例
    for task_def in defined_labeling_tasks:
        task_output_col = task_def.get('output_column')
        if not task_output_col:
            continue

        task_input_cols = task_def.get('input_columns', [])
        if isinstance(task_input_cols, (list, set, tuple)):
            for col in task_input_cols:
                all_input_columns.add(str(col))

        if task_def.get('need_reason', False):
            output_structure_from_tasks[task_output_col] = {
                "value": f"针对'{task_output_col}'的标注结果",
                "reason": f"针对'{task_output_col}'的判断理由"
            }
        else:
            # MODIFIED: Ensure value is part of a dictionary even if no reason is needed,
            # to maintain consistency if the LLM expects a certain structure for all outputs.
            # However, the original logic was to directly assign the value.
            # Sticking to original logic for direct value if no reason.
            # Re-evaluating: The original prompt user provided shows structure like:
            # "建议股民购买": {{ "value": ..., "reason": ...}}
            # "涨跌情况": {{ "value": ... }} -> This implies the output JSON from LLM might not always have "reason".
            # The example output_format_section_escaped should reflect the tasks.
            # The provided prompt in the question has "涨跌情况": { "value": "..." }
            # which suggests single value output is also nested under "value" IF output_structure_from_tasks
            # is built this way.
            # The current logic for output_structure_from_tasks seems to build:
            #   output_structure_from_tasks[task_output_col] = {"value": ...} for no_reason
            # This is fine. The key is that `output_format_section_escaped` correctly shows what LLM should return.
            output_structure_from_tasks[task_output_col] = f"针对'{task_output_col}'的标注结果"


    # ---- NEW: Define and store the order of input columns for the prompt ----
    # Sort for consistency, matching how they are listed in the info_section
    ordered_input_cols_for_prompt = sorted(list(all_input_columns))
    # Ensure st.session_state is available and initialized before trying to set an attribute
    if 'st' in globals() and hasattr(st, 'session_state'):
        st.session_state.ordered_input_cols_for_prompt = ordered_input_cols_for_prompt
    # ---- END NEW ----

    # 构建“提供的信息”部分
    info_section = "提供的参考信息：\n"
    if ordered_input_cols_for_prompt: # Use the new ordered list
        for i, col_name in enumerate(ordered_input_cols_for_prompt, 1):
            info_section += f"  {i}. {col_name}: \"{{{col_name}}}\"\n" # 实际数据占位符
    else:
        info_section += "  (无特定输入列在此处列出，请参照下方任务要求中的描述)\n"

    # 从 parsed_template_json 构建“分析任务与要求”部分
    task_descriptions_from_template = []
    if "prompts" in parsed_template_json and isinstance(parsed_template_json["prompts"], list):
        for i, template_task_info in enumerate(parsed_template_json["prompts"], 1):
            if isinstance(template_task_info, dict):
                task_name = template_task_info.get("task", f"未命名任务{i}")
                task_instruction = template_task_info.get("prompt", "无具体指令。")
                task_descriptions_from_template.append(f"  任务 {i} (目标输出: '{task_name}'):\n    {task_instruction}")
            else:
                task_descriptions_from_template.append(f"  任务 {i}: (模板格式错误，无法解析)")
    else:
        if 'st' in globals() and hasattr(st, 'warning'):
            st.warning("Prompt模板JSON中缺少 'prompts' 列表或格式不正确。请检查AI生成的Prompt模板。")
        task_descriptions_from_template.append("  (无法从模板加载任务指令，请检查Prompt模板)")

    # 构建“输出格式”部分，使用从 defined_labeling_tasks 推断的结构
    # Re-adjusting output_structure_from_tasks for the user's example:
    # The example shows "涨跌情况": { "value": ... } even if no reason.
    # Let's ensure output_structure_from_tasks consistently uses a dict with "value".
    output_format_example_for_llm: Dict[str, Any] = {}
    for task_def in defined_labeling_tasks:
        task_output_col = task_def.get('output_column')
        if not task_output_col:
            continue
        if task_def.get('need_reason', False):
            output_format_example_for_llm[task_output_col] = {
                "value": f"针对'{task_output_col}'的标注结果",
                "reason": f"针对'{task_output_col}'的判断理由"
            }
        else:
            output_format_example_for_llm[task_output_col] = {
                "value": f"针对'{task_output_col}'的标注结果"
            }


    output_format_section = json.dumps(output_format_example_for_llm, ensure_ascii=False, indent=2) # Use the adjusted structure
    # 为最终插入行数据的 .format() 转义花括号
    output_format_section_escaped = output_format_section.replace("{", "{{").replace("}", "}}")

    # 组装最终Prompt
    final_prompt = f"""
请仔细分析以下提供的参考信息，并根据这些信息完成下列分析任务。

{info_section}
分析任务与要求：
{chr(10).join(task_descriptions_from_template)}

请严格按照以下JSON格式返回你的分析结果，不要添加任何额外的解释或说明文字。

{output_format_section_escaped}

请确保返回的是一个结构完全符合上述描述的、合法的 JSON 对象。
如果某项信息在输入中完全缺失或无法根据提供的信息判断，请在对应的字段中明确说明（例如，返回 "无法判断" 或 "信息缺失"）。
"""

    return final_prompt.strip()

def parse_ai_generated_prompt_template(
    ai_generated_json_template_str: str,
    defined_labeling_tasks: List[Dict[str, Any]]
) -> str:
    """
    解析AI生成的JSON Prompt模板，并用它构建最终面向用户的Prompt。
    返回:
    最终格式化好的Prompt字符串（准备填充行数据），或在解析/处理失败时返回原始模板字符串。
    """
    stripped_template_str = ai_generated_json_template_str.strip()
    parsed_json_data: Optional[Dict[str, Any]] = None


    # 尝试1: 直接解析 (如果看起来像JSON对象)
    if stripped_template_str.startswith('{') and stripped_template_str.endswith('}'):
        try:
            parsed_json_data = json.loads(stripped_template_str)
        except json.JSONDecodeError:
            pass 
        except Exception as e:
            if 'st' in globals() and hasattr(st, 'error'):
                st.error(f"直接解析AI生成的JSON模板时发生意外错误: {str(e)}")
            return ai_generated_json_template_str

    # 尝试2: 如果直接解析失败，尝试从markdown代码块中提取JSON
    if parsed_json_data is None:
        match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", stripped_template_str, re.DOTALL)
        if not match:
            match = re.search(r"```\s*(\{[\s\S]*?\})\s*```", stripped_template_str, re.DOTALL)
        
        if match:
            json_substring = match.group(1)
            try:
                parsed_json_data = json.loads(json_substring)
            except json.JSONDecodeError as e_re:
                if 'st' in globals() and hasattr(st, 'error'):
                    st.error(f"从提取的JSON块解析失败: {e_re}。\n提取的块 (前500字符): {json_substring[:500]}...\n原始输出 (前500字符):\n{ai_generated_json_template_str[:500]}...")
                return ai_generated_json_template_str
            except Exception as e_fatal_re:
                if 'st' in globals() and hasattr(st, 'error'):
                    st.error(f"解析提取的JSON块时发生意外错误: {e_fatal_re}")
                return ai_generated_json_template_str
        else: 
            start_index = stripped_template_str.find('{')
            end_index = stripped_template_str.rfind('}')
            if start_index != -1 and end_index != -1 and start_index < end_index:
                json_substring = stripped_template_str[start_index : end_index + 1]
                try:
                    parsed_json_data = json.loads(json_substring)
                except json.JSONDecodeError as e_sub:
                    if 'st' in globals() and hasattr(st, 'error'):
                        st.error(f"无法从AI生成的文本中解析JSON模板。尝试提取的子字符串解析失败: {e_sub}。\n请检查AI的输出是否为合法的JSON。原始输出 (前500字符):\n{ai_generated_json_template_str[:500]}...")
                    return ai_generated_json_template_str
                except Exception as e_fatal_sub:
                    if 'st' in globals() and hasattr(st, 'error'):
                        st.error(f"提取并解析JSON子字符串时发生意外错误: {e_fatal_sub}")
                    return ai_generated_json_template_str
            else: 
                if 'st' in globals() and hasattr(st, 'error'):
                    st.error(f"AI生成的文本不包含有效的JSON结构。请检查AI的输出。原始输出 (前500字符):\n{ai_generated_json_template_str[:500]}...")
                return ai_generated_json_template_str

    if parsed_json_data is not None:
        try:
            if not isinstance(parsed_json_data, dict):
                if 'st' in globals() and hasattr(st, 'error'):
                    st.error(f"解析得到的JSON模板不是一个对象 (字典): 类型为 {type(parsed_json_data)}。\n内容 (前200字符): {str(parsed_json_data)[:200]}...")
                return ai_generated_json_template_str

            if "prompts" not in parsed_json_data or not isinstance(parsed_json_data["prompts"], list):
                if 'st' in globals() and hasattr(st, 'error'):
                    st.error("AI生成的JSON模板缺少 'prompts' 键，或其值不是一个列表。请确保AI遵循指定的输出格式。")
                    if hasattr(st, 'json'): st.json(parsed_json_data) 
                return ai_generated_json_template_str

            for item in parsed_json_data["prompts"]:
                if not isinstance(item, dict) or "task" not in item or "prompt" not in item:
                    if 'st' in globals() and hasattr(st, 'error'):
                        st.error("AI生成的JSON模板中 'prompts' 列表内的元素格式不正确。每个元素应为包含 'task' 和 'prompt'键的字典。")
                        if hasattr(st, 'json'): st.json(parsed_json_data)
                    return ai_generated_json_template_str
            
            return _build_final_user_prompt_from_template(parsed_json_data, defined_labeling_tasks)

        except Exception as e:
            if 'st' in globals() and hasattr(st, 'error'):
                st.error(f"构建最终用户prompt时出错: {str(e)}。\n解析到的JSON模板 (前500字符): {str(parsed_json_data)[:500]}")
            return ai_generated_json_template_str

    if 'st' in globals() and hasattr(st, 'error'):
        st.error("未能从AI的输出中成功解析JSON模板。")
    return ai_generated_json_template_str