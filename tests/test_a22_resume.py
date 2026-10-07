"""Source-only resume checks: synthetic arrays/files and mocked online physics.

Execution belongs to the parent's metered validation. No Maxwell model, original
scene data, SSH, private configuration or generator is used by these fixtures.
"""
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from a20.costs import write_json
from a22 import evaluate, offline_assets


class GuardBook:
    def __init__(self):
        self.role, self.phase, self.stage = 'online', 'online', 'screen_health'
        self.counts, self.events = Counter(), []

    @contextmanager
    def span(self, name, **counts):
        self.counts.update(counts)
        self.events.append((name, self.role, self.stage))
        yield

    @contextmanager
    def action_guard(self, action, *, role, **kwargs):
        if (action, role) not in (('full_J', 'offline_evaluation'), ('truth', 'offline_label')):
            raise AssertionError('Unexpected cache-replay capability')
        previous, self.role = self.role, role
        self.events.append((action, role, self.stage))
        try:
            yield
        finally:
            self.role = previous

    @contextmanager
    def scope(self, phase):
        previous, self.phase = self.phase, phase
        try:
            yield
        finally:
            self.phase = previous

    @contextmanager
    def stage_scope(self, stage):
        previous, self.stage = self.stage, stage
        try:
            yield
        finally:
            self.stage = previous

    def check(self):
        pass


def fixture():
    chart = SimpleNamespace(d=32, Q=np.eye(16))
    chart.expand = lambda x: np.asarray(x)[:16]+1j*np.asarray(x)[16:]
    chart.project = lambda x: np.concatenate((np.asarray(x).real, np.asarray(x).imag))
    problem = SimpleNamespace(parent_id=2001, points=np.zeros((16, 3)), volume=1., frequency=2.,
        dirs=np.zeros((6, 3)), pols=np.zeros((6, 3), complex), receivers=np.zeros((2, 3)),
        obs_basis=np.zeros((2, 2, 3), complex))
    adapter = SimpleNamespace(problem=problem, chart=chart, P=6, m=3, whitening=2., _version=7,
        full_tangent_action=Mock(side_effect=AssertionError('No physical derivative allowed')))
    anchor = SimpleNamespace(adapter=adapter, chi=np.full(16, .1+.04j),
        state=SimpleNamespace(field=np.full((6, 3), .01j)),
        provenance={'source_backward_residual': 0., 'background': [.1, .04]},
        cache_key=SimpleNamespace(configuration='{}'))
    AW = np.zeros((36, 32))
    AW[:32] = np.diag(np.arange(1., 33.))
    model = SimpleNamespace(anchor=anchor, AW=AW, MW=np.ones((6, 1, 32), complex),
        PMW=np.ones((6, 1, 32), complex), basis=np.ones((48, 1)),
        projection=SimpleNamespace(material_version=7), provenance={'actual_rank': 1}, sigma_complex=.01)
    scene = SimpleNamespace(family='gaussian', provenance={'source_count': 6}, geometry={'n': 12, 'truth_n': 14})
    context = SimpleNamespace(provenance={'certificate_type': 'empirical_indicator'},
        lambda_value=1., declared_object_radius=.25)
    direction = dict(id=0, candidate_index=0, v=np.eye(32)[0], origin='fixed')
    descriptor = dict(alpha=1., beta=1., gamma=1., profile_g=1., attribution=1.,
                      dual_defect_norm=0., IR_direction_norm=0.)
    nuisance = np.eye(32)[1]
    joint = direction['v']+.35*nuisance
    amplitudes = [dict(level_id=i, amplitude=amp,
                      predictions={('nominal', 0.): {'pred_nominal': .1},
                                   ('nominal', 1.): {'pred_nominal': .1}})
                  for i, amp in enumerate((.01, .02))]
    cases = [dict(direction=direction, descriptor=descriptor, nuisance=nuisance,
                  joint=joint, amplitudes=amplitudes)]
    config = dict(screening_scenes=[2001], master_seed=17, total_direction_descriptors=1,
        split_ranks=[], finite_screening_directions=1, finite_expansion_directions=1,
        interventions=['nominal'], noise_levels=[0., 1.], noise_draws=1,
        material_absolute_floor=1e-6, nuisance_fraction=.35)
    center = anchor.chi+chart.expand(np.full(32, .001))
    return model, scene, context, direction, descriptor, cases, config, center


def case_row(level, *, status='OK', noise=0.):
    return dict(scene_id=2001, direction_id=0, candidate_index=0, amplitude_level=level,
        amplitude=(.01, .02)[level], noise_level=float(noise), noise_draw=0, intervention='nominal',
        noise_seed=f'17:2001:0:{level}:0:661', evidence_scope='deployable', status=status,
        coefficient_error=0. if status == 'OK' else None,
        true_error=0. if status == 'OK' else None, kkt_relative=0., feasibility=0.)


