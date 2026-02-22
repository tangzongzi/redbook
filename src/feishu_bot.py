#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书机器人交互式审核模块
通过卡片消息直接在聊天窗口完成审核
"""
import json
import os
import logging
import requests
from typing import Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class FeishuInteractiveBot:
    """飞书交互式机器人"""
    
    def __init__(self):
        self.webhook_url = os.getenv('FEISHU_WEBHOOK_URL', '')
        self.app_id = os.getenv('FEISHU_APP_ID', '')
        self.app_secret = os.getenv('FEISHU_APP_SECRET', '')
        self.enabled = bool(self.webhook_url)
        
        # 审核回调函数
        self.approve_callback: Optional[Callable] = None
        self.reject_callback: Optional[Callable] = None
        
        # 存储 pending 的内容 {message_id: content_data}
        self.pending_contents = {}
    
    def send_content_for_approval(self, content_item) -> Optional[str]:
        """
        发送内容审核卡片到飞书
        
        Args:
            content_item: 内容项对象
            
        Returns:
            message_id: 消息ID，用于后续更新
        """
        if not self.enabled:
            logger.warning("飞书 Webhook 未配置")
            return None
        
        try:
            # 构建卡片内容
            card = self._build_approval_card(content_item)
            
            # 发送消息
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
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') == 0:
                # 保存内容数据
                self.pending_contents[content_item.id] = {
                    'item': content_item,
                    'sent_at': datetime.now()
                }
                logger.info(f"审核卡片已发送: {content_item.id}")
                return content_item.id
            else:
                logger.error(f"发送审核卡片失败: {result}")
                return None
                
        except Exception as e:
            logger.error(f"发送审核卡片异常: {e}")
            return None
    
    def _build_approval_card(self, content_item) -> dict:
        """构建审核卡片"""
        
        # 截断内容用于预览
        content_preview = content_item.content[:150] + "..." if len(content_item.content) > 150 else content_item.content
        
        # 标签字符串
        tags_str = " ".join(content_item.tags) if content_item.tags else "无标签"
        
        card = {
            "config": {
                "wide_screen_mode": True,
                "enable_forward": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📱 新内容待审核"
                },
                "subtitle": {
                    "tag": "plain_text",
                    "content": f"关键词: {', '.join(content_item.keywords) if hasattr(content_item, 'keywords') and content_item.keywords else 'AI生成'}"
                },
                "template": "blue"
            },
            "elements": [
                # 标题
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**标题：**\n{content_item.title}"
                    }
                },
                {
                    "tag": "hr"  # 分隔线
                },
                # 内容预览
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**正文预览：**\n{content_preview}"
                    }
                },
                # 标签
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**标签：** {tags_str}"
                    }
                },
                {
                    "tag": "hr"
                },
                # 操作按钮
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 通过并发布"
                            },
                            "type": "primary",
                            "value": {
                                "action": "approve",
                                "content_id": content_item.id
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
                                "content_id": content_item.id
                            }
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "👁️ 查看完整内容"
                            },
                            "type": "default",
                            "value": {
                                "action": "view",
                                "content_id": content_item.id
                            }
                        }
                    ]
                },
                # 提示信息
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "💡 点击「通过」后立即发布到小红书，点击「不通过」则删除此内容"
                        }
                    ]
                }
            ]
        }
        
        return card
    
    def update_card_to_published(self, message_id: str, note_id: str, share_url: str):
        """
        更新卡片为已发布状态
        
        Args:
            message_id: 消息ID
            note_id: 小红书笔记ID
            share_url: 分享链接
        """
        if not self.enabled:
            return
        
        try:
            # 注意：Webhook 机器人无法更新已发送的消息
            # 需要发送一条新消息作为通知
            self.send_publish_success_notification(message_id, note_id, share_url)
            
        except Exception as e:
            logger.error(f"更新卡片状态异常: {e}")
    
    def send_publish_success_notification(self, content_id: str, note_id: str, share_url: str):
        """发送发布成功通知"""
        if not self.enabled:
            return
        
        try:
            # 获取原始内容
            pending_data = self.pending_contents.get(content_id)
            if not pending_data:
                title = "内容"
            else:
                title = pending_data['item'].title
            
            message = {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": "✅ 内容发布成功"
                        },
                        "template": "green"
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": f"**{title}**\n已成功发布到小红书"
                            }
                        },
                        {
                            "tag": "action",
                            "actions": [
                                {
                                    "tag": "button",
                                    "text": {
                                        "tag": "plain_text",
                                        "content": "🔗 查看笔记"
                                    },
                                    "type": "primary",
                                    "url": share_url
                                },
                                {
                                    "tag": "button",
                                    "text": {
                                        "tag": "plain_text",
                                        "content": "📋 复制链接"
                                    },
                                    "type": "default",
                                    "value": {
                                        "action": "copy",
                                        "url": share_url
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
            
            requests.post(
                self.webhook_url,
                json=message,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            # 从 pending 中移除
            if content_id in self.pending_contents:
                del self.pending_contents[content_id]
                
        except Exception as e:
            logger.error(f"发送成功通知异常: {e}")
    
    def send_reject_notification(self, content_id: str):
        """发送拒绝通知"""
        if not self.enabled:
            return
        
        try:
            pending_data = self.pending_contents.get(content_id)
            if pending_data:
                title = pending_data['item'].title
                del self.pending_contents[content_id]
            else:
                title = "内容"
            
            message = {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": "❌ 内容已拒绝"
                        },
                        "template": "grey"
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": f"**{title}**\n已被拒绝，不会发布"
                            }
                        }
                    ]
                }
            }
            
            requests.post(
                self.webhook_url,
                json=message,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
        except Exception as e:
            logger.error(f"发送拒绝通知异常: {e}")


class FeishuEventHandler:
    """
    飞书事件处理器（用于自定义机器人回调）
    
    注意：Webhook 机器人不支持事件回调，需要使用「自定义机器人」+ 服务器接收事件
    如果只有 Webhook，需要通过其他方式获取用户点击（如 Web UI 展示卡片状态）
    """
    
    def __init__(self):
        self.verify_token = os.getenv('FEISHU_VERIFY_TOKEN', '')
        self.encrypt_key = os.getenv('FEISHU_ENCRYPT_KEY', '')
    
    def handle_event(self, event_data: dict) -> dict:
        """
        处理飞书事件
        
        Args:
            event_data: 飞书推送的事件数据
            
        Returns:
            响应数据
        """
        event_type = event_data.get('header', {}).get('event_type')
        
        if event_type == 'im.message.receive_v1':
            return self._handle_message(event_data)
        elif event_type == 'card.action.trigger':
            return self._handle_card_action(event_data)
        
        return {}
    
    def _handle_message(self, event_data: dict) -> dict:
        """处理消息事件"""
        # 可以在这里处理用户发送的命令
        message = event_data.get('event', {}).get('message', {})
        content = json.loads(message.get('content', '{}'))
        text = content.get('text', '')
        
        # 简单的命令处理
        if '列表' in text or 'list' in text.lower():
            return self._send_text_response("当前没有待审核内容")
        
        return {}
    
    def _handle_card_action(self, event_data: dict) -> dict:
        """处理卡片按钮点击事件"""
        action = event_data.get('event', {}).get('action', {})
        action_value = action.get('value', {})
        
        action_type = action_value.get('action')
        content_id = action_value.get('content_id')
        
        if action_type == 'approve':
            # 触发通过回调
            return self._handle_approve(content_id)
        elif action_type == 'reject':
            # 触发拒绝回调
            return self._handle_reject(content_id)
        elif action_type == 'view':
            # 查看完整内容
            return self._handle_view(content_id)
        
        return {}
    
    def _handle_approve(self, content_id: str) -> dict:
        """处理通过操作"""
        # 这里调用发布逻辑
        logger.info(f"用户点击通过: {content_id}")
        
        # 返回响应给飞书，更新卡片
        return {
            "toast": {
                "type": "success",
                "content": "正在发布到小红书..."
            }
        }
    
    def _handle_reject(self, content_id: str) -> dict:
        """处理拒绝操作"""
        logger.info(f"用户点击拒绝: {content_id}")
        
        return {
            "toast": {
                "type": "info",
                "content": "已拒绝此内容"
            }
        }
    
    def _handle_view(self, content_id: str) -> dict:
        """处理查看操作"""
        # 可以返回一个包含完整内容的卡片
        return {
            "toast": {
                "type": "info",
                "content": "请在 Web UI 中查看完整内容"
            }
        }
    
    def _send_text_response(self, text: str) -> dict:
        """发送文本响应"""
        return {
            "content": json.dumps({
                "text": text
            }),
            "msg_type": "text"
        }


# 便捷函数
def get_feishu_bot() -> FeishuInteractiveBot:
    """获取飞书机器人实例"""
    return FeishuInteractiveBot()
