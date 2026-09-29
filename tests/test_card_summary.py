from decimal import Decimal
from test_workflow import client,setup,score


def counts(**changes):
    return dict(reverse=0,ball=0,pole=0,foot=0,missed_gate=0,assistance=0,band=0,exit=0,not_driven=0,seatbelt=0,helmet=0,**{}) | changes


def test_card_counts_roundtrip_correction_and_print(client):
    event,_,entries=setup(client,count=1,sections=6)
    path=f"/api/entries/{entries[0]['id']}/scores"
    data=dict(version=1,card_status='received',card_summary=dict(error_counts=counts(reverse=5,ball=2,pole=1,foot=1,assistance=1,seatbelt=1,helmet=1),driven_sections=6))
    assert client.put(path,json=data).json()['status']=='complete'
    saved=client.get(f"/api/events/{event['id']}/entries/100").json()
    assert saved['sections']==[]
    assert saved['entry']['card_summary']['error_counts']['reverse']==5
    assert Decimal(saved['entry']['card_summary']['error1'])==160
    assert Decimal(saved['entry']['card_summary']['error2'])==1880
    assert Decimal(saved['totals']['total'])==Decimal('1972.49')
    assert '1972,49' in client.get(f"/print/events/{event['id']}/S1").text
    assert client.put(path,json=data).status_code==409
    data['version']=2;data['card_summary']['error_counts']['reverse']=0
    assert client.put(path,json=data).status_code==200
    saved=client.get(f"/api/events/{event['id']}/entries/100").json()
    assert Decimal(saved['totals']['total'])==Decimal('1949.36')


def test_summary_validation_pending_niw_and_missing(client):
    event,_,entries=setup(client,count=1,sections=10)
    path=f"/api/entries/{entries[0]['id']}/scores"
    data=dict(version=1,card_status='received',card_summary=dict(error_counts=counts(),driven_sections=11))
    assert client.put(path,json=data).status_code==422
    data['card_summary']['driven_sections']=6
    assert client.put(path,json=data).status_code==422
    data['card_summary']['driven_sections']=None
    assert client.put(path,json=data).json()['status']=='pending'
    data['version']=2;data['card_summary']['driven_sections']=6;data['niw_reason']='Weniger als 70 % gefahren'
    assert client.put(path,json=data).json()['status']=='niw'
    data['version']=3;data['card_status']='missing'
    assert client.put(path,json=data).status_code==422
    data.pop('card_summary');data['niw_reason']=''
    assert client.put(path,json=data).json()['status']=='pending'
    saved=client.get(f"/api/events/{event['id']}/entries/100").json()
    assert saved['entry']['card_summary'] is None and saved['entry']['card_status']=='missing'


def test_replace_sections_with_summary_and_back_without_double_counting(client):
    event,_,entries=setup(client,count=1,sections=2)
    entry=entries[0];path=f"/api/entries/{entry['id']}/scores"
    assert score(client,entry,[10,20]).status_code==200
    data=dict(version=2,card_status='received',card_summary=dict(error1='173',error2='20',driven_sections=2))
    assert client.put(path,json={**data,'sections':[dict(points=10),dict(points=20)]}).status_code==422
    assert client.put(path,json=data).status_code==200
    saved=client.get(f"/api/events/{event['id']}/entries/100").json()
    assert saved['sections']==[] and Decimal(saved['totals']['total'])==120
    assert score(client,saved['entry'],[1,2]).status_code==200
    saved=client.get(f"/api/events/{event['id']}/entries/100").json()
    assert saved['entry']['card_summary'] is None and Decimal(saved['totals']['total'])==3
