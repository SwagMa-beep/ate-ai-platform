import React, { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  ChevronRight,
  CloudUpload,
  Cpu,
  Download,
  FileText,
  Loader2,
  RefreshCcw,
  Table as TableIcon,
  Upload,
  X,
} from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import {
  getDownloadUrl,
  type ExtractionResult,
  type PinDefinition,
  type RangeRecommendation,
  type TaskStatusResult,
  type UploadResult,
} from '../api/backend';
import { extractionStore, type ExtractionState, type Stage } from '../store/extractionStore';

function downloadFile(url: string, filename: string) {
  try {
    const anchor = document.createElement('a');
    anchor.style.display = 'none';
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    setTimeout(() => document.body.removeChild(anchor), 200);
  } catch (error) {
    console.error('Download failed:', error);
    alert(`下载失败，请检查后端连接：${error}`);
  }
}

function calcConfidence(result: ExtractionResult): number {
  if (!result || !result.statistics) return 0;
  const total = result.statistics.total || 0;
  const blocked = result.statistics.blocked || 0;
  if (total === 0) return 0;
  return Math.round(((total - blocked) / total) * 100 * 10) / 10;
}

interface UploadZoneProps {
  dragOver: boolean;
  onDragOver: (over: boolean) => void;
  onDrop: (event: React.DragEvent) => void;
  onFileSelect: () => void;
  onFileInput: (event: React.ChangeEvent<HTMLInputElement>) => void;
  fileInputRef: React.RefObject<HTMLInputElement>;
  stage: Stage;
  error: string;
  onReset: () => void;
}

const UploadZone = ({
  dragOver,
  onDragOver,
  onDrop,
  onFileSelect,
  onFileInput,
  fileInputRef,
  stage,
  error,
  onReset,
}: UploadZoneProps) => (
  <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="flex flex-col gap-8">
    <div>
      <h1 className="mb-2 font-headline text-4xl font-bold tracking-tight text-on-surface">数据手册智能提取</h1>
      <p className="max-w-2xl text-sm leading-relaxed text-on-surface-variant">
        上传芯片数据手册 PDF，系统会自动提取引脚定义、测试参数和量程建议，并生成结构化测试计划结果。
      </p>
    </div>

    <div
      onDragOver={event => {
        event.preventDefault();
        onDragOver(true);
      }}
      onDragLeave={() => onDragOver(false)}
      onDrop={onDrop}
      onClick={onFileSelect}
      className={`relative flex cursor-pointer flex-col items-center justify-center gap-6 rounded-2xl border-2 border-dashed p-16 transition-all ${
        dragOver
          ? 'border-primary bg-primary/10 shadow-[0_0_40px_#53ddfc20]'
          : 'border-outline-variant/30 bg-surface-container-low hover:border-primary/50 hover:bg-primary/5'
      }`}
    >
      <input ref={fileInputRef} type="file" accept=".pdf" className="hidden" onChange={onFileInput} />
      <div className={`rounded-2xl p-5 transition-all ${dragOver ? 'bg-primary/20' : 'bg-surface-container'}`}>
        <CloudUpload className={`h-12 w-12 transition-colors ${dragOver ? 'text-primary' : 'text-on-surface-variant'}`} />
      </div>
      <div className="text-center">
        <p className="mb-2 font-headline text-xl font-bold text-on-surface">{dragOver ? '松开以上传文件' : '拖拽 PDF 到这里'}</p>
        <p className="text-sm text-on-surface-variant">或点击选择文件，最大 50MB</p>
      </div>
      <button className="flex items-center gap-3 rounded-xl bg-primary px-8 py-4 text-xs font-bold uppercase tracking-widest text-on-primary shadow-lg shadow-primary/10 transition-all hover:brightness-110">
        <Upload className="h-5 w-5" />
        选择 PDF 文件
      </button>
    </div>

    <AnimatePresence>
      {stage === 'error' ? (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="flex items-center gap-4 rounded-2xl border border-error/30 bg-error/10 p-5"
        >
          <AlertTriangle className="h-6 w-6 shrink-0 text-error" />
          <p className="text-sm text-on-surface">{error}</p>
          <button onClick={onReset} className="ml-auto rounded-lg p-1 transition-colors hover:bg-error/20">
            <X className="h-4 w-4 text-error" />
          </button>
        </motion.div>
      ) : null}
    </AnimatePresence>
  </motion.div>
);

