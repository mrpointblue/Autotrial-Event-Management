import base64
import io
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask
from PIL import Image, UnidentifiedImageError
from backend.database import Base, DATA_DIR, engine, get_db
from backend.services.settings import settings, save_settings, app_now

router=APIRouter()
MAX_DATABASE=100*1024*1024
Image.MAX_IMAGE_PIXELS=16_000_000

def backup_dir():
    path=DATA_DIR/'backups';path.mkdir(exist_ok=True);return path


def database_backup(path):
    with sqlite3.connect(str(engine.url.database)) as source,sqlite3.connect(path) as target:
        source.backup(target)


def redirect(): return RedirectResponse('/ui/settings',status_code=303)


@router.get('/ui/settings')
def settings_page(request:Request,db:Session=Depends(get_db)):
    from backend.main import render
    config=settings(db)
    backups=[dict(name=p.name,size=round(p.stat().st_size/1024/1024,2)) for p in sorted(backup_dir().glob('backup-*.sqlite3'),reverse=True)]
    return render(request,'settings.html',page='settings',config=config,
                  clock=app_now(db).astimezone(ZoneInfo(config['timezone'])),
                  system_clock=datetime.now(timezone.utc).astimezone(ZoneInfo(config['timezone'])),
                  timezones=sorted(available_timezones()),backups=backups)


class TimeInput(BaseModel):
    source: str='timezone'
    timezone: str|None=None
    target: str|None=None


@router.post('/api/settings/time')
def set_time(data:TimeInput,db:Session=Depends(get_db)):
    config=settings(db);zone=data.timezone or config['timezone']
    try: tz=ZoneInfo(zone)
    except (ZoneInfoNotFoundError,ValueError): raise HTTPException(422,'Unbekannte Zeitzone.')
    changes=dict(timezone=zone)
    if data.source=='server': changes['offset_seconds']=0
    elif data.source in ('browser','manual'):
        try:
            target=datetime.fromisoformat((data.target or '').replace('Z','+00:00'))
            if not 2020<=target.year<=2099: raise ValueError()
            if target.tzinfo is None:
                # Reject times skipped or repeated during a daylight-saving transition.
                candidates=[target.replace(tzinfo=tz,fold=f) for f in (0,1)]
                valid=[d for d in candidates if d.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)==target]
                if not valid or len({d.utcoffset() for d in valid})!=1: raise ValueError()
                target=valid[0]
            changes['offset_seconds']=(target.astimezone(timezone.utc)-datetime.now(timezone.utc)).total_seconds()
        except (ValueError,OverflowError): raise HTTPException(422,'Ungültige oder durch Zeitumstellung mehrdeutige Uhrzeit. Bitte eine andere Zeit oder die Browserzeit verwenden.')
    elif data.source!='timezone': raise HTTPException(422,'Unbekannte Zeitquelle.')
    save_settings(db,changes)
    return dict(status='saved')


@router.get('/ui/settings/logo')
def get_logo(db:Session=Depends(get_db)):
    config=settings(db)
    if not config['logo_enabled']: raise HTTPException(404,'Kein Logo hinterlegt.')
    if config['logo_png']:
        return Response(base64.b64decode(config['logo_png']),media_type='image/png',headers={'Cache-Control':'no-store'})
    return FileResponse(Path(__file__).parent/'static/msc-logo.svg',headers={'Cache-Control':'no-store'})


@router.post('/ui/settings/logo')
async def upload_logo(logo:UploadFile=File(...),db:Session=Depends(get_db)):
    data=await logo.read(5*1024*1024+1)
    if len(data)>5*1024*1024: raise HTTPException(422,'Logo maximal 5 MB.')
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ('PNG','JPEG') or image.width*image.height>16_000_000: raise ValueError()
            image.load();image=image.convert('RGBA');image.thumbnail((1600,1600))
            output=io.BytesIO();image.save(output,format='PNG')
    except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError):
        raise HTTPException(422,'Bitte ein gültiges PNG- oder JPG-Bild bis 16 Megapixel verwenden.')
    save_settings(db,dict(logo_png=base64.b64encode(output.getvalue()).decode(),logo_enabled=True))
    return redirect()


@router.post('/ui/settings/logo/remove')
def remove_logo(db:Session=Depends(get_db)):
    save_settings(db,dict(logo_png=None,logo_enabled=False));return redirect()


@router.post('/ui/settings/logo/default')
def default_logo(db:Session=Depends(get_db)):
    save_settings(db,dict(logo_png=None,logo_enabled=True));return redirect()


