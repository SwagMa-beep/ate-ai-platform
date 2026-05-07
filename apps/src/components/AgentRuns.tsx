import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Boxes, Clock3, Loader2, RefreshCw, Sparkles, Workflow } from 'lucide-react';
import {
  createFullAteRunAsync,
  getAgentRun,
  getAgentRunArtifact,
  getAgentRunArtifacts,
  listAgentRuns,
  uploadPDF,
  type AgentRunArtifact,
  type AgentRunResult,
} from '../api/backend';
import { getArtifactLabel, getFlowLabel, getRunStatusPresentation, getStepLabel } from '../utils/runPresentation';

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-3 text-[10px] font-bold uppercase tracking-[0.2em] text-on-surface-variant">{children}</h3>;
}

function getStoredFileId() {
  if (typeof window === 'undefined') return '';
  try {
    return window.sessionStorage.getItem('ate_last_file_id') || '';
  } catch {
    return '';
  }
}

function persistFileId(fileId: string) {
  if (typeof window === 'undefined' || !fileId) return;
  try {
    window.sessionStorage.setItem('ate_last_file_id', fileId);
  } catch {
    // ignore storage failures
  }
}

type ReviewSummary = {
  overall_status?: string;
  risk_level?: string;
  summary?: string;
  must_review_items?: string[];
  recommendations?: string[];
};

function getRouteBadge(run: AgentRunResult) {
  if (run.triggered_by?.startsWith('agent_revision:')) {
    return { label: 'AI 自动修复', tone: 'text-secondary bg-secondary/10 border-secondary/20' };
  }
  if (run.flow_name === 'post_review_revision') {
    return { label: '打回路由', tone: 'text-tertiary bg-tertiary/10 border-tertiary/20' };
  }
  if (run.flow_name === 'post_review_delivery') {
    return { label: '批准后续流程', tone: 'text-primary bg-primary/10 border-primary/20' };
  }
  if (run.triggered_by === 'approval' || run.triggered_by === 'human_review_approval') {
    return { label: '批准链路', tone: 'text-primary bg-primary/10 border-primary/20' };
  }
  if (run.triggered_by?.startsWith('human_review_rejection:')) {
    return { label: '打回链路', tone: 'text-accent bg-accent/10 border-accent/20' };
  }
  return null;
}

function getReviewRoutingSummary(run: AgentRunResult | null) {
  const decision = run?.review_decision;
  if (!decision?.rejection_type) return null;
  if (decision.rejection_type === 'input_issue') {
    return '当前属于输入问题，需要用户替换文档或补充缺失输入。';
  }
  if (decision.rejection_type === 'engineering_decision') {
    return '当前属于工程决策问题，需要工程师补充约束或明确测试范围。';
  }
  return '当前属于可自动修复问题，系统会基于复核意见和现有证据自动再跑一轮。';
}

function getRejectionTypeLabel(value?: string) {
  if (value === 'input_issue') return '输入问题';
  if (value === 'engineering_decision') return '工程决策问题';
  if (value === 'auto_fixable') return '可自动修复';
  return '未分类';
}

function getResolutionOwnerLabel(value?: string) {
  if (value === 'agent') return 'AI 自动修复';
  if (value === 'user') return '用户/工程师补充';
  return '待定';
}

function readReviewSummary(run: AgentRunResult | null): ReviewSummary | null {
  const shared = run?.shared as Record<string, unknown> | undefined;
  const review = shared?.review;
  return review && typeof review === 'object' ? (review as ReviewSummary) : null;
}

function getStepMetaNumber(step: AgentRunResult['steps'][number], key: string) {
  const value = step.metadata?.[key];
  return typeof value === 'number' ? value : 0;
}

function sanitizeDetailText(text: string | undefined, fallback: string) {
  if (!text) return fallback;
  if (/\?{3,}/.test(text)) return fallback;
  return text;
}

function isRunActive(status?: string) {
  return status === 'running' || status === 'processing' || status === 'pending';
}

