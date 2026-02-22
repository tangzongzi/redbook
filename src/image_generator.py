"""
AI 图片生成模块
支持多种免费/付费图片生成方案
"""

import os
import requests
import base64
from typing import List, Optional
from pathlib import Path
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
import logging

logger = logging.getLogger(__name__)


@dataclass
class GeneratedImage:
    """生成的图片信息"""
    local_path: str
    prompt: str
    source: str  # 图片来源: ai, search, template


class ImageGenerator:
    """小红书配图生成器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.source = config.get('source', 'ai')
        self.ai_provider = config.get('ai_provider', 'pollinations')
        self.count = config.get('count', 3)
        self.ratio = config.get('ratio', '3:4')
        
        # 图片尺寸配置（小红书推荐 3:4）
        self.ratio_sizes = {
            '3:4': (900, 1200),
            '1:1': (1080, 1080),
            '9:16': (1080, 1920)
        }
        
        # 输出目录
        self.output_dir = Path('../output/images')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"图片生成器初始化完成，来源: {self.source}")
    
    def generate(self, 
                 content_title: str, 
                 content_text: str,
                 tags: List[str],
                 keyword: str) -> List[GeneratedImage]:
        """
        为内容生成配图
        
        Args:
            content_title: 内容标题
            content_text: 内容正文
            tags: 标签列表
            keyword: 核心关键词
            
        Returns:
            List[GeneratedImage]: 生成的图片列表
        """
        if self.source == 'ai':
            return self._generate_ai_images(content_title, content_text, tags, keyword)
        elif self.source == 'search':
            return self._search_images(keyword)
        elif self.source == 'local':
            return self._use_local_images()
        else:
            # 使用默认模板生成
            return self._generate_template_images(content_title, keyword)
    
    def _generate_ai_images(self, title: str, content: str, tags: List[str], keyword: str) -> List[GeneratedImage]:
        """使用 AI 生成图片"""
        images = []
        
        # 生成图片提示词
        prompts = self._create_image_prompts(title, keyword)
        
        for i, prompt in enumerate(prompts[:self.count], 1):
            try:
                if self.ai_provider == 'pollinations':
                    image_path = self._generate_pollinations(prompt, i)
                elif self.ai_provider == 'sd':
                    image_path = self._generate_stable_diffusion(prompt, i)
                else:
                    image_path = self._generate_template_image(prompt, i, keyword)
                
                if image_path:
                    images.append(GeneratedImage(
                        local_path=image_path,
                        prompt=prompt,
                        source='ai'
                    ))
                    
            except Exception as e:
                logger.error(f"生成第 {i} 张图片失败: {e}")
        
        # 如果 AI 生成失败，使用模板
        if not images:
            logger.warning("AI 生成失败，使用模板图片")
            return self._generate_template_images(title, keyword)
        
        return images
    
    def _create_image_prompts(self, title: str, keyword: str) -> List[str]:
        """为图片生成创建提示词"""
        base_prompts = [
            f"A beautiful, modern illustration about {keyword}, clean design, suitable for social media, bright colors, minimalist style, professional photography",
            f"Lifestyle photo related to {keyword}, warm lighting, aesthetic composition, Instagram style, high quality",
            f"Creative flat lay design about {keyword}, top view, organized layout, pastel colors, trendy visual",
        ]
        return base_prompts
    
    def _generate_pollinations(self, prompt: str, index: int) -> Optional[str]:
        """
        使用 Pollinations AI 免费生成图片
        无需 API Key，直接调用
        """
        try:
            # Pollinations 免费图片生成 API
            width, height = self.ratio_sizes.get(self.ratio, (900, 1200))
            
            # URL 编码提示词
            encoded_prompt = requests.utils.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"
            
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            # 保存图片
            image_path = self.output_dir / f"generated_{index}_{os.urandom(4).hex()}.png"
            with open(image_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Pollinations 图片生成成功: {image_path}")
            return str(image_path)
            
        except Exception as e:
            logger.error(f"Pollinations 生成失败: {e}")
            return None
    
    def _generate_stable_diffusion(self, prompt: str, index: int) -> Optional[str]:
        """使用 Stable Diffusion API 生成（需配置本地或远程服务）"""
        # 这里可以接入本地 SD 或在线服务
        logger.warning("Stable Diffusion 暂未实现")
        return None
    
    def _generate_template_images(self, title: str, keyword: str) -> List[GeneratedImage]:
        """生成简单的模板图片（作为后备方案）"""
        images = []
        
        for i in range(self.count):
            image_path = self._generate_template_image(f"Template {i+1}", i+1, keyword)
            if image_path:
                images.append(GeneratedImage(
                    local_path=image_path,
                    prompt=f"Template image for {keyword}",
                    source='template'
                ))
        
        return images
    
    def _generate_template_image(self, text: str, index: int, keyword: str) -> Optional[str]:
        """生成文字模板图片"""
        try:
            width, height = self.ratio_sizes.get(self.ratio, (900, 1200))
            
            # 创建渐变背景
            image = Image.new('RGB', (width, height), color='#FF6B9D')
            draw = ImageDraw.Draw(image)
            
            # 添加渐变效果（简化版）
            for y in range(height):
                r = int(255 - (y / height) * 50)
                g = int(107 - (y / height) * 20)
                b = int(157 - (y / height) * 30)
                draw.line([(0, y), (width, y)], fill=(r, g, b))
            
            # 添加文字
            title_text = f"{keyword}\n精选内容"
            
            # 尝试加载字体，失败则使用默认
            try:
                # 尝试使用系统字体
                font_paths = [
                    "C:/Windows/Fonts/simhei.ttf",  # Windows
                    "/System/Library/Fonts/PingFang.ttc",  # macOS
                    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",  # Linux
                ]
                font = None
                for fp in font_paths:
                    if os.path.exists(fp):
                        font = ImageFont.truetype(fp, 60)
                        break
                
                if font is None:
                    font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # 绘制文字（居中）
            bbox = draw.textbbox((0, 0), title_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (width - text_width) / 2
            y = (height - text_height) / 2
            
            # 添加文字阴影
            draw.text((x+2, y+2), title_text, font=font, fill='#333333')
            draw.text((x, y), title_text, font=font, fill='white')
            
            # 保存
            image_path = self.output_dir / f"template_{index}_{keyword[:10]}_{os.urandom(4).hex()}.png"
            image.save(image_path, quality=95)
            
            return str(image_path)
            
        except Exception as e:
            logger.error(f"生成模板图片失败: {e}")
            return None
    
    def _search_images(self, keyword: str) -> List[GeneratedImage]:
        """从网络搜索图片（可以使用 Unsplash 等免费图库 API）"""
        images = []
        
        # 使用 Unsplash Source（免费）
        try:
            for i in range(self.count):
                width, height = self.ratio_sizes.get(self.ratio, (900, 1200))
                
                # Unsplash 随机图片
                url = f"https://source.unsplash.com/random/{width}x{height}/?{requests.utils.quote(keyword)}"
                
                response = requests.get(url, allow_redirects=True, timeout=30)
                
                image_path = self.output_dir / f"searched_{i+1}_{os.urandom(4).hex()}.jpg"
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                
                images.append(GeneratedImage(
                    local_path=str(image_path),
                    prompt=f"Searched: {keyword}",
                    source='search'
                ))
                
        except Exception as e:
            logger.error(f"搜索图片失败: {e}")
        
        return images if images else self._generate_template_images(keyword, keyword)
    
    def _use_local_images(self) -> List[GeneratedImage]:
        """使用本地图片库"""
        images = []
        local_dir = Path('../output/local_images')
        
        if local_dir.exists():
            for img_path in local_dir.glob('*'):
                if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                    images.append(GeneratedImage(
                        local_path=str(img_path),
                        prompt="Local image",
                        source='local'
                    ))
                    if len(images) >= self.count:
                        break
        
        return images


if __name__ == "__main__":
    # 测试代码
    config = {
        'source': 'ai',
        'ai_provider': 'pollinations',
        'count': 3,
        'ratio': '3:4'
    }
    
    generator = ImageGenerator(config)
    
    # 生成图片
    images = generator.generate(
        content_title="AI工具推荐",
        content_text="今天推荐几款好用的AI工具...",
        tags=["#AI", "#效率工具"],
        keyword="人工智能"
    )
    
    print(f"\n生成了 {len(images)} 张图片:")
    for img in images:
        print(f"  - {img.local_path} ({img.source})")
