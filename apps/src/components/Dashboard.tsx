import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  BrainCircuit,
  Bug,
  CheckCircle2,
  Clock3,
  Cpu,
  FileDigit,
  TrendingUp,
  Upload,
  Wifi,
  WifiOff,
  Workflow,
  Wrench,
} from 'lucide-react';
import { motion } from 'motion/react';
import { checkHealth } from '../api/backend';
import { extractionStore, type ExtractionState } from '../store/extractionStore';
import type { View } from '../types';

interface DashboardProps {
  onViewChange?: (view: View) => void;
}

function MetricCard({
  label,
  value,
  accent = 'text-primary',
}: {
  label: string;
  value: React.ReactNode;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
      <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">{label}</div>
      <div className={`mt-2 font-headline text-3xl font-bold tracking-tighter ${accent}`}>{value}</div>
    </div>
  );
}

export function Dashboard({ onViewChange }: DashboardProps) {
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [backendVersion, setBackendVersion] = useState('');
  const [extractState, setExtractState] = useState<ExtractionState>(extractionStore.getState());

  useEffect(() => {
    checkHealth()
      .then(response => {
        if (response.status === 'success' && response.data) {
          setBackendStatus('online');
          setBackendVersion(response.data.version);
        } else {
          setBackendStatus('offline');
        }
      })
      .catch(() => setBackendStatus('offline'));

    extractionStore.refreshTasks();
    const unsubscribe = extractionStore.subscribe(setExtractState);
    return unsubscribe;
  }, []);

  const taskSummary = useMemo(
    () => ({
      active: extractState.tasks.filter(task => ['pending', 'processing', 'cancelling'].includes(task.status)).length,
      completed: extractState.tasks.filter(task => task.status === 'completed').length,
      failed: extractState.tasks.filter(task => ['failed', 'cancelled'].includes(task.status)).length,
    }),
    [extractState.tasks],
  );

  const insightFeed = [
    {
      id: 'extract',
      icon: extractState.stage === 'done' ? CheckCircle2 : extractState.stage === 'error' ? Bug : BrainCircuit,
      color: extractState.stage === 'done' ? 'text-primary' : extractState.stage === 'error' ? 'text-tertiary' : 'text-secondary',
      border: extractState.stage === 'done' ? 'border-primary/30' : extractState.stage === 'error' ? 'border-tertiary/30' : 'border-secondary/30',
      title:
        extractState.stage === 'done'
          ? `最新提取完成：${extractState.result?.chip_name || '未知芯片'}`
          : extractState.stage === 'error'
            ? '提取任务出现异常'
            : extractState.stage === 'extracting'
              ? `正在分析：${extractState.fileInfo?.filename || 'Datasheet PDF'}`
              : '等待新的提取任务',
      description:
        extractState.message ||
        '模块一会在上传 Datasheet 后自动发起异步提取，并把结果共享给资源映射与代码实验室。',
      time: '实时',
    },
    {
      id: 'package',
      icon: Wrench,
      color: 'text-secondary',
      border: 'border-secondary/30',
      title: '工程包链路已接入前端',
      description: '代码实验室现在可展示计划、编译预检、工程结构验证，并支持直接下载工程包 ZIP。',
      time: '刚更新',
    },
    {
      id: 'task-center',
      icon: Clock3,
      color: 'text-primary',
      border: 'border-primary/30',
      title: '异步任务中心已上线',
      description: '最近任务支持列表查看、重试、取消和清理，重启后任务状态也能恢复。',
      time: '当前版本',
    },
  ];

  const activeFile = extractState.fileInfo?.filename || '当前没有活跃文件';
  const activeProgress = extractState.progress || 0;

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-500">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section className="relative flex min-h-[400px] flex-col justify-between overflow-hidden rounded-2xl border border-outline-variant/5 bg-surface-container-low p-8 lg:col-span-8">
          <div className="pointer-events-none absolute -left-40 -top-40 h-[600px] w-[600px] rounded-full bg-primary/10 blur-[120px]" />

          <div className="relative z-10 flex flex-col items-start justify-between gap-8 md:flex-row">
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary" />
                </span>
                <h2 className="text-xs font-semibold uppercase tracking-widest text-on-surface-variant">平台运行总览</h2>
              </div>

              <div className="mt-2 flex items-baseline gap-3">
                <motion.span
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="font-headline text-8xl font-bold tracking-tighter text-primary md:text-9xl"
                >
                  {backendStatus === 'online' ? '99.2' : '0.0'}
                </motion.span>
                <span className="font-mono text-2xl text-primary/60">%</span>
              </div>

              <p className="mt-3 flex w-fit items-center gap-2 rounded-full bg-surface-container/50 px-3 py-1.5 font-mono text-sm text-on-surface-variant">
                <TrendingUp className="h-4 w-4 text-tertiary" />
                <span className="text-tertiary">+0.4%</span>
                相比上一轮演示链路稳定度
              </p>
            </div>

            <div className="min-w-[260px] rounded-xl border-l-4 border-l-primary bg-surface-container/50 p-6">
              <p className="mb-5 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">关键状态</p>
              <div className="flex flex-col gap-4">
                {[
                  { label: '异步任务', value: `${taskSummary.active} active` },
                  { label: '最近提取参数', value: extractState.result?.statistics.total ?? 0 },
                  { label: '最近引脚数', value: extractState.result?.pin_count ?? 0 },
                ].map(item => (
                  <div key={item.label} className="flex items-center justify-between font-mono text-sm">
                    <span className="text-on-surface-variant">{item.label}</span>
                    <span className="font-bold text-primary">{item.value}</span>
                  </div>
                ))}

                <div className="mt-2 flex items-center justify-between border-t border-outline-variant/10 pt-3 font-mono text-sm">
                  <span className="flex items-center gap-1.5 text-on-surface-variant">
                    {backendStatus === 'online' ? (
                      <Wifi className="h-3.5 w-3.5 text-primary" />
                    ) : backendStatus === 'offline' ? (
                      <WifiOff className="h-3.5 w-3.5 text-error" />
                    ) : (
                      <span className="inline-block h-3.5 w-3.5 animate-pulse rounded-full bg-on-surface-variant" />
                    )}
                    后端 API
                  </span>
                  <span
                    className={`text-xs font-bold ${
                      backendStatus === 'online' ? 'text-primary' : backendStatus === 'offline' ? 'text-error' : 'text-on-surface-variant'
                    }`}
                  >
                    {backendStatus === 'online' ? `v${backendVersion}` : backendStatus === 'offline' ? '未连接' : '检测中...'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="relative z-10 mt-12 flex h-28 w-full items-end gap-1.5 overflow-hidden opacity-40">
            {[32, 48, 36, 74, 88, 65, 44, 22, 53, 81, 66, 38, 18, 52, 33].map((height, index) => (
              <motion.div
                key={index}
                initial={{ height: 0 }}
                animate={{ height: `${height}%` }}
                transition={{ delay: index * 0.05, duration: 0.8 }}
                className={`w-full rounded-t-sm ${height > 75 ? 'bg-tertiary' : 'bg-primary/50'}`}
              />
            ))}
          </div>
        </section>

        <section className="flex flex-col gap-6 rounded-2xl border border-outline-variant/10 bg-surface-container p-6 lg:col-span-4">
          <div className="flex items-center justify-between">
            <h3 className="flex items-center gap-2 font-headline text-lg font-bold text-on-surface">
              <BrainCircuit className="h-5 w-5 text-secondary" />
              AI 洞察流
            </h3>
            <button className="text-xs font-bold text-primary hover:underline" onClick={() => extractionStore.refreshTasks()}>
              刷新
            </button>
          </div>

          <div className="custom-scrollbar flex max-h-[400px] flex-col gap-4 overflow-y-auto pr-1">
            {insightFeed.map(item => (
              <motion.div key={item.id} whileHover={{ x: 4 }} className={`rounded-xl border-l-2 bg-surface-container-highest p-4 ${item.border}`}>
                <div className="flex items-start gap-4">
                  <item.icon className={`mt-0.5 h-5 w-5 shrink-0 ${item.color}`} />
                  <div>
                    <p className="text-sm leading-relaxed tracking-tight text-on-surface">{item.title}</p>
                    <p className="mt-2 text-xs italic leading-relaxed text-on-surface-variant">{item.description}</p>
                    <span className="mt-3 block font-mono text-[10px] uppercase text-on-surface-variant/60">{item.time}</span>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </section>

        <div className="mt-2 grid grid-cols-1 gap-6 lg:col-span-12 lg:grid-cols-3">
          <section className="flex flex-col gap-6 rounded-2xl border border-outline-variant/10 bg-surface-container-low p-7 lg:col-span-2">
            <h3 className="flex items-center gap-2 font-headline text-lg font-bold text-on-surface">
              <FileDigit className="h-5 w-5 text-primary" />
              活动上下文：Datasheet 提取
            </h3>

            <div className="flex flex-col gap-5">
              <div className="flex items-end justify-between">
                <div className="flex max-w-[70%] flex-col gap-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-on-surface-variant">
                    {extractState.stage !== 'idle' ? '当前分析文件' : '等待任务'}
                  </span>
                  <span
                    className={`truncate rounded-lg border px-3 py-1 font-mono text-sm ${
                      extractState.stage !== 'idle'
                        ? 'border-primary/20 bg-primary/10 text-primary'
                        : 'border-outline-variant/10 bg-surface-container text-on-surface-variant/40'
                    }`}
                  >
                    {extractState.stage !== 'idle' ? activeFile : '当前没有活跃任务'}
                  </span>
                </div>
                <div className="flex flex-col items-end">
                  <span className="font-headline text-4xl font-bold tracking-tighter text-on-surface">{activeProgress}%</span>
                </div>
              </div>

              <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-container-highest">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${activeProgress}%` }}
                  transition={{ duration: 1, ease: 'easeOut' }}
                  className={`h-full bg-gradient-to-r ${
                    extractState.stage === 'error' ? 'from-error to-error/50' : 'from-secondary to-primary'
                  }`}
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <MetricCard
                  label="状态"
                  value={
                    extractState.stage === 'done'
                      ? '完成'
                      : extractState.stage === 'error'
                        ? '错误'
                        : extractState.stage === 'idle'
                          ? '待机'
                          : '执行中'
                  }
                  accent={extractState.stage === 'error' ? 'text-error' : 'text-primary'}
                />
                <MetricCard label="提取参数" value={extractState.result?.statistics.total ?? 0} accent="text-on-surface" />
                <MetricCard label="最近任务" value={extractState.tasks.length} accent="text-secondary" />
              </div>
            </div>
          </section>

          <section className="grid grid-cols-2 gap-4 lg:col-span-1">
            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={() => onViewChange?.('extractor')}
              className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-primary/20 bg-primary p-6 text-on-primary shadow-lg shadow-primary/10 transition-all hover:brightness-110"
            >
              <Upload className="h-8 w-8 font-bold" />
              <span className="text-xs font-bold uppercase tracking-widest">????</span>
            </motion.button>

            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={() => onViewChange?.('resources')}
              className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-outline-variant/30 bg-surface-container p-6 text-primary transition-all hover:bg-surface-bright"
            >
              <Bug className="h-8 w-8" />
              <span className="text-xs font-bold uppercase tracking-widest">????</span>
            </motion.button>

            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={() => onViewChange?.('codelab')}
              className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-outline-variant/30 bg-surface-container p-6 text-secondary transition-all hover:bg-surface-bright"
            >
              <Cpu className="h-8 w-8" />
              <span className="text-xs font-bold uppercase tracking-widest">?????</span>
            </motion.button>

            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={() => onViewChange?.('failure')}
              className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-outline-variant/30 bg-surface-container p-6 text-tertiary transition-all hover:bg-surface-bright"
            >
              <Activity className="h-8 w-8" />
              <span className="text-xs font-bold uppercase tracking-widest">????</span>
            </motion.button>

            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={() => onViewChange?.('agentruns')}
              className="col-span-2 flex items-center justify-between gap-4 rounded-2xl border border-secondary/20 bg-secondary/5 p-5 text-left text-secondary transition-all hover:bg-secondary/10"
            >
              <div>
                <div className="text-xs font-bold uppercase tracking-widest">Agent Runs</div>
                <div className="mt-2 text-sm leading-relaxed text-on-surface-variant/80">
                  ?? controller?step ? artifact ????????? agent ???????????
                </div>
              </div>
              <Workflow className="h-8 w-8 shrink-0" />
            </motion.button>
          </section>
        </div>
      </div>
    </div>
  );
}
