import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Code2,
  Copy,
  Cpu,
  Download,
  FileCode2,
  Link2,
  Loader2,
  Package,
  PlayCircle,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Unlink,
  Wand2,
  Workflow,
} from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import {
  generateCode,
  getCodeTemplates,
  getPinDefinitions,
  getRagStatus,
  recommendCodeItems,
  resolveBackendUrl,
  type AgentRunResult,
  type CodegenPlan,
  type CodegenResult,
  type PinDefinition,
  type RagStatus,
  type TemplateItem,
} from '../api/backend';
import { getArtifactLabel, getFlowLabel, getRunStatusPresentation, getStepLabel } from '../utils/runPresentation';

function highlight(raw: string): string {
  return raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/(\/\/[^\n]*)/g, '<span class="syn-comment">$1</span>')
    .replace(
      /\b(DUT_API|void|int|double|float|unsigned|return|for|while|if|else|break|const|vector|using|namespace|std|include)\b/g,
      '<span class="syn-kw">$1</span>',
    )
    .replace(/\b(FOVI|UserPMU|UserDIO|CParam|CBIT128|QTMU_PLUS|RS422)\b/g, '<span class="syn-type">$1</span>')
    .replace(/"([^"]*)"/g, '<span class="syn-str">"$1"</span>')
    .replace(/\b(\d+(?:\.\d+)?(?:e[-+]?\d+)?(?:f)?)\b/g, '<span class="syn-num">$1</span>');
}

const CHIP_TYPES = [
  { id: 'digital', label: '数字逻辑芯片', sub: '74 / CD4000 系列' },
  { id: 'ldo', label: '模拟 LDO 芯片', sub: 'ADP / LT / TPS 系列' },
  { id: 'custom', label: '自定义芯片', sub: '没有模块一结果时的兜底入口' },
] as const;

const DEFAULTS: Record<'digital' | 'ldo' | 'custom', { name: string; items: string[]; vcc: number }> = {
  digital: { name: 'HD74LS00P', items: ['CON', 'FUN', 'VIH', 'VIL'], vcc: 5.0 },
  ldo: { name: 'ADP7118A', items: ['LDO_DROPOUT', 'LDO_ACCURACY', 'LDO_IQ'], vcc: 5.0 },
  custom: { name: 'MyChip', items: [], vcc: 5.0 },
};

const RUNTIME_STEPS = [
  { agent: 'codegen_planner', label: '测试规划', description: '校验测试项、引脚依赖和工程前置条件。' },
  { agent: 'code_assembler', label: '代码装配', description: '根据模板、企业样例和知识库生成测试代码。' },
  { agent: 'static_validator', label: '静态校验', description: '检查结构、规则、TODO 和明显风险。' },
  { agent: 'compile_validator', label: '编译预检', description: '用本地桩头做一次快速编译级预检查。' },
  { agent: 'engineering_packager', label: '工程打包', description: '生成工程目录、VECDIO/PGS 和 ZIP 包。' },
] as const;

function mapBackendChipType(value?: string): 'digital' | 'ldo' | 'custom' {
  const chipType = String(value || '').toUpperCase();
  if (chipType.includes('DIGITAL') || chipType === 'MEMORY') return 'digital';
  if (chipType === 'LDO' || chipType.includes('ANALOG')) return 'ldo';
  return 'custom';
}

function toPinPayload(pins: PinDefinition[]) {
  if (!pins.length) return {};

  return {
    pin_names: pins.map(pin => String(pin.pin_name)),
    input_pins: pins
      .filter(pin => {
        const direction = String(pin.direction || '').toLowerCase();
        return direction.includes('in') || direction === 'i';
      })
      .map(pin => String(pin.pin_name)),
    output_pins: pins
      .filter(pin => {
        const direction = String(pin.direction || '').toLowerCase();
        return direction.includes('out') || direction === 'o';
      })
      .map(pin => String(pin.pin_name)),
  };
}

function SmallTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-3 text-[10px] font-bold uppercase tracking-[0.2em] text-on-surface-variant">{children}</h3>;
}

function StatPill({
  label,
  value,
  tone = 'primary',
}: {
  label: string;
  value: React.ReactNode;
  tone?: 'primary' | 'secondary' | 'tertiary';
}) {
  const toneClass =
    tone === 'secondary'
      ? 'bg-secondary/10 text-secondary'
      : tone === 'tertiary'
        ? 'bg-tertiary/10 text-tertiary'
        : 'bg-primary/10 text-primary';

  return (
    <div className="rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-3 text-center">
      <div className={`rounded-lg py-1 font-headline text-xl font-bold ${toneClass}`}>{value}</div>
      <div className="mt-2 text-[9px] uppercase tracking-widest text-on-surface-variant/60">{label}</div>
    </div>
  );
}

function normalizePlan(plan?: CodegenPlan | null) {
  if (!plan) return null;
  return {
    ...plan,
    resources: plan.resources || [],
    warnings: plan.warnings || [],
    errors: plan.errors || [],
    items: plan.items || [],
  };
}

