// Data task excerpts: Copyright (c) 2026 DataJuicer. License: ./workflow-data-license.txt
// Bilingual presentation cases. Source IDs and reference mappings are metadata, not UI.
export const workflowCases = {
  "harness": [
    {
      "tab": [
        "Tools",
        "工具执行"
      ],
      "title": [
        "An invoice query needs the right tool.",
        "查发票总额，先选对工具。"
      ],
      "background": [
        "Finance requests customer C’s settled invoice total for 2026. There are 80,000 rows and the agent has read-only authorization.",
        "财务要查询客户 C 在 2026 年已结算发票的总额，共 80,000 行。Agent 只有只读权限。"
      ],
      "goal": [
        "Return the settled total without downloading all rows or causing writes.",
        "准确返回已结算总额，不拉取全量、不产生写入。"
      ],
      "judge": [
        "Which tool satisfies the scope, aggregation and side-effect constraints?",
        "哪个工具同时满足查询口径、聚合方式与副作用限制？"
      ],
      "policy": [
        "Over 10,000 rows requires server-side aggregation. Read-only also forbids temporary-table writes.",
        "超过 10,000 行必须服务端聚合；只读授权也禁止写入临时表。"
      ],
      "headers": [
        [
          "Tool",
          "How it works",
          "Constraint"
        ],
        [
          "工具",
          "执行方式",
          "关键限制"
        ]
      ],
      "rows": [
        [
          [
            "A",
            "Download and sum",
            "80,000 rows locally"
          ],
          [
            "B",
            "Read-only aggregate",
            "Filters customer / year / status"
          ],
          [
            "C",
            "Aggregate via temp table",
            "Writes temporary data"
          ],
          [
            "D",
            "Annual total",
            "Includes unsettled invoices"
          ]
        ],
        [
          [
            "A",
            "拉全量，本地求和",
            "80,000 行超出限制"
          ],
          [
            "B",
            "只读，服务端聚合",
            "可限定客户、年份、状态"
          ],
          [
            "C",
            "聚合，但写临时表",
            "存在写入副作用"
          ],
          [
            "D",
            "返回全年总额",
            "包含未结算发票"
          ]
        ]
      ],
      "options": [
        [
          "Tool A",
          "Tool B",
          "Tool C",
          "Tool D"
        ],
        [
          "选择 A",
          "选择 B",
          "选择 C",
          "选择 D"
        ]
      ],
      "answer": 1,
      "why": [
        "A violates the row limit, C writes data and D uses the wrong status scope. B meets all three requirements.",
        "A 违反全量拉取限制；C 写入临时表；D 包含未结算数据。B 同时满足三项要求。"
      ],
      "outcome": [
        "Route the read-only aggregate request to tool B. The executor still validates the actual arguments.",
        "将只读聚合请求路由给 B，执行前继续核对客户、年份和已结算状态。"
      ],
      "artifact": "invoice-query.json",
      "call": [
        "Choose a tool",
        "选择工具"
      ],
      "id": "tools",
      "source_id": "jev-harness-v1-b50ca5f0a62da5b5",
      "source_url": "https://github.com/agentscope-ai/HarnessJevBench",
      "state": {
        "request": {
          "customer": "C",
          "year": 2026,
          "status": "settled",
          "metric": "invoice_total"
        },
        "row_count": 80000,
        "authorization": "read_only",
        "tools": {
          "A": "download_all_then_sum",
          "B": "readonly_server_aggregate",
          "C": "aggregate_with_temp_write",
          "D": "all_status_annual_total"
        }
      },
      "source_note": [
        "Adapted from a linked HarnessJevBench case. Correct actions and subsequent states are staged for explanation, not inference results.",
        "依据关联原题改编；正确动作与后续状态为讲解编排，不代表模型实测。"
      ]
    },
    {
      "tab": [
        "Model routing",
        "模型路由"
      ],
      "title": [
        "Route a long-document task within budget.",
        "长文档抽取，选哪个模型？"
      ],
      "background": [
        "Extract clauses from a 48K-token contract and return structured JSON. The per-request budget is 4 cost units. Model capabilities and costs below are illustrative configurations.",
        "从 48K tokens 的合同材料中提取条款，并返回结构化 JSON。单次预算为 4 个计费单位；下方模型能力与费用均为示例配置。"
      ],
      "goal": [
        "Read the full contract and produce structured output within budget.",
        "完整读取合同，按要求输出结构化结果，并满足预算。"
      ],
      "judge": [
        "Which model meets the task requirements at the lowest feasible cost?",
        "哪个模型满足任务要求，且在可行候选中费用最低？"
      ],
      "policy": [
        "Require a context window of at least 48K tokens and structured JSON output; cost must be ≤ 4. Among models that meet all requirements, choose the cheapest.",
        "上下文容量至少为 48K tokens，支持结构化 JSON 输出，费用不超过 4；先筛出满足全部要求的模型，再选择费用最低者。"
      ],
      "headers": [
        [
          "Model",
          "Context / structured JSON",
          "Cost units"
        ],
        [
          "模型",
          "上下文 / 结构化 JSON",
          "费用单位"
        ]
      ],
      "rows": [
        [
          [
            "Model A",
            "16K / supported",
            "1"
          ],
          [
            "Model B",
            "64K / supported",
            "3"
          ],
          [
            "Model C",
            "128K / supported",
            "6"
          ],
          [
            "Model D",
            "64K / unsupported",
            "2"
          ]
        ],
        [
          [
            "模型 A",
            "16K / 支持",
            "1"
          ],
          [
            "模型 B",
            "64K / 支持",
            "3"
          ],
          [
            "模型 C",
            "128K / 支持",
            "6"
          ],
          [
            "模型 D",
            "64K / 不支持",
            "2"
          ]
        ]
      ],
      "options": [
        [
          "Model A",
          "Model B",
          "Model C",
          "Model D"
        ],
        [
          "选择模型 A",
          "选择模型 B",
          "选择模型 C",
          "选择模型 D"
        ]
      ],
      "answer": 1,
      "why": [
        "A cannot fit the input, C exceeds the budget and D lacks the required output capability. B fits 48K tokens, supports structured JSON and costs 3 units.",
        "A 无法容纳完整输入，C 超出预算，D 不支持所需输出格式。B 的上下文容量足够，支持结构化 JSON，费用为 3。"
      ],
      "outcome": [
        "Route this extraction task to model B. Check the returned JSON against the requested structure before using it.",
        "将本次合同抽取任务路由给模型 B，收到结果后检查 JSON 是否符合要求，再交给后续流程。"
      ],
      "artifact": "model-routing.json",
      "call": [
        "Choose a model",
        "选择模型"
      ],
      "id": "model-routing",
      "source_id": "blog-model-routing-example-v1",
      "source_url": "https://decisionplayground.agentscope.io/piccolo.html#demoharness",
      "state": {
        "task": {
          "type": "contract_clause_extraction",
          "input_tokens": 48000,
          "requires_structured_json": true
        },
        "cost_cap": 4,
        "cost_unit": "illustrative_unit_per_request",
        "selection_rule": "lowest_cost_among_models_meeting_all_requirements",
        "models": {
          "A": {
            "context_tokens": 16000,
            "structured_json": true,
            "cost": 1
          },
          "B": {
            "context_tokens": 64000,
            "structured_json": true,
            "cost": 3
          },
          "C": {
            "context_tokens": 128000,
            "structured_json": true,
            "cost": 6
          },
          "D": {
            "context_tokens": 64000,
            "structured_json": false,
            "cost": 2
          }
        }
      },
      "source_note": [
        "Illustrative model-routing scenario. Model names, capacities and cost units are hypothetical; the selected action is staged for explanation, not a measured model result.",
        "模型路由示意案例。模型名、容量及计费单位均为假设配置；选择结果为讲解编排，不代表真实模型规格、价格或实测结果。"
      ]
    },
    {
      "tab": [
        "Context",
        "上下文管理"
      ],
      "title": [
        "A shorter summary must retain rollback evidence.",
        "压缩轨迹，不能丢掉回滚线索。"
      ],
      "background": [
        "Copying created tmp-31. The copy step says done, but validation failed and rollback is pending. A proposed summary only says “Copy complete.”",
        "复制创建了临时资源 tmp-31。复制步骤虽已 done，但后续校验失败，回滚尚未执行。候选摘要仅写“复制完成”。"
      ],
      "goal": [
        "Reduce context while preserving everything needed for the pending rollback.",
        "减少上下文，同时保留执行回滚所需的证据。"
      ],
      "judge": [
        "Can this summary safely replace the original execution trace?",
        "这份摘要能否替换原轨迹，让后续回滚仍可执行？"
      ],
      "policy": [
        "Keep resource_id until compensation completes. A done copy step is not a completed rollback.",
        "补偿事务完成前必须保留 resource_id；复制 done 不代表回滚已完成。"
      ],
      "headers": [
        [
          "Evidence",
          "Current value",
          "Why it matters"
        ],
        [
          "证据",
          "当前值",
          "用途"
        ]
      ],
      "rows": [
        [
          [
            "Copy",
            "done",
            "Forward step complete"
          ],
          [
            "Temporary resource",
            "tmp-31",
            "Rollback target"
          ],
          [
            "Validation",
            "failed",
            "Rollback required"
          ],
          [
            "Proposed summary",
            "Copy complete",
            "Omits target ID"
          ]
        ],
        [
          [
            "复制步骤",
            "done",
            "只表示正向步骤完成"
          ],
          [
            "临时资源",
            "tmp-31",
            "待回滚的目标"
          ],
          [
            "后续校验",
            "failed",
            "需要补偿"
          ],
          [
            "候选摘要",
            "复制完成",
            "遗漏目标标识"
          ]
        ]
      ],
      "options": [
        [
          "Reject; retain resource ID",
          "Accept and roll back",
          "Treat done as rollback complete"
        ],
        [
          "拒绝替换，保留资源标识",
          "采用摘要，继续回滚",
          "把 done 当作回滚完成"
        ]
      ],
      "answer": 0,
      "why": [
        "The summary drops tmp-31 while rollback still needs it. Without the ID, the executor cannot identify the resource to delete.",
        "回滚仍需要 tmp-31，而摘要丢掉了它。执行器无法仅凭“复制完成”确定待删除的资源。"
      ],
      "outcome": [
        "Keep the original evidence or rewrite the summary to include tmp-31 and pending rollback.",
        "保留原证据，或要求摘要补上 tmp-31 与待回滚状态。"
      ],
      "artifact": "context-summary.txt",
      "call": [
        "Review a summary",
        "审查摘要"
      ],
      "id": "context",
      "source_id": "jev-harness-v1-d0e07fe4d0cbdd4c",
      "source_url": "https://github.com/agentscope-ai/HarnessJevBench",
      "state": {
        "copy_step": {
          "status": "done",
          "resource_id": "tmp-31"
        },
        "validation": "failed",
        "rollback": {
          "action": "delete_resource",
          "status": "pending",
          "target": "tmp-31"
        },
        "proposed_summary": "复制完成"
      },
      "source_note": [
        "Adapted from a linked HarnessJevBench case. Correct actions and subsequent states are staged for explanation, not inference results.",
        "依据关联原题改编；正确动作与后续状态为讲解编排，不代表模型实测。"
      ]
    },
    {
      "tab": [
        "Permission",
        "权限边界"
      ],
      "title": [
        "Similar paths do not share authorization.",
        "目录名相似，不等于获得授权。"
      ],
      "background": [
        "Agent7 wants to read tenant/team700/report.json. Its allow rule covers tenant/team70/* and is active at the current time.",
        "agent7 要读取 tenant/team700/report.json。有效期内的授权仅覆盖 tenant/team70/*。"
      ],
      "goal": [
        "Allow reads only inside the explicitly authorized directory.",
        "只允许读取明确授权范围内的资源。"
      ],
      "judge": [
        "Does the proposed read fall within the actual authorization scope?",
        "拟议读取的资源，是否真正落在授权范围内？"
      ],
      "policy": [
        "Match directory descendants, principal, action and time. Do not replace path matching with string-prefix matching.",
        "核对目录后代、主体、动作和有效期，不能用字符串前缀代替目录匹配。"
      ],
      "headers": [
        [
          "Field",
          "Authorized / observed",
          "Match?"
        ],
        [
          "字段",
          "授权 / 实际请求",
          "是否匹配"
        ]
      ],
      "rows": [
        [
          [
            "Principal",
            "agent7 / agent7",
            "Yes"
          ],
          [
            "Action",
            "read / read",
            "Yes"
          ],
          [
            "Time",
            "20 ≤ 45 < 80",
            "Yes"
          ],
          [
            "Path",
            "team70/* / team700/report.json",
            "No"
          ]
        ],
        [
          [
            "主体",
            "agent7 / agent7",
            "匹配"
          ],
          [
            "动作",
            "read / read",
            "匹配"
          ],
          [
            "时间",
            "20 ≤ 45 < 80",
            "匹配"
          ],
          [
            "路径",
            "team70/* / team700/report.json",
            "不匹配"
          ]
        ]
      ],
      "options": [
        [
          "Deny: outside scope",
          "Allow: same prefix",
          "Allow: read-only needs no grant"
        ],
        [
          "拒绝，目标未获授权",
          "放行，路径前缀相同",
          "放行，只读无需授权"
        ]
      ],
      "answer": 0,
      "why": [
        "team700 is a different directory from team70. The shared text prefix cannot expand the authorization.",
        "team700 与 team70 是不同目录，共同前缀不能扩大权限。只读也必须有对应授权。"
      ],
      "outcome": [
        "Block the read before invoking the tool; request a grant for the actual resource if needed.",
        "在工具调用前阻止读取；确需访问时，申请实际资源范围的授权。"
      ],
      "artifact": "authorization-snapshot.json",
      "call": [
        "Review access",
        "判断访问权限"
      ],
      "id": "permission",
      "source_id": "hjdiag20-authorization-000",
      "source_url": "https://github.com/agentscope-ai/HarnessJevBench",
      "state": {
        "principal": "agent7",
        "action": "read",
        "resource": "tenant/team700/report.json",
        "now": 45,
        "rules": [
          {
            "effect": "allow",
            "principal": "agent7",
            "action": "read",
            "resource": "tenant/team70/*",
            "start": 20,
            "end": 80
          }
        ]
      },
      "source_note": [
        "Adapted from a linked HarnessJevBench case. Correct actions and subsequent states are staged for explanation, not inference results.",
        "依据关联原题改编；正确动作与后续状态为讲解编排，不代表模型实测。"
      ]
    },
    {
      "tab": [
        "Completion",
        "完成验收"
      ],
      "title": [
        "An agent’s “done” is not a completion receipt.",
        "Agent 说完成了，任务就能结束吗？"
      ],
      "background": [
        "The agent reports success. The contract requires lint, unit and permission receipts for r4 / target; permission is still pending.",
        "Agent 已回复“全部通过”。契约要求 r4 / target 下 lint、unit、permission 三项回执，但 permission 仍为 pending。"
      ],
      "goal": [
        "End only after all required checks have valid, current receipts.",
        "只有必需检查均有当前版本的有效回执，才能结束任务。"
      ],
      "judge": [
        "Do the available receipts actually establish completion?",
        "现有执行回执是否足以证明任务已完成？"
      ],
      "policy": [
        "Only non-invalidated pass receipts for r4 / target count. Self-reports and older revisions do not.",
        "只认 r4 / target 且未失效的 pass 回执；自述与旧版结果不能补足缺口。"
      ],
      "headers": [
        [
          "Receipt",
          "Revision / scope",
          "Status"
        ],
        [
          "回执",
          "版本 / 范围",
          "状态"
        ]
      ],
      "rows": [
        [
          [
            "lint",
            "r4 / target",
            "pass"
          ],
          [
            "unit",
            "r4 / target",
            "pass"
          ],
          [
            "permission",
            "r4 / target",
            "pending"
          ],
          [
            "agent_claim",
            "r4 / target",
            "pass (not a receipt)"
          ],
          [
            "lint",
            "r2 / target",
            "pass (stale)"
          ]
        ],
        [
          [
            "lint",
            "r4 / target",
            "pass"
          ],
          [
            "unit",
            "r4 / target",
            "pass"
          ],
          [
            "permission",
            "r4 / target",
            "pending"
          ],
          [
            "agent_claim",
            "r4 / target",
            "自述，不计入回执"
          ],
          [
            "lint",
            "r2 / target",
            "旧版 pass，不计入"
          ]
        ]
      ],
      "options": [
        [
          "Not complete; wait for permission",
          "Complete; the agent said so",
          "Complete; enough pass rows"
        ],
        [
          "不能结束，permission 未通过",
          "可以结束，Agent 已确认",
          "可以结束，pass 条数已足够"
        ]
      ],
      "answer": 0,
      "why": [
        "Two required current checks pass; permission does not. Extra self-reports or stale receipts cannot satisfy it.",
        "lint 与 unit 的当前回执有效，但 permission 仍未通过。旧版回执和自述不能替代这一项。"
      ],
      "outcome": [
        "Keep the task open and obtain the current permission result.",
        "保持任务未完成，继续取得当前版本的 permission 验证结果。"
      ],
      "artifact": "completion-receipts.json",
      "call": [
        "Check completion",
        "判断是否完成"
      ],
      "id": "verify",
      "source_id": "jev-harness-v1-021c38e705bdeca2",
      "source_url": "https://github.com/agentscope-ai/HarnessJevBench",
      "state": {
        "assistant_last_message": "Finished; everything passed.",
        "completion_contract": {
          "required_receipts": [
            "lint",
            "unit",
            "permission"
          ],
          "revision": "r4",
          "scope": "target"
        },
        "receipts": [
          {
            "name": "lint",
            "revision": "r4",
            "scope": "target",
            "status": "pass"
          },
          {
            "name": "unit",
            "revision": "r4",
            "scope": "target",
            "status": "pass"
          },
          {
            "name": "permission",
            "revision": "r4",
            "scope": "target",
            "status": "pending"
          },
          {
            "name": "agent_claim",
            "revision": "r4",
            "scope": "target",
            "status": "pass"
          },
          {
            "name": "lint",
            "revision": "r2",
            "scope": "target",
            "status": "pass"
          }
        ]
      },
      "source_note": [
        "Adapted from a linked HarnessJevBench case. Correct actions and subsequent states are staged for explanation, not inference results.",
        "依据关联原题改编；正确动作与后续状态为讲解编排，不代表模型实测。"
      ]
    },
    {
      "tab": [
        "Recovery",
        "失败恢复"
      ],
      "title": [
        "Resume from server evidence, not local optimism.",
        "断点续传，要以服务端确认为准。"
      ],
      "background": [
        "An upload failed. Local cache marks parts 1–5 complete, but the server confirms only 1–4. Part 5 is unknown; the agent proposes resuming at 6.",
        "上传中断。本地缓存标记分片 1–5 成功，服务端仅确认 1–4，第 5 片 unknown。Agent 拟从第 6 片继续。"
      ],
      "goal": [
        "Resume the same upload without skipping an unconfirmed part.",
        "恢复同一上传任务，不跳过未经确认的分片。"
      ],
      "judge": [
        "Can the agent safely skip part 5, or must it query the server first?",
        "现在能否跳过第 5 片，还是应该先查询服务端？"
      ],
      "policy": [
        "Bind recovery to file hash H1 and session U9. Unknown is not complete.",
        "恢复必须绑定文件哈希 H1 与会话 U9；unknown 不能视作完成。"
      ],
      "headers": [
        [
          "Evidence",
          "Value",
          "Meaning"
        ],
        [
          "证据",
          "值",
          "含义"
        ]
      ],
      "rows": [
        [
          [
            "File / session",
            "H1 / U9",
            "Same upload"
          ],
          [
            "Local complete",
            "1, 2, 3, 4, 5",
            "Local cache only"
          ],
          [
            "Server confirmed",
            "1, 2, 3, 4",
            "Persisted parts"
          ],
          [
            "Part 5",
            "unknown",
            "Needs confirmation"
          ]
        ],
        [
          [
            "文件 / 会话",
            "H1 / U9",
            "同一上传任务"
          ],
          [
            "本地成功",
            "1, 2, 3, 4, 5",
            "仅本地缓存"
          ],
          [
            "服务端确认",
            "1, 2, 3, 4",
            "已有持久化证据"
          ],
          [
            "第 5 片",
            "unknown",
            "仍需确认"
          ]
        ]
      ],
      "options": [
        [
          "Query part 5 on the server",
          "Resume at part 6",
          "Trust local completion"
        ],
        [
          "先查服务端第 5 片状态",
          "直接从第 6 片继续",
          "以本地成功标记为准"
        ]
      ],
      "answer": 0,
      "why": [
        "Skipping part 5 would leave an unverified gap. Query it in the same session before deciding whether to retransmit.",
        "直接跳过第 5 片会留下未确认缺口。应在同一上传会话中查询，再决定是否补传。"
      ],
      "outcome": [
        "Query server status for part 5; retransmit only if confirmed missing.",
        "查询第 5 片服务端状态，确认缺失后再补传。"
      ],
      "artifact": "upload-checkpoint.json",
      "call": [
        "Choose a recovery action",
        "选择恢复动作"
      ],
      "id": "recovery",
      "source_id": "jev-harness-v1-bee4d6d3fdd7d7b7",
      "source_url": "https://github.com/agentscope-ai/HarnessJevBench",
      "state": {
        "current_file_hash": "H1",
        "upload_session": "U9",
        "local_completed_parts": [
          1,
          2,
          3,
          4,
          5
        ],
        "server": {
          "file_hash": "H1",
          "confirmed_parts": [
            1,
            2,
            3,
            4
          ],
          "part_5": "unknown"
        },
        "proposed_resume_from": 6
      },
      "source_note": [
        "Adapted from a linked HarnessJevBench case. Correct actions and subsequent states are staged for explanation, not inference results.",
        "依据关联原题改编；正确动作与后续状态为讲解编排，不代表模型实测。"
      ]
    }
  ],
  "data": [
    {
      "tab": [
        "Admission",
        "数据准入"
      ],
      "title": [
        "Enough text, but the longest line fails the rule.",
        "字符总数达标，记录就能入库吗？"
      ],
      "background": [
        "Warehouse export records contain HTML. After normalization, the segment has 101 characters and a longest line of 50. The admission gate runs before line deduplication.",
        "仓储导出记录带有 HTML 标签。规范化后，片段共有 101 个字符，最长一行为 50 个字符。入库检查须在规范化之后、行去重之前执行。"
      ],
      "goal": [
        "Admit this segment only if both length conditions hold at the required stage.",
        "在指定处理阶段，同时满足总长度与最长行限制，才允许入库。"
      ],
      "judge": [
        "Should this segment be kept or dropped under the admission rules?",
        "按指定阶段的准入规则，这条记录应该保留还是丢弃？"
      ],
      "policy": [
        "Check after normalization, before deduplication: total characters ≥ 100 AND longest line ≤ 49. Do not filter again after deduplication. Characters are Unicode code points.",
        "只在规范化后、行去重前检查：字符数至少 100，且最长行不超过 49 个字符。去重后不重新过滤；字符按 Unicode 码点统计。"
      ],
      "headers": [
        [
          "Stage",
          "Characters",
          "Longest line"
        ],
        [
          "处理阶段",
          "字符数",
          "最长行"
        ]
      ],
      "rows": [
        [
          [
            "Raw export",
            "150",
            "57"
          ],
          [
            "After normalization",
            "101",
            "50"
          ],
          [
            "After line deduplication",
            "101",
            "50"
          ]
        ],
        [
          [
            "原始导出",
            "150",
            "57"
          ],
          [
            "规范化后",
            "101",
            "50"
          ],
          [
            "行去重后",
            "101",
            "50"
          ]
        ]
      ],
      "options": [
        [
          "Keep the segment",
          "Drop the segment"
        ],
        [
          "保留记录",
          "丢弃记录"
        ]
      ],
      "answer": 1,
      "why": [
        "At the required stage, 101 ≥ 100 passes the total-length gate, but 50 > 49 fails the longest-line gate. Both are required, so the decision is DROP.",
        "在规定检查阶段，101 ≥ 100 满足总长度要求，但 50 > 49 违反最长行限制。两项必须同时满足，因此应丢弃。"
      ],
      "outcome": [
        "Exclude the segment from this ingest batch and record the longest-line violation.",
        "本次不将该片段入库，并记录“最长行超限”的原因。"
      ],
      "artifact": "warehouse-ingest-stats.json",
      "call": [
        "Decide admission",
        "判断是否入库"
      ],
      "id": "d1",
      "source_id": "D1-93ec53a23b7e14ff",
      "source_url": "https://github.com/datajuicer/DataJevBench/blob/5010f6aa899dd268aae8b0b9dbc4665e02999443/benchmark/records.jsonl",
      "source_note": [
        "Presentation adapted from a benchmark task; the selected action maps to its published reference label.",
        "依据原题改编展示；所选动作映射到原题参考标签。"
      ],
      "state": "用途：为检索/训练语料导入作保留决定。评测对象是下面给出的完整片段，不能据此推断来源全文；其他合同条件均已满足。\n处理阶段：原始→规范化（HTML实体反解码、Unicode NFKC、删除<…>标签、每行空白折叠为单空格、丢弃空行）→按完全相同的行去重保留首次。两阶段之间以单个换行连接各行。这里只采用明确给出的任务局部处理定义。\n统计由程序对本片段逐阶段计算，供直接使用，无需手工数长文本。chars=Unicode码点数（包含换行），alnum=Unicode字母或数字码点数，words=按空白split的段数，max_line=不含换行的最长行字符数，nonblank_lines=非空行数。\n处理统计（非最终判断）：{\"原始\": {\"chars\": 150, \"alnum\": 103, \"words\": 21, \"lines\": 5, \"max_line\": 57, \"nonblank_lines\": 3}, \"规范化后\": {\"chars\": 101, \"alnum\": 78, \"words\": 16, \"lines\": 2, \"max_line\": 50, \"nonblank_lines\": 2}, \"行去重后\": {\"chars\": 101, \"alnum\": 78, \"words\": 16, \"lines\": 2, \"max_line\": 50, \"nonblank_lines\": 2}}\n准入规则：只在规范化之后、行去重之前过滤：字符数至少100且最长行不超过49字符才保留；之后的去重结果不重新过滤。\n明确合成的导出记录：\n<p>warehouse inventory: record 26, field 1, value 56.</p>\n\n<p>warehouse inventory: record 26, field 2, value 84.</p>\n\n<!-- generated export footer -->\n问题：该片段最终应保留还是丢弃？",
      "option_ids": [
        "KEEP",
        "DROP"
      ],
      "benchmark_reference": {
        "revision": "5010f6aa899dd268aae8b0b9dbc4665e02999443",
        "task_id": "D1-93ec53a23b7e14ff",
        "expected": "DROP",
        "option_ids": [
          "KEEP",
          "DROP"
        ],
        "record_sha256": "512d6f99b25b2ef2d9be3705f7d017f4c0822210323d9e76a35b8bed3c7c19ab",
        "presentation_changes": "Bilingual paraphrase and evidence condensation; option selection is a subset only for the operator-catalog case. Outcome and explanation are presentation text, not additional reference labels."
      }
    },
    {
      "tab": [
        "Processing",
        "清洗方案"
      ],
      "title": [
        "Repeated error tokens need a character-level filter.",
        "错误词反复出现，该选哪个过滤器？"
      ],
      "background": [
        "A pretraining corpus already passed HTML and link removal. One sample is normal financial prose; another repeats ERROR ten times before “connection timeout”.",
        "预训练语料已经去过 HTML 和链接。一条样本是正常财务描述，另一条将 ERROR 重复十次，随后写着 connection timeout。"
      ],
      "goal": [
        "Filter excessive per-document character n-gram repetition while keeping natural text usable and caching the ratio for audit.",
        "按文档过滤过量的字符 n-gram 重复，保留自然文本，并将重复率写入 stats 供审计。"
      ],
      "judge": [
        "Which single next operator matches the required repetition unit and filtering behavior?",
        "下一步哪个算子同时满足“字符级重复检测、按文档过滤、缓存统计”的要求？"
      ],
      "policy": [
        "Use character n-grams, not word n-grams. Compute the ratio per document and cache it in stats. The requested operation is filtering, not rewriting sentences.",
        "必须使用字符 n-gram，而非词 n-gram；逐文档计算重复率并缓存到 stats。任务要求过滤样本，不是改写或删除句子。"
      ],
      "headers": [
        [
          "Sample",
          "Input text",
          "Current state"
        ],
        [
          "样本",
          "输入文本",
          "当前状态"
        ]
      ],
      "rows": [
        [
          [
            "Financial prose",
            "The quarterly revenue report shows steady growth across all departments and regions.",
            "HTML and links already removed"
          ],
          [
            "Error log",
            "ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR connection timeout",
            "HTML and links already removed"
          ]
        ],
        [
          [
            "财务描述",
            "The quarterly revenue report shows steady growth across all departments and regions.",
            "已去 HTML 和链接"
          ],
          [
            "错误日志",
            "ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR connection timeout",
            "已去 HTML 和链接"
          ]
        ]
      ],
      "options": [
        [
          "Word n-gram repetition filter",
          "Repeated-sentence removal",
          "Character n-gram repetition filter",
          "HTML cleanup"
        ],
        [
          "词级重复率过滤器",
          "重复句删除算子",
          "字符级重复率过滤器",
          "HTML 清理算子"
        ]
      ],
      "answer": 2,
      "why": [
        "character_repetition_filter measures character-level n-gram repetition per sample and applies ratio bounds. A word-based filter uses the wrong unit; sentence removal rewrites text; HTML cleanup addresses an already-completed step.",
        "character_repetition_filter 按样本计算字符 n-gram 重复率，并依据阈值过滤。词级过滤单位不符；重复句删除会改写文本；HTML 清理已完成。"
      ],
      "outcome": [
        "Route the corpus to character_repetition_filter. Configure its threshold and execute the filter separately; this demo does not claim measured removal counts.",
        "将语料路由到字符级重复率过滤器，再由执行器配置阈值并运行；此处只展示算子选择。"
      ],
      "artifact": "corpus-repetition-review.json",
      "call": [
        "Choose the next operator",
        "选择下一处理算子"
      ],
      "id": "d2",
      "source_id": "D2-4872f8aa48327928",
      "source_url": "https://github.com/datajuicer/DataJevBench/blob/5010f6aa899dd268aae8b0b9dbc4665e02999443/benchmark/records.jsonl",
      "source_note": [
        "Presentation adapted from a benchmark task; the selected action maps to its published reference label.",
        "依据原题改编展示；所选动作映射到原题参考标签。"
      ],
      "state": "用途：为下游数据使用选择当前应执行的处理节点。\n以下是完整的合成记录或文件元数据，用于模拟生产数据处理。\n输入数据：\n[{\"text\": \"The quarterly revenue report shows steady growth across all departments and regions.\", \"meta\": {\"source\": \"finance_docs\", \"cleaned\": true}}, {\"text\": \"ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR connection timeout\", \"meta\": {\"source\": \"server_logs\", \"cleaned\": true}}]\n数据验收要求与当前状态：\nYou are given a small text corpus already processed by upstream HTML stripping and link removal. The corpus is intended for pretraining, and the downstream acceptance contract requires: (1) no sample may contain excessive character-level n-gram repetition, because such samples indicate stuck loops or repeated error tokens; (2) naturally written financial text must remain usable; (3) the repetition ratio must be computed per document and cached in the stats field for auditing; (4) filtering must be based on character n-grams rather than word n-grams so that partial token repetitions are caught. Inspect the provided data and current processing state. Select exactly one next operator from the catalog that moves the corpus toward satisfying the acceptance contract. Return only the operator ID.\n根据实际输入和未满足的验收要求，从固定算子表选择唯一适合的下一节点。",
      "option_ids": [
        "word_repetition_filter",
        "remove_repeat_sentences_mapper",
        "character_repetition_filter",
        "clean_html_mapper"
      ],
      "benchmark_reference": {
        "revision": "5010f6aa899dd268aae8b0b9dbc4665e02999443",
        "task_id": "D2-4872f8aa48327928",
        "expected": "character_repetition_filter",
        "option_ids": [
          "word_repetition_filter",
          "remove_repeat_sentences_mapper",
          "character_repetition_filter",
          "clean_html_mapper"
        ],
        "record_sha256": "3dccc56bbce34361ca3a359cb211609597e6953ebedd0f4b805fe179085daa7a",
        "presentation_changes": "Bilingual paraphrase and evidence condensation; option selection is a subset only for the operator-catalog case. Outcome and explanation are presentation text, not additional reference labels."
      }
    },
    {
      "tab": [
        "Quality",
        "产物评审"
      ],
      "title": [
        "Which hotel description reads naturally?",
        "两句酒店说明，哪句表达更通顺？"
      ],
      "background": [
        "A data product generates English hotel descriptions from structured attributes. Compare two actual candidates using only the language-usability rubric.",
        "数据产品需要把酒店结构化属性转成英文说明。对照两个候选，只按“语言可用性”这一维度判断。"
      ],
      "goal": [
        "Select the more fluent, grammatical and natural English description.",
        "选出表达更通顺、语法更完整、措辞更自然的英文说明。"
      ],
      "judge": [
        "Under the language-usability rubric, is candidate A or B better?",
        "仅依据语言通顺与语法这一标准，应选候选 A 还是 B？"
      ],
      "policy": [
        "Judge fluency, grammar and natural wording. Do not mix factual coverage into this single rubric. Candidate sentences remain in their original English in both editions.",
        "只评价通顺、语法与措辞自然程度，不将事实覆盖混入这一维度。两句英文保留原文，以免翻译消除语法差异。"
      ],
      "headers": [
        [
          "Material",
          "Content"
        ],
        [
          "材料",
          "内容"
        ]
      ],
      "rows": [
        [
          [
            "Structured attributes",
            "name='hotel north beach'; has_internet='yes'; area='chinatown'"
          ],
          [
            "Candidate A",
            "hotel north beach is near chinatown has internet."
          ],
          [
            "Candidate B",
            "hotel north beach in the chinatown area has internet."
          ]
        ],
        [
          [
            "结构化属性",
            "name='hotel north beach'; has_internet='yes'; area='chinatown'"
          ],
          [
            "候选 A",
            "hotel north beach is near chinatown has internet."
          ],
          [
            "候选 B",
            "hotel north beach in the chinatown area has internet."
          ]
        ]
      ],
      "options": [
        [
          "Candidate A",
          "Candidate B"
        ],
        [
          "选择候选 A",
          "选择候选 B"
        ]
      ],
      "answer": 1,
      "why": [
        "B has a coherent subject and predicate. A joins “is near chinatown” and “has internet” without a conjunction.",
        "B 的主语、修饰语和谓语衔接完整；A 将 is near chinatown 与 has internet 直接拼接，缺少连接。按这一语言标准，应选择 B。"
      ],
      "outcome": [
        "Select B as the description under this language-usability rubric.",
        "按语言可用性这一标准，采用候选 B 作为说明。"
      ],
      "artifact": "hotel-description-review.json",
      "call": [
        "Compare description quality",
        "比较说明质量"
      ],
      "id": "d3",
      "source_id": "D3-ab5b79062176e667",
      "source_url": "https://github.com/datajuicer/DataJevBench/blob/5010f6aa899dd268aae8b0b9dbc4665e02999443/benchmark/records.jsonl",
      "source_note": [
        "Presentation adapted from a benchmark task; the selected action maps to its published reference label.",
        "依据原题改编展示；所选动作映射到原题参考标签。"
      ],
      "state": "任务：为数据产品选择质量更好的候选描述/摘要。依据下面指定的单一rubric比较A与B；参照为公开数据集的人工评价偏好，存在人类主观性，不要求写解释。\nRubric：语言可用性：作为结构化数据的自然语言说明，表达是否通顺、语法是否正确、措辞是否自然；不将事实覆盖程度混入本维度。\n源数据/原文：\ninform(name='hotel north beach',has_internet='yes',area='chinatown')\n\n候选A：\nhotel north beach is near chinatown has internet.\n\n候选B：\nhotel north beach in the chinatown area has internet.",
      "option_ids": [
        "A",
        "B"
      ],
      "benchmark_reference": {
        "revision": "5010f6aa899dd268aae8b0b9dbc4665e02999443",
        "task_id": "D3-ab5b79062176e667",
        "expected": "B",
        "option_ids": [
          "A",
          "B"
        ],
        "record_sha256": "a0b1a19c517f51b621dcf0d7bbb1c8635e4d584fe3dbf2a896da16501cb74910",
        "presentation_changes": "Bilingual paraphrase and evidence condensation; option selection is a subset only for the operator-catalog case. Outcome and explanation are presentation text, not additional reference labels."
      }
    },
    {
      "tab": [
        "Readiness",
        "分析就绪"
      ],
      "title": [
        "A five-year return question is missing its final year.",
        "要回答 2018 年收益问题，材料却止于 2017 年。"
      ],
      "background": [
        "An analyst asks for the difference between PMI stock and S&P 500 percentage returns over the five years ended 2018. The supplied performance table starts in 2013 and stops in 2017.",
        "分析师要比较截至 2018 年的五年间，PMI 股票与 S&P 500 指数的收益率差。当前财报抽取表从 2013 年开始，但最后一行只有 2017 年。"
      ],
      "goal": [
        "Decide whether the supplied material determines the requested answer; do not calculate a different time period.",
        "判断当前材料能否确定目标答案，不用其他时间段的结果替代。"
      ],
      "judge": [
        "Is the visible financial evidence sufficient to answer the 2018 question?",
        "当前可见材料，是否足以回答截至 2018 年的目标问题？"
      ],
      "policy": [
        "Use only the supplied extract, ordinary arithmetic and explicit unit conversions. No external lookup or assumptions about undisclosed values.",
        "只使用当前抽取材料，可做常规算术和明确的单位换算；不可外查或假设未披露数值。"
      ],
      "headers": [
        [
          "Year-end",
          "PMI investment value",
          "S&P 500 value"
        ],
        [
          "年末",
          "PMI 投资组合值",
          "S&P 500 组合值"
        ]
      ],
      "rows": [
        [
          [
            "2013",
            "$100.00",
            "$100.00"
          ],
          [
            "2014",
            "$97.90",
            "$113.70"
          ],
          [
            "2015",
            "$111.00",
            "$115.30"
          ],
          [
            "2016",
            "$120.50",
            "$129.00"
          ],
          [
            "2017",
            "$144.50",
            "$157.20"
          ]
        ],
        [
          [
            "2013",
            "$100.00",
            "$100.00"
          ],
          [
            "2014",
            "$97.90",
            "$113.70"
          ],
          [
            "2015",
            "$111.00",
            "$115.30"
          ],
          [
            "2016",
            "$120.50",
            "$129.00"
          ],
          [
            "2017",
            "$144.50",
            "$157.20"
          ]
        ]
      ],
      "options": [
        [
          "Sufficient information",
          "Insufficient information"
        ],
        [
          "信息足够",
          "信息不足"
        ]
      ],
      "answer": 1,
      "why": [
        "The target period ends in 2018, but neither 2018 endpoint is supplied. Values for 2017 cannot determine the requested five-year return difference.",
        "目标时间段截至 2018 年，但两项 2018 年末数值均未提供。2017 年的数据不能确定所问的五年收益率差。"
      ],
      "outcome": [
        "Request the missing 2018 values or the complete performance table before answering.",
        "请求补充 2018 年末数值或完整收益表，再继续回答。"
      ],
      "artifact": "annual-report-performance.csv",
      "call": [
        "Check information sufficiency",
        "判断材料是否充分"
      ],
      "id": "d4",
      "source_id": "D4-26bba3bf92dd404d",
      "source_url": "https://github.com/datajuicer/DataJevBench/blob/5010f6aa899dd268aae8b0b9dbc4665e02999443/benchmark/records.jsonl",
      "source_note": [
        "Presentation adapted from a benchmark task; the selected action maps to its published reference label.",
        "依据原题改编展示；所选动作映射到原题参考标签。"
      ],
      "state": "任务：将财报中的一个目标指标提取到分析工作表。只依据当前抽取材料判断是否有足够信息给出该问题的确定答案；允许常规算术与明确的单位换算，不允许外部查询或假设未披露数据。选项只判断信息充分性，不要求输出指标值。\n目标问题：what was the difference in percentage return for pmi common stock compared to the s&p 500 index for the five years ended 2018?\n\n当前可见财报抽取材料：\nperformance graph the graph below compares the cumulative total shareholder return on pmi's common stock with the cumulative total return for the same period of pmi's peer group and the s&p 500 index .\nthe graph assumes the investment of $ 100 as of december 31 , 2013 , in pmi common stock ( at prices quoted on the new york stock exchange ) and each of the indices as of the market close and reinvestment of dividends on a quarterly basis .\ndate pmi pmi peer group ( 1 ) s&p 500 index .\n\ndate | pmi | pmi peer group ( 1 ) | s&p 500 index\ndecember 31 2013 | $ 100.00 | $ 100.00 | $ 100.00\ndecember 31 2014 | $ 97.90 | $ 107.80 | $ 113.70\ndecember 31 2015 | $ 111.00 | $ 116.80 | $ 115.30\ndecember 31 2016 | $ 120.50 | $ 118.40 | $ 129.00\ndecember 31 2017 | $ 144.50 | $ 140.50 | $ 157.20\n\n( 1 ) the pmi peer group presented in this graph is the same as that used in the prior year .\nthe pmi peer group was established based on a review of four characteristics : global presence ; a focus on consumer products ; and net revenues and a market capitalization of a similar size to those of pmi .\nthe review also considered the primary international tobacco companies .\nas a result of this review , the following companies constitute the pmi peer group : altria group , inc. , anheuser-busch inbev sa/nv , british american tobacco p.l.c. , the coca-cola company , colgate-palmolive co. , diageo plc , heineken n.v. , imperial brands plc , japan tobacco inc. , johnson & johnson , kimberly-clark corporation , the kraft-heinz company , mcdonald's corp. , mondel z international , inc. , nestl e9 s.a. , pepsico , inc. , the procter & gamble company , roche holding ag , and unilever nv and plc .\nnote : figures are rounded to the nearest $ 0.10. .",
      "option_ids": [
        "SUFFICIENT",
        "INSUFFICIENT"
      ],
      "benchmark_reference": {
        "revision": "5010f6aa899dd268aae8b0b9dbc4665e02999443",
        "task_id": "D4-26bba3bf92dd404d",
        "expected": "INSUFFICIENT",
        "option_ids": [
          "SUFFICIENT",
          "INSUFFICIENT"
        ],
        "record_sha256": "734b5c96c31fa811e8072baaeed23b8f02d859a14fdad513f5079e13433106a3",
        "presentation_changes": "Bilingual paraphrase and evidence condensation; option selection is a subset only for the operator-catalog case. Outcome and explanation are presentation text, not additional reference labels."
      }
    },
    {
      "tab": [
        "Disclosure",
        "披露审查"
      ],
      "title": [
        "Fourteen records do not establish three distinct people.",
        "14 条记录，能证明至少有 3 人吗？"
      ],
      "background": [
        "A synthetic group report is being reviewed for publication. Group demo-ward-A has 14 records, but the number of distinct participants is unknown.",
        "审核一份合成分组报告的发布方案。demo-ward-A 共有 14 条记录，但独立参与者人数没有提供。"
      ],
      "goal": [
        "Assess publication under the stated minimum-group-size rule.",
        "依据给定的最小分组人数规则，判断当前发布方案。"
      ],
      "judge": [
        "Does the evidence establish a privacy violation, no violation, or a need for review?",
        "现有证据应判为存在风险、未发现风险，还是需要补充核验？"
      ],
      "policy": [
        "Every published group must contain at least 3 distinct participants. Record count cannot replace participant count. Unknown values must be verified.",
        "每个发布组至少包含 3 名不同参与者；记录条数不能替代人数；未知值必须核实。"
      ],
      "headers": [
        [
          "Field",
          "Observed value",
          "Rule"
        ],
        [
          "字段",
          "当前值",
          "对应规则"
        ]
      ],
      "rows": [
        [
          [
            "Group",
            "demo-ward-A",
            "Complete group scope"
          ],
          [
            "Records",
            "14",
            "Records are not people"
          ],
          [
            "Distinct participants",
            "unknown / null",
            "At least 3 required"
          ]
        ],
        [
          [
            "分组",
            "demo-ward-A",
            "完整分组范围"
          ],
          [
            "记录数",
            "14",
            "记录数不能替代人数"
          ],
          [
            "独立参与者人数",
            "未知 / null",
            "至少 3 人"
          ]
        ]
      ],
      "options": [
        [
          "Confirmed privacy risk",
          "No risk under these rules",
          "Insufficient evidence: review"
        ],
        [
          "已确认存在隐私风险",
          "按当前规则未发现风险",
          "证据不足，需要核验"
        ]
      ],
      "answer": 2,
      "why": [
        "Fourteen records may come from fewer than three people. Because distinct_participants is unknown, the evidence establishes neither compliance nor a confirmed violation. The reference action is REVIEW.",
        "14 条记录可能来自少于 3 人。独立参与者人数未知，既不能确认达标，也不能直接确认违规，因此应补充核验。"
      ],
      "outcome": [
        "Pause release and verify the deduplicated participant count, then reassess the group under the same rule.",
        "先暂停发布并核实去重后的参与者人数，再按同一规则复核。"
      ],
      "artifact": "group-publication-review.json",
      "call": [
        "Review disclosure evidence",
        "审核披露证据"
      ],
      "id": "d5",
      "source_id": "D5-ca13a134082b4ea8",
      "source_url": "https://github.com/datajuicer/DataJevBench/blob/5010f6aa899dd268aae8b0b9dbc4665e02999443/benchmark/records.jsonl",
      "source_note": [
        "Presentation adapted from a benchmark task; the selected action maps to its published reference label.",
        "依据原题改编展示；所选动作映射到原题参考标签。"
      ],
      "state": "Purpose: Review a data export prepared for public release. All identities and records are synthetic examples and do not correspond to real individuals; please evaluate the current export plan according to the local privacy rules of the task below, rather than judging whether the examples are real people.\nRule: Any published group must contain at least 3 distinct participants; the number of records cannot substitute for the number of people. All counts refer to deduplicated complete groups, and unknowns must be verified.\nFull evaluation scope:\n{\n  \"group\": \"demo-ward-A\",\n  \"records\": 14,\n  \"distinct_participants\": null\n}\nDoes this publication proposal present the specified privacy risks?",
      "option_ids": [
        "RISK",
        "NO_RISK",
        "REVIEW"
      ],
      "benchmark_reference": {
        "revision": "5010f6aa899dd268aae8b0b9dbc4665e02999443",
        "task_id": "D5-ca13a134082b4ea8",
        "expected": "REVIEW",
        "option_ids": [
          "RISK",
          "NO_RISK",
          "REVIEW"
        ],
        "record_sha256": "7b4408c5926234c87c50641051859239c86097ebe6d069644ea975d22d3a1fc2",
        "presentation_changes": "Bilingual paraphrase and evidence condensation; option selection is a subset only for the operator-catalog case. Outcome and explanation are presentation text, not additional reference labels."
      }
    },
    {
      "tab": [
        "Control",
        "执行控制"
      ],
      "title": [
        "A successful conversion still needs output validation.",
        "转换命令成功，不代表数据已经验收。"
      ],
      "background": [
        "A public-transport timetable was exported to the required schema. The conversion succeeded and the current output exists, but that exact output has not passed the required checks.",
        "公共交通时刻表已按给定 schema 导出。转换命令成功，当前输出也已生成，但这份输出尚未通过必需校验。"
      ],
      "goal": [
        "Choose the single next action before publishing the timetable.",
        "在正式发布时刻表前，选择当前最应该执行的一步。"
      ],
      "judge": [
        "Should the workflow inspect, transform, validate, commit or ask next?",
        "下一步应检查、转换、校验、发布，还是询问需求方？"
      ],
      "policy": [
        "Resolve goal conflicts first, then missing input facts, then known transformations. If the current output is not accepted, validate it; publish only after matching acceptance and clear authorization. A successful exit is not acceptance.",
        "依次处理口径冲突、输入事实缺口、已知转换工作；当前输出未验收时应校验。验收通过且授权明确才发布，命令成功退出不等于数据验收。"
      ],
      "headers": [
        [
          "Evidence",
          "Current state",
          "Implication"
        ],
        [
          "证据",
          "当前状态",
          "含义"
        ]
      ],
      "rows": [
        [
          [
            "Conversion",
            "Succeeded; schema mapping applied",
            "No located repair work remains"
          ],
          [
            "Current checksum",
            "sha-out-3-3",
            "Validate this exact output"
          ],
          [
            "Validation checksum",
            "null",
            "No matching acceptance receipt"
          ],
          [
            "Required checks",
            "Row count / schema / source IDs",
            "Not completed"
          ],
          [
            "Release authorization",
            "Confirmed; preserve source",
            "Authorization alone is not acceptance"
          ]
        ],
        [
          [
            "转换命令",
            "成功退出，已应用 schema 映射",
            "没有已定位的待修复工作"
          ],
          [
            "当前输出哈希",
            "sha-out-3-3",
            "须验证这份输出"
          ],
          [
            "校验回执哈希",
            "null",
            "没有匹配的验收回执"
          ],
          [
            "必需校验",
            "行数 / schema / 来源 ID",
            "尚未完成"
          ],
          [
            "发布授权",
            "已明确，须保留源数据",
            "有授权不等于已验收"
          ]
        ]
      ],
      "options": [
        [
          "Inspect files",
          "Transform data",
          "Validate current output",
          "Commit / publish",
          "Ask the requester"
        ],
        [
          "检查文件",
          "执行转换",
          "校验当前输出",
          "正式发布",
          "询问需求方"
        ]
      ],
      "answer": 2,
      "why": [
        "The goal, inputs and conversion are already established. The current output lacks the required acceptance checks, so VALIDATE is the next action; COMMIT is premature.",
        "目标、输入和转换都已明确，当前缺口是输出未通过验收。因此下一步应 VALIDATE，而不是直接发布。"
      ],
      "outcome": [
        "Validate row count, schema and source-ID consistency for sha-out-3-3 before considering publication.",
        "针对 sha-out-3-3 校验行数、schema 和来源 ID 一致性，通过后再考虑发布。"
      ],
      "artifact": "timetable-output-receipts.json",
      "call": [
        "Choose the next workflow action",
        "选择下一步动作"
      ],
      "id": "d6",
      "source_id": "D6-4944b93014e28a93",
      "source_url": "https://github.com/datajuicer/DataJevBench/blob/5010f6aa899dd268aae8b0b9dbc4665e02999443/benchmark/records.jsonl",
      "source_note": [
        "Presentation adapted from a benchmark task; the selected action maps to its published reference label.",
        "依据原题改编展示；所选动作映射到原题参考标签。"
      ],
      "state": "你负责数据处理工作流，只选当前最应该执行的一步，不写完整计划。动作优先级：目标口径有无法由现有材料消除的冲突→询问需求方；否则缺可从现有文件查到的输入事实→检查；否则有已定位且规则明确的转换/修复工作→执行转换；否则当前输出版本尚未验收→校验；全部完成且授权明确→发布。已成功退出不等于数据验收；旧checksum的收据不能验收新输出。\n当前任务和现场：\n{\n  \"request\": \"公共交通时刻表：按给定时刻表schema导出。目标路径为 /project/output/release-3/，覆盖授权已明确；源数据必须保留。\",\n  \"source\": \"/project/input/batch.csv\",\n  \"existing_metadata\": \"/project/input/schema-and-manifest.json\",\n  \"target_schema\": \"已随任务提供；不需要联网\",\n  \"input_checksum\": \"input-3\",\n  \"output_checksum\": \"sha-out-3-3\",\n  \"validation_receipt\": {\n    \"checked_output_checksum\": null,\n    \"all_required_checks_passed\": false\n  },\n  \"evidence\": \"转换命令已经成功退出，当前输出存在且规则映射已执行；但当前字节版本还没有完成必需的行数、schema和来源ID一致性校验。\"\n}\n下一步选哪个动作？",
      "option_ids": [
        "INSPECT",
        "TRANSFORM",
        "VALIDATE",
        "COMMIT",
        "ASK"
      ],
      "benchmark_reference": {
        "revision": "5010f6aa899dd268aae8b0b9dbc4665e02999443",
        "task_id": "D6-4944b93014e28a93",
        "expected": "VALIDATE",
        "option_ids": [
          "INSPECT",
          "TRANSFORM",
          "VALIDATE",
          "COMMIT",
          "ASK"
        ],
        "record_sha256": "c4524b9383a117af5ecbb69a13caadf6cee2a07c3662f75264972b6aacd3dbd3",
        "presentation_changes": "Bilingual paraphrase and evidence condensation; option selection is a subset only for the operator-catalog case. Outcome and explanation are presentation text, not additional reference labels."
      }
    }
  ]
};
