/**
 * ATE-AI-Platform 后端 API 客户端
 * 封装所有与 FastAPI 后端的通信
 */

const BASE_URL = '/api/v1';

// ─── 通用响应类型 ─────────────────────────────────────────────
export interface ApiResponse<T> {
  code: number;
  status: 'success' | 'error';
  message: string;
  data: T | null;
  timestamp: number;
}

// ─── TestPlan 相关类型 ─────────────────────────────────────────
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
  param:        string;
  value:        string;
  range_module: string;
  range_value:  string;
  reason:       string;
  priority:     'high' | 'normal';
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

// ─── 资源映射相关类型 ─────────────────────────────────────────
export interface ResourceMapResult {
  chip_name: string;
  chip_type: string;
  adapter: string;
  pin_count: number;
  pgs_items: number;
  pin_auto_loaded: boolean;
  download: {
    resource_map_excel: string;
    schematic_svg: string;
    bom_excel: string;
  };
  warnings: string[];
}

// ─── 健康检查 ─────────────────────────────────────────────────
export interface HealthResult {
  status: string;
  version: string;
  debug_mode: boolean;
  api_configured: boolean;
  upload_dir: string;
  upload_exists: boolean;
}

// ─── 通用请求函数 ─────────────────────────────────────────────
async function request<T>(
  url: string,
  options?: RequestInit
): Promise<ApiResponse<T>> {
  const response = await fetch(url, options);
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

// ─── 健康检查 ─────────────────────────────────────────────────
export async function checkHealth(): Promise<ApiResponse<HealthResult>> {
  return request<HealthResult>('/health');
}

// ─── TestPlan API ─────────────────────────────────────────────

/** 上传 PDF 文件 */
export async function uploadPDF(file: File): Promise<ApiResponse<UploadResult>> {
  const formData = new FormData();
  formData.append('file', file);
  return request<UploadResult>(`${BASE_URL}/testplan/upload`, {
    method: 'POST',
    body: formData,
  });
}

/** 同步提取 TestPlan */
export async function extractTestplan(
  fileId: string,
  options: { pages?: string; maxWorkers?: number } = {}
): Promise<ApiResponse<ExtractionResult>> {
  const params = new URLSearchParams({ file_id: fileId });
  if (options.pages) params.append('pages', options.pages);
  if (options.maxWorkers) params.append('max_workers', String(options.maxWorkers));
  return request<ExtractionResult>(`${BASE_URL}/testplan/extract?${params}`, {
    method: 'POST',
  });
}

export interface TaskStatusResult {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
  result?: ExtractionResult;
  start_time?: string;
  end_time?: string;
}

/** 异步提取 TestPlan（提交任务） */
export async function extractTestplanAsync(
  fileId: string,
  options: { pages?: string; maxWorkers?: number } = {}
): Promise<ApiResponse<{ task_id: string; status_url: string; file_id: string }>> {
  const params = new URLSearchParams({ file_id: fileId });
  if (options.pages) params.append('pages', options.pages);
  if (options.maxWorkers) params.append('max_workers', String(options.maxWorkers));
  return request(`${BASE_URL}/testplan/extract-async?${params}`, {
    method: 'POST',
  });
}

/** 查询任务状态 */
export async function getTaskStatus(taskId: string): Promise<ApiResponse<TaskStatusResult>> {
  return request<TaskStatusResult>(`${BASE_URL}/testplan/status/${taskId}`);
}

/** 获取引脚定义 */
export async function getPinDefinitions(fileId: string): Promise<ApiResponse<PinsResult>> {
  return request<PinsResult>(`${BASE_URL}/testplan/pins/${fileId}`);
}

/** 获取文件列表 */
export async function listFiles(page = 1, pageSize = 10): Promise<ApiResponse<{ items: FileListItem[]; total: number }>> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return request(`${BASE_URL}/testplan/list?${params}`);
}

