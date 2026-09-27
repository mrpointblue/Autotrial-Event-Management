from decimal import Decimal
import pytest
from backend.schemas import HcfInput
from backend.services.hcf import calculate_hcf
from test_workflow import client, post

@pytest.mark.parametrize('kind,dimensions', [('offroad',(300,139,193)),('atv',(185,101,115)),('quad',(166,106,110))])
def test_reference_vehicle(kind,dimensions):
    value=calculate_hcf(HcfInput(kind=kind,length_cm=dimensions[0],width_cm=dimensions[1],wheelbase_cm=dimensions[2]))
    assert Decimal(value['hcf'])==1

def test_additive_corrections_and_vehicle_specific_rules():
    data=dict(length_cm=343,width_cm=146,wheelbase_cm=203,closed_body=True,front_lock=True,rear_lock=True,traction_control=True)
    result=calculate_hcf(HcfInput(**data))
    assert Decimal(result['base'])==Decimal('1.872')
    assert result['correction_percent']==-30
    assert Decimal(result['hcf'])==Decimal('1.3104')
    assert calculate_hcf(HcfInput(kind='atv',**data))['correction_percent']==-20
    assert calculate_hcf(HcfInput(kind='quad',**data))['correction_percent']==0

def test_auto_save_recalculates_and_snapshot_stays_fixed(client):
    data=dict(manufacturer='Suzuki',model='SJ',class_code='S1',length_cm=343,width_cm=146,wheelbase_cm=203,rear_lock=True)
    vehicle=post(client,'vehicles',data)
    assert Decimal(str(vehicle['hcf']))==Decimal('1.6848')
    driver=post(client,'drivers',dict(start_number=12,name='Test'))
    client.put(f"/api/drivers/{driver['id']}/vehicles",json=dict(vehicle_id=vehicle['id'],is_default=True))
    event=post(client,'events',dict(name='Trial',event_date='2026-09-27',section_count=1))
    post(client,f"events/{event['id']}/entries",dict(driver_id=driver['id']))
    data.update(hcf='99',closed_body=True)
    changed=client.put(f"/api/vehicles/{vehicle['id']}",json=data)
    assert changed.status_code==200
    assert Decimal(str(changed.json()['hcf']))==Decimal('1.872')
    entry=client.get(f"/api/events/{event['id']}/entries/12").json()['entry']
    assert Decimal(str(entry['hcf']))==Decimal('1.6848')

def test_manual_reason_sbs_and_missing_dimensions(client):
    data=dict(manufacturer='Test',model='Test',class_code='SbS',kind='sbs')
    assert client.post('/api/vehicles',json=data).status_code==422
    data.update(hcf_mode='manual',hcf='2')
    assert client.post('/api/vehicles',json=data).status_code==422
    data['hcf_note']='Technische Abnahme nach Fahrzeugliste'
    assert client.post('/api/vehicles',json=data).status_code==201
    assert client.post('/api/hcf/preview',json=dict(kind='offroad')).status_code==422
    assert client.post('/api/hcf/preview',json=dict(kind='offroad',length_cm=1,width_cm=1,wheelbase_cm=1)).status_code==422
    assert client.post('/api/hcf/preview',json=dict(kind='quad',length_cm=166.5,width_cm=106,wheelbase_cm=110)).status_code==422
