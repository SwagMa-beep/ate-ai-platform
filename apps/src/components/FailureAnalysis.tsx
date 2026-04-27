import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Cable,
  Download,
  Loader2,
  Microscope,
  Play,
  RefreshCw,
  Thermometer,
} from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { runDiagnosis, type DiagnosisResult, type WaveformPoint } from '../api/backend';

function AnimatedNumber({ value, decimals = 1 }: { value: number; decimals?: number }) {
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    const start = display;
    const end = value;
    const duration = 800;
    const startTime = Date.now();

    const tick = () => {
      const progress = Math.min(1, (Date.now() - startTime) / duration);
      setDisplay(start + (end - start) * progress);
      if (progress < 1) {
        requestAnimationFrame(tick);
      }
    };

    requestAnimationFrame(tick);
  }, [display, value]);

  return <>{display.toFixed(decimals)}</>;
}

function WaveformSVG({ points }: { points: WaveformPoint[] }) {
  if (!points.length) {
    return null;
  }

  const width = 1000;
  const height = 400;
  const padding = 20;
  const minVoltage = Math.min(...points.map((point) => point.v));
  const maxVoltage = Math.max(...points.map((point) => point.v));
  const voltageRange = maxVoltage - minVoltage || 1;

  const toX = (index: number) => padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
  const toY = (voltage: number) => height - padding - ((voltage - minVoltage) / voltageRange) * (height - padding * 2);

  const buildPath = (dataset: WaveformPoint[]) =>
    dataset
      .map((point, index) => {
        const realIndex = points.indexOf(point);
        return `${index === 0 ? 'M' : 'L'} ${toX(realIndex)},${toY(point.v)}`;
      })
      .join(' ');

  const anomalyPoints = points.filter((point) => point.flag);

  return (
    <svg className="absolute inset-0 h-full w-full" preserveAspectRatio="none" viewBox={`0 0 ${width} ${height}`}>
      {[0, 1, 2, 3].map((row) => (
        <line
          key={row}
          x1={padding}
          y1={padding + (row * (height - padding * 2)) / 3}
          x2={width - padding}
          y2={padding + (row * (height - padding * 2)) / 3}
          stroke="#1e293b"
          strokeWidth="1"
          opacity="0.5"
        />
      ))}

      <path d={buildPath(points.filter((point) => !point.flag))} fill="none" stroke="#53ddfc" strokeWidth="1.5" opacity="0.6" />

      {anomalyPoints.map((point, index) => {
        const realIndex = points.indexOf(point);
        return (
          <circle
            key={`${point.t}-${index}`}
            cx={toX(realIndex)}
            cy={toY(point.v)}
            r="3"
            fill="#ffb148"
            className="drop-shadow-[0_0_6px_rgba(255,177,72,0.9)]"
          />
        );
      })}

      <line
        x1={padding}
        y1={toY(5.0)}
        x2={width - padding}
        y2={toY(5.0)}
        stroke="#53ddfc"
        strokeWidth="0.5"
        strokeDasharray="4,4"
        opacity="0.3"
      />
    </svg>
  );
}

const SEVERITY_STYLE = {
  high: {
    color: 'text-error',
    bg: 'bg-error/10',
    tag: '高',
    icon: Activity,
  },
  medium: {
    color: 'text-tertiary',
    bg: 'bg-tertiary/10',
    tag: '中',
    icon: Thermometer,
  },
  low: {
    color: 'text-secondary',
    bg: 'bg-secondary/10',
    tag: '低',
    icon: Cable,
  },
} as const;

function formatAnomalyType(type: string, channel: number) {
  if (type === 'relay_degradation') {
    return `继电器退化 K${channel + 1}`;
  }
  if (type === 'thermal_drift') {
    return '夹具热漂移';
  }
  if (type === 'contact_noise') {
    return `探针接触噪声 CH${channel}`;
  }
  return type;
}

