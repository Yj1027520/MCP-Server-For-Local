## MCP（Model Context Protocol）简介
官方地址：https://github.com/modelcontextprotocol/python-sdk

MCP（Model Context Protocol）是由 Anthropic 开发的一种开源协议，旨在为 AI 模型提供与外部数据源和工具交互的标准化方式。它就像 AI 应用的“通用接口”，通过客户端-服务器架构，让语言模型（如 Claude）能够安全、高效地访问实时数据、执行操作并扩展功能。MCP 的核心优势在于其统一性与模块化，开发者无需为每个工具或数据源编写定制集成，只需实现 MCP 协议即可让 AI 无缝连接。

### 我的 MCP 实现：天气查询、谷歌自动检索与摄像头控制

我基于 MCP 开发了一个多功能配置，集成了以下特性，开发者可根据需求自由调整：

- **天气查询**：通过 MCP 服务器连接外部天气 API（如 OpenWeatherMap），支持实时获取指定位置的天气预报和警报信息。用户只需输入指定地点，即可获得格式化的天气数据。
- **谷歌自动检索**：利用 MCP 工具，AI 可以动态调用谷歌搜索功能，自动检索相关信息并返回结果，适用于需要实时外部知识的场景。
- **摄像头控制**：集成了摄像头操作功能，通过 MCP 定义的工具，开发者可以控制摄像头执行拍摄、流媒体传输等任务，并支持自定义参数配置。

### 开发者自由配置

此实现的亮点在于其高度可配置性。开发者可以通过修改 MCP 服务器的工具定义（Tools）也就是server服务端、client客户端、服务端代理和提示模板（Prompts），轻松扩展功能。例如：
- 调整天气查询的 API 端点或返回格式。
- 更改谷歌检索的搜索参数或添加其他搜索引擎。
- 为摄像头控制添加新命令，如调整分辨率或切换设备。

### 使用场景

这个配置适用于多种场景，例如：
- **智能助手**：结合天气和检索功能，为用户提供实时信息支持。
- **自动化工作流**：通过摄像头控制与数据检索，构建监控或内容生成系统。
- **开发测试**：开发者可基于此模板快速集成新工具，探索 MCP 的潜力。

MCP 的标准化设计让 AI 不再局限于静态知识库，而是能主动与世界交互。我的代码提供了一个开箱即用的示例，欢迎开发者在此基础上自由发挥！

## MCP 环境配置指南

本指南将帮助你快速搭建 MCP（Model Context Protocol）客户端的开发环境，包括创建项目目录、设置虚拟环境以及安装 MCP SDK。以下是具体步骤：

### 1. 创建项目目录

首先，创建一个新的项目目录并进入其中：

# 创建项目目录
uv init mcp-client

# 进入项目目录
cd MCP-Server-For-Local

---

### 2. 创建 MCP 客户端虚拟环境

为了隔离项目依赖，我们需要创建一个虚拟环境并激活它：

# 创建虚拟环境
uv venv

# 激活虚拟环境（Windows）
.venv\Scripts\activate

# 激活虚拟环境（Linux/MacOS）
source .venv/bin/activate

---

### 3. 安装 MCP SDK

在虚拟环境中安装 MCP 的 Python SDK：

# 安装 MCP SDK
uv add mcp

# 安装 指定安装包比如dashscope等，缺哪个装哪个就行
uv pip install dashscope
---

### 4. 运行代码（可选）

完成环境配置后，你可以编写并运行 MCP 客户端代码。例如，创建一个简单的 `main.py` 文件：

# main.py
from mcp import MCPClient

client = MCPClient()
print("MCP Client initialized!")

然后运行代码：
python main.py

---

### 注意事项

- **依赖工具**：本教程假设你已安装 `uv`。如果没有，请先运行 `pip install uv`。
- **系统兼容性**：Windows 用户使用 `.venv\Scripts\activate`，Linux/MacOS 用户使用 `source .venv/bin/activate`。
- **后续步骤**：安装完成后，可根据项目需求配置天气查询、谷歌检索或摄像头控制等功能（详见项目文档）。

通过以上步骤，你已成功搭建 MCP 客户端的开发环境，可以开始开发和测试了！