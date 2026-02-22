"""
MCP (Model Context Protocol) 发布模块
通过 xiaohongshu-mcp 服务自动发布到小红书
"""

import os
import json
import time
import requests
from typing import List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MCPPublisher:
    """
    MCP 发布器
    调用 xiaohongshu-mcp 服务发布内容
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.server_url = config.get('server_url', 'http://localhost:18060')
        self.timeout = config.get('timeout', 120)
        
        # 检查 MCP 服务是否可用
        self._check_service()
        
        logger.info(f"MCP 发布器初始化完成，服务地址: {self.server_url}")
    
    def _check_service(self):
        """检查 MCP 服务状态"""
        try:
            response = requests.get(f"{self.server_url}/mcp", timeout=5)
            if response.status_code == 200:
                logger.info("MCP 服务连接正常")
            else:
                logger.warning(f"MCP 服务返回异常状态码: {response.status_code}")
        except Exception as e:
            logger.warning(f"MCP 服务可能未启动: {e}")
            logger.info("请先启动 xiaohongshu-mcp 服务: docker compose up -d xhs-mcp")
    
    def publish_note(self,
                     title: str,
                     content: str,
                     image_paths: List[str],
                     tags: List[str]) -> Optional[str]:
        """
        发布图文笔记到小红书
        
        Args:
            title: 笔记标题
            content: 笔记正文
            image_paths: 本地图片路径列表
            tags: 标签列表
            
        Returns:
            str: 发布的笔记ID（如果成功）
        """
        try:
            # 验证图片路径
            valid_images = []
            for path in image_paths:
                if os.path.exists(path):
                    valid_images.append(os.path.abspath(path))
                else:
                    logger.warning(f"图片不存在: {path}")
            
            if not valid_images:
                logger.error("没有有效的图片，无法发布")
                return None
            
            # 格式化内容
            formatted_content = self._format_content(content, tags)
            
            # 调用 MCP 发布
            note_id = self._publish_via_http(title, formatted_content, valid_images)
            
            if note_id:
                logger.info(f"笔记发布成功: {note_id}")
                return note_id
            else:
                logger.error("笔记发布失败")
                return None
                
        except Exception as e:
            logger.error(f"发布过程出错: {e}")
            return None
    
    def _format_content(self, content: str, tags: List[str]) -> str:
        """格式化笔记内容"""
        # 添加标签到内容末尾
        tags_str = ' '.join([f"#{tag.replace('#', '')}" for tag in tags])
        
        # 清理内容
        formatted = content.strip()
        
        # 如果内容没有包含标签，添加在末尾
        if tags_str and tags_str not in formatted:
            formatted += f"\n\n{tags_str}"
        
        return formatted
    
    def _publish_via_http(self, title: str, content: str, image_paths: List[str]) -> Optional[str]:
        """
        通过 HTTP API 调用 MCP 服务发布
        
        这是实际的发布调用，需要 xiaohongshu-mcp 服务支持 /publish 接口
        """
        url = f"{self.server_url}/mcp/publish"
        
        files = []
        try:
            # 构建 multipart 请求
            for img_path in image_paths:
                files.append(('images', open(img_path, 'rb')))
            
            data = {
                'title': title,
                'content': content
            }
            
            logger.info(f"正在调用 MCP 服务发布: {url}")
            logger.info(f"标题: {title[:30]}...")
            logger.info(f"图片数量: {len(image_paths)}")
            
            response = requests.post(
                url, 
                data=data, 
                files=files, 
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                note_id = result.get('note_id') or result.get('id')
                if note_id:
                    logger.info(f"MCP 发布成功，笔记ID: {note_id}")
                    return note_id
                else:
                    logger.error(f"MCP 返回中没有 note_id: {result}")
                    return None
            else:
                logger.error(f"MCP 服务返回错误: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.ConnectionError:
            logger.error(f"无法连接到 MCP 服务: {self.server_url}")
            logger.error("请确保 xiaohongshu-mcp 容器已启动")
            return None
        except Exception as e:
            logger.error(f"HTTP 发布失败: {e}")
            return None
        finally:
            # 确保文件句柄被关闭
            for _, f in files:
                try:
                    f.close()
                except:
                    pass


if __name__ == "__main__":
    # 测试
    import sys
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    config = {
        'server_url': os.getenv('MCP_URL', 'http://localhost:18060'),
        'timeout': 120
    }
    
    publisher = MCPPublisher(config)
    
    # 测试发布（需要真实图片路径）
    test_images = sys.argv[1:] if len(sys.argv) > 1 else []
    
    if test_images:
        note_id = publisher.publish_note(
            title="测试笔记标题",
            content="这是测试内容\n\n测试多行文本...",
            image_paths=test_images,
            tags=["#测试", "#AI"]
        )
        print(f"\n发布结果: {note_id}")
    else:
        print("用法: python mcp_publisher.py <图片路径1> <图片路径2> ...")
