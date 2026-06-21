/**
 * MO 全站 UI 文案映射表
 *
 * 单一真相源：内部术语 → 用户可理解中文文案。
 * 所有页面/组件统一引用本文件，禁止在页面内硬编码内部术语。
 *
 * 规则：
 * - 首屏永远展示中文业务文案，不直接暴露 PRD ID、node id、tool name。
 * - 技术标识符（如 node id、evidence id）仅用于 tooltip / drawer / 调试区。
 * - 新增术语必须在本文档注册，不在页面内临时映射。
 */

// ─── 任务状态 ────────────────────────────────────────────────────────
export const TASK_STATUS_COPY: Record<string, { label: string; shortHelp: string }> = {
  CREATED:                  { label: '已创建',   shortHelp: '任务已创建，等待开始规划' },
  PLANNING:                 { label: '计划生成中', shortHelp: '系统正在分析目标并生成调研计划' },
  WAITING_USER_CLARIFICATION: { label: '等待澄清', shortHelp: '系统需要你补充信息才能继续规划' },
  WAITING_USER_APPROVAL:    { label: '等待你批准', shortHelp: '调研计划已生成，请审阅并批准' },
  PLAN_APPROVED:            { label: '计划已批准', shortHelp: '计划已批准，可以开始执行调研' },
  EXECUTING:                { label: '执行中',   shortHelp: '正在按计划执行调研步骤' },
  REPLANNING:               { label: '重新规划中', shortHelp: '执行中遇到新情况，正在调整计划' },
  REPORT_DRAFT:             { label: '报告草稿', shortHelp: '报告已生成，请审阅内容' },
  REVIEW_REQUIRED:          { label: '待审阅',   shortHelp: '报告中有待确认的结论，请审阅' },
  DONE:                     { label: '已完成',   shortHelp: '任务已完成，可查看和导出报告' },
  FAILED:                   { label: '失败',     shortHelp: '任务执行失败，可查看错误详情' },
}

// ─── 工作流节点状态 ─────────────────────────────────────────────────
export const NODE_STATUS_COPY: Record<string, { label: string; shortHelp: string }> = {
  pending:      { label: '待执行',   shortHelp: '该步骤尚未开始' },
  running:      { label: '执行中',   shortHelp: '该步骤正在运行' },
  waiting_user: { label: '等待你确认', shortHelp: '该步骤需要你的审批或输入才能继续' },
  completed:    { label: '已完成',   shortHelp: '该步骤已成功完成' },
  failed:       { label: '失败',     shortHelp: '该步骤执行失败，可查看错误详情' },
  skipped:      { label: '已跳过',   shortHelp: '该步骤已被跳过' },
}

// ─── 系统模式 / 工作流阶段 ──────────────────────────────────────────
export const SYSTEM_MODE_COPY = {
  planMode: {
    label: '调研计划',
    description: '系统正在分析你的研究目标，拆解调研步骤',
    whatNow: '制定调研计划 — 明确研究范围、候选仓库、评估维度',
  },
  executeMode: {
    label: '执行调研',
    description: '按照批准的计划逐步执行调研',
    whatNow: '执行调研步骤 — 读取仓库、分析代码、评估复现性、生成对比',
  },
  replanMode: {
    label: '重新规划',
    description: '执行中遇到新情况，需要调整调研计划',
    whatNow: '调整计划 — 根据新发现的信息更新调研方向',
  },
  reportMode: {
    label: '生成报告',
    description: '基于调研结果生成结构化报告',
    whatNow: '生成调研报告 — 汇总证据、对比分析、给出建议',
  },
} as const

// ─── 工作流节点 / 工具类型 ──────────────────────────────────────────
export const NODE_TYPE_COPY: Record<string, { label: string; description: string }> = {
  task_intake:             { label: '任务录入',     description: '解析研究目标和资料' },
  plan_builder:            { label: '计划制定',     description: '分析目标并生成调研计划' },
  user_clarification:      { label: '用户澄清',     description: '与用户确认不明确的信息' },
  repo_ingest:             { label: '读取仓库资料',  description: '获取仓库的 README、文件结构、依赖等信息' },
  code_understanding:      { label: '分析代码结构',  description: '识别核心模块、入口、配置和依赖关系' },
  paper_research:          { label: '论文与资料调研', description: '搜索和分析相关论文与文档' },
  reproducibility_analysis:{ label: '评估复现难度',  description: '评估安装步骤、依赖风险、示例和文档质量' },
  comparison_builder:      { label: '对比分析',     description: '基于多维度对比候选仓库的优劣' },
  critic_review:           { label: '批评审阅',     description: '反思性检查调研结论的可靠性和完整性' },
  report_writer:           { label: '报告撰写',     description: '汇总调研结果生成结构化报告' },
  sandbox_runner:          { label: '沙箱执行',     description: '在隔离环境中运行仓库代码（需审批）' },
}

