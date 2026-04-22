# 关键算法流程图

## Datasheet 到 TestPlan 的关键流程

```mermaid
flowchart TD
    A[上传 Datasheet PDF] --> B[文件类型和大小校验]
    B --> C[PDF 文本与表格解析]
    C --> D[页面过滤]
    D --> E[有效页面分块]
    E --> F[本地规则预提取]
    E --> G[LLM 并发结构化提取]
    F --> H[参数和引脚合并]
    G --> H
    H --> I[字段标准化和去重]
    I --> J[A/B/C 类参数分类]
    J --> K[STS8200S 兼容性校验]
    K --> L[量程推荐和风险提示]
    L --> M[生成 TestPlan JSON]
    L --> N[生成 TestPlan Excel]
    M --> O[前端展示和下载]
    N --> O
```

## 资源映射与代码生成流程

```mermaid
flowchart TD
    A[TestPlan JSON] --> B[读取芯片类型和引脚定义]
    B --> C{是否存在引脚定义}
    C -- 是 --> D[自动构建 PinMapping]
    C -- 否 --> E[提示上传 PinMapping 模板]
    D --> F[识别引脚方向和电源/地/IO 分组]
    F --> G[选择 STS8200S 资源]
    G --> H[生成资源映射表]
    G --> I[生成 PGS 配置]
    G --> J[生成 BOM 和 SVG 示意图]
    H --> K[代码生成模块]
    K --> L[选择测试项]
    L --> M[模板生成 C++ 骨架]
    M --> N[RAG 注入 STS8200S 知识]
    N --> O[静态规则校验]
    O --> P[输出测试代码和风险提示]
```

## 良率诊断流程

```mermaid
flowchart TD
    A[输入诊断参数] --> B[生成或接入 VI 波形数据]
    B --> C[特征提取]
    C --> D[异常检测模型]
    D --> E[异常点识别]
    E --> F[故障类型分类]
    F --> G[良率/FTY/趋势计算]
    G --> H[前端可视化展示]
```

## 后续可扩展点

- 将 PDF 文本解析扩展为 OCR + 视觉模型。
- 将资源映射规则扩展为完整 DUT 原理图辅助设计。
- 将良率诊断输入从仿真数据扩展为工控机实时数据。
- 将本地 LLM 调用迁移到云端任务服务，实现日志集中管理和权限控制。
