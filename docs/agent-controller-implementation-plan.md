# ATE AI Platform Agent Controller 整体实现方案

## 1. 目标

将当前偏 `workflow` 的平台，逐步升级为一个以 **Agent Controller** 为核心、各模块逐步 agent 化的工程平台，同时尽量复用已有模块能力，避免大范围推倒重来。

当前目标不是重新设计一套全新平台，而是：

- 保留现有模块一、模块二、模块三、模块四能力
- 先在现有工程上增加统一编排层
- 逐步把模块从“路由直调 service”演进为“controller 调度 agent”
- 最终让平台既能跑业务流程，又具备 agent 项目的统一控制、追踪、回放和扩展能力

---

## 2. 当前架构判断

当前系统更像一个典型的 `workflow platform`，而不是完整的 `agent platform`。

### 2.1 当前主链路

当前整体更接近：

```text
Frontend
  -> API Route
    -> Service
      -> Artifact / Result
```

例如：

- 模块一：`testplan.py -> testplan_service.py`
- 模块二：`resource_map.py -> resource_mapping_service.py`
- 模块三：`codegen.py -> planner/service/validator/testprogram_service`

### 2.2 当前 workflow 特征

当前系统已经具备：

- 分阶段处理能力
- 中间结果产物
- 任务持久化
- 推荐 / 规划 / 校验 / 导出

但仍然缺少这些 agent 平台核心层：

- 统一的 agent controller
- 统一的 run context
- 统一的 artifact store
- agent registry
- flow definition
- step-level orchestration
- retry / fallback / branch 的统一调度

### 2.3 结论

所以当前平台本质上是：

> 一个已经具备较强工程闭环的 workflow 平台，正在具备向 agent 平台升级的条件。

---

## 3. 目标架构

建议最终演进为如下结构：

```text
Frontend
  -> Agent Controller
      -> Run Context / Artifact Store
      -> ExtractorAgent
      -> ResourceMappingAgent
      -> CodegenPlanningAgent
      -> CodeAssemblyAgent
      -> CompileValidationAgent
      -> EngineeringPackageAgent
      -> ReviewAgent
```

### 3.1 核心思想

不再让前端或路由直接串业务 service，而是：

1. 前端提交一个任务
2. Controller 创建一次 run
3. Controller 读取 flow 定义
4. Controller 依次调度 agent
5. 每个 agent 产出 artifact
6. Controller 汇总结果、记录 step 状态、支持回放和重试

---

## 4. 架构分层设计

建议增加 4 个核心层。

### 4.1 Agent Controller

统一负责：

- 创建 run
- 管理 run 状态
- 加载 flow 定义
- 调度 agent
- 汇总 step 结果
- 控制重试 / 中断 / 回退
- 输出统一结果

### 4.2 Agent Registry

统一注册系统内已有 agent，例如：

- `extractor`
- `resource_mapper`
- `codegen_planner`
- `code_assembler`
- `compile_validator`
- `engineering_packager`
- `review_agent`

作用：

- 避免 controller 硬编码具体实现
- 方便后续替换 agent 实现
- 方便测试与 mock

### 4.3 Run Context / Artifact Store

统一维护：

- 输入上下文
- 中间结果
- 最终结果
- warning / error
- 当前 step
- step 执行日志

所有 agent 不直接互相传散乱字段，而是通过：

- `RunContext`
- `ArtifactStore`

共享与沉淀结果。

### 4.4 Flow Definitions

把“模块一提取流”“模块三代码生成流”定义成显式流程，而不是写死在 route 里。

例如：

```text
module3_codegen_flow:
  - codegen_planning_agent
  - code_assembly_agent
  - compile_validation_agent
  - engineering_package_agent
  - review_agent(optional)
```

---

## 5. 推荐目录结构

建议新增如下目录和文件：

```text
backend/app/services/agent_controller.py
backend/app/services/agent_registry.py
backend/app/services/run_store.py
backend/app/services/artifact_store.py

backend/app/agents/base.py
backend/app/agents/types.py
backend/app/agents/extractor_agent.py
backend/app/agents/resource_mapping_agent.py
backend/app/agents/codegen_planning_agent.py
backend/app/agents/code_assembly_agent.py
backend/app/agents/compile_validation_agent.py
backend/app/agents/engineering_package_agent.py
backend/app/agents/review_agent.py

backend/app/flows/module1_extract_flow.py
backend/app/flows/module3_codegen_flow.py
```

