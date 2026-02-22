#!/bin/bash
# ============================================
# 小红书自动发布系统 - 一键部署脚本
# 支持从 GitHub 拉取最新镜像并部署
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
GITHUB_USER="${GITHUB_USER:-}"
GITHUB_REPO="${GITHUB_REPO:-xiaohongshu-auto-publisher}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DATA_DIR="./data"
CONFIG_DIR="./config"
LOGS_DIR="./logs"

# 打印信息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "$1 未安装，请先安装"
        exit 1
    fi
}

# 初始化目录
init_dirs() {
    print_info "创建必要目录..."
    mkdir -p "$DATA_DIR/mcp" "$CONFIG_DIR" "$LOGS_DIR"
    print_success "目录创建完成"
}

# 检查并创建配置文件
init_config() {
    if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
        print_info "创建默认配置文件..."
        cat > "$CONFIG_DIR/config.yaml" << 'EOF'
xiaohongshu:
  keywords:
    - "AI人工智能"
    - "数码科技"
    - "生活方式"
  content_style: "casual"
  images_per_post: 3

scheduler:
  generate_times:
    - "09:00"
    - "14:00"
    - "19:00"

mcp:
  server_url: "http://xhs-mcp:18060"
EOF
        print_success "配置文件创建完成: $CONFIG_DIR/config.yaml"
    fi

    if [ ! -f ".env" ]; then
        print_warning "环境变量文件 .env 不存在"
        echo ""
        read -p "请输入 DeepSeek API Key: " api_key
        echo "DEEPSEEK_API_KEY=$api_key" > .env
        echo "TZ=Asia/Shanghai" >> .env
        
        if [ -n "$GITHUB_USER" ]; then
            echo "GITHUB_USER=$GITHUB_USER" >> .env
        fi
        
        print_success "环境变量文件创建完成: .env"
        print_warning "请妥善保管 .env 文件，不要提交到 Git"
    fi
}

# 下载最新配置文件
download_config() {
    if [ -z "$GITHUB_USER" ]; then
        print_error "未设置 GITHUB_USER，无法下载配置文件"
        return 1
    fi
    
    print_info "从 GitHub 下载最新配置文件..."
    
    local base_url="https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/main"
    
    # 下载配置文件
    curl -fsSL "${base_url}/docker-compose.prod.yml" -o "${COMPOSE_FILE}.tmp" && \
        mv "${COMPOSE_FILE}.tmp" "$COMPOSE_FILE"
    
    curl -fsSL "${base_url}/.env.example" -o ".env.example"
    
    print_success "配置文件下载完成"
}