// ─── 计划步骤工具 ────────────────────────────────────────────────────
export const STEP_TOOL_COPY: Record<string, { label: string; description: string }> = {
  repo_ingest:       { label: '读取仓库资料', description: '获取仓库结构和文档信息' },
  code_understanding:{ label: '分析代码结构', description: '理解核心模块和代码架构' },
  paper_research:    { label: '论文与资料调研', description: '搜索和分析相关文献' },
  repro_eval:        { label: '评估复现难度', description: '评估安装、依赖、测试等维度' },
  comparison:        { label: '对比分析',    description: '多维度对比候选仓库' },
  critic_review:     { label: '批评审阅',    description: '检查结论可靠性和完整性' },
  report_writer:     { label: '报告撰写',    description: '汇总生成调研报告' },
  sandbox_runner:    { label: '沙箱执行',    description: '在隔离环境运行代码' },
}

// ─── 证据与结论 ──────────────────────────────────────────────────────
export const EVIDENCE_COPY = {
  evidenceItem: {
    label: '证据',
    description: '支撑结论的原始数据或引用来源',
  },
  reportClaim: {
    label: '结论',
    description: '基于证据得出的调研发现',
  },
  evidenceChain: {
    label: '证据链',
    description: '从原始数据到最终结论的完整追溯路径',
  },
} as const

export const CLAIM_LABEL_COPY: Record<string, { label: string; description: string; colorHint: string }> = {
  fact:           { label: '事实',   description: '有直接证据支持的确定事实',        colorHint: 'emerald' },
  inference:      { label: '推断',   description: '基于证据推导的合理判断',           colorHint: 'blue' },
  recommendation: { label: '建议',   description: '基于分析给出的行动建议',           colorHint: 'violet' },
  pending:        { label: '待确认', description: '证据不足，需要进一步确认的结论',   colorHint: 'amber' },
}

export const EVIDENCE_STRENGTH_COPY: Record<string, { label: string; description: string }> = {
  strong:  { label: '强证据', description: '来自仓库代码、运行日志或正式文档的直接证据' },
  medium:  { label: '中等证据', description: '来自可靠来源但有一定推断空间' },
  weak:    { label: '弱证据', description: '来自间接引用或模型推断，需要人工确认' },
  missing: { label: '缺失证据', description: '缺少支撑证据，该结论需要补充验证' },
}

export const SOURCE_TYPE_COPY: Record<string, { label: string; icon: string }> = {
  repo_file:         { label: '仓库文件',   icon: 'FileCode' },
  paper:             { label: '论文',       icon: 'FileText' },
  web:               { label: '网络来源',   icon: 'Globe' },
  run_log:           { label: '运行日志',   icon: 'Terminal' },
  user_confirmation: { label: '用户确认',   icon: 'UserCheck' },
  model_inference:   { label: '模型推断',   icon: 'Brain' },
}

// ─── 风险等级 ────────────────────────────────────────────────────────
export const RISK_LEVEL_COPY: Record<string, { label: string; description: string; colorHint: string }> = {
  low:    { label: '低风险', description: '常规操作，出错概率低',                    colorHint: 'emerald' },
  medium: { label: '中风险', description: '有一定复杂度或依赖外部服务，需留意结果',   colorHint: 'amber' },
  high:   { label: '高风险', description: '涉及安装依赖、执行代码或大模型调用，需要审批', colorHint: 'red' },
}

// ─── 其他业务术语 ────────────────────────────────────────────────────
export const BUSINESS_TERM_COPY: Record<string, { label: string; description: string }> = {
  repoDiscovery:  { label: '候选仓库发现',   description: '根据研究目标自动搜索并推荐相关 GitHub 仓库' },
  repoCandidate:  { label: '候选仓库',       description: '系统发现或你提供的待调研仓库' },
  repoCard:       { label: '仓库档案',       description: '仓库的基本信息、结构、依赖和风险概要' },
  comparisonMatrix:{ label: '对比矩阵',       description: '基于多维度对候选仓库进行打分和对比' },
  reportRubric:   { label: '评分维度',       description: '仓库对比的评估维度和权重设置' },
  demoMode:       { label: '示例任务',       description: '使用预置数据快速体验完整流程' },
  modelGateway:   { label: '模型路由',       description: '根据任务类型自动选择最合适的 AI 模型' },
  sandbox:        { label: '沙箱环境',       description: '隔离的安全执行环境' },
  smokeTest:      { label: '快速验证',       description: '运行仓库的基本测试以确认可用性' },
}

// ─── 对比维度 ────────────────────────────────────────────────────────
export const COMPARISON_DIMENSION_COPY: Record<string, { label: string; description: string }> = {
  technical_route: {
    label: '技术路线',
    description: '核心架构、算法路线和技术选型是否清晰合适',
  },
  documentation: {
    label: '文档完整度',
    description: 'README、教程、API 文档和示例是否足够完整',
  },
  reproducibility: {
    label: '可复现性',
    description: '安装、示例、测试、数据和环境要求是否容易复现',
  },
  engineering_fit: {
    label: '工程契合度',
    description: '依赖、接口、部署和集成方式是否适合落地',
  },
  research_value: {
    label: '研究价值',
    description: '是否能支撑论文调研、实验复现或方案选型',
  },
  extensibility: {
    label: '可扩展性',
    description: '模块边界、插件能力和二次开发空间',
  },
  risks: {
    label: '主要风险',
    description: '依赖、维护、版本、证据或复现方面的风险',
  },
  recommended_use_case: {
    label: '适用场景',
    description: '更适合使用该仓库的典型任务或用户场景',
  },
}

