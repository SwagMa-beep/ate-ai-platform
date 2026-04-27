export type View = 'dashboard' | 'extractor' | 'resources' | 'codelab' | 'agentruns' | 'failure';

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
