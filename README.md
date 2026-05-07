# ATE AI Platform

面向 ATE 测试开发场景的工程平台。项目围绕 `Datasheet -> TestPlan -> 资源映射 -> 测试代码 -> 工程包 -> 工程复核` 主链路，提供资料提取、STS8200S 资源映射、RAG 增强代码生成、统一运行中心和 Agent 工作台能力。

当前版本已经不只是单个模块工具集合，而是具备了一条可运行的 `full_ate_development` Agent Flow，用于把分散的模块能力串成一条完整的开发闭环。

## 1. 当前版本能做什么

### 核心业务能力

- `Datasheet / TestPlan 提取`
  - 上传 PDF
  - 提取芯片类型、参数表、引脚定义、测试场景
  - 导出 Excel / JSON
  - 支持缓存复用、参数持久化、引脚方向归一化

- `STS8200S 资源映射`
  - 基于提取结果生成资源映射
  - 输出 PGS、BOM、SVG 等交付物
  - 支持单工位和双工位配置

- `RAG 测试代码生成`
  - 基于测试项、企业知识库和 STS8200S 内置知识进行增强生成
  - 生成测试规划、测试代码、静态检查结果和编译预检结果
  - 支持工程包导出

- `ATE Agent 工作台`
  - 发起完整 `full_ate_development` 流程
  - 查看动态执行过程、Thinking Feed、阶段耗时
  - 查看 review 结论、批准后交付物和中间 artifacts

- `Agent 运行中心`
  - 查看最近运行记录
  - 查看 `run / step / artifact`
  - 查看批准、打回、后续 continuation run
  - 支持清空运行记录

- `良率诊断`
  - 提供诊断页与波形/异常分析展示能力

### Agent 化能力

- `AgentController` 已支持：
  - `should_run`
  - `retry`
  - `skipped`
  - `human_review_required`
  - 统一 step 质量、耗时和中间产物记录

- `RunStore` 已支持：
  - 独立 run 目录
  - `run.json`
  - `steps.json`
  - `artifacts/index.json`
  - artifact 元数据快照

- 已接入的跨模块流程：
  - `full_ate_development`
  - `post_review_delivery`
  - `post_review_revision`

## 2. 平台当前的真实定位

这套平台现在更准确的定位是：

**ATE 开发辅助与交付平台**

而不是：

**批准后自动控制 STS8200S 真机执行测试的平台**

也就是说，当前版本最核心的价值是：

- 帮工程师从 Datasheet 走到结构化 TestPlan
- 帮工程师生成资源映射和测试代码初稿
- 帮工程师整理 review 结果、风险结论和交付包

批准后，系统现在会进入“交付整理”阶段，输出：

- 代码类产物
- 资源映射类产物
- review summary
- bench checklist
- final package 信息

但当前版本**不会**：

- 自动装载程序到 ATE
- 自动连接 STS8200S 机台
- 自动执行真实硬件测试
- 自动采集 DUT 测试结果

## 3. Full ATE Development Flow

当前主流程为：

1. 输入解析
2. TestPlan 提取
3. 参数校验
4. 资源映射
5. RAG 检索
6. 测试规划
7. 代码装配
8. 静态校验
9. 编译预检
10. 工程复核
11. 工程打包

这个流程已经接入统一 `AgentController`，并且会将每一步的状态、时间、警告、错误和产物写入 run 记录。

## 4. 当前前端体验特性

- 左侧导航支持折叠、悬停临时展开和状态记忆
- Agent 工作台支持动态时间线和 Thinking Feed
- Thinking Feed 在运行中展开，完成后自动折叠
- 资源映射页和代码生成页支持结果跨页面保留
- 批准后可直接查看“可交付文件”区域
- 运行中心支持查看 continuation run、review 决策和产物摘要

## 5. RAG 与 PDF 提取说明

### PDF 提取链路

当前 PDF 提取主链路是：

- `pdfplumber` 文本/表格解析
- 页面过滤与本地规则补提取
- `LLMExtractor` 结构化参数与引脚抽取

当前版本**没有正式接入 OCR 主链路**。这意味着：

- 文本版 Datasheet 提取效果较好
- 扫描件、图片型 PDF、截图表格的提取效果会下降

### RAG 现状

当前版本已经对 RAG 查询做了增强：

- 会结合 `goal`
- 芯片名 / 芯片类型
- 推荐测试项
- STS8200S API 关键词

来提高命中率。

如果 RAG 没有返回有效片段，流程不会中断，而是退回到：

- 企业知识库
- 本地模板
- 通用代码润色逻辑

## 6. 典型产物

平台当前可能生成或记录这些典型产物：

