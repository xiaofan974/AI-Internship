# Week 4 Langfuse F1 judge import

Historical import of the frozen F1 golden dataset, split, and saved
judge predictions. This is not a new judge run, not a prompt
refinement, and not an application, approval, or release gate.

## Source

- Golden dataset: `week4_f1_golden_v1`
- Split: `week4_f1_split_v1`
- Label version: `week4_f1_labels_v1`
- Calibration dataset: `week4_f1_calibration_v1`
- Validation dataset: `week4_f1_validation_v1`
- Provenance ok: True
- Ledger: `/Users/aureliemahe/AI-Internship/capstone/aeacusai/data/local/evals/week4/langfuse/week4_f1_judge_import_ledger.json`
- Outputs: 40 from 20 paired scenarios
- Not 40 independent scenarios.

## Configuration

- `LANGFUSE_PUBLIC_KEY`: configured
- `LANGFUSE_SECRET_KEY`: configured
- `LANGFUSE_BASE_URL`: configured
- `AEACUS_LANGFUSE_TRACING`: missing

## Datasets

- Calibration URL: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5jrmj0010ad0kobcprfob
- Validation URL: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5js41002nad0jjxk3p587
- Each dataset contains 20 outputs from 10 paired scenarios: 5 reviewed F1 failures and 15 reviewed passes.
- Both versions of each scenario remain in the same split.
- Reviewed labels are AI-assisted judgments accepted by Lily and are stored in item metadata, not in judge task inputs.

## Historical judge runs

- `Calibration: frozen judge v1`
- `Calibration: frozen judge v2`
- `Validation: frozen judge v1`
- `Validation: frozen judge v2`
- Calibration v1 run: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5jrmj0010ad0kobcprfob/runs/c7ec1923-ad05-4b60-9585-d6c4923e02be
- Calibration v2 run: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5jrmj0010ad0kobcprfob/runs/922aa4d2-ac70-4747-b117-930d7613a7e5
- Validation v1 run: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5js41002nad0jjxk3p587/runs/1cda5b79-62ee-4d4f-9939-b8791039eedf
- Validation v2 run: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5js41002nad0jjxk3p587/runs/6ac6dabb-a6df-4deb-82c7-2da5e75296b4
- Calibration comparison: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5jrmj0010ad0kobcprfob/compare?runs=c7ec1923-ad05-4b60-9585-d6c4923e02be&runs=922aa4d2-ac70-4747-b117-930d7613a7e5
- Validation comparison: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/datasets/cmvl5js41002nad0jjxk3p587/compare?runs=1cda5b79-62ee-4d4f-9939-b8791039eedf&runs=6ac6dabb-a6df-4deb-82c7-2da5e75296b4
- Model calls: False
- Retrieval calls: False
- Hosted evaluators: False
- Judges rerun: False
- Judges refined: False

## Scores

- `judge_f1_pass`: 1=judge pass, 0=judge fail.
- `reviewed_f1_pass`: 1=reviewed pass, 0=reviewed fail. Kept separately identifiable.
- Tasks return saved verdicts, reasons, and excerpts only.
- Generation spans, token usage, and original inference durations were not invented.

## Recomputed confusion matrices

Splits are not combined. Agreement is not headlined.

### Calibration: frozen judge v1

Positive class is F1 failure.

- TP = reviewed fail / judge fail: 0
- FN = reviewed fail / judge pass: 5
- TN = reviewed pass / judge pass: 15
- FP = reviewed pass / judge fail: 0
- TPR = TP/(TP+FN): 0.0 = 0/5
- TNR = TN/(TN+FP): 1.0 = 15/15
- Valid predictions: 20
- Invalid predictions: 0
- Missing predictions: 0
- Matches frozen expected matrix: True

### Calibration: frozen judge v2

Positive class is F1 failure.

- TP = reviewed fail / judge fail: 2
- FN = reviewed fail / judge pass: 3
- TN = reviewed pass / judge pass: 15
- FP = reviewed pass / judge fail: 0
- TPR = TP/(TP+FN): 0.4 = 2/5
- TNR = TN/(TN+FP): 1.0 = 15/15
- Valid predictions: 20
- Invalid predictions: 0
- Missing predictions: 0
- Matches frozen expected matrix: True

### Validation: frozen judge v1

Positive class is F1 failure.

