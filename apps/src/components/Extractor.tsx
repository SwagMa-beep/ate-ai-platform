import React, { useState, useRef, useEffect } from 'react';
import {
  Upload, FileText, Cpu, Table as TableIcon,
  ChevronRight, Download, Loader2, AlertTriangle, CloudUpload, X,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import {
  getDownloadUrl,
  type UploadResult, type ExtractionResult, type PinDefinition, type RangeRecommendation,
} from '../api/backend';
import { extractionStore, type ExtractionState, type Stage } from '../store/extractionStore';

/**
 * 直接触发浏览器下载，不经过 fetch，避免拿到 JSON 错误体后存成远程文件
 * 同源 URL 下 browser 会尊重 download 属性的文件名
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

// 置信度：根据参数数量和blocked比例估算
function calcConfidence(result: ExtractionResult): number {
  if (!result || !result.statistics) return 0;
  const total = result.statistics.total || 0;
  const blocked = result.statistics.blocked || 0;
  if (total === 0) return 0;
  return Math.round(((total - blocked) / total) * 100 * 10) / 10;
}

// ─── 子组件：上传区 ──────────────────────────────────────────
interface UploadZoneProps {
  dragOver: boolean;
  onDragOver: (over: boolean) => void;
  onDrop: (e: React.DragEvent) => void;
  onFileSelect: () => void;
  onFileInput: (e: React.ChangeEvent<HTMLInputElement>) => void;
  fileInputRef: React.RefObject<HTMLInputElement>;
  stage: Stage;
  error: string;
  onReset: () => void;
}

const UploadZone = ({
  dragOver, onDragOver, onDrop, onFileSelect, onFileInput, fileInputRef, stage, error, onReset
}: UploadZoneProps) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -10 }}
    className="flex flex-col gap-8"
  >
    {/* 头部 */}
    <div>
      <h1 className="font-headline text-4xl font-bold text-on-surface tracking-tight mb-2">
        数据手册智能分析
      </h1>
      <p className="text-on-surface-variant font-sans text-sm max-w-2xl leading-relaxed">
        上传芯片 Datasheet PDF，LLM 将自动提取引脚定义、测试参数，并生成标准 TestPlan 文件。
      </p>
    </div>

    {/* 拖拽上传区 */}
    <div
      onDragOver={e => { e.preventDefault(); onDragOver(true); }}
      onDragLeave={() => onDragOver(false)}
      onDrop={onDrop}
      onClick={onFileSelect}
      className={`relative border-2 border-dashed rounded-2xl p-16 flex flex-col items-center justify-center gap-6 cursor-pointer transition-all
        ${dragOver
          ? 'border-primary bg-primary/10 shadow-[0_0_40px_#53ddfc20]'
          : 'border-outline-variant/30 bg-surface-container-low hover:border-primary/50 hover:bg-primary/5'
        }`}
    >
      <input ref={fileInputRef} type="file" accept=".pdf" className="hidden" onChange={onFileInput} />
      <div className={`p-5 rounded-2xl transition-all ${dragOver ? 'bg-primary/20' : 'bg-surface-container'}`}>
        <CloudUpload className={`w-12 h-12 transition-colors ${dragOver ? 'text-primary' : 'text-on-surface-variant'}`} />
      </div>
      <div className="text-center">
        <p className="font-headline text-xl font-bold text-on-surface mb-2">
          {dragOver ? '松开以上传' : '拖拽 PDF 到此处'}
        </p>
        <p className="text-on-surface-variant text-sm">或点击选择文件 · 最大 50MB</p>
      </div>
      <button className="bg-primary text-on-primary font-sans font-bold text-xs uppercase tracking-widest px-8 py-4 rounded-xl flex items-center gap-3 hover:brightness-110 shadow-lg shadow-primary/10 transition-all">
        <Upload className="w-5 h-5" />
        选择 PDF 文件
      </button>
    </div>

    {/* 错误提示 */}
    <AnimatePresence>
      {stage === 'error' && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="flex items-center gap-4 p-5 bg-error/10 border border-error/30 rounded-2xl"
        >
          <AlertTriangle className="w-6 h-6 text-error shrink-0" />
          <p className="text-sm text-on-surface font-sans">{error}</p>
          <button onClick={onReset} className="ml-auto p-1 hover:bg-error/20 rounded-lg transition-colors">
            <X className="w-4 h-4 text-error" />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  </motion.div>
);

