# table_labeling_tool/app.py
import streamlit as st

# 必须是第一个Streamlit命令
st.set_page_config(
    page_title="表格数据AI打标工具",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="expanded"
)

from ui.sidebar import display_sidebar
from ui.tabs import data_load_tab, add_task_tab, prompt_gen_tab, run_labeling_tab, download_tab
from ui.ui_utils import init_session_state # 确保init_session_state被导入
from core.config_manager import CONFIG_DIR # 确保配置目录检查在早期

def main():
    """主函数，运行Streamlit应用。"""
    st.title("🏷️ 表格数据AI打标与处理工具")
    st.caption("通过AI自动为表格数据生成新列、提取信息、进行分类等。")

    # 初始化会话状态变量 (应尽早调用)
    init_session_state() #

    # 显示侧边栏配置
    display_sidebar() #

    # --- 新增：在标签页上方添加引导说明 ---
    st.markdown("---") # 添加一条分割线，视觉上突出下面的导航区
    st.markdown("#### 导航至不同操作步骤：") # 使用稍大一点的 Markdown 标题
    st.write("👇 **请点击下方的标签页，按顺序完成各项操作。每个标签页代表一个主要步骤。**")
    # st.caption("提示：点击下方对应的标签页可以在不同处理步骤之间切换。") # 另一种提示方式

    # 定义主内容标签页
    tab_titles = [
        "📁 1. 数据加载与编辑",
        "🎯 2. 定义打标任务",
        "📝 3. 生成AI指令 (Prompt)",
        "🏷️ 4. 执行AI标注",
        "📥 5. 下载与总结"
    ]
    tab1, tab2, tab3, tab4, tab5 = st.tabs(tab_titles) #

    with tab1:
        data_load_tab.display_data_load_tab() #
    with tab2:
        add_task_tab.display_add_task_tab() #
    with tab3:
        prompt_gen_tab.display_prompt_generation_tab() #
    with tab4:
        run_labeling_tab.display_run_labeling_tab() #
    with tab5:
        download_tab.display_download_tab() #

if __name__ == "__main__":
    CONFIG_DIR.mkdir(exist_ok=True) # 再次确保配置目录存在
    main()