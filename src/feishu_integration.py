#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书多维表格集成模块
用于内容审核和管理
"""
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import asdict

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *

from content_generator import ContentItem

logger = logging.getLogger(__name__)


class FeishuBitableClient:
    """飞书多维表格客户端"""
    
    def __init__(self):
        self.app_id = os.getenv('FEISHU_APP_ID', '')
        self.app_secret = os.getenv('FEISHU_APP_SECRET', '')
        self.app_token = os.getenv('FEISHU_BITABLE_APP_TOKEN', '')
        self.table_id = os.getenv('FEISHU_BITABLE_TABLE_ID', '')
        
        if not all([self.app_id, self.app_secret, self.app_token, self.table_id]):
            logger.warning("飞书配置不完整，将使用本地存储模式")
            self.enabled = False
            self.client = None
        else:
            self.enabled = True
            self.client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .log_level(lark.LogLevel.ERROR) \
                .build()
    
    def add_record(self, item: ContentItem) -> Optional[str]:
        """
        添加记录到飞书多维表格
        
        Args:
            item: 内容项
            
        Returns:
            record_id: 飞书记录ID
        """
        if not self.enabled:
            logger.info("飞书未启用，跳过添加记录")
            return None
        
        try:
            # 构建字段数据
            fields = {
                "标题": item.title,
                "正文": item.content,
                "标签": ", ".join(item.tags),
                "摘要": item.summary,
                "关键词": ", ".join(item.keywords),
                "图片路径": ", ".join(item.image_paths) if item.image_paths else "",
                "状态": "待审核",
                "创建时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            
            # 创建请求
            request = CreateBitableRecordRequest.builder() \
                .app_token(self.app_token) \
                .table_id(self.table_id) \
                .request_body(CreateBitableRecordRequestBody.builder()
                    .fields(fields)
                    .build()
                ) \
                .build()
            
            # 发送请求
            response = self.client.bitable.v1.bitable_record.create(request)
            
            if response.success():
                record_id = response.data.record.record_id
                logger.info(f"成功添加飞书记录: {record_id}")
                return record_id
            else:
                logger.error(f"添加飞书记录失败: {response.msg}")
                return None
                
        except Exception as e:
            logger.error(f"添加飞书记录异常: {e}")
            return None
    
    def get_pending_records(self) -> List[Dict]:
        """
        获取待审核的记录
        
        Returns:
            待审核记录列表
        """
        if not self.enabled:
            return []
        
        try:
            # 构建筛选条件
            request = SearchBitableRecordRequest.builder() \
                .app_token(self.app_token) \
                .table_id(self.table_id) \
                .request_body(SearchBitableRecordRequestBody.builder()
                    .filter(json.dumps({
                        "conditions": [
                            {
                                "field_name": "状态",
                                "operator": "is",
                                "value": ["已通过"]
                            }
                        ]
                    }))
                    .build()
                ) \
                .build()
            
            response = self.client.bitable.v1.bitable_record.search(request)
            
            if response.success():
                records = []
                for record in response.data.items:
                    records.append({
                        'record_id': record.record_id,
                        'fields': record.fields
                    })
                return records
            else:
                logger.error(f"查询飞书记录失败: {response.msg}")
                return []
                
        except Exception as e:
            logger.error(f"查询飞书记录异常: {e}")
            return []
    
    def update_record_status(self, record_id: str, status: str, note_id: str = None, share_url: str = None) -> bool:
        """
        更新记录状态
        
        Args:
            record_id: 飞书记录ID
            status: 新状态（已发布/发布失败）
            note_id: 小红书笔记ID
            share_url: 分享链接
            
        Returns:
            是否成功
        """
        if not self.enabled:
            return False
        
        try:
            fields = {
                "状态": status,
                "发布时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            if note_id:
                fields["笔记ID"] = note_id
            if share_url:
                fields["分享链接"] = share_url
            
            request = UpdateBitableRecordRequest.builder() \
                .app_token(self.app_token) \
                .table_id(self.table_id) \
                .record_id(record_id) \
                .request_body(UpdateBitableRecordRequestBody.builder()
                    .fields(fields)
                    .build()
                ) \
                .build()
            
            response = self.client.bitable.v1.bitable_record.update(request)
            
            if response.success():
                logger.info(f"成功更新飞书记录状态: {record_id} -> {status}")
                return True
            else:
                logger.error(f"更新飞书记录失败: {response.msg}")
                return False
                
        except Exception as e:
            logger.error(f"更新飞书记录异常: {e}")
            return False


class FeishuWebhookNotifier:
    """飞书群机器人通知"""
    
    def __init__(self):
        self.webhook_url = os.getenv('FEISHU_WEBHOOK_URL', '')
        self.enabled = bool(self.webhook_url)
    
    def send_content_generated(self, title: str, summary: str):
        """发送内容生成通知"""
        if not self.enabled:
            return
        
        import requests
        
        message = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📱 新内容待审核"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**标题：**{title}\n\n**摘要：**{summary}"
                        }
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {
                                    "tag": "plain_text",
                                    "content": "去审核"
                                },
                                "type": "primary",
                                "url": "https://feishu.cn"  # 替换为实际表格链接
                            }
                        ]
                    }
                ]
            }
        }
        
        try:
            response = requests.post(self.webhook_url, json=message, timeout=10)
            response.raise_for_status()
            logger.info("飞书通知发送成功")
        except Exception as e:
            logger.error(f"飞书通知发送失败: {e}")
    
    def send_publish_success(self, title: str, share_url: str):
        """发送发布成功通知"""
        if not self.enabled:
            return
        
        import requests
        
        message = {
            "msg_type": "interactive",
            "card": {
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
                            "content": f"**标题：**{title}"
                        }
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {
                                    "tag": "plain_text",
                                    "content": "查看笔记"
                                },
                                "type": "primary",
                                "url": share_url
                            }
                        ]
                    }
                ]
            }
        }
        
        try:
            response = requests.post(self.webhook_url, json=message, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"飞书通知发送失败: {e}")


def get_feishu_client() -> FeishuBitableClient:
    """获取飞书客户端实例"""
    return FeishuBitableClient()


def get_feishu_notifier() -> FeishuWebhookNotifier:
    """获取飞书通知器实例"""
    return FeishuWebhookNotifier()
