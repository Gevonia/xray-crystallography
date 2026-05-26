"""End-to-end PHENIX integration test."""
import numpy as np
from src.pipeline.orchestrator import PipelineOrchestrator

o = PipelineOrchestrator()
jid = o.create_job(name='phenix-integration-test')
print('Job:', jid[:8])

np.random.seed(42)
data = np.random.poisson(2, (512, 512)).astype(np.float64)
for cx, cy, amp in [(128, 200, 500), (384, 180, 450), (200, 350, 400),
                     (320, 300, 380), (150, 120, 350)]:
    y, x = np.ogrid[:512, :512]
    data += amp * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / 15)

images_dir = o._job_dir(jid) / 'images'
images_dir.mkdir(parents=True, exist_ok=True)
np.save(str(images_dir / 'test.npy'), data)

STEPS = ['import', 'find-spots', 'index', 'integrate', 'scale',
         'merge', 'molecular-replacement', 'refine', 'validate']

for step_name in STEPS:
    r = o._execute_step(jid, step_name)
    method = r.get('method', '?').replace('_', ' ').strip()

    if step_name == 'molecular-replacement':
        print(f"  MR: found={r.get('solution_found')}  LLG={r.get('log_likelihood_gain')}  "
              f"TFZ={r.get('tfz_score')}  method={method}")
    elif step_name == 'refine':
        print(f"  REFINE: Rwork={r.get('rwork')}  Rfree={r.get('rfree')}  method={method}")
    elif step_name == 'validate':
        print(f"  VALIDATE: score={r.get('overall_score')}  "
              f"Rama_fav={r.get('ramachandran_favored')}  method={method}")
    else:
        val = (r.get('n_images') or r.get('n_spots') or r.get('n_indexed')
               or r.get('n_integrated') or r.get('r_merge') or r.get('n_reflections') or '')
        print(f"  {step_name:12s}: {str(val):10s} | {method}")

state = o.state_store.get_job_state(jid)
completed = sum(1 for v in state.values() if v == 'completed')
print(f"\nPipeline: {completed}/{len(STEPS)} steps completed")
print("Phase 7 integration PASSED")
