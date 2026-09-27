import pytest
from backend.services.table_b import table_b_points

# Independent reference cells from the supplied table, including the .5 rounding case.
@pytest.mark.parametrize('rank,participants,expected', [
    (1,1,650),(1,2,700),(2,2,600),(1,3,725),(3,3,575),
    (1,6,757),(2,6,714),(3,6,671),(6,6,543),
    (1,7,763),(3,7,688),(5,7,613),(7,7,538),
    (1,18,784),(18,18,516),(1,20,786),(20,20,514),
])
def test_reference_values(rank,participants,expected):
    assert table_b_points(rank,participants)==expected

@pytest.mark.parametrize('rank,participants', [(0,1),(1,0),(2,1),(-1,2)])
def test_invalid_places(rank,participants):
    with pytest.raises(ValueError): table_b_points(rank,participants)

from test_workflow import client,setup,score,post
from backend.database import SessionLocal
from backend.services.scoring import ranked_results


def test_results_include_niw_in_denominator_and_ties(client):
    event,_,entries=setup(client,count=4)
    for entry,points in zip(entries[:3],[[0,0],[0,0],[1,0]]):
        assert score(client,entry,points).status_code==200
    response=client.put(f"/api/entries/{entries[3]['id']}/scores",json=dict(version=1,card_status='missing',niw_reason='Nichtabgabe bestätigt'))
    assert response.status_code==200
    with SessionLocal() as db:
        rows=ranked_results(db,event['id'],'S1')
        assert [row['rank'] for row in rows]==[1,1,3,'NiW']
        assert [row['points_b'] for row in rows]==[740,740,620,None]
        assert all(row['participant_count']==4 for row in rows)
    page=client.get(f"/ui/events/{event['id']}/results")
    assert page.status_code==200 and 'Wertungspunkte B' in page.text and '740' in page.text
    printed=client.get(f"/print/events/{event['id']}/S1")
    assert 'Punkte B' in printed.text and '620' in printed.text and 'N = 4' in printed.text
    assert client.get(f"/ui/events/{event['id']}/result-tables").status_code==200


def test_incomplete_classes_do_not_show_points(client):
    event,_,entries=setup(client,count=2)
    score(client,entries[0],[0,0])
    html=client.get(f"/ui/events/{event['id']}/results").text
    assert '1/2 Nennungen bearbeitet' in html
    assert '<th>Wertungspunkte B</th>' not in html
    assert client.get(f"/print/events/{event['id']}/S1").status_code==409


def test_all_niw_has_no_awarded_points(client):
    event,_,entries=setup(client,count=1)
    client.put(f"/api/entries/{entries[0]['id']}/scores",json=dict(version=1,card_status='missing',niw_reason='NiW'))
    with SessionLocal() as db:
        row=ranked_results(db,event['id'],'S1')[0]
        assert row['points_b'] is None and row['participant_count']==1
    assert client.get(f"/print/events/{event['id']}/S1").status_code==200
