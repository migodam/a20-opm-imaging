# A22 online/assets implementation handoff

Status: CODE_WRITTEN_NOT_EXECUTED. No tests, model imports, physics jobs,
training, integrity hash checks, private connection reads, or remote calls.
The parent owns metered validation and all scientific interpretation.

## Owned files

- `src/a22/assets.py`
- `src/a22/online.py`

No A20/A21/vendor source or configuration was modified. The implementation
imports the immutable backend interfaces already copied into this package.

## Callable interfaces

```text
load_online_scene(scene_id, config=None, book=None,
                  *, stage_a_signal=False, explicit_authorization=False)
    -> OnlineScene(scene_id, family, problem, geometry, provenance)

load_offline_scene(same arguments)
    -> OfflineScene(scene_id, truth, provenance)

fixed_patch_chart(points, volume)
    -> (MaterialChart, provenance)

acquisition_geometry(geometry)
    -> (dirs, pols, receivers, obs_basis)

build_anchor(scene, config=None, book=None, *, device='cpu')
    -> Anchor(adapter, state, chi, provenance, cache_key, cost)
    # book is mandatory before physics; omitted book raises.

build_opm(anchor, config=None)
    -> OPMModel(anchor, view, feedback, hierarchy, projection, basis,
                MW, PMW, AW, provenance, cost)

material_features(opm, W=None)
    -> MaterialFeatures(MW, PMW, AW, W, signatures, provenance, cost)
    # Also supports feature['MW'], feature['PMW'], feature['AW'].

new_scene_recipes(config=None)
    -> immutable-protocol descriptor rows, with NOT_GENERATED status

generate_new_scene_recipe(scene_id, config=None,
                          *, stage_a_signal=False, explicit_authorization=False)
    -> offline continuous-scene descriptor; no data/physics generation
```

## Layout and provenance

Screening defaults are 2001 and 2014 from A17 EXCHANGE_R1, and 2003 and
2009 from A17 CLOSURE_R1. The online reader selects only points/data0/init.
It never reads truth, held_truth, old objective scale, saved Gaussian chart,
or the component-bearing scene_json. Acquisition constants are frozen from
the original input scene manifests. Original init must equal the declared
generative background 0.1+0.04i; a disagreement raises.

The fixed material chart has sixteen real spatial basis columns: eight
octant indicators and eight centered local x-sign detail columns. H.T H=I
and Q=H/sqrt(volume), so volume Q.T Q=I. The resulting material dimension is
32, with real coefficients before imaginary coefficients. Coarse coordinate
indices are [0..7,16..23]. No data/truth fitting or old material Q is used.

The anchor is one full forward prediction at the declared uniform background.
sigma_complex_reference is 0.01 times the RMS of that known-background
prediction; it never uses observation/truth RMS. Proper complex noise has
real/imag variance sigma_complex_reference^2/2. Whitening is sqrt(2)/sigma.

The OPM builder directly constructs retained U8, O4/P4/M4 and degree1 with
rank cap32. Measurement probes are explicit fixed RNG probes, so the old
residual-replacement default cannot make Q measurement dependent. All six
source columns precede seed compression. No automatic empty-U, Petrov or
full-solver fallback exists in this builder; an invalid core propagates.

The complete current basis includes U, preserving the retained direct path.
MW and PMW have shape (6, actual_current_rank, 32); AW is real packed
(1536,32) for the original four screening geometries. Data ordering is each
source's real channels followed by its imaginary channels. Real source
stacking and whitening happen after the complex factor actions.

Material feature evaluation uses compressed_B, the already-paid projected
S image and reduced LU actions. No full J/H/oracle is requested. Exact cache
identity includes parent probe namespace, anchored material, geometry,
material chart, whitening and configuration; no hash is computed.

## Deferred work and limitations

Validation is NOT_RUN. The parent must test geometry equivalence, fixed-patch
metrics, source packing, known-background noise convention, adjoints, retained
direct-path equivalence, cache invalidation and failure accounting before use.

The existing material QP still needs the parent's restricted-coordinate
wrapper when W is not the direct paired patch chart. A general real W mixing
real/imaginary coordinates cannot be represented by the old paired-Q layout.

New IDs2020..2024 (asymmetric) and2031..2034 (shell) remain descriptors only.
They require explicit Stage A signal and generation authorization. Deferred
descriptor generation retains the original scenes.py seed function unchanged;
its SHA-based algorithmic RNG is not a new integrity check. No generator or
seed function ran in this worker. No new observations or truth arrays exist.

Additional existing scenes require explicit public geometry/source records
in config.scene_sources, plus Stage A authorization; defaults cover only the
four screening assets. No held-out assets were loaded.

Runtime access barriers are API capability restrictions, not a Python process
security sandbox. Online builders receive a restricted view without teacher,
full-J/H, reference-step or full-solution callable access.

CPU receipt: `CPU_RECEIPT.json`. Unmetered read/patch tool work is disclosed
as a conservative allowance rather than mislabeled as measured CPU.
