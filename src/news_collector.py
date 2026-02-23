#!/usr/bin/env python3
"""
资讯收集器 - 自动搜索、收集和整理资讯
支持多种搜索源，定时收集，自动去重
"""

import os
import sys
import time
import json
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict
import yaml

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from simple_search import SimpleSearchEngine, SearchResult

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / 'logs' / 'news_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """资讯条目"""
    id: str
    title: str
    url: str
    snippet: str
    source: str
    keyword: str
    collected_at: str
    published_date: Optional[str] = None
    read_count: int = 0
    is_used: bool = False
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'NewsItem':
        return cls(**data)


class NewsCollector:
    """资讯收集器"""
    
    def __init__(self, config_file: Optional[Path] = None):
        """初始化收集器"""
        if config_file is None:
            config_file = Path(__file__).parent.parent / 'config' / 'config.yaml'
        
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 数据目录
        self.data_dir = Path(__file__).parent.parent / 'data'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 资讯存储文件
        self.news_file = self.data_dir / 'collected_news.json'
        
        # 已收集的 URL 集合（用于去重）
        self.seen_urls: Set[str] = set()
        self.seen_hashes: Set[str] = set()
        
        # 加载已有数据
        self.news_list: List[NewsItem] = []
        self._load_news()
        
        # 初始化搜索引擎
        search_config = self.config.get('search', {})
        self.searcher = SimpleSearchEngine(search_config)
        
        # 收集配置
        self.collector_config = self.config.get('news_collector', {})
        self.keywords = self.collector_config.get('keywords', [])
        self.collect_interval = self.collector_config.get('collect_interval', 3600)  # 1小时
        self.max_news_per_keyword = self.collector_config.get('max_news_per_keyword', 20)
        self.max_total_news = self.collector_config.get('max_total_news', 200)
    
    def _load_news(self):
        """加载已收集的资讯"""
        if self.news_file.exists():
            try:
                with open(self.news_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.news_list = [NewsItem.from_dict(item) for item in data]
                    
                    # 构建去重集合
                    for news in self.news_list:
                        self.seen_urls.add(news.url)
                        self.seen_hashes.add(self._hash_content(news.title + news.snippet))
                
                logger.info(f"已加载 {len(self.news_list)} 条资讯")
            except Exception as e:
                logger.error(f"加载资讯失败: {e}")
                self.news_list = []
    
    def _save_news(self):
        """保存资讯到文件"""
        try:
            # 按时间排序，最新的在前
            self.news_list.sort(key=lambda x: x.collected_at, reverse=True)
            
            # 限制总数
            if len(self.news_list) > self.max_total_news:
                self.news_list = self.news_list[:self.max_total_news]
            
            with open(self.news_file, 'w', encoding='utf-8') as f:
                json.dump([news.to_dict() for news in self.news_list], f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存 {len(self.news_list)} 条资讯")
        except Exception as e:
            logger.error(f"保存资讯失败: {e}")
    
    def _hash_content(self, content: str) -> str:
        """生成内容哈希用于去重"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _is_duplicate(self, result: SearchResult) -> bool:
        """检查是否重复"""
        if result.url and result.url in self.seen_urls:
            return True
        
        content_hash = self._hash_content(result.title + result.snippet)
        if content_hash in self.seen_hashes:
            return True
        
        return False
    
    def collect_for_keyword(self, keyword: str) -> List[NewsItem]:
        """为单个关键词收集资讯"""
        logger.info(f"开始收集关键词: {keyword}")
        
        collected: List[NewsItem] = []
        
        try:
            results = self.searcher.search(keyword)
            logger.info(f"关键词 '{keyword}' 搜索到 {len(results)} 条结果")
            
            for result in results:
                if self._is_duplicate(result):
                    continue
                
                news = NewsItem(
                    id=f"news_{int(time.time())}_{len(collected)}",
                    title=result.title,
                    url=result.url,
                    snippet=result.snippet,
                    source=result.source,
                    keyword=keyword,
                    collected_at=datetime.now().isoformat(),
                    published_date=result.published_date
                )
                
                self.news_list.append(news)
                self.seen_urls.add(news.url)
                self.seen_hashes.add(self._hash_content(news.title + news.snippet))
                collected.append(news)
                
                logger.debug(f"收集到: {news.title[:50]}...")
                
                # 限制每个关键词的数量
                if len(collected) >= self.max_news_per_keyword:
                    break
            
        except Exception as e:
            logger.error(f"收集关键词 '{keyword}' 失败: {e}")
        
        logger.info(f"关键词 '{keyword}' 收集了 {len(collected)} 条新资讯")
        return collected
    
    def collect_all(self) -> int:
        """收集所有关键词的资讯"""
        logger.info("=" * 60)
        logger.info("开始收集资讯")
        logger.info("=" * 60)
        
        total_collected = 0
        
        if not self.keywords:
            logger.warning("没有配置关键词，使用默认关键词")
            self.keywords = ['AI人工智能', '科技趋势', '小红书运营']
        
        for keyword in self.keywords:
            collected = self.collect_for_keyword(keyword)
            total_collected += len(collected)
        
        # 保存结果
        self._save_news()
        
        logger.info("=" * 60)
        logger.info(f"资讯收集完成，共收集 {total_collected} 条新资讯")
        logger.info(f"当前总共有 {len(self.news_list)} 条资讯")
        logger.info("=" * 60)
        
        return total_collected
    
    def get_unused_news(self, keyword: Optional[str] = None, limit: int = 10) -> List[NewsItem]:
        """获取未使用的资讯"""
        news = [n for n in self.news_list if not n.is_used]
        
        if keyword:
            news = [n for n in news if n.keyword == keyword]
        
        # 按读取次数排序（最少的优先）
        news.sort(key=lambda x: x.read_count)
        
        return news[:limit]
    
    def mark_as_used(self, news_id: str):
        """标记资讯为已使用"""
        for news in self.news_list:
            if news.id == news_id:
                news.is_used = True
                self._save_news()
                logger.info(f"标记资讯已使用: {news_id}")
                return
        
        logger.warning(f"未找到资讯: {news_id}")
    
    def increment_read_count(self, news_id: str):
        """增加读取次数"""
        for news in self.news_list:
            if news.id == news_id:
                news.read_count += 1
                self._save_news()
                return
    
    def run_forever(self):
        """持续运行，定时收集"""
        logger.info(f"资讯收集器已启动，收集间隔: {self.collect_interval} 秒")
        
        while True:
            try:
                self.collect_all()
            except Exception as e:
                logger.error(f"收集过程出错: {e}")
            
            logger.info(f"等待 {self.collect_interval} 秒后再次收集...")
            time.sleep(self.collect_interval)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='资讯收集器')
    parser.add_argument('--once', action='store_true', help='仅收集一次然后退出')
    parser.add_argument('--keywords', nargs='+', help='指定关键词收集')
    parser.add_argument('--list', action='store_true', help='列出已收集的资讯')
    parser.add_argument('--config', help='配置文件路径')
    
    args = parser.parse_args()
    
    collector = NewsCollector(Path(args.config) if args.config else None)
    
    if args.list:
        # 列出资讯
        print("=" * 80)
        print(f"已收集的资讯 ({len(collector.news_list)} 条)")
        print("=" * 80)
        for i, news in enumerate(collector.news_list[:20], 1):
            status = "[已用]" if news.is_used else "[未用]"
            print(f"\n{i}. {status} [{news.keyword}] {news.title}")
            print(f"   来源: {news.source} | 收集时间: {news.collected_at[:19]}")
            print(f"   摘要: {news.snippet[:80]}...")
        if len(collector.news_list) > 20:
            print(f"\n... 还有 {len(collector.news_list) - 20} 条")
        return
    
    if args.keywords:
        # 收集指定关键词
        collector.keywords = args.keywords
        collector.collect_all()
        return
    
    if args.once:
        # 收集一次
        collector.collect_all()
        return
    
    # 持续运行
    collector.run_forever()


if __name__ == "__main__":
    main()
