# 飞书机器人交互式审核配置

## 方案对比

| 方案 | 难度 | 效果 | 需要条件 |
|------|------|------|---------|
| **方案 A** | ⭐ 简单 | 机器人发卡片，点击后跳转到 Web UI 完成审核 | 只需 Webhook URL |
| **方案 B** | ⭐⭐⭐ 复杂 | 直接在飞书里点击按钮完成审核 | 需要公网服务器 + 域名 |

---

## 方案 A：简单版（推荐）

适用于没有公网服务器的用户。机器人发送带链接的卡片，点击跳转到 Web UI 完成审核。

### 效果预览

```
📱 新内容待审核
━━━━━━━━━━━━━━━━
标题：
🚀 2024年最值得学的AI工具

正文预览：
姐妹们！今天给大家安利几个AI神器...

标签：#AI工具 #效率提升

[✅ 前往审核]  [❌ 删除]
```

点击「前往审核」→ 自动打开 Web UI 并定位到该内容 → 点击通过/拒绝

### 配置步骤

1. **创建飞书群机器人**
   - 打开飞书群设置 → 群机器人 → 添加机器人
   - 选择「自定义机器人」
   - 复制 **Webhook 地址**

2. **配置环境变量**
   ```bash
   # .env 文件
   FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx
   
   # 启用机器人审核模式
   FEISHU_BOT_MODE=webhook
   ```

3. **启动服务**
   ```bash
   ./deploy.sh restart
   ```

### 使用流程

1. 系统生成内容 → 飞书群收到卡片消息
2. 你点击「前往审核」→ 浏览器打开 Web UI
3. 在 Web UI 中点击「通过」或「拒绝」
4. 飞书群收到结果通知

---

## 方案 B：完整交互版

直接在飞书卡片上点击按钮完成审核，无需跳转到 Web UI。

### 效果预览

```
📱 新内容待审核
━━━━━━━━━━━━━━━━
标题：🚀 2024年最值得学的AI工具
正文：姐妹们！今天给大家安利...

[✅ 通过并发布]  [❌ 不通过]  [👁️ 查看]
```

点击「通过并发布」→ 立即发布到小红书 → 卡片更新为成功状态

### 前置条件

- 有一个公网可访问的服务器（或内网穿透）
- 一个域名（或 DDNS）
- 服务器需开放 443 端口

### 配置步骤

#### 1. 创建飞书应用

1. 访问 https://open.feishu.cn/app
2. 创建「企业自建应用」
3. 记录 **App ID** 和 **App Secret**

#### 2. 配置事件订阅

1. 进入应用详情 → 「事件与回调」
2. 设置 **请求地址 URL**：
   ```
   https://你的域名/api/feishu/webhook
   ```
3. 点击「保存」验证连接

#### 3. 订阅事件

添加以下事件：
- `im.message.receive_v1` - 接收消息
- `card.action.trigger` - 卡片按钮点击

#### 4. 配置权限

添加以下权限：
- `im:chat:readonly` - 获取群组信息
- `im:message.group_msg` - 发送群消息
- `im:message:send_as_bot` - 以机器人身份发送消息

#### 5. 发布应用

1. 「版本管理与发布」→ 创建版本
2. 申请发布 → 管理员审批

#### 6. 将机器人加入群聊

1. 在飞书群设置中添加机器人
2. 选择你创建的应用

#### 7. 配置环境变量

```bash
# .env 文件
FEISHU_APP_ID=cli_xxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxx
FEISHU_VERIFY_TOKEN=你的校验Token
FEISHU_ENCRYPT_KEY=你的加密密钥（可选）

# 启用完整交互模式
FEISHU_BOT_MODE=interactive
```

#### 8. 配置回调路由

确保你的服务器可以通过以下地址访问：
```
https://你的域名/api/feishu/webhook
```

需要在路由器/NAS 上做端口转发：
- 外部 443 → 内部 9999（或你配置的端口）

---

## 方案 A vs 方案 B 对比

| 功能 | 方案 A (Webhook) | 方案 B (完整交互) |
|------|-----------------|------------------|
| 配置难度 | ⭐ 简单 | ⭐⭐⭐ 复杂 |
| 是否需要公网 | ❌ 不需要 | ✅ 需要 |
| 审核体验 | 需跳转 Web UI | 直接在飞书完成 |
| 实时反馈 | 一般 | 好 |
| 适用场景 | 个人/小团队 | 企业/高频使用 |

**推荐**：先从方案 A 开始使用，如果需要更好的体验再升级到方案 B。

---

## 常见问题

### Q: 为什么方案 A 点击按钮没有反应？

方案 A 使用的是 Webhook 机器人，它**无法接收按钮点击事件**。按钮只是链接，需要跳转到 Web UI。

### Q: 可以用 ngrok 做内网穿透吗？

可以。用 ngrok 暴露本地服务：
```bash
ngrok http 9999
```
然后使用 ngrok 提供的 https 地址配置飞书事件订阅。

**注意**：ngrok 免费版地址会变化，每次重启需要重新配置。

### Q: 飞书收不到消息怎么办？

检查：
1. Webhook URL 是否正确
2. 服务器是否能访问飞书（防火墙）
3. 查看应用日志：`docker logs xhs-web | grep feishu`

### Q: 可以私聊机器人审核吗？

方案 B 支持。需要在飞书开放平台 → 机器人 → 开启「单聊模式」。

---

## 快速测试

配置完成后，测试消息发送：

```bash
# 进入容器
docker exec -it xhs-web bash

# 运行测试脚本
python -c "
from feishu_bot import get_feishu_bot
from content_generator import ContentItem

bot = get_feishu_bot()
item = ContentItem(
    id='test_001',
    title='测试标题',
    content='这是测试内容',
    tags=['#测试'],
    summary='测试摘要',
    keywords=['测试']
)
bot.send_content_for_approval(item)
"
```
