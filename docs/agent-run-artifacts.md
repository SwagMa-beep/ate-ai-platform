# Agent Run Artifacts 说明

## 目标

`RunStore` 现在不仅保存运行摘要，还会为每次运行建立独立目录，并保存步骤信息与产物索引，方便：

- 回看每一步输出了什么
- 给运行中心展示产物摘要
- 为后续 full flow 串联提供统一中间产物结构

## 目录结构

每次运行会落到：

```text
data/processed/agent_runs/{run_id}/
├── run.json
├── steps.json
└── artifacts/
    ├── index.json
    ├── codegen_plan_1.json
    ├── generated_code_1.json
    ├── static_analysis_1.json
    └── ...
```

## 文件说明

### `run.json`

保存整次运行的聚合结果，包括：

- `run_id`
- `flow_name`
- `status`
- `input_payload`
- `steps`
- `artifacts`
- `warnings`
- `errors`
- `shared`

### `steps.json`

只保存步骤数组，便于单独查看时间线：

- `agent`
- `status`
- `message`
- `warnings`
- `errors`
- `artifacts`
- `metadata`
- `next_action`
- `requires_human_review`

### `artifacts/index.json`

保存本次运行的全部产物索引，供运行中心快速读取。

### `artifacts/*.json`

保存单个产物的 metadata 快照。当前阶段主要保存：

- `name`
- `type`
- `producer`
- `summary`
- `created_at`
- `run_id`
- `metadata_path`

## 当前支持的典型产物

### 模块一

- `source_pdf`
- `testplan_result`

### 模块二

- `mapping_input`
- `resource_mapping`

### 模块三

- `codegen_plan`
- `generated_code`
- `static_analysis`
- `compile_validation`
- `review_summary`
- `engineering_package`

## 与运行中心的关系

运行中心当前主要使用：

- `run.json`
- `artifacts/index.json`

这样页面既能展示：

- 当前 run 走了哪些阶段
- 每个阶段产生了多少产物
- 每个产物的摘要字段

同时又不必直接解析业务代码或最终工程文件。

## 当前边界

当前阶段的 artifacts 仍然以 **metadata 和摘要为主**：

- 有些 artifact 指向真实文件
- 有些 artifact 只有摘要信息

这已经足够支撑：

- 运行回看
- 调试定位
- review summary 展示

后续如果继续进入 full flow 阶段，可以补充：

- 真实文件预览
- artifact 下载接口
- 产物版本对比
- 更完整的 producer / dependency 关系
