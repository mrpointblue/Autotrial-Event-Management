from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, update, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from backend.database import Base, engine, get_db
from backend.models import CLASSES, Driver, Vehicle, DriverVehicle, Event, Entry
from backend.schemas import DriverInput, VehicleInput, EventInput, LinkInput, EntryInput, ScoreInput
from backend.services.hcf import calculate_hcf, vehicle_values, round_hcf, format_hcf
from backend.schemas import HcfInput
from backend.services.scoring import save_scores, class_progress, ranked_results

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        version = conn.exec_driver_sql('PRAGMA user_version').scalar()
        if version not in (0,1): raise RuntimeError('Nicht unterstützte Datenbankversion')
        conn.exec_driver_sql('PRAGMA user_version=1')
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
    return templates.TemplateResponse(request=request,name=name,context=context)

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
    row=Driver(**data.model_dump()); db.add(row); commit(db); return row

@app.get('/api/vehicles')
def vehicles(db:Session=Depends(get_db)): return list(db.scalars(select(Vehicle).order_by(Vehicle.id)))

@app.post('/api/vehicles',status_code=201)
def create_vehicle(data:VehicleInput,db:Session=Depends(get_db)):
    try: values=vehicle_values(data)
    except ValueError as error: raise HTTPException(422,str(error))
    row=Vehicle(**values); db.add(row); commit(db); return row

@app.put('/api/vehicles/{vehicle_id}')
def edit_vehicle(vehicle_id:int,data:VehicleInput,db:Session=Depends(get_db)):
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
    row=Event(**data.model_dump()); db.add(row); commit(db); return row

@app.post('/api/events/{event_id}/entries',status_code=201)
def create_entry(event_id:int,data:EntryInput,db:Session=Depends(get_db)):
    get(db,Event,event_id); driver=get(db,Driver,data.driver_id)
    vehicle_id=data.vehicle_id
    if vehicle_id is None:
        link=db.scalar(select(DriverVehicle).where(DriverVehicle.driver_id==driver.id,DriverVehicle.is_default==True))
        if not link: raise HTTPException(422,'Bitte ein zugeordnetes Fahrzeug auswählen.')
        vehicle_id=link.vehicle_id
    if not db.get(DriverVehicle,(driver.id,vehicle_id)):
        raise HTTPException(422,'Fahrzeug zuerst der Startnummer zuordnen.')
    vehicle=get(db,Vehicle,vehicle_id)
    try: entry_hcf = round_hcf(vehicle.hcf)
    except ValueError as error: raise HTTPException(422,str(error))
    snapshot={c.name:str(entry_hcf) if c.name=='hcf' else getattr(vehicle,c.name) for c in Vehicle.__table__.columns}
    row=Entry(event_id=event_id,driver_id=driver.id,vehicle_id=vehicle.id,start_number=driver.start_number,
        driver_name=driver.name,vehicle_snapshot=snapshot,class_code=vehicle.class_code,hcf=entry_hcf,
        **data.model_dump(exclude={'driver_id','vehicle_id'}))
    db.add(row); commit(db); return row

@app.get('/api/events/{event_id}/entries/{start_number}')
def lookup(event_id:int,start_number:int,db:Session=Depends(get_db)):
    row=db.scalar(select(Entry).where(Entry.event_id==event_id,Entry.start_number==start_number))
    if not row: raise HTTPException(404,'Startnummer ist für diese Veranstaltung nicht genannt.')
    return dict(entry=jsonable_encoder(row),sections=[dict(points=str(r.points) if r.points is not None else None,driven=r.driven) for r in row.results])

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
              page_number:int=Query(default=1,ge=1),db:Session=Depends(get_db)):
    if tab not in ('drivers','vehicles','new-driver','new-vehicle','assign'):
        raise HTTPException(404,'Ansicht nicht gefunden')
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
    return render(request,'master.html',drivers=all_drivers,vehicles=all_vehicles,classes=CLASSES,
                  tab=tab,q=q,class_code=class_code,rows=rows,count=count,pages=pages,page_number=page_number,
                  by_driver=by_driver,by_vehicle=by_vehicle,
                  previous_url=str(request.url.include_query_params(page_number=page_number-1)),
                  next_url=str(request.url.include_query_params(page_number=page_number+1)))

@app.get('/ui/events/{event_id}/{page}')
def event_ui(event_id:int,page:str,request:Request,db:Session=Depends(get_db)):
    if page not in ('checkin','scoring','results'): raise HTTPException(404,'Seite nicht gefunden')
    event=get(db,Event,event_id)
    entries=list(db.scalars(select(Entry).where(Entry.event_id==event_id).order_by(Entry.start_number)))
    return render(request,page+'.html',event=event,drivers=drivers(db),entries=entries,progress=class_progress(db,event_id),page=page)

@app.get('/print/entries/{entry_id}')
def card(entry_id:int,request:Request,db:Session=Depends(get_db)):
    entry=get(db,Entry,entry_id)
    if not entry.technical_approved or not entry.paperwork_approved:
        raise HTTPException(409,'Papierabnahme und technische Abnahme müssen für den Bordkartendruck bestätigt sein.')
    return render(request,'card.html',entry=entry,event=get(db,Event,entry.event_id))

@app.get('/print/events/{event_id}/{class_code}')
def results(event_id:int,class_code:str,request:Request,db:Session=Depends(get_db)):
    event=get(db,Event,event_id)
    return render(request,'print_results.html',event=event,class_code=class_code,rows=ranked_results(db,event_id,class_code))

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
    choices=[dict(id=entry.vehicle_id,label=entry.vehicle_snapshot['manufacturer']+' '+entry.vehicle_snapshot['model'],
                  class_code=entry.class_code,hcf=format_hcf(entry.hcf).replace(',','.'))]
    for item in linked_vehicles(entry.driver_id,db):
        v=item['vehicle']
        if v['id']!=entry.vehicle_id:
            choices.append(dict(id=v['id'],label=v['manufacturer']+' '+v['model'],class_code=v['class_code'],hcf=format_hcf(v['hcf']).replace(',','.')))
    changes=list(db.scalars(select(EntryChange).where(EntryChange.entry_id==entry.id).order_by(EntryChange.id.desc())))
    return render(request,'entry_edit.html',event=get(db,Event,entry.event_id),entry=entry,
                  choices=choices,classes=CLASSES,changes=changes,page='checkin')

@app.put('/api/entries/{entry_id}')
def update_entry(entry_id:int,data:EntryEditInput,db:Session=Depends(get_db)):
    entry=get(db,Entry,entry_id)
    edit_entry(db,entry,data)
    commit(db)
    return dict(id=entry.id,version=entry.version,status=entry.scoring_status)
