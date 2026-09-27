from decimal import Decimal
from sqlalchemy import select
from backend.database import SessionLocal
from backend.models import Entry, EntryChange, Vehicle
from test_workflow import client, setup, score, post


def payload(entry,**changes):
    return dict(version=entry['version'],vehicle_id=entry['vehicle_id'],class_code='V1',hcf='1.73',codriver='Trainer',
                paid=True,technical_approved=True,paperwork_approved=True,reason='Klassenwechsel',**changes)


def test_class_change_updates_progress_results_card_and_audit(client):
    event,vehicle,entries=setup(client,count=2)
    e=entries[0]
    assert score(client,e,[10,20]).status_code==200
    e=client.get(f"/api/events/{event['id']}/entries/100").json()['entry']
    result=client.put(f"/api/entries/{e['id']}",json=payload(e))
    assert result.status_code==200 and result.json()['status']=='complete'
    groups={g['class_code']:g for g in client.get(f"/api/events/{event['id']}/progress").json()}
    assert groups['S1']['total']==1 and not groups['S1']['ready']
    assert groups['V1']['total']==1 and groups['V1']['ready']
    assert 'V1' in client.get(f"/print/entries/{e['id']}").text
    assert client.get(f"/print/events/{event['id']}/V1").status_code==200
    assert client.get(f"/print/events/{event['id']}/S1").status_code==409
    with SessionLocal() as db:
        assert db.get(Vehicle,vehicle['id']).class_code=='S1'
        other=db.get(Entry,entries[1]['id'])
        assert other.class_code=='S1'
        current=db.get(Entry,e['id'])
        assert current.vehicle_snapshot['class_code']=='V1'
        assert [r.points for r in current.results]==[Decimal(10),Decimal(20)]
        audit=db.scalar(select(EntryChange))
        assert audit.before['class_code']=='S1' and audit.after['class_code']=='V1'
    page=client.get(f"/ui/entries/{e['id']}/edit")
    assert page.status_code==200 and 'Änderungsverlauf' in page.text


def test_stale_edit_validation_and_unknown_vehicle(client):
    _,_,entries=setup(client,count=1)
    e=entries[0]; data=payload(e)
    assert client.put(f"/api/entries/{e['id']}",json=data).status_code==200
    assert client.put(f"/api/entries/{e['id']}",json=data).status_code==409
    data.update(version=2,class_code='INVALID')
    assert client.put(f"/api/entries/{e['id']}",json=data).status_code==422
    data.update(class_code='S1',reason=' ')
    assert client.put(f"/api/entries/{e['id']}",json=data).status_code==422
    data.update(reason='Fahrzeugwechsel',vehicle_id=999)
    assert client.put(f"/api/entries/{e['id']}",json=data).status_code==422
    assert client.get('/ui/entries/999/edit').status_code==404
    with SessionLocal() as db: assert len(list(db.scalars(select(EntryChange))))==1


def test_hcf_change_keeps_scores_but_requires_review(client):
    event,_,entries=setup(client,count=1);e=entries[0]
    score(client,e,[10,20])
    e=client.get(f"/api/events/{event['id']}/entries/100").json()['entry']
    data=payload(e);data.update(hcf='1.685')
    changed=client.put(f"/api/entries/{e['id']}",json=data)
    assert changed.status_code==200 and changed.json()['status']=='pending'
    assert client.get(f"/print/events/{event['id']}/V1").status_code==409
    current=client.get(f"/api/events/{event['id']}/entries/100").json()
    assert Decimal(str(current['entry']['hcf']))==Decimal('1.69')
    assert len(current['sections'])==2
    assert score(client,current['entry'],[11,21]).status_code==200
    assert client.get(f"/print/events/{event['id']}/V1").status_code==200


def test_vehicle_switch_snapshots_and_same_vehicle_preserves_technical_data(client):
    event,vehicle,entries=setup(client,count=1);e=entries[0]
    # Later changes in master data must not leak into a class-only entry correction.
    with SessionLocal() as db:
        db.get(Vehicle,vehicle['id']).model='New master model';db.commit()
    assert client.put(f"/api/entries/{e['id']}",json=payload(e)).status_code==200
    current=client.get(f"/api/events/{event['id']}/entries/100").json()['entry']
    assert current['vehicle_snapshot']['model']=='SJ'
    new=post(client,'vehicles',dict(manufacturer='Jeep',model='CJ',class_code='V1',hcf='2'))
    client.put(f"/api/drivers/{e['driver_id']}/vehicles",json=dict(vehicle_id=new['id']))
    data=payload(current);data.update(vehicle_id=new['id'],hcf='2')
    assert client.put(f"/api/entries/{e['id']}",json=data).status_code==200
    current=client.get(f"/api/events/{event['id']}/entries/100").json()['entry']
    assert current['vehicle_snapshot']['model']=='CJ' and current['vehicle_id']==new['id']
