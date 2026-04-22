# 集创赛提交资料整理说明

本目录用于整理本项目参加集创赛需要提交的资料。内容基于当前 ATE-AI-Platform 的实现进度编写，并预留了后续补充测试数据、截图、视频链接和最终 PDF 报告的位置。

## 目录结构

```text
competition_submission_materials/
├── README.md
├── submission_checklist.md                 # 提交材料总清单
├── software/
│   ├── install_and_user_manual.md          # 软件安装及使用说明书
│   └── source_code_notes.md                # 源代码与注释说明
├── technical_docs/
│   ├── implementation_plan_report.md       # 课题实施方案报告
│   ├── midterm_progress_report.md          # 中期进展报告
│   ├── final_technical_report_outline.md   # 结题技术报告大纲
│   └── function_progress.md                # 已实现功能与完成进度
├── validation/
│   ├── test_data_report_template.md        # 测试数据报告模板
│   └── engineering_video_script.md         # 工程验证视频脚本
├── presentation/
│   └── final_ppt_outline.md                # 结题答辩 PPT 大纲
├── summary/
│   └── team_summary_report.md              # 团队总结报告模板
└── diagrams/
    ├── system_architecture.md              # 系统架构图 Mermaid 版本
    └── key_algorithm_flow.md               # 关键算法流程图 Mermaid 版本
```

## 当前项目定位

ATE-AI-Platform 是面向 ATE 测试开发流程的 AI 辅助平台，围绕芯片 Datasheet 到测试开发交付物的链路，提供数据手册解析、测试参数提取、引脚定义识别、STS8200S 资源映射、测试代码生成和良率诊断展示等能力。

当前版本已完成核心演示闭环，能够通过桌面端安装包在 Windows 环境运行，用户无需额外安装 Python。后续若面向客户使用，建议演进为“客户端 + 云端后端”的产品形态。

## 后续使用方式

1. 将本文档中的“待补充”内容替换为真实测试结果、截图、团队信息和视频链接。
2. 将 Markdown 文档整理成 Word 或 PDF 格式。
3. 将 `diagrams/` 中的 Mermaid 图导出为 PNG/SVG 后放入报告和 PPT。
4. 提交前检查 `submission_checklist.md`，确认每项材料是否齐全。