- TP = reviewed fail / judge fail: 0
- FN = reviewed fail / judge pass: 5
- TN = reviewed pass / judge pass: 15
- FP = reviewed pass / judge fail: 0
- TPR = TP/(TP+FN): 0.0 = 0/5
- TNR = TN/(TN+FP): 1.0 = 15/15
- Valid predictions: 20
- Invalid predictions: 0
- Missing predictions: 0
- Matches frozen expected matrix: True

### Validation: frozen judge v2

Positive class is F1 failure.

- TP = reviewed fail / judge fail: 0
- FN = reviewed fail / judge pass: 5
- TN = reviewed pass / judge pass: 15
- FP = reviewed pass / judge fail: 0
- TPR = TP/(TP+FN): 0.0 = 0/5
- TNR = TN/(TN+FP): 1.0 = 15/15
- Valid predictions: 20
- Invalid predictions: 0
- Missing predictions: 0
- Matches frozen expected matrix: True

## Decision

Neither frozen judge qualifies as an F1 detector, approval gate, or release gate. Calibration improvement did not transfer to validation.

## Verified counts

- Prepared outputs: 40
- Prepared scenarios: 20
- Calibration items verified: 20
- Validation items verified: 20
- Calibration v1 verified: 20
- Calibration v2 verified: 20
- Validation v1 verified: 20
- Validation v2 verified: 20
- Failed: 0

## Pilot

- Case: week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S01:2da3cfd8-b8be-4d2a-8754-a763ba2f21e6
- Scenario: TRACE-S01
- Baseline: week4_adk_preview_f1_v2
- Action: verified
- Calibration v1 trace: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/14d760a6375a298886bde031d0f5c2c7
- Calibration v1 judge score: 1
- Calibration v2 trace: https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/2f2fc0fa36e90bebed2dff748e86aeff
- Calibration v2 judge score: 1
- Calibration v1 ingestion delay seconds: 16.3
- Calibration v2 ingestion delay seconds: 44.2

## Remote read-back

- Calibration items: 20
- Validation items: 20
- Calibration v1 run items: 20
- Calibration v2 run items: 20
- Validation v1 run items: 20
- Validation v2 run items: 20
- Calibration source associations: 10
- Validation source associations: 10

## Per-case links

- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S01:2da3cfd8-b8be-4d2a-8754-a763ba2f21e6: reviewed fail (0); source None; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/14d760a6375a298886bde031d0f5c2c7 (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/2f2fc0fa36e90bebed2dff748e86aeff (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S01:4c969b0c-7046-4409-bca2-f096a5d34c83: reviewed pass (1); source 7166080e55ad08c29d937285cfb7de6a; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/a16082cf6dde2653b3c94b94088cdaea (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/f363713115238a37a63cb2a686e21869 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S02:aaabee81-001c-4b03-a1b6-3ed4e8efa655: reviewed pass (1); source None; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/fe55c1b0402f09f36f9fb50daeefd48d (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/adc76350b9f038701d1e53b38e97abb5 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S02:392db6f3-1620-42d1-bf81-b554ee9e1aba: reviewed pass (1); source 2e6260ed434a1d403b2f57b2c3d7de15; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/e7e35a117c558f0fec30bcb83a8e5386 (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/7ab3500f2de117b79a413a432980da54 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S03:9d315772-3c24-4440-a8c1-c52041b19dc1: reviewed pass (1); source None; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/3f361310fd8637c91bd39502cdd657b6 (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/11c178fb88919445cad408d860d53d44 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S03:17017bf1-7aec-4028-8e99-eebc58193325: reviewed pass (1); source b2eb412a339c3478a3062ea349af117b; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/4ac330bdfd165dd346d011c8410b8cd3 (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/6b59c71330b0942c78d2dcabe0ababd7 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S04:ab268600-0757-44ef-b07f-dfb273ce8871: reviewed fail (0); source None; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/821d74a578166e9f12476a2f1b4ef1ac (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/b773b471ea4524583e2de8703ede9e83 (judge=0, fail)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S04:b5caecbd-ace2-42c1-88ea-1592d163a6ed: reviewed fail (0); source 28eb0512d039da0dfb54268b0cc4de93; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/2c136c93b5924e75e5e71c436465150e (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/ad378df560e3a1117662009e6bfa431f (judge=0, fail)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S05:2aa618ff-1b1a-4c16-b74b-3ead8d11e71a: reviewed pass (1); source None; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/def051b30e8ea08af259a1e19dcb21a4 (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/bcb7e9afd2bfa73c186bf6a7e3e9a442 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S05:2bdc75d1-a252-4bec-b287-f21aab2f91de: reviewed pass (1); source 9cf279574ce7d8007de5c59ccb4d1fbe; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/bb953b7791327d4e5735192cd19d4ecc (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/72d92c26ebc01f38ca1a7578786dd3a6 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S06:c1388a22-0ce6-49f4-a625-0ed9ecf41f23: reviewed pass (1); source None; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/789a1730b0892cce3d14ab12c162a6bc (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/451e27270317475b62be2f2b8e645e60 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S06:8e8d9cef-85de-4cd7-b629-7c307ffa5710: reviewed pass (1); source 71a0090cbb31d42dfb6ab691337ef107; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/5deeaf6a4ccb76e715d07ee53d63732a (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/83a574c5f81885ad562410d53683f163 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S07:fa38efad-1ad4-4bee-ac24-91ad2442ee9f: reviewed pass (1); source None; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/bd7767337eca560f0a52eaa5bbe3d027 (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/c005f150929928bbbcc25a4f6d2b3adc (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S07:4b4980c1-3b6d-4e09-b5f4-71eccd9a96ed: reviewed pass (1); source 3aa8a5a909a8a2e4180aae797bdd02cf; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/031322e3037e4dc65182830ee0a20379 (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/59f1c300e4ee7168e8305199ba2d9fbe (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S09:43b6664b-5b39-47b2-97fb-6e2e2514b9f1: reviewed fail (0); source None; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/0bfdbd627ebcf8c35594f99f38442880 (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/808e481f7837cc39c620a963134c64f3 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S09:1615192e-ab2a-4e8d-8902-4913644fc746: reviewed fail (0); source 9e45a212095b701c97937cd966aaeb8a; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/7a2b9b354361d77b9cd4e3a60c89cfc7 (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/43f9b0d99275fafce3cce7121da5eba5 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S10:4e26e322-9f32-408f-a1ea-9ae448554e12: reviewed pass (1); source None; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/3501111800482a0ec10988f6e87106a9 (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/20e7312d027c08e9b950a448d6a3e799 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S10:22b36ab5-77e2-454f-87e0-320245240b75: reviewed pass (1); source 47a39139f47117d6aa2945c996ee6de7; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/e970245de24d5fb5f0c318b5541bb01c (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/2b39787f98b3fee74b87cba2385d2daa (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S11:acaa91b8-95f4-44a5-8825-4a046c29bec2: reviewed pass (1); source None; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/a0ba855894bd4ba476f796b329684638 (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/d4861b11789c2594feb94fc08ced3274 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S11:a08c00bc-1578-4a20-a2d6-89669e3fc29c: reviewed pass (1); source 077a7658f59e50284d71fca5f1510c7c; calibration_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/343b451ae81ac2d49bac7a028bb3252e (judge=1, pass); calibration_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/814bb88160a91cd24f4b0f911ebb18b3 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S08:d0eb1005-47c9-44bc-aa5c-eb9c18d3b601: reviewed pass (1); source None; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/862244677ecc051112b95675619bddef (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/a856ecb5144ffe66a61ba12b2b064627 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S08:21c988a6-775a-4a2f-8513-8aa29423b18a: reviewed fail (0); source 235e3b9abf157c5a4ac153f1c830fd64; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/add11e98f0414793d38b79b627b37fa0 (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/d52b21d6cf1732a73e56868831b78dfd (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S12:9e53160d-b461-45da-9b53-3572bf5b6c13: reviewed pass (1); source None; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/b3633c28e4ab54df1151b50db9f0e967 (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/cf4492cece4f6e38ef47cc8638536905 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S12:e547178d-c70a-4cca-9591-ec733fd01c26: reviewed pass (1); source 36c0ae2d4315f8f77a82131e519e6721; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/f2aaf3badbd9a8f120b894317bf1a531 (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/9a7424a0b533b241a48f92baf94a1623 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S13:4eb39bb8-253c-4c56-aa5f-a1d7dc5ec1bc: reviewed fail (0); source None; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/d0eaf011553925c89d3f343549a536b9 (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/4a3a16c1f44ffa0b4d03b86ce7f583d8 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S13:7ccd9cdd-3612-419a-9cda-b76ce3e901b2: reviewed fail (0); source 01469e43fbce99f65e581ce2d5999260; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/2444e7641abf3f2292dc162d78a0d182 (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/74858f6dbd4cb3722fccd03ea91a29aa (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S14:4112acb0-e775-4193-a734-578b0cc99ae2: reviewed pass (1); source None; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/90a555f961d37733990e9efc385a279a (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/4150750e64d21574e00cfc36efef8f32 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S14:ab3b0d19-a131-4304-b6af-83a24bd1dabd: reviewed pass (1); source 9b2086eafe0284b210b92900e76847eb; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/748beb68f5b63287daf3a955aa9e8f26 (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/f7c0d4a97ad6ef0d9f07d23dc64d61a5 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S15:0fe52a24-d0c4-4f6d-abe3-e4271e8044fa: reviewed fail (0); source None; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/acf1f870f89b8d20461f1173b675e59e (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/52b3fb6fa7031fd7c3fe3073836eee65 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S15:305708e0-218e-4c79-88f2-50f226ec7998: reviewed pass (1); source 1355dd598fa8f31b1e34d5f04a77432d; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/3f73bdacd77d6a4e09d7465a64fcd135 (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/531218db025633f94b141647920a8ec1 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S16:4a7e7395-aaee-4aca-bc5f-b3109c72950d: reviewed pass (1); source None; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/a28c8c3d8699b96b01d1424b874b49d0 (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/107d19357d5933c1092d9273557ff2a5 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S16:07fb835c-7dbf-4b71-9aca-06a43c263150: reviewed pass (1); source 72593e9538937b213690d37e75773994; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/b568cbf03dab8ef0568f6c164e5b6def (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/8777a3ec529ec2728531c83c34bf0c09 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S17:4c2809a3-f27d-48b2-bc4a-f8e3efc41cf5: reviewed pass (1); source None; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/1c97388d0a313108d73f7168a861492f (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/7786a313a35a390a29efaa65f28759c6 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S17:1fc62262-6590-4429-833a-2e9c269a5928: reviewed pass (1); source 41b6cecee4186aca0995d5a6ee36a902; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/86926e8dc9a31b98ccbe6d95d54f213f (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/d3140dd527917eda05440eaaaf13f290 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S18:3bcf7890-78ba-4417-ba06-5d4916bd7ba7: reviewed pass (1); source None; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/aba47c9a42dc0c94a9964852c797a3ef (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/134717c6b5311934c7f4d36626ad9e11 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S18:74c715ab-7ad1-4fb5-afdf-50acc7f7057b: reviewed pass (1); source 130eef63a19e17745b8109b9a013c0c6; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/a9b320afaaaea3f3ddd75043a0d7b914 (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/6684e144b48159a53ccbdd1fa5d77f7f (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S19:3386d04f-a9ec-49cf-8af0-57bdcbc1ed76: reviewed pass (1); source None; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/c8f457a18b164a3ab2121965cbc29c54 (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/cef54254e9a79ebd4d8ec4292fbd926d (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S19:fd86e112-fb20-42fa-b9f7-e0a65125342b: reviewed pass (1); source f59c25e59f453edf2534336af62f5221; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/4178dcd947aca413cf3a434286dbe09a (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/b1c631523f3e2cf6bdd91a86ddef8c8d (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_f1_v2:TRACE-S20:39349126-070f-4c7b-bb2f-a05c5ec33ab4: reviewed pass (1); source None; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/1c4becefabde9b80df74f5a160410c47 (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/851407f6ca675d49ec3f48e035f1d3c2 (judge=1, pass)
- week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S20:feb73275-7e82-4159-8bb9-1e90cf15edac: reviewed fail (0); source 6a3c91627c769b051ec0e9d13aa24681; validation_v1 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/84b5a0750ea6d3fa17a2deb97bb392e9 (judge=1, pass); validation_v2 https://cloud.langfuse.com/project/cmvl15h4200gnad0hwelqbeas/traces/113a2b67a829dc6bf41fd703826fd9a3 (judge=1, pass)

## Limitations

- Outputs are saved historical judge predictions, not new inference.
- Reviewed labels are AI-assisted judgments accepted by Lily, not independent expert legal adjudication.
- Candidate traces were not historically imported, so only parent Langfuse source associations are available.
- Neither judge is an F1 detector, approval gate, or release gate.
- Existing baseline, timing, and F1 prompt comparisons were not rewritten.
- Frozen local golden, split, prompt, and prediction artifacts were not rewritten.
