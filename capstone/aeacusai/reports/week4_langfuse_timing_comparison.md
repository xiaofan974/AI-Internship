# Week 4 Langfuse timing-repair comparison

Source-linked dataset for frozen `week4_adk_preview_v1`, compared as
historical raw model answers versus a fresh application-layer timing
repair. This is not improved model reasoning and not 20 new live
agent executions.

## Source

- Baseline: `week4_adk_preview_v1`
- Dataset: `week4_adk_preview_v1` (`v1`)
- Source SHA-256: `29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1`
- Source verified: True
- Provenance ok: True
- Ledger: `/Users/aureliemahe/AI-Internship/capstone/aeacusai/data/local/evals/week4/langfuse/week4_adk_preview_v1_timing_comparison_ledger.json`
- Historical import ledger: `data/local/evals/week4/langfuse/week4_adk_preview_v1_import_ledger.json`

## Configuration

- `LANGFUSE_PUBLIC_KEY`: configured
- `LANGFUSE_SECRET_KEY`: configured
- `LANGFUSE_BASE_URL`: configured
- `AEACUS_LANGFUSE_TRACING`: missing

## Dataset

- One item per TRACE-S01–S20.
- Each item is linked to its verified historical Langfuse source trace.
- Task input is the scenario only. Reviewed F1–F4 labels stay in metadata.
- The original model answer is not stored as a gold-standard expected output.
- Dataset id: `cmvl38qq70005ad0n1jlmyvuk`
- Dataset URL: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk

## Comparison runs

- Historical raw: `Historical raw model answers`
- Timing repair: `Timing repair: application-layer replay`
- Delivered outputs: Fresh application-layer replay of the original saved observations. No model or retrieval calls.
- Formatter: `aeacus.timing_scope.v1` v1
- Model calls: False
- Retrieval calls: False
- Hosted judges: False
- Raw run URL: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk/runs/22a7a562-ddc9-41ae-9829-1c4fb94d6c09
- Repair run URL: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk/runs/0559cdda-847b-4f3b-9727-8f4b53620820
- Comparison URL: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk/compare?runs=22a7a562-ddc9-41ae-9829-1c4fb94d6c09&runs=0559cdda-847b-4f3b-9727-8f4b53620820

## Scores

- Checker: `deferred_date_qualifications_v1` unchanged.
- Encoding: 1=pass, 0=fail.
- Expected raw: 18/20 pass; fail ['TRACE-S02', 'TRACE-S20'].
- Expected delivered: 20/20 pass; fail [].
- Recomputed raw: 18/20; fail ['TRACE-S02', 'TRACE-S20'].
- Recomputed delivered: 20/20; fail [].
- Delivered-output scores are written only on comparison-run traces, not on the original raw source traces.

## Verified counts

- Prepared pairs: 20
- Dataset items verified: 20
- Historical raw run items verified: 20
- Timing-repair run items verified: 20
- Paired cases verified: 20
- Failed: 0

## Pilot paired case

- Scenario: TRACE-S01
- Action: verified
- Raw trace: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/02344074d3687bdc80c08a49b17f8763
- Raw score: 1
- Delivered trace: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/193fd9f2f61664bd634b6d16f23a3fb1
- Delivered score: 1
- Raw ingestion delay seconds: 18.0
- Delivered ingestion delay seconds: 46.2

## Remote read-back

- Dataset items: 20
- Historical raw run items: 20
- Timing-repair run items: 20

## Per-trace links

