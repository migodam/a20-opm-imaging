"""A bounded cached timing receipt, separate from error-localization evidence.

Four fixed first noiseless/nominal measurements, no truth or full J, one timing
of the common model and four legal k16 splits per scene. No timing selection,
repeat campaign or operator run. These solves do not replace primary vectors.
"""
import csv
import json
from pathlib import Path
import time

import numpy as np

from a20.backend import pack
from a22.core import constrained_material_solve
from .replay import _load_online, _require_evaluation_freeze, SCENES


def run_runtime(root,config,book):
    root=Path(root);_require_evaluation_freeze(root)
    original=json.loads((root/'configs/a22.json').read_text())
    rows=[]
    for sid in SCENES:
        io_start=time.perf_counter()
        cache=_load_online(root,sid,config)
        # Whitelist the existing observation, never the material/error label.
        with np.load(root/f'results/a22/stage_a/scene_{sid}/OFFLINE_label_d0_a0.npz',allow_pickle=False) as z:
            observation=np.array(z['clean_data'],copy=True)
        io_wall=time.perf_counter()-io_start
        construction=json.loads((root/f'results/a22_r1/online/scene_{sid}.json').read_text())['cost']
        for method in ('COMMON_32D','RANDOM','A1','A2','A3'):
            begin,cpu=time.perf_counter(),time.process_time()
            start=time.perf_counter()
            if method=='COMMON_32D':
                basis=None;k=32
            elif method=='RANDOM':
                order=np.random.default_rng(np.random.SeedSequence([20261910,sid])).permutation(32)
                basis=cache.common_V[:,order[:16]];k=16
            else:
                order=np.argsort(cache.scores[method],kind='stable')
                basis=cache.common_V[:,order[:16]];k=16
            split_wall=time.perf_counter()-start
            start=time.perf_counter()
            d=cache.whitening*pack(observation-cache.background)
            A=cache.AW if basis is None else cache.AW@basis
            preparation_wall=time.perf_counter()-start
            start=time.perf_counter()
            with book.scope('online'),book.span('r1_cached_runtime_material_solve',runtime_small_solves=1):
                _,qp,_=constrained_material_solve(A,d,cache.chart,cache.anchor,original,book,basis=basis,lam=cache.lam)
            solve_wall=time.perf_counter()-start
            kernel_wall=time.perf_counter()-begin
            rows.append(dict(scene=sid,method=method,k=k,status='VALID',
                fixed_input='direction0_amplitude0_noiseless_nominal',
                cache_read_wall_seconds=io_wall,cache_read_amortization='shared measured read shown once per scene',
                split_wall_seconds=split_wall,measurement_and_small_operator_wall_seconds=preparation_wall,
                small_solve_wall_seconds=solve_wall,cached_kernel_wall_seconds=kernel_wall,
                cached_one_shot_including_shared_read_seconds=kernel_wall+io_wall,
                process_cpu_seconds=time.process_time()-cpu,
                known_background_physical_construction_wall_seconds=construction['exclusive_walls']['physical_geometry_setup']+construction['exclusive_walls']['full_forward'],
                original_OPM_construction_wall_seconds=construction['exclusive_walls']['a22_fixed_shallow_opm'],
                descriptor_and_identity_construction_receipt='results/a22_r1/online/scene_'+str(sid)+'.json',
                descriptor_scoring='frozen_cached_scores; fresh score construction is separately billed in the physical freeze',
                new_Maxwell_actions=0,new_labels=0,NN='NOT_RUN',
                feasibility=qp['feasibility_violation'],KKT_relative=qp['kkt_relative'],
                timing_scope='cached local CPU kernel; OS cache not flushed; not end-to-end deployment acceleration',
                primary_metric_vectors_replaced=False))
    out=root/'results/a22_r1/CACHED_ONE_SHOT_RUNTIME.csv'
    with out.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,rows[0].keys());writer.writeheader();writer.writerows(rows)
    summary=dict(status='COMPLETE',runtime_small_solves=20,primary_cases_changed=0,
         method_order=['COMMON_32D','RANDOM','A1','A2','A3'],fixed_scenes=list(SCENES),
         new_Maxwell_actions=0,new_fullwave_labels=0,repeat_count=1,
         offline_full_J_timing='NOT_RUN_NO_RUNTIME_CLAIM',speedup_gate='NOT_ESTABLISHED',
         medians={method:{name:float(np.median([r[name] for r in rows if r['method']==method])) for name in
                         ('cache_read_wall_seconds','split_wall_seconds','small_solve_wall_seconds','cached_one_shot_including_shared_read_seconds')}
                  for method in ('COMMON_32D','RANDOM','A1','A2','A3')})
    (root/'results/a22_r1/CACHED_ONE_SHOT_RUNTIME.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary
