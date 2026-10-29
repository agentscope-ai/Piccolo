// Bilingual metric display copy. Update descriptions here; scoring is defined separately.
window.JevBenchmarkMetrics = {
  "schema_version": "jev.metric-descriptions.v1",
  "harnessjevbench": {
    "accuracy": {
      "en": {
        "name": "Decision Accuracy",
        "description": "Decision Accuracy · Higher is better. Measures decision correctness on tasks with definite reference answers. Correct answers score 1; incorrect or failed responses score 0. Scores are averaged within each task, then equally across tasks."
      },
      "zh": {
        "name": "决策准确率",
        "description": "决策准确率 · 越高越好。衡量模型在有明确标准答案的任务上做出正确决策的程度。答对得 1 分，答错或调用失败得 0 分。先计算每个任务内的问题平均分，再对所有任务等权平均。"
      }
    },
    "soft_tv": {
      "en": {
        "name": "Distribution Distance (TV)",
        "description": "Distribution Distance (TV) · Lower is better. Measures the distance between predicted and reference probability distributions on tasks with distribution targets. TV ranges from 0 to 1, where 0 means an exact match. Distances are averaged over valid probability outputs."
      },
      "zh": {
        "name": "概率分布距离（TV）",
        "description": "概率分布距离（TV）· 越低越好。衡量模型预测概率分布与参考分布之间的距离，适用于以概率分布为参考答案的任务。TV 范围为 0–1，0 表示完全一致。最终取有效概率输出的距离平均值；无效或缺失输出不参与计算。"
      }
    }
  }
};
