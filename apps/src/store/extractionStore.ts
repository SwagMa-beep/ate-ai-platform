import {
  cancelExtractionTask,
  checkHealth,
  cleanExtractionTasks,
  extractTestplanAsync,
  getPinDefinitions,
  getTaskStatus,
  listExtractionTasks,
  retryExtractionTask,
  uploadPDF,
  type ExtractionResult,
  type PinDefinition,
  type TaskStatusResult,
  type UploadResult,
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
  tasks: TaskStatusResult[];
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
  tasks: [],
};

type Listener = (state: ExtractionState) => void;

class ExtractionStore {
  private state: ExtractionState = { ...INITIAL_STATE };
  private listeners = new Set<Listener>();
  private pollingTimer: number | null = null;

  constructor() {
    this.loadFromSession();
    this.refreshTasks();
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
    } catch (error) {
      console.error('Failed to load extraction state:', error);
    }
  }

  private saveToSession() {
    try {
      sessionStorage.setItem('ate_extraction_store', JSON.stringify(this.state));
    } catch {
      // ignore session persistence errors
    }
  }

  getState() {
    return this.state;
  }

  subscribe(listener: Listener) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  update(patch: Partial<ExtractionState>) {
    this.state = { ...this.state, ...patch };
    this.saveToSession();
    this.listeners.forEach(listener => listener(this.state));
  }

  async refreshTasks(limit = 12) {
    try {
      const response = await listExtractionTasks(limit);
      if (response.status === 'success' && response.data) {
        this.update({ tasks: response.data.items || [] });
      }
    } catch {
      // ignore task refresh failures
    }
  }

  reset() {
    if (this.pollingTimer) {
      clearTimeout(this.pollingTimer);
      this.pollingTimer = null;
    }
    this.update({ ...INITIAL_STATE, tasks: this.state.tasks });
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
          error: health.message || '后端 API 未连接，请检查本地服务是否启动。',
        });
        return;
      }

      const response = await uploadPDF(file);
      if (response.status === 'success' && response.data) {
        const fileInfo = response.data;
        this.update({ fileInfo, progress: 30, message: '文件上传成功，准备提交提取任务...' });
        await this.triggerExtraction(fileInfo.file_id);
      } else {
        this.update({ stage: 'error', error: response.message || '上传失败' });
      }
    } catch (error: any) {
      this.update({ stage: 'error', error: `上传出错: ${error.message}` });
    }
  }

  private async triggerExtraction(fileId: string) {
    this.update({ stage: 'extracting', progress: 35, message: '提交异步提取任务...' });
    try {
      const response = await extractTestplanAsync(fileId);
      if (response.status === 'success' && response.data) {
        const taskId = response.data.task_id;
        this.update({ taskId });
        await this.refreshTasks();
        this.startPolling(taskId);
      } else {
        this.update({ stage: 'error', error: response.message || '任务提交失败' });
      }
    } catch (error: any) {
      this.update({ stage: 'error', error: `提交失败: ${error.message}` });
    }
  }

  private async startPolling(taskId: string) {
    if (this.pollingTimer) clearTimeout(this.pollingTimer);

    const poll = async () => {
      try {
        const response = await getTaskStatus(taskId);
        if (response.status === 'success' && response.data) {
          const task = response.data;
          let currentProgress = task.progress;
          if (currentProgress > 95 && task.status !== 'completed') currentProgress = 95;

          this.update({
            progress: currentProgress,
            message: task.message || 'AI 正在分析 Datasheet...',
          });
          this.refreshTasks();

          if (task.status === 'completed' && task.result) {
            await this.finalizeExtraction(task.result);
          } else if (task.status === 'failed') {
            this.update({ stage: 'error', error: task.message || '后台任务执行失败' });
          } else if (task.status === 'cancelled') {
            this.update({ stage: 'error', error: task.message || '任务已取消' });
          } else {
            this.pollingTimer = window.setTimeout(poll, 2000);
          }
        }
      } catch (error) {
        console.error('Polling failed:', error);
        this.pollingTimer = window.setTimeout(poll, 5000);
      }
    };

    poll();
  }

  private async finalizeExtraction(result: ExtractionResult) {
    this.update({ result, progress: 95, message: '正在加载引脚映射...' });

    let pins: PinDefinition[] = [];
    if (this.state.fileInfo) {
      try {
        const response = await getPinDefinitions(this.state.fileInfo.file_id);
        if (response.status === 'success' && response.data) {
          pins = response.data.pin_definitions;
        }
      } catch {
        // ignore pin loading failures
      }
    }

    this.update({
      stage: 'done',
      progress: 100,
      message: '提取完成',
      result,
      pins,
    });

    if (this.state.fileInfo?.file_id) {
      sessionStorage.setItem('ate_last_file_id', this.state.fileInfo.file_id);
    }
    this.refreshTasks();
  }

  async retryTask(taskId: string) {
    try {
      const response = await retryExtractionTask(taskId);
      if (response.status === 'success' && response.data) {
        this.update({
          stage: 'extracting',
          taskId: response.data.task_id,
          progress: 5,
          message: '已重新提交提取任务...',
          error: '',
        });
        await this.refreshTasks();
        this.startPolling(response.data.task_id);
      }
    } catch (error: any) {
      this.update({ stage: 'error', error: error.message || '重试任务失败' });
    }
  }

  async cancelTask(taskId: string) {
    try {
      const response = await cancelExtractionTask(taskId);
      if (response.status === 'success') {
        if (this.state.taskId === taskId) {
          this.update({ message: '任务取消中...' });
        }
        this.refreshTasks();
      }
    } catch (error: any) {
      this.update({ stage: 'error', error: error.message || '取消任务失败' });
    }
  }

  async cleanTasks(status?: 'completed' | 'failed' | 'cancelled') {
    try {
      await cleanExtractionTasks(status);
      this.refreshTasks();
    } catch (error: any) {
      this.update({ stage: 'error', error: error.message || '清理任务失败' });
    }
  }
}

export const extractionStore = new ExtractionStore();
