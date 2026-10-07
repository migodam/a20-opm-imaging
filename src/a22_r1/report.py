"""Four-scene summaries, preregistered gates and local diagnostic delivery.

No physics, solver, split selection, calibration, or training occurs here.
The parent scientific review remains distinct from numerical execution.
"""
from __future__ import annotations

from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import platform
import subprocess

import numpy as np

from a20.costs import plain, write_json
from .accounting import paid_history
from .metrics import DEFAULT_METRICS, hierarchical_scene_average, paired_scene_bootstrap
from .replay import SCENES, ONLINE_METHODS, OFFLINE_METHOD

METHODS = (*ONLINE_METHODS, OFFLINE_METHOD)
METRICS = (*DEFAULT_METRICS, 'f_error_phys','f_truth_prior','error_norm',
           'error_phys_norm','error_prior_norm','truth_norm','truth_phys_norm','truth_prior_norm')


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _rows(path):
    path=Path(path)
    stream=(path.open(encoding='utf-8') if path.exists()
            else gzip.open(str(path)+'.gz','rt',encoding='utf-8'))
    with stream:
        return [json.loads(line) for line in stream if line.strip()]


def _csv(path, rows):
    fields=list(dict.fromkeys(name for row in rows for name in row))
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with Path(path).open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream, fields or ['status'])
        writer.writeheader()
        for row in rows:
            writer.writerow({key:json.dumps(plain(value),sort_keys=True,allow_nan=False)
                             if isinstance(value,(dict,list,tuple)) else plain(value)
                             for key,value in row.items()})


def _summary(values, kind):
    if len(values)!=4 or any(value is None or not np.isfinite(value) for value in values):
        return None
    return float(np.mean(values) if kind=='mean' else np.median(values))


def _fmt(value):
    return 'undefined' if value is None else f'{value:.6g}'


def method_screening(scene_rows, method, config, *, k=16):
    """Use only the registered four equal-weight scene means, never cases."""
    lookup={(int(row['scene']),row['method'],int(row['k']),row['test']):row for row in scene_rows}
    a=[lookup.get((sid,method,k,'A'),{}) for sid in SCENES]
    b=[lookup.get((sid,method,k,'B'),{}) for sid in SCENES]
    a_complete=all(row.get('complete',False) for row in a)
    b_complete=all(row.get('complete',False) for row in b)
    medians={name:_summary([row.get(name) for row in a],'median') for name in DEFAULT_METRICS}
    ratios=[(rb['nrmse_phys']/ra['nrmse_phys']
             if ra.get('nrmse_phys') is not None and ra['nrmse_phys']>0
             and rb.get('nrmse_phys') is not None else None) for ra,rb in zip(a,b)]
    ratio=_summary(ratios,'median')
    s1=(a_complete and medians['s_sep']>=config['S1']['median_scene_S_sep_min']
        and medians['q_phys']<=config['S1']['median_scene_q_phys_max']
        and medians['q_prior']>=config['S1']['median_scene_q_prior_min'])
    s3=a_complete and medians['f_truth_phys']>=config['S3']['median_scene_f_truth_phys_min']
    s4=a_complete and b_complete and ratio is not None and ratio<=config['S4']['median_scene_restricted_over_common_NRMSE_phys_max']
    return dict(method=method,k=k,Test_A_complete=a_complete,Test_B_complete=b_complete,
                Test_A_scene_medians=medians, restricted_over_common_scene_ratios=dict(zip(map(str,SCENES),ratios)),
                median_restricted_over_common=ratio,
                S1='SUPPORT' if s1 else ('FAIL' if a_complete else 'INCOMPLETE'),
                S3='SUPPORT' if s3 else ('FAIL' if a_complete else 'INCOMPLETE'),
                S4='SUPPORT' if s4 else ('FAIL' if a_complete and b_complete else 'INCOMPLETE'),
                useful_screening_split=bool(s1 and s3 and s4))


