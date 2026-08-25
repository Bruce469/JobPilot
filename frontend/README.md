# 秋招投递助手 - 前端（M1）

Vite + Vue 3 + TypeScript + Pinia + Vue Router + Element Plus 的单页应用，负责岗位看板/列表、公司库探测抓取、简历管理与打印、统计、设置（备份）等界面与交互。数据经本地后端 FastAPI（`http://127.0.0.1:8000`）落盘 SQLite。

## 环境要求

- Node.js >= 18（开发环境 22）
- 后端已启动：`backend/` 目录下 `python run.py`（默认 `127.0.0.1:8000`）

## 安装依赖

```bash
cd frontend
npm install
```

## 启动开发服务器

```bash
npm run dev
```

启动后浏览器打开 `http://127.0.0.1:5173`（仅监听本机）。

应用启动流程：前端先调用 `GET /api/boot` 获取随机 token（存 sessionStorage），后续所有请求自动携带 `X-Auth-Token` 头；若后端返回 401（如后端重启后 token 变化），自动重新 boot 刷新 token 并重试一次。

## 与后端的代理配置

`vite.config.ts` 中 `server.proxy` 将 `/api` 代理到后端：

```ts
proxy: {
  '/api': {
    target: process.env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8000',
    changeOrigin: false,
  },
}
```

- 后端默认端口 `8000`；若后端因端口被占自动换端口，或你手动指定了 `--port`，请通过环境变量覆盖代理目标：

```bash
VITE_BACKEND_TARGET=http://127.0.0.1:9000 npm run dev
```

- 前端所有 API 调用都以 `/api` 为相对路径（axios `baseURL='/api'`），代理负责转发，避免跨域/CORS 问题（后端 CORS 白名单仅允许 `127.0.0.1:5173`）。

## 常用命令

| 命令 | 说明 |
|---|---|
| `npm run dev` | 启动开发服务器（HMR） |
| `npm run typecheck` | 类型检查（vue-tsc --noEmit） |
| `npm run build` | 生产构建到 `dist/` |
| `npm run preview` | 预览生产构建 |
| `npm test` | 运行单测（vitest，覆盖日期/状态纯逻辑） |

## 目录结构

```
frontend/
├── vite.config.ts          # proxy /api → 127.0.0.1:8000
├── index.html
└── src/
    ├── main.ts             # 入口（挂载 Pinia/Router/Element Plus）
    ├── App.vue             # 布局 + 启动 boot + 备份提醒
    ├── router/index.ts     # 路由
    ├── api/                # axios 封装（token 注入/统一错误）+ 各资源接口
    ├── stores/             # Pinia：app / ui / jobs / companies / resumes
    ├── types/index.ts      # TS 领域类型
    ├── utils/              # date / normalize / download / charts
    ├── composables/        # useStatusFlow（状态流转共用）
    ├── components/         # 通用组件（JobCard/KanbanColumn/JobFormModal/...）
    └── views/              # 看板 / 列表 / 公司库 / 简历列表/编辑/预览 / 统计 / 设置
```

## 页面与功能（M1 全部 Must）

- **看板 `/board`**：按状态分列（终态默认收起，`含已结束` 开关），卡片拖拽流转（vuedraggable，拖拽与按钮流转共用 `POST /api/jobs/{id}/status`）；顶部「今日/本周安排」（聚合 job_events）与「即将截止 ≤3 天」；卡片点击查看时间线。
- **岗位列表 `/jobs`**：搜索（公司/岗位关键词）+ 多条件组合筛选（状态/城市/行业/渠道/含已结束）+ 一键清除；列排序（公司/截止/投递时间/更新时间）；行内状态流转；多选批量删除；新增/编辑弹窗（company/company_id 选择、position/job_type/degree/city/industry/channel/job_url/deadline/resume_id 绑定等）；笔试/面试事件时间过期标红提醒。
- **公司库 `/companies`**：公司 CRUD；「探测」异步任务（轮询 `GET /api/tasks/{id}`）→ 候选链接择一保存 career_url →「抓取」→ 岗位预览勾选 → `POST /api/jobs/import` 导入并展示新增/跳过/失败数；展示探测状态/ATS 类型/最近抓取结果。
- **简历 `/resumes`**：多份简历 CRUD；编辑页结构化区块（基本信息/教育/实习/项目/技能/自我评价，区块可增删）；预览页 A4 渲染 + `window.print()` 打印/另存 PDF；删除被引用简历二次确认（`?force=true` 后置空岗位绑定）；岗位编辑中可选择绑定简历。
- **统计 `/stats`**：卡片数字（总投递/进行中/已Offer/已拒绝/待跟进）+ 漏斗/渠道分布/近 4 周趋势图（ECharts 按需引入）。
- **设置 `/settings`**：备份导出（触发 JSON 下载）、备份导入（选文件 + 合并/覆盖模式，覆盖二次确认）、schema_version 与 token（掩码）信息展示。
- **首次使用引导**：看板空态展示「添加公司 → 探测 → 抓取 → 导入 → 投递」主流程引导。

## 已知限制

- 看板「今日/本周安排」来自各岗位事件，首次加载看板/列表时会按需拉取岗位详情（事件缓存于 store，之后不再重复请求）；个人数据量（≤1000 条）下本机可接受。
- 简历打印使用浏览器 `window.print()`，不同浏览器分页效果可能有细微差异（架构 Q6 已确认接受）。
- 统计口径以后端 `/api/stats` 为准（PRD 4.8）。
- 无暗色模式、无浏览器通知（M2/M3）。
