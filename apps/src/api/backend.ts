/**
 * ATE-AI-Platform 后端 API 客户端
 * 封装所有与 FastAPI 后端的通信
 */

function readStoredApiOrigin(storage: Pick<Storage, 'getItem'> | undefined): string {
  try {
    return storage?.getItem('ate_api_origin') || '';
  } catch {
    return '';
  }
}

function persistApiOrigin(apiOrigin: string) {
  if (!apiOrigin || typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem('ate_api_origin', apiOrigin);
  } catch {
    // ignore storage failures
  }
  try {
    window.localStorage.setItem('ate_api_origin', apiOrigin);
  } catch {
    // ignore storage failures
  }
}

const LOCAL_API_ORIGIN = 'http://127.0.0.1:18081';

function normalizeLocalApiOrigin(apiOrigin: string): string {
  const normalized = (apiOrigin || '').replace(/\/$/, '');
  if (!normalized) return '';
  if (normalized === 'http://127.0.0.1:18080' || normalized === 'http://localhost:18080') {
    return LOCAL_API_ORIGIN;
  }
  return normalized;
}

export function getApiOrigin(): string {
  const envOrigin = (import.meta.env.VITE_API_ORIGIN || '').replace(/\/$/, '');
  if (envOrigin) return envOrigin;

  if (typeof window === 'undefined') return '';

  const fromQuery = normalizeLocalApiOrigin(new URLSearchParams(window.location.search).get('apiOrigin') || '');
  if (fromQuery) {
    persistApiOrigin(fromQuery);
    return fromQuery;
  }

  const fromSession = normalizeLocalApiOrigin(readStoredApiOrigin(window.sessionStorage));
  if (fromSession) {
    persistApiOrigin(fromSession);
    return fromSession;
  }

  const fromLocal = normalizeLocalApiOrigin(readStoredApiOrigin(window.localStorage));
  if (fromLocal) {
    persistApiOrigin(fromLocal);
    return fromLocal;
  }

  if (window.location.protocol === 'file:') return LOCAL_API_ORIGIN;
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') return LOCAL_API_ORIGIN;
  return '';
}

function getBaseUrl(): string {
  return `${getApiOrigin()}/api/v1`;
}

export function resolveBackendUrl(url: string): string {
  const apiOrigin = getApiOrigin();
  if (!url) return url;
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith('//')) {
    const protocol = typeof window !== 'undefined' ? window.location.protocol : 'http:';
    return `${protocol}${url}`;
  }
  if (url.startsWith('/')) return `${apiOrigin}${url}`;
  return `${apiOrigin}/${url.replace(/^\.?\//, '')}`;
}

// 通用响应类型
export interface ApiResponse<T> {
  code: number;
  status: 'success' | 'error';
  message: string;
  data: T | null;
  timestamp: number;
}

// TestPlan 相关类型
export interface UploadResult {
  file_id: string;
  filename: string;
  size: number;
  size_mb: number;
  upload_time: string;
}

export interface ExtractionStatistics {
  total: number;
  A_class: number;
  B_class: number;
  C_class: number;
  blocked: number;
  dc_items: number;
  ac_items: number;
  ldo_items: number;
}

export interface RangeRecommendation {
  param: string;
  value: string;
  range_module: string;
  range_value: string;
  reason: string;
  priority: 'high' | 'normal';
}

export interface ExtractionResult {
  chip_name: string;
  chip_type: string;
  test_scenario: string;
  pin_count: number;
  statistics: ExtractionStatistics;
  files: {
    excel: string;
    json: string;
  };
  sts_compatibility: {
    is_compatible: boolean;
    chip_type: string;
    issues: string[];
    recommendations: string[];
  };
  warnings: string[];
  range_recommendations?: RangeRecommendation[];
  run?: AgentRunResult;
}

export interface PinDefinition {
  pin_no: number | string;
  pin_name: string;
  function?: string;
  direction?: string;
  voltage_max?: number;
  notes?: string;
}

