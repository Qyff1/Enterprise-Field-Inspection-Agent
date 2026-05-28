import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def load_api_config(model_type: str = "openai"):
    """从 .env 环境变量加载 API 配置"""
    return {
        "api_key": os.getenv("API_KEY", ""),
        "base_url": os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "max_tokens": int(os.getenv("MAX_TOKENS", "1000")),
        "model_name": os.getenv("MODEL_NAME", "qwen3.6-plus"),
        "temperature": float(os.getenv("TEMPERATURE", "0.7")),
        "timeout": int(os.getenv("TIMEOUT", "60")),
        "max_retries": int(os.getenv("MAX_RETRIES", "3")),
        "retry_delay": float(os.getenv("RETRY_DELAY", "2.0")),
    }


# ============================================================
# 外勤行程核验配置
# ============================================================
VERIFY_CONFIG = {
    "mileage_threshold_pct": float(os.getenv("MILEAGE_THRESHOLD_PCT", "15")),
    "mileage_warn_pct": float(os.getenv("MILEAGE_WARN_PCT", "5")),
    "time_conflict_minutes": int(os.getenv("TIME_CONFLICT_MINUTES", "30")),
    "regular_location_threshold": int(os.getenv("REGULAR_LOCATION_THRESHOLD", "3")),
    "mcp_timeout_seconds": int(os.getenv("MCP_TIMEOUT_SECONDS", "10")),
    "output_dir": os.path.join(BASE_DIR, "storage", "outputs"),
}

os.makedirs(VERIFY_CONFIG["output_dir"], exist_ok=True)