def seed_partial(root, *, wrong_AW=False):
    model, scene, context, direction, desc, cases, config, center = fixture()
    out = root/'results/a22/stage_a'
    directory = out/'scene_2001'
    directory.mkdir(parents=True)
    np.savez(directory/'online_factors.npz', AW=model.AW*(2 if wrong_AW else 1),
             MW=model.MW, PMW=model.PMW)
    write_json(directory/'online_provenance.json', dict(online=scene.provenance,
        anchor=model.anchor.provenance, opm=model.provenance, descriptor=context.provenance,
        raw_data_label_access=False, exact_background_assumed=[.1, .04],
        direction_selection_uses_truth=False))
    frozen = dict(direction)
    frozen.update(desc, full_J_read=False, label_read=False)
    write_json(directory/'frozen_online_directions.json', [frozen])
    write_json(directory/'frozen_online_budgets.json', evaluate._freeze_budget_rows(cases))
    np.savez(directory/'OFFLINE_J_benchmark.npz', JF=model.AW)
    for amplitude in cases[0]['amplitudes']:
        i, amp = amplitude['level_id'], amplitude['amplitude']
        perturbation = amp*cases[0]['joint']
        np.savez(directory/f'OFFLINE_label_d0_a{i}.npz', clean_data=np.ones((6, 3), complex),
            coefficients=model.anchor.adapter.chart.project(center-model.anchor.chi)+perturbation,
            perturbation_coefficients=perturbation, original_material=center,
            direction=direction['v'], nuisance=cases[0]['nuisance'], amplitude=amp,
            source_order=np.arange(6))
    evaluate._append(out/'direction_metrics.jsonl', case_row(0))
    evaluate._append(out/'direction_metrics.jsonl', case_row(0, status='INVALID_QP', noise=1.))
    evaluate._append(out/'direction_metrics.jsonl', case_row(1, noise=1.))
    # This models interruption before any scene summary was written.
    return model, scene, context, direction, desc, cases, config, center, directory


