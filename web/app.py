"""
小红书自动发布系统 - Web API
半自动工作流：生成 → 审核 → 手动发布
支持飞书多维表格集成
"""
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

APP_DIR = Path(os.getenv('APP_DIR', '/app'))
DATA_DIR = APP_DIR / 'data'
CONFIG_DIR = APP_DIR / 'config'
LOGS_DIR = APP_DIR / 'logs'

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'web.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(APP_DIR / 'src'))

app = Flask(__name__)
CORS(app)

# 飞书表格集成
feishu_client = None
feishu_notifier = None
try:
    from feishu_integration import FeishuBitableClient, FeishuWebhookNotifier
    feishu_client = FeishuBitableClient()
    feishu_notifier = FeishuWebhookNotifier()
    logger.info(f"飞书表格集成: {'已启用' if feishu_client.enabled else '未启用'}")
except Exception as e:
    logger.warning(f"飞书表格集成加载失败: {e}")

# 飞书机器人（交互式审核）
feishu_bot = None
feishu_event_handler = None
feishu_approval_bot = None
try:
    from feishu_bot import FeishuInteractiveBot, FeishuEventHandler
    feishu_bot = FeishuInteractiveBot()
    feishu_event_handler = FeishuEventHandler()
    logger.info(f"飞书机器人: {'已启用' if feishu_bot.enabled else '未启用'}")
except Exception as e:
    logger.warning(f"飞书机器人加载失败: {e}")

try:
    from feishu_approval_bot import FeishuApprovalBot, FeishuWebhookHandler, ContentForApproval
    
    feishu_config = load_config().get('feishu', {})
    feishu_approval_bot = FeishuApprovalBot(
        app_id=feishu_config.get('app_id', ''),
        app_secret=feishu_config.get('app_secret', ''),
        verify_token=feishu_config.get('verify_token', ''),
        encrypt_key=feishu_config.get('encrypt_key', '')
    )
    
    def on_approve(content: ContentForApproval, result):
        queue = load_queue()
        item = next((q for q in queue if q['id'] == content.id), None)
        if item:
            item['status'] = 'approved'
            item['approved_at'] = result.timestamp
            item['approved_by'] = result.user_name
            save_queue(queue)
            log_action('FEISHU_APPROVE', f"ID: {content.id}, By: {result.user_name}")
    
    def on_reject(content: ContentForApproval, result):
        queue = load_queue()
        queue = [q for q in queue if q['id'] != content.id]
        save_queue(queue)
        log_action('FEISHU_REJECT', f"ID: {content.id}, By: {result.user_name}")
    
    feishu_approval_bot.set_callbacks(on_approve, on_reject)
    logger.info(f"飞书审核机器人: {'已启用' if feishu_approval_bot.enabled else '未启用'}")
except Exception as e:
    logger.warning(f"飞书审核机器人加载失败: {e}")

QUEUE_FILE = DATA_DIR / 'queue.json'
CONFIG_FILE = CONFIG_DIR / 'config.yaml'

mcp_publisher = None
_config_cache = {'data': None, 'timestamp': 0}
CONFIG_CACHE_TTL = 30

def load_config():
    """加载配置（带缓存）"""
    now = time.time()
    if _config_cache['data'] and (now - _config_cache['timestamp']) < CONFIG_CACHE_TTL:
        return _config_cache['data']
    
    try:
        import yaml
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
            _config_cache['data'] = config
            _config_cache['timestamp'] = now
            return config
    except Exception as e:
        logger.error(f"加载配置失败: {e}")
        return {}

def clear_config_cache():
    """清除配置缓存"""
    _config_cache['data'] = None
    _config_cache['timestamp'] = 0

