# 关键技术实现细节说明

## 1. 技术实现总览

本项目采用“Electron 桌面端 + React 前端 + FastAPI 后端 + DeepSeek 大模型 + STS8200S 工程规则”的实现方案。系统以 Datasheet PDF 为输入，经过上传、解析、页面过滤、大模型结构化提取、本地规则兜底、平台规则校验和工程文件生成，最终输出 TestPlan、资源映射、PGS、BOM、SVG、C++ 测试代码骨架和诊断结果。

后端主服务在 `backend/app/main.py` 中创建 FastAPI 应用，并挂载以下正式业务路由：

| 模块 | 路由前缀 | 主要作用 |
|---|---|---|
| TestPlan 提取 | `/api/v1/testplan` | PDF 上传、异步提取、状态查询、文件下载 |
| 资源映射 | `/api/v1/resource-map` | DUT 引脚资源映射、PGS、BOM、SVG 输出 |
| 测试代码生成 | `/api/v1/codegen` | STS8200S C++ 测试代码骨架生成 |
| RAG 知识增强 | `/api/v1/rag` | STS8200S 知识库状态、检索和构建 |
| 良率诊断 | `/api/v1/diagnosis` | 仿真 VI 波形、异常检测和诊断结果 |

其中 `backend/app/api/v1/testprogram.py` 目前存在于代码目录中，但未挂载到主应用，不属于当前 App 的正式对外接口。当前正式代码生成接口为 `/api/v1/codegen/*`。

## 2. 前后端数据流

### 2.1 上传与任务创建

用户在前端提取器页面选择 Datasheet PDF 后，前端通过 `apps/src/api/backend.ts` 调用后端上传接口：

```text
POST /api/v1/testplan/upload
```

后端在 `backend/app/api/v1/testplan.py` 中完成以下处理：

1. 校验文件扩展名是否为 `.pdf`。
2. 读取文件内容并检查大小，当前限制为 50MB。
3. 使用 UUID 前 8 位生成 `file_id`。
4. 将文件保存到 `settings.UPLOAD_DIR`。
5. 返回 `file_id`、原始文件名、文件大小和上传时间。

前端拿到 `file_id` 后，继续调用异步提取接口：

```text
POST /api/v1/testplan/extract-async?file_id={file_id}
```

后端创建 `task_id`，将任务状态写入内存字典 `task_status`，再通过 FastAPI `BackgroundTasks` 在后台执行提取任务。前端通过轮询：

```text
GET /api/v1/testplan/status/{task_id}
```

获取任务进度、状态、统计信息、下载地址和引脚结果。

### 2.2 结果下载

提取完成后，后端会生成 Excel 和 JSON 文件。前端下载时调用：

```text
GET /api/v1/testplan/download/{file_id}/excel
GET /api/v1/testplan/download/{file_id}/json
```

下载接口会在处理目录中查找对应 `file_id` 的结果文件，并通过 `FileResponse` 返回。

## 3. Datasheet 解析与页面过滤实现

### 3.1 PDF 解析

核心实现位于：

```text
backend/app/services/testplan_service.py
```

提取入口为 `TestPlanService.extract_from_pdf()`。该方法会调用 PDF 解析器读取每一页文本和表格内容，并将页面转换为统一的 chunk 结构：

```text
{
  "page": 页码,
  "content": 页面文本和表格内容
}
```

解析完成后，系统不会直接把全部页面提交给大模型，而是先进行页面过滤和分块。

### 3.2 页面过滤策略

页面过滤实现位于 `TestPlanService._filter_and_batch_chunks()`。系统会对每一页计算分数，并根据关键词和内容特征判断是否保留。

优先保留的页面包括：

- Electrical Characteristics。
- Absolute Maximum Ratings。
- Recommended Operating Conditions。
- Pin Description。
- Pin Configuration。
- Timing Characteristics。
- Function Table / Truth Table。

优先过滤的页面包括：

- 封面。
- 目录。
- 修订历史。
- 订购信息。
- 免责声明。
- 空白页。
- 与封装尺寸强相关但缺少电气参数的页面。

这样做的目的有三个：

1. 减少无效上下文，降低大模型输入长度。
2. 降低 DeepSeek API 调用耗时和成本。
3. 减少目录、封装尺寸、订购信息等页面对参数提取结果的干扰。

### 3.3 内容压缩和批处理

过滤后，系统会对页面内容做紧凑化处理，减少重复表格字符和无效空白。对于保留下来的页面，系统会按批次组合为 LLM 请求 chunk。当前策略会尽量避免把过重的电气参数页与其他页面合并，从而让并发提取能更快完成。

## 4. 提取加速与缓存实现

### 4.1 缓存键设计

系统在 `testplan_service.py` 中定义了缓存版本：

```text
CACHE_VERSION = "testplan-v3-local-ratings-fastpath"
```

缓存键由以下内容共同生成：

- 缓存版本号。
- PDF 文件内容。
- 用户指定的页码范围。

这样可以保证同一份 PDF、同一页码范围、同一套提取逻辑命中缓存；当提取逻辑升级时，只需要修改 `CACHE_VERSION` 就可以避免旧缓存污染新结果。

