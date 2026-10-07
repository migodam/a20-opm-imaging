"""Explicit local-to-XINAN transfer of four evaluator-only A22 truth inputs.

This transport is separate from the online deployment whitelist.  It reads an
external private connection configuration only after an explicit deploy call;
connection values and raw SSH diagnostics are never printed or copied.
"""
from __future__ import annotations

import time
PROCESS_WALL = time.perf_counter()

import argparse
import ast
import importlib.util
import inspect
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCREENING_IDS = (2001, 2003, 2014, 2009)
NAMESPACE = "data/a22/offline_eval"
SCHEMA = "a22.offline_screening_evaluation.v1"
MEMBERS = tuple(NAMESPACE+"/scene_"+str(sid)+".npz" for sid in SCREENING_IDS)+(NAMESPACE+"/MANIFEST.json",)
sys.path.insert(0, str(ROOT/"src"))


def _child_cpu():
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        return float(usage.ru_utime+usage.ru_stime)
    except ImportError:
        return 0.


def _truth_header(file):
    """Inspect only the truth NPY header; never load or reconstruct the label."""
    with zipfile.ZipFile(file) as archive:
        if archive.namelist() != ["truth.npy"]:
            raise ValueError("EVALUATOR_NPZ_MUST_HAVE_EXACTLY_ONE_TRUTH_MEMBER")
        entry = archive.getinfo("truth.npy")
        if stat.S_ISLNK(entry.external_attr >> 16):
            raise ValueError("EVALUATOR_NPY_SYMLINK_IS_FORBIDDEN")
        with archive.open(entry) as stream:
            if stream.read(6) != b"\x93NUMPY":
                raise ValueError("INVALID_EVALUATOR_NPY_MAGIC")
            version = stream.read(2)
            if len(version) != 2 or version[0] not in (1, 2, 3):
                raise ValueError("INVALID_EVALUATOR_NPY_VERSION")
            width = 2 if version[0] == 1 else 4
            encoded_length = stream.read(width)
            if len(encoded_length) != width:
                raise ValueError("TRUNCATED_EVALUATOR_NPY_HEADER")
            length = int.from_bytes(encoded_length, "little")
            if length > 65536:
                raise ValueError("EVALUATOR_NPY_HEADER_TOO_LARGE")
            text = stream.read(length)
            if len(text) != length:
                raise ValueError("TRUNCATED_EVALUATOR_NPY_HEADER")
            header = ast.literal_eval(text.decode("utf-8" if version[0] == 3 else "latin1"))
            if (not isinstance(header, dict) or tuple(header.get("shape", ())) != (12**3,)
                    or header.get("descr") not in ("<c16", "=c16", ">c16")):
                raise ValueError("EVALUATOR_LABEL_MUST_BE_COMPLEX128_SOLVER_N12")
            if entry.file_size-stream.tell() != (12**3)*16:
                raise ValueError("EVALUATOR_NPY_PAYLOAD_LAYOUT_MISMATCH")
            return dict(shape=[12**3], dtype="complex128", arrays_loaded=False)


def _manifest_contract(value):
    if (value.get("schema") != SCHEMA or value.get("capability") != "OFFLINE_EVALUATOR_ONLY"
            or value.get("online_use_allowed") is not False
            or value.get("allowed_npz_members") != ["truth"]
            or tuple(value.get("scene_ids", ())) != SCREENING_IDS
            or value.get("asset_root_relative") != NAMESPACE
            or value.get("finite_perturbation_center") != "actual_object_solver_grid_material"):
        raise ValueError("INVALID_OFFLINE_EVALUATION_TRANSFER_MANIFEST")
    rows = value.get("scenes", [])
    if len(rows) != 4 or tuple(row.get("scene_id") for row in rows) != SCREENING_IDS:
        raise ValueError("OFFLINE_EVALUATION_TRANSFER_OBJECT_SET_CHANGED")
    for row in rows:
        if (row.get("source") != "scene_"+str(row["scene_id"])+".npz"
                or row.get("saved_truth_shape") != [12**3] or row.get("solver_n") != 12
                or row.get("data_generation_n_declared") != 14
                or row.get("online_use_allowed") is not False):
            raise ValueError("OFFLINE_EVALUATION_TRANSFER_LAYOUT_CHANGED")
    return value


