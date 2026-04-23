# 源代码与关键注释说明

## 1. 源代码结构

```text
ate-ai-platform/
├─ apps/                         # React + Electron 前端
│  ├─ electron/main.cjs           # Electron 主进程，负责启动内置后端
│  ├─ src/
│  │  ├─ api/backend.ts           # 前端 API 客户端
│  │  ├─ components/              # 仪表盘、提取器、资源映射、代码生成、故障诊断页面
│  │  └─ store/extractionStore.ts # 提取任务状态管理
│  └─ package.json                # 前端依赖、桌面端构建和安装包配置
├─ backend/
│  ├─ backend_server.py           # PyInstaller 后端入口
│  ├─ backend-server.spec         # 后端 exe 打包配置
│  └─ app/
│     ├─ main.py                  # FastAPI 主应用和路由挂载
│     ├─ api/v1/                  # FastAPI 接口层
│     ├─ core/                    # 配置、统一响应模型
│     ├─ models/                  # Pydantic 数据模型
│     ├─ services/                # 核心业务逻辑
│     └─ utils/                   # PDF、Excel、SVG、日志工具
├─ competition_submission_materials/ # 比赛提交材料
└─ requirements.txt               # Python 依赖
```

## 2. 主应用路由说明

当前 FastAPI 主应用在 `backend/app/main.py` 中挂载以下正式路由：

| 路由前缀 | 文件 | 作用 |
|---|---|---|
| `/api/v1/testplan` | `backend/app/api/v1/testplan.py` | PDF 上传、TestPlan 提取、任务状态、文件下载 |
| `/api/v1/resource-map` | `backend/app/api/v1/resource_map.py` | DUT 资源映射、PGS、BOM、SVG 输出 |
| `/api/v1/codegen` | `backend/app/api/v1/codegen.py` | STS8200S C++ 测试代码生成 |
| `/api/v1/rag` | `backend/app/api/v1/rag.py` | STS8200S 知识库状态和检索 |
| `/api/v1/diagnosis` | `backend/app/api/v1/diagnosis.py` | 良率诊断和 VI 波形分析 |

说明：`backend/app/api/v1/testprogram.py` 目前存在于目录中，但未挂载到主应用，不属于当前正式接口。当前 App 实际使用的是 `/api/v1/codegen/*`。

## 3. 核心代码模块说明

| 文件 | 作用 | 具体实现说明 |
|---|---|---|
| `backend/app/services/testplan_service.py` | TestPlan 提取主流程 | 负责 PDF 解析、页面过滤、缓存、LLM 调用、本地规则兜底、STS8200S 校验和 Excel/JSON 导出 |
| `backend/app/services/llm_extractor.py` | 大模型结构化提取 | 调用 DeepSeek API，约束 JSON 输出，解析参数、单位、测试条件和引脚定义，并支持并发提取 |
| `backend/app/services/resource_mapping_service.py` | 资源映射 | 根据 TestPlan 和引脚定义生成 STS8200S 资源映射、PGS、BOM 和 SVG |
| `backend/app/services/codegen_service.py` | 测试代码生成 | 根据芯片类型、测试项、引脚和用户需求生成 STS8200S C++ 代码骨架 |
| `backend/app/services/code_validator.py` | 代码静态校验 | 检查生成代码结构、测试函数、通道配置和常见风险点 |
| `backend/app/services/rag_service.py` | RAG 知识增强 | 构建 STS8200S 知识片段索引，为代码生成提供检索增强 |
| `backend/app/services/yield_diagnosis.py` | 良率诊断 | 使用仿真 VI 波形和异常检测逻辑输出良率、FTY 和故障类型 |
| `apps/src/api/backend.ts` | 前端 API 封装 | 封装健康检查、上传、异步提取、状态轮询、下载、资源映射和代码生成接口 |
| `apps/src/store/extractionStore.ts` | 前端状态管理 | 保存当前文件、提取结果、任务进度和跨页面共享状态 |
| `apps/electron/main.cjs` | 桌面端主进程 | 自动选择端口、启动后端 exe、检查 `/health`、注入 API 地址并写入启动日志 |

## 4. Datasheet 提取实现细节

### 4.1 上传阶段

上传接口为：

```text
POST /api/v1/testplan/upload
```

实现逻辑：

1. 检查文件扩展名是否为 `.pdf`。
2. 限制文件大小，避免超大文件阻塞后端。
3. 生成 8 位 `file_id`。
4. 将文件保存到上传目录。
5. 返回 `file_id`、文件名、大小和上传时间。

### 4.2 异步提取阶段

异步提取接口为：

```text
POST /api/v1/testplan/extract-async?file_id={file_id}
GET  /api/v1/testplan/status/{task_id}
```

后端通过 `BackgroundTasks` 启动后台任务，并使用内存字典 `task_status` 保存任务状态。任务状态包括：

- `pending`
- `processing`
- `completed`
- `failed`

前端根据 `task_id` 定时轮询状态接口，并在完成后展示统计结果和下载链接。

