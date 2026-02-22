#!/bin/bash
set -e

echo "🚀 小红书自动发布系统 - 部署脚本"
echo "=================================="

# 检查 docker
echo "📦 检查 Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ 请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ 请先安装 Docker Compose"
    exit 1
fi

# 创建必要的目录
echo "📁 创建数据目录..."
mkdir -p config data/mcp logs

# 检查配置文件
if [ ! -f "config/config.yaml" ]; then
    echo "⚠️  配置文件不存在，使用默认配置"
    cp config/config.yaml.example config/config.yaml 2>/dev/null || true
fi

# 检查环境变量
if [ ! -f ".env" ]; then
    echo "⚠️  环境变量文件不存在"
    read -p "请输入 DeepSeek API Key: " api_key
    echo "DEEPSEEK_API_KEY=$api_key" > .env
    echo "TZ=Asia/Shanghai" >> .env
    echo "✅ 已创建 .env 文件"
fi

# 拉取 MCP 镜像
echo "⬇️  拉取 MCP 镜像..."
docker pull xpzouying/xiaohongshu-mcp:latest

# 启动服务
echo "🟢 启动服务..."
docker-compose up -d

echo ""
echo "✅ 部署完成！"
echo ""
echo "📋 下一步："
echo "1. 查看 MCP 日志获取登录二维码:"
echo "   docker logs -f xhs-mcp"
echo ""
echo "2. 用小红书 APP 扫码登录"
echo ""
echo "3. 访问 Web UI: http://$(hostname -I | awk '{print $1}'):9999"
echo ""
echo "⚠️  注意：首次启动后需要等待 MCP 登录完成后才能发布内容"
