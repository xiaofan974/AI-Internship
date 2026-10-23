# Week 4 offline deployment bundle

Reviewable copies of the gitignored artifacts that the Assessment corpus does not already track.

`MANIFEST.json` lists every file the Streamlit app needs for:

- Assessment: the three pinned classification-subset record files
- Week 4 evaluations: fictional scenarios, frozen traces, saved assertion results, judge payloads, and saved judge predictions

Each bundled copy is byte-identical to the original under `data/local/`. SHA-256 values are recorded in the manifest. The originals are not rewritten.

Excluded on purpose: credentials, local databases, virtualenvs, live/smoke traces, Langfuse import ledgers, and extra judge working files that the Streamlit view does not read.
