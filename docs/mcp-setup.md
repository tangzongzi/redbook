# xiaohongshu-mcp 配置指南

## 什么是 MCP？

MCP (Model Context Protocol) 是一个开放协议，让 AI 应用能够安全地连接到各种数据源和工具。xiaohongshu-mcp 是一个基于 MCP 协议的小红书自动化工具。

## 安装方式

### 方式 1：Docker 部署（推荐）

```bash
# 拉取镜像
docker pull xpzouying/xiaohongshu-mcp

# 下载配置文件
wget https://raw.githubusercontent.com/xpzouying/xiaohongshu-mcp/main/docker/docker-compose.yml

# 创建数据目录
mkdir -p data

# 启动服务
docker compose up -d

# 查看日志（首次需要登录）
docker compose logs -f
```

### 方式 2：预编译二进制

1. 访问 [GitHub Releases](https://github.com/xpzouying/xiaohongshu-mcp/releases)
2. 下载对应系统的文件：
   - Windows: `xiaohongshu-mcp-windows-amd64.exe`
   - macOS (Intel): `xiaohongshu-mcp-darwin-amd64`
   - macOS (Apple Silicon): `xiaohongshu-mcp-darwin-arm64`
   - Linux: `xiaohongshu-mcp-linux-amd64`

3. 运行登录工具（首次）：
```bash
# Windows
xiaohongshu-login-windows-amd64.exe

# macOS/Linux
chmod +x xiaohongshu-login-darwin-arm64
./xiaohongshu-login-darwin-arm64
```

4. 扫码登录后，运行主程序：
```bash
./xiaohongshu-mcp-darwin-arm64
```

## 首次登录

1. 启动服务后会自动打开 Chrome 浏览器
2. 访问小红书登录页面
3. **使用扫码登录**（不推荐账号密码）
4. 登录成功后，Cookie 会自动保存到 `data` 目录
5. 后续启动无需重新登录

⚠️ **注意事项**：
- 如需验证码，**在终端输入**，不要在浏览器输入
- 不要在其他网页同时登录同一账号，会被踢下线
- Cookie 有效期约 30 天，失效后需重新登录

## 配置 MCP 客户端

### Claude Code CLI

```bash
# 添加 MCP 服务器
claude mcp add --transport http xiaohongshu-mcp http://localhost:18060/mcp

# 验证
claude mcp list
```

### Cursor

在项目根目录创建 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "xiaohongshu-mcp": {
      "url": "http://localhost:18060/mcp",
      "description": "小红书MCP服务"
    }
  }
}
```

### VSCode

1. 按 `Ctrl/Cmd + Shift + P`
2. 输入 "MCP: Add Server"
3. 选择 HTTP 方式
4. 输入 `http://localhost:18060/mcp`

## 测试 MCP 服务

```bash
# 检查服务状态
curl http://localhost:18060/mcp

# 预期返回：MCP 协议相关的信息
```

## 支持的 MCP 工具

xiaohongshu-mcp 提供以下工具：

| 工具名 | 功能 |
|-------|------|
| `search_notes` | 搜索笔记 |
| `get_note_detail` | 获取笔记详情 |
| `publish_note` | 发布图文笔记 |
| `publish_video` | 发布视频笔记 |
| `get_user_profile` | 获取用户信息 |
| `comment_note` | 评论笔记 |

## 手动测试发布

在 Claude/Cursor 中输入：

```
帮我发布一篇小红书笔记：
标题：测试笔记标题
正文：这是测试内容
配图：/path/to/image.jpg
标签：#测试 #AI
```

AI 会自动调用 `publish_note` 工具完成发布。

## 故障排查

### 服务无法启动

```bash
# 检查端口占用
lsof -i :18060  # macOS/Linux
netstat -ano | findstr 18060  # Windows

# 修改端口（docker-compose.yml）
ports:
  - "18061:18060"  # 改为 18061
```

### 登录状态失效

```bash
# 删除 Cookie 重新登录
rm -rf data/cookies.json

# 重新启动
docker compose restart
```

### MCP 连接失败

1. 确认服务已启动：`docker compose ps`
2. 确认端口正确：`curl http://localhost:18060/mcp`
3. 检查防火墙设置

## 安全建议

1. **不要分享 Cookie 文件**
2. **使用专用账号**，不要用个人主号
3. **控制发布频率**，避免触发风控
4. **本地部署**，不要在公网暴露 MCP 服务

## 更多信息

- 项目地址：https://github.com/xpzouying/xiaohongshu-mcp
- MCP 协议：https://modelcontextprotocol.io/