export interface PinsResult {
  chip_name: string;
  chip_type: string;
  pin_count: number;
  pin_definitions: PinDefinition[];
  has_pins: boolean;
}

export interface FileListItem {
  filename: string;
  chip_name: string;
  chip_type: string;
  size_mb: number;
  created_time: string;
}

// 资源映射相关类型
export interface ResourceMapResult {
  chip_name: string;
  chip_type: string;
  adapter: string;
  pin_count: number;
  pgs_items: number;
  pin_auto_loaded: boolean;
  summary?: {
    resource_type_counts: Record<string, number>;
    power_pin_count: number;
    bidir_pin_count: number;
    unassigned_count: number;
    dio_site1_count: number;
    dio_site2_count: number;
    site_count: number;
  };
  download: {
    resource_map_excel: string;
    schematic_svg: string;
    bom_excel: string;
  };
  warnings: string[];
  run?: AgentRunResult;
}

// 健康检查
export interface HealthResult {
  status: string;
  version: string;
  debug_mode: boolean;
  api_configured: boolean;
  upload_dir: string;
  upload_exists: boolean;
}

// 通用请求函数
async function request<T>(
  url: string,
  options?: RequestInit,
  timeoutMs = 30000,
): Promise<ApiResponse<T>> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      signal: options?.signal || controller.signal,
    });
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      throw new Error(`请求超时，请检查后端状态或确认当前任务是否执行过慢：${getApiOrigin()}`);
    }
    throw err;
  } finally {
    window.clearTimeout(timer);
  }
  if (!response.ok) {
    // 尝试解析后端错误响应
    try {
      return await response.json();
    } catch {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
  }
  return response.json();
}

// 健康检查
export async function checkHealth(): Promise<ApiResponse<HealthResult>> {
  return request<HealthResult>(`${getApiOrigin()}/health`, undefined, 5000);
}

// TestPlan API
export async function uploadPDF(file: File): Promise<ApiResponse<UploadResult>> {
  const formData = new FormData();
  formData.append('file', file);
  return request<UploadResult>(
    `${getBaseUrl()}/testplan/upload`,
    {
      method: 'POST',
      body: formData,
    },
    60000,
  );
}

export async function extractTestplan(
  fileId: string,
  options: { pages?: string; maxWorkers?: number } = {},
): Promise<ApiResponse<ExtractionResult>> {
  const params = new URLSearchParams({ file_id: fileId });
  if (options.pages) params.append('pages', options.pages);
  if (options.maxWorkers) params.append('max_workers', String(options.maxWorkers));
  return request<ExtractionResult>(`${getBaseUrl()}/testplan/extract?${params}`, {
    method: 'POST',
  });
}

export interface TaskStatusResult {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelling' | 'cancelled';
  progress: number;
  message: string;
  file_id?: string;
  pages?: string;
  max_workers?: number;
  result?: ExtractionResult;
  start_time?: string;
  end_time?: string;
}

export interface TaskListResult {
  items: TaskStatusResult[];
  total: number;
}

export async function extractTestplanAsync(
  fileId: string,
  options: { pages?: string; maxWorkers?: number } = {},
): Promise<ApiResponse<{ task_id: string; status_url: string; file_id: string }>> {
  const params = new URLSearchParams({ file_id: fileId });
  if (options.pages) params.append('pages', options.pages);
  if (options.maxWorkers) params.append('max_workers', String(options.maxWorkers));
  return request(`${getBaseUrl()}/testplan/extract-async?${params}`, {
    method: 'POST',
  });
}

export async function getTaskStatus(taskId: string): Promise<ApiResponse<TaskStatusResult>> {
  return request<TaskStatusResult>(`${getBaseUrl()}/testplan/status/${taskId}`);
}

export async function listExtractionTasks(limit = 50): Promise<ApiResponse<TaskListResult>> {
  return request<TaskListResult>(`${getBaseUrl()}/testplan/tasks?limit=${limit}`);
}

