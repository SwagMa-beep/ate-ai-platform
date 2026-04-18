# ATE-AI-Platform

基于语言大模型的智能ATE测试开发与诊断平台

## 🎯 项目简介

本项目使用AI大模型（DeepSeek）自动从芯片Datasheet中提取测试参数，生成标准化的TestPlan Excel文件，大幅提升ATE测试开发效率。

### 核心功能

- ✅ **模块①**：TestPlan自动提取（已完成）
  - PDF智能解析
  - AI参数提取
  - 数据校验与分类
  - Excel/JSON导出

- 🔨 **模块②**：资源映射与原理图辅助（开发中）
- 🔨 **模块③**：TestProgram智能生成（开发中）
- 🔨 **模块④**：边缘AI量产诊断（开发中）

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- Anaconda（推荐）或 virtualenv

### 2. 安装

```bash
# 克隆项目
git clone <your-repo-url>
cd ate-ai-platform

# 创建虚拟环境（Conda）
conda create -n ate-ai python=3.10
conda activate ate-ai

# 安装依赖
cd backend
pip install -r requirements.txt