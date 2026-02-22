# 飞书多维表格配置指南

## 1. 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/app)
2. 点击「创建企业自建应用」
3. 填写应用名称：「小红书内容管理」
4. 选择应用类型：「企业自建应用」

## 2. 获取凭证

1. 进入应用详情页
2. 在「凭证与基础信息」中获取：
   - **App ID**
   - **App Secret**

将这些值填入 `.env` 文件：

```bash
FEISHU_APP_ID=cli_xxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxx
```

## 3. 添加权限

进入「权限管理」，添加以下权限：

- `bitable:record` - 多维表格记录操作
- `bitable:app` - 多维表格应用操作

## 4. 创建多维表格

1. 在飞书中创建一个多维表格
2. 添加以下字段：

| 字段名称 | 字段类型 | 说明 |
|---------|---------|------|
| 标题 | 文本 | 小红书笔记标题 |
| 正文 | 多行文本 | 笔记正文内容 |
| 标签 | 文本 | #标签，逗号分隔 |
| 摘要 | 文本 | 内容一句话摘要 |
| 关键词 | 文本 | 搜索关键词 |
| 图片路径 | 文本 | 本地图片路径 |
| 状态 | 单选 | 待审核/已通过/已拒绝/已发布 |
| 创建时间 | 日期时间 | 自动生成 |
| 发布时间 | 日期时间 | 实际发布时间 |
| 笔记ID | 文本 | 发布后的小红书笔记ID |

## 5. 获取表格信息

1. 打开多维表格
2. 从 URL 中获取：
   - `app_token`: `https://xxx.feishu.cn/base/APP_TOKEN?table=TABLE_ID`
   - `table_id`: 同上

填入 `.env` 文件：

```bash
FEISHU_BITABLE_APP_TOKEN=xxxxxxxxxx
FEISHU_BITABLE_TABLE_ID=xxxxxxxxxx
```

## 6. 发布应用

1. 进入「版本管理与发布」
2. 创建版本，填写更新说明
3. 点击「申请发布」
4. 让管理员审批通过

## 7. 配置机器人通知（可选）

1. 在飞书群中添加「自定义机器人」
2. 获取 Webhook URL
3. 填入 `.env` 文件：

```bash
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx
```

## 8. 配置自动化流程（推荐）

在多维表格中设置自动化：

### 流程 1：状态变更通知

```
触发条件：当「状态」字段变更为「已通过」
执行操作：发送 HTTP POST 请求到发布服务
```

### 流程 2：发布完成通知

```
触发条件：当「状态」字段变更为「已发布」
执行操作：发送飞书消息通知
```

## 9. 验证配置

运行测试脚本验证飞书配置：

```bash
python test.py
```

## 常见问题

### 1. 提示 "app permission error"

- 检查权限是否已添加
- 确认应用已发布
- 检查 App ID 和 Secret 是否正确

### 2. 无法找到表格

- 确认应用已授权访问该表格
- 检查 app_token 和 table_id 是否正确

### 3. 字段映射失败

- 确保字段名称与代码中一致
- 检查字段类型是否正确

## 不使用飞书的替代方案

如果不想使用飞书，可以将配置中的 `enabled` 设为 `false`：

```yaml
feishu:
  enabled: false
  approval_mode: "auto"
```

系统会自动使用本地 JSON 文件存储，通过修改文件来模拟审批。
