# Week 4 F1 judge v2 calibration

This report scores the frozen F1 judge v2 on the calibration split only. This is the single permitted calibration refinement. The prompt was not refined after this batch. The judge is not an application or approval gate. These are not held-out results.

## Scope

- Judge ID: `week4_f1_judge_v2`
- Parent: `week4_f1_judge_v1`
- Split: calibration only (20 outputs from 10 paired scenarios)
- Positive class: F1 failure (`fail`)
- Model: `gemini-3.8-flash`
- Prompt version: `f1_judge_prompt_v2`
- Prompt SHA-256: `abf09e1eb07c4a2da859182d6a64b2c1f94124afddfcfab1b1af08f581f7ad0e`
- Inference config SHA-256: `98647f8ff1b59f504b1642c96a24c1f18ec1898dc4b9f4748f47d976f11f05c1`
- Generation settings: identical to v1
- Stopped: False
- Stop reason: none

## Refinement provenance

- Hypothesis: V1 accepted an answer whenever its opening or Missing facts section acknowledged uncertainty, without checking whether Why still asserted that unresolved fact.
- Calibration cases that informed v2: TRACE-S01 `bd7ec9dcdb3fcb7c`, TRACE-S04 `c953f67527f058d9`, TRACE-S04 `4913922de88dad21`, TRACE-S09 `f9aafb2598bd29ec`, TRACE-S09 `13df6b9eac4fa317`, TRACE-S02 `c46d129cacb772e2`
- Example A (fail despite a caveat) is adapted from calibration `TRACE-S04` / `c953f67527f058d9` without identifiers in the prompt.
- Example B (conditional pass) is adapted from calibration `TRACE-S02` / `c46d129cacb772e2` without identifiers in the prompt.
- Prompt examples reuse calibration cases. Do not treat this batch as held-out validation.
- Validation payloads and labels were not inspected for this refinement.

## v2 confusion matrix

Failure is the positive class. Invalid or missing predictions are excluded from TP/FN/TN/FP and are not coerced into pass or fail.

- TP: 2
- FN: 3
- TN: 15
- FP: 0
- TPR = TP/(TP+FN): 0.400 = 2/5
- TNR = TN/(TN+FP): 1.000 = 15/15
- Positives represented in the rates: 5
- Negatives represented in the rates: 15

## Coverage

- Expected calibration outputs: 20
- Valid predictions: 20
- Invalid / contract errors: 0
- Missing predictions: 0
- Prediction coverage: 1.0
- All 20 calibration outputs produced a valid judge response.

## v1 versus v2

Both rows are calibration results. Prompt examples reuse calibration cases, so v2 is not a held-out comparison.

| Metric | v1 | v2 |
|---|---|---|
| TP | 0 | 2 |
| FN | 5 | 3 |
| TN | 15 | 15 |
| FP | 0 | 0 |
| TPR | 0.000 (0/5) | 0.400 (2/5) |
| TNR | 1.000 (15/15) | 1.000 (15/15) |
| Valid | 20 | 20 |
| Contract errors | 0 | 0 |
| Missing | 0 | 0 |

- False negatives corrected: 2
- False negatives retained: 3
- New false positives: 0
- Other regressions: 0

### False negatives corrected

- TRACE-S04 / `c953f67527f058d9`: reviewed fail; v1=pass; v2=fail
- TRACE-S04 / `4913922de88dad21`: reviewed fail; v1=pass; v2=fail

### False negatives retained

- TRACE-S01 / `bd7ec9dcdb3fcb7c`: reviewed fail; v1=pass; v2=pass
- TRACE-S09 / `f9aafb2598bd29ec`: reviewed fail; v1=pass; v2=pass
- TRACE-S09 / `13df6b9eac4fa317`: reviewed fail; v1=pass; v2=pass

### New false positives

None.

### Other regressions

None.

## Calibration false negatives

### 1. TRACE-S01 / `bd7ec9dcdb3fcb7c`
- Reviewed label: fail
- Judge verdict: pass
- Reason: The answer properly treats the statutory criteria and missing technical facts as open conditions rather than asserting unstated premises as established facts.
- Relevant answer excerpt: ### Provisional finding

The system provisionally falls within the high-risk classification scope under Annex III, point 4 via Article 6(2). However, whether the system is ultimately classified as high-risk depends on unresolved material facts: specifically, whether the automated…
- Input: A mid-size logistics company uses an AI system to read incoming CVs, discard applications that lack a driving licence, and show remaining candidates in a ranked list to human recruiters. Recruiters may interview anyone on the list.

### 2. TRACE-S09 / `f9aafb2598bd29ec`
- Reviewed label: fail
- Judge verdict: pass
- Reason: The answer properly treats the classification under Article 6(3) as conditional and does not assume unstated premises as established facts.
- Relevant answer excerpt: ### Provisional finding
The tool provisionally falls within the scope of Annex III, point 7(c) as an AI system used on behalf of competent public authorities to assist in examining applications for asylum. However, its classification as high-risk under Article 6(2) versus non-hig…
- Input: A government contractor uses a tool that reads asylum-file PDFs and proposes a “complexity score” so caseworkers can pick which files to open first. The score is visible on the caseworker dashboard.

### 3. TRACE-S09 / `13df6b9eac4fa317`
- Reviewed label: fail
- Judge verdict: pass
- Reason: The answer properly conditions the Annex III and Article 6(3) analysis on the facts provided without treating missing premises as established.
- Relevant answer excerpt: ### Provisional finding

The tool is provisionally classified as a high-risk AI system under Article 6(2) and Annex III, point 7, unless it satisfies the conditions for an exception under Article 6(3).

### Why

The tool is used by a government contractor on asylum files to gener…
- Input: A government contractor uses a tool that reads asylum-file PDFs and proposes a “complexity score” so caseworkers can pick which files to open first. The score is visible on the caseworker dashboard.

## Calibration false positives

None.

## Limitations

- 20 outputs from 10 paired scenarios, not 20 independent cases.
- Only 5 labeled failures in calibration.
- AI-assisted labels reviewed by Lily; not independent legal adjudication.
- The judge uses the same model family as the assessed agent.
- Calibration performance is not held-out validation.
- Prompt examples reuse calibration cases named above.
- This comparison does not promise improvement and does not relabel disagreements to fit the judge.
- Validation examples were not used to design or refine this prompt.
- This judge is not wired into the application or approval controls.