const ProgressView = ({
  progress,
  message,
  fileInfo,
  stage,
}: {
  progress: number;
  message: string;
  fileInfo: UploadResult | null;
  stage: Stage;
}) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.97 }}
    animate={{ opacity: 1, scale: 1 }}
    className="flex flex-col items-center gap-8 rounded-2xl border border-outline-variant/10 bg-surface-container-low p-10 text-center shadow-2xl"
  >
    <div className="relative">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary/10">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      </div>
      <div className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full bg-primary/20">
        <span className="text-[9px] font-black text-primary">{progress}%</span>
      </div>
    </div>

    <div>
      <p className="mb-2 font-headline text-2xl font-bold text-on-surface">{message}</p>
      {fileInfo ? <p className="font-mono text-sm text-on-surface-variant">{fileInfo.filename} 路 {fileInfo.size_mb} MB</p> : null}
    </div>

    <div className="h-2 w-full max-w-md overflow-hidden rounded-full bg-surface-container-highest">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${progress}%` }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="h-full rounded-full bg-gradient-to-r from-secondary to-primary"
      />
    </div>

    <p className="text-xs uppercase tracking-widest text-on-surface-variant/60">
      {stage === 'uploading' ? '上传中...' : '正在解析数据手册，命中缓存时会更快返回'}
    </p>
  </motion.div>
);

function TaskCenter({ tasks, activeTaskId }: { tasks: TaskStatusResult[]; activeTaskId: string | null }) {
  const groupedCount = {
    processing: tasks.filter(task => ['pending', 'processing', 'cancelling'].includes(task.status)).length,
    completed: tasks.filter(task => task.status === 'completed').length,
    failed: tasks.filter(task => ['failed', 'cancelled'].includes(task.status)).length,
  };

  return (
    <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-6 shadow-lg">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div>
          <h3 className="font-headline text-lg font-bold text-on-surface">任务中心</h3>
          <p className="mt-1 text-xs text-on-surface-variant">查看最近的异步提取任务，并支持重试、取消和清理。</p>
        </div>
        <button
          onClick={() => extractionStore.refreshTasks()}
          className="flex items-center gap-2 rounded-lg border border-outline-variant/20 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant transition-colors hover:bg-surface-container"
        >
          <RefreshCcw className="h-3.5 w-3.5" />
          刷新
        </button>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-3">
        {[
          { label: '进行中', value: groupedCount.processing, tone: 'text-primary bg-primary/10' },
          { label: '已完成', value: groupedCount.completed, tone: 'text-secondary bg-secondary/10' },
          { label: '失败/取消', value: groupedCount.failed, tone: 'text-tertiary bg-tertiary/10' },
        ].map(item => (
          <div key={item.label} className="rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-3 text-center">
            <div className={`rounded-lg py-1 text-lg font-bold ${item.tone}`}>{item.value}</div>
            <div className="mt-2 text-[9px] uppercase tracking-widest text-on-surface-variant/60">{item.label}</div>
          </div>
        ))}
      </div>

      <div className="mb-4 flex gap-2">
        <button
          onClick={() => extractionStore.cleanTasks('completed')}
          className="rounded-lg border border-outline-variant/20 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant transition-colors hover:bg-surface-container"
        >
          清理已完成
        </button>
        <button
          onClick={() => extractionStore.cleanTasks('failed')}
          className="rounded-lg border border-outline-variant/20 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant transition-colors hover:bg-surface-container"
        >
          清理失败
        </button>
        <button
          onClick={() => extractionStore.cleanTasks('cancelled')}
          className="rounded-lg border border-outline-variant/20 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant transition-colors hover:bg-surface-container"
        >
          清理已取消
        </button>
      </div>

      <div className="flex max-h-[460px] flex-col gap-3 overflow-y-auto pr-1">
        {tasks.length === 0 ? (
          <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4 text-sm text-on-surface-variant">
            当前还没有异步提取任务。
          </div>
        ) : (
          tasks.map(task => {
            const isActive = activeTaskId === task.task_id;
            const isProcessing = ['pending', 'processing', 'cancelling'].includes(task.status);
            const isRetryable = ['failed', 'cancelled', 'completed'].includes(task.status);
            return (
              <div
                key={task.task_id}
                className={`rounded-xl border p-4 transition-all ${
                  isActive ? 'border-primary/30 bg-primary/8' : 'border-outline-variant/10 bg-surface-container'
                }`}
              >
                <div className="mb-2 flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-primary">{task.task_id}</span>
                      <span
                        className={`rounded px-2 py-0.5 text-[9px] font-bold uppercase ${
                          task.status === 'completed'
                            ? 'bg-secondary/15 text-secondary'
                            : task.status === 'failed' || task.status === 'cancelled'
                              ? 'bg-tertiary/15 text-tertiary'
                              : 'bg-primary/15 text-primary'
                        }`}
                      >
                        {task.status}
                      </span>
                    </div>
                    <div className="mt-1 text-[11px] leading-relaxed text-on-surface-variant/80">{task.message}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-on-surface">{task.progress ?? 0}%</div>
                    <div className="text-[9px] uppercase tracking-widest text-on-surface-variant/50">progress</div>
                  </div>
                </div>

                <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-surface-container-highest">
                  <div className="h-full rounded-full bg-gradient-to-r from-secondary to-primary" style={{ width: `${task.progress ?? 0}%` }} />
                </div>

                <div className="flex gap-2">
                  {isRetryable ? (
                    <button
                      onClick={() => extractionStore.retryTask(task.task_id)}
                      className="rounded-lg border border-outline-variant/20 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant transition-colors hover:bg-surface-container"
                    >
                      重试
                    </button>
                  ) : null}
                  {isProcessing ? (
                    <button
                      onClick={() => extractionStore.cancelTask(task.task_id)}
                      className="rounded-lg border border-tertiary/20 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-tertiary transition-colors hover:bg-tertiary/10"
                    >
                      取消
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}

function ResultView({
  result,
  fileInfo,
  pins,
  tasks,
  activeTaskId,
  onReset,
  confidence,
}: {
  result: ExtractionResult | null;
  fileInfo: UploadResult | null;
  pins: PinDefinition[];
  tasks: TaskStatusResult[];
  activeTaskId: string | null;
  onReset: () => void;
  confidence: number;
}) {
  if (!result || !fileInfo) return null;

  const stats = result.statistics ?? {
    total: 0,
    A_class: 0,
    B_class: 0,
    C_class: 0,
    dc_items: 0,
    ac_items: 0,
    ldo_items: 0,
    blocked: 0,
  };
  const warnings = result.warnings ?? [];
  const run = result.run;
  const doneSteps = run?.steps?.filter(step => step.status === 'completed').length ?? 0;
  const blockedSteps = run?.steps?.filter(step => step.status === 'failed').length ?? 0;
  const runStatusLabel =
    run?.status === 'completed'
      ? '已完成'
      : run?.status === 'failed'
        ? '已阻断'
        : run?.status === 'processing'
          ? '进行中'
          : '未记录';

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-8">
      <div className="flex flex-col items-start justify-between gap-6 md:flex-row md:items-center">
        <div>
          <h1 className="mb-2 font-headline text-4xl font-bold tracking-tight text-on-surface">数据手册智能提取</h1>
          <p className="max-w-2xl text-sm leading-relaxed text-on-surface-variant">
            LLM 解析已完成，正在查看 <span className="font-mono font-bold text-primary">{result.chip_name || fileInfo.filename}</span> 的引脚图、测试参数和量程建议。
          </p>
        </div>
        <button
          onClick={onReset}
          className="flex items-center gap-3 rounded-xl border border-outline-variant/30 bg-surface-container px-6 py-4 text-xs font-bold uppercase tracking-widest text-on-surface-variant transition-all hover:bg-surface-bright"
        >
          <Upload className="h-5 w-5" />
          上传新手册
        </button>
      </div>

      {run ? (
        <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-lg">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.25em] text-primary">本次运行摘要</div>
              <h3 className="font-headline text-xl font-bold text-on-surface">提取结果已写入运行中心</h3>
              <p className="mt-1 text-sm text-on-surface-variant">
                提取页保留主操作视图，详细流程和中间产物可以去“运行中心”回看。
              </p>
            </div>
            <div className="rounded-xl border border-outline-variant/10 bg-surface-container px-4 py-3">
              <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">运行状态</div>
              <div className="mt-1 text-lg font-bold text-primary">{runStatusLabel}</div>
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-4">
            {[
              ['记录 ID', run.run_id.slice(-8), 'font-mono text-primary'],
              ['已完成阶段', doneSteps, 'text-on-surface'],
              ['需关注阶段', blockedSteps, 'text-tertiary'],
              ['产物数', run.artifacts?.length ?? 0, 'text-on-surface'],
            ].map(([label, value, tone]) => (
              <div key={String(label)} className="rounded-xl border border-outline-variant/10 bg-surface-container px-4 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">{label}</div>
                <div className={`mt-2 text-xl font-bold ${tone}`}>{value}</div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        <section className="relative overflow-hidden rounded-2xl border border-outline-variant/10 bg-surface-container-low p-8 shadow-2xl lg:col-span-12">
          <div className="pointer-events-none absolute -right-20 -top-20 h-[400px] w-[400px] rounded-full bg-primary/5 blur-[100px]" />

          <div className="relative z-10 flex flex-col items-start justify-between gap-10 md:flex-row">
            <div className="flex-1">
              <div className="mb-5 flex items-center gap-3">
                <span className="relative flex h-3 w-3">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
                  <span className="relative inline-flex h-3 w-3 rounded-full bg-primary" />
                </span>
                <span className="mr-2 text-[10px] font-bold uppercase tracking-[0.3em] text-primary">提取完成</span>
                {result.test_scenario ? (
                  <span className="rounded border border-primary/20 bg-primary/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-primary">
                    {result.test_scenario}
                  </span>
                ) : null}
              </div>

              <div className="mb-4 flex items-center gap-4">
                <div className="rounded-xl bg-primary/10 p-3">
                  <FileText className="h-8 w-8 text-primary" />
                </div>
                <h2 className="font-headline text-3xl font-bold text-on-surface">{fileInfo.filename}</h2>
              </div>

              <div className="flex flex-wrap gap-3">
                {warnings.slice(0, 2).map((warning, index) => (
                  <span key={index} className="flex items-center gap-1.5 rounded-lg border border-tertiary/20 bg-tertiary/10 px-3 py-1.5 text-xs text-tertiary">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    {warning}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex w-full gap-8 rounded-2xl border border-outline-variant/10 bg-surface-container/40 p-6 backdrop-blur-sm md:w-auto">
              {[
                ['置信度', `${confidence}%`, 'text-primary'],
                ['提取参数', stats.total, 'text-on-surface'],
                ['引脚数', result.pin_count, 'text-on-surface'],
              ].map(([label, value, color], index) => (
                <React.Fragment key={String(label)}>
                  {index > 0 ? <div className="h-auto w-px bg-outline-variant/20" /> : null}
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-on-surface-variant">{label}</span>
                    <span className={`font-headline text-4xl font-bold tracking-tighter ${color}`}>{value}</span>
                  </div>
                </React.Fragment>
              ))}
            </div>
          </div>
        </section>

        <div className="flex flex-col gap-8 lg:col-span-7">
          <div className="overflow-hidden rounded-2xl border border-outline-variant/10 bg-surface-container-low shadow-lg">
            <div className="flex items-center justify-between border-b border-outline-variant/10 bg-surface-container/30 p-6">
              <h3 className="flex items-center gap-3 font-headline text-xl font-bold text-on-surface">
                <Cpu className="h-6 w-6 text-primary" />
                已提取引脚定义
                <span className="text-sm font-normal text-on-surface-variant">({pins.length} 个)</span>
              </h3>
              <button
                onClick={() => downloadFile(getDownloadUrl(fileInfo.file_id, 'json'), `${result.chip_name || fileInfo.filename}_TestPlan.json`)}
                className="flex items-center gap-2 rounded-lg border border-primary/20 bg-surface-bright px-4 py-2 text-xs font-bold uppercase tracking-widest text-primary transition-all hover:bg-primary/10"
              >
                <Download className="h-3.5 w-3.5" />
                结果 JSON
              </button>
            </div>

            <div className="overflow-x-auto">
              {pins.length > 0 ? (
                <table className="w-full text-left">
                  <thead className="bg-surface-container/50 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                    <tr>
                      <th className="px-6 py-4">引脚 #</th>
                      <th className="px-6 py-4">名称</th>
                      <th className="px-6 py-4">方向</th>
                      <th className="px-6 py-4">功能描述</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/5 text-sm">
                    {pins.slice(0, 20).map((pin, index) => (
                      <tr key={index} className="group transition-colors hover:bg-primary/5">
                        <td className="px-6 py-4 font-mono font-bold text-primary">{pin.pin_no}</td>
                        <td className="px-6 py-4 font-bold text-on-surface">{pin.pin_name}</td>
                        <td className="px-6 py-4">
                          <span className="rounded bg-surface-container-highest px-2 py-1 text-[10px] font-bold uppercase tracking-tighter text-on-surface-variant">
                            {pin.direction || '--'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-xs leading-relaxed text-on-surface-variant opacity-90 transition-opacity group-hover:opacity-100">
                          {pin.function || pin.notes || '--'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="py-12 text-center text-sm text-on-surface-variant/50">未提取到引脚定义，部分器件场景可能不包含引脚表。</div>
              )}
              {pins.length > 20 ? (
                <div className="border-t border-outline-variant/10 p-4 text-center text-xs text-on-surface-variant/50">
                  仅展示前 20 条，共 {pins.length} 条，下载结果 JSON 可查看完整数据
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-8 lg:col-span-5">
          <TaskCenter tasks={tasks} activeTaskId={activeTaskId} />

          <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-7 shadow-lg">
            <h3 className="mb-6 flex items-center gap-3 font-headline text-lg font-bold text-on-surface">
              <TableIcon className="h-5 w-5 text-primary" />
              参数提取统计
            </h3>
            <div className="grid grid-cols-2 gap-4">
              {[
                ['总参数', stats.total, 'text-on-surface'],
                ['A 类（必测）', stats.A_class, 'text-primary'],
                ['B 类（推荐）', stats.B_class, 'text-secondary'],
                ['C 类（可选）', stats.C_class, 'text-on-surface-variant'],
                ['DC 测试项', stats.dc_items, 'text-on-surface'],
                ['AC 测试项', stats.ac_items, 'text-on-surface'],
              ].map(([label, value, color]) => (
                <div key={String(label)} className="flex flex-col gap-1 rounded-xl bg-surface-container p-4">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">{label}</span>
                  <span className={`font-headline text-2xl font-bold tracking-tighter ${color}`}>{value}</span>
                </div>
              ))}
            </div>
          </section>

          {result.range_recommendations && result.range_recommendations.length > 0 ? (
            <section className="overflow-hidden rounded-2xl border border-outline-variant/10 bg-surface-container-low shadow-lg">
              <div className="flex items-center justify-between border-b border-outline-variant/10 bg-surface-container/30 px-7 py-5">
                <h3 className="flex items-center gap-3 font-headline text-lg font-bold text-on-surface">
                  <span className="text-lg leading-none">量</span>
                  AI 量程建议
                </h3>
                <span className="text-[10px] font-mono uppercase tracking-widest text-on-surface-variant/50">基于 STS8200S 手册</span>
              </div>
              <div className="flex flex-col divide-y divide-outline-variant/8">
                {result.range_recommendations.map((rec: RangeRecommendation, index: number) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="group px-6 py-4 transition-all hover:bg-primary/5"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex items-center gap-2">
                          <span className="font-mono text-sm font-bold text-primary">{rec.param}</span>
                          {rec.value !== 'N/A' ? (
                            <span className="rounded bg-surface-container px-2 py-0.5 font-mono text-xs text-on-surface-variant/60">{rec.value}</span>
                          ) : null}
                          {rec.priority === 'high' ? (
                            <span className="rounded border border-error/20 bg-error/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-tighter text-error">
                              高优先级
                            </span>
                          ) : null}
                        </div>
                        <p className="text-[11px] leading-relaxed text-on-surface-variant opacity-75 transition-opacity group-hover:opacity-100">{rec.reason}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <span className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/50">推荐量程</span>
                        <span className="block rounded border border-secondary/20 bg-secondary/10 px-2 py-1 font-mono text-xs font-bold text-secondary">
                          {rec.range_module}
                        </span>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </section>
          ) : null}

          <div className="relative overflow-hidden rounded-2xl border-l-4 border-l-primary bg-surface-container-low p-7 shadow-lg">
            <h3 className="mb-5 flex items-center gap-3 font-headline text-sm font-bold text-on-surface">
              <Download className="h-4 w-4 text-primary" />
              下载提取结果
            </h3>
            <div className="flex flex-col gap-3">
              <button
                onClick={() => downloadFile(getDownloadUrl(fileInfo.file_id, 'excel'), `${result.chip_name || fileInfo.filename}_TestPlan.xlsx`)}
                className="group flex w-full items-center justify-between rounded-xl border border-outline-variant/20 bg-surface-container p-4 text-left transition-all hover:border-primary/30 hover:bg-primary/10"
              >
                <span className="text-sm font-bold text-on-surface">测试计划 Excel</span>
                <ChevronRight className="h-4 w-4 text-primary transition-transform group-hover:translate-x-1" />
              </button>
              <button
                onClick={() => downloadFile(getDownloadUrl(fileInfo.file_id, 'json'), `${result.chip_name || fileInfo.filename}_TestPlan.json`)}
                className="group flex w-full items-center justify-between rounded-xl border border-outline-variant/20 bg-surface-container p-4 text-left transition-all hover:border-primary/30 hover:bg-primary/10"
              >
                <span className="text-sm font-bold text-on-surface">结构化 JSON</span>
                <ChevronRight className="h-4 w-4 text-primary transition-transform group-hover:translate-x-1" />
              </button>
            </div>

            {result.sts_compatibility ? (
              <div className="mt-5 border-t border-outline-variant/10 pt-5">
                <span className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">STS 兼容性</span>
                <div className="text-xs leading-relaxed text-on-surface-variant">
                  <div className="mb-1 font-bold">
                    {result.sts_compatibility.is_compatible ? (
                      <span className="text-primary">兼容 STS8200S</span>
                    ) : (
                      <span className="text-error">存在适配问题</span>
                    )}
                  </div>
                  {result.sts_compatibility.issues && result.sts_compatibility.issues.length > 0 ? (
                    <ul className="mt-2 list-disc space-y-1 pl-4">
                      {result.sts_compatibility.issues.map((issue: string, index: number) => (
                        <li key={index}>{issue}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export function Extractor() {
  const [state, setState] = useState<ExtractionState>(extractionStore.getState());
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const unsubscribe = extractionStore.subscribe(setState);
    extractionStore.refreshTasks();
    return unsubscribe;
  }, []);

  const handleFile = (file: File) => {
    extractionStore.startUpload(file);
  };

  const onFileInput = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) handleFile(file);
    event.target.value = '';
  };

  const onDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    const file = event.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const reset = () => {
    extractionStore.reset();
  };

  const { stage, progress, message, fileInfo, result, pins, error, tasks, taskId } = state;
  const confidence = result ? calcConfidence(result) : 0;

  return (
    <div className="flex flex-col gap-8 animate-in slide-in-from-bottom-5 duration-500">
      <AnimatePresence mode="wait">
        {stage === 'idle' || stage === 'error' ? (
          <UploadZone
            key="upload"
            dragOver={dragOver}
            onDragOver={setDragOver}
            onDrop={onDrop}
            onFileSelect={() => fileInputRef.current?.click()}
            onFileInput={onFileInput}
            fileInputRef={fileInputRef}
            stage={stage}
            error={error}
            onReset={reset}
          />
        ) : null}

        {stage === 'uploading' || stage === 'extracting' ? (
          <div key="progress" className="grid grid-cols-1 gap-8 lg:grid-cols-12">
            <div className="lg:col-span-7">
              <ProgressView progress={progress} message={message} fileInfo={fileInfo} stage={stage} />
            </div>
            <div className="lg:col-span-5">
              <TaskCenter tasks={tasks} activeTaskId={taskId} />
            </div>
          </div>
        ) : null}

        {stage === 'done' ? (
          <ResultView
            key="result"
            result={result}
            fileInfo={fileInfo}
            pins={pins}
            tasks={tasks}
            activeTaskId={taskId}
            onReset={reset}
            confidence={confidence}
          />
        ) : null}
      </AnimatePresence>
    </div>
  );
}
