"""
关键词搜索模块
支持多种搜索源：DuckDuckGo(免费)、Bing API、Serper API
"""

import requests
import json
from typing import List, Dict, Optional
from duckduckgo_search import DDGS
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    snippet: str
    source: str
    published_date: Optional[str] = None


class SearchEngine:
    """搜索引擎封装类"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.source = config.get('source', 'duckduckgo')
        self.max_results = config.get('max_results', 5)
        self.time_range = config.get('time_range', 'week')
        
        # API Keys
        self.serper_api_key = config.get('serper_api_key', '')
        self.bing_api_key = config.get('bing_api_key', '')
    
    def search(self, keyword: str) -> List[SearchResult]:
        """
        根据配置执行搜索
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        logger.info(f"使用 {self.source} 搜索关键词: {keyword}")
        
        if self.source == 'duckduckgo':
            return self._search_duckduckgo(keyword)
        elif self.source == 'serper':
            return self._search_serper(keyword)
        elif self.source == 'bing':
            return self._search_bing(keyword)
        else:
            raise ValueError(f"不支持的搜索源: {self.source}")
    
    def _search_duckduckgo(self, keyword: str) -> List[SearchResult]:
        """使用 DuckDuckGo 搜索（免费，无需API Key）"""
        results = []
        
        try:
            with DDGS() as ddgs:
                # 获取网页搜索结果
                ddg_results = ddgs.text(
                    keyword,
                    max_results=self.max_results,
                    timelimit=self.time_range
                )
                
                for r in ddg_results:
                    results.append(SearchResult(
                        title=r.get('title', ''),
                        url=r.get('href', ''),
                        snippet=r.get('body', ''),
                        source='duckduckgo'
                    ))
                    
        except Exception as e:
            logger.error(f"DuckDuckGo 搜索失败: {e}")
            
        return results
    
    def _search_serper(self, keyword: str) -> List[SearchResult]:
        """使用 Serper API 搜索（Google 搜索结果）"""
        results = []
        
        if not self.serper_api_key:
            logger.warning("Serper API Key 未配置，跳过")
            return results
        
        url = "https://google.serper.dev/search"
        headers = {
            'X-API-KEY': self.serper_api_key,
            'Content-Type': 'application/json'
        }
        payload = {
            'q': keyword,
            'num': self.max_results,
            'tbs': f'qdr:{self.time_range[0]}'  # 时间范围
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get('organic', []):
                results.append(SearchResult(
                    title=item.get('title', ''),
                    url=item.get('link', ''),
                    snippet=item.get('snippet', ''),
                    source='serper',
                    published_date=item.get('date')
                ))
                
        except Exception as e:
            logger.error(f"Serper 搜索失败: {e}")
            
        return results
    
    def _search_bing(self, keyword: str) -> List[SearchResult]:
        """使用 Bing API 搜索"""
        results = []
        
        if not self.bing_api_key:
            logger.warning("Bing API Key 未配置，跳过")
            return results
        
        endpoint = "https://api.bing.microsoft.com/v7.0/search"
        headers = {'Ocp-Apim-Subscription-Key': self.bing_api_key}
        params = {
            'q': keyword,
            'count': self.max_results,
            'freshness': self.time_range
        }
        
        try:
            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get('webPages', {}).get('value', []):
                results.append(SearchResult(
                    title=item.get('name', ''),
                    url=item.get('url', ''),
                    snippet=item.get('snippet', ''),
                    source='bing',
                    published_date=item.get('dateLastCrawled')
                ))
                
        except Exception as e:
            logger.error(f"Bing 搜索失败: {e}")
            
        return results
    
    def search_multiple_keywords(self, keywords: List[str]) -> Dict[str, List[SearchResult]]:
        """
        批量搜索多个关键词
        
        Args:
            keywords: 关键词列表
            
        Returns:
            Dict[str, List[SearchResult]]: 关键词到结果的映射
        """
        all_results = {}
        
        for keyword in keywords:
            results = self.search(keyword)
            all_results[keyword] = results
            logger.info(f"关键词 '{keyword}' 找到 {len(results)} 条结果")
            
        return all_results


class ContentExtractor:
    """网页内容提取器"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def extract(self, url: str) -> Optional[str]:
        """
        提取网页正文内容
        
        Args:
            url: 网页 URL
            
        Returns:
            str: 提取的正文内容
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # 使用简单的文本提取（实际项目中可以使用 trafilatura 等库）
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 移除脚本和样式
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # 获取文本
            text = soup.get_text(separator='\n', strip=True)
            
            # 清理文本
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines[:50])  # 只取前50行
            
            return text[:5000]  # 限制长度
            
        except Exception as e:
            logger.error(f"提取网页内容失败 {url}: {e}")
            return None


if __name__ == "__main__":
    # 测试代码
    import yaml
    
    with open('../config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 初始化搜索器
    search_engine = SearchEngine(config['search'])
    
    # 测试搜索
    keywords = ["AI人工智能最新动态", "ChatGPT新功能"]
    results = search_engine.search_multiple_keywords(keywords)
    
    for keyword, items in results.items():
        print(f"\n=== 关键词: {keyword} ===")
        for i, item in enumerate(items[:3], 1):
            print(f"\n{i}. {item.title}")
            print(f"   URL: {item.url}")
            print(f"   摘要: {item.snippet[:100]}...")
