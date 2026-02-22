"""
DeepSeek AI 内容生成模块
基于搜索内容生成小红书风格的文案
"""

import os
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


@dataclass
class XiaohongshuContent:
    """小红书内容数据结构"""
    title: str
    content: str
    tags: List[str]
    summary: str  # 内容摘要，用于飞书展示
    keywords: List[str]  # 使用的关键词


class DeepSeekContentGenerator:
    """基于 DeepSeek API 的小红书内容生成器"""
    
    # 小红书文案风格模板
    STYLE_TEMPLATES = {
        'professional': """专业严谨的科技风格，用词精准，逻辑清晰，适合分享深度技术内容。""",
        'casual': """轻松随意的日常分享风格，用词口语化，像朋友聊天一样，适合生活化内容。""",
        'humorous': """幽默风趣的风格，适当使用网络热梗和表情，让人会心一笑。""",
        'story': """故事叙述风格，有开头、发展、高潮、结尾，引人入胜。"""
    }
    
    def __init__(self, config: Dict):
        self.config = config
        self.api_key = config.get('api_key') or os.getenv('DEEPSEEK_API_KEY')
        self.base_url = config.get('base_url', 'https://api.deepseek.com/v1')
        self.model = config.get('model', 'deepseek-chat')
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 2000)
        
        if not self.api_key:
            raise ValueError("DeepSeek API Key 未配置")
        
        # 初始化 DeepSeek 客户端（兼容 OpenAI 格式）
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        logger.info(f"DeepSeek 生成器初始化完成，模型: {self.model}")
    
    def generate(self, 
                 search_results: List[Dict], 
                 keyword: str,
                 content_style: str = 'casual',
                 target_audience: str = '25-35岁职场人士') -> XiaohongshuContent:
        """
        基于搜索结果生成小红书内容
        
        Args:
            search_results: 搜索结果列表
            keyword: 核心关键词
            content_style: 内容风格
            target_audience: 目标受众描述
            
        Returns:
            XiaohongshuContent: 生成的小红书内容
        """
        # 构建参考信息
        reference_info = self._build_reference(search_results)
        
        # 构建系统提示词
        system_prompt = self._build_system_prompt(content_style, target_audience)
        
        # 构建用户提示词
        user_prompt = f"""
请基于以下信息，创作一篇关于「{keyword}」的小红书笔记。

=== 参考信息 ===
{reference_info}

=== 创作要求 ===
1. 标题要吸睛，使用 emoji，控制在 20 字以内
2. 正文结构清晰，使用 emoji 分段，控制在 300-800 字
3. 语言风格：{self.STYLE_TEMPLATES.get(content_style, self.STYLE_TEMPLATES['casual'])}
4. 目标受众：{target_audience}
5. 结尾要有互动引导（点赞/收藏/评论/关注）
6. 生成 5-8 个相关标签（带 # 号）

请以 JSON 格式输出：
{{
    "title": "笔记标题",
    "content": "正文内容",
    "tags": ["标签1", "标签2", ...],
    "summary": "内容一句话摘要"
}}
"""
        
        try:
            logger.info(f"开始生成内容，关键词: {keyword}")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            # 解析响应
            result_text = response.choices[0].message.content
            result_json = json.loads(result_text)
            
            content = XiaohongshuContent(
                title=result_json.get('title', ''),
                content=result_json.get('content', ''),
                tags=result_json.get('tags', []),
                summary=result_json.get('summary', ''),
                keywords=[keyword]
            )
            
            logger.info(f"内容生成成功: {content.title[:30]}...")
            return content
            
        except Exception as e:
            logger.error(f"内容生成失败: {e}")
            raise
    
    def _build_reference(self, search_results: List[Dict]) -> str:
        """构建参考信息文本"""
        if not search_results:
            return "无搜索结果，请基于通用知识创作。"
        
        references = []
        for i, result in enumerate(search_results[:5], 1):
            title = result.get('title', '')
            snippet = result.get('snippet', '') or result.get('content', '')[:200]
            references.append(f"[{i}] {title}\n    {snippet}")
        
        return '\n\n'.join(references)
    
    def _build_system_prompt(self, content_style: str, target_audience: str) -> str:
        """构建系统提示词"""
        return f"""你是一位专业的小红书内容创作者，擅长将信息转化为吸引眼球的社交媒体内容。

你的创作原则：
1. 标题党但不做作，让人一眼就想点开
2. 内容有价值，读完有收获感
3. 语言生动活泼，避免生硬广告感
4. 善用 emoji 和排版，提升阅读体验
5. 符合小红书社区规范，不涉及敏感内容

风格定位：{self.STYLE_TEMPLATES.get(content_style, self.STYLE_TEMPLATES['casual'])}
目标受众：{target_audience}

输出必须是合法的 JSON 格式。"""
    
    def generate_batch(self,
                      keyword_results: Dict[str, List[Dict]],
                      content_style: str = 'casual',
                      target_audience: str = '25-35岁职场人士') -> List[XiaohongshuContent]:
        """
        批量生成多个关键词的内容
        
        Args:
            keyword_results: 关键词到搜索结果的映射
            content_style: 内容风格
            target_audience: 目标受众
            
        Returns:
            List[XiaohongshuContent]: 内容列表
        """
        contents = []
        
        for keyword, results in keyword_results.items():
            try:
                content = self.generate(results, keyword, content_style, target_audience)
                contents.append(content)
            except Exception as e:
                logger.error(f"生成关键词 '{keyword}' 的内容失败: {e}")
                continue
        
        return contents
    
    def optimize_content(self, content: XiaohongshuContent, feedback: str) -> XiaohongshuContent:
        """
        根据反馈优化内容
        
        Args:
            content: 原始内容
            feedback: 优化建议
            
        Returns:
            XiaohongshuContent: 优化后的内容
        """
        user_prompt = f"""
请根据以下反馈优化小红书笔记：

=== 原标题 ===
{content.title}

=== 原正文 ===
{content.content}

=== 反馈建议 ===
{feedback}

请以 JSON 格式输出优化后的内容：
{{
    "title": "优化后的标题",
    "content": "优化后的正文",
    "tags": ["标签1", "标签2", ...],
    "summary": "内容摘要"
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            result_json = json.loads(response.choices[0].message.content)
            
            return XiaohongshuContent(
                title=result_json.get('title', content.title),
                content=result_json.get('content', content.content),
                tags=result_json.get('tags', content.tags),
                summary=result_json.get('summary', content.summary),
                keywords=content.keywords
            )
            
        except Exception as e:
            logger.error(f"内容优化失败: {e}")
            return content


if __name__ == "__main__":
    # 测试代码
    import yaml
    from dotenv import load_dotenv
    
    load_dotenv()
    
    with open('../config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 初始化生成器
    generator = DeepSeekContentGenerator(config['deepseek'])
    
    # 模拟搜索结果
    mock_results = [
        {
            'title': '2024年AI发展趋势报告',
            'snippet': '人工智能技术正在快速发展，大语言模型、多模态AI等成为热门方向...',
            'url': 'https://example.com/ai-trends'
        },
        {
            'title': 'ChatGPT新功能发布',
            'snippet': 'OpenAI发布了ChatGPT的最新功能，包括代码解释器、插件支持等...',
            'url': 'https://example.com/chatgpt'
        }
    ]
    
    # 生成内容
    content = generator.generate(
        search_results=mock_results,
        keyword='AI人工智能',
        content_style='casual'
    )
    
    print("\n=== 生成的小红书内容 ===")
    print(f"\n标题: {content.title}")
    print(f"\n正文:\n{content.content}")
    print(f"\n标签: {' '.join(content.tags)}")
    print(f"\n摘要: {content.summary}")
