import { CheckCircle, ShieldAlert, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  type AgentRunResult,
  approveAgentRun,
  rejectAgentRunWithRouting,
} from '../../api/backend';
import { EmptyState } from '../common/EmptyState';
import { StatusBadge } from '../common/StatusBadge';

type AgentReview = {
  overall_status?: 'pass' | 'needs_human_review' | 'blocked';
  risk_level?: 'low' | 'medium' | 'high';
  summary?: string;
  completedItems?: string[];
  risks?: string[];
  must_review_items?: string[];
  recommendations?: string[];
  confidence_score?: number;
};

type RejectionType = 'input_issue' | 'engineering_decision' | 'auto_fixable';

export function readAgentReview(run: AgentRunResult | null): AgentReview | null {
  const shared = run?.shared as Record<string, unknown> | undefined;
  const review = shared?.review;
  return review && typeof review === 'object' ? (review as AgentReview) : null;
}

function getRejectionTypeLabel(type?: string) {
  if (type === 'input_issue') return '输入问题';
  if (type === 'engineering_decision') return '工程决策问题';
  if (type === 'auto_fixable') return '可自动修复';
  return '未分类';
}

export function AgentReviewPanel({
  run,
  onDecision,
}: {
  run: AgentRunResult | null;
  onDecision?: (updatedRun?: AgentRunResult) => void;
}) {
  const review = readAgentReview(run);
  const [submitting, setSubmitting] = useState<'approve' | 'reject' | null>(null);
  const [decision, setDecision] = useState<'approved' | 'rejected' | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [rejectReason, setRejectReason] = useState('需要补充修改后再继续。');
  const [rejectionType, setRejectionType] = useState<RejectionType>('engineering_decision');

  useEffect(() => {
    setDecision(null);
    setSubmitting(null);
    setErrorMsg('');
    setRejectReason('需要补充修改后再继续。');
    setRejectionType('engineering_decision');
  }, [run?.run_id]);

  const effectiveStatus = run?.status === 'approved' || run?.status === 'rejected' ? run.status : decision;

  const evidence = useMemo(() => {
    const shared = run?.shared as Record<string, unknown> | undefined;
    const generated = (shared?.generated_result as Record<string, unknown> | undefined) || {};
    const staticAnalysis = (generated.static_analysis as Record<string, unknown> | undefined) || {};
    const compileValidation = (generated.compile_validation as Record<string, unknown> | undefined) || {};
    const extraction = (shared?.extraction_result as Record<string, unknown> | undefined) || {};
    const qualityScores = (run?.steps || []).map(step => step.quality?.score).filter((value): value is number => typeof value === 'number');
    const averageQuality = qualityScores.length
      ? Math.round((qualityScores.reduce((sum, item) => sum + item, 0) / qualityScores.length) * 100)
      : null;
    return {
      artifactCount: run?.artifacts?.length || 0,
      staticPassed: staticAnalysis.passed === true,
      compilePassed: compileValidation.passed === true,
      extractionPinCount: typeof extraction.pin_count === 'number' ? extraction.pin_count : null,
      averageQuality,
      warningCount: run?.warnings?.length || 0,
      errorCount: run?.errors?.length || 0,
    };
  }, [run]);

  if (effectiveStatus === 'approved' || effectiveStatus === 'rejected') {
    const reviewDecision = run?.review_decision;
    return (
      <div className="space-y-4">
        <div className="rounded-2xl border border-tertiary/20 bg-tertiary/10 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-on-surface">工程复核决策</div>
              <p className="mt-1 text-sm text-on-surface-variant/80">
                {effectiveStatus === 'approved'
                  ? '运行已批准，可以继续后续工程步骤。'
                  : '运行已打回，请按复核类型和修改建议处理。'}
              </p>
            </div>
            <StatusBadge
              status={effectiveStatus === 'approved' ? 'success' : 'failed'}
              label={effectiveStatus === 'approved' ? '已批准' : '已打回'}
            />
          </div>
          {reviewDecision?.reason ? (
            <div className="mt-3 space-y-1 text-xs text-on-surface-variant/70">
              <div>打回原因：{reviewDecision.reason}</div>
              {reviewDecision.rejection_type ? <div>问题类型：{getRejectionTypeLabel(reviewDecision.rejection_type)}</div> : null}
              {reviewDecision.resolution_owner ? (
                <div>处理责任：{reviewDecision.resolution_owner === 'agent' ? 'AI 自动修复' : '用户 / 工程师补充修改'}</div>
              ) : null}
              {reviewDecision.next_action ? <div>下一步：{reviewDecision.next_action}</div> : null}
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  if (!review) {
    return (
      <EmptyState
        title="暂未生成复核结论"
        description="完成包含 ReviewAgent 的运行后，这里会展示风险等级、复核依据和下一步建议。"
        icon={<ShieldAlert className="h-5 w-5" />}
      />
    );
  }

  const tone =
    review.overall_status === 'blocked'
      ? 'failed'
      : review.overall_status === 'needs_human_review'
        ? 'human_review_required'
        : 'success';
  const riskText = review.risk_level ? review.risk_level.toUpperCase() : 'UNKNOWN';
  const isReviewRequired = run?.status === 'human_review_required';

  const handleApprove = async () => {
    if (!run?.run_id) return;
    setSubmitting('approve');
    setErrorMsg('');
    try {
      const res = await approveAgentRun(run.run_id);
      if (res.status === 'success') {
        setDecision('approved');
        onDecision?.(res.data || undefined);
      } else {
        setErrorMsg(res.message || '操作失败');
      }
    } catch {
      setErrorMsg('网络异常，请重试');
    } finally {
      setSubmitting(null);
    }
  };

  const handleReject = async () => {
    if (!run?.run_id) return;
    if (!rejectReason.trim()) {
      setErrorMsg('请先填写打回原因。');
      return;
    }
    setSubmitting('reject');
    setErrorMsg('');
    try {
      const res = await rejectAgentRunWithRouting(run.run_id, {
        reviewer: 'ATE Engineer',
        reason: rejectReason.trim(),
        rejection_type: rejectionType,
      });
      if (res.status === 'success') {
        setDecision('rejected');
        onDecision?.(res.data || undefined);
      } else {
        setErrorMsg(res.message || '操作失败');
      }
    } catch {
      setErrorMsg('网络异常，请重试');
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-tertiary/20 bg-tertiary/10 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-on-surface">工程复核结论</div>
            <p className="mt-1 text-sm text-on-surface-variant/80">
              {review.summary || '本次运行需要工程师结合校验结果、资源映射和中间产物后再决定是否继续。'}
            </p>
          </div>
          <StatusBadge
            status={tone}
            label={
              review.overall_status === 'blocked' ? '已阻断' : review.overall_status === 'needs_human_review' ? '需要人工复核' : '通过'
            }
          />
        </div>
        <div className="mt-3 text-xs font-medium text-tertiary">
          复核不是判断 AI 是否完美，而是判断当前结果是否已经具备继续工程流转的最低条件。
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant/55">风险等级</div>
          <div className="mt-2 text-lg font-bold text-on-surface">{riskText}</div>
        </div>
        {typeof review.confidence_score === 'number' ? (
          <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant/55">复核信心</div>
            <div className="mt-2 text-lg font-bold text-on-surface">{(review.confidence_score * 100).toFixed(0)}%</div>
          </div>
        ) : null}
        <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant/55">关键产物</div>
          <div className="mt-2 text-lg font-bold text-on-surface">{evidence.artifactCount}</div>
        </div>
        <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant/55">提取引脚数</div>
          <div className="mt-2 text-lg font-bold text-on-surface">{evidence.extractionPinCount ?? '-'}</div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant/55">静态检查</div>
          <div className="mt-2 text-sm font-semibold text-on-surface">{evidence.staticPassed ? '通过' : '待确认 / 未通过'}</div>
        </div>
        <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant/55">编译预检</div>
          <div className="mt-2 text-sm font-semibold text-on-surface">{evidence.compilePassed ? '通过' : '待确认 / 未通过'}</div>
        </div>
        <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant/55">警告数</div>
          <div className="mt-2 text-lg font-bold text-on-surface">{evidence.warningCount}</div>
        </div>
        <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant/55">平均质量</div>
          <div className="mt-2 text-lg font-bold text-on-surface">{evidence.averageQuality ?? '-'}%</div>
        </div>
      </div>

      {(review.must_review_items || []).length ? (
        <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant/55">必须复核项</div>
          <ul className="mt-2 space-y-2 text-sm text-on-surface-variant/85">
            {(review.must_review_items || []).map(item => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {(review.recommendations || []).length ? (
        <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant/55">下一步建议</div>
          <ul className="mt-2 space-y-2 text-sm text-on-surface-variant/85">
            {(review.recommendations || []).map(item => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {isReviewRequired ? (
        <div className="rounded-2xl border border-tertiary/30 bg-tertiary/5 p-4">
          <div className="text-sm font-semibold text-on-surface">人工复核决策</div>
          <p className="mt-1 text-xs text-on-surface-variant/70">
            同意继续表示结果已经具备继续工程流转的最低条件。打回修改时请明确问题类型和原因，系统会生成后续 revision run。
          </p>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <label className="block">
              <div className="mb-1.5 text-xs font-semibold text-on-surface-variant/70">打回类型</div>
              <select
                value={rejectionType}
                onChange={event => setRejectionType(event.target.value as RejectionType)}
                className="w-full rounded-xl border border-outline-variant/20 bg-surface px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/35"
              >
                <option value="engineering_decision">工程决策问题</option>
                <option value="input_issue">输入问题</option>
                <option value="auto_fixable">可自动修复</option>
              </select>
            </label>

            <label className="block">
              <div className="mb-1.5 text-xs font-semibold text-on-surface-variant/70">打回原因</div>
              <textarea
                value={rejectReason}
                onChange={event => setRejectReason(event.target.value)}
                rows={3}
                className="w-full rounded-xl border border-outline-variant/20 bg-surface px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/35"
              />
            </label>
          </div>

          <div className="mt-3 rounded-xl border border-outline-variant/12 bg-surface-container p-3 text-xs text-on-surface-variant/75">
            {rejectionType === 'auto_fixable'
              ? '当前会按 “AI 自动修复” 路线处理，后续 revision run 会明确使用现有 artifacts、校验结果和打回原因。'
              : rejectionType === 'input_issue'
                ? '当前会按“用户补资料 / 换文档”路线处理，后续 revision run 会明确指出需要替换输入。'
                : '当前会按“用户 / 工程师补充决策”路线处理，后续 revision run 会明确指出需要补充的工程约束。'}
          </div>

          <div className="mt-4 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={handleReject}
              disabled={!!submitting}
              className="inline-flex items-center gap-1.5 rounded-lg border border-rose-400/20 bg-rose-500/10 px-3.5 py-2 text-sm font-medium text-rose-300 hover:bg-rose-500/20 disabled:opacity-50"
            >
              <XCircle className="h-4 w-4" />
              {submitting === 'reject' ? '处理中...' : '打回修改'}
            </button>
            <button
              type="button"
              onClick={handleApprove}
              disabled={!!submitting}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
            >
              <CheckCircle className="h-4 w-4" />
              {submitting === 'approve' ? '处理中...' : '同意继续'}
            </button>
          </div>

          {errorMsg ? <p className="mt-2 text-xs text-rose-300">{errorMsg}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
