from test_workflow import client, setup


def test_color_shared_by_help_nomination_and_both_card_sides(client):
    event,_,entries=setup(client,count=1)
    path=f"/api/events/{event['id']}/classes"
    assert client.post(path,json=dict(code='S1',color='blue')).status_code==201
    ui=client.get(f"/ui/events/{event['id']}/checkin")
    assert 'class-marker-blue' in ui.text and 'S1 · Blau' in ui.text
    assert 'class-marker-blue' in client.get('/ui/help').text
    assert client.get(f"/print/entries/{entries[0]['id']}").text.count('class-marker-blue')==2
    # Updating sections through old clients must not reset an assigned color.
    assert client.post(path,json=dict(code='S1',required_sections=6)).status_code==201
    assert client.get(f"/print/cards/{event['id']}").text.count('class-marker-blue')==2
    assert client.post(path,json=dict(code='Mini',color='purple')).status_code==201
    assert 'Mini · Violett' in client.get(f"/ui/events/{event['id']}/checkin").text
    assert client.post(path,json=dict(code='S1',color='red; bad')).status_code==422


def test_help_without_event_and_reference_defaults(client):
    assert 'Vorbelegung' in client.get('/ui/help').text
    event,_,entries=setup(client,count=1)
    assert client.get(f"/print/cards/{event['id']}").text.count('class-marker-yellow')==2
