# ATE-AI-Platform

面向 ATE 测试开发的 AI 辅助平台。项目围绕芯片 Datasheet 到测试开发交付物的流程，提供 PDF 参数抽取、TestPlan 导出、STS8200S 资源映射、RAG 增强测试代码生成和良率诊断等能力。

本项目适合作为半导体测试软件、工业 AI 应用、后端/全栈实习方向的作品集项目。

## 项目亮点

- 从 Datasheet PDF 中自动抽取电气参数、绝对最大额定值、推荐工作条件和引脚定义。
- 将抽取结果标准化导出为 Excel/JSON，方便 ATE 测试工程师复核和二次编辑。
- 根据芯片类型和引脚信息生成 STS8200S 资源映射、PGS 配置、BOM 和辅助原理图。
- 结合模板规则、内置 STS8200S 知识库和 RAG 检索生成 C++ 测试程序骨架。
- 提供良率诊断演示模块，使用异常检测模型分析仿真 VI 波形并输出故障类型。
- 支持 Web 前端和 Electron 桌面端，前后端通过 FastAPI 接口解耦。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.10+, FastAPI, Pydantic, Uvicorn |
| AI/LLM | DeepSeek API, OpenAI-compatible SDK, instructor |
| 文档处理 | PyMuPDF, pdfplumber |
| 数据处理 | pandas, numpy, openpyxl |
| RAG | ChromaDB 可选，内置 TF-IDF 降级检索 |
| 诊断算法 | IsolationForest, StandardScaler，可降级为规则检测 |
| 前端 | React 19, TypeScript, Vite, Tailwind CSS, lucide-react |
| 桌面端 | Electron, electron-builder/electron-packager |

## 功能模块

### 1. TestPlan 自动提取

输入芯片 Datasheet PDF，系统完成文本解析、LLM 参数抽取、规则校验、参数分类和文件导出。

主要能力：

- PDF 上传与解析
- 同步/异步抽取任务
- 芯片类型识别
- A/B/C 类参数分类
- DC/AC/LDO 测试项识别
- STS8200S 兼容性提示
- Excel 和 JSON 导出

### 2. 资源映射与辅助设计

基于模块一的抽取结果和 PinMapping 信息，自动生成面向 STS8200S 的资源分配。

主要能力：

- 数字芯片、LDO、EEPROM 等场景的适配器选择
- DIO/FH/SH/CBIT/TMU 资源分配
- PGS 配置生成
- 引脚分组生成
- BOM 和资源映射 Excel 导出
- SVG 辅助原理图生成

### 3. TestProgram 智能生成

面向 STS8200S 平台生成 C++ 测试程序骨架，并通过 RAG 注入机台编程知识。

主要能力：

- CON/FUN/VIH/VIL/VOH/VOL/ICC 等测试模板
- LDO Dropout、Accuracy、Iq 等测试模板
- 内置 STS8200S API 参考
- RAG 检索增强生成
- AI 注释润色和风险提示
- 静态代码校验

### 4. 良率诊断演示

使用仿真 VI 波形构建边缘 AI 诊断演示，用于展示量产测试中的异常检测思路。

主要能力：

- VI 波形仿真
- IsolationForest 异常检测
- 继电器退化、热漂移、接触噪声等故障类型识别
- 良率、FTY 和趋势预测
- 前端实时图表展示

## 项目结构

```text
ate-ai-platform/
├── apps/                         # React + Vite + Electron 前端
│   ├── electron/                 # Electron 主进程
│   ├── src/
│   │   ├── api/                  # 后端 API 客户端
│   │   ├── components/           # 页面组件
│   │   ├── store/                # 前端状态
│   │   └── types.ts              # 前端类型定义
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/v1/               # FastAPI 路由
│   │   ├── core/                 # 配置与统一响应
│   │   ├── models/               # Pydantic 数据模型
│   │   ├── services/             # 核心业务逻辑
│   │   └── utils/                # PDF/Excel/SVG/日志工具
│   ├── tests/                    # 接口流程测试
│   ├── cli.py                    # TestPlan 命令行提取工具
│   └── check_env.py              # 环境检查脚本
├── config/                       # 配置文件
├── data/
│   ├── raw/                      # 示例 Datasheet
│   ├── uploads/                  # 上传文件
│   └── processed/                # 生成结果
├── docs/                         # 项目文档
├── logs/                         # 运行日志
└── requirements.txt              # Python 依赖
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 20+ 推荐
- DeepSeek API Key

### 1. 安装后端依赖

```powershell
git clone <your-repo-url>
cd ate-ai-platform

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2. 配置后端环境变量

