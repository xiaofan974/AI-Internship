# Week 4 Langfuse baseline import

Historical import of frozen `week4_adk_preview_v1` only. No new model
calls, retrieval, hosted evaluators, or review-register access.

## Source

- Baseline: `week4_adk_preview_v1`
- Source SHA-256: `29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1`
- Source verified: True
- Ledger: `/Users/aureliemahe/AI-Internship/capstone/aeacusai/data/local/evals/week4/langfuse/week4_adk_preview_v1_import_ledger.json`
- Importer/ledger already present: False

## Configuration

- `LANGFUSE_PUBLIC_KEY`: configured
- `LANGFUSE_SECRET_KEY`: configured
- `LANGFUSE_BASE_URL`: configured
- `AEACUS_LANGFUSE_TRACING`: missing

## Expected original scores

- Reviewed F1–F4 labels: imported AI-assisted judgments accepted by Lily.
- Timing check: 18/20 pass, 2 fail.
- S19 retrieval budget: 1 fail; 19 excluded.
- Score encoding: 1=pass, 0=fail. Reviewed and automated names are separate.

## Verified counts

- Prepared: 20
- Verified: 20
- Uploaded but not fully verified: 0
- Failed: 0
- Skipped already verified: 0

## Pilot

- Scenario: TRACE-S01
- Action: verified
- Trace: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/7166080e55ad08c29d937285cfb7de6a
- Ingestion delay seconds: 14.9
- Missing fields: []
- Missing observations: []
- Missing scores: []
- Read-back scores: reviewed_f1–f4 = 1; automated_deferred_date_qualifications_v1 = 1; S19 score absent (excluded)

The remaining 19 were imported only after this pilot read-back succeeded.

## Remote read-back

- All 20 traces returned `historical-import`, `recorded-events`, and `recorded-evidence` with non-empty root input/output.
- Ingestion delay after flush: 14.7–29.4 seconds. No missing fields, observations, or scores on the verified set.
- TRACE-S02 timing fail read back as `automated_deferred_date_qualifications_v1 = 0`.
- TRACE-S20 timing fail read back as `automated_deferred_date_qualifications_v1 = 0`.
- TRACE-S19 retrieval-budget fail read back as `automated_s19_retrieval_budget_v1 = 0`; the other 19 traces have no S19 score.
- Reviewed labels use separate names (`reviewed_f1` … `reviewed_f4`), 1=pass and 0=fail, attributed as imported AI-assisted judgments accepted by Lily.

## Langfuse links

- TRACE-S01 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/7166080e55ad08c29d937285cfb7de6a
- TRACE-S02 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/2e6260ed434a1d403b2f57b2c3d7de15
- TRACE-S03 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/b2eb412a339c3478a3062ea349af117b
- TRACE-S04 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/28eb0512d039da0dfb54268b0cc4de93
- TRACE-S05 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/9cf279574ce7d8007de5c59ccb4d1fbe
- TRACE-S06 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/71a0090cbb31d42dfb6ab691337ef107
- TRACE-S07 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/3aa8a5a909a8a2e4180aae797bdd02cf
- TRACE-S08 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/235e3b9abf157c5a4ac153f1c830fd64
- TRACE-S09 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/9e45a212095b701c97937cd966aaeb8a
- TRACE-S10 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/47a39139f47117d6aa2945c996ee6de7
- TRACE-S11 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/077a7658f59e50284d71fca5f1510c7c
- TRACE-S12 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/36c0ae2d4315f8f77a82131e519e6721
- TRACE-S13 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/01469e43fbce99f65e581ce2d5999260
- TRACE-S14 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/9b2086eafe0284b210b92900e76847eb
- TRACE-S15 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/1355dd598fa8f31b1e34d5f04a77432d
- TRACE-S16 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/72593e9538937b213690d37e75773994
- TRACE-S17 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/41b6cecee4186aca0995d5a6ee36a902
- TRACE-S18 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/130eef63a19e17745b8109b9a013c0c6
- TRACE-S19 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/f59c25e59f453edf2534336af62f5221
- TRACE-S20 (verified): https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/6a3c91627c769b051ec0e9d13aa24681

## Limitations

- Observation timestamps are import-time. Original run IDs and timestamps are provenance metadata only.
- No per-event timestamps, model generations, or tool durations were invented.
- Duplicate prevention uses deterministic trace/score IDs plus the local ledger.
