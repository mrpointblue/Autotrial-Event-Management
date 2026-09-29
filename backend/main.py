from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, update, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from backend.database import Base, engine, get_db, SessionLocal
from backend.models import CLASSES, Driver, Vehicle, DriverVehicle, Event, Entry, EventClass, Team, TeamMember
from backend.schemas import DriverInput, VehicleInput, EventInput, LinkInput, EntryInput, ScoreInput
from backend.services.hcf import calculate_hcf, vehicle_values, round_hcf, format_hcf
from backend.schemas import HcfInput
from backend.services.scoring import save_scores, class_progress, ranked_results, result_groups, score_totals

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        version = conn.exec_driver_sql('PRAGMA user_version').scalar()
        if version not in (0,1,2,3,4,5): raise RuntimeError('Nicht unterstützte Datenbankversion')
        columns={r[1] for r in conn.exec_driver_sql('PRAGMA table_info(section_results)')}
        for column in ('error1','error2'):
            if column not in columns:
                conn.exec_driver_sql(f'ALTER TABLE section_results ADD COLUMN {column} NUMERIC(14,2) CHECK ({column} IS NULL OR {column} >= 0)')
        entry_columns={r[1] for r in conn.exec_driver_sql('PRAGMA table_info(entries)')}
        if 'card_summary' not in entry_columns:
            conn.exec_driver_sql('ALTER TABLE entries ADD COLUMN card_summary JSON')
        if 'driver_snapshot' not in entry_columns:
            conn.exec_driver_sql('ALTER TABLE entries ADD COLUMN driver_snapshot JSON')
        if 'error_counts' not in columns:
            conn.exec_driver_sql('ALTER TABLE section_results ADD COLUMN error_counts JSON')
        if version < 4:
            for event_id, in conn.exec_driver_sql('SELECT id FROM events'):
                codes=set(CLASSES) | {r[0] for r in conn.exec_driver_sql('SELECT DISTINCT class_code FROM entries WHERE event_id=?',(event_id,))}
                for code in codes:
                    conn.exec_driver_sql('INSERT OR IGNORE INTO event_classes (event_id,code,section_group) VALUES (?,?,?)',(event_id,code,''))
        conn.exec_driver_sql('PRAGMA user_version=5')
    yield

app = FastAPI(title='Autotrial', version='0.1.0', lifespan=lifespan)
ROOT = Path(__file__).parent
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
templates = Jinja2Templates(directory=ROOT/'templates')
templates.env.filters['hcf'] = format_hcf

def get(db,model,id):
    value = db.get(model,id)
    if value is None: raise HTTPException(404,'Datensatz nicht gefunden')
    return value

def commit(db):
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Zuordnung oder Startnummer bereits vorhanden; bitte prüfen.')
    except StaleDataError:
        db.rollback()
        raise HTTPException(409,'Datensatz inzwischen geändert. Bitte neu laden.')

def render(request,name,**context):
    full_ui=request.url.path.startswith('/ui/') and name not in ('result_tables.html','score_overview.html')
    clear=full_ui and request.url.path=='/ui/events' and request.query_params.get('clear_event')=='1'
    active=context.get('event')
    if full_ui and not active and not clear:
        saved=request.cookies.get('active_event','')
        if saved.isdigit() and len(saved)<=18:
            with SessionLocal() as session:
                active=session.get(Event,int(saved))
            if active is not None: context['event']=active
    if clear: context.pop('event',None)
    response=templates.TemplateResponse(request=request,name=name,context=context)
    if full_ui:
        if clear or active is None: response.delete_cookie('active_event')
        else: response.set_cookie('active_event',str(active.id),httponly=True,samesite='lax')
    return response

@app.exception_handler(HTTPException)
async def error_page(request,exc):
    if request.url.path.startswith('/api/') or request.url.path=='/health':
        return JSONResponse({'detail':exc.detail},status_code=exc.status_code)
    return templates.TemplateResponse(request=request,name='error.html',context={'detail':exc.detail},status_code=exc.status_code)

