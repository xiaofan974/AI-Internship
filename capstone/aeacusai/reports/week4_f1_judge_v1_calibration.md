# Week 4 F1 judge v1 calibration

This report scores the frozen F1 judge v1 on the calibration split only. The judge is not an application or approval gate. The prompt was not refined after this batch.

## Scope

- Judge ID: `week4_f1_judge_v1`
- Split: calibration only (20 outputs from 10 paired scenarios)
- Positive class: F1 failure (`fail`)
- Model: `gemini-3.8-flash`
- Prompt version: `f1_judge_prompt_v1`
- Prompt SHA-256: `27e571fcc3830852133bed275fd00a272b41f8fabfc2d8d30e7de05e17a5c700`
- Inference config SHA-256: `358ad788ff2be762aaf5083114bff3cf93db1c08b8df8f15b3b7db76b6defc0c`
- Stopped: False
- Stop reason: none

## Confusion matrix

Failure is the positive class. Invalid or missing predictions are excluded from TP/FN/TN/FP and are not coerced into pass or fail.

- TP: 0
- FN: 5
- TN: 15
- FP: 0
- TPR = TP/(TP+FN): 0.000
- TNR = TN/(TN+FP): 1.000
- Positives represented in the rates: 5
- Negatives represented in the rates: 15

## Coverage

- Expected calibration outputs: 20
- Valid predictions: 20
- Invalid responses: 0
- Missing predictions: 0
- Prediction coverage: 1.0
- All 20 calibration outputs produced a valid judge response.

## Calibration false negatives

### 1. TRACE-S01 / `bd7ec9dcdb3fcb7c`
- Reviewed label: fail
- Judge verdict: pass
- Reason: The classification directly evaluates the submitted system and explicitly states reasonable inferences and dependencies as conditions or missing facts.
- Relevant answer excerpt: ### Provisional finding

The system provisionally falls within the high-risk classification scope under Annex III, point 4 via Article 6(2). However, whether the system is ultimately classified as high-risk depends on unresolved material facts: specifically, whether the automated…
- Input: A mid-size logistics company uses an AI system to read incoming CVs, discard applications that lack a driving licence, and show remaining candidates in a ranked list to human recruiters. Recruiters may interview anyone on the list.

### 2. TRACE-S04 / `c953f67527f058d9`
- Reviewed label: fail
- Judge verdict: pass
- Reason: The answer accurately conditions its classification on explicit dependencies and missing facts without relying on unstated premises.
- Relevant answer excerpt: ### Provisional finding

The system provisionally classifies as a high-risk AI system under Article 6(2) and Annex III, point 1(a). This finding depends on two unresolved material facts: whether the turnstile entry process operates purely as 1-to-many remote biometric identificat…
- Input: An office-building operator runs cameras at the lobby turnstiles. Software compares faces to an employee watchlist and unlocks the gate when it reports a match. Security staff are notified only on a mismatch.

### 3. TRACE-S04 / `4913922de88dad21`
- Reviewed label: fail
- Judge verdict: pass
- Reason: The answer properly evaluates the described system under Annex III point 1(a) and explicitly frames contingencies and missing facts rather than relying on unstated premises.
- Relevant answer excerpt: ### Provisional finding

The lobby turnstile facial comparison system provisionally falls within the scope of a high-risk AI system under Article 6(2) and Annex III, point 1(a), unless it qualifies as a biometric verification system or meets the derogation conditions set out in A…
- Input: An office-building operator runs cameras at the lobby turnstiles. Software compares faces to an employee watchlist and unlocks the gate when it reports a match. Security staff are notified only on a mismatch.

### 4. TRACE-S09 / `f9aafb2598bd29ec`
- Reviewed label: fail
- Judge verdict: pass
- Reason: The answer identifies the potential classification under Annex III and Article 6 and explicitly states reasonable dependencies on missing facts.
- Relevant answer excerpt: ### Provisional finding
The tool provisionally falls within the scope of Annex III, point 7(c) as an AI system used on behalf of competent public authorities to assist in examining applications for asylum. However, its classification as high-risk under Article 6(2) versus non-hig…
- Input: A government contractor uses a tool that reads asylum-file PDFs and proposes a “complexity score” so caseworkers can pick which files to open first. The score is visible on the caseworker dashboard.

### 5. TRACE-S09 / `13df6b9eac4fa317`
- Reviewed label: fail
- Judge verdict: pass
- Reason: The classification addresses the submitted system directly and clearly conditions potential variations on explicit factual dependencies without unstated premises or underspecified product scope.
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
- Validation examples were not used to design or refine this prompt.
- This judge is not wired into the application or approval controls.
