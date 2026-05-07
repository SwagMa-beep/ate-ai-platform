import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Bot,
  BrainCircuit,
  DatabaseZap,
  ImagePlus,
  Loader2,
  RefreshCw,
  Send,
  UserRound,
  Workflow,
  X,
} from 'lucide-react';
import {
  getWorkspaceMemory,
  listAgentRuns,
  resetWorkspaceMemory,
  sendEngineerAssistantMessage,
  type AgentRunResult,
  type AssistantChatResult,
  type AssistantMode,
  type WorkspaceMemory,
} from '../api/backend';
import { Card } from '../components/common/Card';

const MAX_IMAGES = 5;
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const ACCEPTED_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);

type PendingImage = {
  id: string;
  file: File;
  previewUrl: string;
};

type UIMessage =
  | { id: string; role: 'user'; text: string; images: PendingImage[] }
  | { id: string; role: 'assistant'; result: AssistantChatResult }
  | { id: string; role: 'loading'; text: string }
  | { id: string; role: 'error'; text: string };

const modeOptions: Array<{ key: AssistantMode; label: string }> = [
  { key: 'general', label: '综合' },
  { key: 'testplan', label: 'TestPlan' },
  { key: 'resource-map', label: '资源映射' },
  { key: 'codegen', label: '代码生成' },
  { key: 'diagnosis', label: '良率诊断' },
  { key: 'run-analysis', label: '运行分析' },
];

const promptTemplates: Record<AssistantMode, string> = {
  general: '请结合当前上下文分析下一步。',
  testplan: '请分析这次 TestPlan 结果的主要风险。',
  'resource-map': '请检查最近一次资源映射的主要风险。',
  codegen: '请分析最近一次代码生成最值得优先处理的问题。',
  diagnosis: '请分析最近一次诊断最值得优先检查的异常来源。',
  'run-analysis': '请分析最近一次 run 当前卡点和下一步动作。',
};

