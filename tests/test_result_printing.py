from decimal import Decimal
from test_workflow import client, setup, score
from backend.database import SessionLocal
from backend.models import Entry
from backend.services.scoring import ranked_results


def split_score(client,entry,sections):
    return client.put(f"/api/entries/{entry['id']}/scores",json=dict(version=entry['version'],card_status='received',sections=sections))


def test_raw_errors_use_snapshot_hcf_and_round_only_total(client):
    event,_,entries=setup(client,count=1)
    entry=entries[0]
    response=split_score(client,entry,[dict(error1='0.01',error2='10'),dict(error1='0.01',error2='0')])
    assert response.status_code==200
    with SessionLocal() as db:
        row=ranked_results(db,event['id'],'S1')[0]
        assert row['error1']==Decimal('0.01')
        assert row['error2']==Decimal('10')
        assert row['total']==Decimal('10.01')
    stored=client.get(f"/api/events/{event['id']}/entries/100").json()
    assert Decimal(stored['sections'][0]['error1'])==Decimal('0.01')
    assert '10,01' in client.get(f"/print/events/{event['id']}/S1").text


def test_blank_errors_stay_pending_zero_completes_and_conflicting_values_rejected(client):
    event,_,entries=setup(client,count=1)
    entry=entries[0]
    response=split_score(client,entry,[dict(error1=0),dict(error1=0,error2=0)])
    assert response.json()['status']=='pending'
    entry['version']+=1
    assert split_score(client,entry,[dict(points=1,error1=1,error2=0)]*2).status_code==422
    assert split_score(client,entry,[dict(error1=-1,error2=0)]*2).status_code==422
    assert split_score(client,entry,[dict(error1=0,error2=0)]*2).json()['status']=='complete'


def test_legacy_totals_remain_unsplit_and_can_be_replaced(client):
    event,_,entries=setup(client,count=1)
    entry=entries[0]
    score(client,entry,[10,20])
    with SessionLocal() as db:
        row=ranked_results(db,event['id'],'S1')[0]
        assert row['total']==30 and row['error1'] is None and row['error2'] is None
    entry['version']+=1
    split_score(client,entry,[dict(error1=173,error2=0),dict(points=20)])
    with SessionLocal() as db:
        row=ranked_results(db,event['id'],'S1')[0]
        assert row['total']==120 and row['error1'] is None


def test_all_and_adac_require_all_classes_and_keep_class_rankings(client):
    event,_,entries=setup(client,count=2)
    with SessionLocal() as db:
        db.get(Entry,entries[1]['id']).class_code='V1';db.commit()
    score(client,entries[0],[10,0])
    for mode in ('all','adac'):
        assert client.get(f"/print/events/{event['id']}/{mode}").status_code==409
    assert client.get(f"/print/events/{event['id']}/S1").status_code==200
    score(client,entries[1],[20,0])
    all_html=client.get(f"/print/events/{event['id']}/all").text
    assert all_html.count('<article class="class-report">')==2
    adac=client.get(f"/print/events/{event['id']}/adac")
    assert adac.status_code==200 and adac.text.count('<table ')==1
    assert adac.text.count('<td>650</td>')==2
    assert '27.09.2026' in adac.text and 'ADAC · Gesamtauswertung' in adac.text
    assert client.get('/print/events/999/adac').status_code==404


def test_migrate_old_database_preserves_scores(tmp_path):
    import sqlite3,subprocess,sys,os
    path=tmp_path/'autotrial.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE section_results (id INTEGER PRIMARY KEY, entry_id INTEGER, ordinal INTEGER, points NUMERIC(14,4), driven BOOLEAN)')
        db.execute('INSERT INTO section_results VALUES (1,1,1,42.125,1)')
        db.execute('PRAGMA user_version=1')
    code='from fastapi.testclient import TestClient\nfrom backend.main import app\nwith TestClient(app) as c: assert c.get("/health").status_code==200'
    for _ in range(2):
        subprocess.run([sys.executable,'-c',code],env={**os.environ,'DATA_DIR':str(tmp_path)},check=True,capture_output=True)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==11
        assert db.execute('SELECT points,error1,error2 FROM section_results').fetchone()==(42.125,None,None)
