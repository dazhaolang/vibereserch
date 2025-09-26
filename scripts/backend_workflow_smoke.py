#!/usr/bin/env python3
"""Backend workflow smoke test for VibResearch.

This script walks through a representative set of API calls:
  1. Register (or login) a QA user
  2. Authenticate to get a JWT token
  3. Create a project
  4. Fetch project and task intelligence endpoints
  5. Clean up the created project

Usage example:
  python3 scripts/backend_workflow_smoke.py \
    --base-url http://localhost:8000 \
    --email qa_runner@example.com \
    --password QaRunner123! \
    --output backend_workflow_results.json
"""

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
    payload: Optional[Dict[str, Any]] = None


class BackendWorkflowRunner:
    def __init__(self, base_url: str, email: Optional[str], password: Optional[str], timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.results: list[StepResult] = []
        self.token: Optional[str] = None
        self.user_id: Optional[int] = None
        self.project_id: Optional[int] = None

    # ---------- helper utilities ---------------------------------

    def _record(self, result: StepResult) -> None:
        self.results.append(result)
        status = "PASS" if result.ok else "FAIL"
        status_code = f" ({result.status_code})" if result.status_code is not None else ""
        print(f"[{status}] {result.name}{status_code} {result.detail}")

    def _post(self, path: str, json_payload: Dict[str, Any]) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else None
        return self.session.post(url, json=json_payload, headers=headers, timeout=self.timeout)

    def _get(self, path: str) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else None
        return self.session.get(url, headers=headers, timeout=self.timeout)

    def _delete(self, path: str) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else None
        return self.session.delete(url, headers=headers, timeout=self.timeout)

    # ---------- workflow steps ------------------------------------

    def register_or_login(self) -> None:
        email = self.email or f"qa_flow_{int(time.time())}@example.com"
        password = self.password or "QaFlow123!"
        register_payload = {
            "email": email,
            "password": password,
            "username": email.split("@")[0],
        }
        print(f"🔐 Using account: {email}")

        response = self.session.post(
            f"{self.base_url}/api/auth/register",
            json=register_payload,
            timeout=self.timeout,
        )

        if response.status_code == 200:
            payload = response.json()
            self.token = payload.get("access_token")
            self.user_id = payload.get("user_info", {}).get("id")
            self._record(
                StepResult(
                    name="register",
                    ok=True,
                    status_code=response.status_code,
                    payload={"email": email},
                )
            )
        elif response.status_code == 400:
            # Already exists, fall back to login
            login_payload = {"email": email, "password": password}
            login_resp = self.session.post(
                f"{self.base_url}/api/auth/login",
                json=login_payload,
                timeout=self.timeout,
            )
            if login_resp.status_code == 200:
                payload = login_resp.json()
                self.token = payload.get("access_token")
                self.user_id = payload.get("user_info", {}).get("id")
                self._record(
                    StepResult(
                        name="login",
                        ok=True,
                        status_code=login_resp.status_code,
                        payload={"email": email},
                    )
                )
            else:
                self._record(
                    StepResult(
                        name="login",
                        ok=False,
                        status_code=login_resp.status_code,
                        detail=login_resp.text,
                    )
                )
        else:
            self._record(
                StepResult(
                    name="register",
                    ok=False,
                    status_code=response.status_code,
                    detail=response.text,
                )
            )

        # Persist chosen credentials in case later steps need them
        self.email = email
        self.password = password

    def fetch_user_profile(self) -> None:
        if not self.token:
            self._record(StepResult(name="user_profile", ok=False, status_code=None, detail="missing token"))
            return
        response = self._get("/api/user/profile")
        ok = response.status_code == 200
        self._record(
            StepResult(
                name="user_profile",
                ok=ok,
                status_code=response.status_code,
                detail="" if ok else response.text,
            )
        )

    def create_project(self) -> None:
        if not self.token:
            self._record(StepResult(name="project_create", ok=False, status_code=None, detail="missing token"))
            return
        payload = {
            "name": f"QA Workflow Project {int(time.time())}",
            "description": "Automated integration smoke project",
            "category": "workflow",
        }
        response = self._post("/api/project/create-empty", payload)
        ok = response.status_code == 200
        if ok:
            self.project_id = response.json().get("id")
        self._record(
            StepResult(
                name="project_create",
                ok=ok,
                status_code=response.status_code,
                detail="" if ok else response.text,
                payload={"project_id": self.project_id} if ok else None,
            )
        )

    def project_insights(self) -> None:
        if not self.project_id:
            self._record(StepResult(name="project_stats", ok=False, status_code=None, detail="missing project id"))
            return
        stats_resp = self._get(f"/api/project/{self.project_id}/statistics")
        tasks_resp = self._get(f"/api/project/{self.project_id}/tasks")
        self._record(
            StepResult(
                name="project_stats",
                ok=stats_resp.status_code == 200,
                status_code=stats_resp.status_code,
                detail="" if stats_resp.status_code == 200 else stats_resp.text,
            )
        )
        self._record(
            StepResult(
                name="project_tasks",
                ok=tasks_resp.status_code == 200,
                status_code=tasks_resp.status_code,
                detail="" if tasks_resp.status_code == 200 else tasks_resp.text,
            )
        )

    def task_dashboards(self) -> None:
        for name, path in [
            ("tasks_list", "/api/tasks/list"),
            ("tasks_overview", "/api/tasks/overview"),
            ("tasks_statistics", "/api/tasks/statistics"),
            ("tasks_performance", "/api/tasks/performance_metrics"),
        ]:
            resp = self._get(path)
            self._record(
                StepResult(
                    name=name,
                    ok=resp.status_code == 200,
                    status_code=resp.status_code,
                    detail="" if resp.status_code == 200 else resp.text,
                )
            )

    def performance_panels(self) -> None:
        for name, path in [
            ("performance_status", "/api/performance/status"),
            ("performance_dashboard", "/api/performance/dashboard"),
            ("performance_recommend", "/api/performance/recommendations/optimization"),
        ]:
            resp = self._get(path)
            self._record(
                StepResult(
                    name=name,
                    ok=resp.status_code == 200,
                    status_code=resp.status_code,
                    detail="" if resp.status_code == 200 else resp.text,
                )
            )

    def literature_overview(self) -> None:
        resp = self._get("/api/literature/processing-methods")
        self._record(
            StepResult(
                name="literature_methods",
                ok=resp.status_code == 200,
                status_code=resp.status_code,
                detail="" if resp.status_code == 200 else resp.text,
            )
        )

    def cleanup(self) -> None:
        if not self.project_id:
            return
        resp = self._delete(f"/api/project/{self.project_id}")
        self._record(
            StepResult(
                name="project_cleanup",
                ok=resp.status_code in {200, 404},
                status_code=resp.status_code,
                detail="" if resp.status_code in {200, 404} else resp.text,
            )
        )

    # ---------- orchestration ------------------------------------

    def run(self) -> None:
        self.register_or_login()
        if not self.token:
            return
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.fetch_user_profile()
        self.create_project()
        self.project_insights()
        self.task_dashboards()
        self.performance_panels()
        self.literature_overview()
        self.cleanup()

    def summary(self) -> Dict[str, Any]:
        totals = {"PASS": 0, "FAIL": 0}
        for result in self.results:
            totals["PASS" if result.ok else "FAIL"] += 1
        return {
            "base_url": self.base_url,
            "email": self.email,
            "results": [asdict(r) for r in self.results],
            "summary": totals,
            "generated_at": int(time.time()),
        }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backend workflow smoke test")
    parser.add_argument("--base-url", default=os.getenv("VIBERESEARCH_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--email", default=os.getenv("VIBERESEARCH_TEST_EMAIL"))
    parser.add_argument("--password", default=os.getenv("VIBERESEARCH_TEST_PASSWORD"))
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--output", help="Write detailed JSON results to file")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    runner = BackendWorkflowRunner(args.base_url, args.email, args.password, args.timeout)
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

