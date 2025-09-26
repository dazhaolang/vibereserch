# 前端登录流程修复说明

以下内容供测试团队快速了解本次修复内容与后续验证重点。

## 背景问题
- 回归测试中，登录页在输入凭证后立即崩溃，浏览器控制台报错：`A component suspended while responding to synchronous input.`
- React Router 的错误边界捕获到该错误，导致 UI 显示 "Unexpected Application Error"，阻断整体登录流程。

## 根因定位
- 路由表通过 `React.lazy` 动态加载 `/auth` 页面，但应用根节点缺少顶层 `<Suspense>` 边界。
- 当首次触发登录页渲染时，组件挂起（suspend）却没有匹配的 `Suspense` 边界，React 18 会抛出同步输入挂起异常。

## 修复概述
- 在 `frontend/src/App.tsx:38` 新增顶层 `<Suspense>` 包裹 `RouterProvider`，提供统一的加载占位（`SplashScreen`）。
- `/auth` 及其他懒加载路由现在都能在组件挂起时展示加载界面，从而避免同步输入期间的崩溃。

```tsx
// frontend/src/App.tsx:36-41 摘录
export default function App() {
  return (
    <Suspense fallback={<SplashScreen message="正在加载应用…" />}>
      <RouterProvider router={routes(<RootShell />)} />
    </Suspense>
  );
}
```

## 已执行自检
- `npm run lint`

## 建议测试步骤
1. **登录路径回归**：
   - 清空本地存储，直接访问 `/auth`，确认登录页正常渲染。
   - 输入有效凭证，验证登录后导航跳转无异常，浏览器控制台无 `suspend` 相关错误。
2. **路由切换**：
   - 登录状态下刷新 `/auth`，确认会自动重定向至首页。
   - 在未登录状态下访问受保护路由（如 `/tasks`），验证会被重定向至 `/auth`，并显示加载占位界面而非报错。
3. **WebSocket 验证**：
   - 登录成功后打开 WebSocket 相关模块（如任务列表/实时面板），确认请求头中带上 `token` 参数，连接状态为 101 Switching Protocols。
4. **任务 ID 验证**：
   - 触发一次实时任务，确保前端传递的 `task_id` 为数值型，后端不再出现 `int_parsing` 验证错误。

## 仍需关注
- WebSocket 前端 token 管理后续若有调整，需要重新确认 `wsManager` 的持久化策略。
- 若新增其他懒加载路由，保持顶层 `Suspense` 边界即可复用此机制。

## 负责人
- 修复：Codex（2025-09-19）
- 测试联系人：请参考测试计划文档 `docs/post_patch_testing_plan.md`