AI_PROVIDERS = {
    'deepseek': {
        'name': 'DeepSeek',
        'base_url': 'https://api.deepseek.com/v1',
        'default_model': 'deepseek-chat',
        'env_key': 'DEEPSEEK_API_KEY'
    },
    'openai': {
        'name': 'OpenAI',
        'base_url': 'https://api.openai.com/v1',
        'default_model': 'gpt-4o',
        'env_key': 'OPENAI_API_KEY'
    },
    'anthropic': {
        'name': 'Anthropic',
        'base_url': 'https://api.anthropic.com/v1',
        'default_model': 'claude-sonnet-4-20250514',
        'env_key': 'ANTHROPIC_API_KEY'
    },
    'moonshot': {
        'name': '月之暗面',
        'base_url': 'https://api.moonshot.cn/v1',
        'default_model': 'kimi-k2-5',
        'env_key': 'MOONSHOT_API_KEY'
    },
    'zhipu': {
        'name': '智谱AI',
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'default_model': 'glm-4-flash',
        'env_key': 'ZHIPU_API_KEY'
    },
    'baidu': {
        'name': '百度',
        'base_url': 'https://qianfan.baidubce.com/v2',
        'default_model': 'ernie-4.0-8k',
        'env_key': 'BAIDU_API_KEY'
    },
    'ali': {
        'name': '阿里云',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'default_model': 'qwen-plus',
        'env_key': 'ALI_API_KEY'
    },
    'tencent': {
        'name': '腾讯',
        'base_url': 'https://hunyuan.tencentcloudapi.com',
        'default_model': 'hunyuan-standard',
        'env_key': 'TENCENT_API_KEY'
    },
    'doubao': {
        'name': '字节跳动',
        'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
        'default_model': 'doubao-seed-2-0',
        'env_key': 'DOUBAO_API_KEY'
    }
}

def get_ai_client(provider_id: str, config: Dict):
    """获取 AI 客户端"""
    from openai import OpenAI
    
    provider = AI_PROVIDERS.get(provider_id)
    if not provider:
        raise ValueError(f"未知提供商: {provider_id}")
    
    api_key = config.get(provider_id, {}).get('key') or os.getenv(provider['env_key'])
    if not api_key:
        raise ValueError(f"{provider['name']} API Key 未配置")
    
    base_url = config.get(provider_id, {}).get('base_url') or provider['base_url']
    model = config.get(provider_id, {}).get('enabledModels', [provider['default_model']])[0] if config.get(provider_id) else provider['default_model']
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, model

