import io
import sqlite3
from datetime import datetime,timezone
from PIL import Image
from test_workflow import client,setup,post


def png():
    file=io.BytesIO();Image.new('RGB',(40,20),'red').save(file,format='PNG');return file.getvalue()


def test_settings_navigation_timezone_and_clock(client):
    event,_,_=setup(client,count=1)
    client.get(f"/ui/events/{event['id']}/checkin")
    response=client.get('/ui/settings')
    assert response.status_code==200 and f'/ui/events/{event["id"]}/scoring' in response.text
    assert 'settings-link' in client.get('/ui/master-data').text
    assert client.post('/api/settings/time',json=dict(timezone='Not/AZone')).status_code==422
    assert client.post('/api/settings/time',json=dict(timezone='UTC')).status_code==200
    target='2026-10-12T12:30:00Z'
    assert client.post('/api/settings/time',json=dict(source='browser',target=target)).status_code==200
    from backend.services.settings import app_now,settings
    assert abs((app_now()-datetime.fromisoformat(target.replace('Z','+00:00'))).total_seconds())<5
    assert client.post('/api/settings/time',json=dict(source='manual',timezone='Europe/Berlin',target='2026-10-25T02:30')).status_code==422
    assert client.post('/api/settings/time',json=dict(source='manual',target='bad')).status_code==422
    assert client.post('/api/settings/time',json=dict(source='server')).status_code==200
    assert settings()['offset_seconds']==0


def test_logo_upload_remove_default_and_vehicle_cards_unchanged(client):
    event,_,entries=setup(client,count=1)
    assert client.post('/ui/settings/logo',files={'logo':('wrong.svg',b'<svg/>','image/svg+xml')}).status_code==422
    assert client.post('/ui/settings/logo',files={'logo':('club.png',png(),'image/png')}).status_code==200
    logo=client.get('/ui/settings/logo')
    assert logo.status_code==200 and logo.headers['content-type']=='image/png'
    assert '/ui/settings/logo' in client.get(f"/print/participants/{event['id']}").text
    assert '<img' not in client.get(f"/print/drivers/{entries[0]['driver_id']}/vehicles").text
    assert client.post('/ui/settings/logo/remove').status_code==200
    assert '<img' not in client.get(f"/print/participants/{event['id']}").text
    assert client.get('/ui/settings/logo').status_code==404
    assert client.post('/ui/settings/logo/default').status_code==200
    assert 'image/svg+xml' in client.get('/ui/settings/logo').headers['content-type']


def test_database_restore_includes_logo_and_creates_recoverable_backup(client):
    event,_,entries=setup(client,count=1)
    client.post('/api/settings/time',json=dict(timezone='UTC'))
    client.post('/ui/settings/logo',files={'logo':('club.png',png(),'image/png')})
    export=client.get('/ui/settings/database/export')
    assert export.status_code==200 and export.content.startswith(b'SQLite format 3')
    extra=post(client,'drivers',dict(start_number=999,name='Nach der Sicherung'))
    client.post('/api/settings/time',json=dict(timezone='Europe/Berlin'))
    client.get(f"/ui/events/{event['id']}/checkin")
    assert client.post('/ui/settings/database/import',data={'confirmation':'wrong'},files={'database_file':('backup.sqlite3',export.content)}).status_code==422
    response=client.post('/ui/settings/database/import',data={'confirmation':'ERSETZEN'},files={'database_file':('backup.sqlite3',export.content)},follow_redirects=False)
    assert response.status_code==303,response.text
    assert 'active_event' not in client.cookies
    drivers=client.get('/api/drivers').json()
    assert len(drivers)==1 and drivers[0]['start_number']==100
    from backend.services.settings import settings
    from backend.settings_ui import backup_dir
    assert settings()['timezone']=='UTC' and settings()['logo_png']
    backups=list(backup_dir().glob('backup-*.sqlite3'));assert backups
    backup=max(backups,key=lambda p:p.stat().st_mtime)
    with sqlite3.connect(backup) as db:
        assert db.execute('SELECT name FROM drivers WHERE start_number=999').fetchone()[0]=='Nach der Sicherung'
    assert client.get('/ui/settings/database/backups/'+backup.name).status_code==200
    assert client.get('/ui/settings/database/backups/not-a-backup').status_code==404
    assert client.get(f"/api/events/{event['id']}/entries/100").status_code==200


def test_invalid_database_does_not_replace_current_data(client):
    setup(client,count=1)
    for content in [b'not sqlite',b'SQLite format 3\x00bad']:
        assert client.post('/ui/settings/database/import',data={'confirmation':'ERSETZEN'},files={'database_file':('bad.sqlite3',content)}).status_code==422
        assert len(client.get('/api/drivers').json())==1
