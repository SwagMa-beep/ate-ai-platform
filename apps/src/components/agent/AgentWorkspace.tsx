import { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, Loader2, PlayCircle, ShieldAlert } from 'lucide-react';
import {
  checkHealth,
  clearAgentRuns,
  createFullAteRunAsync,
  getAgentRun,
  listAgentRuns,
  uploadPDF,
  type AgentRunResult,
} from '../../api/backend';
import { getStepLabel } from '../../utils/runPresentation';
import { Card } from '../common/Card';
import { EmptyState } from '../common/EmptyState';
import { AgentThinkingFeed, type ThinkingFeedEntry } from './AgentThinkingFeed';
import { AgentRunTimeline } from './AgentRunTimeline';
import { AgentArtifactsPanel } from './AgentArtifactsPanel';
import { AgentReviewPanel } from './AgentReviewPanel';
import { AgentRunTable } from './AgentRunTable';

function isRunActive(status?: string) {
  return status === 'running' || status === 'processing' || status === 'pending';
}

function upsertRun(runs: AgentRunResult[], nextRun: AgentRunResult) {
  return [nextRun, ...runs.filter(run => run.run_id !== nextRun.run_id)];
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

function formatElapsedSince(startedAt?: string, now = Date.now()) {
  if (!startedAt) return '0 秒';
  const started = new Date(startedAt).getTime();
  if (Number.isNaN(started)) return '0 秒';
  const totalSeconds = Math.max(0, Math.floor((now - started) / 1000));
  if (totalSeconds < 60) return `${totalSeconds} 秒`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes} 分 ${seconds} 秒`;
}

function normalizeIsoTime(value?: string) {
  return value && !Number.isNaN(new Date(value).getTime()) ? value : new Date().toISOString();
}

function appendUniqueFeedEntries(existing: ThinkingFeedEntry[], additions: ThinkingFeedEntry[]) {
  const seen = new Set(existing.map(entry => entry.id));
  const next = [...existing];
  additions.forEach(entry => {
    if (seen.has(entry.id)) return;
    seen.add(entry.id);
    next.push(entry);
  });
  return next;
}

export function AgentWorkspace() {
  const [goal, setGoal] = useState('请基于当前 Datasheet 生成 STS8200S 测试开发交付物，包含 TestPlan 提取、资源映射、测试代码初稿、关键工程风险与复核建议；优先保证平台 API、供电脚定义、资源分配和可上机前检查项清晰可核对。');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileId, setFileId] = useState(getStoredFileId());
  const [enableRag, setEnableRag] = useState(true);
  const [enableResourceMap, setEnableResourceMap] = useState(true);
  const [dualSiteMode, setDualSiteMode] = useState(false);
  const [enableStaticCheck, setEnableStaticCheck] = useState(true);
  const [enableDiagnosis, setEnableDiagnosis] = useState(false);
  const [runs, setRuns] = useState<AgentRunResult[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [clearingRuns, setClearingRuns] = useState(false);
  const [message, setMessage] = useState('');
  const [clockTick, setClockTick] = useState(() => Date.now());
  const [thinkingFeed, setThinkingFeed] = useState<ThinkingFeedEntry[]>([]);
  const [thinkingCollapsed, setThinkingCollapsed] = useState(false);
  const lastProgressKeyRef = useRef('');
  const lastRunIdRef = useRef('');

  useEffect(() => {
    listAgentRuns(10)
      .then(response => {
        if (response.status === 'success') {
          const items = response.data?.items || [];
          setRuns(items);
          setSelectedRunId(items[0]?.run_id || null);
        }
      })
      .catch(() => undefined);
  }, []);

  const activeRun = useMemo(
    () => runs.find(run => run.run_id === selectedRunId) || runs[0] || null,
    [runs, selectedRunId],
  );

  useEffect(() => {
    if (!activeRun || !isRunActive(activeRun.status)) return;
    const timer = window.setInterval(() => setClockTick(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [activeRun]);

  useEffect(() => {
    if (!activeRun) {
      setThinkingCollapsed(false);
      return;
    }
    setThinkingCollapsed(!isRunActive(activeRun.status));
  }, [activeRun?.run_id, activeRun?.status]);

  const progressSummary = useMemo(() => {
    if (!activeRun) return null;
    const shared = activeRun.shared as Record<string, unknown> | undefined;
    const progress = shared?.progress as Record<string, unknown> | undefined;
    const reversedSteps = [...(activeRun.steps || [])].reverse();
    const currentStep = reversedSteps.find(step => step.status === 'running') || reversedSteps[0];
    const currentAgent = typeof progress?.current_agent === 'string' ? progress.current_agent : currentStep?.agent;
    const completedSteps =
      typeof progress?.completed_steps === 'number'
        ? progress.completed_steps
        : activeRun.steps.filter(step => step.status !== 'running').length;
    const totalSteps = typeof progress?.total_steps === 'number' ? progress.total_steps : activeRun.steps.length;
    const phaseMessage =
      typeof progress?.message === 'string' ? progress.message : '运行已创建，正在等待后端返回最新进度。';
    return {
      currentLabel: currentAgent ? getStepLabel(currentAgent) : '准备启动',
      completedSteps,
      totalSteps,
      phaseMessage,
      elapsed: formatElapsedSince(activeRun.created_at, clockTick),
    };
  }, [activeRun, clockTick]);

  useEffect(() => {
    if (!activeRun?.run_id) {
      setThinkingFeed([]);
      lastProgressKeyRef.current = '';
      lastRunIdRef.current = '';
      return;
    }

    if (lastRunIdRef.current !== activeRun.run_id) {
      lastRunIdRef.current = activeRun.run_id;
      const seeded: ThinkingFeedEntry[] = [];
      seeded.push({
        id: `${activeRun.run_id}:created`,
        time: normalizeIsoTime(activeRun.created_at),
        label: 'Run 已创建',
        detail: `已创建 ${activeRun.flow_name}，等待 Agent 开始执行。`,
        tone: 'completed',
      });

      activeRun.steps.forEach((step, index) => {
        const stepMeta = (step.metadata as Record<string, unknown> | undefined) || {};
        const startedAt = typeof stepMeta.started_at === 'string' ? stepMeta.started_at : activeRun.created_at;
        const finishedAt = typeof stepMeta.finished_at === 'string' ? stepMeta.finished_at : startedAt;
        seeded.push({
          id: `${activeRun.run_id}:step:${index}:${step.agent}:${step.status}`,
          time: normalizeIsoTime(step.status === 'running' ? startedAt : finishedAt),
          label: `${getStepLabel(step.agent)} · ${step.status === 'running' ? '执行中' : '阶段完成'}`,
          detail: step.message || `${getStepLabel(step.agent)} 已更新为 ${step.status}。`,
          tone: step.status === 'running' ? 'running' : step.status === 'failed' || step.status === 'warning' ? 'warning' : 'completed',
        });
      });

      const shared = activeRun.shared as Record<string, unknown> | undefined;
      const progress = shared?.progress as Record<string, unknown> | undefined;
      const progressMessage = typeof progress?.message === 'string' ? progress.message : '';
      if (progressMessage) {
        seeded.push({
          id: `${activeRun.run_id}:progress:initial:${progressMessage}`,
          time: normalizeIsoTime(activeRun.updated_at || activeRun.created_at),
          label: '实时进度',
          detail: progressMessage,
          tone: isRunActive(activeRun.status) ? 'running' : 'completed',
        });
        lastProgressKeyRef.current = `${activeRun.run_id}:${progressMessage}:${activeRun.updated_at || ''}`;
      } else {
        lastProgressKeyRef.current = '';
      }

      setThinkingFeed(seeded);
      return;
    }

    const additions: ThinkingFeedEntry[] = [];
    activeRun.steps.forEach((step, index) => {
      const id = `${activeRun.run_id}:step:${index}:${step.agent}:${step.status}`;
      const stepMeta = (step.metadata as Record<string, unknown> | undefined) || {};
      const startedAt = typeof stepMeta.started_at === 'string' ? stepMeta.started_at : activeRun.created_at;
      const finishedAt = typeof stepMeta.finished_at === 'string' ? stepMeta.finished_at : startedAt;
      additions.push({
        id,
        time: normalizeIsoTime(step.status === 'running' ? startedAt : finishedAt),
        label: `${getStepLabel(step.agent)} · ${step.status === 'running' ? '执行中' : '阶段完成'}`,
        detail: step.message || `${getStepLabel(step.agent)} 已更新为 ${step.status}。`,
        tone: step.status === 'running' ? 'running' : step.status === 'failed' || step.status === 'warning' ? 'warning' : 'completed',
      });
    });

    const shared = activeRun.shared as Record<string, unknown> | undefined;
    const progress = shared?.progress as Record<string, unknown> | undefined;
    const progressMessage = typeof progress?.message === 'string' ? progress.message : '';
    const progressKey = `${activeRun.run_id}:${progressMessage}:${activeRun.updated_at || ''}`;
    if (progressMessage && progressKey !== lastProgressKeyRef.current) {
      lastProgressKeyRef.current = progressKey;
      additions.push({
        id: `${activeRun.run_id}:progress:${activeRun.updated_at || Date.now()}`,
        time: normalizeIsoTime(activeRun.updated_at || activeRun.created_at),
        label: '实时进度',
        detail: progressMessage,
        tone: isRunActive(activeRun.status) ? 'running' : activeRun.status === 'failed' ? 'warning' : 'completed',
      });
    }

    if (additions.length) {
      setThinkingFeed(current => appendUniqueFeedEntries(current, additions));
    }
  }, [activeRun]);

  useEffect(() => {
    if (!activeRun || !selectedRunId || !isRunActive(activeRun.status)) return;

    let cancelled = false;
    let timer: number | undefined;

    const pollRun = async () => {
      try {
        const response = await getAgentRun(selectedRunId);
        if (cancelled || response.status !== 'success' || !response.data) return;

        const nextRun = response.data;
        setRuns(current => upsertRun(current, nextRun));

        if (isRunActive(nextRun.status)) {
          const shared = nextRun.shared as Record<string, unknown> | undefined;
          const progress = shared?.progress as Record<string, unknown> | undefined;
          const progressMessage = typeof progress?.message === 'string' ? progress.message : '后台正在执行 Agent Flow。';
          setMessage(`运行进行中：${progressMessage}`);
          timer = window.setTimeout(pollRun, 1500);
          return;
        }

        const finishedMessage =
          nextRun.status === 'human_review_required'
            ? '运行已到达工程复核阶段，请查看 ReviewAgent 结论。'
            : nextRun.status === 'completed'
              ? '运行已完成，可继续查看时间线和中间产物。'
              : nextRun.status === 'failed'
                ? '运行已失败，请先查看时间线中的错误步骤。'
                : `运行状态已更新为 ${nextRun.status}。`;
        setMessage(finishedMessage);

        void listAgentRuns(10).then(res => {
          if (!cancelled && res.status === 'success') {
            setRuns(res.data?.items || []);
          }
        });
      } catch (error) {
        if (!cancelled) {
          setMessage(error instanceof Error ? `运行状态刷新失败：${error.message}` : '运行状态刷新失败。');
          timer = window.setTimeout(pollRun, 3000);
        }
      }
    };

    timer = window.setTimeout(pollRun, 1200);
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [activeRun, selectedRunId]);

  const handleRun = async () => {
    setCreating(true);
    setMessage('');
    try {
      try {
        const health = await checkHealth();
        if (health.status !== 'success') {
          setMessage(health.message || '后端当前不可用，请先恢复 API 再启动运行。');
          return;
        }
      } catch (healthError) {
        setMessage(healthError instanceof Error ? `后端连接失败：${healthError.message}` : '后端连接失败，请先启动 API。');
        return;
      }

      let resolvedFileId = fileId.trim();

      if (selectedFile) {
        setMessage('后端已连接，正在上传 Datasheet PDF...');
        const uploadResponse = await uploadPDF(selectedFile);
        if (uploadResponse.status !== 'success' || !uploadResponse.data?.file_id) {
          setMessage(uploadResponse.message || 'Datasheet 上传失败，未能启动运行。');
          return;
        }
        resolvedFileId = uploadResponse.data.file_id;
        setFileId(resolvedFileId);
        persistFileId(resolvedFileId);
      }

      if (!resolvedFileId) {
        setMessage('请先选择 Datasheet PDF，或填写已有的模块一 file_id。');
        return;
      }

      setMessage('上传完成，正在创建 Agent 运行并接入实时进度...');
      const response = await createFullAteRunAsync({
        flow_name: 'full_ate_development',
        goal,
        file_id: resolvedFileId,
        export_package: true,
        auto_recommend: enableRag,
        dual_site: dualSiteMode,
      });
      if (response.status === 'success' && response.data) {
        setRuns(current => upsertRun(current, response.data!));
        setSelectedRunId(response.data.run_id);
        setSelectedFile(null);
        setMessage('已发起新的 full_ate_development 运行，时间线会持续刷新当前进度。');
      } else {
        setMessage(response.message || '创建运行失败，已保留当前工作台内容。');
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '创建运行失败，请稍后重试。');
    } finally {
      setCreating(false);
    }
  };

  const handleClearRuns = async () => {
    if (typeof window !== 'undefined' && !window.confirm('确定要清空最近运行记录吗？')) {
      return;
    }

    setClearingRuns(true);
    try {
      const response = await clearAgentRuns();
      if (response.status === 'success') {
        setRuns([]);
        setSelectedRunId(null);
        setThinkingFeed([]);
        setMessage(`已清空 ${response.data?.deleted_count ?? 0} 条运行记录。`);
      } else {
        setMessage(response.message || '清空运行记录失败。');
      }
    } catch (error) {
      setMessage(error instanceof Error ? `清空运行记录失败：${error.message}` : '清空运行记录失败。');
    } finally {
      setClearingRuns(false);
    }
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
      <div className="space-y-6">
        <Card title="任务输入区">
          <div className="space-y-4">
            <label className="block">
              <div className="mb-1.5 text-xs font-semibold text-on-surface-variant/70">任务目标</div>
              <textarea
                value={goal}
                onChange={event => setGoal(event.target.value)}
                rows={5}
                className="w-full rounded-xl border border-outline-variant/20 bg-surface px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/35"
              />
            </label>

            <label className="block">
              <div className="mb-1.5 text-xs font-semibold text-on-surface-variant/70">Datasheet 上传</div>
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
              <div className="mb-1.5 text-xs font-semibold text-on-surface-variant/70">模块一文件 ID（可选）</div>
              <input
                value={fileId}
                onChange={event => setFileId(event.target.value)}
                placeholder="不上传新 PDF 时，可复用已有 file_id"
                className="w-full rounded-xl border border-outline-variant/20 bg-surface px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/35"
              />
            </label>

            <div className="grid gap-3 md:grid-cols-2">
              <label className="rounded-xl border border-outline-variant/12 bg-surface-container p-3 text-sm">
                <div className="font-semibold text-on-surface">目标平台</div>
                <div className="mt-2 text-primary">STS8200S</div>
              </label>
              <label className="rounded-xl border border-outline-variant/12 bg-surface-container p-3 text-sm">
                <div className="font-semibold text-on-surface">执行模式</div>
                <div className="mt-2 text-primary">完整 ATE 开发流程</div>
              </label>
            </div>

            <div className="space-y-2 rounded-xl border border-outline-variant/12 bg-surface-container p-4 text-sm">
              <div className="font-semibold text-on-surface">执行选项</div>
              <label className="flex items-center gap-3"><input type="checkbox" checked={enableRag} onChange={e => setEnableRag(e.target.checked)} />启用 RAG 检索</label>
              <label className="flex items-center gap-3"><input type="checkbox" checked={enableResourceMap} onChange={e => setEnableResourceMap(e.target.checked)} />生成资源映射</label>
              <label className="flex items-center gap-3"><input type="checkbox" checked={dualSiteMode} onChange={e => setDualSiteMode(e.target.checked)} />启用双工位模式</label>
              <label className="flex items-center gap-3"><input type="checkbox" checked={enableStaticCheck} onChange={e => setEnableStaticCheck(e.target.checked)} />执行静态代码检查</label>
              <label className="flex items-center gap-3"><input type="checkbox" checked={enableDiagnosis} onChange={e => setEnableDiagnosis(e.target.checked)} />启用良率诊断（预留）</label>
            </div>

            <div className="rounded-xl border border-tertiary/20 bg-tertiary/10 px-4 py-3 text-sm text-tertiary">
              <div className="flex items-start gap-2">
                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                <span>生成结果仅用于辅助 ATE 测试开发，需由 ATE 工程师复核后再上机使用。</span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleRun}
              disabled={creating}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
              开始运行
            </button>

            {message ? <div className="text-sm text-primary">{message}</div> : null}
          </div>
        </Card>

        <Card
          title="最近运行记录"
          actions={
            <button
              type="button"
              onClick={handleClearRuns}
              disabled={clearingRuns || !runs.length}
              className="rounded-lg border border-outline-variant/18 bg-surface px-3 py-1.5 text-xs font-semibold text-on-surface-variant transition hover:border-rose-400/25 hover:text-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {clearingRuns ? '清空中...' : '清空记录'}
            </button>
          }
        >
          <AgentRunTable runs={runs} selectedRunId={selectedRunId} onSelect={setSelectedRunId} />
        </Card>
      </div>

      <div className="space-y-6">
        <Card
          title="Thinking Feed"
        >
          <AgentThinkingFeed
            entries={thinkingFeed}
            collapsed={thinkingCollapsed}
            onToggle={() => setThinkingCollapsed(value => !value)}
          />
        </Card>

        <Card
          title="Agent 执行时间线"
          actions={
            activeRun ? (
              <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                <Bot className="h-4 w-4" />
                {activeRun.flow_name}
              </div>
            ) : null
          }
        >
          {activeRun && isRunActive(activeRun.status) && progressSummary ? (
            <div className="mb-4 overflow-hidden rounded-2xl border border-primary/15 bg-primary/10 px-4 py-3 text-sm text-on-surface shadow-lg shadow-primary/10">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 font-semibold text-primary">
                    <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
                    正在执行：{progressSummary.currentLabel}
                  </div>
                  <div className="mt-1 text-on-surface-variant/85">
                    已完成 {progressSummary.completedSteps}/{progressSummary.totalSteps || '?'} 步。
                    {progressSummary.phaseMessage ? ` ${progressSummary.phaseMessage}` : ''}
                  </div>
                </div>
                <div className="rounded-full bg-surface px-3 py-1 text-xs font-semibold text-primary">
                  总耗时 {progressSummary.elapsed}
                </div>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-primary/10">
                <div className="h-full w-1/3 animate-pulse rounded-full bg-gradient-to-r from-transparent via-primary to-transparent" />
              </div>
            </div>
          ) : null}
          {activeRun ? (
            <AgentRunTimeline steps={activeRun.steps} />
          ) : (
            <EmptyState title="暂无运行详情" description="发起一次新的 Agent 运行后，这里会展示完整时间线。" />
          )}
        </Card>

        <Card title="Artifacts 中间产物">
          <AgentArtifactsPanel artifacts={activeRun?.artifacts || []} run={activeRun} />
        </Card>

        <Card title="工程复核">
          <AgentReviewPanel
            run={activeRun}
            onDecision={updatedRun => {
              listAgentRuns(10)
                .then(res => {
                  if (res.status === 'success') {
                    const items = res.data?.items || [];
                    setRuns(items);
                    if (!items.length) {
                      setSelectedRunId(null);
                      return;
                    }
                    const continuationRunId = updatedRun?.continuation_run?.run_id || updatedRun?.continuation_run_id;
                    const fallbackRunId = updatedRun?.run_id || items[0].run_id;
                    const preferredRunId =
                      continuationRunId && items.some(run => run.run_id === continuationRunId) ? continuationRunId : fallbackRunId;
                    setSelectedRunId(preferredRunId);
                    const isRejected = updatedRun?.status === 'rejected';
                    setMessage(
                      continuationRunId
                        ? isRejected
                          ? '复核已打回，已自动切换到后续修改流程。'
                          : '复核已批准，已自动切换到批准后的后续工程流程。'
                        : isRejected
                          ? '复核已打回，可继续查看修改建议和责任归属。'
                          : '复核状态已更新，可继续查看最新运行结果。',
                    );
                  }
                })
                .catch(() => undefined);
            }}
          />
        </Card>
      </div>
    </div>
  );
}
