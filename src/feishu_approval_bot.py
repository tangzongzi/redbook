#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书机器人增强模块
支持向指定用户发送审核卡片，处理交互式按钮回调
"""
import json
import os
import logging
import time
import hashlib
import requests
from typing import Optional, Dict, List, Callable
from datetime import datetime
from dataclasses import dataclass, field

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

logger = logging.getLogger(__name__)


@dataclass
class ApprovalResult:
    """审核结果"""
    content_id: str
    action: str  # 'approve' or 'reject'
    user_id: str
    user_name: str
    timestamp: str
    message_id: str = ""
    note_id: str = ""
    share_url: str = ""


@dataclass
class ContentForApproval:
    """待审核内容"""
    id: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    created_at: str = ""


class FeishuApprovalBot:
    """飞书审核机器人"""
    
    def __init__(self, app_id: str = '', app_secret: str = '', verify_token: str = '', encrypt_key: str = ''):
        self.app_id = app_id or os.getenv('FEISHU_APP_ID', '')
        self.app_secret = app_secret or os.getenv('FEISHU_APP_SECRET', '')
        self.verify_token = verify_token or os.getenv('FEISHU_VERIFY_TOKEN', '')
        self.encrypt_key = encrypt_key or os.getenv('FEISHU_ENCRYPT_KEY', '')
        
        self.enabled = bool(self.app_id and self.app_secret)
        
        self.client = None
        self.tenant_access_token = None
        self.token_expire_time = 0
        
        self.pending_contents: Dict[str, ContentForApproval] = {}
        self.approval_results: Dict[str, ApprovalResult] = {}
        
        self.approve_callback: Optional[Callable] = None
        self.reject_callback: Optional[Callable] = None
        
        if self.enabled:
            self._init_client()
    
    def _init_client(self):
        """初始化飞书客户端"""
        try:
            self.client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .log_level(lark.LogLevel.ERROR) \
                .build()
            logger.info("飞书客户端初始化成功")
        except Exception as e:
            logger.error(f"飞书客户端初始化失败: {e}")
            self.enabled = False
    
    def _get_tenant_access_token(self) -> Optional[str]:
        """获取 tenant_access_token"""
        if self.tenant_access_token and time.time() < self.token_expire_time:
            return self.tenant_access_token
        
        try:
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            response = requests.post(
                url,
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=10
            )
            result = response.json()
            
            if result.get('code') == 0:
                self.tenant_access_token = result.get('tenant_access_token')
                self.token_expire_time = time.time() + result.get('expire', 7200) - 300
                return self.tenant_access_token
            else:
                logger.error(f"获取 token 失败: {result}")
                return None
        except Exception as e:
            logger.error(f"获取 token 异常: {e}")
            return None
    
    def send_to_user(self, user_id: str, content: ContentForApproval) -> Optional[str]:
        """
        发送审核卡片给指定用户
        
        Args:
            user_id: 飞书用户ID (open_id 或 user_id)
            content: 待审核内容
            
        Returns:
            message_id: 消息ID
        """
        if not self.enabled:
            logger.warning("飞书机器人未启用")
            return None
        
        token = self._get_tenant_access_token()
        if not token:
            return None
        
        try:
            card = self._build_approval_card(content)
            
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "receive_id_type": "open_id" if user_id.startswith("ou_") else "user_id"
            }
            
            data = {
                "receive_id": user_id,
                "msg_type": "interactive",
                "content": json.dumps({"card": card})
            }
            
            response = requests.post(url, headers=headers, params=params, json=data, timeout=10)
            result = response.json()
            
            if result.get('code') == 0:
                message_id = result.get('data', {}).get('message_id')
                self.pending_contents[content.id] = content
                logger.info(f"审核卡片已发送给用户 {user_id}: {content.id}")
                return message_id
            else:
                logger.error(f"发送消息失败: {result}")
                return None
                
        except Exception as e:
            logger.error(f"发送消息异常: {e}")
            return None
    
    def send_to_chat(self, chat_id: str, content: ContentForApproval) -> Optional[str]:
        """
        发送审核卡片到群聊
        
        Args:
            chat_id: 群聊ID
            content: 待审核内容
            
        Returns:
            message_id: 消息ID
        """
        if not self.enabled:
            return None
        
        token = self._get_tenant_access_token()
        if not token:
            return None
        
        try:
            card = self._build_approval_card(content)
            
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            params = {"receive_id_type": "chat_id"}
            
            data = {
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps({"card": card})
            }
            
            response = requests.post(url, headers=headers, params=params, json=data, timeout=10)
            result = response.json()
            
            if result.get('code') == 0:
                message_id = result.get('data', {}).get('message_id')
                self.pending_contents[content.id] = content
                logger.info(f"审核卡片已发送到群聊 {chat_id}: {content.id}")
                return message_id
            else:
                logger.error(f"发送消息到群聊失败: {result}")
                return None
                
        except Exception as e:
            logger.error(f"发送消息到群聊异常: {e}")
            return None
    
    def _build_approval_card(self, content: ContentForApproval) -> dict:
        """构建审核卡片"""
        
        content_preview = content.content[:200] + "..." if len(content.content) > 200 else content.content
        tags_str = " ".join([f"#{tag}" for tag in content.tags[:5]]) if content.tags else "无标签"
        
        provider_info = ""
        if content.provider:
            provider_names = {
                'deepseek': 'DeepSeek',
                'openai': 'OpenAI',
                'anthropic': 'Anthropic',
                'moonshot': '月之暗面',
                'zhipu': '智谱AI',
                'baidu': '百度',
                'ali': '阿里云',
                'tencent': '腾讯',
                'doubao': '字节跳动'
            }
            provider_name = provider_names.get(content.provider, content.provider)
            provider_info = f"\n🤖 生成模型: {provider_name} / {content.model}" if content.model else f"\n🤖 生成模型: {provider_name}"
        
        card = {
            "config": {
                "wide_screen_mode": True,
                "enable_forward": True,
                "update_multi": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📋 内容审核通知"
                },
                "subtitle": {
                    "tag": "plain_text",
                    "content": f"ID: {content.id}"
                },
                "template": "blue",
                "icon": {
                    "tag": "standard_icon",
                    "token": "icon_checklist"
                }
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📝 标题**\n{content.title}"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📄 正文预览**\n{content_preview}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**🏷️ 标签**\n{tags_str}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**🔍 关键词**: {', '.join(content.keywords) if content.keywords else '无'}{provider_info}"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"⏰ 生成时间: {content.created_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 通过"
                            },
                            "type": "primary",
                            "value": {
                                "action": "approve",
                                "content_id": content.id
                            }
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "❌ 不通过"
                            },
                            "type": "danger",
                            "value": {
                                "action": "reject",
                                "content_id": content.id
                            }
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "📝 编辑后通过"
                            },
                            "type": "default",
                            "value": {
                                "action": "edit",
                                "content_id": content.id
                            }
                        }
                    ]
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "💡 点击「通过」将自动发布到小红书，点击「不通过」将删除此内容"
                        }
                    ]
                }
            ]
        }
        
        return card
    
    def handle_card_callback(self, event_data: dict) -> dict:
        """
        处理卡片按钮回调
        
        Args:
            event_data: 飞书推送的回调数据
            
        Returns:
            响应数据（用于更新卡片）
        """
        try:
            action = event_data.get('action', {})
            action_value = action.get('value', {})
            
            action_type = action_value.get('action')
            content_id = action_value.get('content_id')
            
            user_info = event_data.get('user', {})
            user_id = user_info.get('open_id', '')
            user_name = user_info.get('name', '未知用户')
            
            open_message_id = event_data.get('open_message_id', '')
            
            content = self.pending_contents.get(content_id)
            if not content:
                return self._build_toast_response("内容不存在或已处理", "error")
            
            if action_type == 'approve':
                result = ApprovalResult(
                    content_id=content_id,
                    action='approve',
                    user_id=user_id,
                    user_name=user_name,
                    timestamp=datetime.now().isoformat(),
                    message_id=open_message_id
                )
                self.approval_results[content_id] = result
                
                if self.approve_callback:
                    try:
                        self.approve_callback(content, result)
                    except Exception as e:
                        logger.error(f"执行通过回调失败: {e}")
                
                del self.pending_contents[content_id]
                
                return self._build_approved_card_response(content, user_name)
            
            elif action_type == 'reject':
                result = ApprovalResult(
                    content_id=content_id,
                    action='reject',
                    user_id=user_id,
                    user_name=user_name,
                    timestamp=datetime.now().isoformat(),
                    message_id=open_message_id
                )
                self.approval_results[content_id] = result
                
                if self.reject_callback:
                    try:
                        self.reject_callback(content, result)
                    except Exception as e:
                        logger.error(f"执行拒绝回调失败: {e}")
                
                del self.pending_contents[content_id]
                
                return self._build_rejected_card_response(content, user_name)
            
            elif action_type == 'edit':
                return self._build_toast_response("请在 Web 控制台编辑内容", "info")
            
            return self._build_toast_response("未知操作", "error")
            
        except Exception as e:
            logger.error(f"处理卡片回调异常: {e}")
            return self._build_toast_response(f"处理失败: {str(e)}", "error")
    
    def _build_toast_response(self, message: str, toast_type: str = "info") -> dict:
        """构建 Toast 响应"""
        return {
            "toast": {
                "type": toast_type,
                "content": message
            }
        }
    
    def _build_approved_card_response(self, content: ContentForApproval, user_name: str) -> dict:
        """构建已通过状态的卡片响应"""
        return {
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "✅ 已通过审核"},
                    "template": "green"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**{content.title}**\n\n已由 {user_name} 审核通过，正在发布到小红书..."
                        }
                    }
                ]
            }
        }
    
    def _build_rejected_card_response(self, content: ContentForApproval, user_name: str) -> dict:
        """构建已拒绝状态的卡片响应"""
        return {
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "❌ 已拒绝"},
                    "template": "red"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**{content.title}**\n\n已由 {user_name} 拒绝，不会发布"
                        }
                    }
                ]
            }
        }
    
    def update_card_published(self, content_id: str, note_id: str, share_url: str):
        """更新卡片为已发布状态"""
        result = self.approval_results.get(content_id)
        if result:
            result.note_id = note_id
            result.share_url = share_url
    
    def get_approval_result(self, content_id: str) -> Optional[ApprovalResult]:
        """获取审核结果"""
        return self.approval_results.get(content_id)
    
    def get_pending_contents(self) -> List[ContentForApproval]:
        """获取所有待审核内容"""
        return list(self.pending_contents.values())
    
    def set_callbacks(self, approve_callback: Callable, reject_callback: Callable):
        """设置审核回调函数"""
        self.approve_callback = approve_callback
        self.reject_callback = reject_callback


class FeishuWebhookHandler:
    """飞书 Webhook 处理器（简化版，用于群机器人）"""
    
    def __init__(self):
        self.webhook_url = os.getenv('FEISHU_WEBHOOK_URL', '')
        self.enabled = bool(self.webhook_url)
        self.pending_contents: Dict[str, ContentForApproval] = {}
        self.approval_results: Dict[str, ApprovalResult] = {}
    
    def send_approval_card(self, content: ContentForApproval) -> bool:
        """发送审核卡片到群聊"""
        if not self.enabled:
            logger.warning("飞书 Webhook 未配置")
            return False
        
        try:
            card = self._build_simple_card(content)
            
            message = {
                "msg_type": "interactive",
                "card": card
            }
            
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            result = response.json()
            
            if result.get('code') == 0:
                self.pending_contents[content.id] = content
                logger.info(f"审核卡片已发送: {content.id}")
                return True
            else:
                logger.error(f"发送审核卡片失败: {result}")
                return False
                
        except Exception as e:
            logger.error(f"发送审核卡片异常: {e}")
            return False
    
    def _build_simple_card(self, content: ContentForApproval) -> dict:
        """构建简化的审核卡片（用于 Webhook）"""
        content_preview = content.content[:150] + "..." if len(content.content) > 150 else content.content
        tags_str = " ".join([f"#{tag}" for tag in content.tags[:5]]) if content.tags else ""
        
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📋 新内容待审核"},
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**标题:** {content.title}\n\n**预览:** {content_preview}\n\n**标签:** {tags_str}"
                    }
                },
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": "⚠️ Webhook 机器人不支持交互按钮，请前往 Web 控制台审核"}
                    ]
                }
            ]
        }
    
    def send_notification(self, title: str, message: str, template: str = "blue"):
        """发送通知消息"""
        if not self.enabled:
            return False
        
        try:
            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": template
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": message}
                    }
                ]
            }
            
            response = requests.post(
                self.webhook_url,
                json={"msg_type": "interactive", "card": card},
                timeout=10
            )
            return response.json().get('code') == 0
        except Exception as e:
            logger.error(f"发送通知异常: {e}")
            return False
