---
name: source_quality
track: team
kind: local_classifier
requires_env: []
inputs: [url]
outputs: [url, domain, source_type, confidence, reason, scope_note]
side_effect: false
timeout_seconds: 0
---
# source_quality

Classifies the type of a URL or domain as `official`, `academic`, `news`,
`social`, or `unknown`.

The tool is pure local logic. It does not call APIs, read secrets, write files,
or change external state. It is not a fact-checker and must not be used to claim
that a source is absolutely trustworthy.
