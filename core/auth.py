"""
Google Calendar OAuth2 认证模块
首次运行会打开浏览器完成授权，之后使用缓存的 token。

网络传输走 requests（urllib3），而非 httplib2：
httplib2 + PySocks 做 HTTPS-over-proxy 隧道不稳定，代理节点稍抖就会
抛 SSLEOFError(UNEXPECTED_EOF_WHILE_READING)。requests 的 CONNECT 隧道
稳定得多，且自动读取系统代理设置，并内置指数退避重试。
"""
import os
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
]

CONFIG_DIR = Path(__file__).parent.parent / "config"
TOKEN_PATH = CONFIG_DIR / "token.json"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"

# 代理：
# - 本地桌面版：走本地 VPN/Clash 端口（国内直连 Google 被墙）。
# - 云端（Streamlit Cloud，在美国）：直连 Google，绝不能挂本地代理，
#   否则会去连不存在的 127.0.0.1:17890 而失败。
#
# 判据不靠“猜环境”，而是绑定认证来源（确定性）：
#   走 Streamlit Secrets 认证 == 云端 == 不挂代理；
#   走本地 token.json 认证   == 本地 == 挂代理。
# 也可用环境变量 LIFEMANAGER_PROXY 显式覆盖（设为空字符串即禁用）。
LOCAL_DEFAULT_PROXY = "http://127.0.0.1:17890"


def _resolve_proxy(is_cloud: bool) -> str:
    override = os.getenv("LIFEMANAGER_PROXY")
    if override is not None:
        return override
    return "" if is_cloud else LOCAL_DEFAULT_PROXY


# 针对间歇性连接/SSL 中断的重试策略（指数退避）。
_RETRY = Retry(
    total=4,
    backoff_factor=0.8,
    status_forcelist=(500, 502, 503, 504),
    allowed_methods=frozenset(["GET", "POST"]),
)


class ProxyError(RuntimeError):
    """代理不可用时抛出，携带人类可读的提示。"""


def _make_session(creds, proxy_url: str) -> AuthorizedSession:
    """构建带认证、代理与自动重试的 requests 会话。"""
    session = AuthorizedSession(creds)
    if proxy_url:
        session.proxies.update({"http": proxy_url, "https": proxy_url})
    adapter = HTTPAdapter(max_retries=_RETRY)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class _RequestsHttp:
    """httplib2.Http 的最小兼容层，底层用 requests 会话。

    googleapiclient 的 build()/execute() 只依赖 .request(uri, method, body,
    headers) -> (response_like, content) 这一接口，这里精确实现它。
    """

    def __init__(self, session: AuthorizedSession, proxy_url: str = ""):
        self._session = session
        self._proxy_url = proxy_url

    def request(self, uri, method="GET", body=None, headers=None, **kwargs):
        import requests as _requests

        try:
            resp = self._session.request(
                method, uri, data=body, headers=headers, timeout=30
            )
        except _requests.exceptions.ProxyError as exc:
            raise ProxyError(
                f"无法连接代理 {self._proxy_url}，请确认 VPN/代理已开启且端口正确。"
            ) from exc

        # 伪造成 httplib2.Response（dict 子类 + .status 属性）
        class _Resp(dict):
            status = resp.status_code
            reason = resp.reason

        info = _Resp()
        for k, v in resp.headers.items():
            info[k.lower()] = v
        info["status"] = str(resp.status_code)
        return info, resp.content


def _creds_from_streamlit_secrets():
    """云端路径：从 Streamlit Secrets 的 [gcp_token] 段构建凭证。

    云端无浏览器、文件系统临时，无法走本地弹窗授权，也不能写 token.json。
    因此直接用预先粘贴到 Secrets 的 refresh_token 等字段构造 Credentials。
    返回 None 表示当前不是 Streamlit 环境或没配 secrets（回退到本地逻辑）。
    """
    try:
        import streamlit as st
    except ModuleNotFoundError:
        return None

    # st.secrets 访问在无 secrets 文件时会抛异常，需保护。
    try:
        if "gcp_token" not in st.secrets:
            return None
        tok = st.secrets["gcp_token"]
    except Exception:
        return None

    creds = Credentials(
        token=tok.get("token"),
        refresh_token=tok["refresh_token"],
        token_uri=tok.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=tok["client_id"],
        client_secret=tok["client_secret"],
        scopes=SCOPES,
    )
    if not creds.valid:
        creds.refresh(Request())
    return creds


def _get_credentials_with_source():
    """返回 (creds, is_cloud)。is_cloud 决定是否挂本地代理。

    两条路径：
    - 云端（Streamlit Cloud）：从 st.secrets 读 refresh_token，不写文件。
    - 本地（桌面版）：读/写 config/token.json，过期自动弹浏览器续期。
    """
    # 云端优先
    cloud_creds = _creds_from_streamlit_secrets()
    if cloud_creds is not None:
        return cloud_creds, True

    # 本地逻辑
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"缺少 OAuth 凭证文件: {CREDENTIALS_PATH}\n"
                    "请从 Google Cloud Console 下载 OAuth 2.0 Client ID 的 JSON 文件，"
                    "重命名为 credentials.json 并放到 config/ 目录下。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json())

    return creds, False


def get_credentials():
    """获取已认证的 Google OAuth2 凭证（向后兼容的公开接口）。"""
    creds, _ = _get_credentials_with_source()
    return creds


def _build_service(api: str, version: str):
    """构建已认证的 Google API service 对象（传输走 requests）。"""
    creds, is_cloud = _get_credentials_with_source()
    proxy_url = _resolve_proxy(is_cloud)
    session = _make_session(creds, proxy_url)
    http = _RequestsHttp(session, proxy_url)
    return build(api, version, http=http)


def get_calendar_service():
    """获取已认证的 Google Calendar API service 对象。"""
    return _build_service("calendar", "v3")


def get_drive_service():
    """获取已认证的 Google Drive API service 对象。"""
    return _build_service("drive", "v3")