# 拉取最新镜像
pull_images() {
    print_info "拉取最新镜像..."
    
    # 设置环境变量供 docker-compose 使用
    export GITHUB_USER
    
    # 如果需要登录 GitHub Container Registry
    if [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_USER" ]; then
        print_info "登录 GitHub Container Registry..."
        echo "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_USER" --password-stdin 2>/dev/null || true
    fi
    
    docker-compose -f "$COMPOSE_FILE" pull
    
    # 拉取 MCP 镜像
    docker pull xpzouying/xiaohongshu-mcp:latest
    
    print_success "镜像拉取完成"
}

# 启动服务
start_services() {
    print_info "启动服务..."
    export GITHUB_USER
    docker-compose -f "$COMPOSE_FILE" up -d
    print_success "服务启动完成"
}

# 停止服务
stop_services() {
    print_info "停止服务..."
    export GITHUB_USER
    docker-compose -f "$COMPOSE_FILE" down
    print_success "服务已停止"
}

# 查看状态
show_status() {
    print_info "服务状态:"
    docker-compose -f "$COMPOSE_FILE" ps
    echo ""
    print_info "容器资源使用:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.Status}}" 2>/dev/null || true
}

# 查看日志
show_logs() {
    local service=$1
    if [ -n "$service" ]; then
        docker-compose -f "$COMPOSE_FILE" logs -f "$service"
    else
        docker-compose -f "$COMPOSE_FILE" logs -f
    fi
}

# 更新到最新版本
update() {
    print_info "更新到最新版本..."
    
    # 备份数据
    backup_dir="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    cp -r "$DATA_DIR" "$CONFIG_DIR" ".env" "$backup_dir/" 2>/dev/null || true
    print_info "数据已备份到: $backup_dir"
    
    # 下载最新配置（可选）
    if [ -n "$GITHUB_USER" ]; then
        read -p "是否下载最新配置文件? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            download_config
        fi
    fi
    
    # 拉取新镜像并重启
    pull_images
    export GITHUB_USER
    docker-compose -f "$COMPOSE_FILE" up -d --remove-orphans
    
    # 清理旧镜像
    docker image prune -f
    
    print_success "更新完成！"
}

# 首次部署引导
first_time_setup() {
    echo ""
    echo "=============================================="
    echo "  小红书自动发布系统 - 首次部署"
    echo "=============================================="
    echo ""
    
    # 检查 Docker
    check_command docker
    check_command docker-compose
    
    # 询问 GitHub 用户名
    if [ -z "$GITHUB_USER" ]; then
        echo ""
        echo "GitHub 用户名用于从 GitHub Container Registry 拉取镜像。"
        echo "如果你 Fork 了本项目并开启了 GitHub Actions，请输入你的 GitHub 用户名。"
        echo "如果直接回车，将使用本地构建方式。"
        echo ""
        read -p "GitHub 用户名 (直接回车跳过): " input_user
        if [ -n "$input_user" ]; then
            GITHUB_USER=$input_user
            echo "GITHUB_USER=$GITHUB_USER" >> .env 2>/dev/null || true
        fi
    fi
    
    # 如果提供了 GitHub 用户名，下载配置文件
    if [ -n "$GITHUB_USER" ]; then
        print_info "将从 GitHub 下载配置文件..."
        
        # 如果配置文件不存在，下载
        if [ ! -f "$COMPOSE_FILE" ]; then
            download_config || print_warning "下载配置文件失败，将使用本地文件"
        fi
    fi
    
    # 检查配置文件
    if [ ! -f "$COMPOSE_FILE" ]; then
        print_error "配置文件 $COMPOSE_FILE 不存在"
        print_info "请确保你在正确的目录，或手动下载配置文件:"
        print_info "wget https://raw.githubusercontent.com/你的用户名/xiaohongshu-auto-publisher/main/docker-compose.prod.yml"
        exit 1
    fi
    
    # 初始化
    init_dirs
    init_config
    
    # 拉取并启动
    pull_images
    start_services
    
    echo ""
    echo "=============================================="
    print_success "部署完成！"
    echo "=============================================="
    echo ""
    
    # 获取 IP 地址
    IP_ADDRESS=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "localhost")
    
    echo "📱 访问地址: http://${IP_ADDRESS}:9999"
    echo ""
    echo "📋 下一步："
    echo "1. 查看 MCP 日志获取登录二维码:"
    echo "   ./deploy.sh logs mcp"
    echo ""
    echo "2. 用小红书 APP 扫码登录"
    echo ""
    echo "3. 登录完成后即可开始使用"
    echo ""
    echo "📖 常用命令："
    echo "   ./deploy.sh status    # 查看状态"
    echo "   ./deploy.sh logs      # 查看日志"
    echo "   ./deploy.sh update    # 更新到最新版"
    echo "   ./deploy.sh stop      # 停止服务"
    echo "=============================================="
}

# 显示帮助
show_help() {
    echo "小红书自动发布系统 - 部署脚本"
    echo ""
    echo "使用方法: $0 [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  setup              首次部署 (默认)"
    echo "  start              启动服务"
    echo "  stop               停止服务"
    echo "  restart            重启服务"
    echo "  update             更新到最新版本"
    echo "  status             查看服务状态"
    echo "  logs [service]     查看日志"
    echo "  pull               拉取最新镜像"
    echo "  backup             备份数据"
    echo "  download-config    下载最新配置文件"
    echo ""
    echo "环境变量:"
    echo "  GITHUB_USER        GitHub 用户名"
    echo "  GITHUB_TOKEN       GitHub Token (用于私有镜像)"
    echo "  COMPOSE_FILE       Docker Compose 文件路径 (默认: docker-compose.prod.yml)"
    echo ""
    echo "示例:"
    echo "  GITHUB_USER=yourname ./deploy.sh setup"
    echo "  ./deploy.sh update"
    echo "  ./deploy.sh logs xhs-web"
}

# 主菜单
main() {
    case "${1:-setup}" in
        help|-h|--help)
            show_help
            ;;
        setup|install)
            first_time_setup
            ;;
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            stop_services
            start_services
            ;;
        update|upgrade)
            update
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "$2"
            ;;
        pull)
            pull_images
            ;;
        download-config)
            download_config
            ;;
        backup)
            backup_dir="backup_$(date +%Y%m%d_%H%M%S)"
            mkdir -p "$backup_dir"
            cp -r "$DATA_DIR" "$CONFIG_DIR" ".env" "$backup_dir/" 2>/dev/null || true
            print_success "数据已备份到: $backup_dir"
            ;;
        *)
            echo "未知命令: $1"
            echo "使用 '$0 help' 查看帮助"
            exit 1
            ;;
    esac
}

main "$@"
