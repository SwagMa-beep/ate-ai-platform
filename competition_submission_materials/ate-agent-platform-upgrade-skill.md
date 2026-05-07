# ATE-AI-Platform Agent 平台二阶段升级 Skill

## 1. 文档目标

本文档用于指导 Codex / AI 编程智能体继续优化 `ATE-AI-Platform` 项目。

当前项目已经完成初步 agent 化，具备：

- `AgentController`
- `RunContext`
- `AgentStepResult`
- `AgentRun`
- `RunStore`
- `AgentRuns API`
- 前端 AgentRuns 运行中心
- 模块三代码生成 flow
- PlanningAgent / CodeAssemblyAgent / StaticValidationAgent / CompileValidationAgent / EngineeringPackageAgent

本阶段目标是将项目从：

```text
轻量 Agent Controller + Run 模型 + 顺序 Flow 编排
```

升级为：

```text
跨模块 Agent Flow + 条件路由 + 可复核 Artifact + fallback / retry + ReviewAgent
```

最终让项目更接近一个真实的 **ATE 测试开发 Agent 系统**。

---

## 2. 项目背景

`ATE-AI-Platform` 是一个面向 ATE 测试开发的 AI 辅助平台，目前已经包含：

- Datasheet 参数抽取
- TestPlan 生成
- STS8200S 资源映射
- RAG 增强代码生成
- C++ 测试程序生成
- 静态校验 / 编译预检
- 良率诊断
- Agent run 记录
- 前端运行中心

项目最初更偏向：

```text
用户选择功能
→ 调用对应 API
→ 执行固定 service
→ 返回结果
```

现在已经进入：

```text
用户创建 run
→ AgentController 调度 AgentStep
→ 保存 steps / warnings / errors / artifacts
→ 前端运行中心回看结果
```

本阶段继续升级为：

```text
用户输入目标 + Datasheet
→ full_ate_development_flow
→ 自动完成 TestPlan 抽取、资源映射、RAG 检索、代码生成、校验、复核和工程打包
```

---

## 3. 改造总原则

1. 不删除已有 API。
2. 不推翻现有 `AgentController`。
3. 不大规模重写已有 `services`。
4. 优先复用现有模块。
5. 每次改动保持项目可运行。
6. 每个 Agent Step 必须产生明确的 step result。
7. 每个关键中间产物必须进入 artifact。
8. 所有失败都必须记录到 `errors` 或 `warnings`。
9. 自动生成的测试代码必须提示：**需由 ATE 工程师复核后再上机使用**。
10. 代码格式必须规范，避免 Python 文件被压缩成一行。
11. 不要把真实 API Key 写入代码或仓库。
12. 不要让 LLM 完全无约束地直接生成最终测试程序。

---

## 4. 推荐目录结构

在现有项目结构上补充或调整：

```text
backend/app/
├── flows/
│   ├── module1_testplan_flow.py
│   ├── module2_resource_flow.py
│   ├── module3_codegen_flow.py
│   └── full_ate_development_flow.py
├── services/
│   ├── agent_controller.py
│   ├── run_store.py
│   ├── llm_extractor.py
│   ├── rag_service.py
│   ├── codegen_service.py
│   ├── yield_diagnosis.py
│   └── ...
├── api/
│   └── v1/
│       ├── agent_runs.py
│       ├── testplan.py
│       ├── resource_map.py
│       ├── codegen.py
│       ├── rag.py
│       └── diagnosis.py
└── models/
    └── ...
```

如果当前项目结构与上面不同，请以当前结构为准，做最小侵入式改造。

---

## 5. 第一阶段：代码格式化与现状保护

### 5.1 目标

在进行功能增强前，先保证代码可读、可维护、可回滚。

### 5.2 要求

- Python 文件不能被压成一行。
- import 分组清晰。
- 函数不要过长。
- 单个 Agent 只做单一职责。
- 避免在 controller 中堆业务逻辑。
- 确保现有模块功能不被破坏。

### 5.3 推荐命令

```bash
pip install black ruff
black backend/app
ruff check backend/app
```

如果项目已有格式化工具或配置，优先使用已有配置。

---

## 6. 第二阶段：升级 AgentController

### 6.1 目标

在现有 `AgentController` 基础上支持：

- 顺序执行
- 条件执行
- skipped 状态
- retry 机制
- flow 中断
- human_review_required 状态
- artifact 注册
- 更清晰的 step 状态

---

### 6.2 标准 Step 状态

