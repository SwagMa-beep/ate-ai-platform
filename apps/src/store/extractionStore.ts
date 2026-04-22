import {
  uploadPDF, extractTestplanAsync, getTaskStatus, getPinDefinitions, checkHealth,
  type UploadResult, type ExtractionResult, type PinDefinition
} from '../api/backend';

export type Stage = 'idle' | 'uploading' | 'extracting' | 'done' | 'error';

export interface ExtractionState {
  stage: Stage;
  progress: number;
  message: string;
  fileInfo: UploadResult | null;
  result: ExtractionResult | null;
  pins: PinDefinition[];
  error: string;
  taskId: string | null;
}

export const INITIAL_STATE: ExtractionState = {
  stage: 'idle',
  progress: 0,
  message: '',
  fileInfo: null,
  result: null,
  pins: [],
  error: '',
  taskId: null,
};

type Listener = (state: ExtractionState) => void;

class ExtractionStore {
  private state: ExtractionState = { ...INITIAL_STATE };
  private listeners = new Set<Listener>();
  private pollingTimer: number | null = null;

  constructor() {
    this.loadFromSession();
    // 如果有未完成的任务，尝试恢复轮询
    if (this.state.stage === 'extracting' && this.state.taskId) {
      this.startPolling(this.state.taskId);
    }
  }

  private loadFromSession() {
    try {
      const saved = sessionStorage.getItem('ate_extraction_store');
      if (saved) {
        const data = JSON.parse(saved);
        this.state = { ...this.state, ...data };
      }
    } catch (e) {
      console.error('Failed to load extraction state:', e);
    }
  }

  private saveToSession() {
    try {
      sessionStorage.setItem('ate_extraction_store', JSON.stringify(this.state));
    } catch (e) {}
  }

  getState() {
    return this.state;
  }

  subscribe(listener: Listener) {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  update(patch: Partial<ExtractionState>) {
    this.state = { ...this.state, ...patch };
    this.saveToSession();
    this.listeners.forEach(l => l(this.state));
  }

  reset() {
    if (this.pollingTimer) {
      clearTimeout(this.pollingTimer);
      this.pollingTimer = null;
    }
    this.update(INITIAL_STATE);
    sessionStorage.removeItem('ate_extraction_store');
  }

  async startUpload(file: File) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      this.update({ stage: 'error', error: '只支持 PDF 格式文件' });
      return;
    }

    this.update({ stage: 'uploading', progress: 10, message: '正在上传文件...', error: '' });

    try {
      const health = await checkHealth();
      if (health.status !== 'success' || !health.data) {
        this.update({
          stage: 'error',
          error: health.message || '后端 API 未连接，请重新打开应用或检查本机防火墙/杀毒软件是否拦截 backend-server.exe',
        });
        return;
      }

      const res = await uploadPDF(file);
      if (res.status === 'success' && res.data) {
        const fileInfo = res.data;
        this.update({ fileInfo, progress: 30, message: '文件上传成功，准备解析...' });
        await this.triggerExtraction(fileInfo.file_id);
      } else {
        this.update({ stage: 'error', error: res.message || '上传失败' });
      }
    } catch (e: any) {
      this.update({ stage: 'error', error: `上传出错: ${e.message}` });
    }
  }

  private async triggerExtraction(fileId: string) {
    this.update({ stage: 'extracting', progress: 35, message: '提交异步提取任务...' });
    try {
      const res = await extractTestplanAsync(fileId);
      if (res.status === 'success' && res.data) {
        const taskId = res.data.task_id;
        this.update({ taskId });
        this.startPolling(taskId);
      } else {
        this.update({ stage: 'error', error: res.message || '任务提交失败' });
      }
    } catch (e: any) {
      this.update({ stage: 'error', error: `提交失败: ${e.message}` });
    }
  }

  private async startPolling(taskId: string) {
    if (this.pollingTimer) clearTimeout(this.pollingTimer);

    const poll = async () => {
      try {
        const res = await getTaskStatus(taskId);
        if (res.status === 'success' && res.data) {
          const task = res.data;
          
          let currentProgress = task.progress;
          // 防止 UI 停留在 100% 却没拿到结果的尴尬
          if (currentProgress > 95 && task.status !== 'completed') currentProgress = 95;

          this.update({ 
            progress: currentProgress, 
            message: task.message || 'AI 正在深度分析中...' 
          });

          if (task.status === 'completed' && task.result) {
            await this.finalizeExtraction(task.result);
          } else if (task.status === 'failed') {
            this.update({ stage: 'error', error: task.message || '后台任务执行失败' });
          } else {
            // 继续轮询
            this.pollingTimer = window.setTimeout(poll, 2000);
          }
        }
      } catch (e: any) {
        console.error('Polling failed:', e);
        this.pollingTimer = window.setTimeout(poll, 5000); // 报错则放慢频率
      }
    };

    poll();
  }

  private async finalizeExtraction(result: ExtractionResult) {
    this.update({ result, progress: 95, message: '正在加载引脚映射...' });
    
    let pins: PinDefinition[] = [];
    if (this.state.fileInfo) {
      try {
        const res = await getPinDefinitions(this.state.fileInfo.file_id);
        if (res.status === 'success' && res.data) {
          pins = res.data.pin_definitions;
        }
      } catch (e) {}
    }

    this.update({ 
      stage: 'done', 
      progress: 100, 
      message: '提取完成', 
      result, 
      pins 
    });

    // ✅ 关键修复：将成功提取的 file_id 持久化到 sessionStorage，供模块二和模块三自动检测
    if (this.state.fileInfo?.file_id) {
      sessionStorage.setItem('ate_last_file_id', this.state.fileInfo.file_id);
    }
  }
}

export const extractionStore = new ExtractionStore();
