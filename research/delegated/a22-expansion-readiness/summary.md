# Conditional 24-scene expansion: input readiness

**Read-only feasibility audit. Expansion is not implemented or preflighted.**
No generator, seed function, solver, test, SSH client, private configuration or
integrity check was executed. Only public source/JSON metadata and file presence
were inspected. No core, configuration, preparation, transport or gate code was
edited. The parent's screening decision remains authoritative.

## Frozen roster and original tags

`configs/a22.json` contains **24 unique IDs**, split **9 development / 3
calibration / 12 evaluation**, comprising 15 existing objects and exactly nine
new objects. All 15 selected existing `common_data.npz` files are present under
`Gaussian/A17/CLOSURE_R1/inputs/object_ID/`. Four already prepared A22 scenes are
2001, 2003, 2014, 2009; the other 11 existing objects need selected-member import.
Existing screening source choices must remain intact: 2001/2014 use EXCHANGE_R1;
2003/2009 use CLOSURE_R1.

| Original family tag | Development | Calibration | Evaluation | Total |
| --- | --- | --- | --- | --- |
| gaussian | 2001, 2003 | — | 2002, 2004 | 4 |
| contact | 2005 | 2007 | 2006, 2008 | 4 |
| asymmetric | 2013, 2014, 2016 | **2020 new** | **2021–2024 new** | 8 |
| shell | 2009, 2010, 2011 | 2012 | **2031–2034 new** | 8 |

Source evidence: original `CLOSURE_R1/inputs/scenes.json` and A16 `scenes.py`
declare four distinct family tags. A secondary Gaussian/contact superfamily
would give three groups of eight, each 3/1/4; it must be explicitly declared
without replacing either original tag. The current evaluator writes
`scene.family` unchanged and has no secondary-group field. Original IDs were
historically exposed A17 validation objects, so the four old evaluation IDs are
not a new blind holdout. Original 2015 is outside the frozen roster.

## Seed blocker and nine-scene cap

| New ID | Family | A22 split | Registered seed | Current recipe j |
| --- | --- | --- | --- | --- |
| 2020 | asymmetric | calibration | 202610072020 | 10 |
| 2021 | asymmetric | evaluation | 202610072021 | 11 |
| 2022 | asymmetric | evaluation | 202610072022 | 12 |
| 2023 | asymmetric | evaluation | 202610072023 | 13 |
| 2024 | asymmetric | evaluation | 202610072024 | 14 |
| 2031 | shell | evaluation | 202610072031 | 10 |
| 2032 | shell | evaluation | 202610072032 | 11 |
| 2033 | shell | evaluation | 202610072033 | 12 |
| 2034 | shell | evaluation | 202610072034 | 13 |

All nine stored values equal **202610070000 + ID**. However,
`assets.generate_new_scene_recipe` calls the unchanged legacy
`make_scene(family,j,split,object_id,representation)`. That function selects its
geometry RNG through `seed('geometry',split,family,j)` from the original A16
seed protocol; **the registered A22 integer is currently metadata only**.
This is a conditional expansion blocker. No new scene may be generated until
the actual seed policy is fixed, frozen and separately preflighted after a
positive screening decision. This audit neither changed nor called that policy.

`assets.new_scene_recipes` checks the exact nine ID/family records but does not
enforce the registered-seed formula as a runtime contract. The future generation
entrypoint must additionally enforce that formula and meter every new physical
label through the existing offline guard. `budget.NEW_TEACHER_LABEL_CAP=9` is
separate from the total `DATA_GENERATION_F_CAP=192`.

## Exact interface gaps and reusable inputs

| Existing module / entrypoint | Reusable part / missing expansion interface |
| --- | --- |
| `assets._source`, `load_online_scene`, `load_offline_scene` | Non-screening IDs require both explicit flags and a declared `scene_sources` record. Public geometry for the 11 old additions can come from original `CLOSURE_R1/inputs/scenes.json`; current portable config declares only four sources. |
| `assets.new_scene_recipes`, `generate_new_scene_recipe` | Dormant continuous-scene descriptors only; no mesh, material arrays, measured data, artifact writes or ledger are produced. Requires the seed fix and an explicit generation preflight. |
| `prepare.prepare_screening` | Selected online members are `points/data0/init`. The exact four-ID check and four-ID loop prevent expansion; a separate bounded 24-ID preparation/manifest path is needed, preserving the original config and screening records. |
| `offline_assets.prepare_offline_screening`, `load_evaluation_truth` | Truth-only NPZs and offline guards are reusable patterns. Both ID/manifest contracts are rigidly four-scene; a separately frozen expansion contract/loader is required before `pilot` can read any added object center. |
| `tools/a22_evaluation_inputs.py` | Explicit private transport is available, but its allowlist is exactly four truth NPZs plus manifest. A separate exact expansion evaluator-input allowlist is required; the existing online deployment whitelist remains unchanged. |
| `tools/a22_remote_jobs.deployment_members` | Already includes public A22 code/config and selected files under `data/a22/online`; it excludes evaluator data. Expanded online assets can use that existing namespace after preparation. |
| `cli.main` / `evaluate.run_stage_a(..., screening=False)` | `pilot` requires positive `SCREENING_DECISION.json`, flattens the frozen 24-ID split, and skips completed screening IDs. It does not prepare missing inputs or generate scenes automatically. |
| `online.build_anchor`, `build_opm`; `evaluate.finite_label` | Existing online known-background anchor and fixed patch32 OPM remain reusable. Labels use actual object material as the offline perturbation center. No mathematics or gate changes are needed for this inventory task. |

Original generation dependencies are
`Gaussian/A17/EXCHANGE_R1/vendor/Gaussian/A16/CURRENT_SELECTION_R1/code/scenes.py`
(`make_scene`, `material`, `acquisition`), its vendored `a10_common.grid`, and the
unchanged DDA kernel, also available as `implementation/vendor/a17/a9_engine.py`.
`run_reference.py:run` lines 73–92 document the original protocol: n=14 truth
material and full forward produce noiseless six-source/128-channel `data0`;
n=12 points, material `truth`, and known-background `init` are saved separately.
That complete reference runner also invokes old tangent/gauge machinery and a
GN trajectory, so it is not a bounded A22 data-generation entrypoint. Only the
minimal protocol pieces should be used by a future metered generator.

New assets need public n12 mesh/acquisition metadata and noiseless n14 data for
the online bundle; n12 actual material belongs only to the evaluator bundle.
Preserve background 0.1+0.04i, k=2, edge=1.5 and six-source/64-receiver geometry.
Do not reuse original `scenes.noise`, whose normalization depends on object data;
A22 noise and whitening remain tied to the known-background prediction.

## Conditional sequence and accounting preflight

After a positive parent screening decision: freeze original tags plus any
secondary grouping; resolve and preflight the nine actual geometry seeds;
import the 11 old selected payloads; generate at most nine new physical labels
under the existing caps; prepare and separately deploy online/evaluator bundles;
then run the existing `pilot` entrypoint. The source/loader/transport gaps above
must be resolved before that entrypoint is called.

With all four screening scenes complete, expansion adds 20 × 3 directions × 2
amplitudes = **120 finite-label forwards**. Screening adds 32, and nine new
noiseless observations require at least nine more generation forwards. Thus the
planning minimum is **161 + already-paid health/retry generation forwards**.
Actual merged ledger counts and the independent feature/direction GPU limits
must be preflighted; nominal arithmetic does not authorize a cap extension or
guarantee completion. No scientific gate was adjudicated by this audit.
