import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Info,
  Loader2,
  Maximize,
  Network,
  RefreshCw,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { generateResourceMap, resolveBackendUrl, type ResourceMapResult } from '../api/backend';

const RESOURCE_PAGE_STORAGE_KEY = 'ate_resource_map_page_state';

function downloadFile(url: string, filename: string) {
  try {
    const anchor = document.createElement('a');
    anchor.style.display = 'none';
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    window.setTimeout(() => document.body.removeChild(anchor), 200);
  } catch (error) {
    console.error('下载失败:', error);
    window.alert(`下载失败，请检查后端连接：${error}`);
  }
}

function getStoredFileId(): string | null {
  const lastId = sessionStorage.getItem('ate_last_file_id');
  if (lastId) return lastId;

  try {
    const raw = sessionStorage.getItem('ate_extraction_store');
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed.fileInfo?.file_id || null;
  } catch {
    return null;
  }
}

type Stage = 'idle' | 'loading' | 'done' | 'error';

interface ResourceState {
  stage: Stage;
  result: ResourceMapResult | null;
  svgUrl: string;
  svgContent: string;
  error: string;
}

const INITIAL_STATE: ResourceState = {
  stage: 'idle',
  result: null,
  svgUrl: '',
  svgContent: '',
  error: '',
};

