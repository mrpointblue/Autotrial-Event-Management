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
    assert client.post(path,json=dict(code='Mini',color='red')).status_code==201
    assert 'Mini · Rot' in client.get(f"/ui/events/{event['id']}/checkin").text
    assert client.post(path,json=dict(code='S1',color='red; bad')).status_code==422


def test_help_without_event_and_reference_defaults(client):
    assert 'Vorbelegung' in client.get('/ui/help').text
    event,_,entries=setup(client,count=1)
    assert client.get(f"/print/cards/{event['id']}").text.count('class-marker-yellow')==2


def test_standard_palette_can_be_changed_and_help_follows(client):
    from backend.services.class_colors import COLORS
    assert list(COLORS.values())==['Weiß (keine Farbe)','Gelb','Grün','Rot','Orange','Blau']
    event,_,entries=setup(client,count=1)
    client.get(f"/ui/events/{event['id']}/checkin")
    html=client.get('/ui/master-data?tab=classes').text
    for color,label in COLORS.items():
        assert f'value="{color}"' in html and label in html
        assert client.post(f"/api/events/{event['id']}/classes",json=dict(code='S1',color=color)).status_code==201
        help_html=client.get('/ui/help').text
        assert f'class-marker-{color}">S1</span>' in help_html
        assert client.get(f"/print/entries/{entries[0]['id']}").text.count(f'class-marker-{color}')==2
    for old in ('pink','purple'):
        assert client.post(f"/api/events/{event['id']}/classes",json=dict(code='S1',color=old)).status_code==422
