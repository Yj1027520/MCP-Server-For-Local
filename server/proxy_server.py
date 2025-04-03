import json
import os
import sys
import asyncio
import logging
import locale
import time
from typing import Any, Dict
from mcp.server.fastmcp import FastMCP
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

# 获取系统编码
system_encoding = locale.getpreferredencoding()
logger_encoding = 'utf-8'

# 确保输出可见
print(f"Proxy Server 启动中... 系统编码: {system_encoding}")
sys.stdout.flush()

# 配置日志系统
logging.basicConfig(
    level=logging.DEBUG,  # 临时设置为 DEBUG 级别以便于调试
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('proxy_server.log', encoding=logger_encoding)
    ]
)
logger = logging.getLogger('ProxyServer')

# 确保标准输出使用正确的编码
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        logger.info(f"已将标准输出编码从 {system_encoding} 重新配置为 utf-8")
    except Exception as e:
        logger.warning(f"无法重新配置标准输出编码: {e}")

print("初始化代理服务器...")
sys.stdout.flush()
logger.info("代理服务器日志初始化完成")

# 初始化 MCP 服务器
mcp = FastMCP("ProxyServer")
exit_stack = AsyncExitStack()

# 设置默认配置文件路径
script_dir = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_FILE = os.path.join(script_dir, "..", "config", "servers.json")
CONFIG_FILE = os.environ.get("MCP_CONFIG", DEFAULT_CONFIG_FILE)

logger.info(f"使用配置文件: {CONFIG_FILE}")
print(f"使用配置文件: {CONFIG_FILE}")
sys.stdout.flush()

def safe_truncate(text, length=100):
    """安全地截断字符串，避免日志过长"""
    if not isinstance(text, str):
        try:
            text = str(text)
        except:
            return "[非字符串内容]"
    
    if len(text) <= length:
        return text
    return text[:length] + "..."