建议统一使用以下状态：

```text
pending
running
success
warning
failed
skipped
human_review_required
```

含义：

| 状态 | 含义 |
|---|---|
| pending | 等待执行 |
| running | 正在执行 |
| success | 成功完成 |
| warning | 完成但存在警告 |
| failed | 执行失败 |
| skipped | 条件不满足，跳过 |
| human_review_required | 需要人工复核 |

---

### 6.3 AgentStepResult 建议结构

如果现有字段不足，可以扩展为：

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentStepResult:
    agent_name: str
    status: str
    message: str = ""
    data: dict = field(default_factory=dict)
    artifacts: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    next_action: Optional[str] = None
    requires_human_review: bool = False
```

---

### 6.4 RunContext 建议结构

```python
from dataclasses import dataclass, field


@dataclass
class RunContext:
    run_id: str
    flow_name: str
    goal: str
    inputs: dict = field(default_factory=dict)
    state: dict = field(default_factory=dict)
    steps: list[dict] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
```

---

### 6.5 BaseAgent 建议接口

```python
class BaseAgent:
    agent_name: str = "base_agent"

    async def run(self, context: RunContext) -> AgentStepResult:
        raise NotImplementedError

    def should_run(self, context: RunContext) -> bool:
        return True

    def max_retries(self) -> int:
        return 0
```

---

## 7. 第三阶段：增加条件分支能力

当前 flow 主要是顺序执行，本阶段需要增加简单、可维护的条件判断机制。

### 7.1 方式一：Agent 自带 `should_run`

示例：

```python
class YieldDiagnosisAgent(BaseAgent):
    agent_name = "yield_diagnosis"

    def should_run(self, context: RunContext) -> bool:
        return bool(context.inputs.get("enable_diagnosis", False))
