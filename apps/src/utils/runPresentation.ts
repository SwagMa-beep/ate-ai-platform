export function getRunStatusPresentation(status?: string) {
  if (status === 'completed') {
    return { label: '已完成', tone: 'text-primary bg-primary/10 border-primary/20' };
  }
  if (status === 'approved') {
    return { label: '已批准', tone: 'text-primary bg-primary/10 border-primary/20' };
  }
  if (status === 'rejected') {
    return { label: '已打回', tone: 'text-tertiary bg-tertiary/10 border-tertiary/20' };
  }
  if (status === 'failed') {
    return { label: '已失败', tone: 'text-tertiary bg-tertiary/10 border-tertiary/20' };
  }
  if (status === 'human_review_required') {
    return { label: '待复核', tone: 'text-accent bg-accent/10 border-accent/20' };
  }
  if (status === 'warning') {
    return { label: '有警告', tone: 'text-accent bg-accent/10 border-accent/20' };
  }
  if (status === 'running' || status === 'processing') {
    return { label: '执行中', tone: 'text-secondary bg-secondary/10 border-secondary/20' };
  }
  if (status === 'skipped') {
    return { label: '已跳过', tone: 'text-on-surface-variant bg-surface border-outline-variant/20' };
  }
  return { label: '待执行', tone: 'text-on-surface-variant bg-surface border-outline-variant/20' };
}

export function getFlowLabel(flowName?: string) {
  if (flowName === 'module1_extract') return '模块一提取流程';
  if (flowName === 'module2_resource_map') return '模块二资源映射流程';
  if (flowName === 'module3_codegen') return '模块三代码生成流程';
  if (flowName === 'full_ate_development') return '全链路开发流程';
  if (flowName === 'post_review_delivery') return '批准后交付流程';
  if (flowName === 'post_review_revision') return '打回后修订流程';
  return flowName || '未命名流程';
}

export function getStepLabel(agent: string) {
  const names: Record<string, string> = {
    input_resolver: '输入解析',
    testplan_extractor: 'TestPlan 提取',
    mapping_input_resolver: '映射输入解析',
    resource_mapper: '资源映射',
    codegen_planner: '测试规划',
    code_assembler: '代码装配',
    static_validator: '静态校验',
    compile_validator: '编译预检',
    review_agent: '工程复核',
    engineering_packager: '工程打包',
    approved_artifact_finalizer: '批准产物定版',
    delivery_packager: '交付摘要整理',
    revision_request_builder: '修改请求整理',
    revision_dispatch_planner: '修改路由规划',
    full_input_resolver: '全链路输入解析',
    full_testplan_extractor: '全链路 TestPlan 提取',
    full_param_validator: '参数校验',
    full_resource_mapper: '全链路资源映射',
    full_rag_retriever: 'RAG 检索',
    full_codegen_planner: '全链路测试规划',
    full_code_assembler: '全链路代码装配',
    full_static_validator: '全链路静态校验',
    full_compile_validator: '全链路编译预检',
    full_review_agent: '全链路工程复核',
    full_engineering_packager: '全链路工程打包',
  };
  return names[agent] || agent;
}

export function getArtifactLabel(type?: string) {
  const labels: Record<string, string> = {
    source_pdf: '原始 PDF',
    testplan_result: '提取结果',
    validation_summary: '参数校验摘要',
    mapping_input: '映射输入',
    resource_mapping: '资源映射结果',
    rag_context: 'RAG 上下文',
    codegen_plan: '生成计划',
    generated_code: '生成代码',
    static_analysis: '静态分析',
    compile_validation: '编译预检结果',
    review_summary: '复核摘要',
    engineering_package: '工程包',
    delivery_summary: '交付摘要',
    bench_checklist: '上机前检查表',
    final_package: '最终交付包',
    revision_request: '修改请求',
    revision_dispatch: '修改路由',
  };
  return labels[type || ''] || type || '未命名产物';
}
