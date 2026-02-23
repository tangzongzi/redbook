# 小红书自动发布系统 - Docker 使用指南

## 功能概述

这个 Docker 镜像包含完整的资讯收集和自动发布系统，支持：

- ✅ **自动搜索资讯**：定时搜索多个关键词的最新资讯
- ✅ **资讯去重管理**：自动去重，记录使用状态
- ✅ **Web 界面**：提供图形化操作界面
- ✅ **API 接口**：完整的 REST API
- ✅ **Docker 部署**：一键部署到任何设备

## 快速开始

### 1. 使用 Docker Compose（推荐）

```bash
# 进入项目目录
cd xiaohongshu-auto-publisher

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 2. 单独使用 Docker

```bash
# 构建镜像
docker build -t xiaohongshu-publisher .

# 运行容器
docker run -d \
  --name xiaohongshu-auto-publisher \
  -p 8080:8080 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  xiaohongshu-publisher
```

## 访问应用

启动成功后，在浏览器中访问：

- **Web 界面**: http://localhost:8080
- **资讯统计**: http://localhost:8080/api/news/stats
- **获取资讯**: http://localhost:8080/api/news

## 配置说明

编辑 `config/config.yaml` 文件来自定义配置：

```yaml
news_collector:
  enabled: true
  keywords:
    - "AI人工智能"
    - "科技趋势"
    - "小红书运营"
    - "互联网创业"
    - "数码新品"
  collect_interval: 3600        # 收集间隔（秒）
  max_news_per_keyword: 20      # 每个关键词最多收集条数
  max_total_news: 200           # 总最多保留条数
```

## 手动收集资讯

```bash
# 进入容器
docker exec -it xiaohongshu-auto-publisher bash

# 收集一次资讯
python src/news_collector.py --once

# 收集指定关键词
python src/news_collector.py --keywords "AI人工智能" "科技趋势"

# 查看已收集的资讯
python src/news_collector.py --list
```

## 目录结构

```
xiaohongshu-auto-publisher/
├── config/          # 配置文件目录
├── data/            # 数据存储（收集的资讯等）
├── logs/            # 日志文件
├── src/             # 源代码
│   ├── news_collector.py  # 资讯收集器
│   └── simple_search.py   # 简单搜索引擎
├── web/             # Web 应用
├── Dockerfile       # Docker 镜像文件
└── docker-compose.yml  # Docker Compose 配置
```

## API 接口

### 获取资讯统计
```
GET /api/news/stats
```

### 获取已收集的资讯
```
GET /api/news?keyword=AI人工智能&limit=20&unused=true
```

### 立即收集资讯
```
POST /api/news/collect
Content-Type: application/json

{
  "keywords": ["AI人工智能", "科技趋势"]
}
```

### 标记资讯为已使用
```
POST /api/news/{news_id}/use
```

## 常见问题

### Q: 如何修改收集的关键词？
A: 编辑 `config/config.yaml` 文件中的 `news_collector.keywords` 列表，然后重启容器。

### Q: 资讯存储在哪里？
A: 资讯存储在 `data/collected_news.json` 文件中。

### Q: 如何查看日志？
A: 使用 `docker-compose logs -f` 或查看 `logs/` 目录。

### Q: 搜索结果不理想怎么办？
A: `simple_search.py` 提供了多搜索源支持，包括百度、Bing、DuckDuckGo。
