import React, { useEffect, useMemo, useState } from 'react';
import { Boxes, CheckCircle2, Clock3, Loader2, RefreshCw, ShieldAlert, Workflow } from 'lucide-react';
import { motion } from 'motion/react';
import { getAgentRun, getAgentRunArtifacts, listAgentRuns, type AgentRunArtifact, type AgentRunResult } from '../api/backend';
import { getArtifactLabel, getFlowLabel, getRunStatusPresentation, getStepLabel } from '../utils/runPresentation';

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-3 text-[10px] font-bold uppercase tracking-[0.2em] text-on-surface-variant">{children}</h3>;
}

export function AgentRuns() {
  const [runs, setRuns] = useState<AgentRunResult[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<AgentRunResult | null>(null);
  const [selectedArtifacts, setSelectedArtifacts] = useState<AgentRunArtifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');

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
      return;
    }

    let cancelled = false;
    setDetailLoading(true);

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

  const summary = useMemo(
    () => ({
      total: runs.length,
      completed: runs.filter(run => run.status === 'completed').length,
      blocked: runs.filter(run => run.status === 'failed').length,
    }),
    [runs],
  );

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-500">
      <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-primary">
              <Workflow className="h-5 w-5" />
              <span className="text-xs font-bold uppercase tracking-[0.25em]">运行总览</span>
            </div>
            <h1 className="font-headline text-3xl font-bold text-on-surface">运行中心</h1>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-on-surface-variant/80">
              这里不是主操作页，而是给你排错和回看流程用的。它会把代码生成这件事拆成几个阶段，告诉你每一步有没有跑通、卡在哪、最终产出了什么。
            </p>
          </div>

          <button
            type="button"
            onClick={() => void loadRuns()}
            className="inline-flex items-center gap-2 self-start rounded-xl border border-primary/20 bg-primary/10 px-4 py-2 text-sm font-bold text-primary transition hover:bg-primary/15"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            刷新记录
          </button>
        </div>

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
            <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">被阻断</div>
            <div className="mt-2 font-headline text-3xl font-bold text-tertiary">{summary.blocked}</div>
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
              先从左侧选择一条运行记录，再看这次代码生成具体经历了哪些阶段。
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
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
              <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">当前记录</div>
                    <div className="mt-2 font-mono text-sm font-bold text-on-surface">{selectedRun.run_id}</div>
                    <div className="mt-1 text-xs text-on-surface-variant/70">{getFlowLabel(selectedRun.flow_name)}</div>
                  </div>
                  <span className={`rounded-lg border px-3 py-1 text-xs font-bold ${getRunStatusPresentation(selectedRun.status).tone}`}>
                    {getRunStatusPresentation(selectedRun.status).label}
                  </span>
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,1fr)]">
                <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                  <div className="mb-3 flex items-center gap-2 text-on-surface">
                    <Clock3 className="h-4 w-4 text-primary" />
                    <span className="text-sm font-semibold">这次生成经历了哪些阶段</span>
                  </div>
                  <div className="space-y-3">
                    {selectedRun.steps.map(step => {
                      const status = getRunStatusPresentation(step.status);
                      return (
                        <div key={`${selectedRun.run_id}-${step.agent}`} className="rounded-lg border border-outline-variant/10 bg-surface px-3 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <div className="text-sm font-semibold text-on-surface">{getStepLabel(step.agent)}</div>
                              <div className="mt-1 text-[11px] text-on-surface-variant/70">{step.agent}</div>
                            </div>
                            <span className={`rounded-md border px-2 py-0.5 text-[9px] font-bold ${status.tone}`}>{status.label}</span>
                          </div>

                          <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-on-surface-variant/70">
                            <span className="rounded-md bg-surface-container-low px-2 py-0.5">产物 {step.artifacts?.length || 0}</span>
                            <span className="rounded-md bg-surface-container-low px-2 py-0.5">警告 {step.warnings?.length || 0}</span>
                            <span className="rounded-md bg-surface-container-low px-2 py-0.5">错误 {step.errors?.length || 0}</span>
                          </div>

                          {step.errors && step.errors.length > 0 && (
                            <div className="mt-3 rounded-md border border-error/20 bg-error/5 px-3 py-2 text-[10px] text-error">
                              {step.errors[0]}
                            </div>
                          )}

                          {!step.errors?.length && step.warnings && step.warnings.length > 0 && (
                            <div className="mt-3 rounded-md border border-tertiary/20 bg-tertiary/5 px-3 py-2 text-[10px] text-tertiary">
                              {step.warnings[0]}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                  <div className="mb-3 flex items-center gap-2 text-on-surface">
                    <Boxes className="h-4 w-4 text-secondary" />
                    <span className="text-sm font-semibold">最终产物摘要</span>
                  </div>
                  {selectedArtifacts.length === 0 ? (
                    <div className="rounded-lg border border-outline-variant/10 bg-surface px-3 py-4 text-sm text-on-surface-variant">
                      当前没有可展示的产物摘要。
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {selectedArtifacts.map((artifact, index) => (
                        <div key={`${artifact.type || 'artifact'}-${index}`} className="rounded-lg border border-secondary/15 bg-surface px-3 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <div className="text-sm font-semibold text-secondary">{getArtifactLabel(artifact.type)}</div>
                              <div className="mt-1 font-mono text-[11px] text-on-surface-variant/70">{artifact.type || 'unknown'}</div>
                            </div>
                            <span className="text-[9px] text-on-surface-variant/60">
                              {artifact.summary ? Object.keys(artifact.summary).length : 0} 个字段
                            </span>
                          </div>
                          {artifact.summary && Object.keys(artifact.summary).length > 0 ? (
                            <div className="mt-3 flex flex-wrap gap-1.5">
                              {Object.entries(artifact.summary)
                                .slice(0, 6)
                                .map(([key, value]) => (
                                  <span key={key} className="rounded-md border border-outline-variant/10 bg-surface-container-low px-2 py-0.5 text-[9px] text-on-surface-variant">
                                    {key}: {String(value)}
                                  </span>
                                ))}
                            </div>
                          ) : (
                            <div className="mt-2 text-[10px] text-on-surface-variant/70">当前没有更多摘要字段。</div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </section>
      </div>

      <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-sm">
        <SectionTitle>怎么用这个页面</SectionTitle>
        <div className="grid gap-3 md:grid-cols-3">
          {[
            '如果代码生成失败，先看左侧最近记录，再点开详情看是卡在测试规划、代码装配还是编译预检。',
            '如果代码生成成功，这里能帮助你回看这次流程到底用了哪些中间产物，而不是只看到最后一份代码。',
            '平时主操作还是在代码实验室，这里更像运行中心和排错中心，不建议把它当成日常主页面。',
          ].map(text => (
            <div key={text} className="rounded-xl border border-outline-variant/10 bg-surface-container px-4 py-3 text-sm leading-relaxed text-on-surface-variant/80">
              {text}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
