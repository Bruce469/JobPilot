"""配置：路径 / 端口 / token，均可用环境变量覆盖。"""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/

DATA_DIR = Path(os.environ.get("APP_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("APP_DB_PATH", DATA_DIR / "app.db"))

HOST = os.environ.get("APP_HOST", "127.0.0.1")
PORT = int(os.environ.get("APP_PORT", "8000"))
# ICP 备案反查服务地址（可选，自建 HG-ha/ICP_Query，部署见 scripts/icp_query/README.md）
ICP_API_URL = os.environ.get("ICP_API_URL", "").strip().rstrip("/")

APP_NAME = "JobPilot"
APP_VERSION = "0.1.0"

# 启动时生成的一次性随机 token，重启即失效
TOKEN = secrets.token_hex(32)

ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
ALLOWED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
