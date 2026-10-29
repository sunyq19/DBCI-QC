"""One isolated, reproducible modular execution per process."""
from pathlib import Path
import json
import sys
import traceback

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))


def emit(module_id, status, message):
    print('@@QC@@' + json.dumps({'module_id': module_id, 'status': status, 'message': message}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    job_dir = Path(sys.argv[1]).resolve()
    try:
        from ephys_qc.core import run_job
        request = json.loads((job_dir / 'request.json').read_text())
        result = run_job(request, job_dir, emit)
        temporary = job_dir / 'result.tmp'
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        temporary.replace(job_dir / 'result.json')
    except Exception as exc:
        (job_dir / 'error.json').write_text(json.dumps({'message': str(exc), 'type': type(exc).__name__}, ensure_ascii=False), encoding='utf-8')
        traceback.print_exc()
        sys.exit(1)
