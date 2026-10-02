import copy,json,uuid
import pytest
from fastapi.testclient import TestClient
from test_workflow import client,setup,post
from backend.main import app
from backend.services.identity import organizers,catalog
from backend.services.transfer import digest
from backend.database import current_tenant,SessionLocal
from backend.models import Event,Driver,Vehicle,Entry,EventClass
from sqlalchemy import select


def login_as(c,name,password='another-password-long'):
    assert c.post('/login',data=dict(username=name,password=password),follow_redirects=False).status_code==303


def make_tenant(c):
    uid=str(uuid.uuid4())
    r=c.post('/ui/admin/organizers',data=dict(name='Anderer Veranstalter',organizer_id=uid),follow_redirects=False)
    assert r.status_code==303,r.text
    assert c.post('/ui/admin/select',data=dict(organizer_id=uid),follow_redirects=False).status_code==303
    return uid


def test_tenant_isolation_across_ui_api_print_and_settings(client):
    event,vehicle,entries=setup(client,count=1)
    uid=make_tenant(client)
    assert 'Fahrer 0' not in client.get('/ui/master-data').text
    assert client.get(f"/api/events/{event['id']}/entries/100").status_code==404
    assert client.get(f"/print/entries/{entries[0]['id']}").status_code==404
    assert client.get(f"/export/events/{event['id']}/trialdata").status_code==404
    assert client.put(f"/api/vehicles/{vehicle['id']}",json=dict(manufacturer='A',model='B',class_code='S1')).status_code in (404,422)
    # Same start number is available independently.
    second,_,_=setup(client,count=1)
    assert second['id']==event['id']
    name='reader-'+uuid.uuid4().hex
    assert client.post('/ui/admin/users',data=dict(username=name,password='another-password-long',role='reader'),follow_redirects=False).status_code==303
    login_as(client,name)
    assert client.get('/ui/events').status_code==200
    assert client.get('/ui/settings/logo').status_code==200
    assert client.post('/api/events',json=dict(name='Denied',event_date='2026-10-03')).status_code==403
    assert client.post('/ui/events/import',files={'event_file':('test.trialdata',b'{}')}).status_code==403
    assert client.get('/ui/settings/database/export').status_code==403
    assert client.post('/ui/admin/select',data=dict(organizer_id=organizers()[0]['id'])).status_code==403
    assert client.get('/ui/admin').status_code==403


def test_organizer_admin_cannot_escalate_or_switch(client):
    uid=make_tenant(client)
    name='orgadmin-'+uuid.uuid4().hex
    assert client.post('/ui/admin/users',data=dict(username=name,password='another-password-long',role='organizer_admin'),follow_redirects=False).status_code==303
    login_as(client,name)
    assert client.get('/ui/admin').status_code==200
    assert client.post('/ui/admin/users',data=dict(username='illegal',password='another-password-long',role='admin')).status_code==403
    assert client.post('/ui/admin/organizers',data=dict(name='Illegal')).status_code==403
    assert client.post('/ui/admin/select',data=dict(organizer_id=str(uuid.uuid4()))).status_code==403
    assert client.post('/ui/admin/profile',data=dict(name='Eigenes Profil',address='Anschrift',contact='Kontakt'),follow_redirects=False).status_code==303


def test_anonymous_and_cross_origin_requests_are_rejected(client):
    assert client.post('/api/drivers',json=dict(name='Bad',start_number=1),headers={'Origin':'https://foreign.invalid'}).status_code==403
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/drivers').status_code==401
        assert anonymous.get('/ui/events',follow_redirects=False).status_code==303
        assert anonymous.get('/health').status_code==200