```

这种方式适合：

- 某些 Agent 是否执行由输入参数决定。
- 某些 Agent 是否执行由前一步 state 决定。

---

### 7.2 方式二：Flow 定义中加入 condition

示例：

```python
flow = [
    {"agent": InputResolveAgent()},
    {"agent": TestPlanExtractAgent()},
    {"agent": ParamValidationAgent()},
    {
        "agent": ResourceMappingAgent(),
        "condition": lambda ctx: ctx.state.get("validation", {}).get("passed") is True,
    },
    {
        "agent": HumanReviewRequiredAgent(),
        "condition": lambda ctx: ctx.state.get("validation", {}).get("passed") is False,
    },
]
```

优先选择当前项目中更容易集成的方式。

---

## 8. 第四阶段：新增 full_ate_development_flow

### 8.1 文件位置

新增文件：

```text
backend/app/flows/full_ate_development_flow.py
```

---

### 8.2 流程目标

实现一个跨模块完整 ATE Agent 流程。

用户输入示例：

```text
根据这个 Datasheet 生成 STS8200S 测试程序，并输出资源映射和风险报告。
```

系统自动执行：

```text
InputResolveAgent
→ TestPlanExtractAgent
→ ParamValidationAgent
→ ResourceMappingAgent
→ RagRetrievalAgent
→ CodegenPlanningAgent
→ CodeAssemblyAgent
→ StaticValidationAgent
→ CompileValidationAgent
→ ReviewAgent
→ EngineeringPackageAgent
```

---

## 9. full_ate_development_flow 中的 Agent 设计

### 9.1 InputResolveAgent

#### 职责

- 读取用户 goal。
- 读取 `file_id` / `pdf_path`。
- 检查输入是否完整。
- 解析目标平台，默认 `STS8200S`。
- 写入 `context.state["input"]`。

#### 输入

```python
context.goal
context.inputs["file_id"]
context.inputs["pdf_path"]
```

#### 输出

```python
context.state["input"] = {
    "goal": "...",
    "pdf_path": "...",
    "target_platform": "STS8200S",
}
```

#### 失败情况

- 没有 goal。
- 没有文件。
- 文件不存在。

---

### 9.2 TestPlanExtractAgent

#### 职责

- 调用现有 TestPlan / LLMExtractor 能力。
- 从 Datasheet 中抽取测试参数。
- 生成结构化 TestPlan。

#### 输出

```python
context.state["testplan"] = {
    "parameters": [],
    "pins": [],
    "test_items": [],
}
```

#### Artifacts

```text
testplan.json
testplan.xlsx
```

#### 注意

如果 LLM 抽取失败，应尝试规则抽取或输出 warning，不要直接吞掉错误。

---

### 9.3 ParamValidationAgent

#### 职责

- 校验 TestPlan 是否足够进入资源映射与代码生成。
- 检查 pin 信息。
- 检查电压 / 电流 / 时序等关键字段。
- 生成 warnings。

#### 输出

```python
context.state["validation"] = {
    "passed": True,
    "missing_fields": [],
    "warnings": [],
}
```

#### 条件分支

```text
passed = true  → 继续 ResourceMappingAgent
passed = false → HumanReviewRequiredAgent 或 ReviewAgent
```

---

### 9.4 ResourceMappingAgent

#### 职责

- 调用现有资源映射模块。
- 生成 STS8200S 资源映射。
- 标记资源冲突和风险。

#### 输出

```python
context.state["resource_map"] = {
    "mappings": [],
    "conflicts": [],
    "warnings": [],
}
```

#### Artifacts

```text
resource_map.json
resource_map.xlsx
```

---

### 9.5 RagRetrievalAgent

#### 职责

- 根据 goal、testplan、resource_map 生成检索 query。
- 调用现有 RAG service。
- 检索 STS8200S 编程知识、模板说明、注意事项。

#### 输出

```python
context.state["rag"] = {
    "query": "...",
    "chunks": [],
    "hit_count": 0,
}
```

#### fallback

如果 RAG 无结果或服务不可用：

```text
不中断流程，写入 warning，并允许模板代码生成继续。
```

warning 示例：

```text
RAG 检索无有效结果，代码生成已降级为模板模式，需重点人工复核。
```

---

### 9.6 CodegenPlanningAgent

#### 职责

- 根据 TestPlan、资源映射、RAG 结果生成代码生成计划。
- 明确需要哪些测试函数。
- 明确 setup / measure / cleanup 结构。
- 明确风险点。

#### 输出

```python
context.state["codegen_plan"] = {
    "test_functions": [],
    "required_sections": ["setup", "measure", "cleanup"],
    "risks": [],
}
```

#### Artifact

```text
codegen_plan.json
```

---

### 9.7 CodeAssemblyAgent

#### 职责

- 调用现有代码生成模块。
- 结合模板、RAG、计划生成 C++ 测试程序。
- 不允许模型完全无约束生成。

#### 输出

```python
context.state["generated_code"] = {
    "filename": "generated_test_program.cpp",
    "content": "...",
    "line_count": 0,
}
```

#### Artifact

```text
generated_test_program.cpp
```

---

### 9.8 StaticValidationAgent

#### 职责

做静态规则检查：

- 检查必要 include。
- 检查 setup / measure / cleanup。
- 检查 TODO。
- 检查空函数。
- 检查明显未定义变量。
- 检查风险提示。

#### 输出

```python
context.state["static_validation"] = {
    "passed": True,
    "issues": [],
    "warnings": [],
}
```

#### 注意

如果失败，不一定终止流程，应进入 ReviewAgent 汇总风险。

---

### 9.9 CompileValidationAgent

#### 职责

- 做编译预检或模拟编译检查。
- 如果项目没有真实编译环境，则进行语法级、依赖级、结构级预检。
- 输出 compile report。

#### 输出

```python
context.state["compile_validation"] = {
    "passed": False,
    "issues": [],
    "suggestions": [],
    "mode": "simulated_compile_check",
}
```

#### Artifact

```text
compile_report.json
```

#### warning 示例

```text
当前环境未配置真实 STS8200S 编译链，仅进行了结构化预检。
```

---

### 9.10 ReviewAgent

#### 定位

这是本阶段最重要的新 Agent。

ReviewAgent 负责汇总和判断：

- TestPlan 是否完整。
- 资源映射是否有冲突。
- RAG 是否命中。
- 生成代码是否完整。
- 静态校验是否通过。
- 编译预检是否通过。
- 是否可以进入人工复核。
- 是否建议上机。
- 哪些地方需要 ATE 工程师重点检查。

#### 输出

```python
context.state["review"] = {
    "overall_status": "needs_human_review",
    "summary": "...",
    "risk_level": "medium",
    "must_review_items": [],
    "recommendations": [],
}
```

#### Review 状态建议

```text
pass
needs_human_review
blocked
```

#### 重要约束

自动生成代码永远不能直接标记为“可直接上机”。

必须输出：

```text
生成结果仅用于辅助测试开发，需由 ATE 工程师复核后再上机使用。
```

---

### 9.11 EngineeringPackageAgent

#### 职责

- 汇总所有 artifact。
- 生成工程交付包。
- 生成最终报告。
- 写入 run artifacts。

#### 输出

```python
context.state["engineering_package"] = {
    "files": [],
    "final_report": "...",
    "download_links": [],
}
```

#### Artifacts

```text
final_report.md
run_summary.json
generated_test_program.cpp
testplan.xlsx
resource_map.xlsx
```

---

## 10. HumanReviewRequiredAgent

### 10.1 触发条件

当出现以下情况时，应触发人工复核：

- 参数缺失严重。
- Datasheet 解析失败。
- 资源映射冲突严重。
- 代码生成失败。
- 静态校验严重失败。
- 编译预检严重失败。

### 10.2 输出

```python
context.state["human_review"] = {
    "required": True,
    "reason": "...",
    "missing_inputs": [],
    "suggested_actions": [],
}
```

### 10.3 状态

```text
human_review_required
```

### 10.4 注意

第一版不需要实现真正的人工输入闭环，只需要在 run 中明确标记人工复核要求。

---

## 11. fallback / retry 策略

### 11.1 RAG fallback

如果 RAG 不可用或无结果：

```text
继续使用模板生成代码。
添加 warning：RAG 检索无有效结果，代码生成已降级为模板模式，需重点人工复核。
```

---

### 11.2 LLM fallback

如果 LLM 调用失败：

```text
使用规则模板或已有默认模板。
添加 warning：LLM 调用失败，已使用规则模板兜底。
```

---

### 11.3 StaticValidation fallback

如果静态校验失败：

```text
不直接终止。
进入 ReviewAgent。
由 ReviewAgent 输出风险等级。
```

---

### 11.4 CompileValidation fallback

如果没有真实编译器：

```text
标记为 simulated_compile_check。
输出 warning：当前环境未配置真实 STS8200S 编译链，仅进行了结构化预检。
```

---

### 11.5 Retry

至少为 LLM 或 RAG 相关步骤提供最多 1 次 retry。

示例：

```python
def max_retries(self) -> int:
    return 1