// ─── 子组件：进度区 ──────────────────────────────────────────
interface ProgressViewProps {
  progress: number;
  message: string;
  fileInfo: UploadResult | null;
  stage: Stage;
}

const ProgressView = ({ progress, message, fileInfo, stage }: ProgressViewProps) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.97 }}
    animate={{ opacity: 1, scale: 1 }}
    className="bg-surface-container-low rounded-2xl p-10 border border-outline-variant/10 shadow-2xl flex flex-col gap-8 items-center text-center"
  >
    <div className="relative">
      <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
        <Loader2 className="w-10 h-10 text-primary animate-spin" />
      </div>
      <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center">
        <span className="text-[9px] font-black text-primary">{progress}%</span>
      </div>
    </div>

    <div>
      <p className="font-headline text-2xl font-bold text-on-surface mb-2">{message}</p>
      {fileInfo && (
        <p className="text-on-surface-variant text-sm font-mono">{fileInfo.filename} · {fileInfo.size_mb} MB</p>
      )}
    </div>

    {/* 进度条 */}
    <div className="w-full max-w-md h-2 bg-surface-container-highest rounded-full overflow-hidden">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${progress}%` }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="h-full bg-gradient-to-r from-secondary to-primary rounded-full"
      />
    </div>

    <p className="text-xs text-on-surface-variant/60 font-mono uppercase tracking-widest">
      {stage === 'uploading' ? '上传中...' : '正在解析 Datasheet，命中缓存会秒级返回'}
    </p>
  </motion.div>
);

// ─── 子组件：结果区 ──────────────────────────────────────────
interface ResultViewProps {
  result: ExtractionResult | null;
  fileInfo: UploadResult | null;
  pins: PinDefinition[];
  onReset: () => void;
  confidence: number;
}

const ResultView = ({ result, fileInfo, pins, onReset, confidence }: ResultViewProps) => {
  if (!result || !fileInfo) return null;
  const stats = result.statistics ?? {
    total: 0, A_class: 0, B_class: 0, C_class: 0,
    dc_items: 0, ac_items: 0, ldo_items: 0, blocked: 0,
  };
  const warnings = result.warnings ?? [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col gap-8"
    >
      {/* 头部 */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <h1 className="font-headline text-4xl font-bold text-on-surface tracking-tight mb-2">
            数据手册智能分析
          </h1>
          <p className="text-on-surface-variant font-sans text-sm max-w-2xl leading-relaxed">
            LLM 解析已完成。正在查看{' '}
            <span className="text-primary font-mono font-bold">{result.chip_name || fileInfo.filename}</span>{' '}
            的引脚图、测试参数和资源映射结果。
          </p>
        </div>
        <button
          onClick={onReset}
          className="bg-surface-container text-on-surface-variant border border-outline-variant/30 font-sans font-bold text-xs uppercase tracking-widest px-6 py-4 rounded-xl flex items-center gap-3 hover:bg-surface-bright transition-all"
        >
          <Upload className="w-5 h-5" />
          上传新手册
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* 状态卡 */}
        <section className="lg:col-span-12 bg-surface-container-low rounded-2xl p-8 relative overflow-hidden border border-outline-variant/10 shadow-2xl">
          <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-primary/5 rounded-full blur-[100px] -mr-20 -mt-20 pointer-events-none" />

          <div className="flex flex-col md:flex-row justify-between items-start gap-10 z-10 relative">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-5">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-primary" />
                </span>
                <span className="font-sans text-primary text-[10px] font-bold tracking-[0.3em] uppercase mr-2">提取完成</span>
                {result.test_scenario && (
                  <span className="font-sans bg-primary/10 text-primary text-[10px] px-2 py-0.5 rounded border border-primary/20 font-bold uppercase tracking-widest">
                    {result.test_scenario} 场景
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 mb-4">
                <div className="p-3 bg-primary/10 rounded-xl">
                  <FileText className="w-8 h-8 text-primary" />
                </div>
                <h2 className="font-headline text-3xl font-bold text-on-surface">{fileInfo.filename}</h2>
              </div>
              <div className="flex flex-wrap gap-3">
                {warnings.slice(0, 2).map((w, i) => (
                  <span key={i} className="flex items-center gap-1.5 text-xs text-tertiary bg-tertiary/10 border border-tertiary/20 px-3 py-1.5 rounded-lg">
                    <AlertTriangle className="w-3.5 h-3.5" /> {w}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex gap-8 w-full md:w-auto bg-surface-container/40 p-6 rounded-2xl backdrop-blur-sm border border-outline-variant/10">
              <div className="flex flex-col gap-1">
                <span className="font-sans text-on-surface-variant text-[10px] uppercase tracking-[0.2em] font-bold">置信度</span>
                <span className="font-headline text-4xl font-bold text-primary tracking-tighter">{confidence}%</span>
              </div>
              <div className="w-px h-auto bg-outline-variant/20" />
              <div className="flex flex-col gap-1">
                <span className="font-sans text-on-surface-variant text-[10px] uppercase tracking-[0.2em] font-bold">提取参数</span>
                <span className="font-headline text-4xl font-bold text-on-surface tracking-tighter">{stats.total}</span>
              </div>
              <div className="w-px h-auto bg-outline-variant/20" />
              <div className="flex flex-col gap-1">
                <span className="font-sans text-on-surface-variant text-[10px] uppercase tracking-[0.2em] font-bold">引脚数</span>
                <span className="font-headline text-4xl font-bold text-on-surface tracking-tighter">{result.pin_count}</span>
              </div>
            </div>
          </div>
        </section>

        {/* 引脚定义表 */}
        <div className="lg:col-span-7 flex flex-col gap-8">
          <div className="bg-surface-container-low rounded-2xl border border-outline-variant/10 overflow-hidden shadow-lg">
            <div className="p-6 border-b border-outline-variant/10 flex justify-between items-center bg-surface-container/30">
              <h3 className="font-headline text-xl font-bold text-on-surface flex items-center gap-3">
                <Cpu className="w-6 h-6 text-primary" />
                已提取引脚定义
                <span className="text-sm text-on-surface-variant font-sans font-normal">({pins.length} 个)</span>
              </h3>
              <button
                onClick={() => downloadFile(getDownloadUrl(fileInfo.file_id, 'json'), `${result.chip_name || fileInfo.filename}_TestPlan.json`)}
                className="text-primary-variant font-bold text-xs uppercase tracking-widest bg-surface-bright px-4 py-2 rounded-lg hover:bg-primary/10 transition-all border border-primary/20 flex items-center gap-2"
              >
                <Download className="w-3.5 h-3.5" /> JSON
              </button>
            </div>

            <div className="overflow-x-auto">
              {pins.length > 0 ? (
                <table className="w-full text-left">
                  <thead className="bg-surface-container/50 text-on-surface-variant font-sans text-[10px] uppercase tracking-widest font-bold">
                    <tr>
                      <th className="py-4 px-6">引脚 #</th>
                      <th className="py-4 px-6">名称</th>
                      <th className="py-4 px-6">方向</th>
                      <th className="py-4 px-6">功能描述</th>
                    </tr>
                  </thead>
                  <tbody className="font-sans text-sm divide-y divide-outline-variant/5">
                    {pins.slice(0, 20).map((pin, idx) => (
                      <tr key={idx} className="hover:bg-primary/5 transition-colors group">
                        <td className="py-4 px-6 font-mono text-primary font-bold">{pin.pin_no}</td>
                        <td className="py-4 px-6 font-bold text-on-surface">{pin.pin_name}</td>
                        <td className="py-4 px-6">
                          <span className="px-2 py-1 bg-surface-container-highest rounded text-[10px] font-bold text-on-surface-variant uppercase tracking-tighter">
                            {pin.direction || '—'}
                          </span>
                        </td>
                        <td className="py-4 px-6 text-on-surface-variant leading-relaxed text-xs opacity-90 group-hover:opacity-100 transition-opacity">
                          {pin.function || pin.notes || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="py-12 text-center text-on-surface-variant/50 font-sans text-sm">
                  未提取到引脚定义（部分芯片类型不包含）
                </div>
              )}
              {pins.length > 20 && (
                <div className="p-4 text-center text-xs text-on-surface-variant/50 border-t border-outline-variant/10">
                  仅显示前 20 条，共 {pins.length} 条 · 下载 JSON 查看完整数据
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 右侧面板：统计 + 下载 */}
        <div className="lg:col-span-5 flex flex-col gap-8">
          {/* 参数统计 */}
          <section className="bg-surface-container-low rounded-2xl p-7 border border-outline-variant/10 shadow-lg">
            <h3 className="font-headline text-lg font-bold text-on-surface flex items-center gap-3 mb-6">
              <TableIcon className="w-5 h-5 text-primary" />
              参数提取统计
            </h3>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: '总参数', value: stats.total, color: 'text-on-surface' },
                { label: 'A 类（必测）', value: stats.A_class, color: 'text-primary' },
                { label: 'B 类（推荐）', value: stats.B_class, color: 'text-secondary' },
                { label: 'C 类（可选）', value: stats.C_class, color: 'text-on-surface-variant' },
                { label: 'DC 测试项', value: stats.dc_items, color: 'text-on-surface' },
                { label: 'AC 测试项', value: stats.ac_items, color: 'text-on-surface' },
              ].map((item, i) => (
                <div key={i} className="bg-surface-container rounded-xl p-4 flex flex-col gap-1">
                  <span className="text-[10px] font-sans text-on-surface-variant uppercase tracking-widest font-bold opacity-60">
                    {item.label}
                  </span>
                  <span className={`font-headline text-2xl font-bold ${item.color} tracking-tighter`}>
                    {item.value}
                  </span>
                </div>
              ))}
            </div>
          </section>

          {/* AI 量程推荐卡片 */}
          {result.range_recommendations && result.range_recommendations.length > 0 && (
            <section className="bg-surface-container-low rounded-2xl border border-outline-variant/10 shadow-lg overflow-hidden">
              <div className="px-7 py-5 border-b border-outline-variant/10 bg-surface-container/30 flex items-center justify-between">
                <h3 className="font-headline text-lg font-bold text-on-surface flex items-center gap-3">
                  <span className="w-5 h-5 text-lg leading-none">⚡</span>
                  AI 量程推荐
                </h3>
                <span className="text-[10px] font-mono text-on-surface-variant/50 uppercase tracking-widest">
                  基于 STS8200S 编程手册
                </span>
              </div>
              <div className="flex flex-col divide-y divide-outline-variant/8">
                {result.range_recommendations.map((rec: RangeRecommendation, i: number) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.06 }}
                    className="px-6 py-4 hover:bg-primary/5 transition-all group"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-sm font-bold text-primary">{rec.param}</span>
                          {rec.value !== 'N/A' && (
                            <span className="font-mono text-xs text-on-surface-variant/60 bg-surface-container px-2 py-0.5 rounded">
                              {rec.value}
                            </span>
                          )}
                          {rec.priority === 'high' && (
                            <span className="text-[9px] font-bold text-error bg-error/10 border border-error/20 px-1.5 py-0.5 rounded uppercase tracking-tighter">
                              高压
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-on-surface-variant leading-relaxed opacity-75 group-hover:opacity-100 transition-opacity">
                          {rec.reason}
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        <span className="text-[10px] font-sans text-on-surface-variant/50 uppercase tracking-widest block mb-1">推荐量程</span>
                        <span className="font-mono text-xs font-bold text-secondary bg-secondary/10 border border-secondary/20 px-2 py-1 rounded block">
                          {rec.range_module}
                        </span>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </section>
          )}

          <div className="glass-panel rounded-2xl p-7 relative overflow-hidden border-l-4 border-l-primary">
            <h3 className="font-headline text-sm font-bold text-on-surface flex items-center gap-3 mb-5">
              <Download className="w-4 h-4 text-primary" />
              下载提取结果
            </h3>
            <div className="flex flex-col gap-3">
              <button
                onClick={() => downloadFile(getDownloadUrl(fileInfo.file_id, 'excel'), `${result.chip_name || fileInfo.filename}_TestPlan.xlsx`)}
                className="flex items-center justify-between p-4 bg-surface-container hover:bg-primary/10 rounded-xl border border-outline-variant/20 hover:border-primary/30 transition-all group w-full text-left"
              >
                <span className="font-sans text-sm font-bold text-on-surface">TestPlan Excel</span>
                <ChevronRight className="w-4 h-4 text-primary group-hover:translate-x-1 transition-transform" />
              </button>
              <button
                onClick={() => downloadFile(getDownloadUrl(fileInfo.file_id, 'json'), `${result.chip_name || fileInfo.filename}_TestPlan.json`)}
                className="flex items-center justify-between p-4 bg-surface-container hover:bg-primary/10 rounded-xl border border-outline-variant/20 hover:border-primary/30 transition-all group w-full text-left"
              >
                <span className="font-sans text-sm font-bold text-on-surface">结构化 JSON</span>
                <ChevronRight className="w-4 h-4 text-primary group-hover:translate-x-1 transition-transform" />
              </button>
            </div>

            {/* 兼容性 */}
            {result.sts_compatibility && typeof result.sts_compatibility === 'object' && (
              <div className="mt-5 pt-5 border-t border-outline-variant/10">
                <span className="text-[10px] text-on-surface-variant uppercase tracking-widest font-bold opacity-60 block mb-2">STS 兼容性</span>
                <div className="text-xs text-on-surface-variant leading-relaxed">
                  <div className="font-bold mb-1">
                    {result.sts_compatibility.is_compatible ? <span className="text-primary">✅ 兼容 STS8200S</span> : <span className="text-error">⚠️ 存在适配问题</span>}
                  </div>
                  {result.sts_compatibility.issues && result.sts_compatibility.issues.length > 0 && (
                    <ul className="list-disc pl-4 mt-2 space-y-1">
                      {result.sts_compatibility.issues.map((issue: string, i: number) => (
                        <li key={i}>{issue}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export function Extractor() {
  const [state, setState] = useState<ExtractionState>(extractionStore.getState());
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const unsubscribe = extractionStore.subscribe(setState);
    return unsubscribe;
  }, []);

  const handleFile = (file: File) => {
    extractionStore.startUpload(file);
  };

  const onFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = '';
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const reset = () => {
    extractionStore.reset();
  };

  const { stage, progress, message, fileInfo, result, pins, error } = state;
  const confidence = result ? calcConfidence(result) : 0;

  // ─── 渲染 ──────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-8 animate-in slide-in-from-bottom-5 duration-500">
      <AnimatePresence mode="wait">
        {(stage === 'idle' || stage === 'error') && (
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
        )}
        {(stage === 'uploading' || stage === 'extracting') && (
          <ProgressView
            key="progress"
            progress={progress}
            message={message}
            fileInfo={fileInfo}
            stage={stage}
          />
        )}
        {stage === 'done' && (
          <ResultView
            key="result"
            result={result}
            fileInfo={fileInfo}
            pins={pins}
            onReset={reset}
            confidence={confidence}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

