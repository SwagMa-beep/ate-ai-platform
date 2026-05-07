# ATE AI Platform

面向 ATE 测试开发场景的工程平台。

项目围绕 `Datasheet -> TestPlan -> 资源映射 -> 测试代码 -> 工程复核 -> 工程包` 主链路，提供资料提取、`STS8200S` 资源映射、RAG 增强代码生成、统一运行中心、Agent 工作台和工程师助手能力。

当前版本已经不是几个独立工具页的集合，而是具备一条可运行的 `full_ate_development` Agent Flow，用于把分散模块串成完整开发闭环。

## 1. 当前版本能力

### 核心业务能力

- `Datasheet / TestPlan`
  - 上传 PDF
  - 提取芯片类型、参数表、引脚定义、测试场景
  - 导出 `Excel / JSON`
  - 支持缓存复用、参数持久化和引脚方向归一化

- `STS8200S 资源映射`
  - 基于提取结果生成资源映射
  - 输出 `PGS / BOM / SVG`
  - 支持单工位和双工位配置

- `RAG 测试代码生成`
  - 基于测试项、企业知识库和 `STS8200S` 内置知识进行增强生成
  - 生成测试规划、测试代码、静态检查结果和编译预检结果
  - 支持工程包导出

- `ATE Agent 工作台`
  - 发起完整 `full_ate_development` 流程
  - 查看动态执行过程、`Thinking Feed`、阶段耗时
  - 查看 `review` 结论、批准后交付物和中间 `artifacts`

- `Agent 运行中心`
  - 查看最近运行记录
  - 查看 `run / step / artifact`
  - 查看批准、打回和后续 `continuation run`
  - 支持清空运行记录

- `工程师助手`
  - 统一的测试 AI 助手入口
  - 读取最近运行、工作区记忆和本地知识片段
  - 支持文本问答
  - 已接入图片问答接口；配置视觉模型后可启用多模态分析

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

## 2. 当前平台定位

这套平台当前更准确的定位是：

**ATE 开发辅助与交付平台**

不是：

**批准后自动控制 STS8200S 真机执行测试的平台**

也就是说，当前版本最核心的价值是：

- 帮工程师从 `Datasheet` 走到结构化 `TestPlan`
- 帮工程师生成资源映射和测试代码初稿
- 帮工程师整理 `review` 结果、风险结论和交付包

批准后，系统当前会进入“交付整理”阶段，输出：

- 代码类产物
- 资源映射类产物
- `review summary`
- `bench checklist`
- `final package` 信息

当前版本**不会**：

- 自动装载程序到 ATE
- 自动连接 `STS8200S` 机台
- 自动执行真实硬件测试
- 自动采集 DUT 实测结果

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

这个流程已经接入统一 `AgentController`，并且会把每一步的状态、时间、警告、错误和产物写入运行记录。

## 4. 工程师助手

当前主框架已经整合“工程师助手”模块，不再维护第二套平行系统。

助手当前可读取：

- 最近运行记录
- 工作区记忆
- 本地知识片段
- 最近的 TestPlan / 资源映射 / 代码生成 / 诊断上下文

后端接口：

- `POST /api/v1/chat/query`
- `POST /api/v1/chat/message`
- `GET /api/v1/workspace-memory`
- `POST /api/v1/workspace-memory/reset`

当前文本助手默认走文本模型。
如果配置了：

- `VISION_API_KEY`
- `VISION_BASE_URL`
- `VISION_MODEL`

则图片问答会走视觉模型。

## 5. PDF 提取、OCR 与 RAG

### PDF 提取链路

当前 PDF 提取主链路是：

- `pdfplumber` 文本/表格解析
- 页面过滤与本地规则补提取
- `LLMExtractor` 结构化参数与引脚抽取

### OCR 现状

当前版本已接入 **按需 OCR fallback**：

- 默认优先使用文本层解析
- 当页面文本层过稀疏时，再触发 OCR 补充
- 适合扫描页、图片页和疑难页兜底

这不是全量 OCR 主链，而是“文本优先、OCR 兜底”的模式。

### RAG 现状

当前版本已经对 RAG 查询做了增强：

- 结合 `goal`
- 芯片名 / 芯片类型
- 推荐测试项
- `STS8200S` API 关键词

来提高命中率。

如果 RAG 没有返回有效片段，流程不会中断，而是退回到：

- 企业知识库
- 本地模板
- 通用代码润色逻辑

## 6. 典型产物

平台当前可生成或记录这些典型产物：

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
├── run.json
├── steps.json
└── artifacts/
    ├── index.json
    ├── *.json
    └── ...
```

## 7. 目录结构

```text
ate-ai-platform/
├── apps/                      # React + Vite + Electron 前端
│   ├── electron/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── utils/
│   │   └── types.ts
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   ├── core/
│   │   ├── flows/
│   │   ├── models/
│   │   ├── services/
│   │   └── utils/
│   ├── tests/
│   ├── check_env.py
│   └── cli.py
├── data/
│   ├── knowledge/
│   ├── uploads/
│   └── processed/
├── docs/
└── requirements.txt
```

## 8. 环境要求

- Python 3.10+
- Node.js 20+
- 推荐 Windows + PowerShell

如需启用文本模型：

- `DEEPSEEK_API_KEY`

如需启用视觉模型：

- `VISION_API_KEY`
- `VISION_BASE_URL`
- `VISION_MODEL`

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

VISION_API_KEY=
VISION_BASE_URL=
VISION_MODEL=

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

### 工程师助手

- `POST /api/v1/chat/query`
- `POST /api/v1/chat/message`
- `GET /api/v1/workspace-memory`
- `POST /api/v1/workspace-memory/reset`

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

## 14. 当前边界

- 自动生成的测试代码、资源映射和工程包，必须由 ATE 工程师复核后再使用
- `review_summary` 和运行中心结论属于辅助判断，不是最终放行依据
- 当前平台仍未实现批准后自动控制 ATE 真机执行测试
- 若未配置模型能力，提取和生成链路会明显受限
- 若 PDF 为扫描件或图片型文档，虽然已有 OCR fallback，但复杂场景效果仍可能下降
- `data/uploads/`、`data/processed/`、`logs/` 为运行产物目录，不建议直接提交生成结果入库

## 15. 相关文档

- [Full ATE Development Flow](docs/full-ate-development-flow.md)
- [Agent Run Artifacts](docs/agent-run-artifacts.md)
- [工程师助手迁移方案](docs/engineer-assistant-migration-plan.md)
- [项目框架图](competition_submission_materials/diagrams/project_framework_v2.md)