在 `backend/.env` 中配置：

```env
DEEPSEEK_API_KEY=sk-your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DEBUG=true
```

检查环境：

```powershell
cd backend
python check_env.py
```

### 3. 启动后端服务

```powershell
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问：

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 4. 启动前端

```powershell
cd apps
npm install
npm run dev
```

前端默认运行在：

```text
http://localhost:3000
```

Vite 开发服务器已配置 `/api`、`/files` 和 `/health` 代理到 `http://localhost:8000`。

## 桌面端运行

开发模式：

```powershell
cd apps
npm run desktop:dev
```

打包 Windows 桌面应用：

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

更多说明见 `docs/desktop-app-deploy.md`。

## 命令行使用

不启动 Web 服务时，也可以直接使用 CLI 对 PDF 进行 TestPlan 抽取。

```powershell
cd backend

# 提取整个 PDF
python cli.py --pdf ../data/raw/ADI-AD780.pdf

# 指定页码范围
python cli.py --pdf ../data/raw/ADI-AD780.pdf --pages 3-9

# 设置并发数
python cli.py --pdf ../data/raw/Renesas-HD74LS00P.pdf --workers 3
```

生成文件默认输出到 `data/processed/`。

## 常用 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| POST | `/api/v1/testplan/upload` | 上传 Datasheet PDF |
| POST | `/api/v1/testplan/extract` | 同步抽取 TestPlan |
| POST | `/api/v1/testplan/extract-async` | 提交异步抽取任务 |
| GET | `/api/v1/testplan/status/{task_id}` | 查询异步任务状态 |
| GET | `/api/v1/testplan/download/{file_id}/{file_type}` | 下载 Excel/JSON |
| GET | `/api/v1/testplan/pins/{file_id}` | 查看引脚定义 |
| POST | `/api/v1/resource-map/generate` | 生成资源映射 |
| POST | `/api/v1/codegen/generate` | 生成 STS8200S 测试代码 |
| GET | `/api/v1/rag/status` | 查看 RAG 索引状态 |
| POST | `/api/v1/diagnosis/run` | 运行良率诊断 |

## 典型工作流

1. 上传芯片 Datasheet PDF。
2. 选择页码范围并提交 TestPlan 抽取任务。
3. 系统输出参数分类、引脚定义、STS8200S 兼容性提示。
4. 下载 TestPlan Excel/JSON。
5. 基于引脚定义生成资源映射、PGS 配置、BOM 和辅助原理图。
6. 选择芯片类型、测试项和引脚分组，生成 STS8200S C++ 测试程序。
7. 在良率诊断页面运行仿真诊断，查看异常事件和趋势预测。

完整演示流程见 `docs/demo-workflow.md`。

## 验证命令

```powershell
# 后端单元测试
python -m pytest backend/tests -q

# 后端语法检查
python -m compileall -q backend/app

# 前端生产构建
cd apps
npm run build
```


## 注意事项

- LLM 抽取和 RAG 增强生成依赖 DeepSeek API Key；未配置时相关 AI 能力不可用。
- 自动生成的测试代码和资源映射应由 ATE 工程师复核后再上机使用。
- `data/uploads/`、`data/processed/` 和 `logs/` 属于运行产物目录，不建议提交生成文件。
- 当前 RAG 支持 ChromaDB 向量库；未安装 ChromaDB 时会自动降级为 TF-IDF 检索。
