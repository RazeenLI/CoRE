# Evaluation Metrics Registry

用途：集中记录项目需要评估的维度、指标及完成状态，避免遗漏或重复。新增实验指标时应同步更新本文件。

状态：`DONE` 已由统一 evaluator 或独立实验实现；`DERIVABLE` 现有输出可计算但尚未正式集成；`PARTIAL` 只有部分实现；`TODO` 尚未实现。

## 1. Result Coverage 与可运行性

先确认方法是否对全部 cases 产生了可加载结果，否则准确率可能只是在成功子集上计算。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Result Coverage | DONE | 区分模型质量与 missing/failed outputs，避免忽略失败 case。 |
| Pipeline Success Rate | DERIVABLE | 与 Result Coverage 不同，它检查流程是否正常结束，即使失败流程可能残留可评估 proposal。 |
| Load/Parse Failure Rate | DONE | 单独暴露格式错误或损坏输出，不与语义错误混合。 |

## 2. Evolution Decision

评估系统是否正确判断 `insert_table`、`extend_table` 或 `create_table`；这是任务的最高层决策，但不能替代内部操作评估。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Decision Accuracy | DONE | 给出总体 operation 判断正确率，最直观但受类别分布影响。 |
| Decision Macro-F1 | DONE | 对三类 decision 等权，避免大类别掩盖小类别失败。 |
| Per-class Precision/Recall/F1 | DERIVABLE | 定位某一 operation 的系统性过预测或漏预测，Accuracy 无法显示方向。 |
| Decision Confusion Matrix | DERIVABLE | 显示具体错误方向，例如 MONDIAL 的 `create→extend`。 |
| Create→Extend Rate | DERIVABLE | 专门量化 create/extend 边界问题，不被其他 confusion 稀释。 |

## 3. Decision 与内部操作解耦

Decision 正确不代表 column/table/constraint actions 正确；Decision 错误时，部分内部操作也可能仍有价值。必须把两层分开评价。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Action F1 conditioned on correct decision | TODO | 检查在 operation 已判断正确时，proposal construction 还剩多少错误。 |
| Action F1 conditioned on wrong decision | TODO | 衡量错误 decision 下内部 mappings 是否仍部分正确。 |
| Correct-decision / Wrong-action Rate | TODO | 直接统计“外层判断对但内部执行错”的 cases，定位 Builder/Evolutor action 问题。 |
| Wrong-decision / Useful-action Rate | TODO | 识别严格 Decision Accuracy 低估的部分正确结果。 |
| Decision–Action Consistency Rate | PARTIAL | 检查 decision 与 table/column actions 是否自洽；当前 validity 只覆盖其中部分规则。 |
| Operation-only Proposal F1 | DERIVABLE | 从 Proposal F1 中移除 decision fact，避免 decision 对内部操作质量重复计分。 |

## 4. Target Relation 与 Column Placement

评估 incoming attributes 被放到哪里；它比 decision 更细，但不包含约束与最终数据库状态。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Target-table Accuracy | DONE | 对 `insert/extend` 检查目标 relation，区别于仅判断 operation 类型。 |
| Target-table Candidate Count | DONE | 发现一次 proposal 映射多个目标表等异常，Accuracy 本身不显示。 |
| Column Placement Precision | DONE | 惩罚多余或错误的 source→target mappings。 |
| Column Placement Recall | DONE | 惩罚遗漏的正确 mappings。 |
| Column Placement Micro-F1 | DONE | 按所有 column facts 汇总，适合总体比较。 |
| Column Placement Macro-F1 | DONE | 每个 case 等权，避免宽表主导结果。 |
| Exact Column-placement Accuracy | TODO | 要求一个 case 的全部 placements 都正确，比平均 F1 更严格。 |

## 5. Proposal Actions

评估 proposal 中的 table/column结构操作是否与 reference 一致；它比 Column F1 更完整，但当前不能替代 constraint-specific metrics。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Proposal Fact Precision/Recall/F1 | DONE | 联合比较 decision、target、create/add/map facts，提供总体 proposal 相似度。 |
| Proposal Fact Macro-F1 | DONE | 每个 case 等权，补充 micro-F1。 |
| Table-action Exact Match | TODO | 单独检查 create/map table actions，避免被大量 column facts 稀释。 |
| Column-action Exact Match | TODO | 检查 action 类型和完整 mapping 集，而不只逐项累计。 |
| Operation-only Fact F1 | DERIVABLE | 去除 decision fact后衡量具体 schema operations。 |

## 6. Constraint Quality

