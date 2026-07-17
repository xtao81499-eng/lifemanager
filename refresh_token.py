"""每周续令牌小工具（云端部署用）。

背景：Google OAuth "测试"状态 + 敏感 scope，refresh_token 每 7 天失效。
云端无浏览器无法自动续期，所以每 7 天在本地电脑跑一次这个脚本：
它会弹浏览器让你重新授权，然后把要粘到 Streamlit Secrets 的 [gcp_token]
段直接打印出来，复制过去覆盖旧的即可。

用法：
    python refresh_token.py

然后把输出的整段 [gcp_token] 粘到 Streamlit Cloud 的
Settings → Secrets 里，保存。云端会自动重启并用新令牌。
"""
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
CONFIG_DIR = Path(__file__).parent / "config"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"
TOKEN_PATH = CONFIG_DIR / "token.json"


def _toml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def main() -> None:
    if not CREDENTIALS_PATH.exists():
        raise SystemExit(f"缺少 {CREDENTIALS_PATH}")

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)

    # 顺便更新本地 token.json（本地桌面版也能继续用）
    TOKEN_PATH.write_text(creds.to_json())

    data = json.loads(creds.to_json())
    fields = {
        "token": data.get("token", ""),
        "refresh_token": data.get("refresh_token", ""),
        "token_uri": data.get("token_uri", "https://oauth2.googleapis.com/token"),
        "client_id": data.get("client_id", ""),
        "client_secret": data.get("client_secret", ""),
    }

    print("\n" + "=" * 60)
    print("授权成功！把下面整段粘到 Streamlit Cloud 的 Secrets：")
    print("=" * 60 + "\n")
    print("[gcp_token]")
    for k, v in fields.items():
        print(f'{k} = "{_toml_escape(v)}"')
    print('\n# 别忘了保留你的 app_password 那一行')
    print("=" * 60)


if __name__ == "__main__":
    main()
