import os
import tempfile
from decimal import Decimal
os.environ['DATA_DIR']=tempfile.mkdtemp(prefix='autotrial-tests-')
import pytest
from fastapi.testclient import TestClient
from backend.database import Base,engine
from backend.main import app

@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c: yield c

def post(c,path,data):
    if path=='vehicles' and 'hcf' in data: data.update(hcf_mode='manual',hcf_note='Bestandsfahrzeug, Abnahme bestätigt')
    r=c.post('/api/'+path,json=data)
    assert r.status_code==201,r.text
    return r.json()

def setup(c,count=3,sections=2):
    event=post(c,'events',dict(name='Trial',event_date='2026-09-27',section_count=sections))
    vehicle=post(c,'vehicles',dict(manufacturer='Suzuki',model='SJ',class_code='S1',hcf='1.73'))
    entries=[]
    for i in range(count):
        driver=post(c,'drivers',dict(start_number=100+i,name=f'Fahrer {i}'))
        assert c.put(f"/api/drivers/{driver['id']}/vehicles",json=dict(vehicle_id=vehicle['id'],is_default=True)).status_code==200
        entries.append(post(c,f"events/{event['id']}/entries",dict(driver_id=driver['id'],technical_approved=True,paperwork_approved=True)))
    return event,vehicle,entries

def score(c,e,points,**kw):
    return c.put(f"/api/entries/{e['id']}/scores",json=dict(version=e['version'],card_status='received',sections=[dict(points=p) for p in points],**kw))

def test_shared_vehicle_snapshot_defaults_and_unique_entry(client):
    event,vehicle,entries=setup(client)
    assert len({e['vehicle_id'] for e in entries})==1
    data=dict(manufacturer='Suzuki',model='Umbau',class_code='V1',hcf='2.5',hcf_mode='manual',hcf_note='Umbau abgenommen')
    assert client.put(f"/api/vehicles/{vehicle['id']}",json=data).status_code==200
    old=client.get(f"/api/events/{event['id']}/entries/100").json()['entry']
    assert old['vehicle_snapshot']['model']=='SJ' and old['class_code']=='S1'
    assert Decimal(str(old['hcf']))==Decimal('1.73')
    assert client.post(f"/api/events/{event['id']}/entries",json=dict(driver_id=entries[0]['driver_id'])).status_code==409
    assert client.post('/api/drivers',json=dict(start_number=100,name='Duplicate')).status_code==409

def test_unordered_scoring_zero_missing_niw_and_print(client):
    event,_,entries=setup(client)
    assert score(client,entries[2],[0,0]).status_code==200
    assert score(client,entries[0],[0,None]).status_code==200
    progress=client.get(f"/api/events/{event['id']}/progress").json()[0]
    assert progress['complete']==1 and len(progress['missing'])==2
    assert client.get(f"/print/events/{event['id']}/S1").status_code==409
    assert client.put(f"/api/entries/{entries[1]['id']}/scores",json=dict(version=1,card_status='missing',niw_reason='Nichtabgabe bestätigt')).status_code==200
    current=client.get(f"/api/events/{event['id']}/entries/100").json()['entry']
    assert score(client,current,[0,0]).status_code==200
    progress=client.get(f"/api/events/{event['id']}/progress").json()[0]
    assert progress['ready'] and progress['niw']==1 and progress['complete']==3
    assert client.get(f"/print/events/{event['id']}/S1").status_code==200

def test_ties_skip_next_rank_and_decimal_math(client):
    from backend.database import SessionLocal
    from backend.services.scoring import ranked_results
    event,_,entries=setup(client)
    for e,p in zip(entries,[['0.1','0.2'],['0.3','0'],['0.4','0']]): assert score(client,e,p).status_code==200
    with SessionLocal() as db:
        rows=ranked_results(db,event['id'],'S1')
        assert [r['rank'] for r in rows]==[1,1,3]
        assert rows[0]['total']==Decimal('0.3')

def test_validation_threshold_concurrency_and_resave(client):
    event,_,entries=setup(client,count=1,sections=10);e=entries[0]
    data=dict(version=1,card_status='received',sections=[dict(points=0,driven=i<6) for i in range(10)])
    assert client.put(f"/api/entries/{e['id']}/scores",json=data).status_code==422
    data['sections'][6]['driven']=True
    assert client.put(f"/api/entries/{e['id']}/scores",json=data).status_code==200
    assert client.put(f"/api/entries/{e['id']}/scores",json=data).status_code==409
    data['version']=2
    assert client.put(f"/api/entries/{e['id']}/scores",json=data).status_code==200
    data['version']=3;data['sections'][0]['points']=-1
    assert client.put(f"/api/entries/{e['id']}/scores",json=data).status_code==422

def test_pages_and_card_gate(client):
    event,_,entries=setup(client,count=1)
    for path in ['/','/ui/events','/ui/master-data',f"/ui/events/{event['id']}/checkin",f"/ui/events/{event['id']}/scoring",f"/ui/events/{event['id']}/results",f"/print/entries/{entries[0]['id']}"]:
        assert client.get(path).status_code==200,path
    assert client.get('/print/entries/999').status_code==404

def test_default_switch_and_checkin_gate(client):
    event,vehicle,entries=setup(client,count=1)
    e=entries[0]
    second=post(client,'vehicles',dict(manufacturer='Jeep',model='CJ',class_code='V1',hcf='2.1'))
    assert client.put(f"/api/drivers/{e['driver_id']}/vehicles",json=dict(vehicle_id=second['id'],is_default=True)).status_code==200
    links=client.get(f"/api/drivers/{e['driver_id']}/vehicles").json()
    assert len(links)==2 and sum(x['is_default'] for x in links)==1
    assert next(x for x in links if x['is_default'])['vehicle']['id']==second['id']
    state=dict(version=1,paid=False,technical_approved=False,paperwork_approved=True)
    assert client.put(f"/api/entries/{e['id']}/checkin",json=state).status_code==200
    assert client.get(f"/print/entries/{e['id']}").status_code==409
    state.update(version=2,technical_approved=True)
    assert client.put(f"/api/entries/{e['id']}/checkin",json=state).status_code==200
    assert client.get(f"/print/entries/{e['id']}").status_code==200

def test_invalid_card_and_class_inputs(client):
    event,_,entries=setup(client,count=1)
    e=entries[0]
    assert score(client,e,[1]).status_code==422
    assert client.put(f"/api/entries/{e['id']}/scores",json=dict(version=1,card_status='missing',sections=[dict(points=0),dict(points=0)])).status_code==422
    assert client.post('/api/vehicles',json=dict(manufacturer='X',model='Y',class_code='unknown',hcf=1)).status_code==422
    assert client.post('/api/vehicles',json=dict(manufacturer='X',model='Y',class_code='S1',hcf=0)).status_code==422
    assert client.get('/print/events/999/S1').status_code==404
