# Reconstruction approach — user & agent activity parser

Dataset: PARSER_DEVELOPMENT_MINIMAL_A03 (43 runs; device snapshots, provider
transcripts, app export). This document states exactly how activity is
reconstructed and what is *not* claimed.

## 1. Sources and what each one is

| Source | What it records | Role in reconstruction |
|---|---|---|
| `evidence/android/<RUN>/messages.json` + `threads.json` | Device-side conversation: USER/AGENT messages, decrypted, with stable `message.id`, per-thread `seq`, `timestamp_ms`, attachments/widgets/presentations | Primary record of **what was said**, by whom, when |
| `evidence/system_files/agents/agent-*/sessions/*.jsonl` | Provider-side agent trace: thinking, tool calls + outputs, commentary, assistant messages, developer notices | Primary record of **what the agent did** to produce replies |
| `evidence/app_export/manifest.json` | Export turns with `turn_id`, role, content, `created_at` | Corroborating record; joins to android |
| `run_index.csv` | Run windows, action sets, pre/post state IDs | Scoping: which run a record belongs to |
| `ground_truth/<RUN>/oracle.jsonl` | Operator ground truth | **Never loaded by the parser** (kept for later evaluation) |

## 2. Reconstruction sequence (in order)

**Step 1 — Load and normalize each source independently.**
Android messages are ordered by `(timestamp_ms, seq)`. Transcript records are
ordered by `seq`. `rowid` is never used for ordering (dataset requirement).

**Step 2 — ID-first joins (before any timestamp reasoning).**
- `android message.id == manifest turn_id`: verified 145/150 overlap. This is
  the strongest cross-source key.
- `call_id` pairs `function_call` ↔ `function_call_output` inside a
  transcript, regardless of position.
- `session_id` groups records *within one source only*. Android session IDs
  (device threads, e.g. `fd9ccdfb-…`, plus the literal `primary_session_id`)
  and transcript session IDs (provider sessions, e.g. `6ca496e2-…`) are
  **different namespaces** and are never joined to each other.

**Step 3 — Transcript ↔ android linkage.**
Transcript messages carry no IDs, so linkage is by **normalized exact text
match** of message content (whitespace-collapsed). Each matching candidate is
retained and records a confidence label (`high-exact-text-match`); repeated
identical text can therefore produce multiple candidates. Unmatched turns are
kept, not dropped.

**Step 4 — Turn grouping (heuristic, labeled as such).**
Within a transcript, a user message owns the actions after it (by `seq`) up
to the next user message. The transcript format records no turn/request ID,
so this is positional inference, not a recorded relationship. Every output
says so.

**Step 5 — Approvals.**
Only explicit `userConfirmationRequired` / `userConfirmationStatus` records
in tool outputs are reported as approvals (observed: `approved`/`declined`).
No approval is ever inferred from a missing popup, from thinking content, or
from delegation. No `always-allow` / standing-grant record exists in the
transcripts.

## 3. What is deliberately not done

- **Thinking content is never reproduced** — only the presence/count of
  thinking blocks (dataset policy).
- **Assistant claims are not treated as external effects** — a reply saying
  "email sent" is recorded as a claim, not as proof of sending (the package
  notes it cannot independently verify server effects).
- **No rowid chronology**; no timestamp-only joins where IDs exist.
- **Unknown fields preserved** — every record keeps its raw source and any
  unrecognized fields; unrecognized top-level records are surfaced, not
  dropped.
- **Every reconstructed fact carries a locator** (file + line number and/or
  rowid) so any claim can be traced back to the exact source bytes.

## 4. Known limitations of the reconstruction

1. Turn grouping is positional; interleaved/concurrent requests would be
   misattributed (not observed in this data: `seq` is strictly increasing
   and agrees with `created_at` in all checked sessions).
2. Compaction deletes records: one session is missing `seq 80`
   (`compaction_count=1`); the trace has holes, and the parser reports
   "surviving events," not complete events.
3. `compaction_checkpoint` records sit outside `seq` numbering.
4. Transcript↔android links depend on text matching; paraphrased or
   truncated content will not link (kept as unlinked, not forced).
5. Provider sessions can span multiple runs; android snapshots are
   cumulative POST states, not per-run isolates — a message in run N's
   snapshot may belong to an earlier run's activity.
6. Development on these known runs is unblinded; this is a development
   parser, not a blinded evaluation.