export async function retryExtractionTask(
  taskId: string,
): Promise<ApiResponse<{ task_id: string; status_url: string; file_id: string }>> {
  return request(`${getBaseUrl()}/testplan/retry/${taskId}`, {
    method: 'POST',
  });
}

export async function cancelExtractionTask(taskId: string): Promise<ApiResponse<{ task_id: string; status: string }>> {
  return request(`${getBaseUrl()}/testplan/cancel/${taskId}`, {
    method: 'POST',
  });
}

export async function cleanExtractionTasks(
  status?: 'completed' | 'failed' | 'cancelled',
): Promise<ApiResponse<{ deleted_count: number; statuses: string[] }>> {
  const suffix = status ? `?status=${status}` : '';
  return request(`${getBaseUrl()}/testplan/tasks${suffix}`, {
    method: 'DELETE',
  });
}

export async function getPinDefinitions(fileId: string): Promise<ApiResponse<PinsResult>> {
  return request<PinsResult>(`${getBaseUrl()}/testplan/pins/${fileId}`);
}

export async function listFiles(
  page = 1,
  pageSize = 10,
): Promise<ApiResponse<{ items: FileListItem[]; total: number }>> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return request(`${getBaseUrl()}/testplan/list?${params}`);
}

export function getDownloadUrl(fileId: string, type: 'excel' | 'json'): string {
  return `${getBaseUrl()}/testplan/download/${fileId}/${type}`;
}