### 4.2 缓存读写流程

缓存文件保存在：

```text
settings.PROCESSED_DIR / "testplan_cache"
```

每个缓存对应两类文件：

- `{cache_key}_TestPlan.xlsx`
- `{cache_key}_TestPlan.json`

处理流程如下：

1. 提取开始前计算 `cache_key`。
2. 检查缓存目录是否存在对应 Excel 和 JSON。
3. 如果命中缓存，直接复制缓存文件到当前任务结果文件，跳过 PDF 解析和 LLM 调用。
4. 如果未命中缓存，正常执行提取流程。
5. 提取成功后，将本次生成的 Excel 和 JSON 写入缓存目录。

缓存机制主要用于重复测试、演示和同一文件多次提取场景，可显著降低二次处理时间。

## 5. 大模型结构化提取实现

### 5.1 LLM 调用入口

大模型提取逻辑位于：

```text
backend/app/services/llm_extractor.py
```

主要方法包括：

- `detect_chip_type()`：根据前几页内容判断芯片类型。
- `extract_from_chunk()`：对单个 chunk 调用大模型提取。
- `extract_parallel()`：使用线程池并发处理多个 chunk。

系统使用 DeepSeek API 完成结构化抽取。Prompt 中会要求模型输出 JSON，并包含参数、引脚和测试条件等字段。

### 5.2 JSON 结果清洗

由于大模型可能返回 Markdown 代码块、解释性文字或格式不稳定的 JSON，系统实现了 `_extract_json_text()`，用于从模型响应中尽量提取有效 JSON 文本。

提取后会继续做：

- JSON 解析。
- 字段标准化。
- 数值类型转换。
- 单位归一化。
- 参数去重。
- 引脚去重。
- page 来源补充。

如果某个 chunk 提取失败，系统会记录错误日志，但不会让整个任务直接中断，而是继续处理其他 chunk。

### 5.3 并发提取

`extract_parallel()` 使用 `ThreadPoolExecutor` 并发处理多个页面 chunk。前端或接口可以通过 `max_workers` 控制并发数，接口限制为 1 到 10。

并发提取的作用是：

1. 多个页面可同时等待 DeepSeek API 响应。
2. 避免某个复杂页面拖慢全部任务。
3. 让较短的 pin table、ratings 页面先完成，提高整体响应速度。

## 6. 本地规则兜底实现

大模型提取之前和之后，系统会执行本地规则补充。相关逻辑主要在 `testplan_service.py` 中，包括：

- `_extract_local_params_from_chunks()`：从页面文本中提取常见电气参数。
- `_extract_pin_definitions_from_chunks()`：从文本型 pin table 中提取引脚定义。
- `_drop_local_pin_chunks()`：如果本地已经稳定提取出引脚表，则减少对应页面的 LLM 请求。

本地规则主要覆盖：

- Absolute Maximum Ratings。
- Recommended Operating Conditions。
- 常见电压、电流、温度参数。
- 文本型 pin table。
- 部分常见芯片 pinout。

这样设计的原因是：部分 Datasheet 的常见参数格式比较固定，用规则提取比全部交给大模型更快、更稳定，也能减少接口调用次数。

## 7. STS8200S 平台规则校验实现

平台规则校验用于把模型抽取结果转换为更接近 ATE 工程实践的结果。系统会对提取到的参数进行：

- 电压范围检查。
- 电流范围检查。
- DIO 资源需求提示。
- CBIT、TMU、VI 等资源适配提示。
- 小电流或静态电流的量程建议。
- 缺失单位、缺失测试条件和异常值 warning。

校验结果会写入 `ExtractionResult`，并返回给前端。前端提取完成页会展示总参数数、A/B/C 类参数数量、DC/AC/LDO 测试项数量、引脚数量、warnings 和 range recommendations。

## 8. TestPlan 文件生成实现

提取完成后，系统会生成两类 TestPlan 文件：

| 文件类型 | 作用 |
|---|---|
| JSON | 供系统内部模块继续读取，例如资源映射和代码生成 |
| Excel | 供测试工程师人工复核、修改和提交 |

JSON 中保存芯片名称、芯片类型、参数列表、引脚定义、统计信息、校验结果和风险提示。Excel 文件用于更直观地展示参数分类、测试项和平台建议。

## 9. 资源映射与辅助设计实现

资源映射逻辑位于：

```text
backend/app/services/resource_mapping_service.py
```

该模块以 `ExtractionResult` 为输入，读取芯片类型、参数列表和引脚定义，然后执行：

1. 引脚分类：输入、输出、电源、地、NC、双向 IO。
2. 测试资源推断：根据芯片类型和测试项判断需要 DIO、VI、TMU、CBIT 等资源。
3. 资源分配：生成 STS8200S 资源映射表。
4. PGS 生成：根据芯片类型生成不同 PGS 配置，例如 general、LDO、EEPROM。
5. BOM 生成：输出辅助设计所需的器件和连接建议。
6. SVG 生成：生成可视化辅助示意图。

输出文件包括资源映射 Excel、PGS 配置、BOM 清单和 SVG 辅助示意图。