@router.get('/ui/settings/database/export')
def export_database():
    file=tempfile.NamedTemporaryFile(suffix='.sqlite3',dir=DATA_DIR,delete=False);file.close();path=Path(file.name)
    try: database_backup(path)
    except Exception: path.unlink(missing_ok=True);raise
    return FileResponse(path,filename='autotrial-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3',
                        media_type='application/octet-stream',background=BackgroundTask(path.unlink,missing_ok=True))


def validate_database(path):
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
            db.execute('PRAGMA trusted_schema=OFF')
            if db.execute('PRAGMA user_version').fetchone()[0]!=9: raise ValueError('Bitte eine Datenbank aus der aktuellen Autotrial-Version importieren.')
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchone(): raise ValueError('Die Datenbank ist beschädigt oder enthält ungültige Zuordnungen.')
            if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') OR upper(sql) LIKE '%CREATE VIRTUAL TABLE%'").fetchone(): raise ValueError('Die Datenbank enthält nicht unterstützte Datenbankobjekte.')
            for table in Base.metadata.sorted_tables:
                actual={r[1]:r[2].upper() for r in db.execute('PRAGMA table_info("'+table.name+'")')}
                if any(c.name not in actual or actual[c.name].replace(' ','')!=str(c.type.compile(engine.dialect)).upper().replace(' ','') for c in table.columns): raise ValueError('Die Datenbankstruktur passt nicht zu Autotrial.')
            import json
            record=db.execute("SELECT value FROM app_settings WHERE key='general'").fetchone()
            if record:
                config=json.loads(record[0])
                if not isinstance(config,dict) or not isinstance(config.get('logo_enabled',True),bool): raise ValueError('Ungültige Einstellungen.')
                ZoneInfo(config.get('timezone','Europe/Berlin'))
                offset=config.get('offset_seconds',0)
                import math
                if not isinstance(offset,(int,float)) or not math.isfinite(offset) or abs(offset)>4_000_000_000: raise ValueError('Ungültige Zeiteinstellung.')
                if config.get('logo_png'):
                    if not isinstance(config['logo_png'],str) or len(config['logo_png'])>8*1024*1024: raise ValueError('Ungültiges Logo.')
                    with Image.open(io.BytesIO(base64.b64decode(config['logo_png'],validate=True))) as img:
                        if img.format!='PNG' or img.width*img.height>16_000_000: raise ValueError('Ungültiges Logo.')
                        img.verify()
    except (sqlite3.DatabaseError,ValueError,KeyError,TypeError,ZoneInfoNotFoundError,OSError,Image.DecompressionBombError) as error:
        raise HTTPException(422,str(error) if isinstance(error,ValueError) else 'Keine gültige Autotrial-Datenbank.')


@router.post('/ui/settings/database/import')
async def import_database(database_file:UploadFile=File(...),confirmation:str=Form(...)):
    if confirmation!='ERSETZEN': raise HTTPException(422,'Zum Bestätigen ERSETZEN eingeben.')
    temp=tempfile.NamedTemporaryFile(suffix='.sqlite3',dir=DATA_DIR,delete=False);path=Path(temp.name)
    try:
        size=0
        while chunk:=await database_file.read(1024*1024):
            size+=len(chunk)
            if size>MAX_DATABASE: raise HTTPException(422,'Datenbank maximal 100 MB.')
            temp.write(chunk)
        temp.close();validate_database(path)
        backup=backup_dir()/('backup-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.sqlite3')
        database_backup(backup)
        # Requests are serialized by the application maintenance gate (one worker).
        engine.dispose()
        try:
            with sqlite3.connect(path) as source,sqlite3.connect(str(engine.url.database)) as target: source.backup(target)
        except Exception:
            with sqlite3.connect(backup) as source,sqlite3.connect(str(engine.url.database)) as target: source.backup(target)
            raise
        finally: engine.dispose()
        response=redirect();response.delete_cookie('active_event');return response
    finally:
        temp.close();path.unlink(missing_ok=True)


@router.get('/ui/settings/database/backups/{name}')
def download_backup(name:str):
    import re
    if not re.fullmatch(r'backup-\d{8}-\d{6}-[a-f0-9]{8}\.sqlite3',name): raise HTTPException(404,'Sicherung nicht gefunden.')
    path=backup_dir()/name
    if not path.is_file(): raise HTTPException(404,'Sicherung nicht gefunden.')
    return FileResponse(path,filename=name,media_type='application/octet-stream')
