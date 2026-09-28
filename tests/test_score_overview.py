from test_workflow import client,setup,score
from backend.database import SessionLocal
from backend.models import Entry


def test_class_overview_filters_and_shows_updated_scores(client):
    event,_,entries=setup(client,count=2)
    with SessionLocal() as db:
        db.get(Entry,entries[1]['id']).class_code='V1';db.commit()
    score(client,entries[0],[10,20])
    path=f"/ui/events/{event['id']}/scoring?class_code=S1"
    page=client.get(path).text
    assert 'data-edit-score="100"' in page and 'data-edit-score="101"' not in page
    assert '30,00' in page and 'Vollständig' in page
    entry=client.get(f"/api/events/{event['id']}/entries/100").json()['entry']
    assert score(client,entry,[5,0]).status_code==200
    fragment=client.get(f"/ui/events/{event['id']}/score-overview?class_code=S1").text
    assert '5,00' in fragment and '30,00' not in fragment
    assert 'data-edit-score="101"' in client.get(f"/ui/events/{event['id']}/scoring").text
    assert client.get('/ui/events/999/score-overview').status_code==404
