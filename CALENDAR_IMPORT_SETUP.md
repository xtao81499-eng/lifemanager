# AI 日程导入模块 - 配置指南

## 本地配置

### 1. 安装依赖
```bash
pip install google-generativeai
```

### 2. 获取 Gemini API Key
1. 访问 https://aistudio.google.com/app/apikey
2. 创建新的 API Key
3. 复制 API Key

### 3. 配置 API Key
编辑 `.streamlit/secrets.toml`，添加：
```toml
GEMINI_API_KEY = "your-api-key-here"
```

### 4. 重新授权 Google Calendar（写入权限）
由于 OAuth 权限从 `calendar.readonly` 升级到 `calendar`，需要重新授权：

1. 删除现有 token：
```bash
rm config/token.json
```

2. 重新运行应用，会自动弹出浏览器授权窗口
3. 授权后会生成新的 `config/token.json`

## Streamlit Cloud 配置

### 1. 添加 Gemini API Key
在 Streamlit Cloud 项目设置中，添加 Secret：
```toml
GEMINI_API_KEY = "your-api-key-here"
```

### 2. 重新生成 refresh_token（写入权限）
由于 Cloud 环境使用 `gcp_token` 段的 refresh_token，需要本地重新授权后上传：

1. 本地删除旧 token 并重新授权（见上方步骤 4）
2. 授权完成后，读取新的 `config/token.json`
3. 在 Streamlit Cloud Secrets 中更新 `[gcp_token]` 段的所有字段：
   - `refresh_token` ← 最重要，必须更新
   - `client_id`
   - `client_secret`
   - `token_uri`

示例格式：
```toml
[gcp_token]
refresh_token = "1//0g..."
client_id = "123456789-xxx.apps.googleusercontent.com"
client_secret = "GOCSPX-xxx"
token_uri = "https://oauth2.googleapis.com/token"
```

## 使用说明

### 功能特性
- 上传备忘录截图，AI 自动解析日程
- 支持编辑事件名称、分类、评分、备注
- 10 个固定分类下拉选择
- 可创建新的 Google Calendar 分类
- 自动保存分类修正，提升未来准确率
- 批量写入 Google Calendar，进度条显示

### 日程格式要求
截图中的日程应遵循以下格式：
```
开始时间-结束时间 事件名称 评分
  备注信息（缩进）
```

示例：
```
0-8:30 睡觉 6
8:30-9:00 晨练 8
  跑步 5km
9:00-12:00 工作 9
12:00-13:00 午饭吃汉堡王 7
```

### 分类规则
AI 基于语义理解分类，非关键词匹配：
- **睡眠**：睡觉、午睡、休息
- **工作**：工作任务、会议、项目
- **餐饮**：早中晚餐、吃饭、做饭
- **运动**：锻炼、跑步、健身
- **学习**：看书、学习、课程
- **社交**：和朋友聚会、非家人聊天、酒吧
- **家庭**：和家人通话、家务
- **娱乐**：看电影、打游戏、刷视频
- **拖延**：无效时间、发呆
- **其他**：不属于以上分类

### 操作流程
1. 上传日程截图
2. 选择日程日期
3. 点击"解析日程"
4. 在预览表格中编辑分类（下拉框选择）
5. 配置日历映射（每个分类写入哪个 Google Calendar）
6. 点击"确认并写入日历"
7. AI 学习你的修正，未来更准确

## 故障排查

### 解析失败
- 检查 GEMINI_API_KEY 是否正确配置
- 确认图片格式正确（PNG/JPG/JPEG）
- 截图中日程格式是否符合要求

### 写入失败
- 确认已重新授权（calendar 权限）
- 检查 `config/token.json` 是否存在
- Cloud 环境检查 `gcp_token.refresh_token` 是否更新

### API 配额限制
Gemini API 免费额度有限，如遇配额问题：
- 等待配额重置
- 或升级 API Key 到付费计划
