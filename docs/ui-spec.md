# AeroSafe console UI specification

## Product intent

The console is a local prototype for exploring maintenance defect text. It helps a user see the
keyword triage result, the pipeline's execution status, and the limits of each demo feature. It
does not issue a maintenance instruction, approve an aircraft for service, or replace operator
procedures.

## Global shell

- The persistent sidebar navigates to Triage, Agent map, Knowledge graph, Parts map, Directives,
  RUL, Audit log, and Evaluation. The active destination is visually and semantically identified.
- The top bar shows the current view, demo aircraft label, EN/FR language mode, and API health.
- The global footer and prototype badges remain visible as context that displayed data is not
  approved maintenance information.
- The desktop palette uses midnight blue for navigation, white elevated cards for work areas,
  cool gray blue page surfaces, teal for active/healthy states, amber for review or unavailable
  states, and red for rejected or error states.

## Screens and interactions

### Triage

- Provide typed text and local Whisper audio input modes. Empty text and empty audio submission
  show an inline error. Invalid or unsupported audio returns a readable error.
- Analyze creates a case, shows the ATA keyword ranking, language/entity tags, evidence count,
  result status, and agent trace. The result must state when the system abstains.
- Evidence, ADs, RUL, Graph, and Agent trace tabs show data for the active case where available.
  Empty data is explained as unavailable; it must not be presented as a negative finding.
- The case board lists recent in-memory cases and their ATA/status summary. Selecting a case
  reloads its result. On page startup, the most recent in-memory case is restored automatically.
  Case history resets when the API process restarts.
- Reviewer controls appear only for a case in `awaiting_approval`; decisions are logged once.

### Agent map

- Show all configured stages in pipeline order: Whisper, Triage, Retrieval, Compliance, Predictive
  maintenance, Draft, Verifier, and Human approval.
- Visually distinguish implemented, optional, stub, and held stages. Labels describe implementation
  state; connected graph nodes must not imply a production implementation.

### Knowledge graph

- Allow choosing an in-memory case and render one case node, its ranked ATA nodes, and its
  deduplicated keyword entity tags.
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
2. Triage can create a case and the graph screen can select and inspect that case's nodes.
3. RUL can process the included sample CSV and rejects malformed or rising-trend data with a
   readable error.
4. Evaluation renders the same metrics returned by the API and identifies its synthetic fixture.
5. Desktop, tablet, and phone layouts retain readable labels, working controls, and visible focus.
6. No screen implies access to operator records, approved aircraft configuration, regulatory
   applicability, validated prognostics, or evidence retrieval that is not implemented.
