import React, { useState, useEffect, useCallback } from 'react';
import { Terminal, Wand2, Copy, Download, CheckCircle2, AlertCircle, Loader2, Laptop, Code2, Cpu, Zap, ChevronRight, Link2, Unlink, BookOpen, ShieldCheck, ShieldAlert, Info } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { generateCode, getCodeTemplates, getPinDefinitions, getRagStatus,
  type CodegenResult, type TemplateItem, type PinDefinition, type RagStatus } from '../api/backend';

// ─── C++ 语法高亮（正则，无需外部库）────────────────────────────
function highlight(raw: string): string {
  return raw
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/(\/\/[^\n]*)/g, '<span class="syn-comment">$1</span>')
    .replace(/\b(DUT_API|void|int|double|float|unsigned|return|for|while|if|else|break|const|vector|using|namespace|std|include)\b/g,
      '<span class="syn-kw">$1</span>')
    .replace(/\b(FOVI|UserPMU|UserDIO|CParam|CBIT128|QTMU_PLUS|RS422)\b/g,
      '<span class="syn-type">$1</span>')
    .replace(/"([^"]*)"/g, '<span class="syn-str">"$1"</span>')
    .replace(/\b(\d+(?:\.\d+)?(?:e[-+]?\d+)?(?:f)?)\b/g,
      '<span class="syn-num">$1</span>');
}

const CHIP_TYPES = [
  { id: 'digital', label: '数字逻辑芯片', sub: '74 / CD4000 系列' },
  { id: 'ldo',     label: '模拟 LDO 芯片', sub: 'ADP / LT / TPS 系列' },
  { id: 'custom',  label: '自定义',         sub: '自行描述规格' },
] as const;

const DEFAULTS: Record<string, { name: string; items: string[]; vcc: number }> = {
  digital: { name: 'HD74LS00P', items: ['CON','FUN','VIH','VIL'], vcc: 5.0 },
  ldo:     { name: 'ADP7118A',  items: ['LDO_DROPOUT','LDO_ACCURACY','LDO_IQ'], vcc: 5.0 },
  custom:  { name: 'MyChip',    items: [], vcc: 5.0 },
};

