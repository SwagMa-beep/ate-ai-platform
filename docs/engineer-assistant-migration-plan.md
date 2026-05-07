# 工程师助手迁移到主框架方案

## 1. 目标

将 `fa/` 中同伴开发的“测试 AI 聊天助手”能力，按 **方案 A：统一工程师助手模块** 融合到现有 ATE AI Platform 主框架中，而不是继续维护第二套平行后端。

迁移后的目标形态是：

- 前端新增一个统一入口：`工程师助手`
- 助手内部支持多种能力模式：
  - `TestPlan 咨询`
  - `资源映射建议`
  - `代码生成辅助`
  - `故障诊断问答`
  - `当前 Run 分析`
- 助手直接读取主平台上下文，而不是维护独立数据流
- 后端继续以当前 `backend/` 为唯一正式服务端

## 2. 为什么选择方案 A

相比“多个独立 AI 助手页面”或“单独维护 fa 子系统”，方案 A 更适合当前项目状态：

- 当前主平台已经形成：
  - `ATE Agent 工作台`
  - `Agent 运行中心`
  - `Datasheet / TestPlan`
  - `资源映射`
  - `代码生成`
  - `良率诊断`
- 如果继续保留 `fa` 作为第二套后端，会造成：
  - 两套配置
  - 两套 RAG
  - 两套 PDF 解析
  - 两套 API
  - 两套知识库路径
  - 两套运行状态
- 统一成一个“工程师助手”入口后，产品形态更完整，协作成本更低，也更适合答辩和最终作品展示

一句话总结：

**助手应该是主平台里的工程副驾，而不是主平台旁边再搭一个小平台。**

## 3. 当前现状判断

### 3.1 主平台现状

当前主仓库已经具备完整主链：

- `full_ate_development`
- `post_review_delivery`
- `post_review_revision`
- `AgentController`
- `RunStore`
- `Agent 工作台`
- `Agent 运行中心`

主平台已经具备统一运行上下文和产物管理能力，因此天然适合作为聊天助手的“上下文提供方”。

### 3.2 `fa/` 现状

`fa/` 当前不是一套可直接上线的完整子系统，而是一个增强能力草稿包。

当前可确认的有效增量主要有：

- `OCR fallback PDF 解析`
  - [fa/backend/app/utils/pdf_parser.py](/d:/software/ate-ai-platform/fa/backend/app/utils/pdf_parser.py)
- `Workspace Memory`
  - [fa/backend/app/services/workspace_memory_service.py](/d:/software/ate-ai-platform/fa/backend/app/services/workspace_memory_service.py)
  - [fa/backend/app/api/v1/workspace_memory.py](/d:/software/ate-ai-platform/fa/backend/app/api/v1/workspace_memory.py)
- `扩展知识库内容`
  - [fa/data/knowledge/](/d:/software/ate-ai-platform/fa/data/knowledge/)

但它目前也存在明显缺口：

- `fa/backend/app/main.py` 引用了 `chat/testplan/resource_map/codegen/diagnosis` 等路由
- 实际 `fa/backend/app/api/v1/` 下只有 `workspace_memory.py`
- 依赖 `app.db.base`、`app.db.session`、`app.core.response`、`app.utils.logger` 等，但 `fa/` 中并未形成完整闭环

因此结论是：

**`fa/` 应被视为主平台增强来源，而不是应继续单独演进的正式系统。**

## 4. 迁移后目标架构

```text
ATE AI Platform
├─ 主工作流页面
│  ├─ Agent 工作台
│  ├─ Agent 运行中心
│  ├─ TestPlan
│  ├─ 资源映射
│  ├─ 代码生成
│  └─ 良率诊断
├─ 工程师助手
│  ├─ TestPlan 咨询
│  ├─ 资源映射建议
│  ├─ 代码生成辅助
│  ├─ 故障诊断问答
│  └─ 当前 Run 分析
└─ 统一后端
   ├─ 现有业务 API
   ├─ chat API
   ├─ workspace memory API
   ├─ OCR fallback PDF 解析
   └─ 统一知识库/RAG
```

## 5. 助手设计原则

### 5.1 单入口

前端只新增一个一级入口：

- `工程师助手`

不建议同时新增：

- `测试聊天助手`
- `资源映射助手`
- `诊断助手`

这种拆法容易让信息架构变散。

### 5.2 多模式

在 `工程师助手` 内部提供模式切换即可：

