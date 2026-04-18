import React, { useState, useEffect, useCallback } from 'react';
import { Microscope, Activity, Download, Play, AlertTriangle, Thermometer, Cable,
         ChevronRight, Share2, ClipboardList, Loader2, RefreshCw, Cpu, Zap } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { runDiagnosis, type DiagnosisResult, type AnomalyEvent, type WaveformPoint } from '../api/backend';

// ─── 辅助：折叠数字动画 ────────────────────────────────────────
function AnimatedNumber({ value, decimals = 1 }: { value: number; decimals?: number }) {
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    const start = display;
    const end   = value;
    const dur   = 800;
    const t0    = Date.now();
    const tick  = () => {
      const p = Math.min(1, (Date.now() - t0) / dur);
      setDisplay(start + (end - start) * p);
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [value]);
  return <>{display.toFixed(decimals)}</>;
}

// ─── 波形 SVG ─────────────────────────────────────────────────
function WaveformSVG({ points }: { points: WaveformPoint[] }) {
  if (!points.length) return null;
  const W = 1000, H = 400, PAD = 20;
  const minV = Math.min(...points.map(p => p.v));
  const maxV = Math.max(...points.map(p => p.v));
  const vRange = maxV - minV || 1;

  const toX = (i: number) => PAD + (i / (points.length - 1)) * (W - PAD * 2);
  const toY = (v: number) => H - PAD - ((v - minV) / vRange) * (H - PAD * 2);

  const normalPath  = points.filter(p => !p.flag).map((p, i) => {
    const idx = points.indexOf(p);
    return `${idx === 0 ? 'M' : 'L'} ${toX(idx)},${toY(p.v)}`;
  }).join(' ');

  const anomalyPts = points.filter(p => p.flag);

  // Build continuous path
  const buildPath = (pts: WaveformPoint[]) => {
    let d = '';
    pts.forEach((p, i) => {
      const idx = points.indexOf(p);
      d += `${i === 0 ? 'M' : 'L'} ${toX(idx)},${toY(p.v)} `;
    });
    return d;
  };

  return (
    <svg className="absolute inset-0 w-full h-full" preserveAspectRatio="none" viewBox={`0 0 ${W} ${H}`}>
      {/* 背景网格 */}
      {[0,1,2,3].map(i => (
        <line key={i} x1={PAD} y1={PAD + i*(H-PAD*2)/3} x2={W-PAD} y2={PAD + i*(H-PAD*2)/3}
          stroke="#1e293b" strokeWidth="1" opacity="0.5" />
      ))}
      {/* 正常信号（青色） */}
      <path d={buildPath(points.filter(p => !p.flag))} fill="none"
        stroke="#53ddfc" strokeWidth="1.5" opacity="0.6" />
      {/* 异常区域高亮（橙色） */}
      {anomalyPts.map((p, i) => {
        const idx = points.indexOf(p);
        return (
          <circle key={i} cx={toX(idx)} cy={toY(p.v)} r="3"
            fill="#ffb148" className="drop-shadow-[0_0_6px_rgba(255,177,72,0.9)]" />
        );
      })}
      {/* 零线 */}
      <line x1={PAD} y1={toY(5.0)} x2={W-PAD} y2={toY(5.0)}
        stroke="#53ddfc" strokeWidth="0.5" strokeDasharray="4,4" opacity="0.3" />
    </svg>
  );
}

// ─── 故障严重度颜色 ────────────────────────────────────────────
const SEVERITY_STYLE = {
  high:   { color: 'text-error',     bg: 'bg-error/10',     border: 'border-error/20',     tag: '高概率', icon: Activity },
  medium: { color: 'text-tertiary',  bg: 'bg-tertiary/10',  border: 'border-tertiary/20',  tag: '中',     icon: Thermometer },
  low:    { color: 'text-secondary', bg: 'bg-secondary/10', border: 'border-secondary/20', tag: '低',     icon: Cable },
};

