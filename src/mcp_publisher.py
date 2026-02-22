"""
MCP (Model Context Protocol) 发布模块
通过 x-mcp 服务自动发布到小红书
使用 JSON-RPC 2.0 协议
"""

import os
import json
import time
import uuid
import base64
import requests
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP JSON-RPC 客户端
    实现完整的 MCP 协议握手和工具调用
    """
    
    def __init__(self, server_url: str, api_key: str = '', timeout: int = 120):
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.request_id = 0
        self.initialized = False
        self.tools = []
        
        self.headers = {
            'Content-Type': 'application/json',
        }
        if api_key:
            self.headers['X-API-Key'] = api_key
    
    def _next_id(self) -> int:
        self.request_id += 1
        return self.request_id
    
    def _send_request(self, method: str, params: Dict = None) -> Dict:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {}
        }
        
        try:
            response = requests.post(
                self.server_url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            
            if 'error' in result:
                logger.error(f"MCP 错误: {result['error']}")
                raise Exception(f"MCP Error: {result['error']}")
            
            return result.get('result', {})
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {e}")
            raise
    
    def _send_notification(self, method: str, params: Dict = None):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        
        try:
            response = requests.post(
                self.server_url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"通知发送失败: {e}")
    
    def connect(self) -> bool:
        try:
            result = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "xiaohongshu-auto-publisher",
                    "version": "1.0.0"
                }
            })
            
            logger.info(f"MCP 服务器: {result.get('serverInfo', {})}")
            logger.info(f"支持的能力: {list(result.get('capabilities', {}).keys())}")
            
            self._send_notification("notifications/initialized")
            
            self.initialized = True
            return True
            
        except Exception as e:
            logger.error(f"MCP 连接失败: {e}")
            return False
    
    def list_tools(self) -> List[Dict]:
        if not self.initialized:
            raise Exception("MCP 未初始化，请先调用 connect()")
        
        result = self._send_request("tools/list", {})
        self.tools = result.get('tools', [])
        logger.info(f"可用工具: {[t.get('name') for t in self.tools]}")
        return self.tools
    
    def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        if not self.initialized:
            raise Exception("MCP 未初始化，请先调用 connect()")
        
        logger.info(f"调用工具: {tool_name}")
        logger.debug(f"参数: {arguments}")
        
        result = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        return result


class MCPPublisher:
    """
    小红书发布器
    通过 x-mcp 服务发布内容到小红书
    """
    
    def __init__(self, config: dict):
        self.config = config
        
        self.server_url = config.get('server_url', 'https://mcp.zouying.work/mcp')
        self.api_key = config.get('api_key', '') or os.getenv('X_MCP_API_KEY', '')
        self.timeout = config.get('timeout', 180)
        
        self.client = MCPClient(
            server_url=self.server_url,
            api_key=self.api_key,
            timeout=self.timeout
        )
        
        self._connected = False
        
        logger.info(f"MCP 发布器初始化，服务地址: {self.server_url}")
    
    def _ensure_connected(self) -> bool:
        if self._connected:
            return True
        
        if not self.api_key:
            logger.error("未配置 X-MCP API Key，请设置 X_MCP_API_KEY 环境变量或在配置中设置 api_key")
            return False
        
        try:
            if self.client.connect():
                self.client.list_tools()
                self._connected = True
                return True
        except Exception as e:
            logger.error(f"连接 MCP 服务失败: {e}")
        
        return False
    
    def check_login_status(self) -> bool:
        if not self._ensure_connected():
            return False
        
        try:
            result = self.client.call_tool("check_login", {})
            is_logged_in = result.get('content', [{}])[0].get('text', '').find('已登录') >= 0
            logger.info(f"登录状态: {'已登录' if is_logged_in else '未登录'}")
            return is_logged_in
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False
    
    def publish_note(self,
                     title: str,
                     content: str,
                     image_paths: List[str],
                     tags: List[str] = None) -> Optional[str]:
        """
        发布图文笔记到小红书
        
        Args:
            title: 笔记标题
            content: 笔记正文
            image_paths: 本地图片路径列表或URL列表
            tags: 标签列表
            
        Returns:
            str: 发布的笔记ID或分享链接
        """
        if not self._ensure_connected():
            return None
        
        try:
            valid_images = []
            for path in image_paths:
                if path.startswith('http://') or path.startswith('https://'):
                    valid_images.append(path)
                elif os.path.exists(path):
                    image_url = self._upload_image(path)
                    if image_url:
                        valid_images.append(image_url)
                else:
                    logger.warning(f"图片不存在: {path}")
            
            if not valid_images:
                logger.error("没有有效的图片，无法发布")
                return None
            
            formatted_content = self._format_content(content, tags or [])
            
            result = self.client.call_tool("publish_note", {
                "title": title,
                "content": formatted_content,
                "images": valid_images
            })
            
            content_list = result.get('content', [])
            if content_list:
                text = content_list[0].get('text', '')
                logger.info(f"发布结果: {text}")
                
                if '成功' in text or 'success' in text.lower():
                    return text
            
            return None
            
        except Exception as e:
            logger.error(f"发布过程出错: {e}")
            return None
    
    def publish_note_with_urls(self,
                                title: str,
                                content: str,
                                image_urls: List[str],
                                tags: List[str] = None) -> Optional[str]:
        """
        使用图片URL发布笔记
        
        Args:
            title: 笔记标题
            content: 笔记正文
            image_urls: 图片URL列表
            tags: 标签列表
            
        Returns:
            str: 发布结果
        """
        if not self._ensure_connected():
            return None
        
        try:
            formatted_content = self._format_content(content, tags or [])
            
            result = self.client.call_tool("publish_note", {
                "title": title,
                "content": formatted_content,
                "images": image_urls
            })
            
            content_list = result.get('content', [])
            if content_list:
                text = content_list[0].get('text', '')
                logger.info(f"发布结果: {text}")
                return text
            
            return None
            
        except Exception as e:
            logger.error(f"发布过程出错: {e}")
            return None
    
    def _upload_image(self, image_path: str) -> Optional[str]:
        """
        上传图片并返回URL
        注意：x-mcp 可能需要先上传图片，这里暂时返回本地路径
        实际使用时可能需要先调用上传工具
        """
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            ext = Path(image_path).suffix.lower()
            mime_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }.get(ext, 'image/jpeg')
            
            data_uri = f"data:{mime_type};base64,{image_data}"
            
            result = self.client.call_tool("upload_image", {
                "image_data": data_uri
            })
            
            content_list = result.get('content', [])
            if content_list:
                return content_list[0].get('text', '')
            
            return None
            
        except Exception as e:
            logger.warning(f"图片上传失败，尝试直接使用本地路径: {e}")
            return image_path
    
    def _format_content(self, content: str, tags: List[str]) -> str:
        formatted = content.strip()
        
        if tags:
            tags_str = ' '.join([f"#{tag.replace('#', '')}" for tag in tags])
            if tags_str and tags_str not in formatted:
                formatted += f"\n\n{tags_str}"
        
        return formatted


def test_mcp_connection(api_key: str):
    client = MCPClient(
        server_url='https://mcp.zouying.work/mcp',
        api_key=api_key
    )
    
    print("正在连接 MCP 服务...")
    if client.connect():
        print("✅ 连接成功!")
        
        print("\n正在获取工具列表...")
        tools = client.list_tools()
        for tool in tools:
            print(f"  - {tool.get('name')}: {tool.get('description', '')[:50]}")
        
        return True
    else:
        print("❌ 连接失败")
        return False


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    api_key = os.getenv('X_MCP_API_KEY', '')
    
    if not api_key:
        print("请设置环境变量 X_MCP_API_KEY")
        print("示例: export X_MCP_API_KEY=your-api-key")
        sys.exit(1)
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_mcp_connection(api_key)
    else:
        publisher = MCPPublisher({'api_key': api_key})
        
        if len(sys.argv) > 2:
            title = sys.argv[1]
            content = sys.argv[2]
            images = sys.argv[3:] if len(sys.argv) > 3 else []
            
            result = publisher.publish_note_with_urls(title, content, images)
            print(f"\n发布结果: {result}")
        else:
            print("用法:")
            print("  python mcp_publisher.py test                              # 测试连接")
            print("  python mcp_publisher.py '标题' '内容' '图片URL1' '图片URL2'  # 发布笔记")
