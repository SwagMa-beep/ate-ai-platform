export type View =
  | 'agent-workspace'
  | 'engineer-assistant'
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
    description: '',
  },
  'engineer-assistant': {
    title: '工程师助手',
    description: '',
  },
  'agent-runs': {
    title: 'Agent 运行中心',
    description: '',
  },
  testplan: {
    title: 'Datasheet / TestPlan',
    description: '',
  },
  'resource-map': {
    title: 'STS8200S 资源映射',
    description: '',
  },
  codegen: {
    title: 'RAG 测试代码生成',
    description: '',
  },
  diagnosis: {
    title: '良率诊断',
    description: '',
  },
  'knowledge-base': {
    title: '知识库管理',
    description: '',
  },
  settings: {
    title: '设置',
    description: '',
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
