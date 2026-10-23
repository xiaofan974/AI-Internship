# Week 4 Langfuse F1 prompt comparison

Frozen F1 prompt experiment on the existing `week4_adk_preview_v1`
dataset. Historical parent raw answers versus the rejected prompt
candidate raw answers. This is not a timing repair, not 20 new live
executions, and not an overall quality percentage.

## Source

- Dataset: `week4_adk_preview_v1`
- Parent baseline: `week4_adk_preview_v1`
- Candidate baseline: `week4_adk_preview_f1_v2`
- Parent SHA-256: `29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1`
- Candidate SHA-256: `3b1fa10c5a05a8db61403ddda04d3e6d5ecf0ae06f684daf3cf30392e253f848`
- Parent instruction: `6d28bfa7d6d42c8ce1c21211b1e87adf877137ed878b1082c0ec6f36716a7de7`
- Candidate instruction: `20f72d6ea00bb6a052266a9abc79066d93119f321a56a3cea446f556cda9517e`
- Live instruction restored to parent: True
- Provenance ok: True
- Ledger: `/Users/aureliemahe/AI-Internship/capstone/aeacusai/data/local/evals/week4/langfuse/week4_adk_preview_v1_f1_comparison_ledger.json`

## Configuration

- `LANGFUSE_PUBLIC_KEY`: configured
- `LANGFUSE_SECRET_KEY`: configured
- `LANGFUSE_BASE_URL`: configured
- `AEACUS_LANGFUSE_TRACING`: missing

## Comparison runs

- Parent: `F1: historical parent answers`
- Candidate: `F1: rejected prompt candidate answers`
- Dataset URL: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk
- Parent run URL: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk/runs/f69dda5b-a214-442a-9a69-9354f7854f59
- Candidate run URL: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk/runs/f7082e56-ac7c-4119-8ee7-cc6dc2550d78
- Comparison URL: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl38qq70005ad0n1jlmyvuk/compare?runs=f69dda5b-a214-442a-9a69-9354f7854f59&runs=f7082e56-ac7c-4119-8ee7-cc6dc2550d78
- Timing formatter applied: False
- Model calls: False
- Retrieval calls: False
- Hosted judges: False

## Reviewed F1 scores

- Score name: `reviewed_f1_pass`. Encoding: 1=pass, 0=fail.
- Imported AI-assisted judgments accepted by Lily.
- Not: independent expert legal adjudication.
- Parent fail IDs: ['TRACE-S04', 'TRACE-S08', 'TRACE-S09', 'TRACE-S13', 'TRACE-S20'].
- Candidate fail IDs: ['TRACE-S01', 'TRACE-S04', 'TRACE-S09', 'TRACE-S13', 'TRACE-S15'].
- Recoveries: ['TRACE-S08', 'TRACE-S20'].
- Regressions: ['TRACE-S01', 'TRACE-S15'].
- Persistent failures: ['TRACE-S04', 'TRACE-S09', 'TRACE-S13'].
- Both versions: 15/20 F1 pass, 5/20 F1 fail. These are not an overall quality percentage.
- Candidate F2 labels were not assigned and were not scored.

## Verified counts

- Prepared pairs: 20
- Parent run items verified: 20
- Candidate run items verified: 20
- Paired cases verified: 20
- Failed: 0

## Pilot paired case

- Scenario: TRACE-S01
- Action: verified
- Parent trace: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/a9878a6b6c827661d96e2dc4f99bea97
- Parent score: 1
- Candidate trace: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/3789c2ae3cb294227e2be92ee4d34f61
- Candidate score: 0
- Parent ingestion delay seconds: 12.8
- Candidate ingestion delay seconds: 12.9

## Remote read-back

- Dataset items: 20
- Parent run items: 20
- Candidate run items: 20

## Per-trace links

- TRACE-S01: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/a9878a6b6c827661d96e2dc4f99bea97 (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/3789c2ae3cb294227e2be92ee4d34f61 (0)
- TRACE-S02: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/84e42139e1102af0d3e8919d88f100d1 (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/af04d7328308e934797d1b359b02c05d (1)
- TRACE-S03: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/378be61b676654bda6a214213100f7c2 (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/77f5764093e07414efeba09947329e17 (1)
- TRACE-S04: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/d7b11d4d2040cff7fd06df256b050d2f (0); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/751cde8a745219e3a70d8b7e5e61baac (0)
- TRACE-S05: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/d662998de43c832d23c6fba893eeb1e4 (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/cab205059911a8f90b4e48ae95696b04 (1)
- TRACE-S06: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/7b46ffb8acb405faed7eb53ac93a13c9 (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/f3de5eaf026bf5bbab5e698d3dd0c4f3 (1)
- TRACE-S07: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/1315c4adb74f5ebd4b947829c2eb05bd (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/a9479bbdd082462007ae5e096b0c085f (1)
- TRACE-S08: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/36a4c5f9780b331a8505c64afb8aea06 (0); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/d93dffc9f86577599fc29bb059ed9863 (1)
- TRACE-S09: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/d1b22b381283a2c8ebe9caa2d9a1be3a (0); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/e12af8a96cfc06bad9bb8eee245828e5 (0)
- TRACE-S10: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/0b026d10c682550d53b6d322fdfb049b (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/4b0da788b64fd8e110788348e5420b5a (1)
- TRACE-S11: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/788d9705806c756962e32f1d7dd2ff59 (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/3cf100e794aaa22a408823968dac5596 (1)
- TRACE-S12: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/b2752f57607f755c6fd4fc8035fc7f3d (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/5fdf903dc66940f3de9121561f8105dd (1)
- TRACE-S13: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/2e15de48505b99f91a94b885739831a8 (0); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/8695fc173fb9bb1fa9ead1162f682ee7 (0)
- TRACE-S14: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/e685a0ff246d1eff004faddda63218ce (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/8f5cf87c9c9d2ea751ddbf77b095d293 (1)
- TRACE-S15: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/eb20dd2fcb767391e4894b1bd51e808e (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/0671977fbc1e8b4ce505b52edf9190f8 (0)
- TRACE-S16: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/38b57fb2be9cf6d1588d4e3511c7a293 (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/fee94e2213be1d5ac4459a99d2ada43e (1)
- TRACE-S17: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/2371ff2614253598ea1e8c54bce88358 (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/41a8349e682df0b035080b9e5b6f0756 (1)
- TRACE-S18: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/850f5a88f5a2b4383e7a16401c62e896 (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/d76dafe2d5d9f64b8969049466bd9c6e (1)
- TRACE-S19: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/18ae258b7b72a9f714571c29fcf7a9e8 (1); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/a9f1a189e7e328aefb962359c82f28e0 (1)
- TRACE-S20: parent https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/d74fada895a0b5573ef9bec29027ab4a (0); candidate https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/145b85813fca1fbb8a0b12441e3c0f39 (1)

## Limitations

- Outputs are the original saved raw answers. The timing formatter was not applied.
- Scores are imported reviewed F1 judgments, not newly generated labels.
- This is not independent expert legal adjudication.
- Candidate F2 was not labelled or scored. No overall quality percentage is reported.
- Existing timing comparison runs and historical source traces were not rewritten.
