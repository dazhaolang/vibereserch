#!/usr/bin/env python3
"""Performance optimization API validator."""

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

class PerformanceInsightsRunner:
    def __init__(self, base_url: str, email: str, password: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.token: Optional[str] = None
        self.results: list[StepResult] = []
        self.project_id: Optional[int] = None

    def _record(self, result: StepResult) -> None:
        self.results.append(result)
        status = "PASS" if result.ok else "FAIL"
        code = f" ({result.status_code})" if result.status_code is not None else ""
        print(f"[{status}] {result.name}{code} {result.detail}")

    def login(self) -> None:
        resp = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"email": self.email, "password": self.password},
            timeout=self.timeout,
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            self._record(StepResult("login", True, resp.status_code))
        else:
            self._record(StepResult("login", False, resp.status_code, resp.text))

    def _get(self, path: str) -> requests.Response:
        url = f"{self.base_url}{path}"
        return self.session.get(url, timeout=self.timeout)

    def _post(self, path: str, payload: Dict[str, Any]) -> requests.Response:
        url = f"{self.base_url}{path}"
        return self.session.post(url, json=payload, timeout=self.timeout)

    def create_project(self) -> None:
        payload = {
            "name": f"Performance QA Project {int(time.time())}",
            "description": "Performance API 测试项目",
            "category": "performance",
        }
        resp = self._post("/api/project/create-empty", payload)
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

    def cleanup_project(self) -> None:
        if not self.project_id:
            return
        resp = self.session.delete(
            f"{self.base_url}/api/project/{self.project_id}", timeout=self.timeout
        )
        self._record(
            StepResult(
                "project_cleanup",
                resp.status_code in {200, 404},
                resp.status_code,
                "" if resp.status_code in {200, 404} else resp.text,
            )
        )

    def get_status(self) -> None:
        resp = self._get("/api/performance/status")
        self._record(
            StepResult(
                "performance_status",
                resp.status_code == 200,
                resp.status_code,
                "" if resp.status_code == 200 else resp.text,
                resp.json() if resp.status_code == 200 else None,
            )
        )

    def get_dashboard(self) -> None:
        resp = self._get("/api/performance/dashboard")
        self._record(
            StepResult(
                "performance_dashboard",
                resp.status_code == 200,
                resp.status_code,
                "" if resp.status_code == 200 else resp.text,
                resp.json() if resp.status_code == 200 else None,
            )
        )

    def get_recommendations(self) -> None:
        resp = self._get("/api/performance/recommendations/optimization")
        self._record(
            StepResult(
                "performance_recommendations",
                resp.status_code == 200,
                resp.status_code,
                "" if resp.status_code == 200 else resp.text,
                resp.json() if resp.status_code == 200 else None,
            )
        )

    def get_cost_analytics(self) -> None:
        resp = self._get("/api/performance/analytics/cost")
        self._record(
            StepResult(
                "performance_cost_analytics",
                resp.status_code == 200,
                resp.status_code,
                "" if resp.status_code == 200 else resp.text,
                resp.json() if resp.status_code == 200 else None,
            )
        )

    def trigger_estimation(self) -> None:
        payload = {
            "project_id": self.project_id,
            "literature_count": 5,
            "processing_mode": "standard",
            "include_all_modes": False,
        }
        resp = self._post("/api/performance/estimate-cost", payload)
        self._record(
            StepResult(
                "performance_estimate_cost",
                resp.status_code == 200,
                resp.status_code,
                "" if resp.status_code == 200 else resp.text,
                resp.json() if resp.status_code == 200 else None,
            )
        )

    def run(self) -> None:
        self.login()
        if not self.token:
            return
        self.create_project()
        if not self.project_id:
            return
        self.get_status()
        self.get_dashboard()
        self.get_recommendations()
        self.get_cost_analytics()
        self.trigger_estimation()
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
    parser = argparse.ArgumentParser(description="Performance optimization API test")
    parser.add_argument("--base-url", default=os.getenv("VIBERESEARCH_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--output", help="Write JSON report to file")
    return parser.parse_args(argv)

def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    runner = PerformanceInsightsRunner(args.base_url, args.email, args.password, args.timeout)
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
