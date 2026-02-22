"""
内容生成调度器
只负责定时生成内容，不自动发布
"""

import os
import sys
import time
import json
import yaml
import schedule
from pathlib import Path
from datetime import datetime

from search_engine import SearchEngine
from content_generator import DeepSeekContentGenerator
from image_generator import ImageGenerator

# 配置路径
CONFIG_FILE = Path('/app/config/config.yaml')
DATA_DIR = Path('/app/data')
LOG_FILE = Path('/app/logs/scheduler.log')

def log(msg):
    """写入日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{timestamp}] {msg}'
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def load_config():
    """加载配置"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}

def generate_content():
    """
    生成内容任务
    搜索关键词 -> AI生成文案 -> 生成图片 -> 存入待审核队列
    """
    try:
        log('[INFO] 开始生成内容')
        config = load_config()
        
        # 初始化组件
        search = SearchEngine(config.get('search', {}))
        generator = DeepSeekContentGenerator(config.get('deepseek', {}))
        image_gen = ImageGenerator(config.get('image', {}))
        
        keywords = config.get('xiaohongshu', {}).get('keywords', [])
        if not keywords:
            log('[WARN] 未配置关键词，跳过')
            return
        
        # 搜索
        log(f'[INFO] 搜索关键词: {keywords}')
        results = search.search_multiple_keywords(keywords)
        
        # 生成内容
        contents = generator.generate_batch(
            results,
            config.get('xiaohongshu', {}).get('content_style', 'casual'),
            config.get('xiaohongshu', {}).get('target_audience', '25-35岁职场人士')
        )
        
        # 生成图片并保存到队列
        queue_file = DATA_DIR / 'queue.json'
        queue = []
        if queue_file.exists():
            with open(queue_file, 'r', encoding='utf-8') as f:
                queue = json.load(f)
        
        for content in contents:
            try:
                images = image_gen.generate(
                    content.title, content.content, content.tags,
                    content.keywords[0] if content.keywords else 'AI'
                )
                
                task = {
                    'id': f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(queue)}",
                    'title': content.title,
                    'content': content.content,
                    'tags': content.tags,
                    'images': [img.local_path for img in images],
                    'status': 'pending',
                    'created_at': datetime.now().isoformat(),
                    'author': 'AI助手'
                }
                queue.append(task)
                log(f'[SUCCESS] 生成: {content.title[:30]}...')
            except Exception as e:
                log(f'[ERROR] 生成图片失败: {e}')
        
        # 保存队列
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        with open(queue_file, 'w', encoding='utf-8') as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        
        log(f'[SUCCESS] 完成，生成 {len(contents)} 条内容待审核')
        
    except Exception as e:
        log(f'[ERROR] 生成失败: {e}')

def main():
    """主函数 - 只生成内容，不自动发布"""
    log('[INFO] 生成调度器启动')
    
    config = load_config()
    schedule_times = config.get('scheduler', {}).get('generate_times', ['09:00', '14:00', '19:00'])
    
    # 配置定时生成任务
    for t in schedule_times:
        schedule.every().day.at(t).do(generate_content)
        log(f'[INFO] 定时生成: {t}')
    
    log('[INFO] 等待定时生成任务...')
    
    # 运行循环
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    main()
