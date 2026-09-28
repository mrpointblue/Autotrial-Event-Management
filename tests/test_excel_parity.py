from decimal import Decimal
from types import SimpleNamespace
import pytest
from test_workflow import client,setup,score,post
from backend.database import SessionLocal
from backend.models import Driver,Entry,EventClass
from backend.services.scoring import score_totals
from backend.main import team_results


def test_error_counts_weighting_and_roundtrip(client):
    event,_,entries=setup(client,count=1,sections=1)
    counts=dict(reverse=3,ball=2,pole=1,foot=1,band=1,exit=2,missed_gate=3,not_driven=0)
    response=client.put(f"/api/entries/{entries[0]['id']}/scores",json=dict(version=1,card_status='received',sections=[dict(error_counts=counts)]))
    assert response.status_code==200
    data=client.get(f"/api/events/{event['id']}/entries/100").json()
    assert data['sections'][0]['error_counts']==counts
    assert Decimal(data['sections'][0]['error1'])==144
    assert Decimal(data['sections'][0]['error2'])==480
    assert '563,24' in client.get(f"/print/events/{event['id']}/S1").text


def test_custom_classes_are_event_scoped_and_protected(client):
    event,_,entries=setup(client,count=1)
    custom=dict(code='Mini Fun',section_group='Sektionen 1–5')
    assert client.post(f"/api/events/{event['id']}/classes",json=custom).status_code==201
    assert client.post(f"/api/events/{event['id']}/classes",json=dict(code='adac')).status_code==422
    second=post(client,'events',dict(name='Anderes Event',event_date='2026-10-01',section_count=1))
    assert client.post(f"/api/events/{second['id']}/entries",json=dict(driver_id=entries[0]['driver_id'],class_code='Mini Fun')).status_code==422
    assert client.delete(f"/api/events/{event['id']}/classes/S1").status_code==409
    assert 'Sektionen 1–5' in client.get(f"/ui/events/{event['id']}/classes").text
    with SessionLocal() as db:
        db.get(Entry,entries[0]['id']).class_code='Mini Fun';db.commit()
    assert 'Mini Fun' in client.get(f"/print/participants/{event['id']}").text
    assert client.delete(f"/api/events/{event['id']}/classes/Mini%20Fun").status_code==409


def test_team_best_three_live_changes_and_pending_classes(client):
    event,_,entries=setup(client,count=5)
    response=client.post(f"/api/events/{event['id']}/teams",json=dict(name='Testteam',start_numbers=[100,101,102,103,104]))
    assert response.status_code==201
    team=response.json()
    assert client.post(f"/api/events/{event['id']}/teams",json=dict(name='Duplikat',start_numbers=[100,100,101])).status_code==422
    assert client.post(f"/api/events/{event['id']}/teams",json=dict(name='Fehlt',start_numbers=[100,101,999])).status_code==422
    for index,entry in enumerate(entries[:4]):score(client,entry,[index,0])
    assert client.get(f"/print/teams/{event['id']}").status_code==409
    score(client,entries[4],[4,0])
    with SessionLocal() as db:
        row=team_results(db,event['id'])[0]
        assert row['total']==2100 and row['rank']==1
        assert [m['entry'].start_number for m in row['members'] if m['counted']]==[100,101,102]
    assert '2100' in client.get(f"/print/events/{event['id']}/all").text
    assert client.put(f"/api/teams/{team['id']}",json=dict(name='Testteam',start_numbers=[102,103,104],version=1)).status_code==200
    assert client.put(f"/api/teams/{team['id']}",json=dict(name='Alt',start_numbers=[100,101,102],version=1)).status_code==409
    with SessionLocal() as db:assert team_results(db,event['id'])[0]['total']==1800
    assert client.get(f"/ui/events/{event['id']}/teams").status_code==200