## 10. 测试代码生成实现

当前正式代码生成模块为：

```text
backend/app/api/v1/codegen.py
backend/app/services/codegen_service.py
backend/app/services/code_validator.py
```

正式接口包括：

```text
POST /api/v1/codegen/generate
GET  /api/v1/codegen/templates
```

前端调用位置为：

```text
apps/src/api/backend.ts
```

代码生成请求中包含：

- `chip_name`
- `chip_type`
- `test_items`
- `user_prompt`
- `pin_names`
- `input_pins`
- `output_pins`
- `vcc`
- `vout`
- `ldo_out_pin`
- `load_ma`

生成策略为：

1. 根据芯片类型和测试项选择模板。
2. 先生成稳定的 C++ 骨架代码。
3. 如 RAG 可用，则检索 STS8200S 知识片段进行增强。
4. 如用户输入了自然语言要求，则调用模型补充注释或细节。
5. 使用 `CodeValidator` 进行静态规则检查。
6. 返回代码文本、行数、函数数和静态分析结果。

当前代码生成定位为“工程初稿”，用于降低重复性编码工作，最终上机前仍需要测试工程师复核。

## 11. RAG 知识增强实现

RAG 服务位于：

```text
backend/app/services/rag_service.py
```

主应用启动时会尝试初始化 STS8200S 内置知识库。如果索引未就绪，则调用 `build_index_from_text()` 构建知识片段；如果已经就绪，则直接加载已有索引。

RAG 的作用主要体现在代码生成阶段：

1. 根据测试项和用户需求检索相关 STS8200S 知识。
2. 将检索结果加入生成 Prompt。
3. 降低模型生成与平台 API 或测试流程不一致的风险。

如果 RAG 初始化失败，系统会记录 warning，并降级为模板生成，不影响其他功能使用。

## 12. 良率诊断实现

诊断模块位于：

```text
backend/app/api/v1/diagnosis.py
backend/app/services/yield_diagnosis.py
```

当前中期版本使用仿真 VI 波形和异常检测逻辑，输出良率、FTY、Bin 分布、VI 波形、异常事件、故障类型和可能原因。前端故障诊断页面读取后端诊断结果后进行可视化展示。

## 13. 桌面端打包与后端启动实现

桌面端主进程位于：

```text
apps/electron/main.cjs
```

核心实现包括：

1. 检测是否为打包环境。
2. 打包环境下定位 `process.resourcesPath/backend-server/backend-server.exe`。
3. 开发环境下优先使用项目 `.venv` 中的 Python，找不到时回退到系统 Python。
4. 在 `18080-18179` 范围内自动寻找可用端口。
5. 启动后端后轮询 `/health` 接口。
6. 后端就绪后把 API 地址传递给前端。
7. 写入 `backend-launch.log`，记录启动命令、端口、stdout/stderr 尾部信息和失败原因。
8. 使用 `backend.pid` 清理上次残留的后端进程。

该方案解决了“另一台电脑不安装 Python 无法运行后端”的问题，也方便定位安装包在用户电脑上的启动异常。

## 14. 前端 API 与状态管理实现

前端 API 封装位于：

```text
apps/src/api/backend.ts
```

该文件统一封装健康检查、上传、异步提取、状态轮询、下载、资源映射、代码生成和 RAG 状态接口。

前端提取状态管理位于：

```text
apps/src/store/extractionStore.ts
```

用于在提取器、资源映射、代码生成等页面之间共享当前文件、提取结果和任务状态。

## 15. 错误处理与可诊断性设计

系统在多个层面增加了错误处理：

- 上传阶段校验文件类型、大小和空文件。
- 提取阶段捕获 PDF 解析、LLM 调用和文件导出异常。
- 异步任务阶段返回 `pending / processing / completed / failed` 状态。
- 前端上传前先检查 `/health`，避免后端未连接时长时间卡住。
- Electron 记录 `backend-launch.log`，方便排查其他电脑上的后端启动问题。
- 后端统一响应结构，前端可以统一解析成功和失败结果。

## 16. 当前实现边界

当前系统已经完成核心演示闭环，但仍有以下边界：

1. 图像型 pinout 和扫描 PDF 识别仍不如文本型 PDF 稳定。
2. 资源映射主要覆盖基础芯片和典型测试项，复杂 DUT 板卡规则需要继续扩展。
3. 代码生成结果是工程初稿，尚未接入真实 STS8200S SDK 编译链路。
4. 良率诊断当前使用仿真数据，尚未接入真实工控机数据。
5. 客户级使用仍需要云端后端、账号权限、任务队列、日志审计和 API Key 安全管理。

## 17. 技术实现小结

本项目的核心实现特点是将 LLM 文档理解能力和 ATE 工程规则结合起来。LLM 负责处理 Datasheet 中格式复杂、语义多变的内容，本地规则负责补充稳定参数、过滤异常结果，STS8200S 规则负责保证输出具有工程可用性。通过 FastAPI 模块化路由、React 前端状态管理和 Electron 桌面端打包，系统形成了从算法能力到工程交付的完整实现链路。