def test_export_duplicate_conflict_and_wrong_organizer(client):
    event,_,entries=setup(client,count=1)
    path=f"/export/events/{event['id']}/trialdata"
    package=client.get(path)
    assert package.status_code==200
    data=package.json()
    assert data['format_version']==1 and data['organizer']['id']
    assert 'password' not in package.text and 'users' not in data['records']
    r=client.post('/ui/events/import',files={'event_file':('event.trialdata',package.content)})
    assert r.status_code==200 and 'identisch' in r.text
    assert client.put(f"/api/events/{event['id']}",json=dict(name='Geändert',event_date='2026-10-03')).status_code==200
    r=client.post('/ui/events/import',files={'event_file':('event.trialdata',package.content)})
    assert r.status_code==409 and 'lokale Stand' in r.text
    make_tenant(client)
    assert client.post('/ui/events/import',files={'event_file':('event.trialdata',package.content)}).status_code==409


def test_round_trip_with_remapped_local_ids_and_no_overwrite(client):
    event,_,entries=setup(client,count=3,sections=5)
    assert client.post(f"/api/events/{event['id']}/teams",json=dict(name='Team',start_numbers=[100,101,102])).status_code==201
    assert client.put(f"/api/entries/{entries[0]['id']}/scores",json=dict(version=1,card_status='received',card_summary=dict(error1='173',error2='80',driven_sections=5))).status_code==200
    raw=client.get(f"/export/events/{event['id']}/trialdata").content
    data=json.loads(raw)
    uid=make_tenant(client)
    # Simulate the same organizer on a separate installation by changing only the
    # transport ownership for this isolated test store.
    data['organizer']['id']=uid
    data['records']['events'][0]['organizer_id']=uid
    data['digest']=digest(data['records'])
    r=client.post('/ui/events/import',files={'event_file':('event.trialdata',json.dumps(data).encode())})
    assert r.status_code==200,r.text
    token=current_tenant.set(next(o for o in organizers() if o['id']==uid))
    try:
        with SessionLocal() as db:
            imported=db.scalar(select(Event).where(Event.uid==data['event_id']))
            assert imported.name=='Trial'
            assert len(list(db.scalars(select(Entry))))==3
            assert db.scalar(select(Entry).where(Entry.start_number==100)).card_summary is not None
            local_id=imported.id
    finally:current_tenant.reset(token)
    again=client.get(f'/export/events/{local_id}/trialdata').json()
    assert again['digest']==data['digest']
    assert client.post('/ui/events/import',files={'event_file':('event.trialdata',json.dumps(data).encode())}).status_code==200
    broken=copy.deepcopy(data);broken['records']['events'][0]['name']='Tampered'
    assert client.post('/ui/events/import',files={'event_file':('event.trialdata',json.dumps(broken).encode())}).status_code==422


def test_import_rolls_back_on_start_number_conflict(client):
    event,_,_=setup(client,count=1)
    data=client.get(f"/export/events/{event['id']}/trialdata").json()
    uid=make_tenant(client);data['organizer']['id']=uid
    data['records']['events'][0]['organizer_id']=uid
    data['digest']=digest(data['records'])
    post(client,'drivers',dict(start_number=100,name='Local driver'))
    r=client.post('/ui/events/import',files={'event_file':('event.trialdata',json.dumps(data).encode())})
    assert r.status_code==409
    assert 'Trial' not in client.get('/ui/events?clear_event=1').text.replace('Autotrial','')
    assert 'Local driver' in client.get('/ui/master-data').text


def test_incoming_and_divergent_versions_are_distinguished(client):
    from backend.services.transfer import assess
    event,_,_=setup(client,count=1)
    data=client.get(f"/export/events/{event['id']}/trialdata").json()
    incoming=copy.deepcopy(data)
    incoming['records']['events'][0]['name']='Auswärts geändert'
    incoming['records']['events'][0]['revision']+=1
    incoming['revision']+=1;incoming['digest']=digest(incoming['records'])
    r=client.post('/ui/events/import',files={'event_file':('new.trialdata',json.dumps(incoming).encode())})
    assert r.status_code==409 and 'gemeinsamen Stand' in r.text
    client.put(f"/api/events/{event['id']}",json=dict(name='Lokal geändert',event_date='2026-10-03'))
    r=client.post('/ui/events/import',files={'event_file':('new.trialdata',json.dumps(incoming).encode())})
    assert r.status_code==409 and 'beiden Seiten' in r.text


