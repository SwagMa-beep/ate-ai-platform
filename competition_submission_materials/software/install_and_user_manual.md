# 软件安装及使用说明书

## 1. 软件名称

ATE-AI-Platform：基于语言大模型的智能 ATE 测试开发辅助平台。

## 2. 运行环境

### 桌面安装版

- 操作系统：Windows 10/11，64 位
- 网络环境：需要访问 DeepSeek API
- 用户环境：无需安装 Python，后端运行时已内置在安装包中

### 开发运行版

- Python 3.10+
- Node.js 20+
- DeepSeek API Key
- 推荐使用 PowerShell 或 Windows Terminal

## 3. 安装方式

1. 获取安装包：

```text
ATE-AI-Platform-Setup-0.0.7.exe
```

2. 双击安装包，按提示完成安装。
3. 安装完成后，从桌面快捷方式或开始菜单启动 `ATE AI Platform`。
4. 若系统安全软件提示未知程序，请确认来源可信后允许运行。

## 4. 桌面端使用流程

### 4.1 启动软件

启动后，软件会自动拉起本地后端服务。仪表盘中“后端 API”显示在线时，表示系统可正常使用。

### 4.2 上传 Datasheet

1. 进入“提取器”页面。
2. 点击“选择 PDF 文件”或将 Datasheet 拖拽到上传区域。
3. 系统会先检查后端 API 是否可用，再上传 PDF。
4. 上传成功后自动提交异步提取任务。

### 4.3 查看提取结果

系统提取完成后展示：

- 芯片名称与类型
- 参数总数
- A/B/C 类参数统计
- DC/AC/LDO 测试项统计
- 引脚定义表
- STS8200S 兼容性提示
- 量程推荐和风险提示

### 4.4 下载结果文件

支持下载：

- TestPlan Excel
- TestPlan JSON

### 4.5 资源映射

在“资源”页面，系统可基于模块一的 TestPlan JSON 和引脚定义生成：

- STS8200S 资源映射表
- PGS 配置
- 引脚分组
- BOM 清单
- 辅助 SVG 示意图

### 4.6 测试代码生成

在“代码实验室”页面，选择芯片类型和测试项，系统生成 STS8200S C++ 测试程序骨架，并输出静态风险提示。

### 4.7 良率诊断

在“故障”页面运行良率诊断演示，系统会生成仿真 VI 波形并进行异常检测和故障类型识别。

## 5. 常见问题

### 5.1 后端 API 显示未连接

可能原因：

- Windows Defender 或杀毒软件拦截了 `backend-server.exe`
- 本地端口被占用
- 安装目录资源缺失

排查方式：

```powershell
notepad "$env:APPDATA\ATE AI Platform\backend-launch.log"
```

### 5.2 上传或提取失败

检查：

- 网络是否能访问 DeepSeek API
- API Key 是否配置
- PDF 是否超过 50MB
- PDF 是否为纯扫描图片

### 5.3 日志位置

```text
%APPDATA%\ATE AI Platform\backend-launch.log
%APPDATA%\ATE AI Platform\logs\error.log
%APPDATA%\ATE AI Platform\logs\extraction.log
```

## 6. 开发版启动方式

后端：

```powershell
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端：

```powershell
cd apps
npm install
npm run dev
```

桌面端开发模式：

```powershell
cd apps
npm run desktop:dev
```
