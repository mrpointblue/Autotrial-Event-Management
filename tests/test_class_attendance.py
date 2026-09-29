from test_workflow import client,setup,post
from test_card_summary import counts
from test_entry_edit import payload


def test_class_defaults_and_per_class_setup(client):
    event=post(client,'events',dict(name='Fünf',event_date='2026-10-01',class_sections={'S1':5,'V1':10}))
    html=client.get(f"/ui/events/{event['id']}/classes").text
    assert 'value="10"' in html and 'value="5"' in html
    from backend.database import SessionLocal
    from backend.models import EventClass
    with SessionLocal() as db:
        assert db.get(EventClass,(event['id'],'V1')).required_sections==10
        assert db.get(EventClass,(event['id'],'S2')).required_sections==5
    assert client.post('/api/events',json=dict(name='Ungültig',event_date='2026-10-01',class_sections={'S1':0})).status_code==422
    assert 'class_sections.S1' in client.get('/ui/events').text


def test_automatic_niw_and_correction_without_manual_driven_input(client):
    event,_,entries=setup(client,count=1,sections=5)
    path=f"/api/entries/{entries[0]['id']}/scores"
    data=dict(version=1,card_status='received',card_summary=dict(error_counts=counts(not_driven=1,helmet=1,seatbelt=1)))
    assert client.put(path,json=data).json()['status']=='complete'
    data['version']=2;data['card_summary']['error_counts']['not_driven']=2
    assert client.put(path,json=data).json()['status']=='niw'
    saved=client.get(f"/api/events/{event['id']}/entries/100").json()
    assert saved['entry']['card_summary']['driven_sections']==3
    assert saved['entry']['card_summary']['auto_niw'] is True
    assert '3 von 5' in saved['entry']['niw_reason']
    assert client.get(f"/api/events/{event['id']}/progress").json()[0]['ready']
    data['version']=3;data['card_summary']['error_counts']['not_driven']=0
    data['niw_reason']=saved['entry']['niw_reason'] # Also safely clears old clients' automatic reason.
    assert client.put(path,json=data).json()['status']=='complete'
    saved=client.get(f"/api/events/{event['id']}/entries/100").json()
    assert not saved['entry']['niw_reason']
    page=client.get(f"/ui/events/{event['id']}/scoring").text
    assert 'name="driven_sections"' not in page


def test_seventy_percent_boundary_class_change_and_count_change(client):
    event,_,entries=setup(client,count=1,sections=10)
    path=f"/api/entries/{entries[0]['id']}/scores"
    data=dict(version=1,card_status='received',card_summary=dict(error_counts=counts(not_driven=3)))
    assert client.put(path,json=data).json()['status']=='complete' # 7/10 = exactly 70%.
    assert client.post(f"/api/events/{event['id']}/classes",json=dict(code='S1',required_sections=5)).status_code==201
    saved=client.get(f"/api/events/{event['id']}/entries/100").json()
    assert saved['required_sections']==5 and saved['entry']['scoring_status']=='niw'
    data['version']=1
    assert client.put(path,json=data).status_code==409
    # Switch to V1 (still ten): automatic NiW must be removed.
    edit=payload(saved['entry'])
    assert client.put(f"/api/entries/{entries[0]['id']}",json=edit).json()['status']=='complete'
    saved=client.get(f"/api/events/{event['id']}/entries/100").json()
    assert saved['required_sections']==10 and saved['entry']['niw_reason']==''
    assert '10 vorgeschriebene Sektionen' in client.get(f"/print/entries/{entries[0]['id']}").text


def test_raw_totals_use_explicit_not_driven_and_preserve_other_niw_reasons(client):
    event,_,entries=setup(client,count=1,sections=5)
    path=f"/api/entries/{entries[0]['id']}/scores"
    data=dict(version=1,card_status='received',card_summary=dict(error1='0',error2='1800',not_driven=2))
    assert client.put(path,json=data).json()['status']=='niw'
    data.update(version=2,niw_reason='Verspätete Abgabe');data['card_summary']['not_driven']=0
    assert client.put(path,json=data).json()['status']=='niw'
    client.post(f"/api/events/{event['id']}/classes",json=dict(code='S1',required_sections=10))
    saved=client.get(f"/api/events/{event['id']}/entries/100").json()['entry']
    assert saved['niw_reason']=='Verspätete Abgabe'
