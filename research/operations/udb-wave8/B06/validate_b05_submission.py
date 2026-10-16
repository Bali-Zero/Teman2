"""Run the actual committed B05 validator; emit only counts and error digests."""
import argparse, gzip, hashlib, importlib.util, json, pathlib, subprocess, sys
from datetime import datetime, timezone
p=argparse.ArgumentParser()
p.add_argument("--validator-root",type=pathlib.Path,required=True)
p.add_argument("--payload",type=pathlib.Path,required=True)
p.add_argument("--output",type=pathlib.Path,required=True)
args=p.parse_args()
rel="research/operations/udb-wave8/B05/b05_contracts_validator.py"
path=args.validator_root/rel
blob=subprocess.check_output(["git","-C",str(args.validator_root),"show","HEAD:"+rel])
if blob!=path.read_bytes(): raise SystemExit("B06_VALIDATOR_NOT_COMMITTED_BYTES")
spec=importlib.util.spec_from_file_location("actual_committed_b05",path)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
raw=gzip.decompress(args.payload.read_bytes());data=json.loads(raw);valid=set(data["valid_consumer_ids"])
result={"validator_path":rel,"validator_source_sha256":hashlib.sha256(blob).hexdigest(),
"validator_committed_head":subprocess.check_output(["git","-C",str(args.validator_root),"rev-parse","HEAD"],text=True).strip(),
"validator_equals_committed_bytes":True,"input_payload_sha256":hashlib.sha256(raw).hexdigest(),
"runner_source_sha256":hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
"observed_at":datetime.now(timezone.utc).isoformat(),"native_probe_executed":False,
"command":"python -I -B validate_b05_submission.py --validator-root COMMITTED_B05_ROOT --payload b06-validator-payload.json.gz --output B05-VALIDATION.json"}
for group in ("original","additional"):
    counts={};rejected=0;total=0
    for record in data[group]:
        errors=m.validate_operation_instance(record,valid_consumer_ids=valid)
        rejected+=bool(errors);total+=len(errors)
        for error in errors:
            digest=hashlib.sha256(error.encode()).hexdigest()
            counts[digest]=counts.get(digest,0)+1
    result[group]={"records":len(data[group]),"accepted":len(data[group])-rejected,
                   "rejected":rejected,"error_count":total,"error_sha256_counts":counts}
result["exit_code"]=int(any(result[g]["rejected"] for g in ("original","additional")))
args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps({g:result[g] for g in ("original","additional","exit_code")}))
raise SystemExit(result["exit_code"])