export function CodeLab() {
  const [chipType, setChipType] = useState<'digital'|'ldo'|'custom'>('digital');
  const [chipName, setChipName] = useState('HD74LS00P');
  const [items, setItems]       = useState<Record<string,boolean>>({ CON:true, FUN:true, VIH:true, VIL:true });
  const [prompt, setPrompt]     = useState('');
  const [vcc, setVcc]           = useState(5.0);
  const [vout, setVout]         = useState(3.3);
  const [templates, setTemplates] = useState<{digital:TemplateItem[];ldo:TemplateItem[]}>({ digital:[], ldo:[] });
  const [stage, setStage]       = useState<'idle'|'loading'|'done'|'error'>('idle');
  const [result, setResult]     = useState<CodegenResult|null>(null);
  const [errMsg, setErrMsg]     = useState('');
  const [copied, setCopied]     = useState(false);
  // ── 模块一引脚数据 ─────────────────────────────────────────
  const [m1FileId, setM1FileId]     = useState<string|null>(null);
  const [m1Pins, setM1Pins]         = useState<PinDefinition[]>([]);
  const [m1ChipName, setM1ChipName] = useState('');
  const [m1Loading, setM1Loading]   = useState(false);
  // ── RAG 状态 ─────────────────────────────────────────────────
  const [ragStatus, setRagStatus]   = useState<RagStatus|null>(null);
  const [showChunks, setShowChunks] = useState(false);

  // ── 初始化：加载模板 + 读取模块一引脚数据 ──────────────────
  useEffect(() => {
    getCodeTemplates().then(r => { if (r.status==='success' && r.data) setTemplates(r.data); });

    // 检测模块一是否有提取结果
    let fileId = sessionStorage.getItem('ate_last_file_id');
    
    // 备选方案：从全局提取状态中恢复
    if (!fileId) {
      try {
        const store = sessionStorage.getItem('ate_extraction_store');
        if (store) {
          const data = JSON.parse(store);
          if (data.fileInfo?.file_id) fileId = data.fileInfo.file_id;
        }
      } catch (e) {}
    }

    if (fileId) {
      setM1FileId(fileId);
      setM1Loading(true);
      getPinDefinitions(fileId)
        .then(r => {
          if (r.status === 'success' && r.data && r.data.has_pins) {
            setM1Pins(r.data.pin_definitions);
            setM1ChipName(r.data.chip_name);
            if (r.data.chip_name) setChipName(r.data.chip_name);
          }
        })
        .catch(() => {})
        .finally(() => setM1Loading(false));
    }
    // 加载 RAG 状态
    getRagStatus().then(r => { if (r.status === 'success' && r.data) setRagStatus(r.data); }).catch(() => {});
  }, []);

  useEffect(() => {
    const d = DEFAULTS[chipType];
    setVcc(d.vcc);
    // 只在没有模块一数据时才重置芯片名
    if (!m1ChipName) setChipName(d.name);
    setItems(Object.fromEntries(d.items.map(k=>[k,true])));
  }, [chipType]);

  const toggle = (id: string) => setItems(p=>({...p,[id]:!p[id]}));
  const selected = Object.entries(items).filter(([,v])=>v).map(([k])=>k);

  const handleGenerate = useCallback(async () => {
    if (!selected.length) { setErrMsg('请至少选择一个测试项'); setStage('error'); return; }
    setStage('loading'); setErrMsg(''); setResult(null);
    try {
      // 如果模块一有引脚数据，自动传入
      const pinPayload = m1Pins.length > 0 ? {
        pin_names:   m1Pins.map(p => String(p.pin_name)),
        input_pins:  m1Pins.filter(p => p.direction?.toLowerCase().includes('in') || p.direction?.toLowerCase() === 'i')
                       .map(p => String(p.pin_name)),
        output_pins: m1Pins.filter(p => p.direction?.toLowerCase().includes('out') || p.direction?.toLowerCase() === 'o')
                       .map(p => String(p.pin_name)),
      } : {};

      const res = await generateCode({
        chip_name: chipName, chip_type: chipType,
        test_items: selected, user_prompt: prompt,
        vcc, vout,
        ...pinPayload,
      });
      if (res.status==='success' && res.data) { setResult(res.data); setStage('done'); }
      else { setErrMsg(res.message||'生成失败'); setStage('error'); }
    } catch(e:any) { setErrMsg(e.message); setStage('error'); }
  }, [chipName, chipType, selected, prompt, vcc, vout, m1Pins]);

  const handleCopy = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.code);
    setCopied(true); setTimeout(()=>setCopied(false), 2000);
  };
  const handleDownload = () => {
    if (!result) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([result.code],{type:'text/plain'}));
    a.download = result.filename; a.click();
  };

  const tpls = chipType==='ldo' ? templates.ldo : templates.digital;

  return (
    <div className="flex flex-col gap-6 animate-in slide-in-from-bottom-4 duration-500">
      {/* Header */}
      <div>
        <h1 className="font-headline text-4xl font-bold text-on-surface tracking-tight mb-2">AI 测试代码生成</h1>
        <p className="text-on-surface-variant text-sm max-w-2xl leading-relaxed">
          选择芯片类型和测试项，AI 将生成符合{' '}
          <span className="text-primary font-mono font-bold">STS8200S</span>{' '}
          编程规范的完整 C++ 测试程序。
        </p>
      </div>

      {/* 模块一联动状态横幅 */}
      {(m1FileId || m1Loading) && (
        <motion.div initial={{opacity:0,y:-6}} animate={{opacity:1,y:0}}
          className={`flex items-center gap-3 px-5 py-3 rounded-xl border text-sm ${
            m1Pins.length > 0
              ? 'bg-primary/10 border-primary/30 text-on-surface'
              : m1Loading
              ? 'bg-surface-container border-outline-variant/20 text-on-surface-variant'
              : 'bg-tertiary/10 border-tertiary/30 text-on-surface-variant'
          }`}>
          {m1Loading
            ? <Loader2 className="w-4 h-4 animate-spin text-primary shrink-0" />
            : m1Pins.length > 0
            ? <Link2 className="w-4 h-4 text-primary shrink-0" />
            : <Unlink className="w-4 h-4 text-tertiary shrink-0" />
          }
          <div className="flex-1">
            {m1Loading ? (
              <span>正在从模块①加载引脚定义...</span>
            ) : m1Pins.length > 0 ? (
              <span>
                已从模块①导入 <span className="font-mono font-bold text-primary">{m1ChipName}</span> 的{' '}
                <span className="font-bold text-primary">{m1Pins.length}</span> 个引脚定义，生成代码将使用真实引脚名称
              </span>
            ) : (
              <span>未检测到模块①提取结果，将使用通用引脚模板</span>
            )}
          </div>
          {m1Pins.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {m1Pins.slice(0, 5).map(p => (
                <span key={p.pin_name} className="text-[9px] font-mono bg-primary/20 text-primary px-1.5 py-0.5 rounded">{p.pin_name}</span>
              ))}
              {m1Pins.length > 5 && <span className="text-[9px] text-on-surface-variant/60">+{m1Pins.length-5}</span>}
            </div>
          )}
        </motion.div>
      )}

      {/* RAG 知识库状态横幅 */}
      {ragStatus && (
        <motion.div initial={{opacity:0,y:-6}} animate={{opacity:1,y:0}} transition={{delay:0.1}}
          className={`flex items-center gap-3 px-5 py-2.5 rounded-xl border text-xs ${
            ragStatus.ready
              ? 'bg-secondary/10 border-secondary/25 text-on-surface'
              : 'bg-surface-container border-outline-variant/20 text-on-surface-variant'
          }`}>
          <BookOpen className={`w-4 h-4 shrink-0 ${ragStatus.ready ? 'text-secondary' : 'text-on-surface-variant/50'}`} />
          <div className="flex-1 flex items-center gap-3">
            <span className="font-bold">
              RAG 知识库
            </span>
            {ragStatus.ready ? (
              <span className="text-on-surface-variant/70">
                已就绪 · <span className="font-mono text-secondary">{ragStatus.doc_count}</span> 个 STS8200S 手册片段 · 
                <span className="font-mono text-on-surface-variant/50 ml-1">{ragStatus.backend}</span>
              </span>
            ) : (
              <span className="text-on-surface-variant/60">知识库未就绪，代码生成将使用模板模式</span>
            )}
          </div>
          <span className={`text-[9px] font-mono px-2 py-0.5 rounded ${ragStatus.ready ? 'bg-secondary/20 text-secondary' : 'bg-surface-container-highest text-on-surface-variant/40'}`}>
            {ragStatus.ready ? '● ONLINE' : '○ OFFLINE'}
          </span>
        </motion.div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* ── 左侧配置面板 ── */}
        <div className="lg:col-span-3 flex flex-col gap-4">

          {/* 芯片类型 */}
          <section className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/10 shadow-sm">
            <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] mb-3">芯片类型</h3>
            <div className="flex flex-col gap-2">
              {CHIP_TYPES.map(ct => (
                <button key={ct.id} onClick={() => setChipType(ct.id as any)}
                  className={`text-left p-3 rounded-xl border transition-all ${
                    chipType === ct.id
                      ? 'border-primary bg-primary/10'
                      : 'border-outline-variant/20 bg-surface-container hover:bg-primary/5'
                  }`}>
                  <div className={`font-bold text-sm ${chipType===ct.id?'text-primary':'text-on-surface'}`}>{ct.label}</div>
                  <div className="text-[10px] mt-0.5 text-on-surface-variant/50 font-mono">{ct.sub}</div>
                </button>
              ))}
            </div>
          </section>

          {/* 参数配置 */}
          <section className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/10 shadow-sm flex flex-col gap-3">
            <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em]">参数配置</h3>
            {[
              { label:'芯片型号', type:'text',   value:chipName, onChange:(v:string)=>setChipName(v), step:undefined },
              { label:'VCC (V)', type:'number', value:vcc,      onChange:(v:string)=>setVcc(Number(v)), step:'0.25' },
              ...(chipType==='ldo'
                ? [{ label:'VOUT 额定 (V)', type:'number', value:vout, onChange:(v:string)=>setVout(Number(v)), step:'0.1' }]
                : [])
            ].map(f => (
              <div key={f.label}>
                <label className="text-[10px] text-on-surface-variant/50 uppercase tracking-widest block mb-1">{f.label}</label>
                <input type={f.type} step={f.step} value={f.value}
                  onChange={e => f.onChange(e.target.value)}
                  className="w-full bg-surface-container border border-outline-variant/30 rounded-lg px-3 py-2 text-sm font-mono text-on-surface focus:outline-none focus:border-primary/50 transition-colors" />
              </div>
            ))}
          </section>

          {/* 测试项目 */}
          <section className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/10 shadow-sm">
            <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] mb-3">
              测试项目 <span className="text-primary normal-case">({selected.length} 已选)</span>
            </h3>
            <div className="flex flex-col gap-1.5">
              {tpls.map(t => (
                <button key={t.id} onClick={() => toggle(t.id)}
                  className={`flex items-center gap-3 p-2.5 rounded-xl text-left transition-all group ${
                    items[t.id] ? 'bg-primary/10 border border-primary/30' : 'border border-transparent hover:bg-surface-container'
                  }`}>
                  <div className={`w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${
                    items[t.id] ? 'bg-primary border-primary' : 'border-outline-variant/50'
                  }`}>
                    {items[t.id] && <CheckCircle2 className="w-3 h-3 text-on-primary" />}
                  </div>
                  <div>
                    <div className={`text-xs font-bold font-mono ${items[t.id]?'text-primary':'text-on-surface'}`}>{t.id}</div>
                    <div className="text-[9px] text-on-surface-variant/60 mt-0.5">{t.name}</div>
                  </div>
                </button>
              ))}
            </div>
          </section>

          {/* 补充说明 */}
          <section className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/10 shadow-sm">
            <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] mb-2">补充说明（可选）</h3>
            <textarea value={prompt} onChange={e=>setPrompt(e.target.value)} rows={3}
              placeholder="例：芯片 14 引脚，标准 TTL，测试温度 25°C..."
              className="w-full bg-surface-container border border-outline-variant/30 rounded-xl px-3 py-2.5 text-xs font-sans text-on-surface placeholder-on-surface-variant/30 focus:outline-none focus:border-primary/50 transition-colors resize-none" />
          </section>

          {/* 生成按钮 */}
          <motion.button whileTap={{scale:0.97}} onClick={handleGenerate}
            disabled={stage==='loading' || !selected.length}
            className="bg-primary text-on-primary font-bold text-sm uppercase tracking-widest px-6 py-4 rounded-xl flex items-center justify-center gap-3 hover:brightness-110 shadow-lg shadow-primary/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed">
            {stage==='loading'
              ? <><Loader2 className="w-5 h-5 animate-spin" />AI 生成中...</>
              : <><Wand2 className="w-5 h-5" />生成测试代码</>
            }
          </motion.button>
        </div>

        {/* ── 中央代码编辑器 ── */}
        <div className="lg:col-span-6">
          <div className="bg-[#0d1117] rounded-2xl border border-outline-variant/10 shadow-2xl flex flex-col h-full min-h-[680px]">

            {/* IDE 顶栏 */}
            <div className="bg-[#161b22] px-5 py-3 flex items-center justify-between border-b border-white/5 rounded-t-2xl">
              <div className="flex items-center gap-3">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-500/70" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
                  <div className="w-3 h-3 rounded-full bg-green-500/70" />
                </div>
                <Terminal className="w-4 h-4 text-gray-500" />
                <span className="font-mono text-xs text-gray-400 font-bold">
                  {result ? result.filename : 'output.cpp'}
                </span>
              </div>
              <div className="flex gap-2">
                <button onClick={handleCopy} disabled={!result}
                  className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg border border-white/10 text-gray-400 hover:text-primary hover:border-primary/40 transition-all disabled:opacity-30">
                  {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-primary" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? '已复制' : '复制'}
                </button>
                <button onClick={handleDownload} disabled={!result}
                  className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg bg-primary text-on-primary hover:brightness-110 transition-all disabled:opacity-30">
                  <Download className="w-3.5 h-3.5" /> 下载 .cpp
                </button>
              </div>
            </div>

            {/* 代码区 */}
            <div className="flex-1 overflow-hidden relative">
              <AnimatePresence mode="wait">

                {/* 空状态 */}
                {stage === 'idle' && (
                  <motion.div key="idle" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
                    className="flex flex-col items-center justify-center h-full gap-6 py-24 px-8 text-center">
                    <div className="p-5 bg-primary/10 rounded-2xl">
                      <Code2 className="w-12 h-12 text-primary" />
                    </div>
                    <div>
                      <p className="font-headline text-xl font-bold text-on-surface mb-2">等待生成指令</p>
                      <p className="text-on-surface-variant/70 text-sm leading-relaxed">
                        在左侧配置芯片类型和测试项<br/>点击「生成测试代码」开始
                      </p>
                    </div>
                    <div className="grid grid-cols-3 gap-3 w-full max-w-xs">
                      {['FOVI 电源','PMU 测量','DIO 向量'].map(f => (
                        <div key={f} className="bg-primary/10 rounded-xl p-3 text-[10px] font-mono text-primary font-bold text-center border border-primary/20">{f}</div>
                      ))}
                    </div>
                  </motion.div>
                )}

                {/* 加载 */}
                {stage === 'loading' && (
                  <motion.div key="loading" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
                    className="flex flex-col items-center justify-center h-full gap-6 py-24">
                    <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
                      <Loader2 className="w-10 h-10 text-primary animate-spin" />
                    </div>
                    <div className="text-center">
                      <p className="font-headline text-xl font-bold text-on-surface mb-2">AI 正在生成代码…</p>
                      <p className="text-sm text-on-surface-variant/70">模板骨架构建中，DeepSeek 润色注释</p>
                    </div>
                    <div className="flex gap-1.5">
                      {[0,1,2].map(i => (
                        <motion.div key={i} animate={{opacity:[0.3,1,0.3]}}
                          transition={{repeat:Infinity,duration:1.2,delay:i*0.2}}
                          className="w-2 h-2 rounded-full bg-primary" />
                      ))}
                    </div>
                  </motion.div>
                )}

                {/* 错误 */}
                {stage === 'error' && (
                  <motion.div key="error" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
                    className="flex flex-col items-center justify-center h-full gap-4 py-24 px-8 text-center">
                    <div className="p-4 bg-error/10 rounded-2xl"><AlertCircle className="w-10 h-10 text-error" /></div>
                    <p className="text-sm text-on-surface-variant max-w-xs">{errMsg}</p>
                    <button onClick={()=>setStage('idle')} className="text-xs text-primary underline hover:opacity-70 transition-opacity">返回重试</button>
                  </motion.div>
                )}

                {/* 代码结果 */}
                {stage === 'done' && result && (
                  <motion.div key="done" initial={{opacity:0}} animate={{opacity:1}}
                    className="flex h-full overflow-auto">
                    {/* 行号 */}
                    <div className="text-right pr-4 pl-3 py-5 select-none bg-[#161b22] border-r border-white/5
                      font-mono text-[11px] text-gray-600 leading-5 min-w-[3rem] shrink-0">
                      {result.code.split('\n').map((_,i) => <div key={i}>{i+1}</div>)}
                    </div>
                    {/* 代码 */}
                    <pre className="flex-1 py-5 pl-5 pr-6 font-mono text-[11px] leading-5 overflow-x-auto
                      text-gray-300 [&_.syn-kw]:text-[#ff7b72] [&_.syn-kw]:font-bold
                      [&_.syn-type]:text-[#79c0ff] [&_.syn-type]:font-bold
                      [&_.syn-str]:text-[#a5d6ff]
                      [&_.syn-num]:text-[#f2cc60]
                      [&_.syn-comment]:text-gray-500 [&_.syn-comment]:italic"
                      dangerouslySetInnerHTML={{__html: highlight(result.code)}} />
                  </motion.div>
                )}

              </AnimatePresence>
            </div>
          </div>
        </div>

        {/* ── 右侧信息面板 ── */}
        <div className="lg:col-span-3 flex flex-col gap-4">

          {/* 平台信息 */}
          <section className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/10 shadow-sm">
            <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] mb-3">目标平台</h3>
            <div className="flex items-center gap-3 p-3 bg-surface-container rounded-xl border border-primary/20 mb-4">
              <div className="p-2 bg-primary/10 rounded-lg"><Laptop className="w-5 h-5 text-primary" /></div>
              <div>
                <div className="font-bold text-sm text-on-surface">STS8200S</div>
                <div className="text-[10px] text-primary/60 font-mono">集成电路测试系统</div>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              {[
                ['系统版本', 'VerP1.1'],
                ['PGS 编辑器', 'v3.0'],
                ['DIO 板卡', 'CBIT128'],
                ['PMU 通道', '24ch FOVI'],
                ['最大测试电压', '50V'],
              ].map(([k,v]) => (
                <div key={k} className="flex justify-between items-center text-xs">
                  <span className="text-on-surface-variant/60">{k}</span>
                  <span className="font-mono text-primary font-bold">{v}</span>
                </div>
              ))}
            </div>
          </section>

          {/* 代码统计 (生成后) */}
          {result && (
            <motion.section initial={{opacity:0,y:10}} animate={{opacity:1,y:0}}
              className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/10 shadow-sm">
              <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] mb-3">代码统计</h3>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {[
                  {label:'总行数', value:result.lines, icon:Code2},
                  {label:'测试函数', value:result.functions, icon:Zap},
                ].map(({label,value,icon:Icon}) => (
                  <div key={label} className="bg-surface-container rounded-xl p-3 text-center border border-outline-variant/10">
                    <Icon className="w-4 h-4 text-primary mx-auto mb-1" />
                    <div className="font-headline text-2xl font-bold text-primary">{value}</div>
                    <div className="text-[9px] text-on-surface-variant/60 uppercase tracking-widest mt-0.5">{label}</div>
                  </div>
                ))}
              </div>
              <div className="p-3 bg-primary/5 rounded-xl border border-primary/10">
                <div className="text-[9px] text-on-surface-variant/50 uppercase tracking-widest mb-2">已生成测试项</div>
                <div className="flex flex-wrap gap-1.5">
                  {result.test_items.map(item => (
                    <span key={item} className="text-[10px] font-mono font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">{item}</span>
                  ))}
                </div>
              </div>
            </motion.section>
          )}

          {/* P3 静态校验面板 */}
          {result && result.static_analysis && (
            <motion.section initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{delay:0.15}}
              className={`bg-surface-container-low rounded-2xl p-5 border shadow-sm ${
                result.static_analysis.passed ? 'border-primary/30' : 'border-error/30'
              }`}>
              <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] mb-4 flex items-center gap-2">
                {result.static_analysis.passed
                  ? <ShieldCheck className="w-3.5 h-3.5 text-primary" />
                  : <ShieldAlert className="w-3.5 h-3.5 text-error" />}
                预校验评分
              </h3>
              {/* 评分进度条 */}
              <div className="flex items-center gap-3 mb-4">
                <div className="flex-1 h-2 bg-surface-container rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${result.static_analysis.score}%` }}
                    transition={{ duration: 0.8, ease: 'easeOut' }}
                    className={`h-full rounded-full ${
                      result.static_analysis.score >= 90 ? 'bg-primary' :
                      result.static_analysis.score >= 60 ? 'bg-tertiary' : 'bg-error'
                    }`}
                  />
                </div>
                <span className={`font-headline text-2xl font-bold ${
                  result.static_analysis.score >= 90 ? 'text-primary' :
                  result.static_analysis.score >= 60 ? 'text-tertiary' : 'text-error'
                }`}>{result.static_analysis.score}</span>
                <span className="text-on-surface-variant/50 text-xs">/100</span>
              </div>
              <p className="text-[10px] text-on-surface-variant/70 leading-relaxed mb-3 italic">
                {result.static_analysis.summary}
              </p>
              {/* 错误列表 */}
              {result.static_analysis.errors?.length > 0 && (
                <div className="flex flex-col gap-1.5 mb-2">
                  {result.static_analysis.errors.map((e: any, i: number) => (
                    <div key={i} className="flex items-start gap-2 text-[10px] text-error bg-error/5 rounded-lg p-2 border-l-2 border-error/50">
                      <ShieldAlert className="w-3 h-3 shrink-0 mt-0.5" />
                      <span>[{e.rule}] {e.message}{e.line ? ` 第${e.line}行` : ''}</span>
                    </div>
                  ))}
                </div>
              )}
              {/* 警告列表 */}
              {result.static_analysis.warnings?.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  {result.static_analysis.warnings.map((w: any, i: number) => (
                    <div key={i} className="flex items-start gap-2 text-[10px] text-tertiary bg-tertiary/5 rounded-lg p-2 border-l-2 border-tertiary/50">
                      <AlertCircle className="w-3 h-3 shrink-0 mt-0.5" />
                      <span>[{w.rule}] {w.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </motion.section>
          )}

          {/* RAG 检索片段展示 */}
          {result && (result as any).retrieved_chunks?.length > 0 && (
            <motion.section initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{delay:0.2}}
              className="bg-surface-container-low rounded-2xl p-5 border border-secondary/20 shadow-sm">
              <button
                onClick={() => setShowChunks(v => !v)}
                className="w-full flex items-center justify-between text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] mb-0"
              >
                <span className="flex items-center gap-2">
                  <BookOpen className="w-3.5 h-3.5 text-secondary" />
                  RAG 检索参考片段
                  <span className="bg-secondary/20 text-secondary px-1.5 py-0.5 rounded font-mono">{(result as any).retrieved_chunks.length}条</span>
                </span>
                <ChevronRight className={`w-3.5 h-3.5 transition-transform ${showChunks ? 'rotate-90' : ''}`} />
              </button>
              <AnimatePresence>
                {showChunks && (
                  <motion.div initial={{height:0,opacity:0}} animate={{height:'auto',opacity:1}} exit={{height:0,opacity:0}}
                    className="overflow-hidden">
                    <div className="flex flex-col gap-2 mt-3 max-h-64 overflow-y-auto">
                      {(result as any).retrieved_chunks.map((chunk: any, i: number) => (
                        <div key={i} className="text-[10px] text-on-surface-variant bg-secondary/5 rounded-lg p-3 border-l-2 border-secondary/30">
                          <div className="font-mono text-secondary font-bold mb-1">{chunk.source} · 相关度 {chunk.score}</div>
                          <p className="leading-relaxed opacity-80 line-clamp-3">{chunk.text}</p>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.section>
          )}

          {/* 使用提示 (未生成时) */}
          {!result && (
            <section className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/10 shadow-sm">
              <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] mb-3">使用提示</h3>
              <div className="flex flex-col gap-3">
                {[
                  {icon:Cpu,         tip:'选择与实际芯片匹配的类型，获得最优模板骨架'},
                  {icon:ChevronRight, tip:'模块①提取后，引脚信息可自动导入本模块'},
                  {icon:CheckCircle2, tip:'生成代码需工程师复核参数值后再上机测试'},
                ].map(({icon:Icon, tip}, i) => (
                  <div key={i} className="flex gap-2.5 text-[11px] text-on-surface-variant/80 leading-relaxed">
                    <Icon className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />
                    <span>{tip}</span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

      </div>
    </div>
  );
}