如果要更稳一点，第一版也可以只新增：

```text
backend/app/services/agent_controller.py
backend/app/agents/
backend/app/flows/module3_codegen_flow.py
```

先只改模块三。

---

## 6. 核心数据模型

第一版不必急着大改数据库，可以先做：

- 结构化 Python 对象
- JSON 落盘
- 与现有文件产物并存

### 6.1 AgentRun

表示一次完整运行。

```json
{
  "run_id": "run_20260426_xxx",
  "flow": "module3_codegen",
  "status": "running",
  "created_at": "...",
  "updated_at": "...",
  "input": {
    "file_id": "...",
    "chip_name": "...",
    "chip_type": "digital"
  },
  "artifacts": ["artifact_1", "artifact_2"],
  "steps": ["planner", "assembler", "validator", "packager"],
  "errors": [],
  "warnings": []
}
```

### 6.2 Artifact

表示中间产物或最终产物。

```json
{
  "artifact_id": "artifact_xxx",
  "run_id": "run_xxx",
  "type": "codegen_plan",
  "path": ".../codegen_plan.json",
  "format": "json",
  "producer": "codegen_planning_agent",
  "summary": {
    "items": 6,
    "requires_vector": true
  }
}
```

### 6.3 AgentStepResult

表示单个 agent 执行结果。

```json
{
  "agent": "compile_validator",
  "status": "completed",
  "warnings": [],
  "errors": [],
  "output_artifacts": ["artifact_compile_report"]
}
```

---

## 7. Agent 基类设计

建议统一一个最小接口。

```python
class BaseAgent:
    agent_name = "base"

    def run(self, context: RunContext) -> AgentStepResult:
        raise NotImplementedError
```

### 7.1 RunContext 建议字段

- `run_id`
- `flow_name`
- `input_payload`
- `artifacts`
- `warnings`
- `errors`
- `metadata`
- `logger`

这样每个 agent 的职责更清晰：

- 读取上下文
- 处理本步骤
- 输出 step result
- 落中间 artifact

---

## 8. Agent Controller 设计

### 8.1 主要职责

`AgentController` 负责：

1. 创建一次 run
2. 装载 flow
3. 顺序执行 agent
4. 记录 step 状态
5. 存储 artifacts
6. 处理错误与重试
7. 生成最终 API 输出

### 8.2 伪代码示意

```python
controller.run_flow(
    flow_name="module3_codegen",
    payload={...}
)
```

```python
def run_flow(flow_name, payload):
    run = run_store.create(flow_name, payload)
    context = RunContext.from_run(run)
    steps = flow_registry.get(flow_name)

    for agent in steps:
        step_result = agent.run(context)
        run_store.record_step(run.run_id, step_result)
        artifact_store.save(step_result.output_artifacts)

        if step_result.errors and step_result.status == "failed":
            break

    return run_store.finalize(run.run_id)
```

---

## 9. 模块三第一阶段实现方案

模块三是当前最适合优先 agent 化的模块。

### 9.1 当前模块三现状

模块三当前已经具备：

- 推荐测试项
- 生成前 plan
- 企业代码知识库
- RAG 检索增强
- 代码生成
- 编译预检
- 工程包导出

这本质上已经是半条 agent pipeline，只是还没有统一 controller。

### 9.2 第一阶段 flow

建议定义：

```text
module3_codegen_flow
  -> CodegenPlanningAgent
  -> CodeAssemblyAgent
  -> CompileValidationAgent
  -> EngineeringPackageAgent
  -> ReviewAgent(optional)
```

### 9.3 与现有 service 的映射

直接复用已有实现：

- `codegen_planner_service.py` -> `CodegenPlanningAgent`
- `codegen_service.py` -> `CodeAssemblyAgent`
- `compile_validation_service.py` -> `CompileValidationAgent`
- `testprogram_service.py` -> `EngineeringPackageAgent`

即：

> 第一阶段只改编排方式，不重写业务逻辑。

### 9.4 API 侧改法

当前：

```text
codegen.py
  -> planner
  -> service.generate
  -> compile validator
  -> package export
```

第一阶段改成：

```text
codegen.py
  -> AgentController.run_flow("module3_codegen", payload)
```

对前端保持接口兼容，优先不改外部返回格式。

---

## 10. 模块一第二阶段方案

模块一后续也适合接入 controller，但不建议一开始就全量重构。

