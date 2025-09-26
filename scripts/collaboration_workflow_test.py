#!/usr/bin/env python3
"""Collaboration workflow API test for VibResearch."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Sequence

import requests

@dataclass
class StepResult:
    name: str
    ok: bool
    status_code: Optional[int]
    detail: str = ""
    response: Optional[Dict[str, Any]] = None

class CollaborationWorkflowRunner:
    def __init__(self, base_url: str, email: str, password: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.results: list[StepResult] = []
        self.token: Optional[str] = None
        self.project_id: Optional[int] = None
        self.workspace_id: Optional[str] = None

    def _record(self, result: StepResult) -> None:
        self.results.append(result)
        status = "PASS" if result.ok else "FAIL"
        code = f" ({result.status_code})" if result.status_code is not None else ""
        print(f"[{status}] {result.name}{code} {result.detail}")

    def _post(self, path: str, payload: Dict[str, Any]) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.token}"}
        return self.session.post(url, json=payload, headers=headers, timeout=self.timeout)

    def _get(self, path: str) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.token}"}
        return self.session.get(url, headers=headers, timeout=self.timeout)

    def _delete(self, path: str) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.token}"}
        return self.session.delete(url, headers=headers, timeout=self.timeout)

    def login(self) -> None:
        resp = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"email": self.email, "password": self.password},
            timeout=self.timeout,
        )
        if resp.status_code == 200:
            payload = resp.json()
            self.token = payload.get("access_token")
            self._record(StepResult("login", True, resp.status_code))
        else:
            self._record(StepResult("login", False, resp.status_code, resp.text))

    def create_project(self) -> None:
        resp = self._post(
            "/api/project/create-empty",
            {
                "name": f"Collab QA Project {int(time.time())}",
                "description": "Collaboration workflow test",
                "category": "collaboration",
            },
        )
        ok = resp.status_code == 200
        if ok:
            self.project_id = resp.json().get("id")
        self._record(
            StepResult(
                "project_create",
                ok,
                resp.status_code,
                "" if ok else resp.text,
                resp.json() if ok else None,
            )
        )

    def create_workspace(self) -> None:
        payload = {
            "project_id": self.project_id,
            "workspace_name": "协作测试工作区",
            "workspace_description": "API 自动化创建",
            "collaboration_settings": {"visibility": "private"},
        }
        resp = self._post("/api/collaborative-workspace/create", payload)
        ok = resp.status_code == 200
        if ok:
            data = resp.json()
            self.workspace_id = data.get("workspace", {}).get("workspace_id")
        self._record(
            StepResult(
                "workspace_create",
                ok,
                resp.status_code,
                "" if ok else resp.text,
                resp.json() if ok else None,
            )
        )

    def join_workspace(self) -> None:
        if not self.workspace_id:
            self._record(StepResult("workspace_join", False, None, "workspace_id missing"))
            return
        resp = self._post(
            "/api/collaborative-workspace/join",
            {"workspace_id": self.workspace_id, "role": "editor"},
        )
        self._record(
            StepResult(
                "workspace_join",
                resp.status_code == 200,
                resp.status_code,
                "" if resp.status_code == 200 else resp.text,
                resp.json() if resp.status_code == 200 else None,
            )
        )

    def create_annotation(self) -> None:
        if not self.workspace_id:
            self._record(StepResult("annotation_create", False, None, "workspace_id missing"))
            return
        payload = {
            "workspace_id": self.workspace_id,
            "literature_id": 0,
            "annotation_data": {
                "content": "自动化测试注释",
                "highlight_text": "",
                "position": {"page": 1, "offset": 0},
            },
        }
        resp = self._post("/api/collaborative-workspace/annotations", payload)
        self._record(
            StepResult(
                "annotation_create",
                resp.status_code == 200,
                resp.status_code,
                "" if resp.status_code == 200 else resp.text,
                resp.json() if resp.status_code == 200 else None,
            )
        )

    def share_insight(self) -> None:
        if not self.workspace_id:
            self._record(StepResult("insight_share", False, None, "workspace_id missing"))
            return
        payload = {
            "workspace_id": self.workspace_id,
            "insight_data": {
                "title": "自动化洞察",
                "summary": "此洞察由测试脚本生成",
                "category": "analysis",
                "tags": ["automation"],
            },
        }
        resp = self._post("/api/collaborative-workspace/insights", payload)
        self._record(
            StepResult(
                "insight_share",
                resp.status_code == 200,
                resp.status_code,
                "" if resp.status_code == 200 else resp.text,
                resp.json() if resp.status_code == 200 else None,
            )
        )

    def get_status(self) -> None:
        if not self.workspace_id:
            self._record(StepResult("workspace_status", False, None, "workspace_id missing"))
            return
        resp = self._get(f"/api/collaborative-workspace/{self.workspace_id}/status")
        self._record(
            StepResult(
                "workspace_status",
                resp.status_code == 200,
                resp.status_code,
                "" if resp.status_code == 200 else resp.text,
                resp.json() if resp.status_code == 200 else None,
            )
        )

    def list_annotations(self) -> None:
        if not self.workspace_id:
            self._record(StepResult("annotations_list", False, None, "workspace_id missing"))
            return
        resp = self._get(f"/api/collaborative-workspace/{self.workspace_id}/annotations")
        self._record(
            StepResult(
                "annotations_list",
                resp.status_code == 200,
                resp.status_code,
                "" if resp.status_code == 200 else resp.text,
                resp.json() if resp.status_code == 200 else None,
            )
        )

    def list_insights(self) -> None:
        if not self.workspace_id:
            self._record(StepResult("insights_list", False, None, "workspace_id missing"))
            return
        resp = self._get(f"/api/collaborative-workspace/{self.workspace_id}/insights")
        self._record(
            StepResult(
                "insights_list",
                resp.status_code == 200,
                resp.status_code,
                "" if resp.status_code == 200 else resp.text,
                resp.json() if resp.status_code == 200 else None,
            )
        )

    def leave_workspace(self) -> None:
        if not self.workspace_id:
            return
        resp = self._delete(f"/api/collaborative-workspace/{self.workspace_id}/leave")
        self._record(
            StepResult(
                "workspace_leave",
                resp.status_code in {200, 404},
                resp.status_code,
                "" if resp.status_code in {200, 404} else resp.text,
            )
        )

    def cleanup_project(self) -> None:
        if not self.project_id:
            return
        resp = self._delete(f"/api/project/{self.project_id}")
        self._record(
            StepResult(
                "project_cleanup",
                resp.status_code in {200, 404},
                resp.status_code,
                "" if resp.status_code in {200, 404} else resp.text,
            )
        )

    def run(self) -> None:
        self.login()
        if not self.token:
            return
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.create_project()
        if not self.project_id:
            return
        self.create_workspace()
        if not self.workspace_id:
            return
        self.join_workspace()
        self.create_annotation()
        self.share_insight()
        self.get_status()
        self.list_annotations()
        self.list_insights()
        self.leave_workspace()
        self.cleanup_project()

    def summary(self) -> Dict[str, Any]:
        totals = {"PASS": 0, "FAIL": 0}
        for result in self.results:
            totals["PASS" if result.ok else "FAIL"] += 1
        return {
            "base_url": self.base_url,
            "results": [asdict(r) for r in self.results],
            "summary": totals,
            "generated_at": int(time.time()),
        }

def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collaboration workflow API test")
    parser.add_argument("--base-url", default=os.getenv("VIBERESEARCH_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--output", help="Write JSON report to file")
    return parser.parse_args(argv)

def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    runner = CollaborationWorkflowRunner(args.base_url, args.email, args.password, args.timeout)
    runner.run()
    summary = runner.summary()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
        print(f"📝 Results written to {args.output}")
    failed = summary["summary"]["FAIL"]
    print(f"✅ PASS: {summary['summary']['PASS']} | ❌ FAIL: {failed}")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