// 资源映射 API
export async function generateResourceMap(
  fileId: string,
  dualSite = false,
): Promise<{ status: string; message: string; data: ResourceMapResult }> {
  const formData = new FormData();
  formData.append('file_id', fileId);
  formData.append('dual_site', String(dualSite));
  const response = await fetch(`${getBaseUrl()}/resource-map/generate`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

// 代码生成相关类型
export interface CodegenRequest {
  chip_name: string;
  chip_type: 'digital' | 'ldo' | 'custom';
  test_items: string[];
  user_prompt: string;
  file_id?: string;
  auto_recommend?: boolean;
  export_package?: boolean;
  pin_names?: string[];
  input_pins?: string[];
  output_pins?: string[];
  vcc?: number;
  vout?: number;
  ldo_out_pin?: number;
  load_ma?: number;
}

export interface CompileValidationResult {
  attempted: boolean;
  passed: boolean;
  compiler?: string;
  command?: string;
  diagnostics?: string[];
}

export interface GeneratedPackageFile {
  file_type: string;
  path: string;
  relative_path: string;
}

export interface PackageValidationCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface PackageBuildValidation {
  attempted: boolean;
  passed: boolean;
  tool?: string | null;
  command?: string[];
  diagnostics?: string[];
}

export interface PackageValidationResult {
  attempted: boolean;
  passed: boolean;
  checks: PackageValidationCheck[];
  build_validation: PackageBuildValidation;
  diagnostics?: string[];
}

export interface CodegenPlanItem {
  item: string;
  description: string;
  apis: string[];
  template_source: string;
  vector_required: boolean;
  pin_requirements: {
    needs_input_pins: boolean;
    needs_output_pins: boolean;
  };
  blocking_errors?: string[];
  warnings?: string[];
}

export interface CodegenPlan {
  chip_name: string;
  chip_type: string;
  scenario: string;
  selected_items: string[];
  recommended_items: string[];
  resources: string[];
  requires_vector: boolean;
  requires_pgs: boolean;
  electrical: {
    vcc: number;
    vout: number;
    ldo_out_pin: number;
    load_ma: number;
  };
  pins: {
    pin_count: number;
    input_count: number;
    output_count: number;
    power_like_count?: number;
  };
  items: CodegenPlanItem[];
  errors: string[];
  warnings: string[];
}

export interface AgentRunStep {
  agent: string;
  status: string;
  message?: string;
  warnings?: string[];
  errors?: string[];
  artifacts?: {
    name?: string;
    type?: string;
    producer?: string;
    summary?: Record<string, unknown>;
  }[];
  metadata?: Record<string, unknown>;
  next_action?: string | null;
  requires_human_review?: boolean;
  quality?: {
    score: number;
    fallback_used: boolean;
    risk_flags: string[];
  };
}

export interface AgentRunArtifact {
  name?: string;
  type?: string;
  producer?: string;
  path?: string;
  format?: string;
  metadata_path?: string;
  summary?: Record<string, unknown>;
}

export interface AgentRunResult {
  run_id: string;
  flow_name: string;
  status: string;
  created_at?: string;
  updated_at?: string;
  steps: AgentRunStep[];
  warnings: string[];
  errors: string[];
  artifacts: AgentRunArtifact[];
  shared?: Record<string, unknown>;
  parent_run_id?: string | null;
  continuation_run_id?: string | null;
  triggered_by?: string | null;
  review_source_run_id?: string | null;
  review_decision?: {
    decision: string;
    reviewer: string;
    reason: string;
    reviewed_at: string;
    rejection_type?: 'input_issue' | 'engineering_decision' | 'auto_fixable';
    resolution_owner?: 'user' | 'agent';
    next_action?: string;
  };
  continuation_run?: AgentRunResult;
  routing_run?: AgentRunResult;
}

export async function listAgentRuns(
  limit = 20,
  flowName?: string,
): Promise<ApiResponse<{ items: AgentRunResult[]; total: number }>> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (flowName) params.append('flow_name', flowName);
  return request<{ items: AgentRunResult[]; total: number }>(`${getBaseUrl()}/agent-runs?${params}`);
}

export async function clearAgentRuns(
  flowName?: string,
): Promise<ApiResponse<{ deleted_count: number; flow_name?: string | null }>> {
  const suffix = flowName ? `?flow_name=${encodeURIComponent(flowName)}` : '';
  return request<{ deleted_count: number; flow_name?: string | null }>(`${getBaseUrl()}/agent-runs${suffix}`, {
    method: 'DELETE',
  });
}

export async function getAgentRun(runId: string): Promise<ApiResponse<AgentRunResult>> {
  return request<AgentRunResult>(`${getBaseUrl()}/agent-runs/${runId}`);
}

export async function getAgentRunArtifacts(
  runId: string,
): Promise<ApiResponse<{ run_id: string; flow_name: string; status: string; artifacts: AgentRunArtifact[] }>> {
  return request<{ run_id: string; flow_name: string; status: string; artifacts: AgentRunArtifact[] }>(
    `${getBaseUrl()}/agent-runs/${runId}/artifacts`,
  );
}

export async function getAgentRunArtifact(
  runId: string,
  artifactName: string,
): Promise<ApiResponse<{ run_id: string; flow_name: string; status: string; artifact: AgentRunArtifact }>> {
  return request<{ run_id: string; flow_name: string; status: string; artifact: AgentRunArtifact }>(
    `${getBaseUrl()}/agent-runs/${runId}/artifacts/${encodeURIComponent(artifactName)}`,
  );
}

export interface FullAteRunCreateRequest {
  flow_name: 'full_ate_development';
  goal: string;
  file_id?: string;
  pdf_path?: string;
  chip_name?: string;
  chip_type?: string;
  test_items?: string[];
  user_prompt?: string;
  auto_recommend?: boolean;
  export_package?: boolean;
  pages?: string;
  max_workers?: number;
  dual_site?: boolean;
  vcc?: number;
  vout?: number;
  ldo_out_pin?: number;
  load_ma?: number;
  async_mode?: boolean;
}

export async function approveAgentRun(
  runId: string,
  reviewer = 'ATE Engineer',
): Promise<ApiResponse<AgentRunResult>> {
  return request<AgentRunResult>(`${getBaseUrl()}/agent-runs/${runId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer }),
  });
}

export async function rejectAgentRun(
  runId: string,
  reason = '',
  reviewer = 'ATE Engineer',
): Promise<ApiResponse<AgentRunResult>> {
  return request<AgentRunResult>(`${getBaseUrl()}/agent-runs/${runId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer, reason }),
  });
}

