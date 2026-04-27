export function getRunStatusPresentation(status?: string) {
  if (status === 'completed') {
    return { label: '已完成', tone: 'text-primary bg-primary/10 border-primary/20' };
  }
  if (status === 'failed') {
    return { label: '已阻断', tone: 'text-tertiary bg-tertiary/10 border-tertiary/20' };
  }
  if (status === 'running' || status === 'processing') {
    return { label: '执行中', tone: 'text-secondary bg-secondary/10 border-secondary/20' };
  }
  return { label: '待执行', tone: 'text-on-surface-variant bg-surface border-outline-variant/20' };
}

export function getFlowLabel(flowName?: string) {
  if (flowName === 'module1_extract') return '模块一提取流程';
  if (flowName === 'module2_resource_map') return '模块二资源映射流程';
  if (flowName === 'module3_codegen') return '模块三代码生成流程';
  return flowName || '未命名流程';
}

export function getStepLabel(agent: string) {
  const names: Record<string, string> = {
    codegen_planner: '测试规划',
    code_assembler: '代码装配',
    static_validator: '静态校验',
    compile_validator: '编译预检',
    engineering_packager: '工程打包',
    input_resolver: '输入解析',
    testplan_extractor: 'TestPlan 提取',
    mapping_input_resolver: '映射输入解析',
    resource_mapper: '资源映射',
  };
  return names[agent] || agent;
}

export function getArtifactLabel(type?: string) {
  const labels: Record<string, string> = {
    codegen_plan: '生成计划',
    generated_code: '生成代码',
    static_analysis: '静态分析',
    compile_validation: '编译预检结果',
    engineering_package: '工程包结果',
    source_pdf: '源 PDF',
    testplan_result: '提取结果',
    mapping_input: '映射输入',
    resource_mapping: '资源映射结果',
  };
  return labels[type || ''] || type || '未知产物';
}
