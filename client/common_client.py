import asyncio
import os
import json
import sys
import logging
import codecs
import locale
from typing import Optional
from contextlib import AsyncExitStack
from dashscope import Generation
from dotenv import load_dotenv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# 获取系统编码
system_encoding = locale.getpreferredencoding()
logger_encoding = 'utf-8'

# 自定义日志处理器，解决 Unicode 编码问题
class EncodingFixStreamHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        if stream is None:
            stream = sys.stdout
        super().__init__(stream)
        
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # 将日志消息中的特殊字符替换为安全的表示
            msg = msg.encode('utf-8', errors='replace').decode('utf-8')
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        EncodingFixStreamHandler(),
        logging.FileHandler('mcp_client.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('MCPClient')

# 确保标准输出使用正确的编码
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    logger.info(f"已将标准输出编码从 {sys.stdout.encoding} 重新配置为 utf-8")

# 添加安全的字符串截断函数
def safe_truncate(text, length=100):
    if not isinstance(text, str):
        try:
            text = str(text)
        except:
            return "[非字符串内容]"
    
    if len(text) <= length:
        return text
    return text[:length] + "..."

class MCPClient:
    def __init__(self):
        """初始化 MCP 客户端"""
        logger.info("初始化 MCP 客户端")
        self.exit_stack = AsyncExitStack()
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.model = os.getenv("MODEL") or "qwen-max"

        if not self.api_key:
            logger.error("未找到 API Key，请在 .env 文件中设置 DASHSCOPE_API_KEY")
            raise ValueError("❌ 未找到 API Key，请在 .env 文件中设置 DASHSCOPE_API_KEY")

        import dashscope
        dashscope.api_key = self.api_key
        logger.info(f"使用模型: {self.model}")
        self.session: Optional[ClientSession] = None

    async def connect_to_server(self, server_script_path: str):
        """连接到 MCP 服务器并列出可用工具"""
        logger.info(f"正在连接到服务器脚本: {server_script_path}")
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            logger.error(f"不支持的服务器脚本类型: {server_script_path}")
            raise ValueError("服务器脚本必须是 .py 或 .js 文件")

        command = "python" if is_python else "node"
        
        # 规范化路径，确保路径分隔符正确
        server_script_path = os.path.normpath(server_script_path)
        
        # 设置环境变量，确保子进程使用 UTF-8 编码
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=env
        )

        logger.info(f"启动服务器进程: {command} {server_script_path}")
        
        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

            logger.info("初始化会话...")
            await self.session.initialize()

            response = await self.session.list_tools()
            tools = response.tools
            tool_names = [tool.name for tool in tools]
            logger.info(f"已连接到服务器，支持的工具: {tool_names}")
            print("\n已连接到服务器，支持以下工具:", tool_names)
        except Exception as e:
            logger.exception(f"连接服务器失败: {str(e)}")
            raise RuntimeError(f"连接服务器失败: {str(e)}")

    async def process_query(self, query: str) -> str:
        """使用 DashScope 处理查询，通过代理服务端调用工具"""
        logger.info(f"处理用户查询: {query}")
        try:
            response = await self.session.list_tools()
            tool_descriptions = "\n".join(
                f"- {tool.name}: {tool.description} (输入参数: {json.dumps(tool.inputSchema)})"
                for tool in response.tools
            )
            logger.debug(f"可用工具描述: {safe_truncate(tool_descriptions, 500)}")

            system_prompt = f"""
                你是一个智能助手，可以根据用户输入决定是否调用工具。当前通过代理服务端支持以下底层工具：
                - query_weather: 查询指定城市代码的天气信息，输入参数为城市代码（如 '110000' 表示北京，'330100' 表示杭州）
                - google_search: 使用 google_search 工具，参数名必须是 query，打开本地谷歌浏览器并搜索指定关键词，输入参数为搜索关键词（如 'Python tutorial'）。
                - capture_camera_image：使用 capture_camera_image 工具，拍照。

                代理服务端工具：
                {tool_descriptions}

                你的任务是：
                1. 理解用户的问题。
                2. 如果需要调用工具，返回 JSON 格式的响应，包含：
                   - "action": "call_tool"
                   - "tool": 底层工具名称（如 'query_weather' 或 'google_search'）
                   - "args": 工具参数（字典格式）
                3. 如果不需要工具，直接返回纯文本回答。

                请以以下格式返回：
                - 工具调用: ```json\n{{"action": "call_tool", "tool": "tool_name", "args": {{...}}}}\n```
                - 普通回答: 直接返回文本

                注意：
                - 如果用户提到城市天气，请将城市名转换为高德地图城市代码（例如"北京" -> "110000"，"杭州" -> "330100"）。
                - 代理服务端会将请求转发到正确的工具，你只需指定底层工具名和参数。
            """
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]

            try:
                logger.info(f"调用 DashScope API，模型: {self.model}")
                logger.debug(f"发送到模型的消息: {safe_truncate(str(messages), 300)}")
                response = await asyncio.to_thread(
                    Generation.call,
                    model=self.model,
                    messages=messages,
                    result_format="message"
                )
                if response.status_code != 200:
                    error_msg = f"DashScope API 失败: {response.message}"
                    logger.error(f"DashScope API 错误: {response.status_code} - {response.message}")
                    return error_msg

                content = response.output.choices[0].message.content
                logger.debug(f"DashScope 返回的原始内容: {safe_truncate(content, 300)}")
                
                try:
                    if "```json" in content:
                        logger.info("检测到工具调用JSON")
                        json_str = content.split("```json")[1].split("```")[0].strip()
                        logger.debug(f"提取的JSON字符串: {safe_truncate(json_str, 200)}")
                        tool_data = json.loads(json_str)
                        
                        if tool_data.get("action") == "call_tool":
                            tool_name = tool_data.get("tool")
                            tool_args = tool_data.get("args", {})

                            if not tool_name:
                                logger.error("工具调用缺少工具名称")
                                return "工具名称缺失"

                            # 包装参数为 {"params": {...}} 结构
                            proxy_params = {
                                "params": {"tool": tool_name, "args": tool_args}
                            }
                            logger.info(f"调用工具: {tool_name}, 参数: {tool_args}")
                            
                            try:
                                result = await self.session.call_tool("proxy_tool_call", proxy_params)
                                tool_result = result.content[0].text
                                logger.info(f"工具调用结果: {safe_truncate(tool_result)}")
                                return tool_result
                            except Exception as tool_error:
                                error_msg = f"工具调用失败: {str(tool_error)}"
                                logger.error(error_msg)
                                return error_msg
                    
                    logger.info("返回普通文本回复")
                    return content
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON解析错误: {e}, 返回原始内容")
                    return content

            except Exception as e:
                error_msg = f"调用 DashScope API 时出错: {str(e)}"
                logger.exception("处理查询时出错")
                return error_msg
                
        except Exception as e:
            logger.exception(f"处理查询失败: {str(e)}")
            return f"处理查询失败: {str(e)}"

    async def chat_loop(self):
        """运行交互式聊天循环"""
        logger.info("启动交互式聊天循环")
        print("\n🤖 MCP 客户端已启动！输入 'quit' 退出")
        print("示例：'北京的天气怎么样？' 或 '在谷歌上搜索 Python 教程'")
        while True:
            try:
                query = input("\n你: ").strip()
                if query.lower() == 'quit':
                    logger.info("用户请求退出，结束聊天循环")
                    break
                logger.info(f"用户输入: {query}")
                response = await self.process_query(query)
                logger.info(f"返回给用户的回复: {safe_truncate(response)}")
                print(f"\n🤖 DashScope: {response}")
            except Exception as e:
                logger.exception("聊天循环发生异常")
                print(f"\n发生错误: {str(e)}")

    async def cleanup(self):
        """清理资源"""
        logger.info("清理资源...")
        try:
            await self.exit_stack.aclose()
            logger.info("资源清理完成")
        except Exception as e:
            logger.exception(f"清理资源失败: {str(e)}")
            print(f"清理资源失败: {str(e)}")

async def main():
    logger.info(f"系统默认编码: {system_encoding}, 日志文件编码: {logger_encoding}")
    
    if len(sys.argv) < 2:
        logger.error("缺少服务器脚本路径参数")
        print("Usage: python common_client.py <path_to_server_script>")
        sys.exit(1)

    server_script = sys.argv[1]
    logger.info(f"启动 MCP 客户端，服务器脚本: {server_script}")
    
    client = MCPClient()
    try:
        await client.connect_to_server(server_script)
        await client.chat_loop()
    except Exception as e:
        logger.exception("程序运行时发生异常")
        print(f"程序异常: {str(e)}")
    finally:
        logger.info("程序退出，执行清理操作")
        await client.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已通过键盘中断停止")
    except Exception as e:
        logger.exception("程序发生未处理异常")