PK/FK 等约束决定更新后的关系结构；只检查 proposal 合法不代表约束与 reference 一致。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Primary-key Precision/Recall/F1 | TODO | 区分遗漏、错误和多余 PK，validity 只能检查是否合法。 |
| Foreign-key Precision/Recall/F1 | TODO | 检查 FK 两端 table/columns 是否与 reference 一致。 |
| Constraint Exact Match | TODO | 要求一个 case 的全部预期 constraints 正确且无额外约束。 |
| Broken-FK Count/Rate | DONE | 检查 FK 是否引用不存在或不兼容对象，衡量合法性而非语义正确性。 |

## 7. Completeness 与 Structural Validity

评估 proposal 是否覆盖输入并能形成内部一致的数据库；这类指标不能说明设计是否符合 reference。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Required-column Coverage | DONE | 检查 incoming columns 是否被纳入 proposal，不判断放置位置是否正确。 |
| Full-column Coverage Rate | DONE | 统计完全无遗漏的 cases，比平均 coverage 更严格。 |
| Raw-valid Rate | DONE | 检查 proposal 原始结构是否满足基础格式/规则。 |
| Checked-valid Rate | DONE | 结合应用后的 RDB 做完整结构检查，比 Raw-valid 更严格。 |
| Invalid-reference Rate | DONE | 单独定位不存在的 table/column references。 |
| Duplicate-definition Rate | DONE | 定位重复创建 table/column/constraint。 |
| Conflicting-operation Rate | DONE | 定位互相矛盾的 schema actions。 |

## 8. Final RDB State

Proposal 看起来正确不保证实际应用结果正确；需要直接评价更新后的 schema、constraints 与 tuples。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Non-target Preservation Score | DONE | 检查不应修改的数据库部分是否保持不变。 |
| Non-target Full-preservation Rate | DONE | 统计完全没有 collateral change 的 cases。 |
| Unexpected Table/Column Modification Rate | DONE | 具体量化误改范围，补充总体 preservation score。 |
| Unexpected FK Attachment Rate | DONE | 单独检查约束被挂到错误 relation。 |
| Final Schema Exact Match | TODO | 直接比较完整目标 schema，避免 proposal正确但 updater应用错误。 |
| Final Constraint Exact/F1 | TODO | 比较最终 RDB constraints，而不只比较 proposal action。 |
| Tuple Incorporation Accuracy | TODO | 检查 incoming rows 是否被正确插入、映射和保留；当前指标主要是 schema-level。 |
| Value Preservation/Transformation Accuracy | TODO | 用于未来 rename、cast、dedup或value transformation，不与 tuple coverage 混合。 |

## 9. Candidate Retrieval / Embedding

评估 Selector 是否保留足够候选；retrieval recall 高不代表最终 evolution decision 正确。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Table Hit@k | DONE | 检查 `insert/extend` 的真实 target relation 是否进入 Top-k。 |
| Table MRR | DONE | 评价真实 target 的平均排序位置，区分同样 Hit@k 下的排序质量。 |
| Column Hit@k | DONE | 检查正确 target column 是否进入候选集。 |
| Column MRR | DONE | 评价正确 column 的排序位置，而不只看是否命中。 |
| Recall–Context-size Curve | TODO | 联合展示 Top-k recall 与传给 Evolutor 的 context 成本。 |
| End-to-end Quality by Top-k | TODO | 验证更高 retrieval recall 是否真正改善 proposal，而非只增加干扰。 |
| Retrieval-conditioned Error Rate | TODO | 区分 candidate miss 与“candidate已召回但 Evolutor仍判断错误”。 |
| Create-context Evaluation | TODO | Create没有唯一 target table，需要评价关系邻居/父表证据是否被召回，不能使用普通 Table Hit@k。 |

## 10. Create/Extend Ambiguity 与 Reference Quality

数据库设计可能存在多个合理结果；strict reference accuracy 与结构合理性应分开报告。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Cross-method Decision Agreement | DERIVABLE | 多方法集中在同一 case 出错可用于发现潜在歧义，但不能直接证明 ground truth 错误。 |
| Ambiguous-case Rate | TODO | 量化 create/extend 均合理的 case 比例，判断 strict accuracy 的解释边界。 |
| Strict Reference Accuracy | DONE | 衡量是否恢复 benchmark reference schema，保持客观可复现。 |
| Ambiguity-aware Accuracy | TODO | 对人工确认的多个合理 decision/outcome进行评价，避免惩罚合理替代设计。 |
| Human Acceptability Rate | TODO | 评价非 reference proposal 是否仍是合理数据库设计，自动 exact match 无法完成。 |
| Annotation Agreement | TODO | 报告人工对 ambiguity/合理性的 Cohen's kappa 或一致率，证明 annotation可靠。 |

