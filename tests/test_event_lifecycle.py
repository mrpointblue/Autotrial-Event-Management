from test_workflow import client, setup


def test_edit_close_read_print_and_reopen(client):
    event,_,entries=setup(client,count=1)
    event_id=event['id']; entry_id=entries[0]['id']
    response=client.put(f'/api/events/{event_id}',json=dict(name='Neuer Name',event_date='2026-10-04',location='Neuer Ort',class_sections={'S1':5}))
    assert response.status_code==200
    assert response.json()['name']=='Neuer Name'
    edit=client.get(f'/ui/events?tab=edit&event_id={event_id}')
    assert edit.status_code==200 and 'Neuer Name' in edit.text and 'class_sections.S1' in edit.text
    assert client.post(f'/api/events/{event_id}/close',json={}).status_code==200
    for path,method,body in [
        (f'/api/events/{event_id}','PUT',dict(name='Verboten',event_date='2026-10-04')),
        (f'/api/events/{event_id}/entries','POST',{}),
        (f'/api/events/{event_id}/classes','POST',dict(code='Neue Klasse')),
        (f'/api/events/{event_id}/class-sections','PUT',dict(required_sections=6)),
        (f'/api/events/{event_id}/teams','POST',{}),
        (f'/api/entries/{entry_id}/scores','PUT',{}),
        (f'/api/entries/{entry_id}/checkin','PUT',{}),
        (f'/api/entries/{entry_id}','PUT',{}),
    ]:
        assert client.request(method,path,json=body).status_code==409
    assert client.get(f'/print/entries/{entry_id}').status_code==200
    assert client.get(f'/api/events/{event_id}/entries/100').json()['entry']['driver_name']=='Fahrer 0'
    assert 'Neuer Name' in client.get('/ui/events?tab=archive&clear_event=1').text
    assert 'Neuer Name' not in client.get('/ui/events?clear_event=1').text
    assert client.post(f'/api/events/{event_id}/reopen',json={}).status_code==200
    assert client.put(f'/api/events/{event_id}',json=dict(name='Wieder offen',event_date='2026-10-04')).status_code==200
    assert '5 vorgeschriebene Sektionen' in client.get(f'/print/entries/{entry_id}').text


def test_event_subtabs_and_invalid_edits(client):
    event,_,_=setup(client,count=1)
    for tab in ('overview','new','edit','archive'):
        assert client.get('/ui/events?tab='+tab).status_code==200
    assert client.get('/ui/events?tab=unknown').status_code==404
    assert client.put(f"/api/events/{event['id']}",json=dict(name='Invalid',event_date='2026-10-04',class_sections={'Unknown':8})).status_code==422
    assert client.get(f"/ui/events?tab=edit&event_id={event['id']}").text.count('value="Trial"')==1
    assert client.post('/api/events/9999/close',json={}).status_code==404