function hasMemory(memory: WorkspaceMemory | null) {
  if (!memory) return false;
  return Boolean(
    memory.current_chip.name ||
      memory.recent_testplan.summary ||
      memory.recent_resource_map.summary ||
      memory.recent_codegen.summary ||
      memory.recent_failure_topic.summary,
  );
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function CompactRow({ label, value }: { label: string; value?: string }) {
  return (
    <div className="rounded-xl border border-outline-variant/10 bg-surface px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.2em] text-on-surface-variant/50">{label}</div>
      <div className="mt-1 text-sm text-on-surface-variant/85">{value || '未记录'}</div>
    </div>
  );
}

export function EngineerAssistantPage() {
  const [mode, setMode] = useState<AssistantMode>('general');
  const [prompt, setPrompt] = useState(promptTemplates.general);
  const [memory, setMemory] = useState<WorkspaceMemory | null>(null);
  const [runs, setRuns] = useState<AgentRunResult[]>([]);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [images, setImages] = useState<PendingImage[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const imagesRef = useRef<PendingImage[]>([]);

  const selectedModeMeta = useMemo(() => modeOptions.find(item => item.key === mode) || modeOptions[0], [mode]);

  useEffect(() => {
    requestAnimationFrame(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }));
  }, [messages]);

  useEffect(() => {
    imagesRef.current = images;
  }, [images]);

  useEffect(
    () => () => {
      imagesRef.current.forEach(image => URL.revokeObjectURL(image.previewUrl));
    },
    [],
  );

  async function loadContext() {
    setRefreshing(true);
    try {
      const [memoryRes, runsRes] = await Promise.all([getWorkspaceMemory(), listAgentRuns(8)]);
      setMemory(memoryRes.data);
      setRuns(runsRes.data?.items || []);
      if (!selectedRunId && runsRes.data?.items?.length) {
        setSelectedRunId(runsRes.data.items[0].run_id);
      }
    } catch (err: any) {
      setError(err?.message || '加载失败');
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void loadContext();
  }, []);

  useEffect(() => {
    setPrompt(promptTemplates[mode]);
  }, [mode]);

  function handleFiles(files: FileList | null) {
    if (!files) return;
    setError('');
    const next: PendingImage[] = [];
    for (const file of Array.from(files)) {
      if (images.length + next.length >= MAX_IMAGES) {
        setError(`最多 ${MAX_IMAGES} 张图片`);
        break;
      }
      if (!ACCEPTED_TYPES.has(file.type)) {
        setError(`不支持：${file.name}`);
        continue;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        setError(`超过 10MB：${file.name}`);
        continue;
      }
      next.push({
        id: `${file.name}_${file.lastModified}_${Math.random().toString(16).slice(2)}`,
        file,
        previewUrl: URL.createObjectURL(file),
      });
    }
    setImages(prev => [...prev, ...next]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function removeImage(id: string) {
    setImages(prev => {
      const target = prev.find(image => image.id === id);
      if (target) URL.revokeObjectURL(target.previewUrl);
      return prev.filter(image => image.id !== id);
    });
  }

  async function handleAsk() {
    if (!prompt.trim() && images.length === 0) {
      setError('请输入问题或上传图片');
      return;
    }

    setLoading(true);
    setError('');
    const sendingImages = images;
    const userMessage: UIMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      text: prompt.trim(),
      images: sendingImages,
    };
    const loadingMessage: UIMessage = {
      id: `loading_${Date.now()}`,
      role: 'loading',
      text: '分析中...',
    };
    setMessages(prev => [...prev, userMessage, loadingMessage]);
    setPrompt('');
    setImages([]);

    try {
      const response = await sendEngineerAssistantMessage({
        message: userMessage.text,
        mode,
        run_id: selectedRunId || undefined,
        images: sendingImages.map(image => image.file),
      });
      const assistantMessage: UIMessage = {
        id: `assistant_${Date.now()}`,
        role: 'assistant',
        result: response.data as AssistantChatResult,
      };
      setMessages(prev => [...prev.filter(item => item.id !== loadingMessage.id), assistantMessage]);
      const memoryRes = await getWorkspaceMemory();
      setMemory(memoryRes.data);
      sendingImages.forEach(image => URL.revokeObjectURL(image.previewUrl));
    } catch (err: any) {
      setMessages(prev => [
        ...prev.filter(item => item.id !== loadingMessage.id),
        { id: `error_${Date.now()}`, role: 'error', text: err?.message || '调用失败' },
      ]);
      setError(err?.message || '调用失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleResetMemory() {
    setResetting(true);
    setError('');
    try {
      const response = await resetWorkspaceMemory();
      setMemory(response.data);
    } catch (err: any) {
      setError(err?.message || '清空失败');
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="space-y-5">
      <Card
        title="工程师助手"
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void loadContext()}
              className="inline-flex items-center gap-2 rounded-xl border border-outline-variant/20 bg-surface-container px-3 py-2 text-sm text-on-surface-variant transition hover:border-primary/20 hover:text-on-surface"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              刷新
            </button>
            <button
              type="button"
              onClick={() => void handleResetMemory()}
              className="inline-flex items-center gap-2 rounded-xl border border-outline-variant/20 bg-surface-container px-3 py-2 text-sm text-on-surface-variant transition hover:border-primary/20 hover:text-on-surface"
            >
              <DatabaseZap className="h-4 w-4" />
              {resetting ? '清空中' : '清空记忆'}
            </button>
          </div>
        }
      >
        <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div className="space-y-4">
            <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
              <div className="mb-3 flex flex-wrap gap-2">
                {modeOptions.map(item => {
                  const active = item.key === mode;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setMode(item.key)}
                      className={`rounded-full px-3 py-2 text-xs transition ${
                        active
                          ? 'bg-primary text-surface'
                          : 'border border-outline-variant/12 bg-surface text-on-surface-variant hover:text-on-surface'
                      }`}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-on-surface">
                  <BrainCircuit className="h-4 w-4 text-primary" />
                  {selectedModeMeta.label}
                </div>

                <select
                  value={selectedRunId}
                  onChange={event => setSelectedRunId(event.target.value)}
                  className="w-full rounded-2xl border border-outline-variant/15 bg-surface px-4 py-3 text-sm text-on-surface outline-none transition focus:border-primary/30"
                >
                  <option value="">最近 run</option>
                  {runs.map(run => (
                    <option key={run.run_id} value={run.run_id}>
                      {run.flow_name} / {run.status} / {run.run_id.slice(0, 8)}
                    </option>
                  ))}
                </select>

                <textarea
                  value={prompt}
                  onChange={event => setPrompt(event.target.value)}
                  rows={6}
                  className="w-full rounded-2xl border border-outline-variant/15 bg-surface px-4 py-3 text-sm text-on-surface outline-none transition focus:border-primary/30"
                  placeholder="输入问题..."
                />

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  multiple
                  className="hidden"
                  onChange={event => handleFiles(event.target.files)}
                />

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl border border-outline-variant/15 bg-surface px-4 py-3 text-sm text-on-surface transition hover:border-primary/25"
                  >
                    <ImagePlus className="h-4 w-4" />
                    图片
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleAsk()}
                    disabled={loading}
                    className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-surface transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    发送
                  </button>
                </div>
              </div>

              {images.length > 0 ? (
                <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
                  {images.map(image => (
                    <div key={image.id} className="relative w-24 shrink-0 overflow-hidden rounded-xl border border-outline-variant/15 bg-surface">
                      <img src={image.previewUrl} alt={image.file.name} className="h-16 w-24 object-cover" />
                      <button
                        type="button"
                        onClick={() => removeImage(image.id)}
                        className="absolute right-1 top-1 rounded-full bg-surface/80 p-1 text-on-surface hover:bg-error hover:text-white"
                      >
                        <X className="h-3 w-3" />
                      </button>
                      <div className="px-2 py-1 text-[9px] text-on-surface-variant/60">{formatBytes(image.file.size)}</div>
                    </div>
                  ))}
                </div>
              ) : null}

              {error ? (
                <div className="mt-3 rounded-xl border border-error/25 bg-error/10 px-3 py-2 text-sm text-error">{error}</div>
              ) : null}
            </div>

            <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-on-surface">
                <Workflow className="h-4 w-4 text-primary" />
                上下文
              </div>
              {hasMemory(memory) ? (
                <div className="space-y-2">
                  <CompactRow
                    label="Chip"
                    value={
                      memory?.current_chip.name
                        ? `${memory.current_chip.name}${memory.current_chip.chip_type ? ` / ${memory.current_chip.chip_type}` : ''}`
                        : ''
                    }
                  />
                  <CompactRow label="TestPlan" value={memory?.recent_testplan.summary} />
                  <CompactRow label="ResourceMap" value={memory?.recent_resource_map.summary} />
                  <CompactRow label="Codegen" value={memory?.recent_codegen.summary} />
                  <CompactRow label="Diagnosis" value={memory?.recent_failure_topic.summary} />
                </div>
              ) : (
                <div className="text-sm text-on-surface-variant/70">暂无上下文</div>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-on-surface">
              <Bot className="h-4 w-4 text-primary" />
              对话
            </div>
            <div className="max-h-[760px] space-y-4 overflow-y-auto pr-1">
              {messages.length === 0 ? (
                <div className="rounded-2xl border border-outline-variant/12 bg-surface px-4 py-5 text-sm text-on-surface-variant/70">
                  等待输入
                </div>
              ) : (
                messages.map(message => {
                  if (message.role === 'user') {
                    return (
                      <div key={message.id} className="flex justify-end gap-3">
                        <div className="max-w-[78%] space-y-2">
                          <div className="rounded-2xl border border-primary/20 bg-primary/10 px-4 py-3 text-sm leading-7 text-on-surface">
                            {message.text || '图片请求'}
                          </div>
                          {message.images.length ? (
                            <div className="flex flex-wrap gap-2">
                              {message.images.map(image => (
                                <img
                                  key={image.id}
                                  src={image.previewUrl}
                                  alt={image.file.name}
                                  className="h-24 w-32 rounded-xl border border-outline-variant/12 object-cover"
                                />
                              ))}
                            </div>
                          ) : null}
                        </div>
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                          <UserRound className="h-5 w-5 text-primary" />
                        </div>
                      </div>
                    );
                  }

                  if (message.role === 'loading') {
                    return (
                      <div key={message.id} className="flex gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-secondary/10">
                          <Bot className="h-5 w-5 text-secondary" />
                        </div>
                        <div className="flex items-center gap-2 rounded-2xl border border-outline-variant/12 bg-surface px-4 py-3 text-sm text-on-surface-variant/75">
                          <Loader2 className="h-4 w-4 animate-spin text-primary" />
                          {message.text}
                        </div>
                      </div>
                    );
                  }

                  if (message.role === 'error') {
                    return (
                      <div key={message.id} className="rounded-2xl border border-error/25 bg-error/10 px-4 py-3 text-sm text-error">
                        {message.text}
                      </div>
                    );
                  }

                  return (
                    <div key={message.id} className="space-y-4 rounded-2xl border border-outline-variant/12 bg-surface px-4 py-4">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 text-sm font-semibold text-on-surface">
                          <Bot className="h-4 w-4 text-primary" />
                          回复
                        </div>
                        <div className="text-xs text-on-surface-variant/60">
                          {message.result.model_backend === 'vision' ? '视觉' : '文本'}
                        </div>
                      </div>

                      <div className="whitespace-pre-wrap text-sm leading-7 text-on-surface-variant/90">
                        {message.result.answer}
                      </div>

                      {message.result.suggested_actions.length ? (
                        <div className="space-y-2">
                          {message.result.suggested_actions.map(action => (
                            <div key={action} className="rounded-xl border border-outline-variant/12 bg-surface-container px-4 py-3 text-sm text-on-surface-variant/85">
                              {action}
                            </div>
                          ))}
                        </div>
                      ) : null}

                      {message.result.retrieved_chunks.length ? (
                        <div className="space-y-3">
                          {message.result.retrieved_chunks.map(chunk => (
                            <div key={`${chunk.source}-${chunk.text.slice(0, 20)}`} className="rounded-xl border border-outline-variant/12 bg-surface-container px-4 py-3">
                              <div className="flex items-center justify-between gap-3 text-xs text-on-surface-variant/60">
                                <span>{chunk.source || 'RAG'}</span>
                                <span>score {typeof chunk.score === 'number' ? chunk.score.toFixed(3) : chunk.score}</span>
                              </div>
                              <div className="mt-2 text-sm leading-7 text-on-surface-variant/85">{chunk.text}</div>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