- `TestPlan`
- `资源映射`
- `代码生成`
- `故障诊断`
- `当前 Run`

### 5.3 上下文驱动

助手必须优先读取主平台当前上下文，而不是只做自由问答。

建议接入的上下文包括：

- 当前芯片名 / 芯片类型
- 最近一次 TestPlan 提取结果
- 最近一次资源映射结果
- 最近一次代码生成结果
- 最近一次故障诊断主题
- 当前选中的 Agent Run
- 当前 Run 的 artifacts / warnings / review summary

## 6. 建议迁移范围

### 6.1 第一批：建议直接迁移

#### A. OCR fallback PDF 解析

来源：

- [fa/backend/app/utils/pdf_parser.py](/d:/software/ate-ai-platform/fa/backend/app/utils/pdf_parser.py)

目标：

- 合并进主仓库：
  - [backend/app/utils/pdf_parser.py](/d:/software/ate-ai-platform/backend/app/utils/pdf_parser.py)

迁移价值：

- 当前主平台正缺 OCR fallback
- 可提升扫描件、图片型 PDF、复杂 pinout 页面的处理能力

建议保留能力：

- `ENABLE_PDF_OCR_FALLBACK`
- `PDF_OCR_MIN_CHARS`
- `PDF_OCR_DPI`
- `extract_method = pdfplumber / ocr / merged`

#### B. Workspace Memory

来源：

- [fa/backend/app/services/workspace_memory_service.py](/d:/software/ate-ai-platform/fa/backend/app/services/workspace_memory_service.py)
- [fa/backend/app/api/v1/workspace_memory.py](/d:/software/ate-ai-platform/fa/backend/app/api/v1/workspace_memory.py)

目标：

- 新增到主仓库：
  - `backend/app/services/workspace_memory_service.py`
  - `backend/app/api/v1/workspace_memory.py`

迁移价值：

- 为工程师助手提供跨页面、跨模块的上下文记忆
- 可记录最近芯片、最近 TestPlan、最近资源映射、最近代码生成和故障主题

#### C. 知识库内容

来源：

- [fa/data/knowledge/](/d:/software/ate-ai-platform/fa/data/knowledge/)

目标：

- 并入主仓库知识库目录
- 让主仓库 `rag_service.py` 支持扫描这些分类知识

建议并入后的目录形态：

```text
data/knowledge/
├─ chips/
├─ codegen/
├─ failure/
├─ resource/
├─ standards/
├─ sts8200s/
└─ testplan/
```

### 6.2 第二批：建议按主框架重写，不直接搬运

#### A. chat API

`fa/main.py` 已经想接 `chat.router`，但 `fa/` 里并没有形成完整实现。

因此不建议从 `fa` 直接搬运，而建议在主仓库按现有架构新建：

- `backend/app/api/v1/chat.py`
- `backend/app/services/chat_service.py`

这个聊天服务要直接依赖主平台现有能力，而不是重新造一套业务链。

#### B. RAG service

来源：

- [fa/backend/app/services/rag_service.py](/d:/software/ate-ai-platform/fa/backend/app/services/rag_service.py)

主仓库已有：

- [backend/app/services/rag_service.py](/d:/software/ate-ai-platform/backend/app/services/rag_service.py)

不建议整文件替换。

建议做法：

- 保留主仓库版本为正式实现
- 有选择地吸收：
  - 多目录知识扫描
  - embedding 配置兼容
  - 分类知识管理能力

### 6.3 第三批：建议暂不迁移

- `fa/backend/app/main.py`
- `fa/backend/app/core/config.py`
- `fa/requirements.txt` 整体

原因：

- 与主仓库现有入口、配置、依赖重复度高
- 直接并入容易引发两套服务端逻辑冲突

## 7. 主框架内的最终落点

### 7.1 后端新增建议

#### 新增 API

- `GET /api/v1/workspace-memory`
- `POST /api/v1/workspace-memory/reset`
- `POST /api/v1/chat/query`

#### 新增服务

- `workspace_memory_service.py`
- `chat_service.py`

#### chat_service 建议职责

- 读取 workspace memory
- 读取最近 run / 当前选中 run
- 读取最近 artifacts
- 根据模式组装提示词
- 调用主仓库 `rag_service`
- 返回：
  - 回答
  - 参考上下文摘要
  - 建议下一步动作

### 7.2 前端新增建议

建议新增页面：

- `apps/src/pages/EngineerAssistantPage.tsx`

建议新增组件：

