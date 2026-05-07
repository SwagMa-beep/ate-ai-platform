# 项目框架图（现状版）

```mermaid
flowchart LR
    User[用户 / ATE 测试工程师]

    subgraph Desktop[桌面交付层]
        Electron[Electron 桌面端]
        Frontend[React + TypeScript + Vite]
    end

    subgraph FrontViews[前端工作区]
        Workspace[ATE Agent 工作台]
        Runs[Agent 运行中心]
        TestPlanUI[Datasheet / TestPlan]
        ResourceUI[STS8200S 资源映射]
        CodegenUI[RAG 测试代码生成]
        DiagnosisUI[良率诊断]
    end

    subgraph API[FastAPI 接口层]
        TestPlanAPI[/api/v1/testplan]
        ResourceAPI[/api/v1/resource-map]
        CodegenAPI[/api/v1/codegen]
        RunAPI[/api/v1/agent-runs]
        RagAPI[/api/v1/rag]
        DiagnosisAPI[/api/v1/diagnosis]
        TestProgramAPI[/api/v1/testprogram]
    end

    subgraph AgentCore[Agent 编排层]
        Controller[AgentController]
        RunStore[RunStore]
        FullFlow[full_ate_development]
        DeliveryFlow[post_review_delivery]
        RevisionFlow[post_review_revision]
        ReviewSvc[ReviewService]
    end

    subgraph Biz[业务服务层]
        TestPlanSvc[TestPlanService]
        ResourceSvc[ResourceMappingService]
        CodegenSvc[CodegenService]
        CompileSvc[CompileValidationService]
        DiagnosisSvc[YieldDiagnosisService]
        TestProgramSvc[TestProgramService]
    end

    subgraph AI[AI 与知识增强层]
        PDFParser[pdfplumber + 页面过滤]
        LLM[DeepSeek LLM]
        RAG[RAGService]
        Rules[本地规则 / STS8200S 平台规则]
        Knowledge[Enterprise Code Knowledge]
    end

    subgraph Output[产物与数据层]
        Uploads[data/uploads]
        Processed[data/processed]
        RunsDir[data/processed/agent_runs]
        Files[TestPlan / PGS / BOM / SVG / Code / Package]
    end

    User --> Electron
    Electron --> Frontend

    Frontend --> Workspace
    Frontend --> Runs
    Frontend --> TestPlanUI
    Frontend --> ResourceUI
    Frontend --> CodegenUI
    Frontend --> DiagnosisUI

    Workspace --> RunAPI
    Runs --> RunAPI
    TestPlanUI --> TestPlanAPI
    ResourceUI --> ResourceAPI
    CodegenUI --> CodegenAPI
    DiagnosisUI --> DiagnosisAPI

    RunAPI --> Controller
    RunAPI --> RunStore
    RunAPI --> FullFlow
    RunAPI --> DeliveryFlow
    RunAPI --> RevisionFlow

    FullFlow --> ReviewSvc
    FullFlow --> TestPlanSvc
    FullFlow --> ResourceSvc
    FullFlow --> CodegenSvc
    FullFlow --> CompileSvc
    FullFlow --> TestProgramSvc

    TestPlanAPI --> TestPlanSvc
    ResourceAPI --> ResourceSvc
    CodegenAPI --> CodegenSvc
    DiagnosisAPI --> DiagnosisSvc
    TestProgramAPI --> TestProgramSvc

    TestPlanSvc --> PDFParser
    TestPlanSvc --> LLM
    TestPlanSvc --> Rules
    CodegenSvc --> RAG
    CodegenSvc --> LLM
    CodegenSvc --> Knowledge
    CodegenSvc --> Rules
    ResourceSvc --> Rules

    RAG --> LLM
    RagAPI --> RAG

    TestPlanSvc --> Uploads
    TestPlanSvc --> Processed
    ResourceSvc --> Processed
    CodegenSvc --> Processed
    TestProgramSvc --> Processed
    Controller --> RunStore
    RunStore --> RunsDir
    Processed --> Files
```

## 框架说明

这版框架图对应你当前已经实现的项目现状，重点不是单个模块，而是“模块能力 + Agent 编排 + 运行记录 + 交付产物”四层联动。

### 1. 桌面与前端层

- 系统通过 `Electron` 打包成桌面应用。
- 前端基于 `React + TypeScript + Vite`。
- 当前主要页面包括：
  - `ATE Agent 工作台`
  - `Agent 运行中心`
  - `Datasheet / TestPlan`
  - `STS8200S 资源映射`
  - `RAG 测试代码生成`
  - `良率诊断`

### 2. 接口与 Agent 编排层

- `FastAPI` 提供统一接口入口。
- `AgentController` 负责：
  - step 编排
  - 重试
  - 条件执行
  - review 中断
  - 耗时与质量记录
- `RunStore` 负责：
  - 保存 `run.json`
  - 保存 `steps.json`
  - 保存 `artifacts/index.json`
  - 为每次运行建立独立目录

### 3. 当前已落地的跨模块流程

- `full_ate_development`
  - 将 Datasheet 提取、参数校验、资源映射、RAG 检索、测试规划、代码生成、静态校验、编译预检、工程复核和打包串成统一流程

- `post_review_delivery`
  - 用于批准后的交付整理
  - 输出 `delivery_summary`、`bench_checklist`、`final_package`

- `post_review_revision`
  - 用于打回后的修订流转
  - 生成 revision request 和后续修订上下文

### 4. 业务服务层

- `TestPlanService`
  - 处理 PDF 提取、参数结构化、引脚识别、结果导出
- `ResourceMappingService`
  - 生成 STS8200S 资源映射、PGS、BOM、SVG
- `CodegenService`
  - 生成测试规划、测试代码、静态检查与工程包
- `CompileValidationService`
  - 执行编译预检
- `YieldDiagnosisService`
  - 输出轻量化诊断结果

### 5. AI 与知识增强层

- `pdfplumber + 页面过滤`
  - 当前 PDF 提取主链
- `DeepSeek LLM`
  - 用于结构化提取和代码增强
- `RAGService`
  - 提供 STS8200S 平台知识增强
- `Enterprise Code Knowledge`
  - 提供企业经验代码和模板兜底
- `本地规则 / STS8200S 平台规则`
  - 保证输出更接近真实工程约束

## 当前项目边界

这张图展示的是**当前真实完成态**，因此也保留了平台边界：

- 已完成 ATE 开发辅助闭环
- 已具备交付整理和 review 流转
- 尚未实现批准后自动驱动真实 STS8200S 机台执行测试
- OCR 识别链路仍未正式进入主流程

## 适用场景

这份图更适合用于：

- 项目答辩
- 结题材料
- README 或技术文档补充
- 向老师或评委说明“现在的系统已经不是单点功能，而是 Agent 化平台”
