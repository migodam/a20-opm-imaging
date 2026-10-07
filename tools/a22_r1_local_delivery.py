"""Local evidence packaging and presence checks; no experiment execution."""
import time
WALL=time.perf_counter()

import argparse
import gzip
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from a20.costs import write_json
from a22_r1.accounting import R1Book,append
from a22_r1.report import cost_summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--job',required=True)
    args=parser.parse_args()
    config=json.loads((ROOT/'configs/a22_r1.json').read_text())
    book=R1Book(ROOT,config,args.job,started_wall=WALL)
    result={};status='FAILED'
    try:
        required=['A22_R1_START_HERE.md','SUBSPACE_SEPARATION_PROTOCOL.md','SPLIT_DEFINITION_AUDIT.md',
                  'ONE_SHOT_ERROR_LOCALIZATION.md','RESTRICTED_PHYSICS_BRANCH.md','CHART_EXTERIOR_AUDIT.md',
                  'results/a22_r1/SPLIT_COMPARISON.csv','results/a22_r1/PER_SCENE_SPLIT_METRICS.csv',
                  'results/a22_r1/GATE_DECISION.json','results/a22_r1/COST_LEDGER.jsonl','results/a22_r1/FAILURE_LEDGER.jsonl']
        for name in required:
            if not (ROOT/name).is_file():raise ValueError('MISSING_DELIVERY:'+name)
        missing=[]
        with book.span('r1_local_link_and_source_audit',delivery_checks=1):
            for name in required[:6]:
                for target in re.findall(r'\]\(([^)]+)\)',(ROOT/name).read_text()):
                    if not target.startswith(('http:','https:','#')):
                        if not (ROOT/target.strip('<>')).exists():missing.append(dict(document=name,target=target))
            if missing:raise ValueError('BROKEN_LOCAL_DOCUMENT_LINKS:'+json.dumps(missing))
            changed=subprocess.check_output(['git','diff',config['source_commit'],'--name-only','--',
                'src/a20','src/a20_r1','src/a21','src/a22','configs/a22.json','results/a22'],cwd=ROOT,text=True).splitlines()
            if changed:raise ValueError('FROZEN_A22_SOURCE_OR_RESULT_MUTATION:'+str(changed))
            source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        compressed=[]
        for path in sorted((ROOT/'results/a22_r1/replay').glob('*/*')):
            if path.suffix not in ('.jsonl','.csv') or path.stat().st_size<5_000_000:continue
            book.check();dest=Path(str(path)+'.gz')
            with book.span('r1_evidence_gzip_and_exact_byte_roundtrip',evidence_compressions=1):
                if not dest.exists():
                    with path.open('rb') as src,dest.open('wb') as raw:
                        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=6) as out:
                            shutil.copyfileobj(src,out,1024*1024)
                with path.open('rb') as src,gzip.open(dest,'rb') as recovered:
                    while True:
                        a,b=src.read(1024*1024),recovered.read(1024*1024)
                        if a!=b:raise ValueError('EVIDENCE_GZIP_BYTE_CONFLICT:'+str(path))
                        if not a:break
            compressed.append(dict(raw_path=path.relative_to(ROOT).as_posix(),
                compressed_path=dest.relative_to(ROOT).as_posix(),raw_bytes=path.stat().st_size,
                compressed_bytes=dest.stat().st_size,exact_uncompressed_bytes=True,
                original_kept_locally=True,new_SHA256_checks=0))
        gate=json.loads((ROOT/'results/a22_r1/GATE_DECISION.json').read_text())
        if gate['NN']!='NOT_RUN' or gate['expansion']!='NOT_RUN':raise ValueError('UNAUTHORIZED_EXPANSION')
        result=dict(schema='a22_r1.local_delivery.v1',status='COMPLETE',required_files=required,
             source_commit=source_commit,compressed_raw_evidence=compressed,local_link_errors=missing,
             frozen_source_changes=changed,public_pushes=0,NN='NOT_RUN',new_physical_actions=0,
             old_scalar_reproduction='FAILED_RETAINED',scientific_case=gate['scientific_case'])
        write_json(ROOT/'results/a22_r1/DELIVERY_MANIFEST.json',result)
        manifest_path=ROOT/'results/a22_r1/SOURCE_AND_COMMAND_MANIFEST.json'
        manifest=json.loads(manifest_path.read_text())
        manifest['implementation_source_commit']=source_commit
        manifest['delivery_artifact_manifest']='results/a22_r1/DELIVERY_MANIFEST.json'
        write_json(manifest_path,manifest)
        start=ROOT/'A22_R1_START_HERE.md'
        text=start.read_text();marker='\n## 本地代码与压缩证据\n'
        text=text.split(marker)[0]
        start.write_text(text+marker+f'\n实现代码commit：`{source_commit}`。大型逐case原始记录保留在本地；Git保存其字节一致的gzip副本，完整向量另有NPZ。路径与实际字节数见[DELIVERY_MANIFEST](results/a22_r1/DELIVERY_MANIFEST.json)。report入口可以直接读gzip缓存。\n',encoding='utf-8')
        status='COMPLETE'
    except BaseException as error:
        result.update(error=str(error),traceback=traceback.format_exc())
    finally:
        write_json(book.directory/'outcome.json',dict(status=status,detail=result))
        receipt=book.finish(status,result)
        totals=cost_summary(ROOT,config)
    print(json.dumps(dict(status=status,source_commit=result.get('source_commit'),
               compressed_files=len(result.get('compressed_raw_evidence',[])),
               CPU_seconds=receipt['process_cpu_seconds'],R1_CPU_seconds=totals['R1_CPU_including_allowance_seconds'],
               GPU_seconds=totals['R1_GPU_related_occupation_seconds'])))
    return 0 if status=='COMPLETE' else 1


if __name__=='__main__':sys.exit(main())