def test_adac_snapshot_export_and_csv_injection(client):
    event,_,entries=setup(client,count=1)
    with SessionLocal() as db:
        entry=db.get(Entry,entries[0]['id']);entry.driver_snapshot={'address':'Teststraße 1','club':'=FORMEL()','adac_number':'00123','email':'test@example.org'}
        db.get(Driver,entry.driver_id).club='Spätere Änderung';db.commit()
    assert client.get(f"/export/events/{event['id']}/adac.csv").status_code==409
    score(client,entries[0],[0,0])
    response=client.get(f"/export/events/{event['id']}/adac.csv")
    assert response.status_code==200 and "'=FORMEL()" in response.text
    assert 'Spätere Änderung' not in response.text and '00123' in response.text
    printed=client.get(f"/print/events/{event['id']}/adac").text
    assert 'Teststraße 1' in printed and '00123' in printed


# Anonymous numeric reference cases from all 44 competitors in the supplied 2026 workbook.
@pytest.mark.parametrize("hcf,raw1,raw2,expected", [['1.44', '532', '0', '369.44'], ['1.54', '652', '0', '423.38'], ['1.68', '524', '800', '1111.90'], ['1.44', '792', '800', '1350.00'], ['1.44', '652', '1280', '1732.78'], ['1.29', '552', '0', '427.91'], ['1.11', '480', '0', '432.43'], ['1.09', '616', '0', '565.14'], ['1.58', '728', '1120', '1580.76'], ['1', '1060', '0', '1060.00'], ['1.13', '20', '0', '17.70'], ['1.13', '212', '0', '187.61'], ['6.93', '336', '0', '48.48'], ['6.93', '520', '0', '75.04'], ['7.49', '864', '0', '115.35'], ['6.72', '388', '80', '137.74'], ['3.8', '524', '0', '137.89'], ['4.47', '644', '0', '144.07'], ['3.77', '184', '0', '48.81'], ['3.87', '208', '0', '53.75'], ['3.78', '268', '0', '70.90'], ['5.11', '248', '0', '48.53'], ['6.09', '492', '0', '80.79'], ['1.98', '36', '0', '18.18'], ['2.13', '52', '0', '24.41'], ['2.53', '64', '0', '25.30'], ['2.53', '92', '0', '36.36'], ['4.13', '220', '0', '53.27'], ['3.87', '212', '0', '54.78'], ['4.13', '268', '0', '64.89'], ['4.93', '416', '0', '84.38'], ['4.13', '664', '0', '160.77'], ['1.43', '100', '0', '69.93'], ['1.66', '128', '0', '77.11'], ['1.76', '160', '0', '90.91'], ['1.94', '536', '320', '596.29'], ['2.15', '392', '0', '182.33'], ['2.19', '324', '480', '627.95'], ['1', '48', '0', '48.00'], ['1.51', '156', '0', '103.31'], ['1.28', '188', '0', '146.88'], ['1.15', '252', '0', '219.13'], ['1', '72', '0', '72.00'], ['1', '300', '0', '300.00']])
def test_2026_workbook_calculations(hcf,raw1,raw2,expected):
    section=SimpleNamespace(error1=Decimal(raw1),error2=Decimal(raw2),points=None)
    entry=SimpleNamespace(hcf=Decimal(hcf),results=[section])
    assert score_totals(entry)["total"]==Decimal(expected)


def test_team_niw_and_tied_teams(client):
    event,_,entries=setup(client,count=3)
    score(client,entries[0],[0,0]);score(client,entries[1],[1,0])
    client.put(f"/api/entries/{entries[2]['id']}/scores",json=dict(version=1,card_status='missing',niw_reason='Nicht in Wertung'))
    for name in ['A','B']:
        assert client.post(f"/api/events/{event['id']}/teams",json=dict(name=name,start_numbers=[100,101,102])).status_code==201
    with SessionLocal() as db:
        rows=team_results(db,event['id'])
        assert [row['rank'] for row in rows]==[1,1]
        assert [row['total'] for row in rows]==[1375,1375]
        assert rows[0]['members'][-1]['points'] is None


def test_custom_pokal_count_and_new_contact_snapshot(client):
    event,_,entries=setup(client,count=1)
    response=client.post(f"/api/events/{event['id']}/classes",json=dict(code='S1',section_group='Auto klein',trophy_count=5))
    assert response.status_code==201
    assert '5 Pokale (Planung)' in client.get(f"/ui/events/{event['id']}/results").text
    with SessionLocal() as db:
        entry=db.get(Entry,entries[0]['id'])
        assert entry.driver_snapshot['name']=='Fahrer 0'