- `apps/src/components/assistant/AssistantPanel.tsx`
- `apps/src/components/assistant/AssistantModeTabs.tsx`
- `apps/src/components/assistant/AssistantContextCard.tsx`
- `apps/src/components/assistant/AssistantMessageList.tsx`

建议模式：

- `testplan`
- `resource-map`
- `codegen`
- `diagnosis`
- `run-analysis`

建议侧边/顶部信息展示：

- 当前芯片
- 最近 TestPlan
- 最近资源映射
- 最近代码生成
- 当前选中 Run

## 8. 与现有页面的关系

工程师助手不是替代现有页面，而是作为“辅助解释和决策层”。

关系建议如下：

- `TestPlan 页`
  - 继续负责提取与结果展示
  - 助手负责解释参数、风险和缺失项

- `资源映射页`
  - 继续负责生成映射、PGS、BOM、SVG
  - 助手负责解释为什么这样分配、哪些 rail 有风险

- `代码生成页`
  - 继续负责代码初稿生成
  - 助手负责解释生成逻辑、指出 review 重点

- `Agent 工作台`
  - 继续负责完整流程
  - 助手负责解释当前 run 卡在哪一步、下一步该做什么

## 9. 分阶段实施建议

### 阶段 1：并 OCR fallback

目标：

- 提升 PDF 解析能力

工作：

- 合并 `fa` OCR 版 `pdf_parser.py`
- 补配置项
- 补依赖
- 补测试

完成标准：

- 文本 PDF 不回退
- 稀疏页可自动 OCR
- 提取结果能标注 `extract_method`

### 阶段 2：并 Workspace Memory

目标：

- 让平台开始具备跨模块上下文记忆

工作：

- 加 `workspace_memory_service`
- 加 API
- 在 TestPlan / ResourceMap / Codegen / Diagnosis 成功后更新上下文

完成标准：

- 能查看最近上下文
- 能 reset
- 能为后续 chat 提供摘要

### 阶段 3：并知识库目录

目标：

- 统一主平台知识来源

工作：

- 迁移 `fa/data/knowledge`
- 更新主仓库 `rag_service.py`
- 增加分类扫描与索引构建

完成标准：

- RAG 可加载扩展知识
- 助手与代码生成都能复用

### 阶段 4：新增工程师助手页面

目标：

- 形成统一助手入口

工作：

- 新增 `EngineerAssistantPage`
- 新增模式切换
- 接主仓库 chat API
- 接 workspace memory

完成标准：

- 可在一个页面下做多模式咨询
- 能读取当前工作区上下文

### 阶段 5：与 Agent 工作台联动

目标：

- 让助手真正理解当前运行状态

工作：

- 接入当前 run
- 接入 artifacts
- 接入 review summary
- 提供“下一步建议”

完成标准：

- 助手可以解释 run 状态
- 助手可回答“为什么卡在这里”“批准后会发生什么”

## 10. 风险与注意事项

### 10.1 不要保留第二套正式后端

风险：

- 状态不同步
- 维护成本翻倍
- 配置冲突
- 文档越来越乱

建议：

- `backend/` 作为唯一正式后端
- `fa/` 只作为迁移来源，迁移完成后归档或删除

### 10.2 不要先做自由聊天，再补上下文

风险：

- 看起来像普通 AI 聊天
- 对 ATE 平台帮助有限

建议：

- 先接上下文，再做聊天

### 10.3 OCR 需要按需启用

风险：

- 全量 OCR 会变慢
- 表格字符错误可能更多

建议：

- 仅在文本层稀疏页触发 OCR fallback

## 11. 最终建议结论

对你们现在这套系统，最合理的融合路径是：

1. 不把 `fa` 继续做成第二套独立系统
2. 保留 `fa` 中最有价值的三块：
   - OCR fallback
   - workspace memory
   - 分类知识库
3. 在主仓库中新增统一入口：
   - `工程师助手`
4. 让它成为基于主平台上下文的多模式工程副驾

一句话总结：

**主平台负责“做事”，工程师助手负责“解释、建议、协同”，二者必须共用同一套后端和上下文。**

## 12. 推荐下一步

如果按实施顺序推进，建议你们下一步就做：

1. 合并 OCR fallback 到主仓库 `pdf_parser.py`
2. 合并 workspace memory 到主仓库
3. 新增 `工程师助手` 页面骨架

这是收益最大、风险最小、最符合当前项目阶段的融合路线。