def decide(scene_rows, config, *, numerical_complete, floor_case_count=0):
    by_method={method:method_screening(scene_rows,method,config) for method in METHODS}
    maps={method:{sid:next((row.get('nrmse_phys') for row in scene_rows
                        if row['scene']==sid and row['method']==method and row['k']==16 and row['test']=='A'),None)
                         for sid in SCENES} for method in ('A2','A3')}
    bootstrap=paired_scene_bootstrap(maps['A3'],maps['A2'],expected_scenes=SCENES)
    improvement=bootstrap['relative_improvement_of_means']
    s2=('SUPPORT' if improvement is not None and improvement>=config['S2']['equal_scene_mean_NRMSE_phys_improvement_vs_A2_min']
        else 'FAIL' if improvement is not None else 'INCOMPLETE')
    a3=by_method['A3']
    gates={name:a3[name] for name in ('S1','S3','S4')};gates['S2']=s2
    complete=numerical_complete and floor_case_count==0 and all(row['Test_A_complete'] and row['Test_B_complete'] for row in by_method.values())
    if not complete:
        case='INCOMPLETE'; interpretation='Numerical or coverage prerequisites do not permit an A/B/C/D conclusion.'
    elif all(value=='SUPPORT' for value in gates.values()):
        case='CASE_A_A3_SPLIT_WORKS'; interpretation='A3 separates in-chart error in this exposed screening, with incremental value and stable restriction.'
    elif by_method['A2']['useful_screening_split'] and s2!='SUPPORT':
        case='CASE_C_A2_MATCHES_OR_BEATS_A3'; interpretation='The frozen O/P/M labels do not add the required practical value over generic reduced recoverability.'
    elif by_method[OFFLINE_METHOD]['useful_screening_split'] and not a3['useful_screening_split']:
        case='CASE_B_SPLIT_EXISTS_A3_DOES_NOT_FIND_IT'; interpretation='The registered offline diagnostic supports a split; the frozen cheap A3 estimator does not.'
    else:
        case='CASE_D_NO_USEFUL_SUBSPACE_SEPARATION'; interpretation='No registered method supports the complete hard-split criteria in this chart and regime. This is not a theorem of impossibility for all material bases.'
    return dict(schema='a22_r1.gates.v1',status='SCREENING_ONLY',scientific_case=case,
        interpretation=interpretation,gates=gates,methods=by_method,bootstrap=bootstrap,
        equal_scene_mean_A3_improvement_vs_A2=improvement,
        numerical_complete=complete,numerical_identity_unit_tests='SEPARATE_EVIDENCE',
        independent_scene_clusters=4,scenes=list(SCENES),historical_exposed=True,
        primary_k=16,secondary_k=8,formal_validation='NOT_RUN',formal_PASS=False,
        historical_scalar_reproduction='FAILED_RETAINED_WITH_EXPLICIT_PRE_OUTCOME_ADDENDUM',
        NN='NOT_RUN',expansion='NOT_RUN',nonlinear_reconstruction='NOT_RUN',
        deployment_acceleration='NOT_ESTABLISHED',publication='LOCAL_ONLY',next_action='STOP_AND_REPORT')


def _comparison(scene_rows):
    rows=[]
    for test in ('A','B'):
        for k in (16,8):
            for method in METHODS:
                selected=[row for sid in SCENES for row in scene_rows
                          if row['scene']==sid and row['method']==method and row['k']==k and row['test']==test]
                item=dict(method=method,k=k,test=test,scene_clusters=len(selected),
                    status='COMPLETE' if len(selected)==4 and all(row.get('complete') for row in selected) else 'INCOMPLETE',
                    information_scope='OFFLINE_ORACLE_DIAGNOSTIC' if method==OFFLINE_METHOD else 'ONLINE_LEGAL')
                for metric in METRICS:
                    values=[row.get(metric) for row in selected]
                    item['equal_scene_mean_'+metric]=_summary(values,'mean')
                    item['median_scene_'+metric]=_summary(values,'median')
                rows.append(item)
    return rows