// ─── 页面引导文本 ────────────────────────────────────────────────────
export const PAGE_GUIDE_COPY = {
  taskCreate: {
    title: '创建调研任务',
    whatNow: '填写你的研究目标 — 系统将据此发现相关仓库并制定调研计划',
    primaryAction: '创建并开始规划',
    repoUrlHelp: '可留空，系统会自动发现推荐候选仓库；也可粘贴 GitHub 链接',
  },
  planReview: {
    title: '审阅调研计划',
    whatNow: '审阅系统生成的调研计划 — 确认目标、澄清疑问、选择仓库、批准执行',
    primaryAction: '批准并开始执行',
    blockReasons: {
      noRepoSelected: '请至少选择一个候选仓库',
      unansweredRequired: '请回答必填的澄清问题',
      waitingApproval: '计划已就绪，请批准后开始执行',
    },
  },
  workflow: {
    title: '执行工作流',
    whatNow: '查看调研执行进度 — 等待中的节点需要你的审批或输入',
    primaryAction: '处理待审批节点',
    blockingNodeHelp: '有一个步骤需要你确认，点击高亮节点查看详情并审批',
  },
  comparison: {
    title: '仓库对比',
    whatNow: '查看多仓库对比结果 — 可调整权重重新打分',
    primaryAction: '查看对比报告',
  },
  report: {
    title: '调研报告',
    whatNow: '查看完整的调研报告 — 包含证据、结论和建议',
    primaryAction: '导出报告',
    notGenerated: '报告尚未生成，请点击按钮开始生成',
  },
  history: {
    title: '历史任务',
    whatNow: '查看和管理所有历史调研任务',
    primaryAction: '新建任务',
    empty: '还没有调研任务，创建一个开始吧',
  },
} as const

// ─── 报告视图 ────────────────────────────────────────────────────────
export const REPORT_VIEW_COPY = {
  readerSummary: {
    label: '阅读概要',
    description: '面向人阅读的报告摘要，不直接展示原始数据。',
  },
  readerFull: {
    label: '完整阅读',
    description: '连续阅读润色后的完整报告。',
  },
  readerSection: {
    label: '章节阅读',
    description: '阅读单个润色后的报告章节。',
  },
  dataOverview: {
    label: '数据视图',
    description: '查看结构化草稿、章节种子、结论与证据。',
  },
  evidence: {
    label: '证据附录',
    description: '查看完整证据链和来源定位。',
  },
  structuredDraft: '结构化章节草稿',
  seedNarratives: '节点章节种子',
  seedStructuredData: '结构化数据快照',
  polishWarnings: '润色警告',
} as const

// ─── 通用 CTA（Call To Action）文案 ──────────────────────────────────
export const CTA_COPY = {
  create:       '创建任务',
  approve:      '批准执行',
  regenerate:   '重新生成',
  submit:       '提交确认',
  confirm:      '确认',
  cancel:       '取消',
  delete:       '删除',
  redo:         '重开任务',
  export:       '导出报告',
  loadDemo:     '加载示例任务',
  retry:        '重试',
  backToHistory:'返回历史',
  viewReport:   '查看报告',
  viewWorkflow: '查看工作流',
  continueTask: '继续任务',
} as const

// ─── 空状态 / 错误状态文案 ──────────────────────────────────────────
export const EMPTY_STATE_COPY = {
  generic: {
    title: '暂无数据',
    description: '当前没有可显示的内容',
  },
  historyEmpty: {
    title: '还没有调研任务',
    description: '创建你的第一个调研任务，或加载示例任务快速体验',
  },
  evidenceEmpty: {
    title: '暂无证据',
    description: '执行调研步骤后将生成证据条目',
  },
  reportNotGenerated: {
    title: '报告尚未生成',
    description: '完成调研执行后可以生成报告',
  },
} as const

// ─── 危险操作确认文案 ────────────────────────────────────────────────
export const DESTRUCTIVE_CONFIRM_COPY = {
  deleteTask: {
    title: '确认删除任务',
    description: '删除后任务及其所有数据将被永久移除，此操作不可撤销',
    confirmLabel: '确认删除',
  },
  deleteExecutingBlocked: {
    title: '无法删除',
    description: '任务正在执行中，请等待执行完成或取消后再删除',
  },
  rerunTask: {
    title: '确认重开任务',
    description: '将基于当前任务的输入创建新任务，原任务不受影响',
    confirmLabel: '确认重开',
  },
} as const