class ResumeTests(unittest.TestCase):
    def test_keys_restore_partial_without_scene_summary_and_keep_invalids(self):
        with tempfile.TemporaryDirectory() as name:
            out = Path(name)
            ok, failed = case_row(0), case_row(1, status='INVALID_QP')
            incomplete = case_row(1, noise=3.)
            incomplete.pop('true_error')
            for row in (ok, failed, incomplete):
                evaluate._append(out/'direction_metrics.jsonl', row)
            rows, splits, scenes, keys, scene_ids = evaluate._restore_stage_a(out)
            self.assertEqual(rows, [ok, failed, incomplete])
            self.assertEqual(keys, {evaluate.stage_a_case_key(ok), evaluate.stage_a_case_key(failed)})
            self.assertEqual((splits, scenes, scene_ids), ([], [], set()))
            changed = dict(ok, intervention='calibration')
            self.assertNotEqual(evaluate.stage_a_case_key(ok), evaluate.stage_a_case_key(changed))
            with self.assertRaises(evaluate.ResumeMismatch):
                evaluate.stage_a_case_key(dict(ok, noise_draw=.5))

    def test_frozen_values_preserved_and_operational_provenance_can_differ(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            path = directory/'online_provenance.json'
            write_json(path, {'source_count': 6, 'cost': {'wall_seconds': 999.}, 'job_id': 'old'})
            original = path.read_bytes()
            evaluate._freeze_json(path, {'source_count': 6, 'cost': {'wall_seconds': 1.}, 'job_id': 'new'},
                                  resume=True, audit=directory/'audit')
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue((directory/'audit/online_provenance.regenerated.json').is_file())
            with self.assertRaises(evaluate.ResumeMismatch):
                evaluate._freeze_json(path, {'source_count': 5}, resume=True, audit=directory/'bad_audit')
            self.assertEqual(path.read_bytes(), original)

    def test_J_cache_is_guarded_shape_checked_and_new_state_contract_checked(self):
        model, *_ = fixture()
        with tempfile.TemporaryDirectory() as name:
            path, book = Path(name)/'J.npz', GuardBook()
            np.savez(path, JF=model.AW)
            with self.assertRaises(evaluate.ResumeMismatch):
                evaluate._load_j_cache(path, model, book, online_verified=False)
            self.assertEqual(book.counts['offline_cache_reads'], 0)
            JF, legacy = evaluate._load_j_cache(path, model, book, online_verified=True)
            np.testing.assert_array_equal(JF, model.AW)
            self.assertTrue(legacy)
            self.assertEqual(book.counts['offline_cache_hits'], 1)
            self.assertEqual(book.counts['full_forward_calls'], 0)
            self.assertEqual(book.counts['data_generation_F_calls'], 0)
            contract = evaluate._cache_contract(model)
            np.savez(path, JF=model.AW, **contract)
            _, legacy = evaluate._load_j_cache(path, model, book, online_verified=True)
            self.assertFalse(legacy)
            contract['anchor_material'] = model.anchor.chi+.001
            np.savez(path, JF=model.AW, **contract)
            with self.assertRaisesRegex(evaluate.ResumeMismatch, 'anchor_material'):
                evaluate._load_j_cache(path, model, book, online_verified=True)
            np.savez(path, JF=np.zeros((35, 32)))
            with self.assertRaisesRegex(evaluate.ResumeMismatch, 'JF_NOT_FINITE_REAL'):
                evaluate._load_j_cache(path, model, book, online_verified=True)
            self.assertEqual(book.counts['offline_cache_hits'], 2)
            self.assertEqual(book.role, 'online')

    def test_only_two_split_identity_residuals_use_established_dimensionless_tolerance(self):
        old = dict(split_rank=4, orthogonality=1e-16, nuisance_leakage=2e-16,
                   regularization=.1, noise_gain=2., sigma_min=1.)
        new = dict(old, orthogonality=3e-16, nuisance_leakage=4e-16)
        with tempfile.TemporaryDirectory() as name:
            evaluate._validate_split_rows([old], new, audit=Path(name))
            self.assertTrue((Path(name)/'split_4_IDENTITY_COMPARISON.json').exists())
            self.assertEqual(old['orthogonality'], 1e-16)
            with self.assertRaisesRegex(evaluate.ResumeMismatch, 'SPLIT_IDENTITY_FAILED'):
                evaluate._validate_split_rows([old], dict(new, orthogonality=1.01e-9))
            with self.assertRaisesRegex(evaluate.ResumeMismatch, 'FROZEN_VALUE'):
                evaluate._validate_split_rows([old], dict(new, sigma_min=1.00001))

    def test_label_cache_checks_material_direction_amplitude_and_six_source_order(self):
        model, _, _, direction, _, cases, _, center = fixture()
        amp, book = .01, GuardBook()
        perturbation = amp*cases[0]['joint']
        kwargs = dict(coefficients=model.anchor.adapter.chart.project(center-model.anchor.chi)+perturbation,
            perturbation_coefficients=perturbation, original_material=center,
            direction=direction['v'], nuisance=cases[0]['nuisance'], amplitude=amp, online_verified=True)
        values = {key: value for key, value in kwargs.items() if key != 'online_verified'}
        values.update(clean_data=np.ones((6, 3), complex), source_order=np.arange(6))
        with tempfile.TemporaryDirectory() as name:
            path = Path(name)/'label.npz'
            np.savez(path, **values)
            raw, meta = evaluate._load_label_cache(path, model, book, **kwargs)
            self.assertEqual(raw.shape, (6, 3))
            self.assertTrue(meta['legacy_cache'])
            self.assertEqual(meta['full_forward_calls'], 0)
            np.savez(path, **dict(values, **evaluate._cache_contract(model), backward_residual=2e-10))
            _, meta = evaluate._load_label_cache(path, model, book, **kwargs)
            self.assertFalse(meta['legacy_cache'])
            self.assertEqual(meta['backward_residual'], 2e-10)
            for key, value in [('amplitude', .02), ('coefficients', np.zeros(32)),
                               ('direction', np.eye(32)[2]), ('source_order', np.arange(6)[::-1]),
                               ('clean_data', np.ones((3, 6), complex))]:
                np.savez(path, **dict(values, **{key: value}))
                with self.assertRaises(evaluate.ResumeMismatch):
                    evaluate._load_label_cache(path, model, book, **kwargs)
            self.assertEqual(book.counts['offline_cache_hits'], 2)
            self.assertEqual(book.counts['data_generation_F_calls'], 0)
            self.assertEqual(book.role, 'online')

    def test_completed_scene_requires_all_registered_case_rows(self):
        config = fixture()[6]
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = root/'scene_2001/frozen_online_budgets.json'
            write_json(path, [{'direction_id': 0, 'amplitude_level': 0},
                              {'direction_id': 0, 'amplitude_level': 1}])
            with self.assertRaisesRegex(evaluate.ResumeMismatch, 'MISSING_CASES'):
                evaluate._validate_complete_scene(root, 2001, [case_row(0)], config)
            evaluate._validate_complete_scene(root, 2001,
                [case_row(level, noise=noise, status='INVALID_QP' if level else 'OK')
                 for level in (0, 1) for noise in (0., 1.)], config)

    def test_partial_resume_pays_rebuild_replays_cache_and_skips_terminal_invalids(self):
        with tempfile.TemporaryDirectory() as name:
            root, book = Path(name), GuardBook()
            model, scene, context, direction, desc, cases, config, center, directory = seed_partial(root)
            frozen_paths = [directory/path for path in ('online_factors.npz', 'online_provenance.json',
                'frozen_online_directions.json', 'frozen_online_budgets.json', 'OFFLINE_J_benchmark.npz',
                'OFFLINE_label_d0_a0.npz', 'OFFLINE_label_d0_a1.npz')]
            before = {path: path.read_bytes() for path in frozen_paths}

            def anchor_build(*args, **kwargs):
                with book.span('mock_paid_anchor', anchor_constructions=1, full_forward_calls=1):
                    return model.anchor

            def opm_build(*args, **kwargs):
                with book.span('mock_paid_opm', opm_constructions=1):
                    return model

            def truth_load(*args):
                audits = list((directory/'resume_audits').glob('*'))
                self.assertEqual(len(audits), 1)
                self.assertTrue((audits[0]/'frozen_online_budgets.regenerated.json').is_file())
                return center

            result = {'qp': {'kkt_relative': 0., 'feasibility_violation': 0.}}
            with patch.object(evaluate, 'load_online_scene', return_value=scene), \
                 patch.object(evaluate, 'build_anchor', side_effect=anchor_build), \
                 patch.object(evaluate, 'build_opm', side_effect=opm_build), \
                 patch.object(evaluate, 'build_descriptor_context', return_value=context), \
                 patch.object(evaluate, 'choose_directions', return_value=[direction]), \
                 patch.object(evaluate, 'direction_descriptor', return_value=desc), \
                 patch.object(evaluate, '_frozen_direction_cases', return_value=cases), \
                 patch.object(evaluate, 'finite_label', side_effect=AssertionError('No new F')), \
                 patch.object(offline_assets, 'load_evaluation_truth', side_effect=truth_load), \
                 patch.object(evaluate, 'evaluate_recovery', return_value=(np.zeros(32), result)) as qp:
                report = evaluate.run_stage_a(root, config, book, device='cpu', resume=True)
            self.assertEqual(report['rows'], 4)
            self.assertEqual(qp.call_count, 1)
            self.assertEqual(book.counts['anchor_constructions'], 1)
            self.assertEqual(book.counts['opm_constructions'], 1)
            self.assertEqual(book.counts['offline_cache_hits'], 2)
            self.assertEqual(book.counts['full_forward_calls'], 1)  # Only the paid mocked rebuild.
            self.assertEqual(book.counts['data_generation_F_calls'], 0)
            self.assertEqual(book.counts['resume_completed_QP_skips'], 3)
            retained = evaluate._read_rows(root/'results/a22/stage_a/direction_metrics.jsonl')
            self.assertEqual([row['status'] for row in retained], ['OK', 'INVALID_QP', 'OK', 'OK'])
            self.assertEqual(len({evaluate.stage_a_case_key(row) for row in retained}), 4)
            self.assertTrue(all(row['evidence_scope'] == 'deployable' for row in retained))
            for path in frozen_paths:
                self.assertEqual(path.read_bytes(), before[path])
            model.anchor.adapter.full_tangent_action.assert_not_called()

    def test_incompatible_AW_refuses_before_offline_load_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as name:
            root, book = Path(name), GuardBook()
            model, scene, context, direction, desc, cases, config, _, directory = seed_partial(root, wrong_AW=True)
            before = (directory/'online_factors.npz').read_bytes()
            with patch.object(evaluate, 'load_online_scene', return_value=scene), \
                 patch.object(evaluate, 'build_anchor', return_value=model.anchor), \
                 patch.object(evaluate, 'build_opm', return_value=model), \
                 patch.object(evaluate, 'build_descriptor_context', return_value=context), \
                 patch.object(evaluate, 'choose_directions', return_value=[direction]), \
                 patch.object(evaluate, 'direction_descriptor', return_value=desc), \
                 patch.object(offline_assets, 'load_evaluation_truth') as truth_load:
                with self.assertRaisesRegex(evaluate.ResumeMismatch, 'ARRAY_MISMATCH:AW'):
                    evaluate.run_stage_a(root, config, book, device='cpu', resume=True)
                truth_load.assert_not_called()
            self.assertEqual((directory/'online_factors.npz').read_bytes(), before)
            self.assertEqual(len(evaluate._read_rows(root/'results/a22/stage_a/direction_metrics.jsonl')), 3)
            self.assertEqual(evaluate._read_rows(root/'results/a22/stage_a/scene_metrics.jsonl')[-1]['status'], 'FAILED')


if __name__ == '__main__':
    unittest.main()