export function FailureAnalysis() {
  const [loading,    setLoading]    = useState(false);
  const [result,     setResult]     = useState<DiagnosisResult | null>(null);
  const [errMsg,     setErrMsg]     = useState('');
  const [autoRun,    setAutoRun]    = useState(false);

  const runAnalysis = useCallback(async () => {
    setLoading(true); setErrMsg('');
    try {
      const res = await runDiagnosis({ n_samples: 200, inject_anomaly: true, anomaly_ratio: 0.08 });
      if (res.status === 'success' && res.data) setResult(res.data);
      else setErrMsg(res.message || '诊断失败');
    } catch (e: any) {
      setErrMsg(e.message);
    } finally { setLoading(false); }
  }, []);

  // 首次自动运行
  useEffect(() => { runAnalysis(); }, []);

  // 自动刷新（30s）
  useEffect(() => {
    if (!autoRun) return;
    const id = setInterval(runAnalysis, 30000);
    return () => clearInterval(id);
  }, [autoRun, runAnalysis]);

  const exportLog = () => {
    if (!result) return;
    const text = JSON.stringify(result, null, 2);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
    a.download = `ATE_Diagnosis_${Date.now()}.json`;
    a.click();
  };

  return (
    <div className="flex flex-col gap-8 animate-in zoom-in-95 duration-500">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 relative">
        <div className="space-y-3">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-surface-container-high rounded-full border border-tertiary/20 shadow-lg shadow-tertiary/5">
            <div className={`w-2 h-2 rounded-full ${loading ? 'bg-primary animate-pulse' : autoRun ? 'bg-tertiary pulse-dot' : 'bg-surface-variant'}`} />
            <span className="text-[10px] font-mono font-bold text-tertiary uppercase tracking-[0.2em]">
              {loading ? 'ML 分析中...' : autoRun ? '实时监测活跃' : '已就绪'}
            </span>
          </div>
          <h1 className="text-5xl font-headline font-black text-on-surface tracking-tighter">失效源分析</h1>
          <p className="text-on-surface-variant text-sm font-sans max-w-2xl leading-relaxed opacity-80">
            IsolationForest 无监督异常检测 + 线性回归良率预测。
            {result && <span className="text-primary font-mono ml-2">耗时 {result.analysis_time_ms.toFixed(0)}ms · {result.model_backend}</span>}
          </p>
        </div>
        <div className="flex gap-4">
          <button onClick={exportLog} disabled={!result}
            className="px-6 py-3.5 rounded-2xl border border-outline-variant/30 bg-surface-container/30 hover:bg-surface-bright text-primary text-xs font-black tracking-[0.2em] uppercase flex items-center gap-2 transition-all disabled:opacity-40">
            <Download className="w-4 h-4" /> 导出分析日志
          </button>
          <button onClick={() => setAutoRun(v => !v)}
            className={`px-5 py-3.5 rounded-2xl border text-xs font-black tracking-[0.2em] uppercase flex items-center gap-2 transition-all ${
              autoRun ? 'bg-tertiary/20 border-tertiary/40 text-tertiary' : 'border-outline-variant/30 text-on-surface-variant'
            }`}>
            <RefreshCw className={`w-4 h-4 ${autoRun ? 'animate-spin' : ''}`} />
            {autoRun ? '停止自动刷新' : '自动刷新'}
          </button>
          <button onClick={runAnalysis} disabled={loading}
            className="px-7 py-3.5 rounded-2xl bg-primary text-on-primary text-xs font-black tracking-[0.2em] uppercase flex items-center gap-2 hover:brightness-110 shadow-2xl shadow-primary/20 transition-all disabled:opacity-60">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
            运行全量诊断
          </button>
        </div>
      </div>

      {errMsg && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="bg-error/10 border border-error/20 rounded-xl px-5 py-3 text-error text-sm">
          {errMsg}
        </motion.div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Waveform */}
        <div className="lg:col-span-8 bg-surface-container-low rounded-3xl relative overflow-hidden group shadow-2xl border border-outline-variant/10">
          <div className="p-8 pb-4 flex justify-between items-center z-10 relative">
            <div>
              <h2 className="text-xl font-headline font-bold text-on-surface flex items-center gap-3">
                <Activity className="w-6 h-6 text-primary" />
                VI 数字化仪迹线 - ML 仿真数据
              </h2>
              <span className="text-[10px] font-mono text-on-surface-variant font-bold tracking-[0.2em] mt-2 block opacity-60">
                CH1 VOLTAGE (V) · 10µs/div · {result?.sample_count ?? '—'} 采样点
              </span>
            </div>
            <div className="flex items-center gap-5 bg-surface-container-highest/60 px-5 py-2.5 rounded-2xl border border-primary/20 backdrop-blur-md">
              <span className="text-[10px] font-sans text-on-surface-variant font-bold uppercase tracking-widest opacity-70">异常率:</span>
              <span className="text-sm font-mono text-tertiary font-black">
                {result ? (result.anomaly_ratio * 100).toFixed(1) : '—'}%
              </span>
            </div>
          </div>

          <div className="relative h-[480px] w-full bg-[#030712] border-y border-outline-variant/10 overflow-hidden">
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:48px_48px] opacity-20" />
            {loading ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                  <Loader2 className="w-10 h-10 text-primary animate-spin" />
                  <span className="text-sm text-on-surface-variant font-mono">IsolationForest 分析中...</span>
                </div>
              </div>
            ) : result?.waveform.length ? (
              <>
                <WaveformSVG points={result.waveform} />
                {/* 异常区域标注 */}
                {result.anomalies.length > 0 && (
                  <div className="absolute left-[65%] top-0 w-[15%] h-full bg-tertiary/5 border-x border-tertiary/20">
                    <div className="absolute -top-0 left-1/2 -translate-x-1/2 bg-tertiary text-on-tertiary text-[9px] font-black px-3 py-1 rounded-b-full uppercase tracking-widest z-20 shadow-xl">
                      检测到异常
                    </div>
                  </div>
                )}
                {/* AI 分析气泡 */}
                {result.anomalies[0] && (
                  <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.4 }}
                    className="absolute top-1/4 right-6 w-72 bg-surface-container/85 backdrop-blur-2xl rounded-3xl border border-outline-variant/20 p-5 shadow-2xl">
                    <div className="flex items-start gap-4">
                      <AlertTriangle className="w-7 h-7 text-tertiary shrink-0 mt-0.5" />
                      <div className="space-y-2">
                        <h4 className="text-sm font-headline font-bold text-on-surface">
                          {result.anomalies[0].type === 'relay_degradation' ? '继电器退化' :
                           result.anomalies[0].type === 'thermal_drift'     ? '夹具热漂移' : '接触噪声'}
                        </h4>
                        <p className="text-[11px] text-on-surface-variant leading-relaxed">
                          {result.anomalies[0].description.slice(0, 80)}...
                        </p>
                        <div className="pt-3 border-t border-outline-variant/10 flex items-center justify-between text-[10px] font-mono text-tertiary font-bold">
                          <span>置信度: {(result.anomalies[0].confidence * 100).toFixed(0)}%</span>
                          <span className="bg-tertiary/10 px-2 py-0.5 rounded">
                            {result.anomalies[0].timestamp}
                          </span>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </>
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-on-surface-variant/40 text-sm">
                点击"运行全量诊断"启动分析
              </div>
            )}
          </div>

          <div className="p-5 px-8 flex justify-between items-center bg-surface-container-low/50">
            <div className="flex gap-8">
              <div className="flex items-center gap-3">
                <div className="w-4 h-0.5 bg-primary shadow-[0_0_8px_rgba(83,221,252,0.8)]" />
                <span className="text-[10px] font-mono font-bold text-on-surface-variant/70 uppercase">CH1 VOLTAGE (V)</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-4 h-0.5 bg-tertiary shadow-[0_0_8px_rgba(255,177,72,0.8)]" />
                <span className="text-[10px] font-mono font-bold text-on-surface-variant/70 uppercase">ANOMALY POINT</span>
              </div>
            </div>
            <span className="text-[10px] font-mono text-on-surface-variant/50">
              {result ? `ML Backend: ${result.model_backend}` : ''}
            </span>
          </div>
        </div>

        {/* Right Panel */}
        <div className="lg:col-span-4 flex flex-col gap-6">
          {/* KPI 卡 */}
          <section className="bg-surface-container p-8 rounded-3xl relative overflow-hidden border border-outline-variant/10 shadow-lg">
            <div className="absolute right-0 top-0 w-24 h-24 bg-primary/5 rounded-bl-full pointer-events-none" />
            <h3 className="text-xs font-sans font-bold text-on-surface-variant uppercase tracking-[0.2em] mb-6 opacity-60">生产能力重点指标</h3>
            <div className="flex items-baseline gap-3 mb-2">
              <span className="text-7xl font-headline font-black text-on-surface tracking-tighter">
                {result ? <AnimatedNumber value={result.fty_rolling} /> : '—'}
              </span>
              <span className="text-xl font-mono text-primary font-black">%</span>
            </div>
            <span className="text-[11px] font-sans font-bold text-on-surface-variant/70 tracking-widest uppercase block border-l-2 border-primary pl-3">
              一次通过率 (FTY) - 当前批次
            </span>
            <div className="mt-8 pt-6 border-t border-outline-variant/15 flex justify-between items-center">
              <div>
                <span className="text-[9px] font-mono text-on-surface-variant uppercase font-bold opacity-50 block mb-2">实时良率趋势</span>
                <span className={`text-sm font-mono font-black flex items-center gap-1 ${result && result.yield_trend < 0 ? 'text-error' : 'text-primary'}`}>
                  <Activity className="w-3 h-3 animate-pulse" />
                  {result ? `${result.yield_trend > 0 ? '+' : ''}${result.yield_trend.toFixed(2)}% /hr` : '—'}
                </span>
              </div>
              <div className="text-right">
                <span className="text-[9px] font-mono text-on-surface-variant uppercase font-bold opacity-50 block mb-2">AI 模型预测 (T+4H)</span>
                <span className="text-sm font-mono text-tertiary font-black">
                  {result ? `${result.yield_predicted.toFixed(1)}%` : '—'}
                </span>
              </div>
            </div>
          </section>

          {/* 故障溯源 */}
          <section className="bg-surface-container-low rounded-3xl flex-1 p-7 border border-outline-variant/10 shadow-sm flex flex-col gap-5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-headline font-bold text-on-surface flex items-center gap-3">
                <Microscope className="w-5 h-5 text-secondary" />
                AI 故障溯源诊断
              </h3>
              {result && (
                <span className="text-[9px] font-mono text-on-surface-variant/50">
                  {result.anomalies.length} 个事件
                </span>
              )}
            </div>

            <div className="flex flex-col gap-3 max-h-[380px] overflow-y-auto pr-1">
              <AnimatePresence>
                {loading ? (
                  <div className="flex items-center justify-center py-10">
                    <Loader2 className="w-8 h-8 animate-spin text-primary" />
                  </div>
                ) : result?.anomalies.length ? (
                  result.anomalies.map((a, i) => {
                    const style = SEVERITY_STYLE[a.severity] || SEVERITY_STYLE.low;
                    const Icon  = style.icon;
                    return (
                      <motion.div key={i}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: i * 0.12 }}
                        className="p-5 bg-surface-container-highest/50 rounded-2xl border border-outline-variant/10 hover:bg-surface-bright/40 transition-all cursor-pointer group">
                        <div className="flex items-start gap-4">
                          <div className={`p-2.5 rounded-xl ${style.bg} ${style.color} group-hover:scale-110 transition-transform`}>
                            <Icon className="w-5 h-5" />
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <h4 className="text-sm font-bold text-on-surface">
                                {a.type === 'relay_degradation' ? `继电器退化 (K${a.channel+1})` :
                                 a.type === 'thermal_drift'     ? '夹具热漂移' :
                                 a.type === 'contact_noise'     ? `探针接触噪声 CH${a.channel}` :
                                 a.type}
                              </h4>
                              <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase ${style.bg} ${style.color}`}>
                                {style.tag}
                              </span>
                            </div>
                            <p className="text-[11px] text-on-surface-variant leading-relaxed opacity-80 group-hover:opacity-100 italic">
                              {a.description}
                            </p>
                            <div className="mt-3 flex items-center justify-between">
                              <div>
                                <span className="text-[9px] text-on-surface-variant uppercase font-bold opacity-50">置信度</span>
                                <span className={`text-lg font-headline font-black tracking-tighter ml-2 ${style.color}`}>
                                  {(a.confidence * 100).toFixed(0)}%
                                </span>
                              </div>
                              <span className="text-[9px] font-mono text-on-surface-variant/40">{a.timestamp}</span>
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    );
                  })
                ) : !loading ? (
                  <div className="text-center py-10 text-on-surface-variant/40 text-sm">
                    点击"运行全量诊断"启动 ML 分析
                  </div>
                ) : null}
              </AnimatePresence>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
