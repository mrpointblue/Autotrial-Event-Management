from test_workflow import client,setup,post


def test_event_navigation_survives_database_and_clear(client):
    assert 'Bordkarten erfassen' not in client.get('/ui/master-data').text
    event,_,_=setup(client,count=1)
    client.get(f"/ui/events/{event['id']}/checkin")
    for path in ['/ui/master-data','/ui/master-data?tab=new-driver','/ui/master-data?tab=vehicles&q=Suzuki','/ui/events']:
        html=client.get(path).text
        assert f'/ui/events/{event["id"]}/scoring' in html
        assert 'Mannschaften' in html and 'Starterliste' in html
    client.get('/ui/events?clear_event=1')
    assert 'Bordkarten erfassen' not in client.get('/ui/master-data').text


def test_active_event_switch_and_invalid_cookie(client):
    first,_,_=setup(client,count=1)
    second=post(client,'events',dict(name='Zweiter Trial',event_date='2026-10-01'))
    client.get(f"/ui/events/{first['id']}/results")
    client.get(f"/ui/events/{second['id']}/checkin")
    html=client.get('/ui/master-data').text
    assert f'/ui/events/{second["id"]}/scoring' in html
    assert f'/ui/events/{first["id"]}/scoring' not in html
    client.cookies.clear();client.cookies.set('active_event','999999')
    assert 'Bordkarten erfassen' not in client.get('/ui/master-data').text
