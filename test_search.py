#!/usr/bin/env python3
"""
搜索功能测试脚本
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import yaml
from search_engine import SearchEngine

def test_search():
    """测试搜索功能"""
    print("=" * 60)
    print("搜索功能测试")
    print("=" * 60)
    
    # 加载配置
    config_file = Path(__file__).parent / 'config' / 'config.yaml'
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 初始化搜索引擎
    search_config = config.get('search', {})
    print(f"\n搜索源: {search_config.get('source', 'duckduckgo')}")
    print(f"搜索配置: {search_config}")
    
    searcher = SearchEngine(search_config)
    
    # 测试关键词
    test_keywords = [
        'AI人工智能',
        '小红书运营技巧',
        '2024年科技趋势'
    ]
    
    for keyword in test_keywords:
        print(f"\n{'=' * 60}")
        print(f"搜索关键词: {keyword}")
        print(f"{'=' * 60}")
        
        try:
            results = searcher.search(keyword)
            print(f"\n✓ 搜索到 {len(results)} 条结果")
            
            if results:
                print("\n前3条结果:")
                for i, r in enumerate(results[:3], 1):
                    print(f"\n{i}. {r.title}")
                    print(f"   URL: {r.url}")
                    print(f"   摘要: {r.snippet[:100]}...")
            else:
                print("\n⚠ 搜索无结果")
                
        except Exception as e:
            print(f"\n✗ 搜索失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_search()
