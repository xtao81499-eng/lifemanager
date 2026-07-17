# Life Manager — 你的个人 Life OS

## 快速开始

### 1. 获取 Google Calendar API 凭证

1. 打开 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目（或选择已有项目）
3. 启用 **Google Calendar API**:
   - 左侧菜单 → API 和服务 → 库 → 搜索 "Google Calendar API" → 启用
4. 创建 OAuth 2.0 凭证:
   - API 和服务 → 凭据 → 创建凭据 → OAuth 客户端 ID
   - 应用类型选 **桌面应用**
   - 下载 JSON 文件，重命名为 `credentials.json`，放入 `config/` 目录

### 2. 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

### 3. 运行测试

```bash
# 先跑解析器单元测试（不需要 API）
python tests/test_parser.py

# 再跑完整流程测试（需要 credentials.json）
python test_fetch.py
```

首次运行 `test_fetch.py` 会打开浏览器完成 OAuth 授权。

## 项目结构

```
lifemanager/
├── config/
│   ├── credentials.json   # Google OAuth 凭证（不入 Git）
│   └── token.json         # 缓存的 access token（不入 Git）
├── core/
│   ├── auth.py            # OAuth2 认证
│   ├── calendar_sync.py   # 日历事件抓取
│   └── parser.py          # 事件标题解析器
├── tests/
│   └── test_parser.py     # 解析器单元测试
├── data/                  # 缓存数据（不入 Git）
├── .streamlit/            # Streamlit 配置
├── test_fetch.py          # 完整流程测试脚本
├── requirements.txt
└── README.md
```

## 日历事件格式

在 Google Calendar 中按以下格式记录：

```
[分类] 任务描述 评分/10
```

示例:
- `[工作] 调试蓝牙模块 7.5/10`
- `[学习] 深度复盘 (8.5/10)`
- `[健身] 跑步5km`
- `[睡眠] 23:00-07:00`
- `09:00-10:00 [工作] 写周报 6/10`