/** 获取下载链接（通过代理） */
export function getDownloadUrl(fileId: string, type: 'excel' | 'json'): string {
  return `${BASE_URL}/testplan/download/${fileId}/${type}`;
}

// ─── 资源映射 API ─────────────────────────────────────────────

/** 生成资源映射 */
export async function generateResourceMap(
  fileId: string,
  dualSite = false
): Promise<{ status: string; message: string; data: ResourceMapResult }> {
  const formData = new FormData();
  formData.append('file_id', fileId);
  formData.append('dual_site', String(dualSite));
  const response = await fetch(`${BASE_URL}/resource-map/generate`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

// ─── 代码生成相关类型 ─────────────────────────────────────────
export interface CodegenRequest {
  chip_name:    string;
  chip_type:    'digital' | 'ldo' | 'custom';
  test_items:   string[];
  user_prompt:  string;
  pin_names?:   string[];
  input_pins?:  string[];
  output_pins?: string[];
  vcc?:         number;
  vout?:        number;
  ldo_out_pin?: number;
  load_ma?:     number;
}

export interface CodegenResult {
  code:        string;
  filename:    string;
  lines:       number;
  functions:   number;
  chip_name:   string;
  chip_type:   string;
  test_items:  string[];
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
}

export interface TemplateItem {
  id:   string;
  name: string;
  desc: string;
}

export interface TemplatesResult {
  digital: TemplateItem[];
  ldo:     TemplateItem[];
}

/** 生成 STS8200S 测试代码 */
export async function generateCode(req: CodegenRequest): Promise<ApiResponse<CodegenResult>> {
  return request<CodegenResult>(`${BASE_URL}/codegen/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}

/** 获取支持的测试项模板列表 */
export async function getCodeTemplates(): Promise<ApiResponse<TemplatesResult>> {
  return request<TemplatesResult>(`${BASE_URL}/codegen/templates`);
}

// ─── RAG 相关类型 ──────────────────────────────────────────────

export interface RagStatus {
  ready:      boolean;
  doc_count:  number;
  backend:    string;
  index_hash: string;
}

/** 获取 RAG 索引状态 */
export async function getRagStatus(): Promise<ApiResponse<RagStatus>> {
  return request<RagStatus>(`${BASE_URL}/rag/status`);
}

/** 构建 RAG 内置知识库 */
export async function buildRagIndex(pdfPath?: string): Promise<ApiResponse<RagStatus>> {
  return request<RagStatus>(`${BASE_URL}/rag/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pdf_path: pdfPath || null }),
  });
}

// ─── 诊断相关类型 ──────────────────────────────────────────────

export interface AnomalyEvent {
  type:        string;
  confidence:  number;
  description: string;
  severity:    'high' | 'medium' | 'low';
  timestamp:   string;
  channel:     number;
}

export interface WaveformPoint {
  t:    number;
  v:    number;
  i:    number;
  flag: boolean;
}

export interface DiagnosisResult {
  yield_rate:       number;
  yield_trend:      number;
  yield_predicted:  number;
  fty_rolling:      number;
  sample_count:     number;
  anomaly_ratio:    number;
  model_backend:    string;
  analysis_time_ms: number;
  anomalies:        AnomalyEvent[];
  waveform:         WaveformPoint[];
}

export interface DiagnosisRequest {
  n_samples?:      number;
  inject_anomaly?: boolean;
  anomaly_ratio?:  number;
  channel?:        number;
}

/** 运行 ML 良率诊断 */
export async function runDiagnosis(req?: DiagnosisRequest): Promise<ApiResponse<DiagnosisResult>> {
  return request<DiagnosisResult>(`${BASE_URL}/diagnosis/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req || {}),
  });
}

/** 获取实时波形数据 */
export async function getWaveform(nPoints?: number): Promise<ApiResponse<{waveform: WaveformPoint[]; yield_rate: number; anomaly_ratio: number}>> {
  const qs = nPoints ? `?n_points=${nPoints}` : '';
  return request(`${BASE_URL}/diagnosis/waveform${qs}`);
}
