from test_workflow import client,setup,post


def test_already_entered_drivers_are_excluded_only_for_the_current_event(client):
    event,_,entries=setup(client,count=1)
    fresh=post(client,'drivers',dict(start_number=222,name='Noch frei'))
    html=client.get(f"/ui/events/{event['id']}/checkin").text
    options=html.split('id="entry-driver"')[1].split('</select>')[0]
    assert '#100' not in options and '#222' in options
    assert 'Fahrer 0' in html # Existing entry remains editable below the form.
    second=post(client,'events',dict(name='Zweite Veranstaltung',event_date='2026-10-01'))
    options=client.get(f"/ui/events/{second['id']}/checkin").text.split('id="entry-driver"')[1].split('</select>')[0]
    assert '#100' in options and '#222' in options


def test_database_shortcuts_preselect_driver_and_existing_entries_open_edit(client):
    event,vehicle,entries=setup(client,count=1)
    fresh=post(client,'drivers',dict(start_number=222,name='Noch frei'))
    client.put(f"/api/drivers/{fresh['id']}/vehicles",json=dict(vehicle_id=vehicle['id'],is_default=True))
    assert 'Zur Nennung hinzufügen' not in client.get('/ui/master-data').text
    client.get(f"/ui/events/{event['id']}/checkin")
    database=client.get('/ui/master-data').text
    path=f"/ui/events/{event['id']}/checkin?driver_id={fresh['id']}"
    assert path in database and f"/ui/entries/{entries[0]['id']}/edit" in database
    assert f"checkin?driver_id={entries[0]['driver_id']}" not in database
    html=client.get(path).text
    assert f'value="{fresh["id"]}" selected>#222' in html
    post(client,f"events/{event['id']}/entries",dict(driver_id=fresh['id'],vehicle_id=vehicle['id']))
    assert path not in client.get('/ui/master-data').text
    response=client.get(path,follow_redirects=False)
    assert response.status_code==303 and '/edit' in response.headers['location']
    assert client.get(f"/ui/events/{event['id']}/checkin?driver_id=99999").status_code==404
    client.get('/ui/events?clear_event=1')
    assert 'Zur Nennung hinzufügen' not in client.get('/ui/master-data').text
