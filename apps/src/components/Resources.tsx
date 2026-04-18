import React, { useState, useEffect, useRef } from 'react';
import {
  Network, Download, ZoomIn, ZoomOut, Maximize,
  Loader2, AlertTriangle, CheckCircle2, RefreshCw, Info,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { generateResourceMap, type ResourceMapResult } from '../api/backend';

/**
 * 直接触发浏览器下载，不经过 fetch
 * 同源 URL 下 browser 会尊重 download 属性指定的文件名
 */
function downloadFile(url: string, filename: string) {
  try {
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => document.body.removeChild(a), 200);
  } catch (err) {
    console.error('下载失败:', err);
    alert(`下载失败，请检查后端连接：${err}`);
  }
}

// ─── 工具：从 sessionStorage 获取上次提取的 file_id ─────────
function getStoredFileId(): string | null {
  const lastId = sessionStorage.getItem('ate_last_file_id');
  if (lastId) return lastId;

  // 备选方案：从全局提取状态中尝试恢复
  try {
    const store = sessionStorage.getItem('ate_extraction_store');
    if (store) {
      const data = JSON.parse(store);
      if (data.fileInfo?.file_id) return data.fileInfo.file_id;
    }
  } catch (e) {}
  return null;
}

type Stage = 'idle' | 'loading' | 'done' | 'error';

interface State {
  stage: Stage;
  result: ResourceMapResult | null;
  svgUrl: string;      // 仅用于下载
  svgContent: string;  // SVG 文本内容，用于内嵌预览
  error: string;
}

const INITIAL: State = { stage: 'idle', result: null, svgUrl: '', svgContent: '', error: '' };