export function AgentRuns() {
  const [runs, setRuns] = useState<AgentRunResult[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<AgentRunResult | null>(null);
  const [comparisonRun, setComparisonRun] = useState<AgentRunResult | null>(null);
  const [selectedArtifacts, setSelectedArtifacts] = useState<AgentRunArtifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');

  const [selectedArtifactName, setSelectedArtifactName] = useState<string | null>(null);
  const [selectedArtifactDetail, setSelectedArtifactDetail] = useState<AgentRunArtifact | null>(null);
  const [artifactLoading, setArtifactLoading] = useState(false);
  const [artifactError, setArtifactError] = useState('');

  const [createError, setCreateError] = useState('');
  const [creating, setCreating] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fullGoal, setFullGoal] = useState(
    '根据当前 Datasheet 串联提取、资源映射、RAG、代码生成、工程复核与工程打包，输出可复核的 STS8200S 开发结果。',
  );
  const [fullFileId, setFullFileId] = useState(getStoredFileId());
  const [exportPackage, setExportPackage] = useState(true);

  const loadRuns = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await listAgentRuns(20);
      if (response.status === 'success' && response.data) {
        const nextRuns = response.data.items || [];
        setRuns(nextRuns);
        setSelectedRunId(current => {
          if (current && nextRuns.some(run => run.run_id === current)) return current;
          return nextRuns[0]?.run_id || null;
        });
      } else {
        setRuns([]);
        setError(response.message || '未能加载运行记录');
      }
    } catch (loadError) {
      setRuns([]);
      setError(loadError instanceof Error ? loadError.message : '未能加载运行记录');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadRuns();
  }, []);

  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRun(null);
      setSelectedArtifacts([]);
      setSelectedArtifactName(null);
      setSelectedArtifactDetail(null);
      setArtifactError('');
      return;
    }

    let cancelled = false;
    setDetailLoading(true);
    setSelectedArtifactName(null);
    setSelectedArtifactDetail(null);
    setArtifactError('');

    Promise.all([getAgentRun(selectedRunId), getAgentRunArtifacts(selectedRunId)])
      .then(([runResponse, artifactResponse]) => {
        if (cancelled) return;
        setSelectedRun(runResponse.status === 'success' && runResponse.data ? runResponse.data : null);
        setSelectedArtifacts(artifactResponse.status === 'success' && artifactResponse.data ? artifactResponse.data.artifacts || [] : []);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedRunId]);

  useEffect(() => {
    if (!selectedRunId || !selectedArtifactName) {
      setSelectedArtifactDetail(null);
      setArtifactError('');
      return;
    }

    let cancelled = false;
    setArtifactLoading(true);
    setArtifactError('');

    getAgentRunArtifact(selectedRunId, selectedArtifactName)
      .then(response => {
        if (cancelled) return;
        if (response.status === 'success' && response.data?.artifact) {
          setSelectedArtifactDetail(response.data.artifact);
        } else {
          setSelectedArtifactDetail(null);
          setArtifactError(response.message || '未能加载产物详情');
        }
      })
      .catch(loadError => {
        if (cancelled) return;
        setSelectedArtifactDetail(null);
        setArtifactError(loadError instanceof Error ? loadError.message : '未能加载产物详情');
      })
      .finally(() => {
        if (!cancelled) setArtifactLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedRunId, selectedArtifactName]);

  useEffect(() => {
    const shouldCompare = !!selectedRun?.triggered_by?.startsWith('agent_revision:');
    const sourceRunId = selectedRun?.review_source_run_id;
    if (!shouldCompare || !sourceRunId) {
      setComparisonRun(null);
      return;
    }

    const existing = runs.find(run => run.run_id === sourceRunId);
    if (existing) {
      setComparisonRun(existing);
      return;
    }

    let cancelled = false;
    getAgentRun(sourceRunId)
      .then(response => {
        if (!cancelled && response.status === 'success' && response.data) {
          setComparisonRun(response.data);
        }
      })
      .catch(() => {
        if (!cancelled) setComparisonRun(null);
      });

    return () => {
      cancelled = true;
    };
  }, [runs, selectedRun]);

  useEffect(() => {
    if (!selectedRunId || !selectedRun || !isRunActive(selectedRun.status)) return;

    let cancelled = false;
    let timer: number | undefined;

    const pollSelectedRun = async () => {
      try {
        const response = await getAgentRun(selectedRunId);
        if (cancelled || response.status !== 'success' || !response.data) return;

        const nextRun = response.data;
        setSelectedRun(nextRun);
        setRuns(current => [nextRun, ...current.filter(item => item.run_id !== nextRun.run_id)]);

        if (isRunActive(nextRun.status)) {
          timer = window.setTimeout(pollSelectedRun, 1500);
          return;
        }

        void getAgentRunArtifacts(selectedRunId).then(artifactResponse => {
          if (!cancelled && artifactResponse.status === 'success' && artifactResponse.data) {
            setSelectedArtifacts(artifactResponse.data.artifacts || []);
          }
        });
      } catch {
        if (!cancelled) {
          timer = window.setTimeout(pollSelectedRun, 3000);
        }
      }
    };

    timer = window.setTimeout(pollSelectedRun, 1200);
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [selectedRunId, selectedRun]);

  const summary = useMemo(
    () => ({
      total: runs.length,
      completed: runs.filter(run => run.status === 'completed').length,
      attention: runs.filter(run => ['failed', 'human_review_required', 'warning'].includes(run.status)).length,
    }),
    [runs],
  );

  const reviewSummary = useMemo(() => readReviewSummary(selectedRun), [selectedRun]);
  const comparisonReviewSummary = useMemo(() => readReviewSummary(comparisonRun), [comparisonRun]);

  const handleCreateFullRun = async () => {
    if (!fullGoal.trim()) {
      setCreateError('请先填写全链路目标。');
      return;
    }

    setCreating(true);
    setCreateError('');
    try {
      let resolvedFileId = fullFileId.trim();

      if (selectedFile) {
        const uploadResponse = await uploadPDF(selectedFile);
        if (uploadResponse.status !== 'success' || !uploadResponse.data?.file_id) {
          setCreateError(uploadResponse.message || 'Datasheet 上传失败，未能创建全链路运行。');
          return;
        }
        resolvedFileId = uploadResponse.data.file_id;
        setFullFileId(resolvedFileId);
        persistFileId(resolvedFileId);
      }

      if (!resolvedFileId) {
        setCreateError('请先选择 Datasheet PDF，或填写已有上传文件的 file_id。');
        return;
      }

      const response = await createFullAteRunAsync({
        flow_name: 'full_ate_development',
        goal: fullGoal.trim(),
        file_id: resolvedFileId,
        export_package: exportPackage,
      });
      if (response.status === 'success' && response.data) {
        setRuns(current => [response.data!, ...current.filter(run => run.run_id !== response.data!.run_id)]);
        setSelectedRunId(response.data.run_id);
        setSelectedRun(response.data);
        setSelectedArtifacts([]);
        setSelectedFile(null);
        await loadRuns();
      } else {
        setCreateError(response.message || '创建全链路运行失败');
      }
    } catch (createRunError) {
      setCreateError(createRunError instanceof Error ? createRunError.message : '创建全链路运行失败');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-500">
      <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-6 shadow-sm">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_380px]">
          <div>
            <div className="mb-2 flex items-center gap-2 text-primary">
              <Workflow className="h-5 w-5" />
              <span className="text-xs font-bold uppercase tracking-[0.25em]">运行总览</span>
            </div>
            <h1 className="font-headline text-3xl font-bold text-on-surface">运行中心</h1>
            <div className="mt-5 grid gap-3 md:grid-cols-3">
              <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">总记录数</div>
                <div className="mt-2 font-headline text-3xl font-bold text-primary">{summary.total}</div>
              </div>
              <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">已完成</div>
                <div className="mt-2 font-headline text-3xl font-bold text-secondary">{summary.completed}</div>
              </div>
              <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">需关注</div>
                <div className="mt-2 font-headline text-3xl font-bold text-accent">{summary.attention}</div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-primary/15 bg-primary/5 p-5">
            <div className="mb-3 flex items-center gap-2 text-primary">
              <Sparkles className="h-4 w-4" />
              <span className="text-xs font-bold uppercase tracking-[0.2em]">Full Flow</span>
            </div>
            <h2 className="text-lg font-semibold text-on-surface">创建全链路运行</h2>
            <div className="mt-4 space-y-3">
              <label className="block">
                <div className="mb-1.5 text-[11px] font-semibold text-on-surface-variant/70">目标说明</div>
                <textarea
                  value={fullGoal}
                  onChange={event => setFullGoal(event.target.value)}
                  rows={4}
                  className="w-full rounded-xl border border-outline-variant/20 bg-surface px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/30"
                  placeholder="例如：根据当前 Datasheet 生成 STS8200S 测试工程，并给出风险复核结论。"
                />
              </label>

              <label className="block">
                <div className="mb-1.5 text-[11px] font-semibold text-on-surface-variant/70">Datasheet PDF</div>
                <label className="flex cursor-pointer items-center justify-between rounded-xl border border-dashed border-outline-variant/20 bg-surface px-3 py-3 text-sm text-on-surface-variant">
                  <span>{selectedFile ? selectedFile.name : '选择 PDF'}</span>
                  <input
                    type="file"
                    accept=".pdf"
                    className="hidden"
                    disabled={creating}
                    onChange={event => setSelectedFile(event.target.files?.[0] || null)}
                  />
                  <span className="rounded-lg bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary">选择文件</span>
                </label>
              </label>

              <label className="block">
                <div className="mb-1.5 text-[11px] font-semibold text-on-surface-variant/70">文件 ID</div>
                <input
                  value={fullFileId}
                  onChange={event => setFullFileId(event.target.value)}
                  className="w-full rounded-xl border border-outline-variant/20 bg-surface px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/30"
                  placeholder="优先填写模块上传后返回的 file_id"
                />
              </label>

              <label className="flex items-center gap-2 rounded-xl border border-outline-variant/10 bg-surface px-3 py-2 text-sm text-on-surface">
                <input
                  type="checkbox"
                  checked={exportPackage}
                  onChange={event => setExportPackage(event.target.checked)}
                  className="accent-[var(--color-primary)]"
                />
                同时导出工程包
              </label>

              {createError ? (
                <div className="rounded-xl border border-error/20 bg-error/5 px-3 py-2 text-sm text-error">{createError}</div>
              ) : null}

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => void handleCreateFullRun()}
                  disabled={creating}
                  className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-bold text-surface transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Workflow className="h-4 w-4" />}
                  创建全链路运行
                </button>
                <button
                  type="button"
                  onClick={() => void loadRuns()}
                  className="inline-flex items-center gap-2 rounded-xl border border-primary/20 bg-primary/10 px-4 py-2 text-sm font-bold text-primary transition hover:bg-primary/15"
                >
                  <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  刷新记录
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-sm">
          <SectionTitle>最近记录</SectionTitle>
          {loading ? (
            <div className="flex items-center gap-3 rounded-xl border border-outline-variant/10 bg-surface-container px-4 py-6 text-sm text-on-surface-variant">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              正在加载运行记录...
            </div>
          ) : error ? (
            <div className="rounded-xl border border-error/20 bg-error/5 px-4 py-4 text-sm text-error">{error}</div>
          ) : runs.length === 0 ? (
            <div className="rounded-xl border border-outline-variant/10 bg-surface-container px-4 py-6 text-sm text-on-surface-variant">
              当前还没有可展示的运行记录。
            </div>
          ) : (
            <div className="space-y-3">
              {runs.map(run => {
                const doneSteps = run.steps.filter(step => step.status === 'completed').length;
                const status = getRunStatusPresentation(run.status);
                const routeBadge = getRouteBadge(run);
                return (
                  <button
                    key={run.run_id}
                    type="button"
                    onClick={() => setSelectedRunId(run.run_id)}
                    className={`w-full rounded-xl border px-4 py-3 text-left transition ${
                      selectedRunId === run.run_id
                        ? 'border-primary/30 bg-primary/5'
                        : 'border-outline-variant/10 bg-surface-container hover:border-primary/20 hover:bg-primary/5'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="font-mono text-[11px] font-bold text-on-surface">{run.run_id}</div>
                        <div className="mt-1 text-[11px] text-on-surface-variant/70">{getFlowLabel(run.flow_name)}</div>
                      </div>
                      <span className={`rounded-md border px-2 py-0.5 text-[9px] font-bold ${status.tone}`}>{status.label}</span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5 text-[10px] text-on-surface-variant/70">
                      <span className="rounded-md bg-surface px-2 py-0.5">阶段 {run.steps.length}</span>
                      <span className="rounded-md bg-surface px-2 py-0.5">完成 {doneSteps}</span>
                      <span className="rounded-md bg-surface px-2 py-0.5">产物 {run.artifacts.length}</span>
                      {routeBadge ? <span className={`rounded-md border px-2 py-0.5 ${routeBadge.tone}`}>{routeBadge.label}</span> : null}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-sm">
          <SectionTitle>流程详情</SectionTitle>
          {!selectedRunId ? (
            <div className="rounded-xl border border-outline-variant/10 bg-surface-container px-4 py-6 text-sm text-on-surface-variant">
              先从左侧选择一条运行记录，再查看这次流程经历了哪些阶段。
            </div>
          ) : detailLoading ? (
            <div className="flex items-center gap-3 rounded-xl border border-outline-variant/10 bg-surface-container px-4 py-6 text-sm text-on-surface-variant">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              正在加载流程详情...
            </div>
          ) : !selectedRun ? (
            <div className="rounded-xl border border-tertiary/20 bg-tertiary/5 px-4 py-6 text-sm text-tertiary">
              这条记录当前不可用，请稍后重试。
            </div>
          ) : (
            <div className="space-y-4">
              {getRouteBadge(selectedRun) ? (
                <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-md border px-2.5 py-1 text-[10px] font-bold ${getRouteBadge(selectedRun)?.tone}`}>
                      {getRouteBadge(selectedRun)?.label}
                    </span>
                    {selectedRun.review_decision?.rejection_type ? (
                      <span className="rounded-md border border-outline-variant/15 bg-surface px-2.5 py-1 text-[10px] font-semibold text-on-surface-variant">
                        问题类型：{getRejectionTypeLabel(selectedRun.review_decision.rejection_type)}
                      </span>
                    ) : null}
                    {selectedRun.review_decision?.resolution_owner ? (
                      <span className="rounded-md border border-outline-variant/15 bg-surface px-2.5 py-1 text-[10px] font-semibold text-on-surface-variant">
                        处理责任：{getResolutionOwnerLabel(selectedRun.review_decision.resolution_owner)}
                      </span>
                    ) : null}
                  </div>
                  {getReviewRoutingSummary(selectedRun) ? (
                    <div className="mt-2 text-xs text-on-surface-variant/75">{getReviewRoutingSummary(selectedRun)}</div>
                  ) : null}
                </div>
              ) : null}

              {selectedRun.triggered_by?.startsWith('agent_revision:') && comparisonRun ? (
                <div className="rounded-xl border border-secondary/20 bg-secondary/5 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-[10px] font-bold uppercase tracking-widest text-secondary/80">修复前后对比</div>
                      <div className="mt-1 text-sm font-semibold text-on-surface">当前正在查看 AI 自动修复后的运行结果</div>
                      <div className="mt-1 text-xs text-on-surface-variant/75">原始被打回 Run：{comparisonRun.run_id}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedRunId(comparisonRun.run_id)}
                      className="rounded-md border border-secondary/20 bg-surface px-2.5 py-1 text-[10px] font-semibold text-secondary transition hover:bg-secondary/5"
                    >
                      查看原始 Run
                    </button>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <div className="rounded-lg border border-outline-variant/10 bg-surface px-3 py-3">
                      <div className="text-[11px] font-semibold text-on-surface-variant/75">原始被打回结果</div>
                      <div className="mt-2 space-y-1 text-[11px] text-on-surface-variant/80">
                        <div>状态：{getRunStatusPresentation(comparisonRun.status).label}</div>
                        <div>步骤数：{comparisonRun.steps.length}</div>
                        <div>产物数：{comparisonRun.artifacts.length}</div>
                        <div>警告数：{comparisonRun.warnings.length}</div>
                        <div>错误数：{comparisonRun.errors.length}</div>
                        {comparisonRun.review_decision?.reason ? <div>打回原因：{comparisonRun.review_decision.reason}</div> : null}
                        {comparisonReviewSummary?.risk_level ? <div>风险等级：{comparisonReviewSummary.risk_level}</div> : null}
                      </div>
                    </div>

                    <div className="rounded-lg border border-secondary/20 bg-secondary/5 px-3 py-3">
                      <div className="text-[11px] font-semibold text-secondary">当前自动修复结果</div>
                      <div className="mt-2 space-y-1 text-[11px] text-on-surface-variant/80">
                        <div>状态：{getRunStatusPresentation(selectedRun.status).label}</div>
                        <div>步骤数：{selectedRun.steps.length}</div>
                        <div>产物数：{selectedRun.artifacts.length}</div>
                        <div>警告数：{selectedRun.warnings.length}</div>
                        <div>错误数：{selectedRun.errors.length}</div>
                        {selectedRun.review_source_run_id ? <div>来源复核 Run：{selectedRun.review_source_run_id}</div> : null}
                        <div>修复目标：根据打回原因和已有证据自动再跑一轮</div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 rounded-lg border border-outline-variant/10 bg-surface px-3 py-3 text-[11px] text-on-surface-variant/80">
                    <div className="font-semibold text-on-surface">关键变化</div>
                    <div className="mt-1">错误变化：{comparisonRun.errors.length} {'->'} {selectedRun.errors.length}</div>
                    <div className="mt-1">警告变化：{comparisonRun.warnings.length} {'->'} {selectedRun.warnings.length}</div>
                    <div className="mt-1">产物变化：{comparisonRun.artifacts.length} {'->'} {selectedRun.artifacts.length}</div>
                    {comparisonReviewSummary?.must_review_items?.length ? (
                      <div className="mt-1">原始必审项：{comparisonReviewSummary.must_review_items.slice(0, 2).join('；')}</div>
                    ) : null}
                  </div>
                </div>
              ) : null}

              <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">当前记录</div>
                    <div className="mt-2 font-mono text-sm font-bold text-on-surface">{selectedRun.run_id}</div>
                    <div className="mt-1 text-xs text-on-surface-variant/70">{getFlowLabel(selectedRun.flow_name)}</div>
                    {(selectedRun.parent_run_id || selectedRun.continuation_run_id) ? (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {selectedRun.parent_run_id ? (
                          <button
                            type="button"
                            onClick={() => setSelectedRunId(selectedRun.parent_run_id || null)}
                            className="rounded-md border border-outline-variant/20 bg-surface px-2.5 py-1 text-[10px] font-semibold text-on-surface-variant transition hover:border-primary/25 hover:bg-primary/5"
                          >
                            上游 Run：{selectedRun.parent_run_id}
                          </button>
                        ) : null}
                        {selectedRun.continuation_run_id ? (
                          <button
                            type="button"
                            onClick={() => setSelectedRunId(selectedRun.continuation_run_id || null)}
                            className="rounded-md border border-primary/20 bg-primary/10 px-2.5 py-1 text-[10px] font-semibold text-primary transition hover:bg-primary/15"
                          >
                            后续 Run：{selectedRun.continuation_run_id}
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                  <span className={`rounded-lg border px-3 py-1 text-xs font-bold ${getRunStatusPresentation(selectedRun.status).tone}`}>
                    {getRunStatusPresentation(selectedRun.status).label}
                  </span>
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(320px,1fr)]">
                <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                  <div className="mb-3 flex items-center gap-2 text-on-surface">
                    <Clock3 className="h-4 w-4 text-primary" />
                    <span className="text-sm font-semibold">阶段时间线</span>
                  </div>
                  <div className="space-y-3">
                    {selectedRun.steps.map(step => {
                      const status = getRunStatusPresentation(step.status);
                      const retriesUsed = getStepMetaNumber(step, 'retries_used');
                      const attempts = getStepMetaNumber(step, 'attempts');
                      return (
                        <div key={`${selectedRun.run_id}-${step.agent}`} className="rounded-lg border border-outline-variant/10 bg-surface px-3 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <div className="text-sm font-semibold text-on-surface">{getStepLabel(step.agent)}</div>
                              <div className="mt-1 text-[11px] text-on-surface-variant/70">{step.message || step.agent}</div>
                            </div>
                            <span className={`rounded-md border px-2 py-0.5 text-[9px] font-bold ${status.tone}`}>{status.label}</span>
                          </div>

                          <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-on-surface-variant/70">
                            <span className="rounded-md bg-surface-container-low px-2 py-0.5">产物 {step.artifacts?.length || 0}</span>
                            <span className="rounded-md bg-surface-container-low px-2 py-0.5">警告 {step.warnings?.length || 0}</span>
                            <span className="rounded-md bg-surface-container-low px-2 py-0.5">错误 {step.errors?.length || 0}</span>
                            {retriesUsed > 0 ? <span className="rounded-md bg-surface-container-low px-2 py-0.5">重试 {retriesUsed} 次</span> : null}
                            {attempts > 1 ? <span className="rounded-md bg-surface-container-low px-2 py-0.5">尝试 {attempts} 次</span> : null}
                            {step.requires_human_review ? <span className="rounded-md bg-accent/10 px-2 py-0.5 text-accent">需人工复核</span> : null}
                          </div>

                          {step.next_action ? (
                            <div className="mt-3 rounded-md border border-secondary/15 bg-secondary/5 px-3 py-2 text-[10px] text-secondary">
                              下一步：{step.next_action}
                            </div>
                          ) : null}

                          {step.errors && step.errors.length > 0 ? (
                            <div className="mt-3 rounded-md border border-error/20 bg-error/5 px-3 py-2 text-[10px] text-error">
                              {sanitizeDetailText(step.errors[0], '该阶段出现错误，请结合状态和下一步建议继续排查。')}
                            </div>
                          ) : null}

                          {!step.errors?.length && step.warnings && step.warnings.length > 0 ? (
                            <div className="mt-3 rounded-md border border-tertiary/20 bg-tertiary/5 px-3 py-2 text-[10px] text-tertiary">
                              {sanitizeDetailText(step.warnings[0], '该阶段存在警告，请优先参考状态说明和下一步建议。')}
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                    <div className="mb-3 flex items-center gap-2 text-on-surface">
                      <AlertTriangle className="h-4 w-4 text-accent" />
                      <span className="text-sm font-semibold">复核结论</span>
                    </div>
                    {reviewSummary ? (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="text-xs font-semibold text-on-surface">总体状态</div>
                            <div className="mt-1 text-[11px] text-on-surface-variant/70">
                              风险等级：{reviewSummary.risk_level || '未标注'}
                            </div>
                          </div>
                          <span className="rounded-md border border-accent/20 bg-accent/10 px-2 py-0.5 text-[10px] font-bold text-accent">
                            {reviewSummary.overall_status || 'needs_human_review'}
                          </span>
                        </div>
                        {reviewSummary.summary ? (
                          <div className="rounded-lg border border-outline-variant/10 bg-surface px-3 py-3 text-[11px] leading-relaxed text-on-surface-variant/80">
                            {reviewSummary.summary}
                          </div>
                        ) : null}
                        {reviewSummary.must_review_items?.length ? (
                          <div className="space-y-2">
                            <div className="text-[11px] font-semibold text-on-surface-variant/80">必须复核</div>
                            {reviewSummary.must_review_items.slice(0, 4).map(item => (
                              <div key={item} className="rounded-md border border-accent/10 bg-surface px-2 py-1 text-[10px] text-on-surface-variant">
                                {item}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {reviewSummary.recommendations?.length ? (
                          <div className="space-y-2">
                            <div className="text-[11px] font-semibold text-on-surface-variant/80">建议动作</div>
                            {reviewSummary.recommendations.slice(0, 3).map(item => (
                              <div key={item} className="rounded-md border border-outline-variant/10 bg-surface px-2 py-1 text-[10px] text-on-surface-variant">
                                {item}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {selectedRun.review_decision ? (
                          <div className="rounded-lg border border-outline-variant/10 bg-surface px-3 py-3 text-[11px] text-on-surface-variant/80">
                            <div className="font-semibold text-on-surface">复核动作说明</div>
                            <div className="mt-1">复核人：{selectedRun.review_decision.reviewer}</div>
                            {selectedRun.review_decision.reason ? <div className="mt-1">原因：{selectedRun.review_decision.reason}</div> : null}
                            {selectedRun.review_decision.next_action ? <div className="mt-1">下一步：{selectedRun.review_decision.next_action}</div> : null}
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <div className="rounded-lg border border-outline-variant/10 bg-surface px-3 py-4 text-sm text-on-surface-variant">
                        当前没有复核摘要。
                      </div>
                    )}
                  </div>

                  <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                    <div className="mb-3 flex items-center gap-2 text-on-surface">
                      <Boxes className="h-4 w-4 text-secondary" />
                      <span className="text-sm font-semibold">产物摘要</span>
                    </div>
                    {selectedArtifacts.length === 0 ? (
                      <div className="rounded-lg border border-outline-variant/10 bg-surface px-3 py-4 text-sm text-on-surface-variant">
                        当前没有可展示的产物摘要。
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {selectedArtifacts.map((artifact, index) => {
                          const artifactKey = artifact.name || artifact.type || `artifact-${index}`;
                          const active = selectedArtifactName === (artifact.name || artifact.type || artifactKey);
                          return (
                            <button
                              key={artifactKey}
                              type="button"
                              onClick={() => setSelectedArtifactName(artifact.name || artifact.type || artifactKey)}
                              className={`w-full rounded-lg border px-3 py-3 text-left transition ${
                                active
                                  ? 'border-secondary/30 bg-secondary/5'
                                  : 'border-secondary/15 bg-surface hover:border-secondary/25 hover:bg-secondary/5'
                              }`}
                            >
                              <div className="flex items-center justify-between gap-3">
                                <div>
                                  <div className="text-sm font-semibold text-secondary">{getArtifactLabel(artifact.type)}</div>
                                  <div className="mt-1 font-mono text-[11px] text-on-surface-variant/70">{artifact.name || artifact.type || 'unknown'}</div>
                                </div>
                                <span className="text-[9px] text-on-surface-variant/60">
                                  {artifact.summary ? Object.keys(artifact.summary).length : 0} 个字段
                                </span>
                              </div>
                              <div className="mt-2 flex flex-wrap gap-1.5 text-[9px] text-on-surface-variant/70">
                                {artifact.producer ? <span className="rounded-md bg-surface-container-low px-2 py-0.5">来源 {artifact.producer}</span> : null}
                                {artifact.metadata_path ? <span className="rounded-md bg-surface-container-low px-2 py-0.5">索引已落盘</span> : null}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                    <div className="mb-3 text-sm font-semibold text-on-surface">产物详情预览</div>
                    {!selectedArtifactName ? (
                      <div className="rounded-lg border border-outline-variant/10 bg-surface px-3 py-4 text-sm text-on-surface-variant">
                        从上方选择一个产物，即可查看更细的摘要和索引信息。
                      </div>
                    ) : artifactLoading ? (
                      <div className="flex items-center gap-3 rounded-lg border border-outline-variant/10 bg-surface px-3 py-4 text-sm text-on-surface-variant">
                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                        正在加载产物详情...
                      </div>
                    ) : artifactError ? (
                      <div className="rounded-lg border border-error/20 bg-error/5 px-3 py-4 text-sm text-error">{artifactError}</div>
                    ) : selectedArtifactDetail ? (
                      <div className="space-y-3">
                        <div className="rounded-lg border border-outline-variant/10 bg-surface px-3 py-3">
                          <div className="text-sm font-semibold text-on-surface">{getArtifactLabel(selectedArtifactDetail.type)}</div>
                          <div className="mt-1 font-mono text-[11px] text-on-surface-variant/70">
                            {selectedArtifactDetail.name || selectedArtifactDetail.type || selectedArtifactName}
                          </div>
                          <div className="mt-2 space-y-1 text-[11px] text-on-surface-variant/80">
                            {selectedArtifactDetail.producer ? <div>来源：{selectedArtifactDetail.producer}</div> : null}
                            {selectedArtifactDetail.path ? <div>路径：{selectedArtifactDetail.path}</div> : null}
                            {selectedArtifactDetail.metadata_path ? <div>索引：{selectedArtifactDetail.metadata_path}</div> : null}
                            {selectedArtifactDetail.format ? <div>格式：{selectedArtifactDetail.format}</div> : null}
                          </div>
                        </div>
                        {selectedArtifactDetail.summary && Object.keys(selectedArtifactDetail.summary).length > 0 ? (
                          <div className="rounded-lg border border-outline-variant/10 bg-surface px-3 py-3">
                            <div className="mb-2 text-[11px] font-semibold text-on-surface-variant/80">摘要字段</div>
                            <div className="flex flex-wrap gap-1.5">
                              {Object.entries(selectedArtifactDetail.summary).map(([key, value]) => (
                                <span key={key} className="rounded-md border border-outline-variant/10 bg-surface-container-low px-2 py-0.5 text-[10px] text-on-surface-variant">
                                  {key}: {String(value)}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <div className="rounded-lg border border-outline-variant/10 bg-surface px-3 py-4 text-sm text-on-surface-variant">
                        当前没有更多产物详情。
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>

    </div>
  );
}
