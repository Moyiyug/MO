# MO - 科研仓库调研与方案辅助智能体

MO 是一个本地优先的科研仓库调研工作台。用户创建调研任务后，系统先进入 **PlanMode** 生成结构化计划；用户批准后进入 **ExecuteMode**，执行仓库摄取、代码理解、论文/资料补充、复现评估、多仓库对比，最后生成带证据链的 Markdown 报告。

当前重点：核心前后端链路已跑通，后续主要优化前端展示、信息层级和交互体验。

## 功能概览

- 任务创建：研究目标、0-5 个 GitHub 仓库、论文/资料 URL、权限开关。
- RepoDiscovery：未提供仓库时，可在 PlanMode 自动发现候选 GitHub 仓库。
- PlanMode：计划、风险、澄清问题、候选仓库确认、步骤开关与 rubric 权重。
- ExecuteMode：LangGraph 节点执行，SSE 推送工作流事件，`waiting_user` 节点等待审批。
- Evidence/Report：证据链、claim 标签、报告生成/重新生成/确认/导出。
- History/Demo：历史任务打开、重开、删除；离线 demo 任务可一键加载。
- Optional Sandbox：默认关闭；启用后仍需任务权限与节点审批。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.13, FastAPI, Pydantic, SQLModel, LangGraph |
| 存储 | SQLite, LangGraph SQLite checkpoint, Chroma |
| 模型 | 自研 ModelGateway + LiteLLM 兼容模型配置 |
| 前端 | React 19, Vite 8, TypeScript, TanStack Query, Zustand |
| 展示 | Tailwind CSS v4, Radix/shadcn-style components, React Flow, Markdown/Mermaid |

## 快速开始

### 1. 环境要求

| 组件 | 推荐 |
|---|---|
| Python | 3.13 |
| Node.js | 24.x（18+ 通常也可） |
| npm | 11.x（9+ 通常也可） |
| Git | 用于仓库摄取与执行前检查 |

### 2. 配置环境变量

```powershell
cd D:\MyProject\MO
copy .env.example .env
copy apps\web\.env.example apps\web\.env
```

后端读取仓库根目录 `.env`；前端读取 `apps/web/.env`。

最小可启动配置：

```env
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

常用可选配置：

| 变量 | 用途 |
|---|---|
| `KIMI_API_KEY` / `KIMI_BASE_URL` | vision/video 能力 |
| `QWEN_API_KEY` / `QWEN_BASE_URL` | DashScope embedding |
| `GITHUB_TOKEN` | GitHub Search 提额、私有仓库授权 |
| `TAVILY_API_KEY` | gpt-researcher 联网检索 |
| `DEMO_MODE=true` | 后端启动时自动写入离线 demo |
| `SANDBOX_ENABLED=true` | 允许沙箱模块工作，仍需任务权限与审批 |
| `VITE_API_BASE_URL` | 前端请求的后端地址，默认 `http://localhost:8000` |

完整说明见 [`.env.example`](.env.example)。

### 3. 安装依赖

```powershell
# 后端
python -m venv apps\api\.venv
apps\api\.venv\Scripts\activate
pip install -r requirements.txt

# 前端
cd apps\web
npm install
cd ..\..
```

### 4. 启动服务

后端（仓库根目录）：

```powershell
cd D:\MyProject\MO
apps\api\.venv\Scripts\activate
uvicorn mo_api.main:app --reload --port 8000 --app-dir apps/api
```

前端：

```powershell
cd D:\MyProject\MO\apps\web
npm run dev
```

访问：

- 前端：http://localhost:5173
- 后端健康检查：http://localhost:8000/health
- 后端 API 文档：http://localhost:8000/docs

## 使用流程

```text
创建任务 -> 审阅计划 -> 选择候选仓库 -> 批准计划 -> 执行工作流 -> 查看对比/报告 -> 历史管理
```

- 首页 `/`：创建任务；仓库 URL 可留空以触发 RepoDiscovery。
- `/tasks/{task_id}/plan`：审阅计划、回答澄清、确认候选仓库、批准计划。
- `/tasks/{task_id}/workflow`：开始执行并查看节点状态；审批暂停点在这里处理。
- `/tasks/{task_id}/comparison`：查看多仓库对比与权重。
- `/tasks/{task_id}/report`：生成/查看/确认/导出报告。
- `/history`：打开、重开、删除历史任务；也可加载离线 demo。

## 配置原则

- `.env` 和 `apps/web/.env` 不入库；示例值只放 `.env.example`。
- 模型名称、base URL、API key 变量名由 `apps/api/model_profiles.json` 管理；业务代码不得硬编码。
- 付费 API、联网调研、仓库克隆、沙箱命令等高风险动作必须经过权限开关和工作流审批。
- `runtime/` 存放 SQLite、checkpoint、Chroma 索引、沙箱目录等运行时产物，不提交。

## 常用命令

```powershell
# 后端测试
apps\api\.venv\Scripts\python.exe -m pytest -q

# 前端检查/构建
cd apps\web
npm run build
```

## 项目结构

```text
MO/
├── apps/api/          # FastAPI 后端与 mo_api 包
├── apps/web/          # React/Vite 前端
├── docs/context/      # PRD、技术、前后端与测试上下文
├── external/          # 上游参考仓库（可选，不入库）
├── runtime/           # 运行时数据（不入库）
├── .env.example       # 后端环境变量模板
├── requirements.txt   # 后端依赖入口
└── AGENTS.md          # Codex/Cursor 开发智能体约定
```

## 文档索引

| 文档 | 说明 |
|---|---|
| [docs/context/MO_PRD.md](docs/context/MO_PRD.md) | 产品需求与铁律 |
| [docs/context/MO_Tech.md](docs/context/MO_Tech.md) | 技术栈与架构边界 |
| [docs/context/MO_Backend.md](docs/context/MO_Backend.md) | 后端规范、API、存储、上游集成 |
| [docs/context/MO_Frontend.md](docs/context/MO_Frontend.md) | 前端架构、展示规范、重构约束 |
| [docs/context/MO_Backend_Testing.md](docs/context/MO_Backend_Testing.md) | 后端测试规范 |
| [AGENTS.md](AGENTS.md) | 智能体/贡献者开发约定 |

## 安全提醒

- 不提交 `.env`、API key、token、绝对路径、堆栈和运行日志。
- 没有证据的结论必须保留 `pending` 或 `inference` 标签。
- 无 run log 不声称复现成功。
