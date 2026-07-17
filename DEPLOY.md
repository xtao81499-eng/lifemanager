# Life Manager 云部署指南（Streamlit Community Cloud）

目标：把应用部署到云上，手机在任何网络（4G/外网）都能通过一个固定网址访问，
**不依赖公司电脑、不碰公司网络**。

---

## 一、前置：代码要能上 GitHub

云平台从 GitHub 拉代码，所以先把项目传上去。

1. 注册 GitHub 账号（https://github.com ，若已有跳过）。
2. 新建一个 **Private（私有）** 仓库，名字随意（如 `lifemanager`）。
   ⚠️ 一定要选 Private——里面虽然不含密钥，但没必要公开。
3. 本项目已初始化好 git 且 `.gitignore` 已排除密钥文件
   （`config/credentials.json`、`config/token.json`、`.env` 都不会上传）。
   按 GitHub 新仓库页面给的命令 push 上去即可（形如）：
   ```
   git remote add origin https://github.com/<你的用户名>/lifemanager.git
   git branch -M main
   git push -u origin main
   ```

## 二、部署到 Streamlit Cloud

1. 打开 https://share.streamlit.io ，用 **GitHub 账号登录**。
2. 点 **New app** → 选你刚推的仓库、分支 `main`、主文件 `app.py`。
3. 点 Deploy。首次部署会装依赖，等几分钟。

## 三、填 Secrets（关键，密钥不进 git 就靠这里）

在 Streamlit Cloud 的 app 页面 → 右下 **Manage app** → **Settings → Secrets**，
粘入下面内容（**值替换成你自己的**）：

```toml
app_password = "你自己设一个强密码"

[gcp_token]
token = "..."
refresh_token = "..."
token_uri = "https://oauth2.googleapis.com/token"
client_id = "..."
client_secret = "..."
```

**这些值从哪来？** 在本地电脑项目目录运行：
```
python refresh_token.py
```
它会弹浏览器让你用 Google 账号授权，然后**直接打印出上面 [gcp_token] 那一整段**，
复制粘贴过去即可。`app_password` 那行自己加。

保存后云端会自动重启。

## 四、手机访问

1. Streamlit 会给你一个固定网址，形如 `https://xxx.streamlit.app`。
2. 手机浏览器打开 → 输入你设的 `app_password` → 看到数据。
3. 添加到主屏幕当 App 用：
   - iPhone Safari：分享 → 添加到主屏幕
   - 安卓 Chrome：⋮ → 添加到主屏幕 / 安装应用

---

## 每 7 天要做一次的事（令牌续期）

因为 Google 授权处于"测试"状态 + 敏感权限，`refresh_token` **每 7 天失效**。
失效后云端会加载不出数据。续期方法（约 1 分钟，在家里电脑做，不碰公司）：

1. 本地跑 `python refresh_token.py` → 重新授权。
2. 把新打印出的 `[gcp_token]` 段粘回 Streamlit Secrets（覆盖旧的），保存。

**想彻底免掉这一步**：把 Google OAuth 应用"发布为正式"（Google Cloud Console
→ OAuth 同意屏幕 → 发布）。敏感 scope 可能需 Google 审核（数天到数周）。
以后嫌每周烦了再做。

---

## 本地桌面版不受影响

以上全部只影响云端。本地桌面版（双击桌面 Life Manager）逻辑不变：
- 无 secrets → 密码门自动放行
- 走本地 `token.json` + 本地代理（VPN）
- 令牌过期自动弹浏览器续期