export function FailureAnalysis() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiagnosisResult | null>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);

  const runAnalysis = useCallback(async () => {
    setLoading(true);
    setErrorMessage('');

    try {
      const response = await runDiagnosis({ n_samples: 200, inject_anomaly: true, anomaly_ratio: 0.08 });
      if (response.status === 'success' && response.data) {
        setResult(response.data);
      } else {
        setErrorMessage(response.message || '诊断失败');
      }
    } catch (error: any) {
      setErrorMessage(error?.message || '诊断请求失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    runAnalysis();
  }, [runAnalysis]);

  useEffect(() => {
    if (!autoRefresh) {
      return;
    }
    const timer = window.setInterval(runAnalysis, 30000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, runAnalysis]);

  const exportLog = () => {
    if (!result) {
      return;
    }
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const anchor = document.createElement('a');
    anchor.href = URL.createObjectURL(blob);
    anchor.download = `ATE_Diagnosis_${Date.now()}.json`;
    anchor.click();
  };

  const anomalyRatio = result ? (result.anomaly_ratio * 100).toFixed(1) : '--';

  return (
    <div className="animate-in zoom-in-95 flex flex-col gap-8 duration-500">
      <div className="relative flex flex-col justify-between gap-6 md:flex-row md:items-end">
        <div className="space-y-3">
          <div className="inline-flex items-center gap-2 rounded-full border border-tertiary/20 bg-surface-container-high px-4 py-1.5 shadow-lg shadow-tertiary/5">
            <div
              className={`h-2 w-2 rounded-full ${
                loading ? 'animate-pulse bg-primary' : autoRefresh ? 'pulse-dot bg-tertiary' : 'bg-surface-variant'
              }`}
            />
            <span className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-tertiary">
              {loading ? 'ML 分析中' : autoRefresh ? '实时监测中' : '已就绪'}
            </span>
          </div>

          <h1 className="font-headline text-5xl font-black tracking-tighter text-on-surface">故障诊断</h1>
          <p className="max-w-2xl text-sm leading-relaxed text-on-surface-variant opacity-80">
            基于 IsolationForest 的异常检测和良率趋势分析，适合演示机台波形、接触异常和热漂移等风险场景。
            {result && (
              <span className="ml-2 font-mono text-primary">
                耗时 {result.analysis_time_ms.toFixed(0)}ms | {result.model_backend}
              </span>
            )}
          </p>
        </div>

        <div className="flex flex-wrap gap-4">
          <button
            onClick={exportLog}
            disabled={!result}
            className="flex items-center gap-2 rounded-2xl border border-outline-variant/30 bg-surface-container/30 px-6 py-3.5 text-xs font-black uppercase tracking-[0.2em] text-primary transition-all hover:bg-surface-bright disabled:opacity-40"
          >
            <Download className="h-4 w-4" />
            导出分析日志
          </button>

          <button
            onClick={() => setAutoRefresh((value) => !value)}
            className={`flex items-center gap-2 rounded-2xl border px-5 py-3.5 text-xs font-black uppercase tracking-[0.2em] transition-all ${
              autoRefresh ? 'border-tertiary/40 bg-tertiary/20 text-tertiary' : 'border-outline-variant/30 text-on-surface-variant'
            }`}
          >
            <RefreshCw className={`h-4 w-4 ${autoRefresh ? 'animate-spin' : ''}`} />
            {autoRefresh ? '停止自动刷新' : '自动刷新'}
          </button>

          <button
            onClick={runAnalysis}
            disabled={loading}
            className="flex items-center gap-2 rounded-2xl bg-primary px-7 py-3.5 text-xs font-black uppercase tracking-[0.2em] text-on-primary shadow-2xl shadow-primary/20 transition-all hover:brightness-110 disabled:opacity-60"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-current" />}
            运行全量诊断
          </button>
        </div>
      </div>

      {errorMessage && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="rounded-xl border border-error/20 bg-error/10 px-5 py-3 text-sm text-error">
          {errorMessage}
        </motion.div>
      )}

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        <div className="group relative overflow-hidden rounded-3xl border border-outline-variant/10 bg-surface-container-low shadow-2xl lg:col-span-8">
          <div className="relative z-10 flex items-center justify-between p-8 pb-4">
            <div>
              <h2 className="flex items-center gap-3 text-xl font-headline font-bold text-on-surface">
                <Activity className="h-6 w-6 text-primary" />
                VI 数字化波形
              </h2>
              <span className="mt-2 block font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-on-surface-variant opacity-60">
                CH1 VOLTAGE (V) | 10us/div | {result?.sample_count ?? '--'} 采样点
              </span>
            </div>

            <div className="flex items-center gap-5 rounded-2xl border border-primary/20 bg-surface-container-highest/60 px-5 py-2.5 backdrop-blur-md">
              <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant opacity-70">异常率</span>
              <span className="font-mono text-sm font-black text-tertiary">{anomalyRatio}%</span>
            </div>
          </div>

          <div className="relative h-[480px] w-full overflow-hidden border-y border-outline-variant/10 bg-[#030712]">
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:48px_48px] opacity-20" />

            {loading ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                  <Loader2 className="h-10 w-10 animate-spin text-primary" />
                  <span className="font-mono text-sm text-on-surface-variant">IsolationForest 分析中...</span>
                </div>
              </div>
            ) : result?.waveform.length ? (
              <>
                <WaveformSVG points={result.waveform} />

                {result.anomalies.length > 0 && (
                  <div className="absolute left-[65%] top-0 h-full w-[15%] border-x border-tertiary/20 bg-tertiary/5">
                    <div className="absolute left-1/2 top-0 z-20 -translate-x-1/2 rounded-b-full bg-tertiary px-3 py-1 text-[9px] font-black uppercase tracking-widest text-on-tertiary shadow-xl">
                      检测到异常
                    </div>
                  </div>
                )}

                {result.anomalies[0] && (
                  <motion.div
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.4 }}
                    className="absolute right-6 top-1/4 w-72 rounded-3xl border border-outline-variant/20 bg-surface-container/85 p-5 shadow-2xl backdrop-blur-2xl"
                  >
                    <div className="flex items-start gap-4">
                      <AlertTriangle className="mt-0.5 h-7 w-7 shrink-0 text-tertiary" />
                      <div className="space-y-2">
                        <h4 className="text-sm font-headline font-bold text-on-surface">
                          {formatAnomalyType(result.anomalies[0].type, result.anomalies[0].channel)}
                        </h4>
                        <p className="text-[11px] leading-relaxed text-on-surface-variant">
                          {result.anomalies[0].description.slice(0, 80)}...
                        </p>
                        <div className="flex items-center justify-between border-t border-outline-variant/10 pt-3 font-mono text-[10px] font-bold text-tertiary">
                          <span>置信度 {(result.anomalies[0].confidence * 100).toFixed(0)}%</span>
                          <span className="rounded bg-tertiary/10 px-2 py-0.5">{result.anomalies[0].timestamp}</span>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </>
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-sm text-on-surface-variant/40">
                点击“运行全量诊断”开始分析
              </div>
            )}
          </div>

          <div className="flex items-center justify-between bg-surface-container-low/50 p-5 px-8">
            <div className="flex gap-8">
              <div className="flex items-center gap-3">
                <div className="h-0.5 w-4 bg-primary shadow-[0_0_8px_rgba(83,221,252,0.8)]" />
                <span className="font-mono text-[10px] font-bold uppercase text-on-surface-variant/70">CH1 VOLTAGE (V)</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="h-0.5 w-4 bg-tertiary shadow-[0_0_8px_rgba(255,177,72,0.8)]" />
                <span className="font-mono text-[10px] font-bold uppercase text-on-surface-variant/70">ANOMALY POINT</span>
              </div>
            </div>
            <span className="font-mono text-[10px] text-on-surface-variant/50">
              {result ? `ML Backend: ${result.model_backend}` : ''}
            </span>
          </div>
        </div>

        <div className="flex flex-col gap-6 lg:col-span-4">
          <section className="relative overflow-hidden rounded-3xl border border-outline-variant/10 bg-surface-container p-8 shadow-lg">
            <div className="pointer-events-none absolute right-0 top-0 h-24 w-24 rounded-bl-full bg-primary/5" />
            <h3 className="mb-6 text-xs font-bold uppercase tracking-[0.2em] text-on-surface-variant opacity-60">良率关键指标</h3>
            <div className="mb-2 flex items-baseline gap-3">
              <span className="font-headline text-7xl font-black tracking-tighter text-on-surface">
                {result ? <AnimatedNumber value={result.fty_rolling} /> : '--'}
              </span>
              <span className="font-mono text-xl font-black text-primary">%</span>
            </div>
            <span className="block border-l-2 border-primary pl-3 text-[11px] font-bold uppercase tracking-widest text-on-surface-variant/70">
              当前批次一次通过率 FTY
            </span>

            <div className="mt-8 flex items-center justify-between border-t border-outline-variant/15 pt-6">
              <div>
                <span className="mb-2 block font-mono text-[9px] font-bold uppercase text-on-surface-variant opacity-50">实时良率趋势</span>
                <span
                  className={`flex items-center gap-1 font-mono text-sm font-black ${
                    result && result.yield_trend < 0 ? 'text-error' : 'text-primary'
                  }`}
                >
                  <Activity className="h-3 w-3 animate-pulse" />
                  {result ? `${result.yield_trend > 0 ? '+' : ''}${result.yield_trend.toFixed(2)}% /hr` : '--'}
                </span>
              </div>

              <div className="text-right">
                <span className="mb-2 block font-mono text-[9px] font-bold uppercase text-on-surface-variant opacity-50">AI 预测 T+4H</span>
                <span className="font-mono text-sm font-black text-tertiary">
                  {result ? `${result.yield_predicted.toFixed(1)}%` : '--'}
                </span>
              </div>
            </div>
          </section>

          <section className="flex flex-1 flex-col gap-5 rounded-3xl border border-outline-variant/10 bg-surface-container-low p-7 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="flex items-center gap-3 text-sm font-headline font-bold text-on-surface">
                <Microscope className="h-5 w-5 text-secondary" />
                AI 故障溯源
              </h3>
              {result && <span className="font-mono text-[9px] text-on-surface-variant/50">{result.anomalies.length} 个事件</span>}
            </div>

            <div className="max-h-[380px] space-y-3 overflow-y-auto pr-1">
              <AnimatePresence>
                {loading ? (
                  <div className="flex justify-center py-10">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  </div>
                ) : result?.anomalies.length ? (
                  result.anomalies.map((anomaly, index) => {
                    const style = SEVERITY_STYLE[anomaly.severity] || SEVERITY_STYLE.low;
                    const Icon = style.icon;
                    return (
                      <motion.div
                        key={`${anomaly.timestamp}-${index}`}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: index * 0.12 }}
                        className="group cursor-pointer rounded-2xl border border-outline-variant/10 bg-surface-container-highest/50 p-5 transition-all hover:bg-surface-bright/40"
                      >
                        <div className="flex items-start gap-4">
                          <div className={`rounded-xl p-2.5 transition-transform group-hover:scale-110 ${style.bg} ${style.color}`}>
                            <Icon className="h-5 w-5" />
                          </div>
                          <div className="flex-1">
                            <div className="mb-2 flex items-center gap-2">
                              <h4 className="text-sm font-bold text-on-surface">{formatAnomalyType(anomaly.type, anomaly.channel)}</h4>
                              <span className={`rounded px-2 py-0.5 text-[9px] font-bold uppercase ${style.bg} ${style.color}`}>
                                {style.tag}
                              </span>
                            </div>
                            <p className="text-[11px] italic leading-relaxed text-on-surface-variant opacity-80 group-hover:opacity-100">
                              {anomaly.description}
                            </p>
                            <div className="mt-3 flex items-center justify-between">
                              <div>
                                <span className="text-[9px] font-bold uppercase text-on-surface-variant opacity-50">置信度</span>
                                <span className={`ml-2 font-headline text-lg font-black tracking-tighter ${style.color}`}>
                                  {(anomaly.confidence * 100).toFixed(0)}%
                                </span>
                              </div>
                              <span className="font-mono text-[9px] text-on-surface-variant/40">{anomaly.timestamp}</span>
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    );
                  })
                ) : (
                  <div className="py-10 text-center text-sm text-on-surface-variant/40">点击“运行全量诊断”开始 ML 分析</div>
                )}
              </AnimatePresence>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
