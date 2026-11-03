"""Retries keep operational failures and interruptions separate from game outcomes."""
import json
from scripts.summarize_playground_audit import summarize


def test_retry_retains_script_failure_and_restart_interruption(tmp_path):
    runs=tmp_path/'runs/terraria_survival-505'
    interrupted=runs/'attempt-1';interrupted.mkdir(parents=True)
    (interrupted/'initial-state.json').write_text('{}')
    failed=runs/'attempt-2';failed.mkdir()
    # Historical runner versions recorded exceptions without an errors entry.
    (failed/'result.json').write_text(json.dumps({'game':'terraria_survival','seed':505,
        'started_at':2,'status':'audit_error','error_type':'TimeoutError','errors':[]}))
    active=tmp_path/'runs/terraria_survival-101/attempt-1';active.mkdir(parents=True)
    (active/'initial-state.json').write_text('{}')
    valid={'game':'terraria_survival','seed':505,'started_at':3,'status':'budget_exhausted',
        'terminal':False,'outcome':'budget_exhausted','model_calls':1200,'errors':[]}
    source=tmp_path/'summary.json'
    source.write_text(json.dumps({'games':['terraria_survival'],'seeds':[101,505],
        'runs':[valid],'active':[{'game':'terraria_survival','seed':101,'artifacts':str(active)}]}))
    result=summarize(source,tmp_path/'analysis')
    row=result['games'][0]
    assert result['completed_runs']==1
    assert row['budget_exhausted']==1 and row['wins']==row['draws']==0
    assert row['failed_attempts']==row['errors']==1 and row['error_requests']==0
    assert row['interrupted_attempts']==1
    assert result['interrupted_attempts']==[{'game':'terraria_survival','seed':505,'artifacts':str(interrupted)}]