- TRACE-S01: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/7166080e55ad08c29d937285cfb7de6a; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/02344074d3687bdc80c08a49b17f8763 (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/193fd9f2f61664bd634b6d16f23a3fb1 (1)
- TRACE-S02: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/2e6260ed434a1d403b2f57b2c3d7de15; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/7863decbe23e028ea318bf195534e1ca (0); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/3b91b52f6188c0012a5148e52074c737 (1)
- TRACE-S03: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/b2eb412a339c3478a3062ea349af117b; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/82d51a8603dae0d988981648293e5fce (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/fa192d58aa0ffe5473e67f6393ea4073 (1)
- TRACE-S04: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/28eb0512d039da0dfb54268b0cc4de93; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/17fce61a059ffcd16983e26aed917b06 (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/311f0450541a82ecf282b1066280d85e (1)
- TRACE-S05: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/9cf279574ce7d8007de5c59ccb4d1fbe; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/2dcbec3e5c64584f11ec33bc4485368c (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/19a8b0a2209a7d80e1962e39f06f2b74 (1)
- TRACE-S06: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/71a0090cbb31d42dfb6ab691337ef107; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/09fbe68b053420d8555de2259bfbfaab (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/911425f9049533e9d5c4f973ade5a437 (1)
- TRACE-S07: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/3aa8a5a909a8a2e4180aae797bdd02cf; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/218b60ef701c78f833c40a94df8de82b (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/50bb1d695164b6305ec6ef037e61baad (1)
- TRACE-S08: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/235e3b9abf157c5a4ac153f1c830fd64; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/ef0cf8bf1e472581e56e34efaa89ec36 (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/705e959f995a4bb8429849075712fc5f (1)
- TRACE-S09: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/9e45a212095b701c97937cd966aaeb8a; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/87f6bf6e060fa4a312741c2652cb8873 (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/05b4dd51988bc5ee7553f6004dfd9d68 (1)
- TRACE-S10: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/47a39139f47117d6aa2945c996ee6de7; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/259586b7e46f3ce377d0d44b80f422a1 (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/299f6e9fc8eabdf9f4e063a6b8d44243 (1)
- TRACE-S11: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/077a7658f59e50284d71fca5f1510c7c; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/890460b50769c8538dee5ad9d0c1f89c (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/da3f98e43aab7078ed00dfbdd6b76209 (1)
- TRACE-S12: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/36c0ae2d4315f8f77a82131e519e6721; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/fd876614b3a0cab832587dffd3a181d4 (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/66615967a59475c7426566c6fe4dc867 (1)
- TRACE-S13: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/01469e43fbce99f65e581ce2d5999260; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/b37853b029ee3c01f2d999c137e61b6c (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/bc6756351f357b78ee7c76716247060f (1)
- TRACE-S14: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/9b2086eafe0284b210b92900e76847eb; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/949bfb70e9a9e8cd13536a083f78b660 (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/aca3f281df0f5ce458b3b47a8fcfac83 (1)
- TRACE-S15: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/1355dd598fa8f31b1e34d5f04a77432d; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/0b33d8d7526b99174c6b133bd6259ecf (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/5acda1283c2dbfc14acef1c214975cd0 (1)
- TRACE-S16: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/72593e9538937b213690d37e75773994; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/66027ba0e71dd086a3100a2433d0c124 (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/613b4cb796f5b65fbceeb7d5433e0c37 (1)
- TRACE-S17: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/41b6cecee4186aca0995d5a6ee36a902; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/b8d4ff4310c7bcc12bf6b8e4dba67958 (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/40f6fd4fa0135791dc712cca759064c6 (1)
- TRACE-S18: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/130eef63a19e17745b8109b9a013c0c6; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/8a6e83542288d1eecd08dbd9749513a4 (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/77a1aba0536a767ed885ec6a4b30eece (1)
- TRACE-S19: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/f59c25e59f453edf2534336af62f5221; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/89e330c85e8be58b5460d65326946382 (1); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/9362fe10e5ae72ab0179805f48dc3615 (1)
- TRACE-S20: source https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/6a3c91627c769b051ec0e9d13aa24681; raw https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/369cf17f4a21d898761749e42c736aac (0); delivered https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/c1859faf74d5366a534827bab9dc939a (1)

## Limitations

- Delivered outputs were regenerated with the deterministic Timing and scope formatter from the original saved observations.
- This comparison is an application-layer repair, not a claim that the model reasoned better.
- No new inference, retrieval, hosted judges, or review-register access.
- Duplicate prevention uses stable dataset item IDs, named experiment runs, and the local ledger.
