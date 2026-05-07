# ATE AI Platform

面向 ATE 测试开发场景的工程平台。项目围绕 `Datasheet -> TestPlan -> 资源映射 -> 测试代码 -> 工程包 -> 工程复核` 主链路，提供资料提取、STS8200S 资源映射、RAG 增强代码生成、运行中心和工程复核能力。

当前版本已经完成这些核心升级：

- 模块一、模块二、模块三统一接入 `run / step / artifact` 模型
- `AgentController` 支持 `should_run / retry / skipped / human_review_required`
- `RunStore` 支持独立 run 目录和 artifact 索引
- 运行中心支持查看跨模块运行记录、阶段状态、复核结论与产物摘要
- 支持发起 `full_ate_development` 全链路运行

## 1. 项目定位

这不是一个单纯的“代码生成器”，而是在现有业务模块基础上逐步升级出来的 ATE Agent Platform：

- 模块一：从 Datasheet / PDF 提取芯片参数、引脚和测试场景
- 模块二：基于提取结果生成资源映射、PGS、BOM、SVG
- 模块三：基于测试项、企业知识库和 RAG 生成测试代码与工程包
- 模块四：提供良率诊断与波形分析演示能力
- 运行中心：查看运行过程、步骤状态、中间产物和复核结论

## 2. 当前能力概览

### 模块一：TestPlan 提取

- PDF 上传与页码范围提取
- 同步提取与异步任务
- 芯片类型、参数、引脚、测试场景识别
- Excel / JSON 结果导出
- 统一接入运行中心

### 模块二：资源映射

- 基于提取结果生成 STS8200S 资源映射
- 输出 PGS、BOM、SVG、Excel
- 统一接入运行中心

### 模块三：代码实验室

- 测试项推荐
- 生成前规划 `plan`
- 企业知识库与 RAG 增强
- C++ 代码生成
- 静态校验
- 编译预检
- 工程包导出
- 工程复核摘要
- 统一接入运行中心

### 运行中心

- 查看最近运行记录
- 查看 `run / step / artifact`
- 查看复核结论与下一步建议
- 发起 `full_ate_development` 全链路运行

## 3. Agent 化进度

### 已完成

- `AgentController` 已支持：
  - 条件执行 `should_run`
  - 重试 `max_retries`
  - 跳过 `skipped`
  - 人工复核 `human_review_required`
- `RunStore` 已支持：
  - `run.json`
  - `steps.json`
  - `artifacts/index.json`
  - 单个 artifact 元数据索引
- 模块一、模块二、模块三均已接入统一运行模型
- 模块三已接入 `ReviewAgent`
- 已支持 `full_ate_development` 全链路 flow

### 当前边界

- 这还不是完全成熟的多智能体平台
- 当前更准确的阶段是：
  - 平台主链已统一 run 模型
  - 前后端已具备运行中心与工作台
  - 全链路 flow 已有第一版可运行骨架

## 4. 目录结构

```text
ate-ai-platform/
├── apps/                           # React + Vite + Electron 前端
│   ├── electron/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── store/
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
│   ├── uploads/
│   └── processed/
├── docs/
└── requirements.txt
```

## 5. 环境要求

- Python 3.10+
- Node.js 20+
- 推荐使用 Windows + PowerShell
- 若启用 LLM / RAG 能力，需要配置模型 API Key

## 6. 后端启动

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

- OpenAPI：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

## 7. 前端启动

```powershell
cd apps
npm install
npm run dev
```

默认地址：

- 前端：`http://127.0.0.1:3000`

## 8. 桌面端启动

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

## 9. 常用接口

### 模块一

- `POST /api/v1/testplan/upload`
- `POST /api/v1/testplan/extract`
- `POST /api/v1/testplan/extract-async`
- `GET /api/v1/testplan/status/{task_id}`
- `GET /api/v1/testplan/download/{file_id}/{file_type}`
- `GET /api/v1/testplan/pins/{file_id}`

### 模块二

- `POST /api/v1/resource-map/generate`

### 模块三

- `POST /api/v1/codegen/generate`
- `POST /api/v1/codegen/plan`

### 运行中心

- `GET /api/v1/agent-runs`
- `GET /api/v1/agent-runs/{run_id}`
- `GET /api/v1/agent-runs/{run_id}/artifacts`
- `GET /api/v1/agent-runs/{run_id}/artifacts/{artifact_name}`
- `POST /api/v1/agent-runs`
- `POST /api/v1/agent-runs/{run_id}/approve`
- `POST /api/v1/agent-runs/{run_id}/reject`

### 其他

- `GET /health`
- `GET /api/v1/rag/status`
- `POST /api/v1/diagnosis/run`

## 10. 全链路运行说明

当前已支持第一版全链路 flow：`full_ate_development`

阶段包括：

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

这条 flow 当前更适合：

- 调试
- 架构验证
- 演示 Agent 化主链

而不是替代三个主页面的全部细粒度操作。

## 11. 验证命令

后端测试：

```powershell
python -m pytest backend/tests -q
```

后端语法检查：

```powershell
python -m compileall -q backend/app
```

前端构建：

```powershell
cd apps
npm run build
```

## 12. 重要说明

- 自动生成的测试代码、资源映射和工程包，必须由 ATE 工程师复核后再上机使用
- `review_summary` 与运行中心中的复核结论属于辅助判断，不是最终放行依据
- `data/uploads/`、`data/processed/`、`logs/` 为运行产物目录，不建议将生成结果直接提交入库
- 若未配置 RAG / 模型能力，部分步骤会降级执行，但平台仍可输出基础结果

## 13. 相关文档

- [模块三 Agent 化一期说明](docs/phase2-run-model-completion.md)
- [Agent Controller 实施方案](docs/agent-controller-implementation-plan.md)
- [Agent Run 产物结构说明](docs/agent-run-artifacts.md)
- [全链路 Flow 说明](docs/full-ate-development-flow.md)
