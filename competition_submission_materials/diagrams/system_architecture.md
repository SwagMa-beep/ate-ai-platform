# 系统架构设计图

可将下方 Mermaid 图导出为 PNG/SVG 后放入技术报告和 PPT。

```mermaid
flowchart TB
    User[用户/测试工程师] --> Desktop[Electron 桌面端]
    Desktop --> React[React + TypeScript 前端]
    React --> API[FastAPI 后端服务]

    subgraph Frontend[前端交互层]
        React --> Dashboard[仪表盘]
        React --> Extractor[Datasheet 提取器]
        React --> ResourceUI[资源映射页面]
        React --> CodeLab[代码实验室]
        React --> DiagnosisUI[良率诊断页面]
    end

    subgraph Backend[后端服务层]
        API --> Upload[PDF 上传与任务管理]
        API --> Parser[PDF 解析与页面过滤]
        API --> LLM[LLM 结构化提取]
        API --> Validator[STS8200S 规则校验]
        API --> ResourceMap[资源映射与辅助设计]
        API --> CodeGen[测试代码生成]
        API --> Diagnosis[良率诊断服务]
    end

    subgraph AI[AI 与知识层]
        LLM --> DeepSeek[DeepSeek API]
        CodeGen --> RAG[RAG/STS8200S 知识库]
        Diagnosis --> ML[异常检测模型]
    end

    subgraph Output[工程交付物]
        Validator --> TestPlan[TestPlan Excel/JSON]
        ResourceMap --> ResourceFiles[资源映射表/PGS/BOM/SVG]
        CodeGen --> CPP[C++ 测试程序骨架]
        Diagnosis --> Report[诊断结果/波形数据]
    end

    subgraph Packaging[部署层]
        Desktop --> BackendExe[PyInstaller backend-server.exe]
        BackendExe --> API
    end
```

## 图示说明

- 前端负责用户交互、状态展示和文件下载。
- 后端负责 PDF 处理、模型调用、规则校验和文件生成。
- AI 层包含 DeepSeek 大模型、STS8200S 知识库和异常检测模型。
- 输出层对应比赛要求中的 TestPlan、资源映射、测试代码和诊断结果。
- 桌面端通过 Electron + PyInstaller 实现 Windows 安装运行。
