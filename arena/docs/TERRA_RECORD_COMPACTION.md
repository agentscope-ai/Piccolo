# Terra v19 公开记录去重

> 此文描述 v19 完整公开记录的无损去重。2026-10-21 起，前端及新策略可在其上使用 `engine.model_input()` 的意图视图；字段保留范围与评测见 [模型输入优化](MODEL_INPUT_INTENT_20261021.md)。`observe()` 与旧记录的严格回放仍遵守下方合同。

入口仍为共享注册表 `get_engine('terraria_survival').observe(snapshot)`。前端、采样和RL使用同一条 `as_record → adapt_record → compact_record` 链路；物理快照、合法动作ID、动作执行、期限、奖励、可见性及实时调度均不变。

新记录包含：

```json
{
  "prompt_revision": "terramai-visible-hierarchy-v19-compact-public-facts",
  "record_format": "jev.terramai.compact-public.v1"
}
```

表示规则：

- `{"$ref":"/observation/last_effects"}` 指向当前 `State` 内完全相同的公开值，不访问引擎或外部数据。重复动作效果、成长计数、工具靶格和目标只保留一份。
- `observation.known_surface_route` 的 `columns=["x","y","last_seen_frame"]` 对应每条 `rows`；全表相同的 `certainty` 共同存储。每个路线点和观察时间完整保留；不同certainty或额外字段的旧结构保持原样。
- 多个敌人完全相同的 `native_attack` 放入 `shared_facts.native_attacks`，各敌人引用它。不同几何、命中方向、精度或不确定性不会合并。
- 候选共同的提前终止条件放入 `shared_facts.candidate_execution`，每个候选继续保留自身的240/300/360物理帧期限与完整策略描述。

`jev_terraria_contract.expand_record(record)` 无损恢复原v18公开记录，适用于等价校验与冻结评测隔离身份，不能用来替换模型当时实际看到的输入。`record_for_revision(snapshot, revision)` 按决策时保存的版本生成记录；旧v17/v18和新v19的回放均比较完整原记录，不能仅因展开后相同而接受不同的新输入。重新适配已压缩记录保持幂等。

旧轨迹、概率、标签、loss metadata不重写。新格式只进入新采样；模型策略效果须重新实测。

回归入口：

```bash
.venv/bin/python -m unittest tests.terra_record_compact
```

两条真实公开状态用原 `PromptTemplate` 和SFT310 tokenizer测得：10,516→8,231及16,189→12,845训练tokens，分别减少21.73%与20.66%；候选值、标签及对应token ID保持一致。该结果是格式长度与等价验证，不是模型胜率或墙钟提速。