@app.get('/health')
def health(db:Session=Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status':'ok','version':'0.1.0'}

@app.get('/')
def root(): return RedirectResponse('/ui/events')

@app.get('/api/drivers')
def drivers(db:Session=Depends(get_db)): return list(db.scalars(select(Driver).order_by(Driver.start_number)))

@app.post('/api/drivers',status_code=201)
def create_driver(data:DriverInput,db:Session=Depends(get_db)):
    number=data.start_number
    if number is None:
        # Serialize allocation so simultaneous registrations cannot choose the same gap.
        db.execute(text('BEGIN IMMEDIATE'))
        used=set(db.scalars(select(Driver.start_number)))
        number=next((n for n in range(1,1000) if n not in used),None)
        if number is None: raise HTTPException(409,'Alle Startnummern von 1 bis 999 sind vergeben.')
    elif db.scalar(select(Driver.id).where(Driver.start_number==number)):
        raise HTTPException(409,f'Startnummer {number} ist bereits vergeben. Bitte eine freie Nummer wählen.')
    row=Driver(start_number=number,**data.model_dump(exclude={'start_number'}))
    db.add(row); commit(db); return row

@app.get('/api/vehicles')
def vehicles(db:Session=Depends(get_db)): return list(db.scalars(select(Vehicle).order_by(Vehicle.id)))

@app.post('/api/vehicles',status_code=201)
def create_vehicle(data:VehicleInput,db:Session=Depends(get_db)):
    validate_class(db,data.class_code)
    try: values=vehicle_values(data)
    except ValueError as error: raise HTTPException(422,str(error))
    row=Vehicle(**values); db.add(row); commit(db); return row

@app.put('/api/vehicles/{vehicle_id}')
def edit_vehicle(vehicle_id:int,data:VehicleInput,db:Session=Depends(get_db)):
    validate_class(db,data.class_code)
    row=get(db,Vehicle,vehicle_id)
    try: values=vehicle_values(data)
    except ValueError as error: raise HTTPException(422,str(error))
    for key,value in values.items(): setattr(row,key,value)
    commit(db); return row

@app.put('/api/drivers/{driver_id}/vehicles')
def link_vehicle(driver_id:int,data:LinkInput,db:Session=Depends(get_db)):
    get(db,Driver,driver_id); get(db,Vehicle,data.vehicle_id)
    if data.is_default:
        db.execute(update(DriverVehicle).where(DriverVehicle.driver_id==driver_id).values(is_default=False))
    row=db.get(DriverVehicle,(driver_id,data.vehicle_id))
    if row is None:
        row=DriverVehicle(driver_id=driver_id,vehicle_id=data.vehicle_id); db.add(row)
    row.is_default=data.is_default; commit(db); return row

@app.get('/api/drivers/{driver_id}/vehicles')
def linked_vehicles(driver_id:int,db:Session=Depends(get_db)):
    get(db,Driver,driver_id)
    return [dict(vehicle=jsonable_encoder(v),is_default=link.is_default) for v,link in db.execute(select(Vehicle,DriverVehicle).join(DriverVehicle,Vehicle.id==DriverVehicle.vehicle_id).where(DriverVehicle.driver_id==driver_id))]

@app.post('/api/events',status_code=201)
def create_event(data:EventInput,db:Session=Depends(get_db)):
    row=Event(**data.model_dump()); db.add(row); db.flush()
    db.add_all(EventClass(event_id=row.id,code=code) for code in CLASSES)
    commit(db); return row

@app.post('/api/events/{event_id}/entries',status_code=201)
def create_entry(event_id:int,data:EntryInput,db:Session=Depends(get_db)):
    get(db,Event,event_id); driver=get(db,Driver,data.driver_id)
    vehicle_id=data.vehicle_id
    if vehicle_id is None:
        link=db.scalar(select(DriverVehicle).where(DriverVehicle.driver_id==driver.id,DriverVehicle.is_default==True))
        if not link: raise HTTPException(422,'Kein Standardfahrzeug hinterlegt. Bitte ein Fahrzeug auswählen.')
        vehicle_id=link.vehicle_id
    vehicle=get(db,Vehicle,vehicle_id)
    try: entry_hcf = round_hcf(vehicle.hcf)
    except ValueError as error: raise HTTPException(422,str(error))
    class_code=data.class_code or vehicle.class_code
    validate_class(db,class_code,event_id)
    snapshot={c.name:str(entry_hcf) if c.name=='hcf' else getattr(vehicle,c.name) for c in Vehicle.__table__.columns}
    row=Entry(event_id=event_id,driver_id=driver.id,vehicle_id=vehicle.id,start_number=driver.start_number,
        driver_name=driver.name,driver_snapshot={key:getattr(driver,key) for key in ('name','address','email','club','adac_number')},vehicle_snapshot={**snapshot,'class_code':class_code},class_code=class_code,hcf=entry_hcf,
        **data.model_dump(exclude={'driver_id','vehicle_id','class_code'}))
    db.add(row); commit(db); return row

@app.get('/api/events/{event_id}/entries/{start_number}')
def lookup(event_id:int,start_number:int,db:Session=Depends(get_db)):
    row=db.scalar(select(Entry).where(Entry.event_id==event_id,Entry.start_number==start_number))
    if not row: raise HTTPException(404,'Startnummer ist für diese Veranstaltung nicht genannt.')
    return dict(entry=jsonable_encoder(row),totals={k:str(v) if v is not None else None for k,v in score_totals(row).items()},sections=[dict(error_counts=r.error_counts,points=str(r.points) if r.points is not None else None,error1=str(r.error1) if r.error1 is not None else None,error2=str(r.error2) if r.error2 is not None else None,driven=r.driven) for r in row.results])

@app.put('/api/entries/{entry_id}/scores')
def record(entry_id:int,data:ScoreInput,db:Session=Depends(get_db)):
    row=get(db,Entry,entry_id)
    save_scores(row,get(db,Event,row.event_id),data); commit(db)
    return dict(id=row.id,version=row.version,status=row.scoring_status)

@app.get('/api/events/{event_id}/progress')
def progress(event_id:int,db:Session=Depends(get_db)):
    get(db,Event,event_id); return class_progress(db,event_id)

@app.get('/ui/events')
def events_ui(request:Request,db:Session=Depends(get_db)):
    return render(request,'events.html',events=list(db.scalars(select(Event).order_by(Event.event_date.desc()))))

@app.get('/ui/master-data')
def master_ui(request:Request,tab:str='drivers',q:str='',class_code:str='',
              page_number:int=Query(default=1,ge=1),vehicle_id:int|None=Query(default=None,ge=1),db:Session=Depends(get_db)):
    if tab == 'classes':
        saved=request.cookies.get('active_event','')
        active=db.get(Event,int(saved)) if saved.isdigit() and len(saved)<=18 else None
        return render(request,'classes.html',tab='classes',event=active,
                      event_classes=list(db.scalars(select(EventClass).where(EventClass.event_id==active.id).order_by(EventClass.code))) if active else [])
    if tab not in ('drivers','vehicles','new-driver','new-vehicle','assign'):
        raise HTTPException(404,'Ansicht nicht gefunden')
    if tab=='assign' and vehicle_id is not None: get(db,Vehicle,vehicle_id)
    all_drivers, all_vehicles = drivers(db), vehicles(db)
    driver_map = {d.id:d for d in all_drivers}
    vehicle_map = {v.id:v for v in all_vehicles}
    by_driver = {d.id:[] for d in all_drivers}
    by_vehicle = {v.id:[] for v in all_vehicles}
    for link in db.scalars(select(DriverVehicle).order_by(DriverVehicle.driver_id,DriverVehicle.vehicle_id)):
        by_driver[link.driver_id].append(dict(vehicle=vehicle_map[link.vehicle_id],is_default=link.is_default))
        by_vehicle[link.vehicle_id].append(dict(driver=driver_map[link.driver_id],is_default=link.is_default))
    for links in by_driver.values(): links.sort(key=lambda x:not x['is_default'])
    for links in by_vehicle.values(): links.sort(key=lambda x:x['driver'].start_number)
    query = q.strip().casefold()
    if tab == 'vehicles':
        rows = [v for v in all_vehicles if (not class_code or v.class_code==class_code) and
                query in ' '.join([str(v.id),'F'+str(v.id),v.manufacturer,v.model,v.plate,v.class_code]+
                [str(x['driver'].start_number)+' '+x['driver'].name for x in by_vehicle[v.id]]).casefold()]
    else:
        rows = [d for d in all_drivers if (not class_code or any(x['vehicle'].class_code==class_code for x in by_driver[d.id])) and
                query in ' '.join([str(d.start_number),d.name,d.club,d.adac_number]+
                [x['vehicle'].manufacturer+' '+x['vehicle'].model+' '+x['vehicle'].plate for x in by_driver[d.id]]).casefold()]
    count = len(rows)
    pages = max(1,(count+24)//25)
    page_number = min(page_number,pages)
    rows = rows[(page_number-1)*25:page_number*25]
    return render(request,'master.html',drivers=all_drivers,vehicles=all_vehicles,classes=available_classes(db),
                  assigned_vehicle_id=vehicle_id,tab=tab,q=q,class_code=class_code,rows=rows,count=count,pages=pages,page_number=page_number,
                  by_driver=by_driver,by_vehicle=by_vehicle,
                  previous_url=str(request.url.include_query_params(page_number=page_number-1)),
                  next_url=str(request.url.include_query_params(page_number=page_number+1)))

@app.get('/ui/events/{event_id}/{page}')
def event_ui(event_id:int,page:str,request:Request,db:Session=Depends(get_db)):
    if page not in ('checkin','scoring','results','result-tables','participants','classes','teams','score-overview'): raise HTTPException(404,'Seite nicht gefunden')
    event=get(db,Event,event_id)
    if page=='score-overview':
        return render(request,'score_overview.html',event=event,**score_overview(db,event_id,request.query_params.get('class_code','')))
    if page=='result-tables':
        return render(request,'result_tables.html',event=event,result_groups=result_groups(db,event_id),team_results=team_results(db,event_id))
    entries=list(db.scalars(select(Entry).where(Entry.event_id==event_id).order_by(Entry.start_number)))
    return render(request,page+'.html',event=event,drivers=drivers(db),vehicles=vehicles(db) if page=='checkin' else [],entries=entries,progress=class_progress(db,event_id),page=page,
                  result_groups=result_groups(db,event_id) if page=='results' else [],
                  participant_groups=participant_groups(db,event_id) if page=='participants' else [],
                  event_classes=list(db.scalars(select(EventClass).where(EventClass.event_id==event_id).order_by(EventClass.code))),
                  team_results=team_results(db,event_id) if page in ('teams','results') else [],
                  **score_overview(db,event_id,request.query_params.get('class_code','')))

@app.get('/print/entries/{entry_id}')
def card(entry_id:int,request:Request,db:Session=Depends(get_db)):
    entry=get(db,Entry,entry_id)
    if not entry.technical_approved or not entry.paperwork_approved:
        raise HTTPException(409,'Papierabnahme und technische Abnahme müssen für den Bordkartendruck bestätigt sein.')
    return render(request,'card.html',entry=entry,event=get(db,Event,entry.event_id))

@app.get('/print/events/{event_id}/{class_code}')
def results(event_id:int,class_code:str,request:Request,db:Session=Depends(get_db)):
    event=get(db,Event,event_id)
    if class_code in ('all','adac'):
        groups=result_groups(db,event_id)
        if not groups: raise HTTPException(404,'Noch keine Nennungen für diese Veranstaltung.')
        incomplete=[g['class_code'] for g in groups if not g['ready']]
        if incomplete: raise HTTPException(409,'Gesamtdruck erst nach vollständiger Erfassung. Offen: '+', '.join(incomplete))
    else:
        rows=ranked_results(db,event_id,class_code)
        groups=[dict(class_code=class_code,rows=rows,total=len(rows))]
    return render(request,'print_results.html',event=event,groups=groups,adac=class_code=='adac',
                  starter_count=sum(g['total'] for g in groups),adac_rows=adac_rows(db,groups) if class_code=='adac' else [],
                  team_results=team_results(db,event_id) if class_code in ('all','adac') else [])

from backend.schemas import CheckinInput

@app.put('/api/entries/{entry_id}/checkin')
def update_checkin(entry_id:int,data:CheckinInput,db:Session=Depends(get_db)):
    row=get(db,Entry,entry_id)
    if row.version != data.version: raise HTTPException(409,'Nennung inzwischen geändert. Bitte neu laden.')
    for key,value in data.model_dump(exclude={'version'}).items(): setattr(row,key,value)
    row.version += 1
    commit(db); return row


@app.post('/api/hcf/preview')
def hcf_preview(data:HcfInput):
    try: return calculate_hcf(data)
    except ValueError as error: raise HTTPException(422,str(error))

from backend.schemas import EntryEditInput
from backend.models import EntryChange
from backend.services.entries import edit_entry

@app.get('/ui/entries/{entry_id}/edit')
def entry_edit_ui(entry_id:int,request:Request,db:Session=Depends(get_db)):
    entry=get(db,Entry,entry_id)
    choices=[dict(id=entry.vehicle_id,label=entry.vehicle_snapshot['manufacturer']+' '+entry.vehicle_snapshot['model']+' · '+(entry.vehicle_snapshot.get('plate') or 'ohne Kennzeichen'),
                  class_code=entry.class_code,hcf=format_hcf(entry.hcf).replace(',','.'))]
    for v in vehicles(db):
        if v.id!=entry.vehicle_id:
            choices.append(dict(id=v.id,label=v.manufacturer+' '+v.model+' · '+(v.plate or 'ohne Kennzeichen'),class_code=v.class_code,hcf=format_hcf(v.hcf).replace(',','.')))
    changes=list(db.scalars(select(EntryChange).where(EntryChange.entry_id==entry.id).order_by(EntryChange.id.desc())))
    return render(request,'entry_edit.html',event=get(db,Event,entry.event_id),entry=entry,
                  choices=choices,classes=available_classes(db,entry.event_id),changes=changes,page='checkin')

@app.put('/api/entries/{entry_id}')
def update_entry(entry_id:int,data:EntryEditInput,db:Session=Depends(get_db)):
    entry=get(db,Entry,entry_id)
    validate_class(db,data.class_code,entry.event_id)
    edit_entry(db,entry,data)
    commit(db)
    return dict(id=entry.id,version=entry.version,status=entry.scoring_status)


# Reports share the live event data; no separate copied results can become stale.
def participant_groups(db,event_id):
    groups={}
    for entry in db.scalars(select(Entry).where(Entry.event_id==event_id).order_by(Entry.class_code,Entry.start_number)):
        groups.setdefault(entry.class_code,[]).append(entry)
    return [dict(class_code=key,entries=entries,section_group=(db.get(EventClass,(event_id,key)).section_group if db.get(EventClass,(event_id,key)) else '')) for key,entries in groups.items()]


def adac_rows(db,groups):
    rows=[]
    for group in groups:
        for result in group['rows']:
            entry=result['entry']
            contact=entry.driver_snapshot
            if contact is None:
                driver=db.get(Driver,entry.driver_id)
                contact={key:getattr(driver,key) for key in ('address','email','club','adac_number')}
            rows.append(dict(result,contact=contact,legacy_contact=entry.driver_snapshot is None))
    return rows


@app.get('/print/participants/{event_id}')
def print_participants(event_id:int,request:Request,db:Session=Depends(get_db)):
    event=get(db,Event,event_id)
    groups=participant_groups(db,event_id)
    return render(request,'print_participants.html',event=event,groups=groups,
                  total=sum(len(g['entries']) for g in groups))


@app.get('/export/events/{event_id}/adac.csv')
def export_adac(event_id:int,db:Session=Depends(get_db)):
    import csv,io
    event=get(db,Event,event_id)
    groups=result_groups(db,event_id)
    if not groups: raise HTTPException(404,'Noch keine Nennungen.')
    if any(not g['ready'] for g in groups): raise HTTPException(409,'Alle Klassen müssen vollständig erfasst sein.')
    output=io.StringIO(newline='')
    writer=csv.writer(output,delimiter=';')
    writer.writerow(['Veranstaltung','Datum','Klasse','Starterzahl','Platz','Punkte B','Startnummer','Name','Anschrift','E-Mail','Verein','ADAC-Mitgliedsnummer','Fahrzeug','HCF','Fehler1 nach HCF','Fehler2','Gesamt','NiW-Grund','Kontaktdaten'])
    def safe(value):
        value=str(value)
        return "'"+value if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')) else value
    for row in adac_rows(db,groups):
        e=row['entry'];contact=row['contact']
        values=[event.name,event.event_date.strftime('%d.%m.%Y'),e.class_code,row['participant_count'],row['rank'],row['points_b'] if row['points_b'] is not None else '',e.start_number,e.driver_name,
                contact.get('address',''),contact.get('email',''),contact.get('club',''),contact.get('adac_number',''),
                e.vehicle_snapshot['manufacturer']+' '+e.vehicle_snapshot['model'],format_hcf(e.hcf),
                format_hcf(row['error1']) if row['error1'] is not None else '',format_hcf(row['error2']) if row['error2'] is not None else '',
                format_hcf(row['total']) if row['total'] is not None else '',e.niw_reason,
                'Aktuelle Stammdaten (Altbestand)' if row['legacy_contact'] else 'Stand bei Nennung']
        writer.writerow([safe(v) for v in values])
    return Response(('\ufeff'+output.getvalue()).encode('utf-8'),media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition':f'attachment; filename="adac-event-{event_id}.csv"'})


from backend.schemas import EventClassInput, TeamInput


def available_classes(db,event_id=None):
    query=select(EventClass.code)
    if event_id is not None: query=query.where(EventClass.event_id==event_id)
    return sorted(set(db.scalars(query)) | (set(CLASSES) if event_id is None else set()))


def validate_class(db,code,event_id=None):
    if code not in available_classes(db,event_id):
        raise HTTPException(422,'Klasse zuerst unter Veranstaltungsklassen anlegen.')


@app.post('/api/events/{event_id}/classes',status_code=201)
def add_event_class(event_id:int,data:EventClassInput,db:Session=Depends(get_db)):
    get(db,Event,event_id)
    row=db.get(EventClass,(event_id,data.code))
    if row:
        row.section_group=data.section_group
        row.trophy_count=data.trophy_count
    else: db.add(EventClass(event_id=event_id,**data.model_dump()))
    commit(db)
    return {'status':'saved'}


@app.delete('/api/events/{event_id}/classes/{code}')
def remove_event_class(event_id:int,code:str,db:Session=Depends(get_db)):
    row=db.get(EventClass,(event_id,code))
    if row is None: raise HTTPException(404,'Klasse nicht gefunden.')
    if db.scalar(select(Entry.id).where(Entry.event_id==event_id,Entry.class_code==code).limit(1)):
        raise HTTPException(409,'Klasse enthält Nennungen. Zuerst die Nennungen einer anderen Klasse zuordnen.')
    db.delete(row);commit(db);return {'status':'deleted'}


def save_team(db,event_id,data,team=None):
    entries=list(db.scalars(select(Entry).where(Entry.event_id==event_id,Entry.start_number.in_(data.start_numbers))))
    if len(entries)!=len(data.start_numbers): raise HTTPException(422,'Alle Startnummern müssen für diese Veranstaltung genannt sein.')
    if team is None:
        team=Team(event_id=event_id,name=data.name);db.add(team)
    else:
        if team.version!=data.version: raise HTTPException(409,'Mannschaft inzwischen geändert. Bitte neu laden.')
        team.name=data.name;team.version+=1
    current={m.entry_id:m for m in team.members}
    team.members[:]=[current.get(e.id) or TeamMember(entry_id=e.id) for e in entries]
    commit(db);return {'id':team.id,'version':team.version}


@app.post('/api/events/{event_id}/teams',status_code=201)
def create_team(event_id:int,data:TeamInput,db:Session=Depends(get_db)):
    get(db,Event,event_id);return save_team(db,event_id,data)


@app.put('/api/teams/{team_id}')
def update_team(team_id:int,data:TeamInput,db:Session=Depends(get_db)):
    team=get(db,Team,team_id);return save_team(db,team.event_id,data,team)


def team_results(db,event_id):
    groups=result_groups(db,event_id)
    scored={r['entry'].id:r for g in groups for r in g['rows']}
    results=[]
    for team in db.scalars(select(Team).where(Team.event_id==event_id).order_by(Team.name)):
        members=[]
        for member in team.members:
            entry=db.get(Entry,member.entry_id)
            row=scored.get(entry.id)
            members.append(dict(entry=entry,points=row['points_b'] if row else None,ready=row is not None,counted=False))
        members.sort(key=lambda m:(-(m['points'] or 0),m['entry'].start_number))
        ready=all(m['ready'] for m in members)
        if ready:
            for m in members[:3]: m['counted']=True
        results.append(dict(team=team,members=members,ready=ready,total=sum(m['points'] or 0 for m in members[:3]) if ready else None,rank=None))
    # A team placing is only final when all nominated teams are complete.
    if results and all(r['ready'] for r in results):
        results.sort(key=lambda r:(-r['total'],r['team'].name.casefold(),r['team'].id))
        previous=None;rank=0
        for index,row in enumerate(results,1):
            if row['total']!=previous: rank=index
            row['rank']=rank;previous=row['total']
    return results


@app.get('/print/teams/{event_id}')
def print_teams(event_id:int,request:Request,db:Session=Depends(get_db)):
    event=get(db,Event,event_id);rows=team_results(db,event_id)
    if not rows: raise HTTPException(404,'Noch keine Mannschaften genannt.')
    if not all(row['ready'] for row in rows): raise HTTPException(409,'Die zugehörigen Klassen sind noch nicht vollständig erfasst.')
    return render(request,'print_teams.html',event=event,team_results=rows)


def score_overview(db,event_id,class_code):
    query=select(Entry).where(Entry.event_id==event_id)
    if class_code: query=query.where(Entry.class_code==class_code)
    rows=[]
    for entry in db.scalars(query.order_by(Entry.class_code,Entry.start_number)):
        rows.append(dict(entry=entry,**score_totals(entry)))
    return dict(selected_class=class_code,score_rows=rows)


@app.get('/api/drivers/available-start-numbers')
def free_start_numbers(db:Session=Depends(get_db)):
    used=set(db.scalars(select(Driver.start_number)))
    free=[n for n in range(1,1000) if n not in used]
    return dict(next_number=free[0] if free else None,free_numbers=free)


@app.get('/print/drivers/{driver_id}/vehicles')
@app.get('/print/drivers/{driver_id}/vehicles/{vehicle_id}')
def vehicle_cards(driver_id:int,request:Request,vehicle_id:int|None=None,db:Session=Depends(get_db)):
    driver=get(db,Driver,driver_id)
    query=select(Vehicle).join(DriverVehicle,DriverVehicle.vehicle_id==Vehicle.id).where(DriverVehicle.driver_id==driver_id).order_by(Vehicle.id)
    if vehicle_id is not None: query=query.where(Vehicle.id==vehicle_id)
    vehicles=list(db.scalars(query))
    if not vehicles: raise HTTPException(404,'Kein zugeordnetes Fahrzeug für diese Startnummer gefunden.')
    return render(request,'vehicle_cards.html',driver=driver,vehicles=vehicles)