export async function rejectAgentRunWithRouting(
  runId: string,
  payload: {
    reviewer?: string;
    reason: string;
    rejection_type: 'input_issue' | 'engineering_decision' | 'auto_fixable';
  },
): Promise<ApiResponse<AgentRunResult>> {
  return request<AgentRunResult>(`${getBaseUrl()}/agent-runs/${runId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reviewer: payload.reviewer || 'ATE Engineer',
      reason: payload.reason,
      rejection_type: payload.rejection_type,
    }),
  });
}

export async function createFullAteRun(payload: FullAteRunCreateRequest): Promise<ApiResponse<AgentRunResult>> {
  return request<AgentRunResult>(
    `${getBaseUrl()}/agent-runs`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    180000,
  );
}

export async function createFullAteRunAsync(payload: FullAteRunCreateRequest): Promise<ApiResponse<AgentRunResult>> {
  return request<AgentRunResult>(
    `${getBaseUrl()}/agent-runs`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, async_mode: true }),
    },
    15000,
  );
}

export interface PackageExportResult {
  generation_id: string;
  chip_name: string;
  chip_type: string;
  generator_mode: string;
  output_dir: string;
  package_zip?: string | null;
  download_url?: string | null;
  generated_files: GeneratedPackageFile[];
  function_count: number;
  test_items: string[];
  package_validation?: PackageValidationResult;
  notes: string[];
  inputs: {
    testplan_json: string;
    resource_map_excel?: string | null;
    bom_excel?: string | null;
    schematic_svg?: string | null;
  };
}

export interface CodegenResult {
  code: string;
  filename: string;
  lines: number;
  functions: number;
  chip_name: string;
  chip_type: string;
  test_items: string[];
  recommended_items?: string[];
  knowledge_used?: boolean;
  knowledge_items?: {
    item: string;
    description: string;
    apis: string[];
    scenarios: string[];
  }[];
  ai_analysis: string[];
  static_analysis?: {
    passed: boolean;
    score: number;
    summary: string;
    errors: { rule: string; message: string; line?: number }[];
    warnings: { rule: string; message: string }[];
    duration_ms: number;
  };
  retrieved_chunks?: {
    text: string;
    source: string;
    score: number;
  }[];
  plan?: CodegenPlan;
  compile_validation?: CompileValidationResult;
  package_export?: PackageExportResult;
  run?: AgentRunResult;
}

export interface TemplateItem {
  id: string;
  name: string;
  desc: string;
}

export interface TemplatesResult {
  digital: TemplateItem[];
  ldo: TemplateItem[];
  knowledge_summary?: {
    root: string;
    sample_count: number;
    item_count: number;
  };
}

export async function generateCode(req: CodegenRequest): Promise<ApiResponse<CodegenResult>> {
  return request<CodegenResult>(`${getBaseUrl()}/codegen/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}

export async function getCodeTemplates(): Promise<ApiResponse<TemplatesResult>> {
  return request<TemplatesResult>(`${getBaseUrl()}/codegen/templates`);
}

export interface CodegenRecommendation {
  chip_type: string;
  scenario: string;
  source: string;
  recommended_items: string[];
  optional_items: string[];
  detected_params?: string[];
  reason_summary?: string[];
  available_items: string[];
}

export async function recommendCodeItems(
  req: { chip_type?: string; file_id?: string },
): Promise<ApiResponse<CodegenRecommendation>> {
  return request<CodegenRecommendation>(`${getBaseUrl()}/codegen/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}

// RAG 相关类型
export interface RagStatus {
  ready: boolean;
  doc_count: number;
  backend: string;
  index_hash: string;
}

export async function getRagStatus(): Promise<ApiResponse<RagStatus>> {
  return request<RagStatus>(`${getBaseUrl()}/rag/status`);
}

export async function buildRagIndex(pdfPath?: string): Promise<ApiResponse<RagStatus>> {
  return request<RagStatus>(`${getBaseUrl()}/rag/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pdf_path: pdfPath || null }),
  });
}

