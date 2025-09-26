"""前端质量检查脚本。

依次执行 `npm run lint` 与 `npm run build`，用于确认前端代码可正常通过检查并完成生产构建。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "frontend"


def run(command: list[str]) -> None:
    print(f"$ {' '.join(command)}")
    subprocess.run(command, cwd=FRONTEND_DIR, check=True)


def main() -> None:
    run(["npm", "run", "lint"])
    run(["npm", "run", "build"])
    print("🎉 Frontend lint & build succeeded")


if __name__ == "__main__":
    main()
