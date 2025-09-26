"""任务日志记录服务"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger


class TaskLogger:
    """任务执行日志记录器"""

    def __init__(self, base_dir: str = "artifacts/system_tests"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_run_session(self, run_id: Optional[str] = None) -> str:
        """创建运行会话目录"""
        if not run_id:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        session_dir = self.base_dir / run_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (session_dir / "tasks").mkdir(exist_ok=True)
        (session_dir / "logs").mkdir(exist_ok=True)
        (session_dir / "results").mkdir(exist_ok=True)

        return run_id

    def log_task_trigger(
        self,
        run_id: str,
        task_id: str,
        mode: str,
        config: Dict[str, Any],
        user_id: int,
        project_id: int
    ) -> None:
        """记录任务触发事件"""
        session_dir = self.base_dir / run_id

        task_log = {
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
            "config": config,
            "user_id": user_id,
            "project_id": project_id,
            "status": "triggered"
        }

        # 写入任务特定日志
        task_file = session_dir / "tasks" / f"task_{task_id}.json"
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(task_log, f, indent=2, ensure_ascii=False)

        # 追加到汇总日志
        summary_file = session_dir / "task_summary.jsonl"
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(task_log, ensure_ascii=False) + "\n")

        logger.info(f"Task {task_id} logged to {task_file}")

    def log_task_progress(
        self,
        run_id: str,
        task_id: str,
        progress: int,
        message: str,
        stage: Optional[str] = None
    ) -> None:
        """记录任务进度"""
        session_dir = self.base_dir / run_id

        progress_log = {
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "progress": progress,
            "message": message,
            "stage": stage,
            "event_type": "progress"
        }

        # 写入进度日志
        progress_file = session_dir / "logs" / f"progress_{task_id}.jsonl"
        with open(progress_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(progress_log, ensure_ascii=False) + "\n")

        logger.debug(f"Progress logged for task {task_id}: {progress}% - {message}")

    def log_task_completion(
        self,
        run_id: str,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        """记录任务完成状态"""
        session_dir = self.base_dir / run_id

        completion_log = {
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "result": result,
            "error": error,
            "event_type": "completion"
        }

        # 更新任务文件
        task_file = session_dir / "tasks" / f"task_{task_id}.json"
        if task_file.exists():
            with open(task_file, "r", encoding="utf-8") as f:
                task_data = json.load(f)

            task_data.update({
                "completed_at": datetime.now().isoformat(),
                "status": status,
                "result": result,
                "error": error
            })

            with open(task_file, "w", encoding="utf-8") as f:
                json.dump(task_data, f, indent=2, ensure_ascii=False)

        # 写入结果日志
        if result:
            result_file = session_dir / "results" / f"result_{task_id}.json"
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

        logger.info(f"Task {task_id} completed with status: {status}")

    def log_mode_execution(
        self,
        run_id: str,
        mode: str,
        query: str,
        config: Dict[str, Any],
        execution_plan: Dict[str, Any]
    ) -> None:
        """记录模式执行计划"""
        session_dir = self.base_dir / run_id

        mode_log = {
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
            "query": query,
            "config": config,
            "execution_plan": execution_plan,
            "estimated_resources": execution_plan.get("resource_estimates", {}),
            "phases": execution_plan.get("phases", [])
        }

        mode_file = session_dir / f"mode_execution_{mode}.json"
        with open(mode_file, "w", encoding="utf-8") as f:
            json.dump(mode_log, f, indent=2, ensure_ascii=False)

        logger.info(f"Mode {mode} execution plan logged to {mode_file}")

    def generate_session_report(self, run_id: str) -> Dict[str, Any]:
        """生成会话报告"""
        session_dir = self.base_dir / run_id

        if not session_dir.exists():
            raise ValueError(f"Session {run_id} not found")

        # 统计任务数据
        tasks_dir = session_dir / "tasks"
        task_files = list(tasks_dir.glob("task_*.json"))

        tasks_summary = {
            "total_tasks": len(task_files),
            "completed": 0,
            "failed": 0,
            "pending": 0,
            "tasks": []
        }

        for task_file in task_files:
            with open(task_file, "r", encoding="utf-8") as f:
                task_data = json.load(f)

            status = task_data.get("status", "pending")
            if status == "completed":
                tasks_summary["completed"] += 1
            elif status == "failed":
                tasks_summary["failed"] += 1
            else:
                tasks_summary["pending"] += 1

            tasks_summary["tasks"].append({
                "task_id": task_data["task_id"],
                "mode": task_data["mode"],
                "status": status,
                "timestamp": task_data["timestamp"]
            })

        # 生成报告
        report = {
            "run_id": run_id,
            "generated_at": datetime.now().isoformat(),
            "session_dir": str(session_dir),
            "tasks_summary": tasks_summary,
            "success_rate": tasks_summary["completed"] / max(tasks_summary["total_tasks"], 1) * 100
        }

        # 保存报告
        report_file = session_dir / "session_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Session report generated: {report_file}")
        return report


# 全局实例
task_logger = TaskLogger()