export function Resources() {
  const [state, setState] = useState<State>(INITIAL);
  const [dualSite, setDualSite] = useState(false);
  const [fileId, setFileId] = useState<string | null>(null);
  const [manualFileId, setManualFileId] = useState('');

  const update = (patch: Partial<State>) =>
    setState(prev => ({ ...prev, ...patch }));

  // 初始化：尝试从 sessionStorage 获取 file_id
  useEffect(() => {
    const id = getStoredFileId();
    setFileId(id);
  }, []);

  const runGenerate = async (id: string) => {
    update({ stage: 'loading', error: '', result: null, svgUrl: '', svgContent: '' });
    try {
      const res = await generateResourceMap(id, dualSite);
      if (res.status === 'success' && res.data) {
        const svgUrl = res.data.download.schematic_svg;
        // 预加载 SVG 文本内容用于内嵌预览
        let svgContent = '';
        try {
          const svgResp = await fetch(svgUrl);
          if (svgResp.ok) svgContent = await svgResp.text();
        } catch {
          // SVG 预览失败不影响主功能
        }
        update({ stage: 'done', result: res.data, svgUrl, svgContent });
      } else {
        update({ stage: 'error', error: res.message || '生成失败' });
      }
    } catch (e: any) {
      update({ stage: 'error', error: e.message || '网络错误' });
    }
  };

  const handleGenerate = () => {
    const id = fileId || manualFileId.trim();
    if (!id) {
      update({ stage: 'error', error: '请先在"数据手册提取"页面上传并提取一份 Datasheet，或手动输入 file_id' });
      return;
    }
    runGenerate(id);
  };

  const { stage, result, svgUrl, svgContent, error } = state;

  // ─── 空状态 / 输入 file_id ────────────────────────────────
  const IdleView = () => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col gap-8"
    >
      <section className="mb-2">
        <h1 className="text-4xl font-headline font-bold text-primary tracking-tight mb-2">资源映射 & 原理图</h1>
        <p className="text-on-surface-variant font-sans text-sm max-w-2xl leading-relaxed">
          基于模块①提取的引脚定义，自动生成 ATE 仪器资源分配方案与负载板原理图。
        </p>
      </section>

      <div className="bg-surface-container-low rounded-2xl p-8 border border-outline-variant/10 shadow-lg flex flex-col gap-6 max-w-2xl">
        {fileId ? (
          <div className="flex items-center gap-4 p-5 bg-primary/10 border border-primary/20 rounded-xl">
            <CheckCircle2 className="w-6 h-6 text-primary shrink-0" />
            <div>
              <p className="text-sm font-bold text-on-surface">已检测到提取结果</p>
              <p className="text-xs text-on-surface-variant font-mono mt-1">file_id: {fileId}</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3 p-4 bg-tertiary/10 border border-tertiary/20 rounded-xl">
              <Info className="w-5 h-5 text-tertiary shrink-0" />
              <p className="text-xs text-on-surface-variant">
                未检测到上次提取结果，请先在「数据手册提取」完成分析，或手动输入 file_id
              </p>
            </div>
            <input
              type="text"
              placeholder="手动输入 file_id（如：a1b2c3d4）"
              value={manualFileId}
              onChange={e => setManualFileId(e.target.value)}
              className="bg-surface-container-highest border border-outline-variant/30 rounded-xl px-4 py-3 text-sm font-mono text-on-surface placeholder-on-surface-variant/40 focus:outline-none focus:border-primary/50 transition-colors"
            />
          </div>
        )}

        {/* 双工位选项 */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => setDualSite(!dualSite)}
            className={`w-12 h-6 rounded-full transition-colors relative ${dualSite ? 'bg-primary' : 'bg-surface-container-highest'}`}
          >
            <div className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-all ${dualSite ? 'left-7' : 'left-1'}`} />
          </button>
          <span className="text-sm font-sans text-on-surface-variant">双工位模式（LDO 场景）</span>
        </div>

        <button
          onClick={handleGenerate}
          className="bg-primary text-on-primary font-sans font-bold text-sm uppercase tracking-widest px-8 py-4 rounded-xl flex items-center justify-center gap-3 hover:brightness-110 shadow-lg shadow-primary/10 transition-all"
        >
          <Network className="w-5 h-5" />
          生成资源映射
        </button>

        {stage === 'error' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-start gap-3 p-4 bg-error/10 border border-error/20 rounded-xl"
          >
            <AlertTriangle className="w-5 h-5 text-error shrink-0 mt-0.5" />
            <p className="text-sm text-on-surface-variant">{error}</p>
          </motion.div>
        )}
      </div>
    </motion.div>
  );

  // ─── 加载中 ───────────────────────────────────────────────
  const LoadingView = () => (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col items-center justify-center gap-6 py-24"
    >
      <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
        <Loader2 className="w-10 h-10 text-primary animate-spin" />
      </div>
      <div className="text-center">
        <p className="font-headline text-xl font-bold text-on-surface mb-2">正在生成资源映射...</p>
        <p className="text-on-surface-variant text-sm">AI 正在分析引脚定义并分配 ATE 仪器资源</p>
      </div>
    </motion.div>
  );

  // ─── 结果展示 ─────────────────────────────────────────────
  const ResultView = () => {
    if (!result) return null;
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-8"
      >
        {/* 头部 */}
        <section className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-4xl font-headline font-bold text-primary tracking-tight mb-2">资源映射 & 原理图</h1>
            <p className="text-on-surface-variant font-sans text-sm max-w-2xl leading-relaxed">
              芯片 <span className="text-primary font-bold">{result.chip_name}</span> ·
              类型 <span className="font-mono text-on-surface">{result.chip_type}</span> ·
              适配器 <span className="font-mono text-secondary">{result.adapter}</span>
            </p>
          </div>
          <button
            onClick={() => setState(INITIAL)}
            className="flex items-center gap-2 px-5 py-3 rounded-xl border border-outline-variant/30 text-on-surface-variant text-xs font-bold uppercase tracking-widest hover:bg-surface-bright transition-all"
          >
            <RefreshCw className="w-4 h-4" /> 重新生成
          </button>
        </section>

        {/* 警告 */}
        {result.warnings.length > 0 && (
          <div className="flex flex-col gap-2">
            {result.warnings.map((w, i) => (
              <div key={i} className="flex items-center gap-3 p-3 bg-tertiary/10 border border-tertiary/20 rounded-xl text-xs text-on-surface-variant">
                <AlertTriangle className="w-4 h-4 text-tertiary shrink-0" /> {w}
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* 统计卡 */}
          <div className="lg:col-span-4 flex flex-col gap-6">
            <div className="bg-surface-container-low rounded-2xl p-6 border border-outline-variant/10 shadow-lg">
              <div className="absolute top-0 left-0 w-full h-full hero-glow pointer-events-none" />

              <div className="flex justify-between items-center mb-6">
                <h2 className="text-lg font-headline font-bold text-on-surface">映射结果</h2>
                <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest ${
                  result.pin_auto_loaded
                    ? 'bg-primary/10 text-primary'
                    : 'bg-tertiary/10 text-tertiary'
                }`}>
                  {result.pin_auto_loaded ? '自动加载' : '手动上传'}
                </span>
              </div>

              <div className="space-y-4">
                {[
                  { label: '已映射引脚', value: result.pin_count, unit: '个' },
                  { label: 'PGS 配置项', value: result.pgs_items, unit: '项' },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between p-4 bg-surface-container rounded-xl border border-outline-variant/5">
                    <span className="text-xs font-sans text-on-surface-variant uppercase tracking-widest font-bold opacity-70">{item.label}</span>
                    <div className="flex items-baseline gap-1">
                      <span className="font-headline text-2xl font-bold text-primary tracking-tighter">{item.value}</span>
                      <span className="text-xs text-on-surface-variant">{item.unit}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 下载区 */}
            <div className="bg-surface-container-low rounded-2xl p-6 border border-outline-variant/10 shadow-sm flex flex-col gap-3">
              <h3 className="text-sm font-headline font-bold text-on-surface mb-2 flex items-center gap-2">
                <Download className="w-4 h-4 text-primary" /> 下载文件
              </h3>
              {[
                { label: '资源映射 Excel', url: result.download.resource_map_excel, filename: `${result.chip_name}_ResourceMap.xlsx` },
                { label: 'SVG 原理图',     url: result.download.schematic_svg,      filename: `${result.chip_name}_Schematic.svg` },
                { label: 'BOM 清单 Excel', url: result.download.bom_excel,          filename: `${result.chip_name}_BOM.xlsx` },
              ].map((item, i) => (
                <button
                  key={i}
                  onClick={() => downloadFile(item.url, item.filename)}
                  className="flex items-center justify-between p-3.5 bg-surface-container hover:bg-primary/10 rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-all group text-sm w-full text-left"
                >
                  <span className="font-sans font-medium text-on-surface">{item.label}</span>
                  <Download className="w-4 h-4 text-primary group-hover:scale-110 transition-transform" />
                </button>
              ))}
            </div>
          </div>

          {/* SVG 原理图区 */}
          <div className="lg:col-span-8">
            <div className="bg-surface-container-low rounded-2xl flex flex-col border border-outline-variant/10 shadow-2xl h-full overflow-hidden">
              <div className="bg-surface-container px-6 py-4 flex justify-between items-center border-b border-outline-variant/10">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <Network className="w-5 h-5 text-primary" />
                  </div>
                  <h2 className="text-lg font-headline font-bold text-on-surface">AI 生成原理图</h2>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center bg-surface-container-highest rounded-xl p-1 border border-outline-variant/20">
                    <button className="p-2 text-on-surface-variant hover:text-primary transition-colors"><ZoomOut className="w-4 h-4" /></button>
                    <button className="p-2 text-on-surface-variant hover:text-primary transition-colors border-l border-outline-variant/10"><ZoomIn className="w-4 h-4" /></button>
                    <button className="p-2 text-on-surface-variant hover:text-primary transition-colors border-l border-outline-variant/10"><Maximize className="w-4 h-4" /></button>
                  </div>
                  <button
                    onClick={() => downloadFile(result.download.schematic_svg, `${result.chip_name}_Schematic.svg`)}
                    className="bg-primary text-on-primary text-xs font-bold uppercase tracking-widest px-5 py-2.5 rounded-xl hover:brightness-110 transition-all flex items-center gap-2"
                  >
                    <Download className="w-4 h-4" /> 导出 SVG
                  </button>
                </div>
              </div>

              <div className="flex-1 bg-surface-container-lowest p-10 relative overflow-hidden min-h-[500px] flex items-center justify-center">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,#192540_1px,transparent_1px)] bg-[size:30px_30px] opacity-20" />
                {svgContent ? (
                  <div
                    className="w-full h-full min-h-[480px] flex items-center justify-center overflow-auto p-4"
                    dangerouslySetInnerHTML={{ __html: svgContent }}
                  />
                ) : svgUrl ? (
                  // SVG fetch 失败时降级显示占位
                  <div className="relative w-full max-w-2xl h-full border border-outline-variant/20 rounded-2xl p-8 flex flex-col items-center justify-center bg-surface-container/10">
                    <AlertTriangle className="w-10 h-10 text-tertiary mb-4" />
                    <p className="text-sm text-on-surface-variant">SVG 预览加载失败</p>
                    <button
                      onClick={() => downloadFile(svgUrl, `${result.chip_name}_Schematic.svg`)}
                      className="mt-4 text-xs text-primary underline"
                    >
                      点击直接下载 SVG 文件
                    </button>
                  </div>
                ) : (
                  <div className="relative w-full max-w-2xl h-full border border-outline-variant/20 rounded-2xl p-8 flex flex-col items-center justify-center bg-surface-container/10">
                    <svg viewBox="0 0 400 200" className="w-full h-auto opacity-80 drop-shadow-2xl">
                      <path d="M50 100 L150 100" stroke="#53ddfc" strokeWidth="2" strokeLinecap="round" />
                      <path d="M150 70 L200 100 L150 130 Z" fill="rgba(83, 221, 252, 0.05)" stroke="#699cff" strokeWidth="2" />
                      <path d="M200 100 L300 100" stroke="#53ddfc" strokeWidth="2" strokeLinecap="round" />
                      <path d="M250 100 L250 40 L120 40 L120 80" stroke="#53ddfc" strokeDasharray="6 6" strokeWidth="1.5" />
                      <circle cx="120" cy="80" r="3" fill="#53ddfc" />
                      <circle cx="250" cy="100" r="3" fill="#53ddfc" />
                      <circle cx="300" cy="100" r="4" fill="#699cff" />
                      <text x="45" y="90" fill="#a3aac4" fontSize="10" fontFamily="Inter">DPS_Force</text>
                      <text x="260" y="90" fill="#a3aac4" fontSize="10" fontFamily="Inter">DUT_Pin_1</text>
                      <text x="170" y="30" fill="#ffb148" fontSize="11" fontFamily="Inter" fontWeight="bold">Kelvin Sense</text>
                    </svg>
                    <p className="mt-4 text-xs text-on-surface-variant/50">原理图预览加载中...</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    );
  };

  return (
    <div className="flex flex-col gap-8 animate-in slide-in-from-right-5 duration-500">
      <AnimatePresence mode="wait">
        {(stage === 'idle' || stage === 'error') && (
          <motion.div key="idle"><IdleView /></motion.div>
        )}
        {stage === 'loading' && (
          <motion.div key="loading"><LoadingView /></motion.div>
        )}
        {stage === 'done' && (
          <motion.div key="done"><ResultView /></motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