```

---

## 12. 强化 RunStore 和 Artifact Store

### 12.1 目标

当前 run store 如果只是保存摘要，需要升级为更清晰的 artifact 结构。

### 12.2 推荐目录结构

```text
data/processed/agent_runs/
└── {run_id}/
    ├── run.json
    ├── steps.json
    ├── artifacts/
    │   ├── testplan.json
    │   ├── testplan.xlsx
    │   ├── resource_map.json
    │   ├── codegen_plan.json
    │   ├── generated_test_program.cpp
    │   ├── static_validation.json
    │   ├── compile_report.json
    │   ├── review.json
    │   └── final_report.md
    └── logs/
        └── agent.log
```

---

### 12.3 Artifact 字段

每个 artifact 建议包含：

```python
{
    "name": "generated_test_program.cpp",
    "type": "code",
    "format": "cpp",
    "path": "...",
    "producer": "CodeAssemblyAgent",
    "created_at": "...",
    "summary": "...",
    "preview": "...",
}
```

---

### 12.4 API 要求

确保 `AgentRuns API` 至少支持：

```text
GET /api/v1/agent-runs
GET /api/v1/agent-runs/{run_id}
GET /api/v1/agent-runs/{run_id}/artifacts
GET /api/v1/agent-runs/{run_id}/artifacts/{artifact_name}
```

如果最后一个接口暂时不方便实现，可以先返回 artifact 元信息和可下载路径。

---

## 13. AgentRuns 前端升级

在现有 AgentRuns 页面基础上增加以下能力。

### 13.1 Flow 类型展示

展示 run 所属 flow：

```text
module1_testplan
module2_resource
module3_codegen
full_ate_development
```

---

### 13.2 Step Timeline

每个 step 展示：

- `agent_name`
- `status`
- `message`
- `warnings`
- `errors`
- `artifact count`

---

### 13.3 Artifact 列表

展示：

- 文件名
- 类型
- 生产 Agent
- 摘要
- 下载 / 预览按钮

---

### 13.4 Review Summary

重点展示 ReviewAgent 输出：

- `overall_status`
- `risk_level`
- `must_review_items`
- `recommendations`

---

### 13.5 状态颜色建议

```text
success: 绿色
warning: 黄色
failed: 红色
human_review_required: 橙色
skipped: 灰色
```

---

## 14. Agent Run 创建入口

如果当前 `/api/v1/agent-runs` 只能查看 run，需要增加创建 full flow 的能力。

### 14.1 推荐接口

```text
POST /api/v1/agent-runs
```

### 14.2 请求示例

```json
{
  "flow_name": "full_ate_development",
  "goal": "根据这个 Datasheet 生成 STS8200S 测试程序，并输出风险报告",
  "file_id": "xxx",
  "pdf_path": "xxx",
  "enable_diagnosis": false
}
```

### 14.3 响应示例

```json
{
  "run_id": "...",
  "flow_name": "full_ate_development",
  "status": "success",
  "steps": [],
  "artifacts": [],
  "review": {},
  "warnings": [],
  "errors": []
}
```

---

## 15. 测试要求

至少新增基础测试或脚本验证。

### 15.1 RunStore 测试

验证：

- 能保存 run。
- 能读取 run。
- 能列出 run。
- 能读取 artifacts。

---

### 15.2 AgentController 测试

验证：

- 顺序执行 flow。
- agent 失败时记录错误。
- `should_run` 为 false 时跳过。
- retry 生效。
- artifact 被记录。

---

### 15.3 full_ate_flow 最小测试

可以使用 mock 输入和 mock service，验证：

```text
InputResolveAgent
→ TestPlanExtractAgent
→ ParamValidationAgent
→ ReviewAgent
→ EngineeringPackageAgent
```

能够完整跑通。

---

## 16. README 更新要求

在 README 中新增如下章节。

### 16.1 Agent Run 平台

```markdown
## Agent Run 平台

