"""A20-R1 paired seed policies; full-reference inputs are diagnostic only.

The physical actions and Schur/Arnoldi algebra remain in ``a20``.  Every
source is injected before compression.  A protected material block keeps
the complete resolved target span before filling its remaining allocation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
import numpy as np
from scipy import linalg as la

from a20.backend import BasisView, ForbiddenAccess, unpack
from a20.opm import (Hierarchy, Projection, ReducedJacobian, SchurFeedback,
                     SeedBundle, UnsafeCore, orth)


METHODS = {
    'FIXED-DEEP': {'O': 4, 'P': 4, 'M': 4, 'degree': 3},
    'WIDE-M': {'O': 4, 'P': 4, 'M': 16, 'degree': 1},
    'CHEAP-TASK': {'O': 4, 'P': 4, 'M': 4, 'degree': 3},
    'ORACLE-M': {'O': 4, 'P': 4, 'M': 4, 'degree': 3},
    'PROTECTED-ORACLE': {'O': 3, 'P': 3, 'M': 6, 'degree': 3},
    'PROTECTED-RANDOM': {'O': 3, 'P': 3, 'M': 6, 'degree': 3},
}
ORACLE_IDS = frozenset(('ORACLE-M', 'PROTECTED-ORACLE'))
EXTRA_STREAM = 1604


def _real_vector(value, size=None, name='material vector'):
    raw = np.asarray(value)
    if raw.ndim != 1 or np.iscomplexobj(raw):
        raise ValueError(name + ' must be a one-dimensional REAL vector')
    if size is not None and raw.shape != (size,):
        raise ValueError(name + ' dimension mismatch')
    out = np.array(raw, dtype=float, copy=True)
    if not np.all(np.isfinite(out)):
        raise ValueError(name + ' must be finite')
    return out


def _readonly(value):
    out = np.array(value, copy=True)
    out.flags.writeable = False
    return out


@dataclass(frozen=True, slots=True)
class AcceptedHistory:
    """A copied, alpha-scaled step from this parent's own accepted update.

    ``accepted_index`` is the number of accepted updates, starting at one.
    Rejected trials and saved frozen-reference directions are not history.
    The nonlinear driver is responsible for constructing this only on accept.
    """
    parent: int
    method: str
    accepted_index: int
    step: np.ndarray

    def __post_init__(self):
        if isinstance(self.parent, bool) or not isinstance(self.parent, (int, np.integer)):
            raise ValueError('AcceptedHistory parent must be an integer')
        if self.method not in METHODS:
            raise ValueError('AcceptedHistory unregistered method owner')
        if (isinstance(self.accepted_index, bool)
                or not isinstance(self.accepted_index, (int, np.integer))
                or self.accepted_index < 1):
            raise ValueError('AcceptedHistory requires accepted_index >= 1')
        object.__setattr__(self, 'step', _readonly(_real_vector(self.step, name='accepted step')))

    def validated_step(self, parent, method, size):
        if self.parent != parent or self.method != method:
            raise ForbiddenAccess('PREVIOUS_ACCEPTED_OWNER_MISMATCH')
        return _real_vector(self.step, size, 'accepted step')


@dataclass(frozen=True, slots=True)
class ProbeBank:
    parent: int
    material_dimension: int
    data_dimension: int
    rng_seed: tuple
    extra_rng_seed: tuple
    material_probes: np.ndarray
    measurement_probes: np.ndarray
    creation_cost: dict

    def __post_init__(self):
        material = np.asarray(self.material_probes)
        observation = np.asarray(self.measurement_probes)
        if (material.shape != (self.material_dimension, 16)
                or observation.shape != (self.data_dimension, 4)
                or np.iscomplexobj(material) or np.iscomplexobj(observation)
                or not np.all(np.isfinite(material)) or not np.all(np.isfinite(observation))):
            raise ValueError('ProbeBank requires finite real M16/O4 dimensions')
        object.__setattr__(self, 'material_probes', _readonly(self.material_probes))
        object.__setattr__(self, 'measurement_probes', _readonly(self.measurement_probes))

    @property
    def legacy_material_probes(self):
        return self.material_probes[:, :4].copy()


@dataclass
class PolicyModel:
    projection: Projection
    jacobian: ReducedJacobian
    seeds: SeedBundle
    schur: SchurFeedback
    info: dict
    _material_span: np.ndarray = field(default=None, repr=False)

    @property
    def material_span(self):
        return self._material_span.copy()

    @property
    def qM(self):
        return self.seeds.blocks['M']


def _sum_costs(*costs):
    out = {'counts': {}, 'exclusive_walls': {},
           'wall_seconds': 0., 'process_cpu_seconds': 0.}
    for cost in costs:
        for kind in ('counts', 'exclusive_walls'):
            for key, value in cost.get(kind, {}).items():
                out[kind][key] = out[kind].get(key, 0) + value
        for kind in ('wall_seconds', 'process_cpu_seconds'):
            out[kind] += cost.get(kind, 0.)
    return out


def _start_cost(book):
    book.synchronize()
    wall, cpu = time.perf_counter(), time.process_time()
    return book.snapshot(), wall, cpu


def _finish_cost(book, started):
    before, wall, cpu = started
    book.synchronize()
    cost = book.delta(before)
    cost.update(wall_seconds=time.perf_counter()-wall,
                process_cpu_seconds=time.process_time()-cpu)
    return cost


def _costed(book, components, label, action):
    started = _start_cost(book)
    try:
        return action()
    finally:
        components[label] = _finish_cost(book, started)


def _normalize_columns(value):
    # Exactly the legacy M4 normalization, including its zero handling.
    return value / np.maximum(la.norm(value, axis=0), 1e-300)


def paired_probe_bank(view, config):
    """Legacy M4 then O4 RNG draws; M12 extras use an independent fixed stream.

    O column zero is replaced by the current measured residual at build time.
    Drawing an M16-shaped array from the legacy generator would change both
    the M4 prefix (row-major draws) and O4, and is deliberately avoided.
    """
    started = _start_cost(view.book)
    seed = (int(config.get('master_seed', 20261005)), int(view._a.problem.parent_id))
    extra_seed = (*seed, EXTRA_STREAM)
    with view.book.span('r1_paired_probe_draws', r1_probe_banks=1):
        rng = np.random.default_rng(np.random.SeedSequence(seed))
        legacy = _normalize_columns(rng.normal(size=(view.chart.d, 4)))
        observation = rng.normal(size=(view.P*2*view.m, 4))
        extra_rng = np.random.default_rng(np.random.SeedSequence(extra_seed))
        extras = _normalize_columns(extra_rng.normal(size=(view.chart.d, 12)))
    bank = ProbeBank(seed[1], view.chart.d, view.P*2*view.m, seed, extra_seed,
                     np.column_stack((legacy, extras)), observation, {})
    bank.creation_cost.update(_finish_cost(view.book, started))
    return bank


def build_schur(adapter, x, state, residual, config):
    """Paid common receiver scaffold, reusable only at this exact state/material."""
    started = _start_cost(adapter.book)
    view = BasisView(adapter, x, state, residual)
    phase = adapter.book.phase if adapter.book.phase in ('legal_seed', 'offline_oracle_seed') else 'legal_seed'
    with adapter.book.scope(phase):
        material_version = adapter.version(x)
        U = view.receiver(config['retained_rank'])
        fallback = None
        try:
            schur = SchurFeedback(view, U, config)
        except UnsafeCore:
            fallback = 'unsafe_retained_to_empty_U'
            adapter.book.counts['empty_U_fallbacks'] += 1
            schur = SchurFeedback(view, np.empty((adapter.n, 0), complex), config)
    schur.r1_info = {'retained_fallback': fallback, 'creation_cost': {}}
    schur._r1_material_version = material_version
    schur.r1_info['creation_cost'].update(_finish_cost(adapter.book, started))
    return schur


def source_target_block(view, schur, target):
    """Return *all* source KB(target) columns, before any rank compression."""
    target = _real_vector(target, view.chart.d, 'target')
    injected = view.B(target[:, None])
    if injected.shape != (view.P, view.n, 1):
        raise ValueError('B target source dimension mismatch')
    return schur.K(injected[:, :, 0].T)


def _allocation(config, method):
    allocation = METHODS[method].copy()
    # R1's allocation is frozen.  Accept explicit mirrors in merged configs,
    # but never silently change a method using a different seed allocation.
    settings = config.get('r1_methods', config.get('methods', {}))
    if isinstance(settings, dict) and method in settings:
        entry = settings[method]
        for key in ('O', 'P', 'M', 'degree'):
            value = entry.get(key, entry.get('seed_rank_'+key, allocation[key]))
            if key != 'degree':
                value = entry.get('seed_ranks', {}).get(key, value)
            if value != allocation[key]:
                raise ValueError('Frozen R1 allocation mismatch: ' + method + ':' + key)
    return allocation


def _capture(block, basis):
    norm = float(la.norm(block))
    if norm == 0.:
        return {'norm': 0., 'capture': None, 'relative_residual': None, 'zero': True}
    residual = float(la.norm(block-basis@(basis.conj().T@block)))
    amplitude = float(la.norm(basis.conj().T@block)/norm)
    return {'norm': norm, 'capture': amplitude**2, 'amplitude_capture': amplitude,
            'relative_residual': residual/norm, 'zero': False}


def _real_span(probes, rtol, book):
    with book.span('r1_material_probe_span_SVD', r1_material_probe_span_SVD=1):
        u, sv, _ = la.svd(probes, full_matrices=False)
        threshold = rtol*max(float(la.norm(probes)), float(sv[0]) if len(sv) else 0.)
        return u[:, sv > threshold]


def build_model(adapter, x, state, residual, ell, config, method_id, *,
                reference_step=None, previous=None, scaffold=None, schur=None, bank=None):
    """Build the registered R1 policy without a full J, adjoint, or truth query.

    Only ORACLE-M and PROTECTED-ORACLE accept an explicitly supplied offline
    reference.  Common cached objects are owner/material/state checked.  Cost
    components describe actual paid work; standalone cost adds reused common
    construction once, and adds only the noncommon FIXED scaffold for CHEAP.
    """
    if method_id not in METHODS:
        raise ValueError('Unregistered R1 method: ' + str(method_id))
    oracle = method_id in ORACLE_IDS
    if reference_step is not None and not oracle:
        raise ForbiddenAccess('LEGAL_SEED_REFERENCE_STEP_FORBIDDEN')
    if oracle and reference_step is None:
        raise ValueError('Offline oracle requires an explicit reference_step')
    started = _start_cost(adapter.book)
    x = np.asarray(x).copy()
    residual = _real_vector(residual, adapter.P*2*adapter.m, 'residual')
    ell = _real_vector(ell, adapter.p, 'ell')
    if not np.array_equal(x, state.chi) or state.model is not adapter.model:
        raise ValueError('B state owner/material mismatch')
    if previous is not None and not isinstance(previous, AcceptedHistory):
        raise ForbiddenAccess('PREVIOUS_REQUIRES_OWNED_ACCEPTED_HISTORY')
    history = None if previous is None else previous.validated_step(
        adapter.problem.parent_id, method_id, adapter.p)
    target = None if reference_step is None else _real_vector(reference_step, adapter.p, 'reference_step')
    allocation = _allocation(config, method_id)
    components, reused, reused_costs = {}, {}, {}
    phase = 'offline_oracle_seed' if oracle else 'legal_seed'
    with adapter.book.scope(phase):
        view = BasisView(adapter, x, state, residual)
        if schur is None:
            schur = _costed(adapter.book, components, 'schur',
                lambda: build_schur(adapter, x, state, residual, config))
            reused['schur'] = False
        else:
            if (not isinstance(schur, SchurFeedback) or schur.view._a is not adapter
                    or schur.view._state is not state or not np.array_equal(schur.view.x, x)):
                raise ValueError('Schur owner/material/state mismatch')
            # Reject a stale operator even if its material array still matches.
            adapter.version(x)
            if hasattr(schur, '_r1_material_version') and schur._r1_material_version != adapter.version(x):
                raise ValueError('Schur cache invalidated by material refresh')
            reused['schur'] = True
            reused_costs['schur'] = getattr(schur, 'r1_info', {}).get('creation_cost', {})
        schur._r1_material_version = adapter.version(x)
        if bank is None:
            bank = _costed(adapter.book, components, 'bank', lambda: paired_probe_bank(view, config))
            reused['bank'] = False
        else:
            seed = (int(config.get('master_seed', 20261005)), int(adapter.problem.parent_id))
            if (not isinstance(bank, ProbeBank) or bank.parent != adapter.problem.parent_id
                    or bank.material_dimension != adapter.p or bank.data_dimension != adapter.P*2*adapter.m
                    or bank.rng_seed != seed):
                raise ValueError('Probe bank owner/dimension/RNG mismatch')
            reused['bank'] = True
            reused_costs['bank'] = bank.creation_cost
        material = bank.material_probes[:, :allocation['M']].copy()
        observation = bank.measurement_probes[:, :allocation['O']].copy()
        observation[:, 0] = residual
        labels = ['paired_random_'+str(i) for i in range(allocation['M'])]
        history_slot = None
        if method_id == 'CHEAP-TASK':
            if scaffold is None:
                scaffold = _costed(adapter.book, components, 'cheap_scaffold', lambda: build_model(
                    adapter, x, state, residual, ell, config, 'FIXED-DEEP', schur=schur, bank=bank))
                reused['scaffold'] = False
            else:
                if (not isinstance(scaffold, PolicyModel) or scaffold.info['method_id'] != 'FIXED-DEEP'
                        or scaffold.jacobian.adapter is not adapter or scaffold.jacobian.state is not state
                        or not np.array_equal(scaffold.jacobian.x, x)
                        or not np.array_equal(scaffold.seeds.measurement_probes[:, 0], residual)
                        or scaffold.info.get('full_reference_used')
                        or scaffold.info.get('previous_owner') is not None):
                    raise ValueError('CHEAP scaffold must be this state\'s FIXED-DEEP model')
                scaffold.projection.check()
                reused['scaffold'] = True
                reused_costs['scaffold_noncommon'] = scaffold.info['noncommon_cost']
            def cheap_gradient():
                with adapter.book.span('r1_cheap_reduced_gradient', r1_cheap_gradients=1):
                    # A preceding FIXED QP may have acquired its material
                    # matrix.  An independent Jacobian guarantees CHEAP's
                    # cold S*/core*/B* work is paid rather than borrowing it.
                    cold_jacobian = ReducedJacobian(adapter, x, state, scaffold.projection)
                    return cold_jacobian.pullback(residual)+ell
            target = _costed(adapter.book, components, 'cheap_gradient', cheap_gradient)
            material[:, 0] = -target/max(float(la.norm(target)), 1e-300)
            labels[0] = 'negative_cheap_reduced_gradient_plus_ell'
            history_slot = 1
        elif oracle:
            material[:, 0] = target/max(float(la.norm(target)), 1e-300)
            labels[0] = 'offline_full_reference_step'
            history_slot = 1
        elif method_id == 'PROTECTED-RANDOM':
            target = material[:, 0].copy()
            labels[0] = 'paired_random_protected_target'
            history_slot = 1
        else:
            history_slot = 0
        previous_norm = None if history is None else float(la.norm(history))
        if history is not None and previous_norm > 1e-12:
            # Legacy build_seeds normalizes its history replacement once
            # when assigning it and again with the complete M4 bank.
            material[:, history_slot] = _normalize_columns((history/previous_norm)[:, None])[:, 0]
            labels[history_slot] = 'own_previous_accepted_step'
        else:
            history_slot = None
        # The uncompressed matrix is source-major, then probe-major.  It is
        # intentionally built in one all-source B action, never from source 0.
        raw = {}
        def material_sources():
            b = view.B(material)
            if b.shape != (view.P, view.n, allocation['M']):
                raise ValueError('B material source dimension mismatch')
            return schur.K(b.transpose(1, 0, 2).reshape(view.n, -1))
        raw['M'] = _costed(adapter.book, components, 'material_sources', material_sources)
        def observation_sources():
            data = unpack(adapter.whiten(observation, adjoint=True), view.P, view.m)
            return schur.T_adjoint(view.S_adjoint(data.transpose(1, 0, 2).reshape(view.m, -1)))
        raw['O'] = _costed(adapter.book, components, 'observation_sources', observation_sources)
        raw['P'] = _costed(adapter.book, components, 'forcing_sources', lambda: schur.K(view.forcing()))
        blocks, records = {}, {}
        target_block = raw['M'].reshape(view.n, view.P, allocation['M'])[:, :, 0]
        protected = method_id.startswith('PROTECTED-')
        for name in 'OPM':
            def compress(name=name):
                with adapter.book.span('seed_'+name+'_compression', **{'seed_'+name+'_input_rhs': raw[name].shape[1]}):
                    if name == 'M' and protected:
                        q_target, target_rec = orth(target_block, against=schur.U,
                            rtol=config.get('orthogonal_rank_rtol', 1e-10))
                        if q_target.shape[1] > allocation['M']:
                            raise ValueError('Protected all-source target rank exceeds M allocation')
                        q_fill, fill_rec = orth(raw[name], against=np.column_stack((schur.U, q_target)),
                            rank=allocation['M']-q_target.shape[1], rtol=config.get('orthogonal_rank_rtol', 1e-10))
                        q = np.column_stack((q_target, q_fill))
                        rec = {'input_columns': raw[name].shape[1], 'rank': q.shape[1],
                            'deflated': raw[name].shape[1]-q.shape[1], 'protected_rank': q_target.shape[1],
                            'protected_target': target_rec, 'random_fill': fill_rec,
                            'target_capture': _capture(target_block, q)}
                        return q, rec
                    return orth(raw[name], against=schur.U, rank=allocation[name],
                                rtol=config.get('orthogonal_rank_rtol', 1e-10))
            q, rec = _costed(adapter.book, components, 'compression_'+name, compress)
            rec.update(source_count=view.P, requested_rank=allocation[name],
                original_column_norms=la.norm(raw[name], axis=0).tolist(),
                no_truth_or_reference_step=not (name == 'M' and oracle), truth_used=False,
                full_reference_used=bool(name == 'M' and oracle),
                provenance={'O': 'measured residual and paired independent whitened data probes, C*',
                    'P': 'all known illumination forcing, Kb',
                    'M': ', '.join(labels)}[name])
            blocks[name], records[name] = q, rec
        seeds = SeedBundle(blocks, records, list(bank.rng_seed), material, observation)
        hierarchy = Hierarchy(view, schur, seeds, config)
        Z, info = _costed(adapter.book, components, 'hierarchy', lambda: hierarchy.at_degree(allocation['degree']))
        projection = _costed(adapter.book, components, 'projection', lambda: Projection(adapter, x, Z, config))
        jacobian = ReducedJacobian(adapter, x, state, projection)
        span = _costed(adapter.book, components, 'material_span', lambda: _real_span(
            material, config.get('orthogonal_rank_rtol', 1e-10), adapter.book))
        previous_capture = None
        if history_slot is not None:
            previous_block = raw['M'].reshape(view.n, view.P, allocation['M'])[:, :, history_slot]
            previous_capture = {'seed': _capture(previous_block, blocks['M']), 'final': _capture(previous_block, Z)}
        mapping = [{'column': source*allocation['M']+probe, 'source_index': source,
                    'probe_index': probe, 'probe_provenance': labels[probe]}
                   for source in range(view.P) for probe in range(allocation['M'])]
        source_mapping = {'M': mapping,
            'O': [{'column': source*allocation['O']+probe, 'source_index': source, 'probe_index': probe}
                  for source in range(view.P) for probe in range(allocation['O'])],
            'P': [{'column': source, 'source_index': source} for source in range(view.P)]}
        info.update(method_id=method_id, allocation=allocation.copy(),
            requested_rank_bound=int(config['retained_rank']+(allocation['O']+allocation['P']+allocation['M'])*(allocation['degree']+1)),
            actual_seed_ranks={key: blocks[key].shape[1] for key in 'OPM'},
            seed_provenance=records, seed_rng=list(bank.rng_seed), extra_rng_seed=list(bank.extra_rng_seed),
            probe_source_mapping=mapping, probe_source_mapping_by_family=source_mapping,
            material_probe_provenance=labels, material_span_rank=span.shape[1],
            no_truth_or_reference_step=not oracle, truth_used=False, full_reference_used=oracle,
            protected=protected, target_capture=_capture(target_block, blocks['M'])
                if protected or oracle or method_id == 'CHEAP-TASK' else None,
            previous_norm=previous_norm, previous_capture=previous_capture,
            previous_status='absent' if history is None else 'used' if history_slot is not None else 'legacy_small_norm_skip',
            previous_owner=None if previous is None else {'parent': previous.parent, 'method': previous.method,
                'accepted_index': previous.accepted_index, 'source': 'own_alpha_scaled_accepted_step'},
            task_probe_slot=0 if method_id == 'CHEAP-TASK' else None, previous_probe_slot=history_slot,
            retained_fallback=getattr(schur, 'r1_info', {}).get('retained_fallback'),
            core=projection.stability, galerkin_core=projection.galerkin_stability,
            projection=projection.kind, fallback=projection.fallback,
            cost_components=components, reused=reused, reused_creation_costs=reused_costs)
    actual = _finish_cost(adapter.book, started)
    info['actual_cost'] = actual
    info['noncommon_cost'] = _sum_costs(*(value for key, value in components.items() if key not in ('schur', 'bank')))
    # Include validation/provenance/assembly overhead in the reused scaffold,
    # while removing its common construction exactly once.  An internally
    # computed CHEAP scaffold is already inside actual_cost and is not added.
    for key in ('wall_seconds', 'process_cpu_seconds'):
        info['noncommon_cost'][key] = (actual[key]-components.get('schur', {}).get(key, 0.)
                                      -components.get('bank', {}).get(key, 0.))
    info['standalone_cost'] = _sum_costs(actual, *reused_costs.values())
    return PolicyModel(projection, jacobian, seeds, schur, info, span)
