# MO — 科研仓库调研与方案辅助智能体

MO 是一个面向科研仓库调研的 Web 应用：从**创建任务**进入 **PlanMode** 生成计划，经用户批准后进入 **ExecuteMode** 完成仓库摄取、代码理解、论文补充、复现评估、多仓库对比，最终生成带证据链的结构化报告。

**技术栈**：Python 3.13 + FastAPI + LangGraph（后端）｜React + Vite + TypeScript（前端）

## 快速开始

### 1. 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.13（推荐） |
| Node.js | 18+ |
| npm | 9+ |

### 2. 配置环境变量

```powershell
# 仓库根目录
copy .env.example .env
# 编辑 .env，至少填入 DEEPSEEK_API_KEY（及可选 KIMI_API_KEY）

# 前端 API 地址
copy apps\web\.env.example apps\web\.env
```

`.env` 放在**仓库根目录**；后端从根目录启动时会自动加载。

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

**终端 1 — 后端**（在仓库根目录）：

```powershell
cd D:\MyProject\MO
apps\api\.venv\Scripts\activate
uvicorn mo_api.main:app --reload --port 8000 --app-dir apps/api
```

**终端 2 — 前端**：

```powershell
cd D:\MyProject\MO\apps\web
npm run dev
```

浏览器打开 [http://localhost:5173](http://localhost:5173)。健康检查：[http://localhost:8000/health](http://localhost:8000/health)

### 5. 最快体验（Demo）

无需真实仓库与模型调用，可加载离线示例任务：

1. 在 `.env` 中设置 `DEMO_MODE=true` 后重启后端（启动时自动种子），或
2. 打开 [http://localhost:5173/history](http://localhost:5173/history)，点击 **「加载示例任务」**

## 使用流程（简要）

```text
创建任务 → 审阅/批准计划 → 开始执行 → 查看工作流 → 对比矩阵 → 报告/导出
```

- **创建任务**：首页填写研究目标与 1–5 个 GitHub 仓库 URL
- **计划审阅**：确认步骤与风险后批准（未批准不会执行）
- **工作流**：SSE 实时展示节点状态；需审批的步骤会高亮暂停
- **项目历史**：`/history` 查看过往任务，可「重开」克隆为新任务

完整说明、环境变量表与沙箱配置见 **[docs/MO_操作指南.md](docs/MO_操作指南.md)**。

## 项目结构

```text
MO/
├── apps/api/          # FastAPI 后端（mo_api 包）
├── apps/web/          # React 前端
├── docs/
│   ├── MO_操作指南.md  # 安装、配置、使用（本文档的详细版）
│   └── context/       # 产品/技术 PRD 与开发计划
├── external/          # 上游参考仓库（可选）
├── runtime/           # SQLite、索引、运行时产物（不入库）
├── .env.example       # 后端环境变量模板
└── requirements.txt   # 后端 Python 依赖入口
```

## 测试

```powershell
cd apps\api
.venv\Scripts\activate
python -m pytest -q
```

## 文档索引

| 文档 | 说明 |
|------|------|
| [docs/MO_操作指南.md](docs/MO_操作指南.md) | 安装、环境变量、启动、使用、排错 |
| [docs/context/MO_PRD.md](docs/context/MO_PRD.md) | 产品需求 |
| [docs/context/MO_DevPlan.md](docs/context/MO_DevPlan.md) | 开发计划与里程碑 |
| [AGENTS.md](AGENTS.md) | 智能体/贡献者开发约定 |

## 许可与注意

- 勿将 `.env` 及 API Key 提交到版本控制
- 联网调研、仓库克隆、冒烟测试等高风险能力默认关闭，需在任务中显式开启并经审批
- 模型名称与路由见 `apps/api/model_profiles.json`，密钥仅从环境变量读取
