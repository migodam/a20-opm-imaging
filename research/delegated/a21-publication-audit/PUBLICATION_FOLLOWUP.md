# A21 publication follow-up: operational provenance and public entry

Reviewed all 80 prior file/category locations across 80 files, plus the remote/release helper sources. Values are not reproduced. Ordinary source/project/runtime paths are classified separately from connection metadata. No original evidence or copied public file was edited.

Classifications: {"ORDINARY_SOURCE_PROJECT_RUNTIME_PATH": 1298}.
Connection/privacy candidates requiring parent classification before copied-public redaction: 0. Exact safe locations appear below and in PUBLICATION_FOLLOWUP_CLASSIFICATION.json. Preserve local immutable evidence; redact only copied PUBLIC payload if the identified value is an actual live connection target, key path, username/email or secret.

| File | Line | Field | Class |
|---|---:|---|---|
| none | - | - | No live connection/secret candidate detected |

All ordinary absolute-path locations are retained with field/line/class only in the JSON table. Large JSONL ledgers have one original-line location per candidate; no original values enter either report.

## New public root entries

- `a21-publication/START_HERE.md`: {"NOT_RUN_boundary_present": true, "existing_A20_retained": true, "exists": true, "offline_asset_split_explicit": true, "release_or_asset_link_present": true}
- `a21-publication/README.md`: {"NOT_RUN_boundary_present": true, "existing_A20_retained": true, "exists": true, "offline_asset_split_explicit": true, "release_or_asset_link_present": false}

## Original-root release-asset helper

{
  "file": "tools/a21_release_assets.py",
  "functions": [
    "build"
  ],
  "offline_label_present": true,
  "cache_diagnostics_named": true,
  "credential_candidate_count": 0,
  "physics_import_present": false,
  "subprocess_use": "git metadata/status/ls-files reads only; no upload or physics calls",
  "physics_prohibition_text_present": true,
  "physics_execution_calls_present": false
}

Checks above are source/wording inspection only. The helper was not executed, no assets were built/uploaded, and no scientific/physics/QP/tests were run. The parent retains final publication and scientific authority.

Manual source review confirms the helper's subprocesses read git metadata only. The Maxwell/QP words occur in the asset's prohibition/provenance marker, not execution commands. The helper selects exactly 5 cache NPZ, 5 cache JSON and 35 diagnostic NPZ for the separate offline asset; it rejects raw arrays from the main Git bundle, symlinks and replacing an existing release asset. The README reaches the release links through START_HERE and REPRODUCE, so its lack of a direct release URL is not a broken offline split.

For JSON documents, the complete field path in the classification table is the authoritative location; repeated-key line references may point at the first matching key. Python/Markdown source and JSONL line references are exact. All 80 original file/category locations classified as ordinary source/project/runtime paths; no actual live SSH target, private-key path, Tailscale IP, username/email or environment-secret value was detected in that scope.
