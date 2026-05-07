export type View =
  | 'agent-workspace'
  | 'agent-runs'
  | 'testplan'
  | 'resource-map'
  | 'codegen'
  | 'diagnosis'
  | 'knowledge-base'
  | 'settings';

export type ThemeMode = 'dark' | 'light';

export const viewMeta: Record<View, { title: string; description: string }> = {
  'agent-workspace': {
    title: 'ATE Agent 工作台',
    description: '自动化总入口，负责发起完整 ATE Agent 开发流程。',
  },
  'agent-runs': {
    title: 'Agent 运行中心',
    description: '查看历史运行、步骤时间线、中间产物和工程复核结果。',
  },
  testplan: {
    title: 'Datasheet / TestPlan',
    description: '手动工具模式下的数据手册提取与测试计划生成页面。',
  },
  'resource-map': {
    title: 'STS8200S 资源映射',
    description: '手动生成资源映射、BOM、PGS 与 SVG 交付件。',
  },
  codegen: {
    title: 'RAG 测试代码生成',
    description: '手动生成测试代码、工程包与辅助复核信息。',
  },
  diagnosis: {
    title: '良率诊断',
    description: '用于查看诊断结果、波形趋势和异常模式。',
  },
  'knowledge-base': {
    title: '知识库管理',
    description: '查看企业样例、RAG 资料与知识资产接入状态。',
  },
  settings: {
    title: '设置',
    description: '统一管理系统配置、运行方式和桌面端使用提示。',
  },
};

export interface Insight {
  id: string;
  type: 'critical' | 'info' | 'success';
  title: string;
  description: string;
  time: string;
}

export interface PinDefinition {
  id: string;
  name: string;
  type: string;
  description: string;
}

export interface ResourceMapping {
  pin: string;
  type: string;
  resource: string;
  isWarning?: boolean;
}
