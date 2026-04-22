# 源代码与关键注释说明

## 1. 源代码结构

```text
ate-ai-platform/
├── apps/                         # React + Electron 前端
│   ├── electron/main.cjs          # Electron 主进程，负责启动内置后端
│   └── src/
│       ├── api/backend.ts         # 前端 API 客户端
│       ├── components/            # 仪表盘、提取器、资源映射、代码生成、故障诊断页面
│       └── store/extractionStore.ts # 提取任务状态管理
├── backend/
│   ├── backend_server.py          # PyInstaller 后端入口
│   ├── backend-server.spec        # 后端 exe 打包配置
│   └── app/
│       ├── api/v1/                # FastAPI 接口
│       ├── core/                  # 配置、响应模型
│       ├── models/                # Pydantic 数据模型
│       ├── services/              # 核心业务逻辑
│       └── utils/                 # PDF、Excel、SVG、日志工具
└── requirements.txt               # Python 依赖
```

## 2. 核心代码模块说明

| 文件 | 作用 | 说明 |
|---|---|---|
| `backend/app/services/testplan_service.py` | TestPlan 提取主流程 | 包含 PDF 解析、页面过滤、LLM 提取、本地规则补充、缓存和导出 |
| `backend/app/services/llm_extractor.py` | 大模型结构化提取 | 调用 DeepSeek API，将文本转换为结构化参数和引脚定义 |
| `backend/app/services/resource_mapping_service.py` | 资源映射 | 将引脚和测试项映射到 STS8200S 资源 |
| `backend/app/services/testprogram_service.py` | 测试代码生成 | 生成 STS8200S C++ 测试程序骨架 |
| `backend/app/services/code_validator.py` | 代码静态校验 | 检查生成代码中的 API、通道号和测试结果设置 |
| `backend/app/services/yield_diagnosis.py` | 良率诊断 | 使用仿真波形和异常检测模型进行故障识别 |
| `apps/src/store/extractionStore.ts` | 前端提取状态管理 | 管理上传、异步任务、轮询、错误和结果缓存 |
| `apps/electron/main.cjs` | 桌面端主进程 | 启动后端 exe、自动分配端口、写入启动日志 |

## 3. 关键注释建议

后续提交源码时建议重点检查以下位置是否有注释：

1. PDF 页面过滤逻辑：说明如何跳过封面、目录、修订记录和空白页。
2. LLM 提取提示词：说明输出 JSON 结构约束和参数分类规则。
3. 本地规则兜底：说明为什么对常见参数和部分图像引脚做规则补充。
4. STS8200S 校验规则：说明电压、电流、DIO、CBIT 等硬件约束来源。
5. 资源映射规则：说明引脚方向、资源类型和测试项之间的映射关系。
6. 代码静态校验：说明首检错误率降低的实现依据。
7. 桌面端后端启动逻辑：说明为什么要内置 PyInstaller 后端和写入诊断日志。

## 4. 代码提交说明

当前 GitHub 仓库已包含完整源码和主要工程配置。安装包由于可能包含本地 API Key，不建议直接提交到公开仓库。正式提交比赛材料时建议：

1. 提交源码压缩包或 GitHub 仓库链接。
2. 单独提交安装包。
3. 若安装包包含 API Key，仅用于评审演示，不公开发布。
4. 客户级版本应改为用户自行配置 API Key 或连接云端后端。
