from test_workflow import client,setup,post
from backend.database import SessionLocal
from backend.models import Driver


def test_start_number_gaps_limits_and_duplicate(client):
    post(client,'drivers',dict(start_number=1,name='Belegt 1'))
    post(client,'drivers',dict(start_number=3,name='Belegt 3'))
    assert client.get('/api/drivers/available-start-numbers').json()['next_number']==2
    assert post(client,'drivers',dict(name='Automatisch'))['start_number']==2
    assert post(client,'drivers',dict(name='Nächster'))['start_number']==4
    assert client.post('/api/drivers',json=dict(start_number=3,name='Doppelt')).status_code==409
    for number in (0,1000,-1):assert client.post('/api/drivers',json=dict(start_number=number,name='Ungültig')).status_code==422
    assert post(client,'drivers',dict(start_number=999,name='Letzte Nummer'))['start_number']==999


def test_full_number_pool(client):
    with SessionLocal() as db:
        db.add_all(Driver(start_number=n,name=f'Test {n}') for n in range(1,1000));db.commit()
    assert client.get('/api/drivers/available-start-numbers').json()==dict(next_number=None,free_numbers=[])
    assert client.post('/api/drivers',json=dict(name='Voll')).status_code==409


def test_cards_follow_driver_vehicle_link(client):
    event,vehicle,entries=setup(client,count=2)
    first,second=entries
    extra=post(client,'vehicles',dict(manufacturer='Demo',model='Zweitfahrzeug',class_code='V1',hcf='2.15'))
    client.put(f"/api/drivers/{first['driver_id']}/vehicles",json=dict(vehicle_id=extra['id']))
    path=f"/print/drivers/{first['driver_id']}/vehicles"
    result=client.get(path)
    assert result.status_code==200
    assert result.text.count('class="vehicle-id-card"')==2
    assert result.text.count('<strong>Startnummer 100</strong>')==2
    assert '2,15' in result.text and '85,6 × 53,98 mm' in result.text
    assert client.get(path+f"/{extra['id']}").text.count('class="vehicle-id-card"')==1
    assert client.get(f"/print/drivers/{second['driver_id']}/vehicles/{extra['id']}").status_code==404
    shared=client.get(f"/print/drivers/{second['driver_id']}/vehicles/{vehicle['id']}")
    assert 'Startnummer 101' in shared.text and 'Startnummer 100' not in shared.text


def test_parallel_automatic_allocation(client):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses=list(pool.map(lambda i:client.post('/api/drivers',json=dict(name=f'Parallel {i}')),range(4)))
    assert all(r.status_code==201 for r in responses)
    assert sorted(r.json()['start_number'] for r in responses)==[1,2,3,4]