- `testplan_result`
- `resource_mapping`
- `codegen_plan`
- `generated_code`
- `static_analysis`
- `compile_validation`
- `review_summary`
- `engineering_package`
- `delivery_summary`
- `bench_checklist`
- `final_package`

产物元数据默认落在：

```text
data/processed/agent_runs/{run_id}/
├─ run.json
├─ steps.json
└─ artifacts/
   ├─ index.json
   ├─ *.json
   └─ ...
```

## 7. 目录结构

```text
ate-ai-platform/
├─ apps/                      # React + Vite + Electron 前端
│  ├─ electron/
│  ├─ src/
│  │  ├─ api/
│  │  ├─ components/
│  │  ├─ pages/
│  │  ├─ utils/
│  │  └─ types.ts
│  └─ package.json
├─ backend/
│  ├─ app/
│  │  ├─ api/v1/
│  │  ├─ core/
│  │  ├─ flows/
│  │  ├─ models/
│  │  ├─ services/
│  │  └─ utils/
│  ├─ tests/
│  ├─ check_env.py
│  └─ cli.py
├─ data/
│  ├─ uploads/
│  └─ processed/
├─ docs/
└─ requirements.txt
```

## 8. 环境要求

- Python 3.10+
- Node.js 20+
- 推荐 Windows + PowerShell
- 如需启用 LLM / RAG，请配置 DeepSeek API Key

## 9. 后端启动

```powershell
git clone <your-repo-url>
cd ate-ai-platform

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

配置 `backend/.env`：

```env
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DEBUG=true
```

检查环境：

```powershell
cd backend
python check_env.py
```

启动后端：

```powershell
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

可用地址：

- OpenAPI: `http://127.0.0.1:8000/docs`
- 健康检查: `http://127.0.0.1:8000/health`

## 10. 前端启动

```powershell
cd apps
npm install
npm run dev
```

默认地址：

- 前端: `http://127.0.0.1:3000`

## 11. 桌面端

开发模式：

```powershell
cd apps
npm run desktop:dev
```

构建桌面端：

```powershell
cd apps
npm run desktop:build
```

生成安装包：

```powershell
cd apps
$env:ELECTRON_MIRROR='https://npmmirror.com/mirrors/electron/'
$env:ELECTRON_BUILDER_BINARIES_MIRROR='https://npmmirror.com/mirrors/electron-builder-binaries/'
npm run desktop:installer
```

## 12. 常用接口

### TestPlan

- `POST /api/v1/testplan/upload`
- `POST /api/v1/testplan/extract`
- `POST /api/v1/testplan/extract-async`
- `GET /api/v1/testplan/status/{task_id}`
- `GET /api/v1/testplan/download/{file_id}/{file_type}`
- `GET /api/v1/testplan/pins/{file_id}`

### 资源映射

- `POST /api/v1/resource-map/generate`

### 代码生成

- `POST /api/v1/codegen/generate`
- `POST /api/v1/codegen/plan`

### Agent Runs

- `GET /api/v1/agent-runs`
- `GET /api/v1/agent-runs/{run_id}`
- `GET /api/v1/agent-runs/{run_id}/artifacts`
- `GET /api/v1/agent-runs/{run_id}/artifacts/{artifact_name}`
- `POST /api/v1/agent-runs`
- `POST /api/v1/agent-runs/{run_id}/approve`
- `POST /api/v1/agent-runs/{run_id}/reject`
- `DELETE /api/v1/agent-runs`

### 其他

- `GET /health`
- `GET /api/v1/rag/status`
- `POST /api/v1/diagnosis/run`

## 13. 验证命令

后端测试：

```powershell
python -m pytest backend/tests -q
```

后端语法检查：

```powershell
python -m compileall -q backend/app
```

前端校验：

```powershell
cd apps
npm run lint
npm run build
```

## 14. 当前边界与注意事项

- 自动生成的测试代码、资源映射和工程包，必须由 ATE 工程师复核后再使用
- `review_summary` 和运行中心里的结论属于辅助判断，不是最终放行依据
- 若未配置模型能力，提取和生成链路会明显受限
- 若 PDF 为扫描件或图片型文档，当前提取效果会下降
- `data/uploads/`、`data/processed/`、`logs/` 为运行产物目录，不建议直接提交生成结果入库

## 15. 相关文档

- [Full ATE Development Flow](docs/full-ate-development-flow.md)
- [Agent Run Artifacts](docs/agent-run-artifacts.md)
- [Agent Controller 实施方案](docs/agent-controller-implementation-plan.md)
- [阶段性 Agent 化说明](docs/phase2-run-model-completion.md)
