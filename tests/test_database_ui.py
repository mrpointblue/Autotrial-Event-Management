from test_workflow import client, setup, post

def test_overview_relations_and_search(client):
    event,vehicle,entries=setup(client)
    html=client.get('/ui/master-data').text
    assert 'Fahrerübersicht' in html and 'Standardfahrzeug' in html
    assert '1,73' in html and '1.730000' not in html
    assert 'id="vehicle-form"' not in html
    html=client.get('/ui/master-data?tab=vehicles').text
    assert 'Fahrer 0' in html and 'Fahrer 1' in html and 'Fahrer 2' in html
    html=client.get('/ui/master-data?q=101').text
    assert '#101' in html and '#100' not in html
    html=client.get('/ui/master-data?tab=vehicles&q=101').text
    assert 'Suzuki' in html
    assert 'Keine passenden Einträge' in client.get('/ui/master-data?class_code=V1').text
    for tab in ['new-driver','new-vehicle','assign']:
        response=client.get('/ui/master-data',params={'tab':tab})
        assert response.status_code==200
    assert 'id="vehicle-form"' in client.get('/ui/master-data?tab=new-vehicle').text

def test_pagination_and_empty_unassigned_records(client):
    assert 'Noch keine Fahrer angelegt' in client.get('/ui/master-data').text
    for number in range(1,28): post(client,'drivers',dict(start_number=number,name=f'Person {number}'))
    first=client.get('/ui/master-data').text
    assert '27 Treffer' in first and 'Seite 1 von 2' in first
    assert '#26' not in first and 'Kein Standardfahrzeug' in first
    second=client.get('/ui/master-data?page_number=2').text
    assert '#26' in second and '#25' not in second
    assert client.get('/ui/master-data?page_number=0').status_code==422
    assert client.get('/ui/master-data?tab=wrong').status_code==404

def test_html_escaping(client):
    post(client,'drivers',dict(start_number=1,name='<script>alert(1)</script>'))
    html=client.get('/ui/master-data').text
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html

def test_checkin_search_and_vehicle_selection_present(client):
    event,_,_=setup(client)
    html=client.get(f"/ui/events/{event['id']}/checkin").text
    assert 'id="entry-driver-search"' in html
    assert 'id="driver-search-info"' in html
    assert 'Startnummer, Nachname oder Vorname' in html
    assert 'id="entry-driver"' in html and 'id="entry-vehicle"' in html
    assert '#100 · Fahrer 0' not in html
    assert '0 noch nicht genannte Fahrer' in html


def test_assignment_search_and_vehicle_list_shortcut(client):
    _,vehicle,_=setup(client,count=1)
    listing=client.get('/ui/master-data?tab=vehicles').text
    assert f'tab=assign&amp;vehicle_id={vehicle["id"]}' in listing
    page=client.get('/ui/master-data',params={'tab':'assign','vehicle_id':vehicle['id']})
    assert page.status_code==200
    assert 'id="assign-driver-search"' in page.text and 'id="assign-vehicle-search"' in page.text
    assert f'value="{vehicle["id"]}" selected>F{vehicle["id"]}' in page.text
    assert 'data-return-tab="vehicles"' in page.text
    assert client.get('/ui/master-data?tab=assign&vehicle_id=99999').status_code==404
