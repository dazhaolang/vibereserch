"""简单的后端健康检查脚本。

在运行前确保 FastAPI 服务已启动（默认 http://127.0.0.1:8000）。
通过检查关键探活接口来快速发现不可用的依赖。
"""

from __future__ import annotations

import os
from typing import Any, Dict

import requests

BASE_URL = os.environ.get("VIBERES_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT = float(os.environ.get("VIBERES_HTTP_TIMEOUT", "10"))


def fetch_json(path: str) -> Dict[str, Any]:
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def assert_status_ok(data: Dict[str, Any], field: str = "status") -> None:
    status = data.get(field)
    assert status in {"ok", "healthy"}, f"Unexpected {field}: {status!r}"


def assert_no_unhealthy_components(data: Dict[str, Any]) -> None:
    components = data.get("components", [])
    unhealthy = [c for c in components if c.get("status") == "unhealthy"]
    assert not unhealthy, f"Unhealthy components detected: {unhealthy}"


def main() -> None:
    print(f"🔎 Checking backend health on {BASE_URL}")

    live_data = fetch_json("/live")
    assert_status_ok(live_data)
    print("✅ /live passed")

    healthz_data = fetch_json("/healthz")
    assert_status_ok(healthz_data)
    assert_no_unhealthy_components(healthz_data)
    print("✅ /healthz passed")

    readyz_data = fetch_json("/readyz")
    assert_status_ok(readyz_data)
    assert_no_unhealthy_components(readyz_data)
    print("✅ /readyz passed")

    health_data = fetch_json("/health")
    status = health_data.get("status")
    assert status in {"healthy", "degraded"}, f"/health reported unexpected status: {status}"
    print("✅ /health summary looks good")

    print("🎉 All health checks succeeded")


if __name__ == "__main__":
    main()