def generate_with_ai(client, model, search_results, keyword, style='casual'):
    """使用 AI 生成内容"""
    import random
    
    reference_info = "\n\n".join([
        f"- {r.get('title', '')}: {r.get('snippet', '')[:200]}"
        for r in search_results[:5]
    ])
    
    style_prompts = {
        'professional': '专业严谨的科技风格，用词精准，逻辑清晰',
        'casual': '轻松随意的日常分享风格，用词口语化，像朋友聊天',
        'humorous': '幽默风趣的风格，适当使用网络热梗和表情',
        'story': '故事叙述风格，有开头、发展、高潮、结尾'
    }
    
    system_prompt = f"""你是一个小红书内容创作者。根据提供的搜索结果，生成小红书风格的笔记。
要求：
1. 风格：{style_prompts.get(style, style_prompts['casual'])}
2. 标题要吸引眼球，使用emoji
3. 内容结构清晰，适当使用emoji和换行
4. 添加相关话题标签
5. 输出JSON格式：{{"title": "标题", "content": "正文", "tags": ["标签1", "标签2"]}}"""

    user_prompt = f"""关键词：{keyword}

参考搜索结果：
{reference_info}

请根据以上信息生成小红书内容。"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        result_text = response.choices[0].message.content
        
        import re
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            content = json.loads(json_match.group())
            return {
                'title': content.get('title', ''),
                'content': content.get('content', ''),
                'tags': content.get('tags', [])
            }
    except Exception as e:
        logger.error(f"AI 生成失败: {e}")
        raise

    return {'title': f'{keyword} 分享', 'content': f'关于 {keyword} 的分享...', 'tags': [keyword]}

def init_mcp():
    """初始化 MCP 发布器"""
    global mcp_publisher
    try:
        from mcp_publisher import MCPPublisher
        config = load_config()
        mcp_config = config.get('mcp', {})
        
        if not mcp_config.get('enabled', True):
            logger.info("MCP 发布器已禁用")
            mcp_publisher = None
            return
        
        mcp_publisher = MCPPublisher({
            'server_url': mcp_config.get('server_url', 'https://mcp.zouying.work/mcp'),
            'api_key': mcp_config.get('api_key', '') or os.getenv('X_MCP_API_KEY', ''),
            'timeout': mcp_config.get('timeout', 180)
        })
        logger.info("MCP 发布器初始化成功")
    except Exception as e:
        logger.warning(f"MCP 发布器初始化失败: {e}")
        mcp_publisher = None

def load_queue():
    """加载队列"""
    if QUEUE_FILE.exists():
        try:
            with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载队列失败: {e}")
    return []

def save_queue(queue):
    """保存队列"""
    try:
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存队列失败: {e}")
        return False

def log_action(action, details=""):
    """记录操作日志"""
    logger.info(f"{action} - {details}")

@app.route('/')
def index():
    """主页"""
    return send_from_directory('.', 'dashboard.html')

@app.route('/health')
def health():
    """健康检查"""
    health_status = {
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'feishu': feishu_client.enabled if feishu_client else False,
            'mcp': mcp_publisher is not None
        }
    }
    
    queue = load_queue()
    health_status['queue'] = {
        'pending': len([q for q in queue if q['status'] == 'pending']),
        'approved': len([q for q in queue if q['status'] == 'approved']),
        'published': len([q for q in queue if q['status'] == 'published'])
    }
    
    return jsonify(health_status)

@app.route('/api/stats')
def get_stats():
    """获取统计信息"""
    queue = load_queue()
    today = datetime.now().strftime('%Y-%m-%d')
    
    stats = {
        'pending': len([q for q in queue if q['status'] == 'pending']),
        'approved': len([q for q in queue if q['status'] == 'approved']),
        'published': len([q for q in queue if q['status'] == 'published']),
        'today_published': len([q for q in queue if q['status'] == 'published' and q.get('published_at', '').startswith(today)]),
        'today_generated': len([q for q in queue if q.get('created_at', '').startswith(today)])
    }
    return jsonify(stats)

@app.route('/api/queue')
def get_queue():
    """获取队列"""
    status = request.args.get('status', 'all')
    queue = load_queue()
    
    if status != 'all':
        queue = [q for q in queue if q['status'] == status]
    
    # 按创建时间倒序
    queue = sorted(queue, key=lambda x: x.get('created_at', ''), reverse=True)
    return jsonify(queue)

@app.route('/api/queue/<item_id>/approve', methods=['POST'])
def approve_item(item_id):
    """批准内容"""
    queue = load_queue()
    for item in queue:
        if item['id'] == item_id:
            if item['status'] == 'pending':
                item['status'] = 'approved'
                item['approved_at'] = datetime.now().isoformat()
                save_queue(queue)
                log_action('APPROVE', f"ID: {item_id}, 标题: {item.get('title', '')[:30]}...")
                return jsonify({'success': True, 'message': '已批准'})
            return jsonify({'success': False, 'message': '该内容已被处理'})
    return jsonify({'success': False, 'message': '未找到内容'}), 404

@app.route('/api/queue/<item_id>/reject', methods=['POST'])
def reject_item(item_id):
    """拒绝/删除内容"""
    queue = load_queue()
    for item in queue:
        if item['id'] == item_id:
            item['status'] = 'rejected'
            item['rejected_at'] = datetime.now().isoformat()
            save_queue(queue)
            log_action('REJECT', f"ID: {item_id}, 标题: {item.get('title', '')[:30]}...")
            return jsonify({'success': True, 'message': '已删除'})
    return jsonify({'success': False, 'message': '未找到内容'}), 404

@app.route('/api/publish', methods=['POST'])
def publish_item():
    """发布已批准的内容（手动触发）"""
    global mcp_publisher
    
    if not mcp_publisher:
        init_mcp()
    
    if not mcp_publisher:
        return jsonify({'success': False, 'message': 'MCP 发布器未初始化'}), 500
    
    data = request.get_json()
    item_id = data.get('id') if data else None
    
    queue = load_queue()
    
    # 如果指定了 ID，发布指定内容；否则发布最早批准的
    target_item = None
    if item_id:
        for item in queue:
            if item['id'] == item_id and item['status'] == 'approved':
                target_item = item
                break
    else:
        approved_items = [q for q in queue if q['status'] == 'approved']
        if approved_items:
            target_item = approved_items[0]
    
    if not target_item:
        return jsonify({'success': False, 'message': '没有待发布的内容'}), 400
    
    try:
        # 调用 MCP 发布
        result = mcp_publisher.publish_note(
            title=target_item['title'],
            content=target_item['content'],
            image_paths=target_item.get('images', []),
            tags=target_item.get('tags', [])
        )
        
        if result.get('success'):
            target_item['status'] = 'published'
            target_item['published_at'] = datetime.now().isoformat()
            target_item['note_id'] = result.get('note_id')
            target_item['share_url'] = result.get('share_url')
            save_queue(queue)
            
            # 更新飞书机器人消息（如果通过机器人审核的）
            if feishu_bot and feishu_bot.enabled:
                try:
                    feishu_bot.send_publish_success_notification(
                        target_item['id'],
                        result.get('note_id'),
                        result.get('share_url', '')
                    )
                except Exception as e:
                    logger.warning(f"发送飞书机器人通知失败: {e}")
            
            log_action('PUBLISH', f"ID: {target_item['id']}, NoteID: {result.get('note_id')}")
            return jsonify({
                'success': True, 
                'message': '发布成功',
                'note_id': result.get('note_id'),
                'share_url': result.get('share_url')
            })
        else:
            error_msg = result.get('error', '未知错误')
            log_action('PUBLISH_FAIL', f"ID: {target_item['id']}, Error: {error_msg}")
            return jsonify({'success': False, 'message': f'发布失败: {error_msg}'}), 500
            
    except Exception as e:
        log_action('PUBLISH_ERROR', f"ID: {target_item['id']}, Error: {str(e)}")
        return jsonify({'success': False, 'message': f'发布异常: {str(e)}'}), 500

@app.route('/api/generate', methods=['POST'])
def generate_content():
    """手动触发内容生成"""
    try:
        from image_generator import ImageGenerator
        from search_engine import SearchEngine
        
        config = load_config()
        xhs_config = config.get('xiaohongshu', {})
        
        provider_config = config.get('providers', {})
        default_provider = xhs_config.get('default_provider', 'deepseek')
        provider_cfg = provider_config.get(default_provider, {})
        
        if not provider_cfg.get('key'):
            return jsonify({'success': False, 'message': f'{default_provider} API Key 未配置'}), 400
        
        client, model = get_ai_client(default_provider, provider_config)
        
        import random
        keywords = xhs_config.get('keywords', ['AI人工智能'])
        keyword = random.choice(keywords)
        
        searcher = SearchEngine()
        search_results = searcher.search(keyword, max_results=5)
        
        if not search_results:
            return jsonify({'success': False, 'message': '搜索无结果'}), 400
        
        content = generate_with_ai(client, model, search_results, keyword, xhs_config.get('content_style', 'casual'))
        
        if not content or not content.get('title'):
            return jsonify({'success': False, 'message': '内容生成失败'}), 500
        
        img_gen = ImageGenerator()
        img_count = xhs_config.get('images_per_post', 3)
        images = img_gen.generate(keyword, content['title'], count=img_count)
        
        item = {
            'id': f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'keyword': keyword,
            'provider': default_provider,
            'model': model,
            'title': content['title'],
            'content': content['content'],
            'tags': content.get('tags', []),
            'images': images,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'source_results': [r.get('title', '') for r in search_results[:3]]
        }
        
        queue = load_queue()
        queue.append(item)
        save_queue(queue)
        
        # 写入飞书多维表格（如果启用）
        if feishu_client and feishu_client.enabled:
            try:
                from content_generator import ContentItem
                content_item = ContentItem(
                    id=item['id'],
                    title=item['title'],
                    content=item['content'],
                    tags=item['tags'],
                    summary=item['content'][:100] + '...',
                    keywords=[keyword]
                )
                feishu_client.add_record(content_item)
                
                # 发送飞书通知
                if feishu_notifier:
                    feishu_notifier.send_content_generated(item['title'], content_item.summary)
                
                log_action('GENERATE', f"关键词: {keyword}, 标题: {item['title'][:30]}...，已写入飞书")
            except Exception as e:
                log_action('FEISHU_ERROR', f"写入飞书失败: {e}")
        
        # 发送飞书机器人交互式卡片（如果启用）
        if feishu_bot and feishu_bot.enabled:
            try:
                from content_generator import ContentItem
                content_item = ContentItem(
                    id=item['id'],
                    title=item['title'],
                    content=item['content'],
                    tags=item['tags'],
                    summary=item['content'][:100] + '...',
                    keywords=[keyword]
                )
                feishu_bot.send_content_for_approval(content_item)
                log_action('GENERATE', f"关键词: {keyword}, 标题: {item['title'][:30]}...，已发送飞书机器人")
            except Exception as e:
                log_action('FEISHU_BOT_ERROR', f"发送飞书机器人失败: {e}")
        
        if not (feishu_client and feishu_client.enabled) and not (feishu_bot and feishu_bot.enabled):
            log_action('GENERATE', f"关键词: {keyword}, 标题: {item['title'][:30]}...")
        
        return jsonify({
            'success': True,
            'message': '内容生成成功',
            'item': item
        })
        
    except Exception as e:
        import traceback
        log_action('GENERATE_ERROR', f"Error: {str(e)}")
        logger.error(f"生成错误: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'生成失败: {str(e)}'}), 500

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置"""
    config = load_config()
    mcp_config = config.get('mcp', {})
    config['mcpApiKey'] = mcp_config.get('api_key', '')
    config['mcpServerUrl'] = mcp_config.get('server_url', 'https://mcp.zouying.work/mcp')
    return jsonify(config)