### 4.3 页面过滤与加速

页面过滤在 `TestPlanService._filter_and_batch_chunks()` 中实现。系统会根据关键词和页面特征打分，优先保留电气特性、引脚描述、推荐工作条件、绝对最大额定值、时序表和功能表页面，过滤封面、目录、修订历史、订购信息和空白页。

系统还实现了缓存机制。缓存键由缓存版本、PDF 内容和页码范围共同生成。命中缓存时，系统直接复制历史 Excel/JSON 结果，跳过大模型调用。

## 5. LLM 提取实现细节

大模型提取在 `LLMExtractor` 中实现。核心流程为：

1. 根据前几页内容识别芯片类型。
2. 将页面 chunk 交给 DeepSeek API。
3. Prompt 要求模型输出 JSON。
4. 对模型返回内容提取 JSON 文本。
5. 解析参数、引脚和测试条件。
6. 对字段进行标准化和去重。
7. 多个 chunk 使用线程池并发执行。

模型输出字段主要包括：

- 参数名称。
- 参数符号。
- 最小值、典型值、最大值。
- 单位。
- 测试条件。
- 参数类别。
- 引脚编号。
- 引脚名称。
- 引脚方向。
- 引脚功能。

## 6. 本地规则兜底实现细节

为了降低大模型输出不稳定的影响，系统加入本地规则：

- 对 Absolute Maximum Ratings 提取常见极限参数。
- 对 Recommended Operating Conditions 提取工作条件。
- 对文本型 pin table 提取引脚编号、名称和方向。
- 对重复参数进行合并。
- 对缺失测试条件生成 warning。
- 如果本地已稳定提取引脚表，则减少对应页面 LLM 请求。

这种设计让系统形成“LLM 主提取 + 规则补充 + 平台校验”的混合方案。

## 7. STS8200S 校验实现细节

平台规则校验主要检查：

- 电压是否超出平台建议范围。
- 电流是否需要特殊量程。
- DIO 通道是否满足测试需求。
- CBIT、TMU、VI 等资源是否需要人工确认。
- 参数是否缺少单位或测试条件。
- 是否存在明显异常值。

校验结果会写入 TestPlan，并返回给前端用于展示 warning 和量程建议。

## 8. 资源映射实现细节

资源映射模块读取模块一生成的 TestPlan JSON 和引脚定义，执行：

1. 按引脚名称和功能推断引脚类型。
2. 将输入、输出、电源、地、NC 等引脚分组。
3. 根据测试项需求分配 STS8200S 资源。
4. 生成资源映射 Excel。
5. 生成 PGS 配置。
6. 生成 BOM 清单。
7. 生成 SVG 辅助示意图。

该模块当前主要提供 DUT 原理图辅助设计建议，复杂板卡约束仍需要后续扩展。

## 9. 测试代码生成实现细节

当前正式代码生成接口为：

```text
POST /api/v1/codegen/generate
GET  /api/v1/codegen/templates
```

实现流程：

1. 校验测试项是否属于支持列表。
2. 根据芯片类型选择数字芯片或 LDO 模板。
3. 根据引脚和测试项生成 C++ 骨架。
4. 如 RAG 可用，则检索 STS8200S 知识增强生成结果。
5. 如用户提供自然语言要求，则对模板代码进行补充。
6. 使用 `CodeValidator` 做静态检查。
7. 返回代码、行数、函数数和静态分析结果。

当前支持的典型测试项包括：

- 数字芯片：CON、FUN、VIH、VIL、VOH、VOL、IOS、ICC 等。
- LDO：LDO_DROPOUT、LDO_ACCURACY、LDO_IQ。

## 10. 桌面端打包实现细节

桌面端使用 Electron，后端使用 PyInstaller 打包为 `backend-server.exe`。启动流程如下：

1. Electron 主进程启动。
2. 清理上次残留的后端 pid。
3. 在 `18080-18179` 范围内寻找可用端口。
4. 打包环境下启动 `backend-server.exe`。
5. 开发环境下优先使用 `.venv/Scripts/python.exe` 启动后端。
6. 轮询 `http://127.0.0.1:{port}/health`。
7. 后端健康后，将 API 地址传给前端。
8. 启动日志写入 `backend-launch.log`。

该实现使用户在其他电脑上安装后不需要手动配置 Python 环境。

## 11. 建议重点注释位置

后续提交源代码时建议重点检查以下位置的注释：

1. PDF 页面过滤逻辑：说明如何判断有效页和无效页。
2. LLM Prompt：说明 JSON 输出约束和参数分类规则。
3. 本地规则兜底：说明为什么对常见参数和引脚做规则补充。
4. 缓存机制：说明缓存键由 PDF 内容、页码范围和版本号组成。
5. STS8200S 校验规则：说明电压、电流、DIO、CBIT 等约束来源。
6. 资源映射规则：说明引脚方向、资源类型和测试项之间的映射关系。
7. 代码静态校验：说明如何降低首检错误。
8. Electron 后端启动逻辑：说明端口选择、健康检查和日志诊断。