def _table(comparison, test='A', k=16):
    lines=['| 方法 | physics NRMSE均值 | prior NRMSE均值 | S_sep中位数 | q_phys中位数 | q_prior中位数 | truth_phys中位数 |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for method in METHODS:
        row=next(item for item in comparison if item['method']==method and item['k']==k and item['test']==test)
        values=[row['equal_scene_mean_nrmse_phys'],row['equal_scene_mean_nrmse_prior'],row['median_scene_s_sep'],
                row['median_scene_q_phys'],row['median_scene_q_prior'],row['median_scene_f_truth_phys']]
        lines.append('| '+('FULL-J（仅离线）' if method==OFFLINE_METHOD else method)+' | '+' | '.join(map(_fmt,values))+' |')
    return '\n'.join(lines)


def _bootstrap_raw(root, scenes):
    lookup={(row['scene'],row['method']):row['nrmse_phys'] for row in scenes if row['test']=='A' and row['k']==16}
    a3=np.array([lookup.get((sid,'A3'),np.nan) for sid in SCENES])
    a2=np.array([lookup.get((sid,'A2'),np.nan) for sid in SCENES])
    idx=np.random.default_rng(20261911).integers(0,4,size=(2000,4))
    rows=[]
    for number, selected in enumerate(idx):
        m3,m2=float(np.mean(a3[selected])),float(np.mean(a2[selected]))
        valid=np.isfinite(m3) and np.isfinite(m2) and m2>0
        rows.append(dict(resample=number,scene_indices=selected.tolist(),sampled_scene_ids=[SCENES[i] for i in selected],
             mean_A2=m2 if np.isfinite(m2) else None,mean_A3=m3 if np.isfinite(m3) else None,
             mean_difference=m2-m3 if valid else None,relative_improvement=1-m3/m2 if valid else None))
    _csv(root/'results/a22_r1/PAIRED_SCENE_BOOTSTRAP.csv',rows)


def split_projector_audit(root):
    """Audit frozen selected sets, without changing scores or selections."""
    rows=[]
    for sid in SCENES:
        with np.load(Path(root)/f'results/a22_r1/online/splits/scene_{sid}.npz',allow_pickle=False) as z:
            for k in (16,8):
                for first,second in (('A1','A2'),('A2','A3')):
                    x,y=z[f'V_phys_{first}_k{k}'],z[f'V_phys_{second}_k{k}']
                    a,b=z['order_'+first][:k],z['order_'+second][:k]
                    rows.append(dict(scene=sid,k=k,first=first,second=second,
                        indices_first=a.tolist(),indices_second=b.tolist(),
                        same_selected_index_set=bool(set(a)==set(b)),
                        same_selected_index_order=bool(np.array_equal(a,b)),
                        projector_frobenius_distance=float(np.linalg.norm(x@x.T-y@y.T)),
                        selected_index_jaccard=len(set(a)&set(b))/len(set(a)|set(b))))
    _csv(Path(root)/'results/a22_r1/SPLIT_PROJECTOR_EQUALITY.csv',rows)
    write_json(Path(root)/'results/a22_r1/SPLIT_PROJECTOR_EQUALITY.json',dict(
        scope='same registered candidate pool; no arbitrary optimal split search',rows=rows,
        primary_A2_A3_same_index_sets=all(r['same_selected_index_set'] for r in rows if r['k']==16 and r['first']=='A2'),
        secondary_A2_A3_same_index_sets=all(r['same_selected_index_set'] for r in rows if r['k']==8 and r['first']=='A2')))
    return rows


def cost_summary(root, config):
    root=Path(root);rows=_rows(root/'results/a22_r1/COST_LEDGER.jsonl')
    paid=paid_history(root)
    inclusive=[row for row in rows if row.get('additive_receipt')]
    counts=Counter()
    for row in inclusive: counts.update(row.get('counts',{}))
    measured=sum(row.get('process_cpu_seconds',0.) for row in inclusive if 'allowance' not in str(row.get('measurement','')).lower())
    summary=dict(schema='a22_r1.cost_summary.v1',R1_CPU_including_allowance_seconds=paid['cpu'],
        R1_CPU_measured_seconds=measured,R1_CPU_source_allowance_seconds=paid['cpu']-measured,
        R1_GPU_related_occupation_seconds=paid['gpu'],
        CPU_cap_seconds=config['cpu_cap_seconds'],GPU_cap_seconds=config['gpu_occupation_cap_seconds'],
        historical_A22_CPU_seconds=config['historical_a22_cpu_seconds'],
        historical_A22_GPU_seconds=config['historical_a22_gpu_seconds'],
        cumulative_A22_GPU_seconds=config['historical_a22_gpu_seconds']+paid['gpu'],
        background_predictions=paid['backgrounds'],new_fullwave_labels=paid['new_labels'],
        unique_inclusive_receipt_count=len(paid['receipts']),counts=dict(counts),
        action_aggregation='F/Fstar/L/Lstar are exclusive; Maxwell_matvec_rhs is their aggregate and is not added again',
        nested_spans_additive=False,failed_receipts_retained=True,
        complete_deployment_time='NOT_MEASURED',rank_speedup_claim='NOT_ESTABLISHED')
    write_json(root/'results/a22_r1/COST_SUMMARY.json',summary)
    return summary


def generate_report(root, config):
    root=Path(root);out=root/'results/a22_r1'
    summary=_json(out/'REPLAY_SUMMARY.json')
    if summary.get('status')!='COMPLETE':
        raise ValueError('REPORT_REQUIRES_COMPLETED_CASE_GRID_NOT_FILTERED_SUCCESSES')
    raw=_rows(root/summary['case_metric_path'])
    grouped=hierarchical_scene_average(raw,metric_names=METRICS,
                    expected_conditions=summary['expected_conditions'],expected_groups=summary['expected_groups'])
    scene_rows=grouped['scene_rows']
    for row in scene_rows:
        row.update(status='COMPLETE' if row['complete'] else 'INCOMPLETE',historical_exposed=True,
                   family=next(value['family'] for value in raw if value['scene']==row['scene']))
    branch=hierarchical_scene_average([r for r in raw if r['test']=='B'],
                metric_names=('data_residual','solve_wall_seconds','solve_process_cpu_seconds','prior_coefficient_norm'),
                expected_conditions=summary['expected_conditions'],
                expected_groups=[r for r in summary['expected_groups'] if r['test']=='B'])
    branch_lookup={(r['scene'],r['method'],r['k'],r['test']):r for r in branch['scene_rows']}
    for row in scene_rows:
        b=branch_lookup.get((row['scene'],row['method'],row['k'],row['test']))
        if b: row.update({name:b[name] for name in ('data_residual','solve_wall_seconds','solve_process_cpu_seconds','prior_coefficient_norm')})
    comparison=_comparison(scene_rows)
    _csv(out/'PER_SCENE_SPLIT_METRICS.csv',scene_rows)
    _csv(out/'SPLIT_COMPARISON.csv',comparison)
    _csv(out/'PER_CONDITION_SPLIT_METRICS.csv',grouped['condition_rows'])
    _csv(out/'RESTRICTED_BRANCH_RUNTIME_AND_DATA.csv',branch['scene_rows'])
    write_json(out/'AGGREGATION_AUDIT.json',dict(main=grouped['audit'],branch=branch['audit'],
                   replicate_unit='noise_draw',condition_unit='48 equally weighted conditions per scene',
                   statistical_unit='4 scenes, not 2112 cases'))
    floor_count=sum(bool(r.get('floor_phys_active')) or bool(r.get('floor_prior_active')) for r in raw)
    complete=(grouped['audit']['incomplete_scene_group_count']==0
              and branch['audit']['incomplete_scene_group_count']==0
              and summary['invalid_restricted_QPs']==0 and len(raw)==42240)
    gate=decide(scene_rows,config,numerical_complete=complete,floor_case_count=floor_count)
    gate.update(raw_cases=2112,metric_rows=len(raw),restricted_solves=21120,
                invalid_restricted_QPs=summary['invalid_restricted_QPs'],NRMSE_floor_rows=floor_count,
                frozen_QP_validation=summary['common_reproduction'].get('validation_maxima'),
                explicit_protocol_conflict='REPRODUCTION_CONFLICT_ADDENDUM.md')
    equality=split_projector_audit(root)
    gate['primary_A2_A3_same_selected_index_sets']=all(r['same_selected_index_set'] for r in equality if r['k']==16 and r['first']=='A2')
    write_json(out/'GATE_DECISION.json',gate)
    _bootstrap_raw(root,scene_rows)
    from .chart_audit import build_chart_audit
    chart=build_chart_audit(root)
    write_json(out/'CHART_EXTERIOR_AUDIT.json',chart)
    from .plots import render_plots
    figures=render_plots(root,scene_rows,comparison)
    paid=cost_summary(root,config)
    _write_documents(root,config,summary,gate,scene_rows,comparison,chart,paid)
    qps=[r['qp'] for r in raw if r['test']=='B' and r['status']=='OK']
    numerical=dict(common_QP_validation=summary['common_reproduction'].get('validation_maxima'),
            restricted_valid_QPs=len(qps),restricted_invalid_QPs=summary['invalid_restricted_QPs'],
            max_restricted_KKT_relative=max(q['kkt_relative'] for q in qps),
            max_restricted_feasibility_violation=max(q['feasibility_violation'] for q in qps),
            max_restricted_complementarity=max(q['complementarity'] for q in qps),
            existing_validated_active_equation_polishes=sum(bool(q.get('validated_active_equations')) for q in qps),
            max_prior_component_norm=max(r['prior_coefficient_norm'] for r in raw if r['test']=='B' and r['status']=='OK'),
            NRMSE_floor_rows=floor_count,
            undefined_primary_metric_rows=sum(any(r.get(name) is None for name in DEFAULT_METRICS) for r in raw),
            max_projector_completeness_residual=max(r['projector_completeness_residual'] for r in raw),
            max_energy_identity_residual=max(max(r['error_energy_identity_residual'],r['signal_energy_identity_residual']) for r in raw),
            warning='Original solver emitted ill-conditioned active-KKT matrix LinAlgWarnings. No jitter/pinv/solver rewrite was used. Every returned restricted point still passed the original final audits.',
            numerical_warning_count='NOT_SAVED_BY_INITIAL_FOREGROUND_REPLAY',
            source_audit='research/delegated/a22-r1-cache-audit/PLATFORM_REPRODUCTION_AUDIT.md')
    write_json(out/'NUMERICAL_AUDIT.json',numerical)
    freeze=_json(out/'SPLIT_FREEZE.json'); offline=_json(out/'OFFLINE_SPLIT_FREEZE.json')
    write_json(out/'SOURCE_AND_COMMAND_MANIFEST.json',dict(frozen_A22_commit=config['source_commit'],
        implementation_branch='a22-r1-subspace-separation',source_manifest_stage='final_commit_in_START_HERE',
        protocol_commit='c4d70bd',explicit_addendum_commit='7d29bd5',cached_QP_validation_commit='ca709e6',
        commands=['python -B -m a22_r1.cli freeze --job a22-r1-freeze-001 --device cuda',
                  'python -B -m a22_r1.cli replay --job a22-r1-replay-001',
                  'python -B -m a22_r1.cli replay --job a22-r1-replay-windows-001',
                  'python -B -m a22_r1.cli replay-cached --job a22-r1-replay-cached-001',
                  'python -B -m a22_r1.cli report --job a22-r1-report-001'],
        online_freeze=freeze,offline_diagnostic_freeze=offline,
        random_seed=20261910,bootstrap_seed=20261911,noise_seed=[20261007,'scene','direction','amplitude_level','noise_draw',661],
        frozen_background='.1+.04j',material_chart='32 real mass-normalized coefficients',
        precision='complex128/float64',OPM='U8/O4/P4/M4 degree1 rank32',
        private_config_contents='EXCLUDED',new_SHA256_checks=0,
        report_environment=dict(python=platform.python_version(),platform=platform.platform())))
    return dict(scientific_case=gate['scientific_case'],gates=gate['gates'],
        primary_A3=gate['methods']['A3'],A3_vs_A2=gate['bootstrap'],
        independent_scenes=4,figures=len(figures['figures']),invalid_QPs=summary['invalid_restricted_QPs'],
        raw_metric_rows=len(raw),all_secondary_metrics_preserved=True,NN='NOT_RUN',next_action='STOP_AND_REPORT')


def _write_documents(root,config,summary,gate,scenes,comparison,chart,paid):
    case=gate['scientific_case']; a3=gate['methods']['A3']; boot=gate['bootstrap']
    common='''本实验只检验已知背景 `0.1+0.04i` 下、固定32维质量归一材料图中的分离。四个对象全部历史暴露；2001/2003是Gaussian，2014为非Gaussian/asymmetric分段材料，2009为多尺度shell。统计单位只有四个scene，不能把2112个noise/方向案例作为独立对象。没有NN、nonlinear GN/DBIM、新标签、rank/degree搜索或自动扩展。'''
    conflict='''旧标量严格复现仍为FAILED：Mac104/2112、原Windows26/2112不匹配。Test A/B使用整组Windows共同向量，先重验同一个缓存quadratic、可行域、保存normal及原KKT；2112/2112有效。选择平台与这项处理在查看split结果前登记。参见[显式补充](REPRODUCTION_CONFLICT_ADDENDUM.md)和[source audit](research/delegated/a22-r1-cache-audit/PLATFORM_REPRODUCTION_AUDIT.md)。不能把本报告称为bitwise旧Stage A复现。'''
    meanings='''NRMSE使用投影真值范数，floor为1e-6并单独标记；q和能量比例使用原始能量，不加epsilon。S_sep是prior/physics NRMSE；q_phys<1表示物理子空间的误差份额低于信号份额，q_prior>1相反。逐case的S_sep²=q_prior/q_phys（floor不激活时）成立；逐scene平均后不能再对这些均值强行套同一等式。所有图内误差均与图外真值分开。'''
    lines=['| scene | 方法 | physics NRMSE | prior NRMSE | S_sep | q_phys | q_prior | truth_phys |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for sid in SCENES:
        for method in METHODS:
            row=next(r for r in scenes if r['scene']==sid and r['method']==method and r['k']==16 and r['test']=='A')
            lines.append('| '+str(sid)+' | '+method+' | '+' | '.join(_fmt(row[n]) for n in
              ('nrmse_phys','nrmse_prior','s_sep','q_phys','q_prior','f_truth_phys'))+' |')
    paired=['| scene | A2 physics NRMSE | A3 physics NRMSE | A3相对改善 |', '|---|---:|---:|---:|']
    for sid in SCENES:
        values=[next(r['nrmse_phys'] for r in scenes if r['scene']==sid and r['method']==m and r['k']==16 and r['test']=='A') for m in ('A2','A3')]
        ratio=1-values[1]/values[0] if all(v is not None and v>0 for v in values) else None
        paired.append('| '+str(sid)+' | '+_fmt(values[0])+' | '+_fmt(values[1])+' | '+_fmt(ratio)+' |')
    branch=['| 方法 | restricted/common median scene ratio | S4 |', '|---|---:|---|']
    for method in METHODS:
        m=gate['methods'][method];branch.append('| '+method+' | '+_fmt(m['median_restricted_over_common'])+' | '+m['S4']+' |')
    interpretation={
      'CASE_A_A3_SPLIT_WORKS':'冻结A3支持图内分离筛查，并满足相对A2的预注册增量与受限分支条件。它仍不能证明新对象上可靠，也不能启动本实验中的NN。',
      'CASE_C_A2_MATCHES_OR_BEATS_A3':'在本筛查中，A2达到相对分离筛查阈值，而A3没有达到预注册15%的增量；不能把O/P/M标签宣称为构造该split所必需。停止NN，保留更简单的物理编码对照。',
      'CASE_B_SPLIT_EXISTS_A3_DOES_NOT_FIND_IT':'冻结full-J离线诊断支持有用分离，但A3未达到完整条件。分离并非因此被否定；当前廉价A3估计器的作用不足。停止NN。',
      'CASE_D_NO_USEFUL_SUBSPACE_SEPARATION':'在当前背景、有限幅度/噪声/校准条件、32维图及同一候选坐标中，注册的split未共同满足分离、信号覆盖与稳定受限恢复。停止把这个hard split交给prior-only NN；这不等于证明所有物理/先验分解在所有状态上不可能。',
      'INCOMPLETE':'前置数值或覆盖条件不足，不能强行选取支持性结论或宣判普遍失败；停止并保留缺口。'}[case]
    start=f'''# A22-R1 直接 physics/prior 分离实验

**裁决：{case}。** {interpretation}

{common}

主k=16的A3：S_sep场景中位数 **{_fmt(a3['Test_A_scene_medians']['s_sep'])}**，q_phys **{_fmt(a3['Test_A_scene_medians']['q_phys'])}**，q_prior **{_fmt(a3['Test_A_scene_medians']['q_prior'])}**，truth_phys **{_fmt(a3['Test_A_scene_medians']['f_truth_phys'])}**。相对A2的等场景平均physics NRMSE改善 **{_fmt(boot['relative_improvement_of_means'])}**；2000次四scene配对bootstrap区间 `{boot['relative_improvement_of_means_ci95']}`。S1/S2/S3/S4：`{gate['gates']}`。这些是screening SUPPORT/FAIL，没有formal PASS。

physics NRMSE中位数仍为 **{_fmt(a3['Test_A_scene_medians']['nrmse_phys'])}**；相对分离不等于低绝对误差，不能据此宣称物理分支已经可靠成像。A2/A3在主k16是否选取相同候选集合：`{gate['primary_A2_A3_same_selected_index_sets']}`，详见[projector audit](results/a22_r1/SPLIT_PROJECTOR_EQUALITY.csv)。若集合相同，零增量是同一投影的结果，不是四scene上的一般无效性证明。

{_table(comparison)}

{conflict}

## 阅读顺序

1. [冻结协议](SUBSPACE_SEPARATION_PROTOCOL.md)及[split来源](SPLIT_DEFINITION_AUDIT.md)
2. [共同解误差定位](ONE_SHOT_ERROR_LOCALIZATION.md)
3. [真实受限分支](RESTRICTED_PHYSICS_BRANCH.md)
4. [图外能量](CHART_EXTERIOR_AUDIT.md)
5. [机器判决](results/a22_r1/GATE_DECISION.json)、[四scene指标](results/a22_r1/PER_SCENE_SPLIT_METRICS.csv)、[方法比较](results/a22_r1/SPLIT_COMPARISON.csv)
6. [费用](results/a22_r1/COST_SUMMARY.json)、[失败账本](results/a22_r1/FAILURE_LEDGER.jsonl)、[原始输出入口](results/a22_r1/REPLAY_SUMMARY.json)

## 证据边界

原理论包已经给出的是条件性的线性recoverability/attribution论证；本实验不重做理论。单元与identity tests验证实现，不能代替Maxwell实验。真实Maxwell证据来自既有32个clean有限幅度label与四个付费背景重建。full-J只在在线split全部冻结之后用于OFFLINE诊断。可部署证据仅限已知背景的缓存OPM及一次受约束材料解，未测未知背景或真正端到端time-to-image；rank32不构成部署加速。

保存2112个共同32D向量、21120个受限向量和42240条split指标。四个背景重建不可避免，因为旧缓存缺y0与完整descriptor映射；新full-wave label数为0，cache replay物理调用为0。费用以[COST_LEDGER](results/a22_r1/COST_LEDGER.jsonl)唯一inclusive receipts为准，失败/重跑没有删除，nested actions不重复加账。历史A22账本保持冻结。

## 图和复现

图A–F的PNG/SVG及原始数据在[figures](figures/A22_R1/PLOT_MANIFEST.json)。缓存入口、参数、seeds、source记录在[SOURCE_AND_COMMAND_MANIFEST](results/a22_r1/SOURCE_AND_COMMAND_MANIFEST.json)。运行 `PYTHONPATH=src python -B -m a22_r1.cli report --job a22-r1-report-NEW` 重新汇总现有缓存；不要重跑freeze或生成label。新的job名称必须唯一。

本地交付；未自动publish、扩展场景、启动NN或下一阶段。
'''
    (root/'A22_R1_START_HERE.md').write_text(start,encoding='utf-8')
    localization=f'''# One-shot共同解误差定位

**{case}。** {interpretation}

{common}

{meanings}

## Test A主比较，k=16

{_table(comparison)}

每case共同32D解只算一次，所有方法投影相同误差；不按方法换optimizer。noise draws先平均，再等权平均每scene的48个方向×幅度×noise×intervention条件。k8仅作固定稳健性检查，不选k。完整绝对误差、分母、fraction、floor和identity residual保存在原始JSONL。

{chr(10).join(lines)}

## A2/A3配对

{chr(10).join(paired)}

主要点估计 `1-mean_scene(A3 NRMSEphys)/mean_scene(A2 NRMSEphys)={_fmt(boot['relative_improvement_of_means'])}`；四scene配对bootstrap95%区间 `{boot['relative_improvement_of_means_ci95']}`。不是在2112案例上bootstrap。阈值15%不因区间或家族结果放宽。

冻结A2/A3在主k16的候选集合相同：`{gate['primary_A2_A3_same_selected_index_sets']}`。逐scene/k的index、Jaccard和projector差在[SPLIT_PROJECTOR_EQUALITY](results/a22_r1/SPLIT_PROJECTOR_EQUALITY.csv)。排序顺序可不同，但Test A的子空间projector相同；bootstrap中的machine-level零差不能当作独立新场景上的等效性证明。当前有限幅度、噪声与校准条件下physics NRMSE绝对值仍较大。

{conflict}

## 限制

S_sep很大仍可能是两侧都不准确，必须与绝对NRMSE、q、signal coverage及Test B同时读。full-J按固定候选方向的regularized witness预算排序，不是按真值择优，也未旋转成一个任意最优LIS；其失败不能证明所有hard splits均不可能。图外材料属于chart-exterior，绝不作为图内V_prior失败。
'''
    (root/'ONE_SHOT_ERROR_LOCALIZATION.md').write_text(localization,encoding='utf-8')
    restricted=f'''# 受限physics-only分支

**{case}；NN与扩展仍为NOT_RUN。**

Test B对每个冻结split直接解 `min ||d-AW V_phys a||² + lambda||a||²`，`V_prior=0`。每方法显式使用原full-scene lambda，而不是重新由restricted A定标。Gaussian/voxel像素可行域仍由原32D mass chart映射：Re chi>=-0.5、Im chi>=0；original solver/SLSQP、exact redundant-row compression、active-equation检查、feasibility/KKT阈值保持原样。无post clipping、jitter、pinv或Maxwell fallback。

21120个受限QP，invalid `{summary['invalid_restricted_QPs']}`。原solver在active-KKT解上发出ill-conditioned matrix警告；不隐瞒，不改solver。所有返回的点仍通过原最终合同，详细结果见[NUMERICAL_AUDIT](results/a22_r1/NUMERICAL_AUDIT.json)及每case QP字段。

{chr(10).join(branch)}

S4按每scene restricted physics NRMSE均值 / common projection physics NRMSE均值，再取四scene中位数；不是把所有draw视为独立数据或先筛掉失败。Test B的prior NRMSE=1源于prior被置零，不能拿其S_sep或q当作Test A分离证据。

## Test B主表（用于实际分支误差）

{_table(comparison,test='B')}

线性白化data residual、small-solve measured wall/CPU、prior coefficient leakage在[RESTRICTED_BRANCH_RUNTIME_AND_DATA.csv](results/a22_r1/RESTRICTED_BRANCH_RUNTIME_AND_DATA.csv)。完整nonlinear residual为NOT_RUN，未启动任何new nonlinear solve。受限分支在Mac上执行，common archive来自原Windows；差异及阈值保留见[补充](REPRODUCTION_CONFLICT_ADDENDUM.md)。
'''
    (root/'RESTRICTED_PHYSICS_BRANCH.md').write_text(restricted,encoding='utf-8')
    split='''# Split definition / information audit

所有方法都在原 `online_split_16.npz` 中 `[V_phys,V_prior]` 的有符号、完整32列基底上选列。材料W/体积metric、六源逐源Re/Im packing、known background、whitening与lambda固定。RANDOM用单个固定排列，k8/k16嵌套；没有dense k sweep。

A1/A2/A3原公式、原预算和descriptor不变。旧缓存没有32方向预算，因此只补全同一个候选池；冻结排序条件是amplitude0/noise1/nominal，不据恢复误差定条件、不拟合校准器。raw预算越小排名越前，按candidate index稳定打破并列。声明的有限材料prior半径仍在预算中，不能称为零先验测试。

在线builder只能读取已知几何/背景、合法测量/配置及OPM因子，拒读truth、full-J/H、full gradient、GN optimum、teacher。此处split不依据truth或full32恢复输出。全局online freeze后才读取旧label和fullJ到独立offline evaluator。OFFLINE_FULL_J以full-J regularized witness预算对同一32候选排序，明确不是deployable。没有为fullJ再生成任何数据。

完整indices、raw scores、scope、随机种子与cache来源在[SPLIT_FREEZE](results/a22_r1/SPLIT_FREEZE.json)、[OFFLINE freeze](results/a22_r1/OFFLINE_SPLIT_FREEZE.json)及相应NPZ。Window/Mac的offline浮点平台变体单独保留在platform_variants，不覆盖冻结online split。需要按候选frame限制解释结果，不能将OFFLINE诊断等同任意优化LIS。

Test A先读取整组固定共同解；Test B保持同一个物理目标/原lambda，仅限制解空间。拒读、预算、packing、noise方差1/2、零分母、QP失败与旧源码不变均有测试。任何正规新验证/训练要重新审计数据边界，本experiment不自动执行。

严格历史标量复现失败保留；explicit处理见[REPRODUCTION_CONFLICT_ADDENDUM](REPRODUCTION_CONFLICT_ADDENDUM.md)，在split指标之前提交，S1–S4与评分完全未改。
'''
    (root/'SPLIT_DEFINITION_AUDIT.md').write_text(split,encoding='utf-8')
    chart_lines=['| scene | 原对象图内能量 | 原对象图外能量 | 有限幅度案例图内能量范围 |',
                 '|---|---:|---:|---|']
    for item in chart['per_scene_summary']:
        frac=item['original']['chart_retained_energy_fraction']
        chart_lines.append('| '+str(item['scene'])+' | '+_fmt(frac)+' | '+_fmt(1-frac)+' | '
            +_fmt(item['finite_retained_energy_fraction_min'])+' – '+_fmt(item['finite_retained_energy_fraction_max'])+' |')
    (root/'CHART_EXTERIOR_AUDIT.md').write_text('''# Chart-exterior audit

材料扰动严格分成 `chi-chi0 = W x + chi_outside_W`。W是固定质量正交32维实chart；本实验中的V_prior只是W内部的补空间，不包含chi_outside_W。

'''+ '\n'.join(chart_lines)+'''

这些比例是原对象相对已知背景的material energy，不是重建成功率。finite cases继承原材料并加W内扰动，因此覆盖会变化，但图外部分保持原样。audit共有4个原对象+32个finite labels，projection、orthogonality和能量identity一致。原始值见[CHART_EXTERIOR_RAW.csv](results/a22_r1/CHART_EXTERIOR_RAW.csv)及[JSON](results/a22_r1/CHART_EXTERIOR_RAW.json)。

完整finite材料向量未独立保存；这里按已保存的original_material与perturbation_coefficients生成规则核验，没有声称这是独立新full-wave证据。它只隔离已有chart外误差，不对图内split提供额外评分或使用truth选方向。

已有full-wave data仍包含原对象的chart-exterior材料。把它的能量排除出V_prior指标，不能消除它对测量和图内恢复的散射影响；这里没有生成W-only新labels来隔离这种污染。因此结果属于实际既有有限幅度/噪声/校准条件下的图内恢复，不是消除了所有图外nuisance的内在可识别性定理。

Gaussian chart只覆盖约46–49%，2014约5.8%，shell约13.4%；即使一个图内split有效也不能据此宣称完整原对象成像有效。图外能量不能被算作V_prior失败，任何完整图像主张需另行扩展材料chart并独立验证；本experiment不自动做这件事。
''',encoding='utf-8')
    (root/'A22_R1_GATE_DECISION.md').write_text(f'# A22-R1 screening decision\n\n**{case}**。{interpretation}\n\nS1–S4：`{gate["gates"]}`。独立scene数为4，formal PASS=false。\n\n历史scalar复现FAILED单独保留；同一冻结QP合同有效后才执行直接split诊断。NN、自动扩展、nonlinear reconstruction、publish均NOT_RUN。详细定义和机器指标在[START](A22_R1_START_HERE.md)及[GATE_DECISION](results/a22_r1/GATE_DECISION.json)。\n',encoding='utf-8')
