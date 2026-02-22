# GitHub 配置指南

本文档指导你如何 Fork 本项目并配置自动构建和更新。

## 快速配置步骤

### 1. Fork 项目

1. 访问原项目页面
2. 点击右上角的 **Fork** 按钮
3. 选择你的个人账号或组织

### 2. 修改配置

Fork 后需要修改以下文件中的占位符：

#### README.md

找到并替换以下占位符：
```markdown
[![Build Docker Images](https://github.com/YOUR_USERNAME/xiaohongshu-auto-publisher/actions/workflows/docker-build.yml/badge.svg)](https://github.com/YOUR_USERNAME/xiaohongshu-auto-publisher/actions/workflows/docker-build.yml)
```

替换为：
```markdown
[![Build Docker Images](https://github.com/你的用户名/xiaohongshu-auto-publisher/actions/workflows/docker-build.yml/badge.svg)](https://github.com/你的用户名/xiaohongshu-auto-publisher/actions/workflows/docker-build.yml)
```

#### docker-compose.prod.yml

将镜像名称修改为你的：
```yaml
services:
  xhs-web:
    image: ghcr.io/你的用户名/xiaohongshu-auto-publisher-web:latest
  
  xhs-generator:
    image: ghcr.io/你的用户名/xiaohongshu-auto-publisher-generator:latest
```

### 3. 启用 GitHub Actions

1. 进入你 Fork 的仓库
2. 点击 **Actions** 标签
3. 点击 **I understand my workflows, go ahead and enable them**

### 4. 配置权限

确保 GitHub Actions 有权限推送包：

1. 进入 **Settings** → **Actions** → **General**
2. 找到 **Workflow permissions**
3. 选择 **Read and write permissions**
4. 勾选 **Allow GitHub Actions to create and approve pull requests**
5. 点击 **Save**

## 自动构建触发条件

配置完成后，以下操作会自动触发镜像构建：

| 触发条件 | 说明 |
|---------|------|
| 推送到 `main` 分支 | 构建 `latest` 标签的镜像 |
| 创建 `v*` 标签 | 构建对应版本标签的镜像 |
| 手动触发 | 在 Actions 页面点击运行 |

## 部署到 NAS

### 方法一：使用 deploy.sh（推荐）

```bash
# 1. SSH 登录到 NAS
ssh user@nas-ip

# 2. 创建部署目录
mkdir -p ~/xiaohongshu-auto-publisher
cd ~/xiaohongshu-auto-publisher

# 3. 下载部署脚本和配置文件
curl -o deploy.sh https://raw.githubusercontent.com/你的用户名/xiaohongshu-auto-publisher/main/deploy.sh
curl -o docker-compose.prod.yml https://raw.githubusercontent.com/你的用户名/xiaohongshu-auto-publisher/main/docker-compose.prod.yml
curl -o .env.example https://raw.githubusercontent.com/你的用户名/xiaohongshu-auto-publisher/main/.env.example

# 4. 添加执行权限并部署
chmod +x deploy.sh
./deploy.sh setup
```

### 方法二：手动部署

```bash
# 1. 下载配置文件
wget https://raw.githubusercontent.com/你的用户名/xiaohongshu-auto-publisher/main/docker-compose.prod.yml
wget https://raw.githubusercontent.com/你的用户名/xiaohongshu-auto-publisher/main/.env.example -O .env

# 2. 编辑 .env 文件，填入 DEEPSEEK_API_KEY

# 3. 登录 GitHub Container Registry
docker login ghcr.io -u 你的GitHub用户名 -p 你的GitHubToken

# 4. 拉取并启动
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

## 自动更新配置

### 使用 Watchtower（推荐）

在 `docker-compose.prod.yml` 中已配置 Watchtower，启用即可：

```bash
# 启用自动更新
docker-compose -f docker-compose.prod.yml --profile auto-update up -d

# 查看 Watchtower 日志
docker logs -f xhs-watchtower
```

### 配置 NAS 定时任务

以 Synology DSM 为例：

1. 打开 **控制面板** → **任务计划**
2. 点击 **新增** → **计划的任务** → **用户定义的脚本**
3. 设置任务名称，如 "XHS Auto Update"
4. 设置时间表（建议每天凌晨 3 点）
5. 在 **任务设置** 中输入脚本：

```bash
cd /volume1/docker/xiaohongshu-auto-publisher
./deploy.sh update
```

6. 点击 **确定** 保存

## GitHub Token 获取

如果需要拉取私有镜像，需要配置 GitHub Token：

1. 访问 https://github.com/settings/tokens
2. 点击 **Generate new token (classic)**
3. 勾选 `read:packages` 权限
4. 生成 Token 并保存

将 Token 配置到 `.env` 文件：
```bash
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```

## 更新项目代码

当原项目有更新时，你可以同步到 Fork：

### 方法一：GitHub Web 界面

1. 访问你 Fork 的仓库
2. 点击 **Sync fork** 按钮
3. 点击 **Update branch**

同步后会自动触发新的镜像构建。

### 方法二：命令行

```bash
# 添加原仓库为上游
git remote add upstream https://github.com/原作者/原始仓库.git

# 拉取原仓库更新
git fetch upstream

# 合并到主分支
git checkout main
git merge upstream/main

# 推送到你 Fork 的仓库
git push origin main
```

## 自定义修改

如果你想自定义代码：

1. 克隆你 Fork 的仓库到本地
2. 修改代码
3. 提交并推送
4. GitHub Actions 会自动构建新镜像
5. NAS 上的 Watchtower 会自动拉取更新

```bash
# 本地开发
git clone https://github.com/你的用户名/xiaohongshu-auto-publisher.git
cd xiaohongshu-auto-publisher

# 修改代码...

# 提交
git add .
git commit -m "feat: 添加新功能"
git push origin main
```

## 故障排查

### 镜像拉取失败

检查 GitHub Packages 是否公开：
1. 访问 `https://github.com/你的用户名?tab=packages`
2. 点击包名称
3. 点击 **Package settings**
4. 在 **Danger Zone** 中将包设为公开

### 构建失败

查看 Actions 日志：
1. 进入仓库 **Actions** 标签
2. 点击失败的 workflow
3. 查看详细日志

### 部署失败

检查日志：
```bash
docker logs xhs-web
docker logs xhs-generator
docker logs xhs-mcp
```
