#!/usr/bin/env python3
"""Comprehensive API smoke/regression script for VibResearch."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Optional, Sequence
from urllib.parse import urljoin

import requests


@dataclass
class TestResult:
    name: str
    method: str
    path: str
    status: str
    status_code: Optional[int]
    elapsed_ms: Optional[float]
    detail: str = ""
    response_excerpt: Optional[str] = None


class ApiTestSuite:
    def __init__(self, base_url: str, email: Optional[str], password: Optional[str], timeout: float) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.email = email
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.results: list[TestResult] = []
        self.authenticated = False
        self.access_token: Optional[str] = None
        self.context: dict[str, Any] = {}
        self.generated_credentials = False

    # --- core helpers -------------------------------------------------
    def _record(
        self,
        name: str,
        method: str,
        path: str,
        status: str,
        status_code: Optional[int],
        elapsed_ms: Optional[float],
        detail: str = "",
        response_excerpt: Optional[str] = None,
    ) -> None:
        self.results.append(
            TestResult(
                name=name,
                method=method,
                path=path,
                status=status,
                status_code=status_code,
                elapsed_ms=elapsed_ms,
                detail=detail,
                response_excerpt=response_excerpt,
            )
        )

    def _request(
        self,
        *,
        name: str,
        method: str,
        path: str,
        expected_status: Sequence[int] = (200,),
        requires_auth: bool = False,
        json_payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        allow_status: Optional[Iterable[int]] = None,
    ) -> Optional[requests.Response]:
        if requires_auth and not self.authenticated:
            self._record(name, method, path, "SKIP", None, None, "auth token unavailable")
            return None

        url = urljoin(self.base_url, path.lstrip("/"))
        start = time.perf_counter()
        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                json=json_payload,
                params=params,
            )
            elapsed = (time.perf_counter() - start) * 1000
        except requests.RequestException as exc:  # pragma: no cover - runtime feedback
            self._record(
                name,
                method,
                path,
                "ERROR",
                None,
                None,
                detail=str(exc),
            )
            return None

        excerpt: Optional[str]
        try:
            excerpt = json.dumps(response.json(), ensure_ascii=False)[:200]
        except Exception:
            excerpt = response.text[:200] if response.text else None

        ok_statuses = set(expected_status)
        if allow_status:
            ok_statuses.update(allow_status)

        if response.status_code in ok_statuses:
            status = "PASS" if response.status_code in expected_status else "WARN"
            detail = ""
        else:
            status = "FAIL"
            detail = f"unexpected status {response.status_code}"

        self._record(name, method, path, status, response.status_code, elapsed, detail, excerpt)
        return response

    def _record_pending_task(self, task_id: Optional[int]) -> None:
        if not task_id:
            return
        pending = self.context.setdefault("pending_tasks", [])
        if task_id not in pending:
            pending.append(task_id)

    # --- public endpoints ---------------------------------------------
    def test_public_endpoints(self) -> None:
        self._request(name="root", method="GET", path="/")
        self._request(name="openapi", method="GET", path="/openapi.json")
        self._request(name="docs", method="GET", path="/api/docs")
        self._request(name="health", method="GET", path="/health")
        self._request(name="healthz", method="GET", path="/healthz")
        self._request(name="readyz", method="GET", path="/readyz", allow_status=(503,))
        self._request(name="live", method="GET", path="/live")
        self._request(name="status", method="GET", path="/status")
        self._request(name="info", method="GET", path="/info")

    # --- auth & user --------------------------------------------------
    def _apply_token(self, token: Optional[str]) -> bool:
        if not token:
            return False
        self.access_token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.authenticated = True
        return True

    def _random_credential(self) -> tuple[str, str, str]:
        suffix = f"{int(time.time())}_{secrets.token_hex(3)}"
        email = f"qa_{suffix}@example.com"
        password = f"Qa!{secrets.token_hex(2)}{suffix}"
        username = f"qa_runner_{suffix}"
        return email, password, username

    def authenticate(self) -> None:
        if self.email and self.password:
            response = self._request(
                name="auth_login",
                method="POST",
                path="/api/auth/login",
                json_payload={"email": self.email, "password": self.password},
            )
            if response and response.status_code == 200:
                if self._apply_token(response.json().get("access_token")):
                    self.context.setdefault("credentials", {"email": self.email, "password": self.password})
                    self._request(name="auth_me", method="GET", path="/api/auth/me", requires_auth=True)
                    return
                self._record("auth_token", "POST", "/api/auth/login", "FAIL", response.status_code, None, "missing token")

        self.generated_credentials = True
        email, password, username = self._random_credential()
        self.email, self.password = email, password
        register_payload = {
            "email": email,
            "password": password,
            "username": username,
            "full_name": "QA Automation",
            "institution": "QA Lab",
            "research_field": "Automation",
        }
        response = self._request(
            name="auth_register",
            method="POST",
            path="/api/auth/register",
            json_payload=register_payload,
            expected_status=(200,),
        )
        if response and response.status_code == 200:
            if self._apply_token(response.json().get("access_token")):
                self.context["credentials"] = {"email": email, "password": password, "username": username}
                self._request(name="auth_me", method="GET", path="/api/auth/me", requires_auth=True)
                return
            self._record("auth_token", "POST", "/api/auth/register", "FAIL", response.status_code, None, "missing token")

        # Registration failed; mark authentication as skipped but keep context
        self.context["credentials"] = {"email": email, "password": password, "username": username}

    def test_user_endpoints(self) -> None:
        profile = self._request(name="user_profile_get", method="GET", path="/api/user/profile", requires_auth=True)
        new_full_name = f"QA Runner {int(time.time())}"
        self._request(
            name="user_profile_update",
            method="PUT",
            path="/api/user/profile",
            requires_auth=True,
            json_payload={"full_name": new_full_name, "institution": "QA Lab", "research_field": "Automation"},
        )
        if profile and profile.status_code == 200:
            self._request(name="user_profile_refresh", method="GET", path="/api/user/profile", requires_auth=True)
        self._request(name="user_usage", method="GET", path="/api/user/usage-statistics", requires_auth=True)

    # --- project workflow ---------------------------------------------
    def test_project_flow(self) -> None:
        unique_name = f"QA Smoke Project {int(time.time())}"
        response = self._request(
            name="project_create",
            method="POST",
            path="/api/project/create-empty",
            requires_auth=True,
            json_payload={
                "name": unique_name,
                "description": "Automated smoke project",
                "category": "regression",
            },
        )
        project_id: Optional[int] = None
        if response and response.status_code == 200:
            project_id = response.json().get("id")
            self.context["project_id"] = project_id

        self._request(name="project_list", method="GET", path="/api/project/list", requires_auth=True)

        if project_id:
            project_path = f"/api/project/{project_id}"
            self._request(name="project_detail", method="GET", path=project_path, requires_auth=True)
            self._request(
                name="project_statistics",
                method="GET",
                path=f"/api/project/{project_id}/statistics",
                requires_auth=True,
            )
            self._request(
                name="project_tasks",
                method="GET",
                path=f"/api/project/{project_id}/tasks",
                requires_auth=True,
            )

    # --- literature endpoints ----------------------------------------
    def test_literature_endpoints(self) -> None:
        self._request(
            name="literature_processing_methods",
            method="GET",
            path="/api/literature/processing-methods",
            requires_auth=True,
        )
        self._request(
            name="literature_statistics_v2",
            method="GET",
            path="/api/literature/statistics-v2",
            requires_auth=True,
        )
        self._request(
            name="literature_user_library",
            method="GET",
            path="/api/literature/user-library",
            requires_auth=True,
        )
        self._request(
            name="literature_list",
            method="GET",
            path="/api/literature/",
            requires_auth=True,
        )
        project_id = self.context.get("project_id")
        if project_id:
            self._request(
                name="literature_project",
                method="GET",
                path=f"/api/literature/project/{project_id}",
                requires_auth=True,
            )
            self._request(
                name="literature_project_stats",
                method="GET",
                path=f"/api/literature/project/{project_id}/statistics",
                requires_auth=True,
            )

    # --- task endpoints -----------------------------------------------
    def test_task_endpoints(self) -> None:
        self._request(name="task_list", method="GET", path="/api/task/", requires_auth=True)
        self._request(name="task_statistics", method="GET", path="/api/task/stats", requires_auth=True)
        self._request(name="tasks_list", method="GET", path="/api/tasks/list", requires_auth=True)
        self._request(name="tasks_overview", method="GET", path="/api/tasks/overview", requires_auth=True)
        self._request(name="tasks_statistics", method="GET", path="/api/tasks/statistics", requires_auth=True)
        self._request(name="tasks_performance", method="GET", path="/api/tasks/performance_metrics", requires_auth=True)

    # --- monitoring / performance -------------------------------------
    def test_monitoring_endpoints(self) -> None:
        self._request(
            name="monitor_overview",
            method="GET",
            path="/api/monitoring/metrics/overview",
            requires_auth=True,
        )
        self._request(
            name="monitor_endpoint_stats",
            method="GET",
            path="/api/monitoring/metrics/endpoint-stats",
            requires_auth=True,
        )
        self._request(
            name="monitor_business_metrics",
            method="GET",
            path="/api/monitoring/metrics/business-metrics",
            requires_auth=True,
        )
        self._request(
            name="monitor_system_health",
            method="GET",
            path="/api/monitoring/metrics/system-health",
            requires_auth=True,
        )
        self._request(
            name="monitor_performance_report",
            method="GET",
            path="/api/monitoring/metrics/performance-report",
            requires_auth=True,
            allow_status=(403,),
        )
        self._request(
            name="monitor_slow_endpoints",
            method="GET",
            path="/api/monitoring/metrics/slow-endpoints",
            requires_auth=True,
        )

    def test_performance_endpoints(self) -> None:
        self._request(
            name="performance_status",
            method="GET",
            path="/api/performance/status",
            requires_auth=True,
        )
        self._request(
            name="performance_dashboard",
            method="GET",
            path="/api/performance/dashboard",
            requires_auth=True,
        )
        self._request(
            name="performance_recommendations",
            method="GET",
            path="/api/performance/recommendations/optimization",
            requires_auth=True,
        )

    def test_research_modes(self) -> None:
        project_id = self.context.get("project_id")
        if not project_id:
            self._record(
                "research_modes",
                "POST",
                "/api/research/query",
                "SKIP",
                None,
                None,
                "project_id unavailable",
            )
            return

        base_payload = {
            "project_id": project_id,
            "query": "自动化验证研究模式",
        }
        self._request(
            name="research_mode_rag",
            method="POST",
            path="/api/research/query",
            requires_auth=True,
            json_payload={**base_payload, "mode": "rag", "max_literature_count": 3},
            allow_status=(202,),
        )
        deep_response = self._request(
            name="research_mode_deep",
            method="POST",
            path="/api/research/query",
            requires_auth=True,
            json_payload={**base_payload, "mode": "deep", "processing_method": "deep"},
            allow_status=(202,),
        )
        if deep_response and deep_response.status_code in {200, 202}:
            try:
                payload = deep_response.json().get("payload", {})
            except ValueError:
                payload = {}
            self._record_pending_task(payload.get("task_id"))

        auto_response = self._request(
            name="research_mode_auto",
            method="POST",
            path="/api/research/query",
            requires_auth=True,
            json_payload={
                **base_payload,
                "mode": "auto",
                "keywords": ["automation", "quality"],
                "auto_config": {"enable_ai_filtering": True, "processing_method": "standard"},
                "agent": "claude",
            },
            allow_status=(202,),
        )
        if auto_response and auto_response.status_code in {200, 202}:
            try:
                auto_payload = auto_response.json().get("payload", {})
            except ValueError:
                auto_payload = {}
            for task in auto_payload.get("tasks", []):
                self._record_pending_task(task.get("task_id"))
        self._request(
            name="research_analysis",
            method="POST",
            path="/api/research/analysis",
            requires_auth=True,
            json_payload={
                "project_id": project_id,
                "query": "自动化验证研究模式",
                "context": {"source": "qa"},
            },
            allow_status=(202,),
        )

    def test_integration_capabilities(self) -> None:
        self._request(
            name="integration_capabilities",
            method="GET",
            path="/api/integration/claude-code/capabilities",
            requires_auth=True,
        )
        self._request(
            name="smart_assistant_capabilities",
            method="GET",
            path="/api/smart-assistant/capabilities",
            requires_auth=True,
        )
        self._request(
            name="knowledge_graph_entity_types",
            method="GET",
            path="/api/knowledge-graph/entity-types",
            requires_auth=True,
        )
        self._request(
            name="knowledge_graph_capabilities",
            method="GET",
            path="/api/knowledge-graph/analysis-capabilities",
            requires_auth=True,
        )
        self._request(
            name="collab_features",
            method="GET",
            path="/api/collaborative-workspace/features",
            requires_auth=True,
        )
        self._request(
            name="mcp_tools",
            method="GET",
            path="/api/mcp/tools",
            requires_auth=True,
        )

    def test_analysis_endpoints(self) -> None:
        project_id = self.context.get("project_id")
        if not project_id:
            self._record(
                "analysis_endpoints",
                "POST",
                "/api/analysis/ask-question",
                "SKIP",
                None,
                None,
                "project_id unavailable",
            )
            return

        question_response = self._request(
            name="analysis_ask_question",
            method="POST",
            path="/api/analysis/ask-question",
            requires_auth=True,
            json_payload={
                "project_id": project_id,
                "question": "测试项目当前的研究重点",
                "use_main_experience": False,
                "context": {"source": "qa-regression"},
            },
        )
        experience_response = self._request(
            name="analysis_generate_experience",
            method="POST",
            path="/api/analysis/generate-experience",
            requires_auth=True,
            json_payload={
                "project_id": project_id,
                "processing_method": "enhanced",
                "research_question": "自动化测试经验生成",
            },
        )
        if experience_response and experience_response.status_code in {200, 202}:
            try:
                payload = experience_response.json()
            except ValueError:
                payload = {}
            self._record_pending_task(payload.get("task_id"))

        self._request(
            name="analysis_generate_main_experience",
            method="POST",
            path="/api/analysis/generate-main-experience",
            requires_auth=True,
            params={
                "project_id": project_id,
                "research_domain": "自动化测试",
            },
        )

        idea_response = self._request(
            name="analysis_generate_ideas",
            method="POST",
            path="/api/analysis/generate-ideas",
            requires_auth=True,
            json_payload={
                "project_id": project_id,
                "research_domain": "自动化测试",
                "innovation_direction": "质量保障",
            },
        )

    # --- cleanup ------------------------------------------------------
    def cleanup(self) -> None:
        project_id = self.context.get("project_id")
        if not project_id:
            return

        if self.authenticated:
            task_list_response = self._request(
                name="cleanup_task_list",
                method="GET",
                path="/api/task/",
                requires_auth=True,
                params={"project_id": project_id},
            )
            if task_list_response and task_list_response.status_code == 200:
                try:
                    task_items = task_list_response.json().get("tasks", [])
                except ValueError:
                    task_items = []
                for item in task_items:
                    if item.get("status") in {"pending", "running", "processing"}:
                        self._record_pending_task(item.get("id"))

            for task_id in sorted(set(self.context.get("pending_tasks", []))):
                self._request(
                    name=f"task_cancel_{task_id}",
                    method="POST",
                    path=f"/api/task/{task_id}/cancel",
                    requires_auth=True,
                    allow_status=(404,),
                )

        self._request(
            name="project_delete",
            method="DELETE",
            path=f"/api/project/{project_id}",
            requires_auth=True,
            allow_status=(404,),
        )

    # --- reporting ----------------------------------------------------
    def summarize(self) -> dict[str, Any]:
        summary = {"PASS": 0, "WARN": 0, "FAIL": 0, "ERROR": 0, "SKIP": 0}
        for result in self.results:
            summary[result.status] = summary.get(result.status, 0) + 1
        return summary

    def print_report(self) -> None:
        summary = self.summarize()
        total = sum(summary.values())
        print("\n=== API Regression Summary ===")
        print(
            " | ".join(
                f"{key}: {summary.get(key, 0)}" for key in ["PASS", "WARN", "FAIL", "ERROR", "SKIP"]
            )
        )
        print(f"Total checks: {total}")
        print("\nDetailed results:")
        for result in self.results:
            elapsed = f"{result.elapsed_ms:.1f}ms" if result.elapsed_ms is not None else "-"
            detail = f" ({result.detail})" if result.detail else ""
            print(f"[{result.status}] {result.name} {result.method} {result.path} -> {result.status_code} in {elapsed}{detail}")
            if result.response_excerpt:
                print(f"  ↳ {result.response_excerpt}")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run VibResearch API regression checks")
    parser.add_argument("--base-url", default=os.getenv("VIBERESEARCH_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--email", default=os.getenv("VIBERESEARCH_TEST_EMAIL"))
    parser.add_argument("--password", default=os.getenv("VIBERESEARCH_TEST_PASSWORD"))
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--output", help="Write detailed JSON report to file")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    suite = ApiTestSuite(args.base_url, args.email, args.password, args.timeout)
    suite.test_public_endpoints()
    suite.authenticate()
    if suite.authenticated:
        suite.test_user_endpoints()
        suite.test_project_flow()
        suite.test_literature_endpoints()
        suite.test_task_endpoints()
        suite.test_monitoring_endpoints()
        suite.test_performance_endpoints()
        suite.test_research_modes()
        suite.test_integration_capabilities()
        suite.test_analysis_endpoints()
        suite.cleanup()
    else:
        print("⚠️  Authentication skipped - provide --email and --password for protected endpoints")

    suite.print_report()

    if args.output:
        payload = {
            "base_url": args.base_url,
            "results": [asdict(result) for result in suite.results],
            "summary": suite.summarize(),
            "generated_at": int(time.time()),
        }
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(f"Report written to {args.output}")

    summary = suite.summarize()
    return 0 if summary.get("FAIL", 0) == 0 and summary.get("ERROR", 0) == 0 else 1


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