def evaluation_members(root=ROOT):
    """An exact five-file allowlist; no source mixed NPZ or online config."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    for name in MEMBERS:
        path = root
        for part in name.split("/"):
            path = path/part
            if path.is_symlink():
                raise ValueError("OFFLINE_EVALUATION_TRANSFER_SYMLINK_IS_FORBIDDEN")
        if not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError("OFFLINE_EVALUATION_TRANSFER_INPUT_IS_MISSING_OR_OUTSIDE_ROOT")
    _manifest_contract(json.loads((root/(NAMESPACE+"/MANIFEST.json")).read_text(encoding="utf-8")))
    for name in MEMBERS[:-1]:
        _truth_header(root/name)
    return MEMBERS


def _helper(root):
    source = Path(root)/"tools/a22_remote_jobs.py"
    module_name = "a22_private_evaluation_transport_"+uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(module_name, source)
    if spec is None or spec.loader is None:
        raise ImportError("A22_PRIVATE_TRANSPORT_HELPER_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _remote_code(helper, archive_relative):
    # Reuse the identical bounded header/manifest validators remotely.  Source
    # injection here is our own code, not executable content from an archive.
    validators = inspect.getsource(_truth_header)+"\n"+inspect.getsource(_manifest_contract)
    return f"""import ast,io,json,pathlib,stat,time,uuid,zipfile
root=pathlib.Path(r'{helper.REMOTE}').resolve()
SCREENING_IDS={SCREENING_IDS!r}
NAMESPACE={NAMESPACE!r}
SCHEMA={SCHEMA!r}
MEMBERS={MEMBERS!r}
archive=root/{archive_relative!r}
row=dict(status='FAILED',capability='OFFLINE_EVALUATOR_ONLY',online_use_allowed=False,
         remote_namespace=NAMESPACE,members=0,private_files_transferred=False,
         original_mixed_npz_transferred=False,arrays_loaded=False,new_integrity_hash_checks=0)
{validators}
try:
 if pathlib.Path(r'{helper.SHARED_LOCK}').exists(): raise RuntimeError('SHARED_GPU_LOCK_EXISTS')
 destination=root
 for part in NAMESPACE.split('/'):
  destination=destination/part
  if destination.is_symlink(): raise ValueError('EVALUATOR_NAMESPACE_SYMLINK_IS_FORBIDDEN')
 plan=[]
 with zipfile.ZipFile(archive) as zipped:
  entries=zipped.infolist()
  if len(entries)!=len(MEMBERS) or set(entry.filename for entry in entries)!=set(MEMBERS): raise ValueError('EVALUATOR_ARCHIVE_MUST_MATCH_EXACT_FIVE_FILE_ALLOWLIST')
  for entry in entries:
   if entry.is_dir() or stat.S_ISLNK(entry.external_attr>>16): raise ValueError('EVALUATOR_ARCHIVE_MEMBER_TYPE_FORBIDDEN')
   payload=zipped.read(entry)
   if entry.filename.endswith('.npz'):
    _truth_header(io.BytesIO(payload))
   else:
    _manifest_contract(json.loads(payload))
   path=root/entry.filename
   if path.is_symlink(): raise ValueError('EVALUATOR_TARGET_SYMLINK_IS_FORBIDDEN')
   if path.exists():
    if path.read_bytes()!=payload: raise ValueError('IMMUTABLE_EVALUATOR_INPUT_CONFLICT')
   else:
    plan.append((path,payload))
  # Validate the whole archive and every immutable destination before writing.
  for path,payload in plan:
   path.parent.mkdir(parents=True,exist_ok=True)
   temporary=path.with_name('.'+path.name+'.incoming-'+uuid.uuid4().hex)
   try:
    temporary.write_bytes(payload)
    temporary.replace(path)
   finally:
    temporary.unlink(missing_ok=True)
 row.update(status='A22_OFFLINE_EVALUATION_INPUTS_DEPLOYED',members=len(MEMBERS),
            files_written=len(plan),files_reused=len(MEMBERS)-len(plan))
except BaseException as error:
 row['error_type']=type(error).__name__
finally:
 archive.unlink(missing_ok=True)
 row['remote_process_cpu_seconds']=time.process_time()
 print(json.dumps(row,allow_nan=False))
"""


def deploy(private_config, *, root=ROOT):
    """Explicit transport only.  Call through main for external CPU accounting."""
    root = Path(root).resolve()
    members = evaluation_members(root)
    helper = _helper(root)
    remote_cpu = 0.
    details = dict(capability="OFFLINE_EVALUATOR_ONLY", online_use_allowed=False,
                   remote_namespace=NAMESPACE, member_count=len(members),
                   private_files_transferred=False, original_mixed_npz_transferred=False,
                   new_integrity_hash_checks=0, arrays_loaded=False)
    # No connection object exists before the exact input allowlist passes.
    transport = helper.PrivateTransport(private_config, root=root)
    name = "a22-evaluation-upload-"+uuid.uuid4().hex+".zip"
    archive_relative = NAMESPACE+"/.transfer/"+name
    try:
        with tempfile.TemporaryDirectory(prefix="a22-evaluation-inputs-") as directory:
            archive = Path(directory)/name
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
                for member in members:
                    zipped.write(root/member, member)
            details["compressed_bytes"] = archive.stat().st_size
            ready = helper._python(transport, f"""import json,pathlib,time