@app.route('/api/config', methods=['POST'])
def save_config_api():
    """保存配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '无效数据'}), 400
        
        existing_config = load_config()
        
        if 'feishuUserId' in data or 'feishuChatId' in data:
            if 'xiaohongshu' not in existing_config:
                existing_config['xiaohongshu'] = {}
            existing_config['xiaohongshu']['feishu_user_id'] = data.get('feishuUserId', '')
            existing_config['xiaohongshu']['feishu_chat_id'] = data.get('feishuChatId', '')
        
        if 'feishuAppId' in data or 'feishuAppSecret' in data or 'feishuVerifyToken' in data or 'feishuEncryptKey' in data:
            if 'feishu' not in existing_config:
                existing_config['feishu'] = {}
            existing_config['feishu']['app_id'] = data.get('feishuAppId', '')
            existing_config['feishu']['app_secret'] = data.get('feishuAppSecret', '')
            existing_config['feishu']['verify_token'] = data.get('feishuVerifyToken', '')
            existing_config['feishu']['encrypt_key'] = data.get('feishuEncryptKey', '')
            if existing_config['feishu']['app_id'] and existing_config['feishu']['app_secret']:
                existing_config['feishu']['enabled'] = True
        
        if 'mcpApiKey' in data or 'mcpServerUrl' in data:
            if 'mcp' not in existing_config:
                existing_config['mcp'] = {}
            existing_config['mcp']['api_key'] = data.get('mcpApiKey', '')
            existing_config['mcp']['server_url'] = data.get('mcpServerUrl', 'https://mcp.zouying.work/mcp')
            existing_config['mcp']['enabled'] = True
            global mcp_publisher
            mcp_publisher = None
        
        if 'providers' in data:
            existing_config['providers'] = data.get('providers')
        
        if 'keywords' in data:
            if 'xiaohongshu' not in existing_config:
                existing_config['xiaohongshu'] = {}
            existing_config['xiaohongshu']['keywords'] = data.get('keywords', [])
        
        if 'style' in data:
            if 'xiaohongshu' not in existing_config:
                existing_config['xiaohongshu'] = {}
            existing_config['xiaohongshu']['content_style'] = data.get('style', 'casual')
        
        import yaml
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(existing_config, f, allow_unicode=True, default_flow_style=False)
        
        clear_config_cache()
        logger.info("配置已保存")
        return jsonify({'success': True, 'message': '配置已保存'})
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'}), 500

@app.route('/api/logs')
def get_logs():
    """获取日志"""
    lines = request.args.get('lines', 50, type=int)
    try:
        log_file = LOGS_DIR / f"web_{datetime.now().strftime('%Y%m')}.log"
        if not log_file.exists():
            return jsonify([])
        
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        return jsonify(all_lines[-lines:])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/feishu/sync', methods=['POST'])
def sync_feishu():
    """
    同步飞书表格中已审核的内容
    将飞书中「已通过」状态的内容同步到本地并发布
    """
    global feishu_client, mcp_publisher
    
    if not feishu_client or not feishu_client.enabled:
        return jsonify({'success': False, 'message': '飞书集成未启用'}), 400
    
    if not mcp_publisher:
        init_mcp()
    
    try:
        records = feishu_client.get_pending_records()
        
        if not records:
            return jsonify({'success': True, 'message': '没有待发布的已审核内容', 'published': 0})
        
        published_count = 0
        for record in records:
            fields = record.get('fields', {})
            record_id = record.get('record_id')
            
            title = fields.get('标题', '')
            content = fields.get('正文', '')
            tags_str = fields.get('标签', '')
            tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            
            if not title or not content:
                continue
            
            try:
                result = mcp_publisher.publish_note(
                    title=title,
                    content=content,
                    image_paths=[],
                    tags=tags
                )
                
                if result.get('success'):
                    feishu_client.update_record_status(
                        record_id=record_id,
                        status='已发布',
                        note_id=result.get('note_id'),
                        share_url=result.get('share_url')
                    )
                    
                    # 发送成功通知
                    if feishu_notifier:
                        feishu_notifier.send_publish_success(title, result.get('share_url', ''))
                    
                    published_count += 1
                    log_action('FEISHU_PUBLISH', f"标题: {title[:30]}..., NoteID: {result.get('note_id')}")
                else:
                    feishu_client.update_record_status(record_id, '发布失败')
                    log_action('FEISHU_PUBLISH_FAIL', f"标题: {title[:30]}...")
                    
            except Exception as e:
                log_action('FEISHU_PUBLISH_ERROR', f"标题: {title[:30]}..., Error: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': f'同步完成，发布了 {published_count} 条内容',
            'published': published_count
        })
        
    except Exception as e:
        log_action('FEISHU_SYNC_ERROR', f"Error: {str(e)}")
        return jsonify({'success': False, 'message': f'同步失败: {str(e)}'}), 500


def poll_feishu_approved():
    """
    后台轮询飞书已审核内容
    每 5 分钟检查一次
    """
    global feishu_client, mcp_publisher
    
    while True:
        try:
            time.sleep(300)  # 5 分钟
            
            if not feishu_client or not feishu_client.enabled:
                continue
            
            if not mcp_publisher:
                init_mcp()
            
            # 获取已审核记录
            records = feishu_client.get_pending_records()
            
            for record in records:
                fields = record.get('fields', {})
                record_id = record.get('record_id')
                
                title = fields.get('标题', '')
                content = fields.get('正文', '')
                tags_str = fields.get('标签', '')
                tags = [t.strip() for t in tags_str.split(',') if t.strip()]
                
                if not title or not content:
                    continue
                
                # 发布
                result = mcp_publisher.publish_note(
                    title=title,
                    content=content,
                    image_paths=[],
                    tags=tags
                )
                
                if result.get('success'):
                    feishu_client.update_record_status(
                        record_id=record_id,
                        status='已发布',
                        note_id=result.get('note_id'),
                        share_url=result.get('share_url')
                    )
                    
                    if feishu_notifier:
                        feishu_notifier.send_publish_success(title, result.get('share_url', ''))
                    
                    log_action('FEISHU_AUTO_PUBLISH', f"标题: {title[:30]}...")
                else:
                    feishu_client.update_record_status(record_id, '发布失败')
                    
        except Exception as e:
            log_action('FEISHU_POLL_ERROR', f"Error: {str(e)}")


@app.route('/api/feishu/send-approval', methods=['POST'])
def send_approval_card():
    """
    发送审核卡片给指定用户或群聊
    
    请求体:
    {
        "content_id": "内容ID",
        "user_id": "飞书用户ID (可选)",
        "chat_id": "飞书群聊ID (可选)"
    }
    """
    global feishu_approval_bot
    
    if not feishu_approval_bot or not feishu_approval_bot.enabled:
        return jsonify({'success': False, 'message': '飞书审核机器人未启用'}), 400
    
    data = request.get_json()
    content_id = data.get('content_id')
    user_id = data.get('user_id')
    chat_id = data.get('chat_id')
    
    if not content_id:
        return jsonify({'success': False, 'message': '缺少 content_id'}), 400
    
    if not user_id and not chat_id:
        return jsonify({'success': False, 'message': '需要指定 user_id 或 chat_id'}), 400
    
    queue = load_queue()
    item = next((q for q in queue if q['id'] == content_id), None)
    
    if not item:
        return jsonify({'success': False, 'message': '内容不存在'}), 404
    
    from feishu_approval_bot import ContentForApproval
    content = ContentForApproval(
        id=item['id'],
        title=item['title'],
        content=item['content'],
        tags=item.get('tags', []),
        images=item.get('images', []),
        keywords=[item.get('keyword', '')],
        provider=item.get('provider', ''),
        model=item.get('model', ''),
        created_at=item.get('created_at', '')
    )
    
    message_id = None
    if user_id:
        message_id = feishu_approval_bot.send_to_user(user_id, content)
    elif chat_id:
        message_id = feishu_approval_bot.send_to_chat(chat_id, content)
    
    if message_id:
        item['feishu_message_id'] = message_id
        save_queue(queue)
        log_action('FEISHU_SEND_APPROVAL', f"ID: {content_id}, To: {user_id or chat_id}")
        return jsonify({'success': True, 'message_id': message_id})
    else:
        return jsonify({'success': False, 'message': '发送失败'}), 500


@app.route('/api/feishu/callback', methods=['POST'])
def feishu_card_callback():
    """
    接收飞书卡片按钮点击回调
    """
    global feishu_approval_bot, mcp_publisher
    
    if not feishu_approval_bot:
        return jsonify({'error': '飞书审核机器人未初始化'}), 500
    
    try:
        event_data = request.get_json()
        
        if event_data.get('challenge'):
            return jsonify({'challenge': event_data['challenge']})
        
        event_type = event_data.get('header', {}).get('event_type')
        
        if event_type == 'card.action.trigger':
            action_value = event_data.get('event', {}).get('action', {}).get('value', {})
            action_type = action_value.get('action')
            content_id = action_value.get('content_id')
            
            response = feishu_approval_bot.handle_card_callback(event_data.get('event', {}))
            
            if action_type == 'approve':
                queue = load_queue()
                item = next((q for q in queue if q['id'] == content_id), None)
                
                if item and item['status'] in ['pending', 'approved']:
                    if not mcp_publisher:
                        init_mcp()
                    
                    if mcp_publisher:
                        result = mcp_publisher.publish_note(
                            title=item['title'],
                            content=item['content'],
                            image_paths=item.get('images', []),
                            tags=item.get('tags', [])
                        )
                        
                        if result.get('success'):
                            item['status'] = 'published'
                            item['published_at'] = datetime.now().isoformat()
                            item['note_id'] = result.get('note_id')
                            item['share_url'] = result.get('share_url')
                            save_queue(queue)
                            
                            feishu_approval_bot.update_card_published(
                                content_id,
                                result.get('note_id'),
                                result.get('share_url', '')
                            )
                            
                            log_action('FEISHU_PUBLISH', f"ID: {content_id}, NoteID: {result.get('note_id')}")
            
            return jsonify(response)
        
        return jsonify({})
        
    except Exception as e:
        logger.error(f"处理飞书回调异常: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/feishu/webhook', methods=['POST'])
def feishu_webhook():
    """
    接收飞书事件推送
    用于处理机器人卡片按钮点击事件
    """
    global feishu_event_handler, mcp_publisher
    
    try:
        event_data = request.get_json()
        
        # 验证请求（如果是挑战请求）
        if event_data.get('challenge'):
            return jsonify({'challenge': event_data['challenge']})
        
        # 处理事件
        if feishu_event_handler:
            response = feishu_event_handler.handle_event(event_data)
            
            # 处理通过/拒绝操作
            event_type = event_data.get('header', {}).get('event_type')
            if event_type == 'card.action.trigger':
                action = event_data.get('event', {}).get('action', {})
                action_value = action.get('value', {})
                action_type = action_value.get('action')
                content_id = action_value.get('content_id')
                
                if action_type == 'approve':
                    # 查找并发布内容
                    queue = load_queue()
                    item = next((q for q in queue if q['id'] == content_id), None)
                    
                    if item and item['status'] == 'pending':
                        if not mcp_publisher:
                            init_mcp()
                        
                        result = mcp_publisher.publish_note(
                            title=item['title'],
                            content=item['content'],
                            image_paths=item.get('images', []),
                            tags=item.get('tags', [])
                        )
                        
                        if result.get('success'):
                            item['status'] = 'published'
                            item['published_at'] = datetime.now().isoformat()
                            item['note_id'] = result.get('note_id')
                            item['share_url'] = result.get('share_url')
                            save_queue(queue)
                            
                            # 更新飞书机器人消息
                            if feishu_bot:
                                feishu_bot.send_publish_success_notification(
                                    content_id, 
                                    result.get('note_id'), 
                                    result.get('share_url', '')
                                )
                            
                            log_action('FEISHU_BOT_PUBLISH', f"ID: {content_id}, NoteID: {result.get('note_id')}")
                        else:
                            return jsonify({'toast': {'type': 'error', 'content': '发布失败，请重试'}})
                
                elif action_type == 'reject':
                    # 删除内容
                    queue = load_queue()
                    queue = [q for q in queue if q['id'] != content_id]
                    save_queue(queue)
                    
                    if feishu_bot:
                        feishu_bot.send_reject_notification(content_id)
                    
                    log_action('FEISHU_BOT_REJECT', f"ID: {content_id}")
            
            return jsonify(response)
        
        return jsonify({})
        
    except Exception as e:
        logger.error(f"处理飞书事件异常: {e}")
        return jsonify({'error': str(e)}), 500


# 启动飞书轮询线程（如果启用）
if feishu_client and feishu_client.enabled:
    poll_thread = threading.Thread(target=poll_feishu_approved, daemon=True)
    poll_thread.start()
    logger.info("飞书轮询线程已启动")

if __name__ == '__main__':
    init_mcp()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=os.getenv('FLASK_DEBUG', 'true').lower() == 'true')
