# 小红书自动发布系统 🤖

基于 DeepSeek AI + MCP 的半自动内容发布方案。

[![Build Docker Images](https://github.com/YOUR_USERNAME/xiaohongshu-auto-publisher/actions/workflows/docker-build.yml/badge.svg)](https://github.com/YOUR_USERNAME/xiaohongshu-auto-publisher/actions/workflows/docker-build.yml)

## 工作流程

```
定时/手动生成          人工审核             手动发布
     │                  │                  │
     ▼                  ▼                  ▼
┌─────────┐      ┌─────────────┐      ┌──────────┐
│ 搜索    │      │  Web UI     │      │ 点击发布 │
│ AI生成  │─────▶│  查看内容   │─────▶│ 调用MCP  │
│ 生成图片│      │  批准/删除  │      │ 发布到   │
└─────────┘      └─────────────┘      │ 小红书   │
                                      └──────────┘
```

## 功能特点

- 🤖 **AI 内容生成**: 基于 DeepSeek API 自动生成小红书风格文案
- 🎨 **自动配图**: 使用 Pollinations AI 免费生成图片
- 👀 **人工审核**: Web UI 可视化审核，确保内容质量
- 📊 **飞书集成**: 支持飞书多维表格审核（可选）
- 📱 **一键发布**: 审核通过后手动触发发布到小红书
- 🔄 **自动更新**: 支持自动拉取最新 Docker 镜像

## 快速开始（推荐）

### 方法一：使用一键部署脚本

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/xiaohongshu-auto-publisher.git
cd xiaohongshu-auto-publisher

# 2. 运行部署脚本
chmod +x deploy.sh
./deploy.sh setup
```

### 方法二：手动部署

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/xiaohongshu-auto-publisher.git
cd xiaohongshu-auto-publisher

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 启动服务
docker-compose -f docker-compose.prod.yml up -d

# 4. 配置 MCP（首次）
docker logs -f xhs-mcp
# 用小红书 APP 扫码登录

# 5. 访问 Web UI
open http://localhost:9999
```

## 自动更新配置

本项目支持多种自动更新方式：

### 方式一：Watchtower 自动更新（推荐）

在 `docker-compose.prod.yml` 中已配置 Watchtower，启用后每天凌晨 4 点自动检查并更新：

```bash
# 启用自动更新
docker-compose -f docker-compose.prod.yml --profile auto-update up -d
```

### 方式二：手动更新

```bash
# 使用部署脚本一键更新
./deploy.sh update

# 或手动执行
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

### 方式三：NAS 定时任务

在 NAS 上设置定时任务（如每天凌晨 3 点）：

```bash
0 3 * * * cd /path/to/xiaohongshu-auto-publisher && ./deploy.sh update
```

## 目录结构

```
.
├── docker-compose.yml           # 开发环境配置
├── docker-compose.prod.yml      # 生产环境配置
├── deploy.sh                    # 一键部署脚本
├── web/                         # Web UI 服务
│   ├── app.py
│   ├── dashboard.html
│   └── Dockerfile
├── src/                         # 内容生成服务
│   ├── scheduler.py
│   ├── content_generator.py
│   ├── image_generator.py
│   ├── search_engine.py
│   ├── mcp_publisher.py
│   └── Dockerfile
├── config/                      # 配置文件（需创建）
│   └── config.yaml
├── data/                        # 数据存储
│   ├── queue.json              # 内容队列
│   └── mcp/                    # MCP 登录态
├── logs/                        # 日志文件
└── .github/workflows/           # GitHub Actions
    └── docker-build.yml        # 自动构建镜像
```

## 配置说明

### 1. 环境变量 `.env`

```bash
# 必需
DEEPSEEK_API_KEY=sk-your-key    # DeepSeek API Key

# 可选
GITHUB_USER=yourusername        # GitHub 用户名（用于拉取镜像）
TZ=Asia/Shanghai               # 时区
```

### 2. 应用配置 `config/config.yaml`

```yaml
xiaohongshu:
  # 搜索关键词池，每次随机选择
  keywords:
    - "AI人工智能"
    - "数码科技"
    - "生活方式"
  
  # 文案风格
  content_style: "casual"  # casual(轻松) / professional(专业) / humorous(幽默) / story(故事)
  
  # 每篇笔记图片数量
  images_per_post: 3

scheduler:
  # 每天自动生成内容的时间点
  generate_times:
    - "09:00"
    - "14:00"
    - "19:00"

mcp:
  # MCP 服务地址（容器内通信）
  server_url: "http://xhs-mcp:18060"
```

## 使用指南

### 1. 生成内容

- **自动**: 按配置的时间点自动生成
- **手动**: 在 Web UI 点击「立即生成」

### 2. 审核内容

1. 打开 Web UI (`http://NAS_IP:9999`)
2. 在「待审核」标签查看生成的内容
3. 点击「批准」或「删除」

### 3. 发布内容

1. 切换到「已批准」标签
2. 检查内容无误后点击「发布」
3. 系统调用 MCP 发布到小红书

## 常用命令

```bash
# 查看服务状态
./deploy.sh status

# 查看日志（全部）
./deploy.sh logs

# 查看特定服务日志
./deploy.sh logs xhs-web
./deploy.sh logs xhs-mcp

# 重启服务
./deploy.sh restart

# 更新到最新版本
./deploy.sh update

# 备份数据
./deploy.sh backup

# 停止服务
./deploy.sh stop
```

## 开发指南

### 本地开发

```bash
# 使用开发配置启动
docker-compose up -d

# 代码修改后自动重启（Flask 热重载）
```

### 构建镜像

```bash
# Web 服务
docker build -t xhs-web:latest -f web/Dockerfile .

# 生成器服务
docker build -t xhs-generator:latest -f src/Dockerfile ./src
```

## GitHub 配置说明

### 1. Fork 本项目

点击右上角的 "Fork" 按钮，将项目复制到你的 GitHub 账号下。

### 2. 配置 Secrets（可选）

如果需要自动部署到你的服务器，配置以下 Secrets：

- `DEPLOY_WEBHOOK_URL`: 部署 Webhook 地址

### 3. 启用 GitHub Packages

1. 进入仓库 Settings → Packages
2. 确保 GitHub Actions 有权限推送包

### 4. 镜像地址

构建完成后，镜像将发布到：

```
ghcr.io/YOUR_USERNAME/xiaohongshu-auto-publisher-web:latest
ghcr.io/YOUR_USERNAME/xiaohongshu-auto-publisher-generator:latest
```

## 技术栈

- **后端**: Python 3.11 + Flask
- **前端**: 原生 HTML/JS + Tailwind CSS
- **AI 生成**: DeepSeek API
- **图片生成**: Pollinations AI
- **内容搜索**: DuckDuckGo
- **发布**: xiaohongshu-mcp (MCP 协议)
- **部署**: Docker + Docker Compose

## 飞书集成（可选）

系统支持通过飞书多维表格进行内容审核，适合团队协作场景。

### 飞书集成工作流程

```
AI 生成内容 ──▶ 写入飞书表格 ──▶ 你在飞书审核 ──▶ 系统自动发布 ──▶ 更新飞书状态
                    │                                       │
                    ▼                                       ▼
              状态: 待审核                           状态: 已发布
                                                    笔记ID: xxx
```

### 配置飞书集成

1. **创建飞书应用**
   - 访问 [飞书开放平台](https://open.feishu.cn/app)
   - 创建「企业自建应用」
   - 获取 App ID 和 App Secret

2. **创建多维表格**
   - 在飞书中创建多维表格
   - 添加字段：标题、正文、标签、摘要、关键词、图片路径、状态、创建时间、发布时间、笔记ID、分享链接

3. **配置环境变量**
   ```bash
   FEISHU_APP_ID=cli_xxxxxxxxxx
   FEISHU_APP_SECRET=xxxxxxxxxx
   FEISHU_BITABLE_APP_TOKEN=xxxxxxxxxx
   FEISHU_BITABLE_TABLE_ID=xxxxxxxxxx
   FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx  # 可选
   ```

4. **启用飞书集成**
   ```yaml
   # config/config.yaml
   feishu:
     enabled: true
     approval_mode: "manual"
   ```

### 飞书审核操作

1. **内容生成后**
   - 系统自动将内容写入飞书表格
   - 状态为「待审核」
   - 飞书群收到通知（如果配置了 Webhook）

2. **审核操作**
   - 在飞书表格中将「状态」字段改为「已通过」
   - 系统每 5 分钟自动检查
   - 检测到「已通过」后自动发布到小红书

3. **发布完成后**
   - 飞书表格状态更新为「已发布」
   - 自动填充「笔记ID」和「分享链接」
   - 飞书群收到发布成功通知

### 手动触发飞书同步

```bash
# 调用 API 立即同步飞书中已审核的内容
curl -X POST http://localhost:9999/api/feishu/sync
```

详细配置请参考 [飞书配置指南](docs/feishu-setup.md)

## 注意事项

1. **MCP 登录**: 首次启动后必须扫码登录小红书，Cookie 保存在 `data/mcp/`
2. **API Key**: DeepSeek API Key 不要泄露，妥善保管 `.env` 文件
3. **内容审核**: 建议开启人工审核，避免发布不当内容
4. **频率限制**: 注意小红书的发文频率限制，避免账号异常
5. **飞书权限**: 飞书应用需要申请 `bitable:record` 和 `bitable:app` 权限

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 PR！

## 致谢

- [xiaohongshu-mcp](https://github.com/xpou/ying/xiaohongshu-mcp) - 小红书 MCP 服务
- [DeepSeek](https://deepseek.com/) - AI 内容生成
- [Pollinations](https://pollinations.ai/) - 免费 AI 图片生成