root=pathlib.Path(r'{helper.REMOTE}').resolve()
if pathlib.Path(r'{helper.SHARED_LOCK}').exists(): raise RuntimeError('SHARED_GPU_LOCK_EXISTS')
directory=root
for part in {NAMESPACE!r}.split('/')+['.transfer']:
 directory=directory/part
 if directory.is_symlink(): raise ValueError('EVALUATOR_TRANSFER_NAMESPACE_SYMLINK_IS_FORBIDDEN')
directory.mkdir(parents=True,exist_ok=True)
print(json.dumps(dict(status='A22_EVALUATOR_TRANSFER_READY',remote_process_cpu_seconds=time.process_time())))
""", timeout=60)
            remote_cpu += float(ready.get("remote_process_cpu_seconds", 0.))
            if ready.get("status") != "A22_EVALUATOR_TRANSFER_READY":
                raise helper.TransportFailure("Remote evaluator input namespace preparation failed")
            transport.copy_to(archive, archive_relative)
            result = helper._python(transport, _remote_code(helper, archive_relative), timeout=60)
            remote_cpu += float(result.get("remote_process_cpu_seconds", 0.))
            safe_fields = ("status", "members", "files_written", "files_reused", "error_type")
            details.update({key: result[key] for key in safe_fields if key in result})
            if result.get("status") != "A22_OFFLINE_EVALUATION_INPUTS_DEPLOYED" or result.get("members") != 5:
                raise helper.TransportFailure("Remote evaluator input deployment failed; paid receipt preserved")
            details["remote_process_cpu_seconds"] = remote_cpu
            return details
    except BaseException as error:
        details["remote_process_cpu_seconds"] = remote_cpu
        error.accounting = details
        raise


def _record(root, details, status, child_before):
    from a22.budget import register_external, write_json
    identity = "a22-evaluation-inputs-transport-"+uuid.uuid4().hex
    remote_cpu = float(details.get("remote_process_cpu_seconds", 0.))
    controller_cpu = time.process_time()
    child_cpu = max(0., _child_cpu()-child_before)
    reserve = .01
    cpu = controller_cpu+child_cpu+remote_cpu+reserve
    receipt = dict(scope=identity, action="offline_evaluation_inputs_deploy", status=status,
                   process_cpu_seconds=cpu, controller_process_cpu_seconds=controller_cpu,
                   local_child_process_cpu_seconds=child_cpu, remote_process_cpu_seconds=remote_cpu,
                   finalization_reserve_seconds=reserve, wall_seconds=time.perf_counter()-PROCESS_WALL,
                   GPU_seconds=0., gpu_occupation_seconds=0., details=details,
                   measurement="local startup/import CPU plus local child CPU and both remote Python transport receipts",
                   new_integrity_hash_checks=0)
    root = Path(root)
    path = root/"results/a22/transport"/(identity+".json")
    write_json(path, receipt)
    register_external(root, identity, cpu, gpu_seconds=0., wall_seconds=receipt["wall_seconds"],
                      receipt=path.relative_to(root).as_posix(), status=status,
                      measurement=receipt["measurement"], counts={"offline_evaluation_transfer_attempts": 1})


def main(argv=None):
    child_before = _child_cpu()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("deploy",))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--private-config", required=True,
                        help="External or ignored private connection file; never copied or printed")
    args = parser.parse_args(argv)
    details, status = {}, "FAILED"
    try:
        details = deploy(args.private_config, root=args.root)
        status = "COMPLETE"
        print(json.dumps(details, allow_nan=False))
        return 0
    except BaseException as error:
        details.update(getattr(error, "accounting", {}))
        # Do not display exception text, traceback, arguments, private paths or
        # raw SSH diagnostics.  The error type is sufficient for paid receipts.
        print("A22 evaluator input transport failed: "+type(error).__name__+"; private details suppressed", file=sys.stderr)
        return 2
    finally:
        try:
            _record(args.root, details, status, child_before)
        except Exception as error:
            print("A22 evaluator input transport accounting failed: "+type(error).__name__+"; private details suppressed", file=sys.stderr)
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