function readStoredResourceState(): ResourceState | null {
  try {
    const raw = window.sessionStorage.getItem(RESOURCE_PAGE_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ResourceState>;
    return {
      stage: parsed.stage === 'done' || parsed.stage === 'error' ? parsed.stage : 'idle',
      result: parsed.result || null,
      svgUrl: parsed.svgUrl || '',
      svgContent: parsed.svgContent || '',
      error: parsed.error || '',
    };
  } catch {
    return null;
  }
}

function persistResourceState(state: ResourceState) {
  try {
    window.sessionStorage.setItem(RESOURCE_PAGE_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore storage failures
  }
}

function clearStoredResourceState() {
  try {
    window.sessionStorage.removeItem(RESOURCE_PAGE_STORAGE_KEY);
  } catch {
    // ignore storage failures
  }
}

export function Resources() {
  const [state, setState] = useState<ResourceState>(() => {
    if (typeof window === 'undefined') return INITIAL_STATE;
    return readStoredResourceState() || INITIAL_STATE;
  });
  const [dualSite, setDualSite] = useState(false);
  const [fileId, setFileId] = useState<string | null>(null);
  const [manualFileId, setManualFileId] = useState('');

  const updateState = (patch: Partial<ResourceState>) => {
    setState(prev => ({ ...prev, ...patch }));
  };

  useEffect(() => {
    setFileId(getStoredFileId());
  }, []);

  useEffect(() => {
    if (state.stage === 'done' && state.result) {
      persistResourceState(state);
      return;
    }
    if (state.stage === 'error' && state.error) {
      persistResourceState(state);
      return;
    }
    if (state.stage === 'idle') {
      clearStoredResourceState();
    }
  }, [state]);

  const activeFileId = useMemo(() => fileId || manualFileId.trim(), [fileId, manualFileId]);

  const runGenerate = async (targetFileId: string) => {
    updateState({ stage: 'loading', error: '', result: null, svgUrl: '', svgContent: '' });

    try {
      const response = await generateResourceMap(targetFileId, dualSite);
      if (response.status !== 'success' || !response.data) {
        updateState({ stage: 'error', error: response.message || '资源映射生成失败' });
        return;
      }

      const svgUrl = resolveBackendUrl(response.data.download.schematic_svg);
      const result: ResourceMapResult = {
        ...response.data,
        download: {
          resource_map_excel: resolveBackendUrl(response.data.download.resource_map_excel),
          schematic_svg: svgUrl,
          bom_excel: resolveBackendUrl(response.data.download.bom_excel),
        },
      };

      let svgContent = '';
      try {
        const svgResponse = await fetch(svgUrl);
        if (svgResponse.ok) svgContent = await svgResponse.text();
      } catch {
        svgContent = '';
      }

      updateState({ stage: 'done', result, svgUrl, svgContent, error: '' });
    } catch (error: any) {
      updateState({ stage: 'error', error: error?.message || '网络错误' });
    }
  };

  const handleGenerate = () => {
    if (!activeFileId) {
      updateState({
        stage: 'error',
        error: '请先在“提取器”页面完成数据手册提取，或手动输入一个文件 ID。',
      });
      return;
    }
    void runGenerate(activeFileId);
  };

  const { stage, result, svgUrl, svgContent, error } = state;

  const idleView = (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-8">
      <section className="mb-2">
        <h1 className="mb-2 text-4xl font-headline font-bold tracking-tight text-primary">资源映射与原理图</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-on-surface-variant">
          基于模块一提取出的引脚定义，自动生成 ATE 资源分配方案、PGS 配置和负载板原理图草案。
        </p>
      </section>

      <div className="flex max-w-2xl flex-col gap-6 rounded-2xl border border-outline-variant/10 bg-surface-container-low p-8 shadow-lg">
        {fileId ? (
          <div className="flex items-center gap-4 rounded-xl border border-primary/20 bg-primary/10 p-5">
            <CheckCircle2 className="h-6 w-6 shrink-0 text-primary" />
            <div>
              <p className="text-sm font-bold text-on-surface">已检测到最近一次提取结果</p>
              <p className="mt-1 font-mono text-xs text-on-surface-variant">文件 ID: {fileId}</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3 rounded-xl border border-tertiary/20 bg-tertiary/10 p-4">
              <Info className="h-5 w-5 shrink-0 text-tertiary" />
              <p className="text-xs text-on-surface-variant">
                没有检测到提取结果。你可以先去“提取器”完成文档解析，或直接手动输入文件 ID。
              </p>
            </div>
            <input
              type="text"
              placeholder="手动输入文件 ID，例如 A1B2C3D4"
              value={manualFileId}
              onChange={event => setManualFileId(event.target.value)}
              className="rounded-xl border border-outline-variant/30 bg-surface-container-highest px-4 py-3 font-mono text-sm text-on-surface placeholder:text-on-surface-variant/40 focus:border-primary/50 focus:outline-none"
            />
          </div>
        )}

        <div className="flex items-center gap-4">
          <button
            onClick={() => setDualSite(value => !value)}
            className={`relative h-6 w-12 rounded-full transition-colors ${dualSite ? 'bg-primary' : 'bg-surface-container-highest'}`}
          >
            <div className={`absolute top-1 h-4 w-4 rounded-full bg-white shadow transition-all ${dualSite ? 'left-7' : 'left-1'}`} />
          </button>
          <span className="text-sm text-on-surface-variant">双工位模式，适合 LDO 或双站点验证场景</span>
        </div>

        <button
          onClick={handleGenerate}
          className="flex items-center justify-center gap-3 rounded-xl bg-primary px-8 py-4 text-sm font-bold uppercase tracking-widest text-on-primary shadow-lg shadow-primary/10 transition-all hover:brightness-110"
        >
          <Network className="h-5 w-5" />
          生成资源映射
        </button>

        {stage === 'error' ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-start gap-3 rounded-xl border border-error/20 bg-error/10 p-4">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-error" />
            <p className="text-sm text-on-surface-variant">{error}</p>
          </motion.div>
        ) : null}
      </div>
    </motion.div>
  );

  const loadingView = (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center justify-center gap-6 py-24">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary/10">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      </div>
      <div className="text-center">
        <p className="mb-2 font-headline text-xl font-bold text-on-surface">正在生成资源映射...</p>
        <p className="text-sm text-on-surface-variant">系统正在分析引脚定义、资源约束和下载产物。</p>
      </div>
    </motion.div>
  );

  const resultView =
    result && stage === 'done' ? (
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-8">
        <section className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <h1 className="mb-2 text-4xl font-headline font-bold tracking-tight text-primary">资源映射与原理图</h1>
            <p className="max-w-2xl text-sm leading-relaxed text-on-surface-variant">
              芯片 <span className="font-bold text-primary">{result.chip_name}</span>
              <span className="mx-2">|</span>
              类型 <span className="font-mono text-on-surface">{result.chip_type}</span>
              <span className="mx-2">|</span>
              适配器 <span className="font-mono text-secondary">{result.adapter}</span>
            </p>
          </div>

          <button
            onClick={() => {
              clearStoredResourceState();
              setState(INITIAL_STATE);
            }}
            className="flex items-center gap-2 rounded-xl border border-outline-variant/30 px-5 py-3 text-xs font-bold uppercase tracking-widest text-on-surface-variant transition-all hover:bg-surface-bright"
          >
            <RefreshCw className="h-4 w-4" />
            重新生成
          </button>
        </section>

        {result.warnings.length > 0 ? (
          <div className="flex flex-col gap-2">
            {result.warnings.map(warning => (
              <div key={warning} className="flex items-center gap-3 rounded-xl border border-tertiary/20 bg-tertiary/10 p-3 text-xs text-on-surface-variant">
                <AlertTriangle className="h-4 w-4 shrink-0 text-tertiary" />
                {warning}
              </div>
            ))}
          </div>
        ) : null}

        {result.run ? (
          <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.25em] text-primary">本次运行摘要</div>
                <h3 className="font-headline text-xl font-bold text-on-surface">资源映射结果已写入运行中心</h3>
                <p className="mt-1 text-sm text-on-surface-variant">
                  资源页保留主操作和下载视图，详细阶段和中间产物可以去“运行中心”回看。
                </p>
              </div>
              <div className="rounded-xl border border-outline-variant/10 bg-surface-container px-4 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">运行状态</div>
                <div className="mt-1 text-lg font-bold text-primary">
                  {result.run.status === 'completed' ? '已完成' : result.run.status === 'failed' ? '已阻断' : '进行中'}
                </div>
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-4">
              {[
                ['记录 ID', result.run.run_id.slice(-8), 'font-mono text-primary'],
                ['已完成阶段', result.run.steps.filter(step => step.status === 'completed').length, 'text-on-surface'],
                ['需关注阶段', result.run.steps.filter(step => step.status === 'failed').length, 'text-tertiary'],
                ['产物数', result.run.artifacts?.length ?? 0, 'text-on-surface'],
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
          <div className="flex flex-col gap-6 lg:col-span-4">
            <div className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-6 shadow-lg">
              <div className="mb-6 flex items-center justify-between">
                <h2 className="text-lg font-headline font-bold text-on-surface">映射结果</h2>
                <span
                  className={`rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-widest ${
                    result.pin_auto_loaded ? 'bg-primary/10 text-primary' : 'bg-tertiary/10 text-tertiary'
                  }`}
                >
                  {result.pin_auto_loaded ? '自动载入' : '手动文件 ID'}
                </span>
              </div>

              <div className="space-y-4">
                {[
                  { label: '已映射引脚', value: result.pin_count, unit: '个' },
                  { label: 'PGS 配置项', value: result.pgs_items, unit: '项' },
                ].map(item => (
                  <div key={item.label} className="flex items-center justify-between rounded-xl border border-outline-variant/5 bg-surface-container p-4">
                    <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant opacity-70">{item.label}</span>
                    <div className="flex items-baseline gap-1">
                      <span className="font-headline text-2xl font-bold tracking-tighter text-primary">{item.value}</span>
                      <span className="text-xs text-on-surface-variant">{item.unit}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {result.summary ? (
              <div className="rounded-2xl border border-secondary/15 bg-surface-container-low p-6 shadow-sm">
                <h3 className="mb-3 text-sm font-headline font-bold text-on-surface">复杂场景摘要</h3>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: '工位数量', value: result.summary.site_count },
                    { label: 'Power Rails', value: result.summary.power_pin_count },
                    { label: '双向 IO', value: result.summary.bidir_pin_count },
                    { label: '未分配', value: result.summary.unassigned_count },
                    { label: 'DIO SITE1', value: result.summary.dio_site1_count },
                    { label: 'DIO SITE2', value: result.summary.dio_site2_count },
                  ].map(item => (
                    <div key={item.label} className="rounded-xl border border-outline-variant/10 bg-surface-container p-3 text-center">
                      <div className="font-headline text-xl font-bold text-secondary">{item.value}</div>
                      <div className="mt-1 text-[10px] uppercase tracking-widest text-on-surface-variant/60">{item.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="flex flex-col gap-3 rounded-2xl border border-outline-variant/10 bg-surface-container-low p-6 shadow-sm">
              <h3 className="mb-2 flex items-center gap-2 text-sm font-headline font-bold text-on-surface">
                <Download className="h-4 w-4 text-primary" />
                下载产物
              </h3>

              {[
                {
                  label: '资源映射表 Excel',
                  url: result.download.resource_map_excel,
                  filename: `${result.chip_name}_ResourceMap.xlsx`,
                },
                {
                  label: '原理图 SVG',
                  url: result.download.schematic_svg,
                  filename: `${result.chip_name}_Schematic.svg`,
                },
                {
                  label: 'BOM 清单 Excel',
                  url: result.download.bom_excel,
                  filename: `${result.chip_name}_BOM.xlsx`,
                },
              ].map(item => (
                <button
                  key={item.label}
                  onClick={() => downloadFile(item.url, item.filename)}
                  className="group flex w-full items-center justify-between rounded-xl border border-outline-variant/10 bg-surface-container p-3.5 text-left text-sm transition-all hover:border-primary/30 hover:bg-primary/10"
                >
                  <span className="font-medium text-on-surface">{item.label}</span>
                  <Download className="h-4 w-4 text-primary transition-transform group-hover:scale-110" />
                </button>
              ))}
            </div>
          </div>

          <div className="lg:col-span-8">
            <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-outline-variant/10 bg-surface-container-low shadow-2xl">
              <div className="flex items-center justify-between border-b border-outline-variant/10 bg-surface-container px-6 py-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-primary/10 p-2">
                    <Network className="h-5 w-5 text-primary" />
                  </div>
                  <h2 className="text-lg font-headline font-bold text-on-surface">AI 生成原理图预览</h2>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex items-center rounded-xl border border-outline-variant/20 bg-surface-container-highest p-1">
                    <button className="p-2 text-on-surface-variant transition-colors hover:text-primary">
                      <ZoomOut className="h-4 w-4" />
                    </button>
                    <button className="border-l border-outline-variant/10 p-2 text-on-surface-variant transition-colors hover:text-primary">
                      <ZoomIn className="h-4 w-4" />
                    </button>
                    <button className="border-l border-outline-variant/10 p-2 text-on-surface-variant transition-colors hover:text-primary">
                      <Maximize className="h-4 w-4" />
                    </button>
                  </div>

                  <button
                    onClick={() => downloadFile(result.download.schematic_svg, `${result.chip_name}_Schematic.svg`)}
                    className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-xs font-bold uppercase tracking-widest text-on-primary transition-all hover:brightness-110"
                  >
                    <Download className="h-4 w-4" />
                    导出 SVG
                  </button>
                </div>
              </div>

              <div className="relative flex min-h-[500px] flex-1 items-center justify-center overflow-hidden bg-surface-container-lowest p-10">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,#192540_1px,transparent_1px)] bg-[size:30px_30px] opacity-20" />

                {svgContent ? (
                  <div
                    className="flex h-full min-h-[480px] w-full items-center justify-center overflow-auto p-4"
                    dangerouslySetInnerHTML={{ __html: svgContent }}
                  />
                ) : svgUrl ? (
                  <div className="relative flex h-full w-full max-w-2xl flex-col items-center justify-center rounded-2xl border border-outline-variant/20 bg-surface-container/10 p-8">
                    <AlertTriangle className="mb-4 h-10 w-10 text-tertiary" />
                    <p className="text-sm text-on-surface-variant">SVG 预览加载失败</p>
                    <button
                      onClick={() => downloadFile(svgUrl, `${result.chip_name}_Schematic.svg`)}
                      className="mt-4 text-xs text-primary underline"
                    >
                      点击直接下载 SVG 文件
                    </button>
                  </div>
                ) : (
                  <div className="relative flex h-full w-full max-w-2xl flex-col items-center justify-center rounded-2xl border border-outline-variant/20 bg-surface-container/10 p-8">
                    <svg viewBox="0 0 400 200" className="h-auto w-full opacity-80 drop-shadow-2xl">
                      <path d="M50 100 L150 100" stroke="#53ddfc" strokeWidth="2" strokeLinecap="round" />
                      <path d="M150 70 L200 100 L150 130 Z" fill="rgba(83, 221, 252, 0.05)" stroke="#699cff" strokeWidth="2" />
                      <path d="M200 100 L300 100" stroke="#53ddfc" strokeWidth="2" strokeLinecap="round" />
                      <path d="M250 100 L250 40 L120 40 L120 80" stroke="#53ddfc" strokeDasharray="6 6" strokeWidth="1.5" />
                      <circle cx="120" cy="80" r="3" fill="#53ddfc" />
                      <circle cx="250" cy="100" r="3" fill="#53ddfc" />
                      <circle cx="300" cy="100" r="4" fill="#699cff" />
                      <text x="45" y="90" fill="#a3aac4" fontSize="10" fontFamily="Inter">
                        DPS_Force
                      </text>
                      <text x="260" y="90" fill="#a3aac4" fontSize="10" fontFamily="Inter">
                        DUT_Pin_1
                      </text>
                      <text x="170" y="30" fill="#ffb148" fontSize="11" fontFamily="Inter" fontWeight="bold">
                        Kelvin Sense
                      </text>
                    </svg>
                    <p className="mt-4 text-xs text-on-surface-variant/50">原理图预览加载中...</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    ) : null;

  return (
    <div className="animate-in slide-in-from-right-5 flex flex-col gap-8 duration-500">
      <AnimatePresence mode="wait">
        {(stage === 'idle' || stage === 'error') && <motion.div key="idle">{idleView}</motion.div>}
        {stage === 'loading' && <motion.div key="loading">{loadingView}</motion.div>}
        {stage === 'done' && <motion.div key="done">{resultView}</motion.div>}
      </AnimatePresence>
    </div>
  );
}
