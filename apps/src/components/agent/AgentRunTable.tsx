import { type AgentRunResult } from '../../api/backend';
import { getFlowLabel, getRunStatusPresentation } from '../../utils/runPresentation';
import { StatusBadge } from '../common/StatusBadge';
import { EmptyState } from '../common/EmptyState';

export function AgentRunTable({
  runs,
  selectedRunId,
  onSelect,
}: {
  runs: AgentRunResult[];
  selectedRunId?: string | null;
  onSelect: (runId: string) => void;
}) {
  if (!runs.length) {
    return <EmptyState title="还没有运行记录" description="发起一次 Agent 运行后，这里会展示历史 run 列表和详情入口。" />;
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-outline-variant/12">
      <table className="min-w-full divide-y divide-outline-variant/10">
        <thead className="bg-surface-container">
          <tr className="text-left text-xs uppercase tracking-wider text-on-surface-variant/60">
            <th className="px-4 py-3">Flow</th>
            <th className="px-4 py-3">状态</th>
            <th className="px-4 py-3">步骤数</th>
            <th className="px-4 py-3">产物数</th>
            <th className="px-4 py-3">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-outline-variant/10 bg-surface-container-low">
          {runs.map(run => {
            const presentation = getRunStatusPresentation(run.status);
            return (
              <tr key={run.run_id} className={selectedRunId === run.run_id ? 'bg-primary/8' : ''}>
                <td className="px-4 py-3">
                  <div className="font-medium text-on-surface">{getFlowLabel(run.flow_name)}</div>
                  <div className="mt-1 font-mono text-xs text-on-surface-variant/70">{run.run_id}</div>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={presentation.tone as Parameters<typeof StatusBadge>[0]['status']} label={presentation.label} />
                </td>
                <td className="px-4 py-3 text-sm text-on-surface-variant">{run.steps.length}</td>
                <td className="px-4 py-3 text-sm text-on-surface-variant">{run.artifacts.length}</td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => onSelect(run.run_id)}
                    className="rounded-lg bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary transition hover:bg-primary/15"
                  >
                    查看
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