function normalizeRun(run?: AgentRunResult | null) {
  if (!run) return null;
  return {
    ...run,
    steps: run.steps || [],
    warnings: run.warnings || [],
    errors: run.errors || [],
    artifacts: run.artifacts || [],
  };
}

export function CodeLab() {
  const [chipType, setChipType] = useState<'digital' | 'ldo' | 'custom'>('digital');
  const [chipName, setChipName] = useState('HD74LS00P');
  const [items, setItems] = useState<Record<string, boolean>>({ CON: true, FUN: true, VIH: true, VIL: true });
  const [prompt, setPrompt] = useState('');
  const [vcc, setVcc] = useState(5.0);
  const [vout, setVout] = useState(3.3);
  const [templates, setTemplates] = useState<{ digital: TemplateItem[]; ldo: TemplateItem[] }>({ digital: [], ldo: [] });
  const [stage, setStage] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [result, setResult] = useState<CodegenResult | null>(null);
  const [errMsg, setErrMsg] = useState('');
  const [copied, setCopied] = useState(false);

  const [m1FileId, setM1FileId] = useState<string | null>(null);
  const [m1Pins, setM1Pins] = useState<PinDefinition[]>([]);
  const [m1ChipName, setM1ChipName] = useState('');
  const [m1ChipType, setM1ChipType] = useState<'digital' | 'ldo' | 'custom' | null>(null);
  const [m1Loading, setM1Loading] = useState(false);

  const [recommendedItems, setRecommendedItems] = useState<string[]>([]);
  const [optionalItems, setOptionalItems] = useState<string[]>([]);
  const [detectedParams, setDetectedParams] = useState<string[]>([]);
  const [recommendationReasons, setRecommendationReasons] = useState<string[]>([]);
  const [recommendationSource, setRecommendationSource] = useState<'manual' | 'module1'>('manual');
  const [allowManualChipType, setAllowManualChipType] = useState(false);

  const [ragStatus, setRagStatus] = useState<RagStatus | null>(null);
  const [showChunks, setShowChunks] = useState(false);
  const [showQualityDetails, setShowQualityDetails] = useState(false);
  const [showCompileDetails, setShowCompileDetails] = useState(false);
  const [showPackageDetails, setShowPackageDetails] = useState(false);
  const [showEngineeringDetails, setShowEngineeringDetails] = useState(false);

  const linkedFromModule1 = Boolean(m1FileId);
  const chipTypeLocked = linkedFromModule1 && !allowManualChipType;
  const effectiveChipType = chipTypeLocked && m1ChipType ? m1ChipType : chipType;

  useEffect(() => {
    getCodeTemplates().then(response => {
      if (response.status === 'success' && response.data) {
        setTemplates(response.data);
      }
    });

    let fileId = sessionStorage.getItem('ate_last_file_id');
    if (!fileId) {
      try {
        const store = sessionStorage.getItem('ate_extraction_store');
        if (store) {
          const data = JSON.parse(store);
          if (data.fileInfo?.file_id) fileId = data.fileInfo.file_id;
        }
      } catch {
        // ignore bad payloads
      }
    }

    if (fileId) {
      setM1FileId(fileId);
      setM1Loading(true);
      getPinDefinitions(fileId)
        .then(response => {
          if (response.status !== 'success' || !response.data) return;
          const nextChipType = mapBackendChipType(response.data.chip_type);
          setM1Pins(response.data.has_pins ? response.data.pin_definitions : []);
          setM1ChipName(response.data.chip_name || '');
          setM1ChipType(nextChipType);
          if (response.data.chip_name) setChipName(response.data.chip_name);
          setChipType(nextChipType);
        })
        .catch(() => {})
        .finally(() => setM1Loading(false));
    }

    getRagStatus()
      .then(response => {
        if (response.status === 'success' && response.data) {
          setRagStatus(response.data);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const fallback = DEFAULTS[chipType];
    setVcc(fallback.vcc);
    if (!m1ChipName) setChipName(fallback.name);
    if (!linkedFromModule1) {
      setItems(Object.fromEntries(fallback.items.map(item => [item, true])));
    }
  }, [chipType, linkedFromModule1, m1ChipName]);

  useEffect(() => {
    const payload = chipTypeLocked && m1FileId ? { file_id: m1FileId } : { chip_type: effectiveChipType };

    recommendCodeItems(payload)
      .then(response => {
        if (response.status !== 'success' || !response.data) return;
        const nextRecommended = response.data.recommended_items || [];
        const nextOptional = response.data.optional_items || [];
        setRecommendedItems(nextRecommended);
        setOptionalItems(nextOptional);
        setDetectedParams(response.data.detected_params || []);
        setRecommendationReasons(response.data.reason_summary || []);
        setRecommendationSource(response.data.source === 'module1' ? 'module1' : 'manual');

        setItems(previous => {
          const hasSelection = Object.values(previous).some(Boolean);
          if (chipTypeLocked || !hasSelection) {
            return Object.fromEntries(nextRecommended.map(item => [item, true]));
          }
          return previous;
        });
      })
      .catch(() => {});
  }, [chipTypeLocked, effectiveChipType, m1FileId]);

  const selected = useMemo(
    () =>
      Object.entries(items)
        .filter(([, value]) => value)
        .map(([key]) => key),
    [items],
  );

  const baseTemplates = effectiveChipType === 'ldo' ? templates.ldo : templates.digital;
  const recommendedSet = new Set(recommendedItems);
  const optionalSet = new Set(optionalItems);
  const orderedTemplates = [...baseTemplates].sort((a, b) => {
    const score = (itemId: string) => {
      if (recommendedSet.has(itemId)) return 0;
      if (optionalSet.has(itemId)) return 1;
      return 2;
    };
    const diff = score(a.id) - score(b.id);
    return diff !== 0 ? diff : a.id.localeCompare(b.id);
  });

  const safePlan = normalizePlan(result?.plan);
  const safeRun = normalizeRun(result?.run);
  const packageFiles = result?.package_export?.generated_files || [];
  const resultCode = result?.code || '';
  const resultFilename = result?.filename || 'output.cpp';
  const hasGeneratedCode = Boolean(resultCode);
  const hasBlockingPlan = Boolean(safePlan?.errors.length);
  const packageHasVector = packageFiles.some(file => file.relative_path.endsWith('.vecdio'));
  const packageHasPgs = packageFiles.some(file => file.relative_path.endsWith('.pgs'));
  const packageHighlights = packageFiles.filter(file =>
    /\.(vecdio|pgs|json|sln|vcxproj)$/i.test(file.relative_path) || file.relative_path.endsWith('source/test.cpp'),
  );
  const vectorSummary = {
    files: packageFiles.filter(file => /\.vecdio$/i.test(file.relative_path)).length,
    plans: packageFiles.filter(file => /vector_plan\.json$/i.test(file.relative_path)).length,
  };
  const pgsSummary = {
    files: packageFiles.filter(file => /\.pgs$/i.test(file.relative_path)).length,
    plans: packageFiles.filter(file => /pgs_plan\.json$/i.test(file.relative_path)).length,
  };
  const engineeringSummary = {
    jsons: packageFiles.filter(file => /\.json$/i.test(file.relative_path)).length,
    projects: packageFiles.filter(file => /\.(sln|vcxproj)$/i.test(file.relative_path)).length,
  };

  const runtimeSteps = useMemo(() => {
    const stepMap = new Map((safeRun?.steps || []).map(step => [step.agent, step]));
    return RUNTIME_STEPS.map(base => {
      const step = stepMap.get(base.agent);
      const loadingStep = stage === 'loading' && !step;
      return {
        ...base,
        status: step?.status || (loadingStep ? 'running' : stage === 'idle' ? 'pending' : 'pending'),
        warnings: step?.warnings || [],
        errors: step?.errors || [],
        artifacts: step?.artifacts || [],
      };
    });
  }, [safeRun, stage]);

  const completedSteps = runtimeSteps.filter(step => step.status === 'completed').length;
  const blockedSteps = runtimeSteps.filter(step => step.status === 'failed').length;
  const artifactTypeSummary = Array.from(
    (safeRun?.artifacts || []).reduce((accumulator, artifact) => {
      const type = artifact.type || 'unknown';
      accumulator.set(type, (accumulator.get(type) || 0) + 1);
      return accumulator;
    }, new Map<string, number>()),
  );

  const currentRunStatus = safeRun ? getRunStatusPresentation(safeRun.status) : getRunStatusPresentation(stage === 'loading' ? 'running' : 'pending');

  const toggle = (id: string) => setItems(previous => ({ ...previous, [id]: !previous[id] }));

  const handleGenerate = useCallback(async () => {
    if (!selected.length && !linkedFromModule1) {
      setErrMsg('请至少选择一个测试项。');
      setStage('error');
      return;
    }

    setStage('loading');
    setErrMsg('');
    setResult(null);

    try {
      const response = await generateCode({
        chip_name: chipName,
        chip_type: effectiveChipType,
        test_items: selected,
        user_prompt: prompt,
        file_id: m1FileId || undefined,
        auto_recommend: true,
        export_package: linkedFromModule1,
        vcc,
        vout,
        ...toPinPayload(m1Pins),
      });

      if (response.status === 'success' && response.data) {
        setResult(response.data);
        setStage('done');
      } else {
        setResult((response.data as CodegenResult | null) || null);
        setErrMsg(response.message || '代码生成失败。');
        setStage('error');
      }
    } catch (error: any) {
      setErrMsg(error.message || '代码生成失败。');
      setStage('error');
    }
  }, [chipName, effectiveChipType, linkedFromModule1, m1FileId, m1Pins, prompt, selected, vcc, vout]);

  const handleCopy = () => {
    if (!hasGeneratedCode) return;
    navigator.clipboard.writeText(resultCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!hasGeneratedCode) return;
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([resultCode], { type: 'text/plain' }));
    link.download = resultFilename;
    link.click();
  };

  return (
    <div className="flex flex-col gap-6 animate-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col gap-2">
        <h1 className="font-headline text-4xl font-bold tracking-tight text-on-surface">代码实验室</h1>
        <p className="max-w-4xl text-sm leading-relaxed text-on-surface-variant">
          这里不再只是一键出代码的黑盒页面。模块三会先生成一次运行记录，再按“测试规划、代码装配、静态校验、编译预检、工程打包”的顺序输出结果和工程包。
        </p>
      </div>

      {(linkedFromModule1 || m1Loading) && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className={`flex items-center gap-3 rounded-2xl border px-5 py-3 text-sm ${
            m1Pins.length > 0
              ? 'border-primary/30 bg-primary/10 text-on-surface'
              : m1Loading
                ? 'border-outline-variant/20 bg-surface-container text-on-surface-variant'
                : 'border-tertiary/30 bg-tertiary/10 text-on-surface-variant'
          }`}
        >
          {m1Loading ? (
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
          ) : m1Pins.length > 0 ? (
            <Link2 className="h-4 w-4 shrink-0 text-primary" />
          ) : (
            <Unlink className="h-4 w-4 shrink-0 text-tertiary" />
          )}
          <div className="flex-1">
            {m1Loading ? (
              <span>正在读取模块一结果和引脚定义...</span>
            ) : m1Pins.length > 0 ? (
              <span>
                已关联模块一结果：<span className="font-mono font-bold text-primary">{m1ChipName || chipName}</span>，已带入
                <span className="mx-1 font-bold text-primary">{m1Pins.length}</span>个引脚定义。
              </span>
            ) : (
              <span>检测到模块一文件，但暂未读取到引脚定义，当前会使用通用模板兜底。</span>
            )}
          </div>
        </motion.div>
      )}

      {ragStatus && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className={`flex items-center gap-3 rounded-2xl border px-5 py-2.5 text-xs ${
            ragStatus.ready
              ? 'border-secondary/25 bg-secondary/10 text-on-surface'
              : 'border-outline-variant/20 bg-surface-container text-on-surface-variant'
          }`}
        >
          <BookOpen className={`h-4 w-4 shrink-0 ${ragStatus.ready ? 'text-secondary' : 'text-on-surface-variant/50'}`} />
          <div className="flex flex-1 items-center gap-3">
            <span className="font-bold">RAG 知识库</span>
            {ragStatus.ready ? (
              <span className="text-on-surface-variant/70">
                已就绪 · <span className="font-mono text-secondary">{ragStatus.doc_count}</span> 个 STS8200S 片段 ·
                <span className="ml-1 font-mono text-on-surface-variant/50">{ragStatus.backend}</span>
              </span>
            ) : (
              <span className="text-on-surface-variant/60">当前未加载知识库，系统会优先使用企业样例和内置模板。</span>
            )}
          </div>
          <span
            className={`rounded px-2 py-0.5 text-[9px] font-mono ${
              ragStatus.ready ? 'bg-secondary/20 text-secondary' : 'bg-surface-container-highest text-on-surface-variant/40'
            }`}
          >
            {ragStatus.ready ? 'ONLINE' : 'OFFLINE'}
          </span>
        </motion.div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-sm">
            <SmallTitle>芯片类型</SmallTitle>

            {linkedFromModule1 && (
              <div className="mb-3 rounded-xl border border-primary/20 bg-primary/10 px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs font-bold text-primary">{chipTypeLocked ? '当前由模块一识别结果接管类型' : '当前处于手动覆盖模式'}</div>
                    <div className="mt-1 text-[11px] leading-relaxed text-on-surface-variant/80">
                      识别结果：{m1ChipName || chipName} / {m1ChipType || chipType}
                    </div>
                    <div className="mt-1 text-[11px] leading-relaxed text-on-surface-variant/70">
                      推荐来源：{recommendationSource === 'module1' ? '模块一结果 + 企业知识库' : '手动类型 + 企业知识库'}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setAllowManualChipType(previous => !previous)}
                    className="shrink-0 rounded-lg border border-primary/25 px-2.5 py-1 text-[10px] font-bold text-primary transition-colors hover:bg-primary/10"
                  >
                    {chipTypeLocked ? '手动覆盖' : '恢复自动'}
                  </button>
                </div>
              </div>
            )}

            <div className="flex flex-col gap-2">
              {CHIP_TYPES.map(item => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setChipType(item.id)}
                  disabled={chipTypeLocked}
                  className={`rounded-xl border p-3 text-left transition-all ${
                    effectiveChipType === item.id
                      ? 'border-primary bg-primary/10'
                      : 'border-outline-variant/20 bg-surface-container hover:bg-primary/5'
                  } ${chipTypeLocked ? 'cursor-not-allowed opacity-55 hover:bg-surface-container' : ''}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className={`text-sm font-bold ${effectiveChipType === item.id ? 'text-primary' : 'text-on-surface'}`}>{item.label}</div>
                    {linkedFromModule1 && m1ChipType === item.id && chipTypeLocked && (
                      <span className="rounded-md bg-primary/15 px-1.5 py-0.5 text-[9px] font-bold text-primary">模块一</span>
                    )}
                  </div>
                  <div className="mt-0.5 font-mono text-[10px] text-on-surface-variant/50">{item.sub}</div>
                </button>
              ))}
            </div>
          </section>

          <section className="flex flex-col gap-3 rounded-2xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-sm">
            <SmallTitle>参数配置</SmallTitle>
            {[
              { label: '芯片型号', type: 'text', value: chipName, onChange: (value: string) => setChipName(value) },
              { label: 'VCC (V)', type: 'number', value: vcc, onChange: (value: string) => setVcc(Number(value)), step: '0.25' },
              ...(effectiveChipType === 'ldo'
                ? [{ label: 'VOUT 额定值 (V)', type: 'number', value: vout, onChange: (value: string) => setVout(Number(value)), step: '0.1' }]
                : []),
            ].map(field => (
              <div key={field.label}>
                <label className="mb-1 block text-[10px] uppercase tracking-widest text-on-surface-variant/50">{field.label}</label>
                <input
                  type={field.type}
                  step={field.step}
                  value={field.value}
                  onChange={event => field.onChange(event.target.value)}
                  className="w-full rounded-lg border border-outline-variant/30 bg-surface-container px-3 py-2 text-sm font-mono text-on-surface transition-colors focus:border-primary/50 focus:outline-none"
                />
              </div>
            ))}
          </section>

          <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-sm">
            <SmallTitle>
              测试项选择 <span className="normal-case text-primary">({selected.length} 已选)</span>
            </SmallTitle>

            {(recommendedItems.length > 0 || linkedFromModule1) && (
              <div className="mb-3 rounded-xl border border-secondary/20 bg-secondary/10 px-3 py-2.5 text-[11px] text-on-surface-variant/80">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-bold text-secondary">{recommendationSource === 'module1' ? '自动推荐测试项' : '按当前类型推荐测试项'}</span>
                  {recommendedItems.length > 0 && <span className="font-mono text-secondary">{recommendedItems.length} 项</span>}
                </div>
                <div className="mt-1.5 leading-relaxed">
                  {chipTypeLocked
                    ? '当前推荐来自模块一提取结果和企业知识库，通常只需要在此基础上做增删确认。'
                    : '当前推荐跟随你选择的芯片类型变化，适合作为手工模式的起点。'}
                </div>
              </div>
            )}

            <div className="flex max-h-[420px] flex-col gap-1.5 overflow-y-auto pr-1">
              {orderedTemplates.map(template => {
                const isRecommended = recommendedSet.has(template.id);
                const isOptional = optionalSet.has(template.id);
                return (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => toggle(template.id)}
                    className={`group flex items-center gap-3 rounded-xl p-2.5 text-left transition-all ${
                      items[template.id] ? 'border border-primary/30 bg-primary/10' : 'border border-transparent hover:bg-surface-container'
                    }`}
                  >
                    <div
                      className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border-2 transition-colors ${
                        items[template.id] ? 'border-primary bg-primary' : 'border-outline-variant/50'
                      }`}
                    >
                      {items[template.id] && <CheckCircle2 className="h-3 w-3 text-on-primary" />}
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className={`font-mono text-xs font-bold ${items[template.id] ? 'text-primary' : 'text-on-surface'}`}>{template.id}</div>
                        {isRecommended && <span className="rounded bg-secondary/15 px-1.5 py-0.5 text-[9px] font-bold text-secondary">推荐</span>}
                        {!isRecommended && isOptional && (
                          <span className="rounded bg-surface-container-highest px-1.5 py-0.5 text-[9px] font-bold text-on-surface-variant/60">可选</span>
                        )}
                      </div>
                      <div className="mt-0.5 text-[10px] leading-relaxed text-on-surface-variant/65">{template.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-sm">
            <SmallTitle>补充说明</SmallTitle>
            <textarea
              value={prompt}
              onChange={event => setPrompt(event.target.value)}
              rows={4}
              placeholder="例如：双工位、保留企业样例里的测试节奏、优先生成工程包、给门限扫描补中文注释。"
              className="w-full resize-none rounded-xl border border-outline-variant/30 bg-surface-container px-3 py-2.5 text-xs text-on-surface transition-colors placeholder:text-on-surface-variant/30 focus:border-primary/50 focus:outline-none"
            />
          </section>

          <motion.button
            whileTap={{ scale: 0.97 }}
            type="button"
            onClick={handleGenerate}
            disabled={stage === 'loading' || (!selected.length && !linkedFromModule1)}
            className="flex items-center justify-center gap-3 rounded-xl bg-primary px-6 py-4 text-sm font-bold uppercase tracking-widest text-on-primary shadow-lg shadow-primary/20 transition-all hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {stage === 'loading' ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                正在创建运行记录...
              </>
            ) : (
              <>
                <Wand2 className="h-5 w-5" />
                创建本次生成
              </>
            )}
          </motion.button>
        </div>

        <div className="flex flex-col gap-4">
          <section className="rounded-2xl border border-primary/20 bg-surface-container-low p-5 shadow-sm">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <SmallTitle>运行主线</SmallTitle>
                <h2 className="text-xl font-bold text-on-surface">这次代码生成先创建 run，再逐步推进各阶段</h2>
                <p className="mt-2 text-sm leading-relaxed text-on-surface-variant/75">
                  这里优先展示运行阶段和阻断点，再展示最终代码结果。更详细的历史记录和跨次对比，请去“运行中心”查看。
                </p>
              </div>
              <div className={`rounded-xl border px-3 py-2 text-xs font-bold ${currentRunStatus.tone}`}>{currentRunStatus.label}</div>
            </div>

            <div className="grid gap-3 md:grid-cols-5">
              {runtimeSteps.map((step, index) => {
                const status = getRunStatusPresentation(step.status);
                return (
                  <div key={step.agent} className="rounded-xl border border-outline-variant/10 bg-surface-container p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">阶段 {index + 1}</div>
                      <span className={`rounded-md border px-2 py-0.5 text-[9px] font-bold ${status.tone}`}>{status.label}</span>
                    </div>
                    <div className="text-sm font-semibold text-on-surface">{step.label}</div>
                    <div className="mt-1 min-h-[52px] text-[11px] leading-relaxed text-on-surface-variant/70">{step.description}</div>
                    <div className="mt-3 flex flex-wrap gap-1.5 text-[10px] text-on-surface-variant/70">
                      <span className="rounded-md bg-surface px-2 py-0.5">产物 {step.artifacts.length}</span>
                      <span className="rounded-md bg-surface px-2 py-0.5">警告 {step.warnings.length}</span>
                      <span className="rounded-md bg-surface px-2 py-0.5">错误 {step.errors.length}</span>
                    </div>
                    {step.errors.length > 0 && (
                      <div className="mt-3 rounded-lg border border-error/20 bg-error/5 px-3 py-2 text-[10px] leading-relaxed text-error">
                        {step.errors[0]}
                      </div>
                    )}
                    {!step.errors.length && step.warnings.length > 0 && (
                      <div className="mt-3 rounded-lg border border-tertiary/20 bg-tertiary/5 px-3 py-2 text-[10px] leading-relaxed text-tertiary">
                        {step.warnings[0]}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="flex min-h-[720px] flex-col rounded-2xl border border-outline-variant/10 bg-[#0d1117] shadow-2xl">
              <div className="flex items-center justify-between rounded-t-2xl border-b border-white/5 bg-[#161b22] px-5 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex gap-1.5">
                    <div className="h-3 w-3 rounded-full bg-red-500/70" />
                    <div className="h-3 w-3 rounded-full bg-yellow-500/70" />
                    <div className="h-3 w-3 rounded-full bg-green-500/70" />
                  </div>
                  <Terminal className="h-4 w-4 text-gray-500" />
                  <span className="font-mono text-xs font-bold text-gray-400">{resultFilename}</span>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleCopy}
                    disabled={!hasGeneratedCode}
                    className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs font-bold text-gray-400 transition-all hover:border-primary/40 hover:text-primary disabled:opacity-30"
                  >
                    {copied ? <CheckCircle2 className="h-3.5 w-3.5 text-primary" /> : <Copy className="h-3.5 w-3.5" />}
                    {copied ? '已复制' : '复制'}
                  </button>
                  <button
                    type="button"
                    onClick={handleDownload}
                    disabled={!hasGeneratedCode}
                    className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-on-primary transition-all hover:brightness-110 disabled:opacity-30"
                  >
                    <Download className="h-3.5 w-3.5" />
                    下载 .cpp
                  </button>
                </div>
              </div>

              <div className="relative flex-1 overflow-hidden">
                <AnimatePresence mode="wait">
                  {stage === 'idle' && (
                    <motion.div
                      key="idle"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="flex h-full flex-col items-center justify-center gap-6 px-8 py-24 text-center"
                    >
                      <div className="rounded-2xl bg-primary/10 p-5">
                        <PlayCircle className="h-12 w-12 text-primary" />
                      </div>
                      <div>
                        <p className="mb-2 font-headline text-xl font-bold text-on-surface">等待创建本次运行</p>
                        <p className="max-w-2xl text-sm leading-relaxed text-on-surface-variant/70">
                          点击左下角按钮后，系统会先创建一次运行记录，再依次完成测试规划、代码装配、静态校验、编译预检和工程打包。
                        </p>
                      </div>
                    </motion.div>
                  )}

                  {stage === 'loading' && (
                    <motion.div
                      key="loading"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="flex h-full flex-col items-center justify-center gap-6 py-24 text-center"
                    >
                      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary/10">
                        <Loader2 className="h-10 w-10 animate-spin text-primary" />
                      </div>
                      <div>
                        <p className="mb-2 font-headline text-xl font-bold text-on-surface">运行已创建，正在推进模块三流程...</p>
                        <p className="text-sm text-on-surface-variant/70">请先关注上方阶段状态，代码和工程包会在后续阶段逐步补齐。</p>
                      </div>
                    </motion.div>
                  )}

                  {stage === 'error' && (
                    <motion.div
                      key="error"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="flex h-full flex-col items-center justify-center gap-4 px-8 py-24 text-center"
                    >
                      <div className="rounded-2xl bg-error/10 p-4">
                        <AlertCircle className="h-10 w-10 text-error" />
                      </div>
                      <div className="max-w-2xl">
                        <p className="mb-2 font-headline text-xl font-bold text-on-surface">本次运行被阻断</p>
                        <p className="text-sm leading-relaxed text-on-surface-variant">{errMsg}</p>
                      </div>
                      {hasBlockingPlan && (
                        <div className="w-full max-w-2xl rounded-2xl border border-error/20 bg-error/5 p-4 text-left">
                          <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-error">
                            <ShieldAlert className="h-4 w-4" />
                            生成前阻断项
                          </div>
                          <div className="flex flex-col gap-2">
                            {safePlan?.errors.slice(0, 4).map(entry => (
                              <div key={entry} className="rounded-lg border-l-2 border-error/50 bg-surface-container px-3 py-2 text-[11px] leading-relaxed text-on-surface-variant">
                                {entry}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      <button type="button" onClick={() => setStage('idle')} className="text-xs text-primary underline transition-opacity hover:opacity-70">
                        返回重试
                      </button>
                    </motion.div>
                  )}

                  {stage === 'done' && hasGeneratedCode && (
                    <motion.div key="done" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex h-full overflow-auto">
                      <div className="min-w-[3rem] shrink-0 select-none border-r border-white/5 bg-[#161b22] py-5 pl-3 pr-4 font-mono text-[11px] leading-5 text-gray-600">
                        {resultCode.split('\n').map((_, index) => (
                          <div key={index}>{index + 1}</div>
                        ))}
                      </div>
                      <pre
                        className="flex-1 overflow-x-auto py-5 pl-5 pr-6 font-mono text-[11px] leading-5 text-gray-300 [&_.syn-comment]:italic [&_.syn-comment]:text-gray-500 [&_.syn-kw]:font-bold [&_.syn-kw]:text-[#ff7b72] [&_.syn-num]:text-[#f2cc60] [&_.syn-str]:text-[#a5d6ff] [&_.syn-type]:font-bold [&_.syn-type]:text-[#79c0ff]"
                        dangerouslySetInnerHTML={{ __html: highlight(resultCode) }}
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            <div className="flex flex-col gap-4">
              <section className="rounded-2xl border border-secondary/20 bg-surface-container-low p-5 shadow-sm">
                <SmallTitle>推荐依据</SmallTitle>
                {detectedParams.length > 0 && (
                  <div className="mb-3">
                    <div className="mb-2 text-[9px] uppercase tracking-widest text-on-surface-variant/50">命中参数</div>
                    <div className="flex flex-wrap gap-1.5">
                      {detectedParams.slice(0, 10).map(item => (
                        <span key={item} className="rounded-md bg-secondary/10 px-2 py-0.5 text-[10px] font-mono font-bold text-secondary">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {recommendationReasons.length > 0 ? (
                  <div className="flex flex-col gap-2">
                    {recommendationReasons.slice(0, 3).map(reason => (
                      <div key={reason} className="rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-2 text-[11px] leading-relaxed text-on-surface-variant/80">
                        {reason}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-[11px] leading-relaxed text-on-surface-variant/75">
                    当前会优先结合模块一结果、企业样例和知识库推荐测试项。这里主要用来解释“为什么选这些项”，不是主操作区。
                  </div>
                )}
              </section>

              {safeRun && (
                <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-sm">
                  <SmallTitle>本次运行摘要</SmallTitle>
                  <div className="font-mono text-sm font-bold text-on-surface">{safeRun.run_id}</div>
                  <div className="mt-1 text-[11px] text-on-surface-variant/70">{getFlowLabel(safeRun.flow_name)}</div>
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <StatPill label="已完成" value={completedSteps} />
                    <StatPill label="需关注" value={blockedSteps} tone="tertiary" />
                    <StatPill label="产物" value={safeRun.artifacts.length} tone="secondary" />
                  </div>
                  {artifactTypeSummary.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {artifactTypeSummary.slice(0, 4).map(([type, count]) => (
                        <span key={type} className="rounded-md border border-secondary/20 bg-surface px-2 py-1 text-[10px] font-mono text-secondary">
                          {getArtifactLabel(type)} x {count}
                        </span>
                      ))}
                    </div>
                  )}
                </section>
              )}

              {(result || safePlan) && (
                <section className="rounded-2xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-sm">
                  <SmallTitle>交付摘要</SmallTitle>
                  {result && hasGeneratedCode && (
                    <div className="mb-3 grid grid-cols-2 gap-2">
                      <StatPill label="总行数" value={result.lines} />
                      <StatPill label="测试函数" value={result.functions} />
                    </div>
                  )}
                  {result?.static_analysis && (
                    <div className="rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-3 text-[11px]">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-on-surface">代码质量</span>
                        <span className="font-bold text-primary">{result.static_analysis.score}/100</span>
                      </div>
                      <div className="mt-1 text-on-surface-variant/75">{result.static_analysis.summary}</div>
                    </div>
                  )}
                  {result?.compile_validation?.attempted && (
                    <div className="mt-3 rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-3 text-[11px]">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-on-surface">编译预检</span>
                        <span className={result.compile_validation.passed ? 'font-bold text-primary' : 'font-bold text-tertiary'}>
                          {result.compile_validation.passed ? '通过' : '需修正'}
                        </span>
                      </div>
                      {result.compile_validation.diagnostics?.[0] && (
                        <div className="mt-1 line-clamp-3 text-on-surface-variant/75">{result.compile_validation.diagnostics[0]}</div>
                      )}
                    </div>
                  )}
                  {result?.package_export && (
                    <div className="mt-3 rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-3 text-[11px]">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-on-surface">工程包</span>
                        <span className="font-bold text-secondary">{packageFiles.length} 个文件</span>
                      </div>
                      <div className="mt-1 text-on-surface-variant/75">
                        VECDIO {packageHasVector ? '已准备' : '未准备'} / PGS {packageHasPgs ? '已准备' : '未准备'}
                      </div>
                      {result.package_export.download_url && (
                        <a
                          href={resolveBackendUrl(result.package_export.download_url)}
                          className="mt-3 inline-flex items-center gap-2 rounded-xl bg-primary px-3 py-2 text-xs font-bold text-on-primary transition-all hover:brightness-110"
                        >
                          <Download className="h-3.5 w-3.5" />
                          下载工程包 ZIP
                        </a>
                      )}
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() => setShowPackageDetails(value => !value)}
                    className="mt-3 inline-flex items-center gap-2 text-xs font-bold text-primary"
                  >
                    <ChevronRight className={`h-3.5 w-3.5 transition-transform ${showPackageDetails ? 'rotate-90' : ''}`} />
                    {showPackageDetails ? '收起更多细节' : '查看更多细节'}
                  </button>

                  <AnimatePresence initial={false}>
                    {showPackageDetails && (
                      <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                        {safePlan && (
                          <div className="mt-3 rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-3">
                            <div className="mb-2 text-[9px] uppercase tracking-widest text-on-surface-variant/50">生成计划</div>
                            <div className="mb-2 grid grid-cols-2 gap-2">
                              <StatPill label="场景" value={safePlan.scenario} tone="secondary" />
                              <StatPill label="资源数" value={safePlan.resources.length} tone="secondary" />
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              {safePlan.resources.slice(0, 8).map(resource => (
                                <span key={resource} className="rounded-md bg-secondary/10 px-2 py-0.5 text-[10px] font-mono font-bold text-secondary">
                                  {resource}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {result?.package_export && (
                          <div className="mt-3 rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-3">
                            <div className="mb-2 text-[9px] uppercase tracking-widest text-on-surface-variant/50">关键文件</div>
                            <div className="flex flex-wrap gap-1.5">
                              {packageHighlights.slice(0, 8).map(file => (
                                <span key={`highlight-${file.relative_path}`} className="rounded-md bg-surface-container-high px-2 py-1 font-mono text-[10px] text-on-surface">
                                  {file.relative_path}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {result?.retrieved_chunks && result.retrieved_chunks.length > 0 && (
                          <div className="mt-3 rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-3">
                            <div className="mb-2 text-[9px] uppercase tracking-widest text-on-surface-variant/50">RAG 片段</div>
                            <div className="flex flex-col gap-2">
                              {result.retrieved_chunks.slice(0, 3).map((chunk, index) => (
                                <div key={index} className="rounded-lg border-l-2 border-secondary/30 bg-secondary/5 p-3 text-[10px] text-on-surface-variant">
                                  <div className="mb-1 font-mono font-bold text-secondary">{chunk.source} · 评分 {chunk.score}</div>
                                  <p className="line-clamp-3 leading-relaxed opacity-80">{chunk.text}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </section>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