// 诊断相关类型
export interface AnomalyEvent {
  type: string;
  confidence: number;
  description: string;
  severity: 'high' | 'medium' | 'low';
  timestamp: string;
  channel: number;
}

export interface WaveformPoint {
  t: number;
  v: number;
  i: number;
  flag: boolean;
}

export interface DiagnosisResult {
  yield_rate: number;
  yield_trend: number;
  yield_predicted: number;
  fty_rolling: number;
  sample_count: number;
  anomaly_ratio: number;
  model_backend: string;
  analysis_time_ms: number;
  anomalies: AnomalyEvent[];
  waveform: WaveformPoint[];
}

export interface DiagnosisRequest {
  n_samples?: number;
  inject_anomaly?: boolean;
  anomaly_ratio?: number;
  channel?: number;
}

export async function runDiagnosis(req?: DiagnosisRequest): Promise<ApiResponse<DiagnosisResult>> {
  return request<DiagnosisResult>(`${getBaseUrl()}/diagnosis/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req || {}),
  });
}

export async function getWaveform(
  nPoints?: number,
): Promise<ApiResponse<{ waveform: WaveformPoint[]; yield_rate: number; anomaly_ratio: number }>> {
  const qs = nPoints ? `?n_points=${nPoints}` : '';
  return request(`${getBaseUrl()}/diagnosis/waveform${qs}`);
}

export interface WorkspaceMemoryNote {
  text: string;
  updated_at: string;
}

export interface WorkspaceMemory {
  current_chip: {
    name: string;
    chip_type: string;
    updated_at: string;
  };
  recent_testplan: {
    file_id: string;
    file_name: string;
    summary: string;
    updated_at: string;
  };
  recent_resource_map: {
    file_name: string;
    summary: string;
    updated_at: string;
  };
  recent_codegen: {
    template: string;
    summary: string;
    updated_at: string;
  };
  recent_failure_topic: {
    topic: string;
    summary: string;
    updated_at: string;
  };
  notes: WorkspaceMemoryNote[];
}

export type AssistantMode = 'general' | 'testplan' | 'resource-map' | 'codegen' | 'diagnosis' | 'run-analysis';

export interface AssistantChatRequest {
  message: string;
  mode: AssistantMode;
  run_id?: string;
}

export interface AssistantChunk {
  source: string;
  score: number;
  text: string;
}

export interface AssistantChatResult {
  mode: AssistantMode;
  answer: string;
  context_summary: string;
  related_run?: AgentRunResult | null;
  retrieved_chunks: AssistantChunk[];
  suggested_actions: string[];
  image_count?: number;
  model_backend?: string;
}

export async function getWorkspaceMemory(): Promise<ApiResponse<WorkspaceMemory>> {
  return request<WorkspaceMemory>(`${getBaseUrl()}/workspace-memory`);
}

export async function resetWorkspaceMemory(): Promise<ApiResponse<WorkspaceMemory>> {
  return request<WorkspaceMemory>(`${getBaseUrl()}/workspace-memory/reset`, {
    method: 'POST',
  });
}

export async function queryEngineerAssistant(
  payload: AssistantChatRequest,
): Promise<ApiResponse<AssistantChatResult>> {
  return request<AssistantChatResult>(`${getBaseUrl()}/chat/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function sendEngineerAssistantMessage(payload: {
  message: string;
  mode: AssistantMode;
  run_id?: string;
  images?: File[];
}): Promise<ApiResponse<AssistantChatResult>> {
  const form = new FormData();
  form.append('message', payload.message || '');
  form.append('mode', payload.mode);
  if (payload.run_id) form.append('run_id', payload.run_id);
  (payload.images || []).forEach(file => form.append('images', file));
  return request<AssistantChatResult>(`${getBaseUrl()}/chat/message`, {
    method: 'POST',
    body: form,
  });
}
