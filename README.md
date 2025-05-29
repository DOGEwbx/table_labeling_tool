# 表格数据AI打标与处理工具 (Table Data AI Labeling and Processing Tool)

体验链接: https://tablelabelingtool-bingxuan.streamlit.app/

🏷️ 本工具是一个基于Streamlit的Web应用程序，旨在帮助用户通过大型语言模型（LLM，如GPT系列）对表格数据（如CSV, Excel文件）进行自动化的数据标注、信息提取、分类等任务。

## ✨ 主要功能

* **数据加载与编辑**:
    * 支持多种文件格式导入 (CSV, Excel, Parquet, JSONL)。
    * 数据预览和实时编辑。
    * 行/列的搜索、删除操作。
    * 编辑后数据下载。
* **灵活的任务定义**:
    * 用户可以定义一个或多个打标任务。
    * 为每个任务指定输入列、期望的输出列名。
    * 详细描述打标需求和指令。
    * 可选择是否要求AI提供判断理由（会自动生成理由列）。
* **智能Prompt工程**:
    * **AI辅助生成Prompt模板**: 根据用户定义的打标任务，请求AI（如GPT）生成一个结构化的JSON Prompt模板。
    * **模板编辑与最终Prompt预览**: 用户可以编辑AI生成的JSON模板，并实时预览根据该模板构建的、将用于处理每一行数据的最终用户Prompt。
    * **占位符校验**: 对比最终用户Prompt中的占位符（如`{列名}`）与已加载数据的列名，确保匹配。
* **可配置的AI调用**:
    * 支持配置API Key, Base URL (兼容OpenAI及其他兼容API)。
    * 可调整模型名称、Temperature、Max Tokens等参数。
    * 支持API配置的保存与加载。
* **高效的标注执行**:
    * **试标注**: 对少量数据（例如前5行）进行快速测试，验证Prompt效果和API连通性。
    * **全量标注**: 使用多线程并发处理整个数据集，提高标注效率。
    * 可配置并发线程数、失败重试次数、请求间隔。
    * 实时显示标注进度、成功/失败统计和预计剩余时间。
    * 查看失败行详情。
* **任务流程管理**:
    * 保存和加载完整的任务流程配置，包括API设置、打标任务定义、生成的Prompt模板以及关联的数据文件路径。
* **结果下载**:
    * 将AI标注的结果（包括理由列）合并回原始数据。
    * 支持多种格式下载 (Excel, CSV, Parquet, JSONL)。

## 🛠️ 项目结构

本工具代码结构清晰，分为核心逻辑 (`core/`) 和用户界面 (`ui/`) 两大部分，便于维护和扩展。

```
table_labeling_tool/
├── app.py                     # 主 Streamlit 应用入口
├── core/                      # 核心逻辑模块
│   ├── config_manager.py      # 配置管理
│   ├── data_handler.py        # 数据处理
│   ├── openai_caller.py       # OpenAI API 调用
│   └── utils.py               # 通用工具函数
├── ui/                        # Streamlit UI 组件
│   ├── sidebar.py             # 侧边栏UI
│   ├── tabs/                  # 各标签页UI
│   └── ui_utils.py            # UI工具函数
├── .streamlit_labeling_configs/ # 用户配置存储目录 (自动创建)
└── requirements.txt           # Python依赖
```

## 🚀 快速开始

### 先决条件

* Python 3.8 或更高版本
* pip (Python包安装器)

### 安装与设置

1.  **获取代码**:
    将项目文件下载或克隆到本地。

2.  **创建虚拟环境 (推荐)**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate   # Windows
    ```

3.  **安装依赖**:
    在项目根目录下 (即包含 `requirements.txt` 的 `table_labeling_tool` 文件夹) 运行：
    ```bash
    pip install -r requirements.txt
    ```

### 配置

1.  **API密钥**:
    首次运行应用后，在左侧边栏的 "API 调用配置" 部分填入您的OpenAI API密钥和Base URL（如果不是使用官方OpenAI服务）。
    * **API Key**: 您的LLM服务提供商的API密钥。
    * **Base URL**: API的端点地址。
    * **模型名称**: 您希望使用的模型，例如 `gpt-4o`, `gpt-3.5-turbo`。
    * 其他参数如 Temperature, Max Tokens 可按需调整。
2.  **保存配置**:
    您可以为当前API配置命名并保存，方便后续快速加载。API配置和任务流程配置默认保存在项目根目录下的 `.streamlit_labeling_configs` 文件夹中。

### 运行应用

在项目根目录下 (`table_labeling_tool/`) 运行:
```bash
streamlit run app.py
```
应用将在您的默认浏览器中打开。

## 📖 使用指南

1.  **📁 1. 数据加载与编辑**:
    * 上传您的表格数据文件。
    * 预览数据，可进行搜索、直接编辑单元格、删除列等操作。
    * 可下载编辑后的数据。

2.  **🎯 2. 定义打标任务**:
    * 点击 "添加新的打标任务"。
    * 选择将作为AI分析依据的 "输入列"。
    * 为AI生成的结果指定 "新输出列的名称"。
    * 在 "详细打标需求/指令" 中清晰描述您的要求，例如：“根据'用户评论'列，判断评论的情感是积极、消极还是中性，并在新列'情感分析结果'中输出判断。”
    * 如果需要AI解释其判断过程，勾选 "要求AI提供判断理由"。
    * 添加多个任务以满足复杂的数据处理需求。

3.  **📝 3. 生成AI指令 (Prompt)**:
    * 点击 "向AI请求生成Prompt模板"。系统会根据您在步骤2中定义的任务，请求您配置的LLM生成一个JSON格式的指令模板。
    * 您可以在 "AI生成的JSON Prompt模板" 编辑框中修改此模板。
    * "最终用户Prompt预览" 会显示根据模板和任务定义整合后的、将实际发送给LLM进行每行数据处理的指令。请检查此处的占位符 `{列名}` 是否与您的数据列名匹配。

4.  **🏷️ 4. 执行AI标注**:
    * **试标注**: 选择少量数据行进行测试，以快速验证Prompt效果和API配置。结果会直接显示。
    * **全量标注**: 对所有数据行执行标注。此过程可能耗时较长，请耐心等待。界面会显示进度条、预计剩余时间及统计信息。
    * 如果出现标注失败的情况，可以展开错误详情查看。

5.  **📥 5. 下载与总结**:
    * 预览标注后的数据（通常显示最后几行）。
    * 选择合适的格式（XLSX, CSV, Parquet, JSONL）下载包含AI标注结果的完整数据表。
    * 查看最终的标注统计总结。

## 📦 打包为可执行文件 (进阶)

如果您希望将此应用分发给没有Python环境的用户，可以使用PyInstaller进行打包。这通常是一个复杂的过程，需要调试和处理依赖。

可以参考[知乎回答](https://zhuanlan.zhihu.com/p/695939376)的教程

打包好的exe请点击[夸克网盘链接](https://pan.quark.cn/s/530f167e617b)


---

Happy Labeling! 🎉