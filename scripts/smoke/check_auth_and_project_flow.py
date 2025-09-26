"""端到端验证：注册 -> 登录 -> 创建项目 -> 查询/删除项目。

运行前请确保后端服务已启动，并允许使用脚本生成的随机账号。
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict

import requests

BASE_URL = os.environ.get("VIBERES_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = float(os.environ.get("VIBERES_HTTP_TIMEOUT", "15"))
PASSWORD = os.environ.get("VIBERES_SMOKE_PASSWORD", "Test@123456")


def post_json(path: str, payload: Dict[str, Any], token: str | None = None) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.post(
        f"{BASE_URL}{path}", json=payload, headers=headers, timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def get_json(path: str, token: str | None = None) -> Dict[str, Any]:
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def delete_json(path: str, token: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=TIMEOUT)

    if response.status_code == 405:
        print("⚠️ DELETE not supported by this deployment, skipping cleanup")
        return {"success": False, "skipped": True}

    response.raise_for_status()
    if response.content:
        return response.json()
    return {}


def main() -> None:
    unique_id = uuid.uuid4().hex[:12]
    email = f"smoke_{unique_id}@example.com"
    username = f"smoke_{unique_id}"

    print(f"🧪 Registering new user {email}")
    token_payload = post_json(
        "/api/auth/register",
        {
            "email": email,
            "username": username,
            "password": PASSWORD,
            "full_name": "Smoke Tester",
            "institution": "QA Lab",
            "research_field": "Smoke Testing",
        },
    )

    access_token = token_payload["access_token"]
    assert token_payload["user_info"]["email"] == email
    print("✅ Registration succeeded")

    print("🔐 Logging in with registered credentials")
    login_payload = post_json(
        "/api/auth/login", {"email": email, "password": PASSWORD}
    )
    login_token = login_payload["access_token"]
    assert login_token, "Login response missing access token"
    print("✅ Login succeeded")

    print("🙋 Fetching profile via /api/auth/me")
    profile = get_json("/api/auth/me", token=login_token)
    assert profile["email"] == email
    print("✅ Profile retrieved")

    print("📁 Creating empty project")
    project_payload = post_json(
        "/api/project/create-empty",
        {"name": f"Smoke Project {unique_id}", "description": "Smoke test project"},
        token=login_token,
    )
    project_id = project_payload["id"]
    assert project_payload["name"].startswith("Smoke Project")
    print(f"✅ Project created (id={project_id})")

    print("📋 Listing projects to ensure presence")
    project_list = get_json("/api/project/list", token=login_token)
    ids = [item["id"] for item in project_list]
    assert project_id in ids, "Created project not found in list"
    print("✅ Project visible in list")

    print("🧹 Deleting project to keep workspace clean")
    delete_payload = delete_json(f"/api/project/{project_id}", token=login_token)
    if delete_payload.get("skipped"):
        print("ℹ️ Project deletion not available; leaving smoke project in place")
    else:
        assert delete_payload.get("success") is True
        print("✅ Project deleted")

    print("🎉 Auth & project workflow passed")


if __name__ == "__main__":
    main()
