# AeroSafe console UI specification

## Product intent

The console is a local prototype for exploring maintenance defect text. It helps a user see the
keyword triage result, the pipeline's execution status, and the limits of each demo feature. It
does not issue a maintenance instruction, approve an aircraft for service, or replace operator
procedures.

## Global shell

- The persistent sidebar navigates to Cockpit, Agent Mesh, Knowledge Graph, Source Library,
  RUL Estimator, Audit Chain, and Evaluation. The active destination is visually and semantically identified.
- The top bar shows the current view, a clear “aircraft context not connected” state, detected
  language, and API health. It must not name an aircraft until a profile is entered and sourced.
- The global footer and prototype badges remain visible as context that displayed data is not
  approved maintenance information.
- The desktop palette uses midnight blue for navigation, white elevated cards for work areas,
  cool gray blue page surfaces, teal for active/healthy states, amber for review or unavailable
  states, and red for rejected or error states.
- Cards, workflow stages, and aircraft map markers use restrained layered depth and short hover
  lift/tilt interactions on pointer devices. Touch layouts remain static and reduced-motion settings
  disable these transitions.

## Screens and interactions

### Triage

- Provide typed text and local Whisper audio input modes. Empty text and empty audio submission
  show an inline error. Invalid or unsupported audio returns a readable error.
- Analyze creates a case, shows its original description, creation time, ATA keyword ranking,
  matched keyword signals, language/entity tags, evidence count,
  result status, and agent trace. The result must state when the system abstains.
- Evidence, Triage signals, ADs, RUL, Graph, and Agent trace tabs show data for the active case where available.
  Empty data is explained as unavailable; it must not be presented as a negative finding.
- The case board lists recent durable local cases with ATA, status, and timestamp. Search matches
  case ID, description, keyword tags, ranked ATA chapters, and user-entered aircraft/component
  context; status filters and paging are available. Selecting a case reloads its result. On page
  startup, the newest case is restored.
  SQLite preserves history through service restarts.
- A selected case can be exported as versioned JSON with its analysis payload and explicit
  prototype limitations. Export is a user-initiated local browser download; it is not an approved
  maintenance record.
- “Revise as new case” copies the selected report and any user-entered aircraft/component context
  into the input form. Analyzing it creates a new case and audit trail; it never overwrites the
  original.
- An optional expandable form accepts aircraft model, aircraft serial/MSN, component, part number,
  and component serial. A nearby note says these details are user-entered and unverified and do not
  affect triage or directive applicability. Results and case rows show supplied details as
  unverified; blank context has an explicit empty state.
- Reviewer controls appear only for a case in `awaiting_approval`; decisions are logged once.
- AI investigation is a separate unchecked opt-in. Its label says the defect text and matching local
  source excerpts are sent to OpenAI. The displayed credential state means “configured,” not
  provider-validated; failed runs preserve the local baseline and show a clear error.

### Source Library

- Accept only PDF, TXT, and Markdown, with 8 MiB, 120-page PDF, and 250,000 extracted-character limits.
- Display filename, file hash, page/character/chunk counts, and local creation time. Users can remove
  an uploaded file and its searchable chunks.
- Explain that search is lexical and local, OCR/vector search are unavailable, and AI mode sends
  matching excerpts externally only after explicit opt-in.

### Agent map

- Describe the actual workflow: local keyword triage, optional Investigation Lead, read-only Evidence
  Scout, exact quote identity check, and a separate reviewer. Do not advertise planned agents as live.

### Knowledge graph

- Allow choosing any stored case, including cases beyond the first 100, and render one case node,
  its ranked ATA nodes, and all of its deduplicated keyword entity tags.
- Mouse click, Enter, and Space select a node and update its label, explanation, and source.
- The legend distinguishes case, ATA ranking, and keyword tag nodes. The page states that source
  reports, directives, configuration, and external graph data are not connected.
- A missing case state offers a direct instruction to create a case first.

### Parts map

- Show the illustrative aircraft outline and selectable ATA chapter markers/list.
- Selecting a chapter highlights the marker and shows its keyword rank for the active case.
- The view explicitly states that the outline is not an aircraft configuration or maintenance
  record. Unsupported ATA chapters must not appear to have a real component map.

### Directives

- Show an unevaluated state until directive data and an applicability rules engine are connected.
- Explain that no result does not mean no applicable directive exists.

### RUL

- Accept a CSV upload or the one-click sample file using the documented `cycle,health_index`
  schema. The threshold is editable and validated.
- On success, show the observed series, linear projection, threshold, estimated remaining cycles,
  and calculation context. On invalid input or non-declining data, show an inline explanation.
- Keep the demo-estimator label and maintenance-decision warning adjacent to the estimate.
- This standalone explorer is not currently attached to a case or an aircraft sensor feed.

### Audit log

- Load records only after verifying the hash chain. Show a visible intact/corrupt result and the
  verify action. If verification fails, do not render records as trusted.
- On narrow screens, preserve access to record identity and action while allowing the hash columns
  to scroll or collapse.

### Evaluation

- Load and refresh the synthetic ATA smoke-set metrics from `/evaluation` and display sample count,
  accuracy, macro-F1, and per-class precision/recall/F1.
- Keep the synthetic/non-operational warning next to the metrics and allow downloading the exact
  input CSV used to produce them.
- Show only measured metrics as score tiles. Explain prerequisites for pending metrics once in a
  compact section rather than rendering empty-value tiles.
- Keep retrieval recall, validated RUL RMSE, unsupported-claim rate, and voice WER unavailable
  until suitable labeled data and corresponding implementations exist.

## Layout, accessibility, and states

- At wide widths, the sidebar remains persistent and multi-column work areas use a main panel plus
  a supporting panel. At tablet widths, panels stack. At phone widths, navigation and wide graphs
  may scroll inside their own regions; the full page must not lose access to controls horizontally.
- Use semantic headings, labels, live error/status messages, visible keyboard focus, and accessible
  names for interactive SVG nodes. Tab-like controls expose `aria-selected` state.
- Loading, empty, success, unavailable, and error states are styled distinctly. Do not use color as
  the only status signal; pair color with readable text.
- Motion is limited to short hover/focus transitions and must not gate access to content.

## Acceptance checklist

1. All eight sidebar destinations open directly by hash and update the active navigation state.
2. Triage can create a case, search/filter/paginate case history, and restore a case after restart.
3. The graph screen can select and inspect any stored case's local triage nodes.
4. RUL can process the included sample CSV and rejects malformed or rising-trend data with a
   readable error.
5. Evaluation renders the same metrics returned by the API and identifies its synthetic fixture.
6. Desktop, tablet, and phone layouts retain readable labels, working controls, and visible focus.
7. No screen implies access to operator records, approved aircraft configuration, regulatory
   applicability, validated prognostics, or evidence retrieval that is not implemented.