def load_server_config(config_file: str) -> list:
    """加载服务器配置"""
    logger.info(f"正在加载服务器配置: {config_file}")
    print(f"正在加载服务器配置: {config_file}")
    sys.stdout.flush()
    
    # 创建默认空配置
    empty_config = []
    
    try:
        # 检查配置文件是否存在
        if not os.path.exists(config_file):
            logger.warning(f"配置文件不存在: {config_file}")
            print(f"配置文件不存在: {config_file}")
            sys.stdout.flush()
            
            # 创建包含空列表的默认配置
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(empty_config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已创建空配置文件: {config_file}")
            return empty_config
            
        # 配置文件存在，尝试加载
        with open(config_file, 'r', encoding='utf-8') as f:
            try:
                servers = json.load(f)
                
                logger.info(f"已加载 {len(servers)} 个服务器配置")
                print(f"已加载 {len(servers)} 个服务器配置")
                sys.stdout.flush()
                
                if not isinstance(servers, list):
                    logger.error("配置文件必须包含服务器配置列表")
                    return empty_config
                    
                return servers
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析错误: {str(e)}")
                print(f"配置文件解析错误: {str(e)}")
                sys.stdout.flush()
                return empty_config
                
    except Exception as e:
        logger.error(f"加载配置失败: {str(e)}")
        print(f"加载配置失败: {str(e)}")
        sys.stdout.flush()
        return empty_config

# 加载服务器配置
print("加载服务器配置...")
sys.stdout.flush()

SERVERS = load_server_config(CONFIG_FILE)
sessions: Dict[str, ClientSession] = {}
tool_mapping: Dict[str, str] = {}

# 注册一个默认工具，确保即使没有配置也能正常工作
@mcp.tool(description="默认帮助工具，返回可用工具列表")
async def help() -> str:
    """返回可用工具列表"""
    if not tool_mapping:
        return "当前没有可用的工具。请检查配置文件和服务器脚本。"
    
    tools_list = ", ".join(tool_mapping.keys())
    return f"可用工具列表: {tools_list}"

async def initialize_servers():
    """初始化所有服务器连接"""
    logger.info(f"开始初始化 {len(SERVERS)} 个服务器")
    print(f"开始初始化 {len(SERVERS)} 个服务器...")
    sys.stdout.flush()
    
    if len(SERVERS) == 0:
        logger.warning("没有配置服务器，将跳过初始化")
        print("没有配置服务器，仅提供基本功能")
        sys.stdout.flush()
        return
    
    for i, server in enumerate(SERVERS):
        server_name = server.get("name", f"Server-{i}")
        script_path = server.get("script", "")
        
        if not script_path:
            logger.error(f"服务器 {server_name} 缺少脚本路径")
            continue
            
        logger.info(f"正在初始化服务器: {server_name}, 脚本: {script_path}")
        print(f"正在初始化服务器: {server_name}, 脚本: {script_path}")
        sys.stdout.flush()
        
        try:
            command = "python"
            
            # 尝试多种可能的路径
            possible_paths = [
                os.path.join(script_dir, script_path),  # 相对于脚本目录
                os.path.abspath(script_path),           # 绝对路径
                script_path                             # 原始路径
            ]
            
            full_script_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    full_script_path = path
                    break
            
            if not full_script_path:
                logger.error(f"找不到服务器脚本: {script_path}")
                print(f"找不到服务器脚本: {script_path}")
                sys.stdout.flush()
                continue
                
            logger.info(f"使用脚本路径: {full_script_path}")
            print(f"使用脚本路径: {full_script_path}")
            sys.stdout.flush()
            
            # 设置环境变量，确保子进程使用 UTF-8 编码
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            
            server_params = StdioServerParameters(
                command=command, 
                args=[full_script_path], 
                env=env
            )
            
            print(f"启动服务器进程: {server_name}")
            sys.stdout.flush()
            
            # 设置启动超时
            start_time = time.time()
            stdio_transport = await asyncio.wait_for(
                exit_stack.enter_async_context(stdio_client(server_params)),
                timeout=10  # 10秒超时
            )
            stdio, write = stdio_transport
            
            print(f"建立会话连接: {server_name}")
            sys.stdout.flush()
            
            session = await asyncio.wait_for(
                exit_stack.enter_async_context(ClientSession(stdio, write)),
                timeout=10  # 10秒超时
            )
            
            print(f"初始化会话: {server_name}")
            sys.stdout.flush()
            
            await asyncio.wait_for(
                session.initialize(),
                timeout=10  # 10秒超时
            )
            
            sessions[server_name] = session
            
            # 获取服务器提供的工具
            print(f"获取工具列表: {server_name}")
            sys.stdout.flush()
            
            response = await asyncio.wait_for(
                session.list_tools(),
                timeout=10  # 10秒超时
            )
            
            # 注册工具映射
            for tool in response.tools:
                tool_mapping[tool.name] = server_name
                logger.info(f"注册工具 '{tool.name}' 来自 {server_name}")
                print(f"注册工具 '{tool.name}' 来自 {server_name}")
                sys.stdout.flush()
                
            logger.info(f"服务器 {server_name} 初始化完成，提供 {len(response.tools)} 个工具")
            print(f"服务器 {server_name} 初始化完成，提供 {len(response.tools)} 个工具")
            sys.stdout.flush()
            
        except asyncio.TimeoutError:
            logger.error(f"初始化服务器 {server_name} 超时")
            print(f"初始化服务器 {server_name} 超时，跳过")
            sys.stdout.flush()
            continue
        except Exception as e:
            logger.error(f"初始化服务器 {server_name} 失败: {str(e)}")
            print(f"初始化服务器 {server_name} 失败: {str(e)}")
            sys.stdout.flush()
            continue

@mcp.tool(description="代理工具，根据工具名动态调用其他服务端的工具，输入格式为字典：{'tool': 'tool_name', 'args': {...}}")
async def proxy_tool_call(params: Dict[str, Any]) -> str:
    """代理工具调用，将请求转发到适当的服务器"""
    try:
        tool_name = params.get("tool")
        tool_args = params.get("args", {})
        
        logger.info(f"收到工具调用请求: {tool_name}")
        
        if not tool_name:
            logger.error("工具调用缺少工具名称")
            return "错误: 缺少工具名称"
            
        if tool_name not in tool_mapping:
            logger.error(f"未知工具: {tool_name}")
            available_tools = list(tool_mapping.keys())
            return f"未知工具: {tool_name}。可用工具: {available_tools}"
            
        server_name = tool_mapping[tool_name]
        logger.info(f"转发 {tool_name} 调用到服务器 {server_name}")
        
        if server_name not in sessions:
            logger.error(f"服务器会话不存在: {server_name}")
            return f"服务器会话不存在: {server_name}"
            
        session = sessions[server_name]
        try:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, tool_args), 
                timeout=30  # 30秒超时
            )
            response_text = result.content[0].text
            logger.info(f"工具 {tool_name} 调用成功")
            return response_text
        except asyncio.TimeoutError:
            logger.error(f"工具 {tool_name} 调用超时")
            return f"工具调用超时: {tool_name}"
            
    except Exception as e:
        logger.exception(f"工具调用失败: {str(e)}")
        return f"工具调用失败: {str(e)}"

