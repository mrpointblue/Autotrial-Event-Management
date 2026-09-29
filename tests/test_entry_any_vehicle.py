from decimal import Decimal
from sqlalchemy import select
from backend.database import SessionLocal
from backend.models import DriverVehicle
from test_workflow import client,setup,post
from test_entry_edit import payload


def test_entry_can_use_another_drivers_vehicle_without_changing_links(client):
    event,standard,entries=setup(client,count=1)
    other=post(client,'vehicles',dict(manufacturer='Jeep',model='CJ Leihwagen',plate='IZ-TEST 42',class_code='V1',hcf='2.50'))
    owner=post(client,'drivers',dict(start_number=42,name='Eigentümer'))
    client.put(f"/api/drivers/{owner['id']}/vehicles",json=dict(vehicle_id=other['id'],is_default=True))
    borrower=post(client,'drivers',dict(start_number=43,name='Gastfahrer'))
    client.put(f"/api/drivers/{borrower['id']}/vehicles",json=dict(vehicle_id=standard['id'],is_default=True))
    entry=post(client,f"events/{event['id']}/entries",dict(driver_id=borrower['id'],vehicle_id=other['id'],class_code='S1'))
    assert entry['vehicle_id']==other['id'] and entry['class_code']=='S1'
    assert Decimal(str(entry['hcf']))==Decimal('2.50')
    assert entry['vehicle_snapshot']['plate']=='IZ-TEST 42'
    with SessionLocal() as db:
        assert db.get(DriverVehicle,(borrower['id'],other['id'])) is None
        assert db.get(DriverVehicle,(borrower['id'],standard['id'])).is_default
        assert db.get(DriverVehicle,(owner['id'],other['id'])).is_default
    page=client.get(f"/ui/events/{event['id']}/checkin").text
    assert 'entry-vehicle-search' in page and 'IZ-TEST 42' in page


def test_unassigned_vehicle_and_driver_without_default_can_be_nominated_and_edited(client):
    event,_,entries=setup(client,count=1)
    vehicle=post(client,'vehicles',dict(manufacturer='Jeep',model='Frei',class_code='V1',hcf='2'))
    driver=post(client,'drivers',dict(start_number=77,name='Ohne Standard'))
    assert client.post(f"/api/events/{event['id']}/entries",json=dict(driver_id=driver['id'])).status_code==422
    assert client.post(f"/api/events/{event['id']}/entries",json=dict(driver_id=driver['id'],vehicle_id=99999)).status_code==404
    post(client,f"events/{event['id']}/entries",dict(driver_id=driver['id'],vehicle_id=vehicle['id'],class_code='S1'))
    data=payload(entries[0]);data.update(vehicle_id=vehicle['id'],hcf='2')
    assert client.put(f"/api/entries/{entries[0]['id']}",json=data).status_code==200
    with SessionLocal() as db:
        assert list(db.scalars(select(DriverVehicle).where(DriverVehicle.vehicle_id==vehicle['id'])))==[]
    assert 'edit-vehicle-search' in client.get(f"/ui/entries/{entries[0]['id']}/edit").text
