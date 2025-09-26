# Smoke Test Scripts

本目录提供若干可独立运行的冒烟脚本，用于快速验证核心能力。所有脚本均依赖标准异常来提示错误，便于直接定位问题。

## 1. 后端健康检查

```bash
python scripts/smoke/check_health_endpoints.py
```

- 默认访问 `http://127.0.0.1:8000`，可通过环境变量 `VIBERES_BASE_URL` 自定义。
- 覆盖 `/live`、`/healthz`、`/readyz`、`/health`，出现非 200 或组件异常会直接抛出断言错误。

## 2. 认证 + 项目流程

```bash
python scripts/smoke/check_auth_and_project_flow.py
```

- 自动生成唯一账号，执行注册 → 登录 → 获取个人信息 → 创建/删除空项目的完整流程。
- 可通过 `VIBERES_BASE_URL` 修改后端地址，`VIBERES_SMOKE_PASSWORD` 自定义测试密码。
- 若任何步骤失败会触发 HTTP 异常或断言错误。

## 3. 前端代码质量

```bash
python scripts/smoke/check_frontend_build.py
```

- 在 `frontend/` 目录依次执行 `npm run lint`、`npm run build`。
- 需要本地已安装 Node.js 与依赖（首次运行请先执行 `npm install`）。

---

**运行前置条件**

- 后端脚本假定 FastAPI 服务已启动，必要时可启用 `LIGHTWEIGHT_MODE=true` 以减少依赖。
- 前端脚本会依据 `frontend/package.json` 中的脚本执行命令，构建结果输出到 `frontend/dist/`。

若需批量执行，可将上述命令写入自定义的 shell 脚本或 CI 配置，脚本出错即会返回非零状态，适合接入自动化流程。