## 11. Robustness Slices

总体平均值可能掩盖某类 schema 或 case 的系统性失败，应按预先定义的属性切片。

| Slice/Metric | 状态 | 为什么使用 |
|---|---|---|
| Dataset | DONE | 检查结论能否跨 domain/schema style复现。 |
| Small/Medium/Large | DONE | 检查随 context规模变化的趋势。 |
| Operation Type | DERIVABLE | 区分 create、extend、insert 的不同难点。 |
| Clean vs Perturbed | TODO | 判断错误来自结构推理还是 rename/order等扰动。 |
| Perturbation Type | TODO | 分别衡量 table rename、column rename、shuffle、low-overlap。 |
| PK Width / Composite-key | TODO | 检查复合 grain 是否是主要失败来源。 |
| Relation Role | TODO | 分析 entity、association、history、weak-entity等结构类别。 |
| Schema-overlap Bucket | TODO | 衡量高字段重叠是否诱发 create→extend。 |
| Sample-row Count | TODO | 判断有限 value evidence 对 grain inference 的影响。 |

## 12. Validator 与 Revision Loop

Validator 的最终 validity 提升需要与误拒绝、无效重试和修复类型一起评价。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Retry Rate / Mean Retry Count | DERIVABLE | 衡量闭环被触发的频率和额外成本。 |
| Error Detection Precision/Recall | TODO | 检查 Validator 是否正确发现 evaluator可验证的错误，而非只看最终 valid。 |
| False-accept Rate | TODO | 统计 invalid proposal被 Validator接受的比例。 |
| False-reject Rate | TODO | 统计 valid proposal被错误退回的比例。 |
| Repair Success Rate | TODO | 衡量 retry 是否将 invalid/incorrect proposal修复。 |
| Decision Correction/Harm Rate | DERIVABLE | 分开统计 retry把错误 decision改对和把正确 decision改错。 |
| No-change Retry Rate | TODO | 发现 Evolutor重复生成同类 proposal的无效循环。 |

## 13. Efficiency

Standard 的多阶段质量收益需要与额外成本共同报告。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| End-to-end Latency | PARTIAL | 当前可从运行记录估算，但并发墙钟不能作为严格 latency benchmark。 |
| Per-stage Latency | TODO | 定位 Profiler、Selector、Evolutor、Validator 的实际成本。 |
| LLM Call Count | TODO | 比 latency 更稳定地反映 agent pipeline复杂度。 |
| Input/Output Tokens | TODO | 衡量推理成本和 context reduction收益。 |
| Peak Context Size | TODO | 检查 Selector 是否真正降低长上下文压力。 |
| Retry Cost | TODO | 单独量化 Validator闭环增加的时间与tokens。 |

## 14. Statistical Reliability

单次运行可能受 sampling 和模型随机性影响；最终论文需要不确定性与配对比较。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Mean ± Standard Deviation | PARTIAL | Aggregator支持多次运行，但当前主要结果大多只有一次。 |
| Bootstrap Confidence Interval | TODO | 为Accuracy/F1提供不确定性范围，不依赖正态假设。 |
| Paired Significance Test | TODO | 同一 cases上比较方法，区别真实改进与随机波动。 |
| Fixed-seed Reproducibility | PARTIAL | 当前 greedy配置降低随机性，但仍需记录完整环境和版本。 |

## 15. Baseline Fairness

Matching baselines 与 evolution system解决的问题不同，应同时报告其原生能力和适配后的端到端能力。

| Metric | 状态 | 为什么使用 |
|---|---|---|
| Native Correspondence Precision/Recall/F1 | TODO | 评价 COMA/JL/Magneto 原本擅长的 matching，不因 proposal adapter掩盖其能力。 |
| Adapted End-to-end Metrics | DONE | 衡量其 correspondence 经统一 adapter后能否完成 evolution任务。 |
| Adapter-induced Error Rate | TODO | 区分 baseline matcher错误与 correspondence-to-proposal规则错误。 |
| Coverage/Failure Rate | DONE | 避免只在 adapter成功输出的子集上比较。 |

## 最小论文主表建议

主表至少包含：Result Coverage、Decision Accuracy、Decision Macro-F1、Target Accuracy、Column Micro-F1、Operation-only Proposal F1、Constraint F1、Checked-valid Rate、Non-target Full-preservation 和 End-to-end Latency。

Create/extend ambiguity、embedding Top-k、Validator、robustness slices和效率分解应作为独立表或图，不应全部压入一个主表。