def test_invalid_references_and_values_rejected_before_writing(client):
    event,_,_=setup(client,count=1)
    data=client.get(f"/export/events/{event['id']}/trialdata").json()
    for change in ('reference','sections','format'):
        broken=copy.deepcopy(data)
        if change=='reference':broken['records']['entries'][0]['driver_id']=str(uuid.uuid4())
        if change=='sections':broken['records']['event_classes'][0]['required_sections']=0
        if change=='format':broken['format_version']=999
        broken['digest']=digest(broken['records'])
        assert client.post('/ui/events/import',files={'event_file':('bad.trialdata',json.dumps(broken).encode())}).status_code==422


def test_editor_cannot_change_settings_and_deactivation_revokes_session(client):
    make_tenant(client)
    username='editor-'+uuid.uuid4().hex
    assert client.post('/ui/admin/users',data=dict(username=username,password='another-password-long',role='editor'),follow_redirects=False).status_code==303
    with TestClient(app) as editor:
        login_as(editor,username)
        assert editor.post('/api/events',json=dict(name='Allowed',event_date='2026-10-03')).status_code==201
        assert editor.post('/api/settings/time',json=dict(source='server')).status_code==403
        assert editor.post('/ui/admin/profile',data=dict(name='Bad')).status_code==403
        with catalog() as db:uid=db.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone()[0]
        assert client.post(f'/ui/admin/users/{uid}/disable',follow_redirects=False).status_code==303
        assert editor.get('/api/drivers').status_code==401


def test_logos_are_isolated_and_exported(client):
    import io,base64
    from PIL import Image
    event,_,_=setup(client,count=1)
    output=io.BytesIO();Image.new('RGB',(25,25),'red').save(output,format='PNG')
    assert client.post('/ui/settings/logo',files={'logo':('red.png',output.getvalue(),'image/png')},follow_redirects=False).status_code==303
    first=client.get('/ui/settings/logo').content
    data=client.get(f"/export/events/{event['id']}/trialdata").json()
    assert data['settings']['logo_png']
    make_tenant(client)
    assert client.get('/ui/settings/logo').content!=first


def test_stale_organizer_forms_are_rejected(client):
    from backend.services.identity import authenticated
    _,old=authenticated(client.cookies.get('trial_session'))
    make_tenant(client)
    assert client.post('/api/events',json=dict(name='Wrong tab',event_date='2026-10-03'),headers={'X-Trial-Organizer':old['id']}).status_code==409
    assert client.post('/ui/admin/profile?_tenant='+old['id'],data=dict(name='Wrong tab')).status_code==409


def test_setup_is_closed_after_first_account(client):
    assert client.get('/setup',follow_redirects=False).status_code==303
    assert client.post('/setup',data=dict(username='secondadmin',password='another-password-long'),follow_redirects=False).status_code==409


def test_short_organizer_numbers_and_recognition_from_file(client):
    from backend.services.identity import authenticated
    _,initial=authenticated(client.cookies.get('trial_session'))
    html=client.get('/ui/admin').text
    assert f'V{initial["number"]:03d}' in html
    assert 'Vorhandene Veranstalter-ID' not in html
    event,_,_=setup(client,count=1)
    data=client.get(f"/export/events/{event['id']}/trialdata").json()
    new_id=str(uuid.uuid4());data['organizer']['id']=new_id
    data['organizer']['name']='Transportierter Verein'
    data['records']['events'][0]['organizer_id']=new_id
    data['digest']=digest(data['records'])
    response=client.post('/ui/admin/organizers/from-file',files={'event_file':('event.trialdata',json.dumps(data).encode())},follow_redirects=False)
    assert response.status_code==303,response.text
    _,selected=authenticated(client.cookies.get('trial_session'))
    assert selected['id']==new_id and selected['number']!=initial['number']
    assert selected['name']=='Transportierter Verein'
    number=selected['number']
    response=client.post('/ui/admin/organizers/from-file',files={'event_file':('event.trialdata',json.dumps(data).encode())},follow_redirects=False)
    assert response.status_code==303
    _,again=authenticated(client.cookies.get('trial_session'))
    assert again['number']==number
