# ExampleCo synthetic policy corpus

These files are **synthetic demonstration data** for RAG testing. They describe a fictional company named **ExampleCo**. They are **not** official Northwind documents and **not** Maven course materials.

Do not re-ingest `northwind-handbook`. That Northwind snippet stays in Pinecone as a separate document.

Splitter used for the estimates below: `RecursiveCharacterTextSplitter`, chunk size 800, overlap 100 (local check only; no OpenAI or Pinecone calls).

## Inventory

| File | `document_id` | `source` | Characters | Expected chunks | Expected vector IDs |
| --- | --- | --- | --- | --- | --- |
| `remote_work.txt` | `exampleco-remote-work` | `exampleco-synthetic-policies` | 1453 | 2 | `exampleco-remote-work:0`, `exampleco-remote-work:1` |
| `annual_leave.txt` | `exampleco-annual-leave` | `exampleco-synthetic-policies` | 1388 | 2 | `exampleco-annual-leave:0`, `exampleco-annual-leave:1` |
| `expenses.txt` | `exampleco-expenses` | `exampleco-synthetic-policies` | 1478 | 3 | `exampleco-expenses:0`, `exampleco-expenses:1`, `exampleco-expenses:2` |
| `it_equipment.txt` | `exampleco-it-equipment` | `exampleco-synthetic-policies` | 1416 | 3 | `exampleco-it-equipment:0`, `exampleco-it-equipment:1`, `exampleco-it-equipment:2` |
| `information_security.txt` | `exampleco-information-security` | `exampleco-synthetic-policies` | 1464 | 3 | `exampleco-information-security:0`, `exampleco-information-security:1`, `exampleco-information-security:2` |

Total if ingested as five separate `/ingest` requests: **13 chunks**, **5 embedding calls**. None of these IDs collide with `northwind-handbook:0`.

Remote work and expenses/IT equipment overlap on home-office broadband and hardware. Retrieval should send laptop questions to IT equipment, not expenses or remote work.

## Factual test questions

1. **How many remote days can ExampleCo employees work, and which weekdays?**
   Expected: Tuesday and Thursday only; Monday, Wednesday, and Friday are office days.
   Source: `exampleco-remote-work`

2. **How many days of paid annual leave do full-time ExampleCo employees receive?**
   Expected: 22 days plus English public holidays observed by ExampleCo.
   Source: `exampleco-annual-leave`

3. **What expense amount can an ExampleCo line manager approve on their own?**
   Expected: up to £250 in a single submission.
   Source: `exampleco-expenses`

4. **Who approves an ExampleCo catalogue laptop that costs £500?**
   Expected: the Head of IT (items £400.01–£1,200). A line manager’s £250 expense approval does not authorise hardware.
   Source: `exampleco-it-equipment` (not `exampleco-expenses` or `exampleco-remote-work`)

5. **When is unused ExampleCo production access revoked?**
   Expected: after 60 days unused.
   Source: `exampleco-information-security`

## Unanswerable questions (should refuse)

1. **Can ExampleCo employees bring dogs to the office?**
   No pet policy exists in this corpus.

2. **Does ExampleCo offer a paid sabbatical after five years?**
   No sabbatical policy exists in this corpus.

The expected refusal text from `/ask` is: `I don't have enough information to answer that.`
