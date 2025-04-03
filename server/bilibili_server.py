import os
import json
import sys
import logging
from typing import Any, Dict, List, Optional

from bilibili_api import search, sync, video
from mcp.server.fastmcp import FastMCP

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bilibili_server.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('BilibiliServer')

# 初始化 MCP 服务器
mcp = FastMCP("BilibiliServer")

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

@mcp.tool(description="在 Bilibili 上搜索指定关键词")
async def bilibili_search(keyword: str) -> str:
    """
    使用给定的关键词在 Bilibili 上搜索内容。
    
    Args:
        keyword: 要在 Bilibili 上搜索的关键词
        
    Returns:
        包含搜索结果的 JSON 字符串
    """
    try:
        logger.info(f"正在 Bilibili 搜索关键词: {keyword}")
        results = await search.search(keyword)
        
        # 提取最有用的信息
        formatted_results = []
        
        # 处理视频结果
        if 'result' in results and isinstance(results['result'], list):
            for item in results['result'][:5]:  # 只取前5条结果
                if item.get('type') == 'video':
                    formatted_item = {
                        'title': item.get('title', ''),
                        'author': item.get('author', ''),
                        'bvid': item.get('bvid', ''),
                        'play': item.get('play', 0),
                        'duration': item.get('duration', ''),
                        'description': item.get('description', ''),
                        'url': f"https://www.bilibili.com/video/{item.get('bvid', '')}"
                    }
                    formatted_results.append(formatted_item)
        
        # 限制响应大小并格式化
        response = {
            'keyword': keyword,
            'count': len(formatted_results),
            'items': formatted_results
        }
        
        logger.info(f"搜索完成，返回 {len(formatted_results)} 条结果")
        return json.dumps(response, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.exception(f"Bilibili 搜索出错: {str(e)}")
        return json.dumps({
            'error': f"搜索失败: {str(e)}",
            'keyword': keyword
        }, ensure_ascii=False)

@mcp.tool(description="获取 Bilibili 视频详细信息")
async def bilibili_video_info(bvid: str) -> str:
    """
    获取指定 BV 号视频的详细信息。
    
    Args:
        bvid: Bilibili 视频的 BV 号 (如 BV1xx411c7mD)
        
    Returns:
        包含视频详细信息的 JSON 字符串
    """
    try:
        logger.info(f"获取视频信息: {bvid}")
        
        # 创建视频对象
        v = video.Video(bvid=bvid)
        
        # 获取视频信息
        info = await v.get_info()
        
        # 提取关键信息
        result = {
            'bvid': bvid,
            'title': info.get('title', ''),
            'desc': info.get('desc', ''),
            'author': info.get('owner', {}).get('name', ''),
            'mid': info.get('owner', {}).get('mid', 0),
            'view_count': info.get('stat', {}).get('view', 0),
            'like_count': info.get('stat', {}).get('like', 0),
            'coin_count': info.get('stat', {}).get('coin', 0),
            'favorite_count': info.get('stat', {}).get('favorite', 0),
            'duration': info.get('duration', 0),
            'pubdate': info.get('pubdate', 0),
            'tags': [tag.get('tag_name', '') for tag in info.get('tag', [])],
            'url': f"https://www.bilibili.com/video/{bvid}"
        }
        
        logger.info(f"成功获取视频信息: {result['title']}")
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.exception(f"获取视频信息失败: {str(e)}")
        return json.dumps({
            'error': f"获取视频信息失败: {str(e)}",
            'bvid': bvid
        }, ensure_ascii=False)

@mcp.tool(description="获取 Bilibili 视频的热门评论")
async def bilibili_video_comments(bvid: str, limit: int = 10) -> str:
    """
    获取指定 BV 号视频的热门评论。
    
    Args:
        bvid: Bilibili 视频的 BV 号 (如 BV1xx411c7mD)
        limit: 要获取的评论数量，默认10条
        
    Returns:
        包含视频评论的 JSON 字符串
    """
    try:
        logger.info(f"获取视频评论: {bvid}, 数量: {limit}")
        
        # 创建视频对象
        v = video.Video(bvid=bvid)
        
        # 获取视频评论
        comments_raw = await v.get_comments(page_index=1)
        
        # 提取评论信息
        comments = []
        if 'replies' in comments_raw and comments_raw['replies']:
            for comment in comments_raw['replies'][:limit]:
                comment_data = {
                    'user': comment.get('member', {}).get('uname', ''),
                    'content': comment.get('content', {}).get('message', ''),
                    'like': comment.get('like', 0),
                    'time': comment.get('ctime', 0)
                }
                comments.append(comment_data)
        
        result = {
            'bvid': bvid,
            'comment_count': len(comments),
            'comments': comments
        }
        
        logger.info(f"成功获取 {len(comments)} 条评论")
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.exception(f"获取视频评论失败: {str(e)}")
        return json.dumps({
            'error': f"获取视频评论失败: {str(e)}",
            'bvid': bvid
        }, ensure_ascii=False)

@mcp.tool(description="在 Bilibili 上获取热门排行榜")
async def bilibili_ranking(rid: int = 0, day: int = 7) -> str:
    """
    获取 Bilibili 热门排行榜。
    
    Args:
        rid: 分区 ID，0 表示全站，1 动画，3 音乐，4 游戏等
        day: 时间范围，可选 1, 3, 7, 30 天
        
    Returns:
        包含排行榜信息的 JSON 字符串
    """
    try:
        logger.info(f"获取排行榜: 分区 {rid}, 时间范围 {day}天")
        
        from bilibili_api import ranking
        rank_data = await ranking.get_ranking_videos(rid=rid, day=day)
        
        # 提取关键信息
        videos = []
        for item in rank_data[:20]:  # 只取前20条
            video_info = {
                'title': item.get('title', ''),
                'author': item.get('owner', {}).get('name', ''),
                'bvid': item.get('bvid', ''),
                'play': item.get('stat', {}).get('view', 0),
                'like': item.get('stat', {}).get('like', 0),
                'url': f"https://www.bilibili.com/video/{item.get('bvid', '')}"
            }
            videos.append(video_info)
        
        result = {
            'rid': rid,
            'day': day,
            'count': len(videos),
            'videos': videos
        }
        
        logger.info(f"成功获取排行榜，共 {len(videos)} 条视频")
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.exception(f"获取排行榜失败: {str(e)}")
        return json.dumps({
            'error': f"获取排行榜失败: {str(e)}",
            'rid': rid,
            'day': day
        }, ensure_ascii=False)

if __name__ == "__main__":
    try:
        print("启动 Bilibili MCP 服务器...")
        sys.stdout.flush()
        logger.info("启动 Bilibili MCP 服务器")
        
        # 列出注册的工具
        tools = [
            "bilibili_search - 在 Bilibili 上搜索指定关键词",
            "bilibili_video_info - 获取 Bilibili 视频详细信息",
            "bilibili_video_comments - 获取 Bilibili 视频的热门评论",
            "bilibili_ranking - 在 Bilibili 上获取热门排行榜"
        ]
        
        logger.info(f"注册了 {len(tools)} 个工具: {', '.join(tool.split(' - ')[0] for tool in tools)}")
        print(f"注册了 {len(tools)} 个工具: {', '.join(tool.split(' - ')[0] for tool in tools)}")
        sys.stdout.flush()
        
        # 启动服务器
        mcp.run_stdio()
        
    except KeyboardInterrupt:
        logger.info("服务器已通过键盘中断停止")
    except Exception as e:
        logger.exception(f"服务器运行时发生异常: {str(e)}")
        print(f"服务器运行时发生异常: {str(e)}")
        sys.stdout.flush() 