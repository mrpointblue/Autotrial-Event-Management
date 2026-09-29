from decimal import Decimal
from sqlalchemy import select
from backend.database import SessionLocal
from backend.models import Vehicle,DriverVehicle,Entry
from test_workflow import client,setup,post


def test_vehicle_edit_prefill_and_snapshot_protection(client):
    _,vehicle,entries=setup(client,count=1)
    page=client.get(f"/ui/master-data?tab=edit-vehicle&vehicle_id={vehicle['id']}")
    assert page.status_code==200
    assert 'value="Suzuki"' in page.text and 'value="SJ"' in page.text
    assert 'value="1.73"' in page.text and 'data-method="PUT"' in page.text
    assert f'/api/vehicles/{vehicle["id"]}' in page.text
    data=dict(manufacturer='Suzuki',model='SJ geändert',class_code='V1',hcf='2.00',hcf_mode='manual',hcf_note='Umbau geprüft')
    assert client.put(f"/api/vehicles/{vehicle['id']}",json=data).status_code==200
    with SessionLocal() as db:
        assert db.get(Vehicle,vehicle['id']).model=='SJ geändert'
        entry=db.get(Entry,entries[0]['id'])
        assert entry.vehicle_snapshot['model']=='SJ' and entry.hcf==Decimal('1.73')
    assert client.get('/ui/master-data?tab=edit-vehicle&vehicle_id=9999').status_code==404


def test_delete_unused_vehicle_cleans_links_and_used_vehicle_is_protected(client):
    _,used,entries=setup(client,count=1)
    unused=post(client,'vehicles',dict(manufacturer='Test',model='Löschbar',class_code='S1',hcf='1'))
    driver_id=entries[0]['driver_id']
    client.put(f'/api/drivers/{driver_id}/vehicles',json=dict(vehicle_id=unused['id'],is_default=True))
    assert client.delete(f"/api/vehicles/{used['id']}").status_code==409
    with SessionLocal() as db:
        assert db.get(Vehicle,used['id']) and db.get(DriverVehicle,(driver_id,used['id']))
    assert client.delete(f"/api/vehicles/{unused['id']}").status_code==200
    with SessionLocal() as db:
        assert db.get(Vehicle,unused['id']) is None
        assert db.get(DriverVehicle,(driver_id,unused['id'])) is None
        assert db.get(Vehicle,used['id']) is not None
    assert client.delete(f"/api/vehicles/{unused['id']}").status_code==404
    listing=client.get('/ui/master-data?tab=vehicles').text
    assert 'Bearbeiten' in listing and 'Löschen' in listing and 'data-confirm=' in listing