本项目在原有 ATE AI 工作流平台基础上新增 Agent Run 架构，通过 AgentController 统一管理任务运行、步骤执行、中间产物、错误与警告。

### 核心能力

- RunContext：统一维护一次任务运行的上下文
- AgentStepResult：记录每个 Agent Step 的状态和产物
- RunStore：保存运行记录和 artifacts
- AgentRuns API：支持查看历史运行和中间产物
- AgentRuns 前端页面：支持流程回看和排错
```

---

### 16.2 full_ate_development_flow

```markdown
## full_ate_development_flow

新增跨模块 ATE 测试开发 Agent Flow，支持从 Datasheet 输入到测试程序生成的自动化流程：

1. 输入解析
2. TestPlan 抽取
3. 参数校验
4. STS8200S 资源映射
5. RAG 检索
6. 代码生成规划
7. C++ 测试程序生成
8. 静态校验
9. 编译预检
10. 工程复核总结
11. 工程交付包生成

生成结果仅用于辅助测试开发，需由 ATE 工程师复核后再上机使用。
```

---

## 17. 文档更新要求

新增或更新：

```text
docs/agent-controller-implementation-plan.md
docs/full-ate-development-flow.md
docs/agent-run-artifacts.md
```

---

### 17.1 docs/full-ate-development-flow.md 内容建议

应包含：

- 设计目标
- flow 架构图
- agent step 说明
- state 字段说明
- artifacts 说明
- fallback 说明
- 风险控制说明

---

### 17.2 docs/agent-run-artifacts.md 内容建议

应包含：

- artifact 目录结构
- artifact 元数据字段
- artifact 生产者 producer
- artifact 下载与预览方式
- artifact 与 run 的关系

---

## 18. 验收标准

完成后应满足以下标准。

---

### 18.1 后端验收

- 存在 `full_ate_development_flow.py`。
- `AgentController` 支持条件执行或 `should_run`。
- 至少支持一种 retry 机制。
- 至少支持一种 `human_review_required` 状态。
- 新增 `ReviewAgent`。
- `RunStore` 能保存 artifact 文件或 artifact metadata。
- `AgentRuns API` 能查看 run 和 artifacts。

---

### 18.2 Flow 验收

`full_ate_development_flow` 至少包含：

```text
InputResolveAgent
TestPlanExtractAgent
ParamValidationAgent
ResourceMappingAgent
RagRetrievalAgent
CodegenPlanningAgent
CodeAssemblyAgent
StaticValidationAgent
CompileValidationAgent
ReviewAgent
EngineeringPackageAgent
```

如果某些 Agent 暂时无法完整接入真实 service，可以先 mock 或降级，但必须保留清晰 TODO 和 warning。

---

### 18.3 前端验收

AgentRuns 页面至少展示：

- run 列表
- run 详情
- step timeline
- artifacts
- warnings
- errors
- review summary

---

### 18.4 文档验收

README 和 docs 必须说明：

- Agent Run 架构
- full_ate_development_flow
- artifacts
- 复核提醒
- 降级策略

---

## 19. 推荐开发顺序

### Step 1：代码格式化与现状保护

- 格式化 `backend/app`。
- 确保现有功能不坏。
- 不改业务逻辑。

---

### Step 2：增强 AgentController

- 支持 `should_run`。
- 支持 retry。
- 支持 `skipped`。
- 支持 `human_review_required`。
- 支持 artifact 注册。

---

### Step 3：升级 RunStore

- `run_id` 独立目录。
- `run.json`。
- `steps.json`。
- `artifacts/` 目录。
- artifact metadata。

---

### Step 4：新增 ReviewAgent

- 先接入现有 `module3_codegen_flow`。
- 汇总代码生成、静态校验、编译预检结果。
- 生成 `review.json` 和 `review summary`。

---

### Step 5：新增 full_ate_development_flow

- 串联 TestPlan、ResourceMap、RAG、Codegen、Review、Package。
- 支持参数校验分支。
- 支持 RAG fallback。
- 支持 human review 状态。

---

### Step 6：升级 AgentRuns API

- 支持创建 full flow run。
- 支持 artifact 查看。
- 支持 review summary 返回。

---

### Step 7：升级前端 AgentRuns 页面

- step timeline。
- artifact list。
- review summary。
- warnings / errors 展示。

---

### Step 8：更新 README 和 docs

- 写清楚 agent 化架构。
- 写清楚 full flow。
- 写清楚 artifacts。
- 写清楚复核和风险控制。

---

## 20. 面试表达目标

完成后，项目可以这样介绍：

> 我对 ATE-AI-Platform 做了二阶段 Agent 化升级。第一阶段先引入 AgentController、RunContext、AgentStepResult 和 RunStore，把原本路由直调 service 的模式升级为可追踪的 Agent Run 模型。第二阶段进一步新增 full_ate_development_flow，将 Datasheet 解析、TestPlan 抽取、资源映射、RAG 检索、代码生成、静态校验、编译预检和 ReviewAgent 串成跨模块 Agent 工作流，并通过 artifacts 保存中间产物，支持运行回看、风险提示和人工复核。

重点体现：

- 不是简单调 API。
- 有统一 run 模型。
- 有 agent step。
- 有 artifacts。
- 有条件分支。
- 有 fallback / retry。
- 有 ReviewAgent。
- 有真实工业 ATE 场景。
- 有工程化可追踪能力。

---

## 21. 禁止事项

不要做以下事情：

1. 不要删除原有模块 API。
2. 不要把所有逻辑写进一个大函数。
3. 不要让 LLM 无约束直接生成最终代码。
4. 不要把自动生成代码标记为“可直接上机”。
5. 不要忽略 RAG 或 LLM 失败。
6. 不要只返回最终结果而不记录步骤。
7. 不要只做前端展示而没有真实后端 run 记录。
8. 不要引入复杂依赖导致项目无法启动。
9. 不要把真实 API Key 写进代码。
10. 不要破坏现有 Electron / React / FastAPI 运行方式。

---

## 22. Codex 执行指令示例

### 第一次指令

```text
请阅读 .skills/ate-agent-platform-upgrade/SKILL.md，先执行 Step 1 到 Step 3：格式化后端代码、增强 AgentController 的 should_run/retry/skipped/human_review_required 能力，并升级 RunStore 的 artifacts 目录结构。不要改动现有业务功能。
```

---

### 第二次指令

```text
继续根据 Skill 实现 ReviewAgent，并先接入现有 module3_codegen_flow，要求能在 run 详情中看到 review summary 和 artifacts。
```

---

### 第三次指令

```text
继续实现 full_ate_development_flow，串联 TestPlan、ResourceMap、RAG、Codegen、Review 和 EngineeringPackage，并更新 AgentRuns API、前端页面和 README。
```

---

## 23. 最终效果

完成本阶段后，项目应从：

```text
轻量 Agent Run 平台
```

升级为：

```text
面向 ATE 测试开发的跨模块 Agent 工作流系统
```

核心能力包括：

- 用户输入自然语言目标。
- 系统自动执行跨模块任务链。
- 每个 Agent Step 可追踪。
- 每个关键中间产物可回看。
- RAG / LLM 失败有 fallback。
- 校验失败有 ReviewAgent 汇总风险。
- 最终结果明确提示人工复核。
- 前端运行中心支持回看、排错、预览和下载 artifacts。