async def run_proxy():
    """运行代理服务器"""
    logger.info("启动 MCP 代理服务器")
    print("启动 MCP 代理服务器...")
    sys.stdout.flush()
    
    try:
        await mcp.run_stdio_async()
    except Exception as e:
        logger.exception(f"代理服务器运行错误: {str(e)}")
        print(f"代理服务器运行错误: {str(e)}")
        sys.stdout.flush()

async def main():
    """主函数"""
    try:
        print("==== 代理服务器启动 ====")
        sys.stdout.flush()
        
        logger.info("==== 代理服务器启动 ====")
        logger.info(f"系统默认编码: {system_encoding}, 日志文件编码: {logger_encoding}")
        
        # 创建默认空配置文件
        await initialize_servers()
        
        # 显示已注册的工具
        tools_count = len(tool_mapping)
        logger.info(f"代理服务器已注册 {tools_count} 个工具: {list(tool_mapping.keys())}")
        print(f"代理服务器已注册 {tools_count} 个工具: {list(tool_mapping.keys())}")
        sys.stdout.flush()
        
        if tools_count == 0:
            logger.warning("警告: 没有注册任何工具，将提供基本帮助功能")
            print("警告: 没有注册任何工具，将提供基本帮助功能")
            sys.stdout.flush()
            
        # 通过单独的任务运行代理，以便于捕获异常
        proxy_task = asyncio.create_task(run_proxy())
        
        # 等待代理任务完成或出错
        await proxy_task
        
    except Exception as e:
        logger.exception("代理服务器运行时发生异常")
        print(f"代理服务器运行时发生异常: {str(e)}")
        sys.stdout.flush()
        return 1

if __name__ == "__main__":
    try:
        print("启动主程序...")
        sys.stdout.flush()
        
        # 直接输出以便调试
        sys.stdout.write("准备运行主函数...\n")
        sys.stdout.flush()
        
        exit_code = asyncio.run(main())
        if exit_code:
            sys.exit(exit_code)
            
    except KeyboardInterrupt:
        print("代理服务器已通过键盘中断停止")
        sys.stdout.flush()
        logger.info("代理服务器已通过键盘中断停止")
        
    except Exception as e:
        print(f"代理服务器发生未处理异常: {str(e)}")
        sys.stdout.flush()
        logger.exception("代理服务器发生未处理异常")
        
    finally:
        print("==== 代理服务器关闭 ====")
        sys.stdout.flush()
        logger.info("==== 代理服务器关闭 ====")
        
        try:
            # 安全关闭资源
            asyncio.run(exit_stack.aclose())
        except Exception as e:
            print(f"关闭资源时发生异常: {str(e)}")
            sys.stdout.flush()
            logger.exception("关闭资源时发生异常")