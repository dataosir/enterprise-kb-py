# F12 · 检索评测（Benchmark）

## 1. 背景与目标

调 chunk_size / top_k 缺乏量化依据。离线 benchmark 在隔离临时向量库上对比多组参数组合的 Hit@1、Hit@K、平均分，不调用 LLM，适合学习与 CI 冒烟。

## 2. 用户故事 / 场景

- 作为学习者，我运行 `make benchmark` 看哪组 chunk/topK 在 sample-docs 上命中最好。
- 作为开发者，我扩展 `benchmark_cases.json` 加入业务问题。
- 作为面试准备，我结合 [`../../enterprise/RAG_EVALUATION.md`](../../enterprise/RAG_EVALUATION.md) 解释 Hit@K 指标。

## 3. 功能范围

**In**

- 脚本：`scripts/benchmark_rag_params.py`
- 一键：`scripts/benchmark.sh` / `make benchmark`
- 用例：`scripts/benchmark_cases.json`（5 条默认）
- 隔离目录：`data/benchmark/`（不污染生产 Chroma）
- 输出：终端表格 + CSV + JSON
- 指标：hit@1, hit@k, avg_score, ctx_chars, chunks

**Out**

- 端到端 RAGAS（faithfulness、answer relevancy）
- 自动写回推荐参数到 rag_settings
- LLM 回答质量评分

## 4. 主流程与边界

1. 对每组 `(chunk_size, top_k)` 重建临时索引。
2. 对每条 case 检索，检查 top1/topk 是否命中 `expected_doc`。
3. 汇总并推荐（命中率相同则选分数更低、上下文更短）。

**边界**：仅测检索，不含生成；用例需人工维护期望文档名。

## 5. 关键配置键

命令行参数：`--chunk-sizes`, `--top-k-values`, `--cases-file`, `--verbose`

## 6. 代码锚点

- `scripts/benchmark_rag_params.py`
- `scripts/benchmark.sh`
- `scripts/benchmark_cases.json`
- `Makefile` — `benchmark` target

## 7. 验收标准

- [ ] `make benchmark` 无 API Key 可完成
- [ ] 输出 `data/benchmark/benchmark_rag_params.csv`
- [ ] sample-docs 默认 5 题 hit@1=100%
- [ ] `--verbose` 打印每组明细

## 8. 已知缺口 / 待迭代

- 未覆盖 hybrid / rerank 路径
- 无 CI 自动跑 benchmark
- RAGAS 集成见 enterprise 方案 Phase 6