### 10.1 推荐 flow

```text
module1_extract_flow
  -> UploadResolveAgent
  -> PdfExtractAgent
  -> RuleValidateAgent
  -> ArtifactExportAgent
```

### 10.2 可复用代码

- `testplan_service.py`
- `llm_extractor.py`
- `task_status_store.py`

### 10.3 收益

这样模块一异步任务中心以后就能自然迁移到统一 run 模型中。

---

## 11. 模块二第三阶段方案

模块二可拆成：

```text
module2_resource_flow
  -> PinLoadAgent
  -> ResourceMappingAgent
  -> PGSGenerationAgent
  -> SvgExportAgent
  -> SummaryAgent
```

可复用：

- `resource_mapping_service.py`
- `pgs_generation_service.py`

---

## 12. 前端改造方案

前端不必一开始就推翻页面，只需逐步从“接口驱动”转向“run 驱动”。

### 12.1 第一阶段

在不破坏现有页面的前提下：

- 提交任务时创建 run
- 前端轮询 run 状态
- 前端读取 run artifacts

### 12.2 统一前端视图

未来模块一任务中心、模块三代码生成页都可以统一成：

- 当前 flow
- 当前 step
- step 状态
- warnings / errors
- 中间 artifacts
- 最终结果

### 12.3 CodeLab 可增加的 run 信息

- `run_id`
- 当前执行步骤
- 已完成 agent
- 失败在哪个 agent
- 生成计划 artifact
- 工程包 artifact

---

## 13. 接口设计建议

建议新增一套统一 run 接口，同时保留旧接口以保证兼容。

### 13.1 新增接口

- `POST /api/v1/agent-runs`
- `GET /api/v1/agent-runs/{run_id}`
- `GET /api/v1/agent-runs/{run_id}/artifacts`
- `POST /api/v1/agent-runs/{run_id}/retry`
- `POST /api/v1/agent-runs/{run_id}/cancel`

### 13.2 旧接口保留

- `/codegen/generate`
- `/codegen/plan`
- `/testplan/extract-async`

旧接口内部逐步改成调用 controller。

这样可以保证：

- 前端无需一次性大改
- 答辩和已有 demo 不受影响
- 后续可以逐步迁移

---

## 14. 分阶段实施计划

### Phase 1：模块三内部 agent 化

目标：

- 不改外部体验
- 先改内部结构

内容：

- 新建 `BaseAgent`
- 新建 `AgentController`
- 新建 `module3_codegen_flow`
- 把模块三 service 包装成 agent
- `codegen.py` 改成调用 controller
- 保持旧接口结构

收益：

- 风险最低
- 收益最大
- 最容易体现 agent 化价值

### Phase 2：统一 run / artifact 模型

内容：

- 新建 `run_store.py`
- 新建 `artifact_store.py`
- 给模块三返回 `run_id`
- 前端显示 step 状态和 artifact

收益：

- 真正开始从 workflow 过渡到 agent platform

### Phase 3：模块一接入

内容：

- 将异步提取链改成 flow
- 将任务系统逐步并入 run 模型

### Phase 4：模块二接入

内容：

- 资源映射、PGS、SVG 输出纳入 artifact 流

### Phase 5：跨模块大链路

最终形成：

```text
Extract Flow
  -> Resource Mapping Flow
  -> Codegen Flow
  -> Review Flow
```

---

## 15. 当前最推荐落地版本

当前最推荐做的不是“大而全 agent 平台”，而是：

### V1 Agent 化目标

- 只改模块三
- 保留现有接口
- 新增内部 controller
- 新增 run / artifact 结构
- 前端先只做少量 run 视图预留

原因：

- 风险低
- 改动集中
- 最符合你当前项目现状
- 最容易在答辩或演示中讲清楚“agent 化升级”

---

## 16. 预期收益

完成后，项目会从：

```text
多个 service 串起来的 workflow
```

升级成：

```text
一个 controller 驱动多个 agent，围绕 artifact 运转的平台
```

带来的收益包括：

- 职责边界更清晰
- 每一步更可追踪
- 更容易重试与回放
- 更容易做 review / fallback
- 更容易扩展为多 agent 协作平台
- 更符合 agent 项目的技术叙事

---

## 17. 一句话实施建议

先把 **模块三做成第一条标准 agent flow**，不要先全局重构。

这是风险最低、收益最大、最容易让项目气质从 workflow 升级为 agent platform 的实施路径。

