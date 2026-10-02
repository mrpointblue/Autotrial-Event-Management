"""Versioned, bounded JSON transport. No SQL or executable content is accepted."""
import base64,hashlib,io,json,uuid
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select,Boolean,Integer,Numeric,Date,JSON,String
from PIL import Image
from backend.database import current_tenant,current_user
from backend.models import Event,Driver,Vehicle,Entry,SectionResult,EntryChange,EventClass,Team,TeamMember,DriverVehicle,AppSetting
from backend.services.settings import settings
from backend.services.class_colors import COLORS

MODELS={'drivers':Driver,'vehicles':Vehicle,'events':Event,'driver_vehicles':DriverVehicle,'event_classes':EventClass,'entries':Entry,'section_results':SectionResult,'entry_changes':EntryChange,'teams':Team,'team_members':TeamMember}
REFS={'driver_id':'drivers','vehicle_id':'vehicles','event_id':'events','entry_id':'entries','team_id':'teams'}
MAX_SIZE=20*1024*1024

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def fail(message):raise HTTPException(422,message)
def rows_for(db,event):
    entries=list(db.scalars(select(Entry).where(Entry.event_id==event.id)))
    entry_ids=[e.id for e in entries]
    teams=list(db.scalars(select(Team).where(Team.event_id==event.id)))
    # Include the organizer's reusable master records and assignments, never user accounts.
    return {'drivers':list(db.scalars(select(Driver))), 'vehicles':list(db.scalars(select(Vehicle))), 'events':[event],
        'driver_vehicles':list(db.scalars(select(DriverVehicle))),
        'event_classes':list(db.scalars(select(EventClass).where(EventClass.event_id==event.id))), 'entries':entries,
        'section_results':list(db.scalars(select(SectionResult).where(SectionResult.entry_id.in_(entry_ids)))),
        'entry_changes':list(db.scalars(select(EntryChange).where(EntryChange.entry_id.in_(entry_ids)))),
        'teams':teams,'team_members':list(db.scalars(select(TeamMember).where(TeamMember.team_id.in_([t.id for t in teams]))))}

def records(db,event):
    groups=rows_for(db,event)
    maps={key:{r.id:r.uid for r in rows} for key,rows in groups.items() if 'uid' in MODELS[key].__table__.columns}
    result={}
    for key,rows in groups.items():
        result[key]=[]
        for row in rows:
            data={c.name:getattr(row,c.name) for c in row.__table__.columns if c.name not in ('id','uid')}
            if hasattr(row,'uid'):data['id']=row.uid
            for ref,target in REFS.items():
                if ref in data:data[ref]=maps[target][data[ref]]
            if key=='entries' and data['vehicle_snapshot']:
                data['vehicle_snapshot']={**data['vehicle_snapshot'],'id':data['vehicle_id']}
            if key=='entry_changes':
                for part in ('before','after'):
                    data[part]=dict(data[part])
                    if 'vehicle_id' in data[part]:data[part]['vehicle_id']=maps['vehicles'].get(data[part]['vehicle_id'],str(data[part]['vehicle_id']))
            result[key].append(jsonable_encoder(data,custom_encoder={Decimal:str}))
        result[key].sort(key=lambda row:canonical(row))
    return result

def export_event(db,event):
    data=records(db,event);checksum=digest(data);key='transfer:'+event.uid
    baseline=db.get(AppSetting,key)
    payload={'format':'autotrial-event','format_version':1,'organizer':{k:current_tenant.get()[k] for k in ('id','name','address','contact')},
        'event_id':event.uid,'revision':event.revision,'updated_at':event.updated_at,'records':data,'digest':checksum,
        'base_digest':baseline.value['digest'] if baseline else checksum,
        'settings':settings(db)}
    if not baseline:
        db.info['importing']=True
        db.add(AppSetting(key=key,value={'digest':checksum}));db.commit()
    return canonical(payload)

def read_package(raw):
    if len(raw)>MAX_SIZE:fail('Veranstaltungsdatei maximal 20 MB.')
    try:
        data=json.loads(raw)
        if data['format']!='autotrial-event' or data['format_version']!=1:fail('Dieses Veranstaltungsformat wird nicht unterstützt.')
        uuid.UUID(data['organizer']['id']);uuid.UUID(data['event_id'])
        if set(data['records'])!=set(MODELS):fail('Veranstaltungsdatei ist unvollständig.')
        if digest(data['records'])!=data['digest']:fail('Die Veranstaltungsdatei ist beschädigt.')
        if len(data['records']['events'])!=1 or data['records']['events'][0]['id']!=data['event_id']:fail('Veranstaltungs-ID stimmt nicht überein.')
        if data['revision']!=data['records']['events'][0]['revision']:fail('Änderungsstand stimmt nicht überein.')
        if sum(len(rows) for rows in data['records'].values())>100000:fail('Zu viele Einträge in der Datei.')
        ids={}
        for key,model in MODELS.items():
            ids[key]=set()
            columns={c.name:c for c in model.__table__.columns if c.name not in ('id','uid')}
            expected=set(columns)|({'id'} if 'uid' in model.__table__.columns else set())
            for row in data['records'][key]:
                if set(row)!=expected:fail('Unbekannte oder fehlende Angaben in '+key+'.')
                if 'id' in row:
                    uuid.UUID(row['id'])
                    if row['id'] in ids[key]:fail('Doppelte Kennung in der Datei.')
                    ids[key].add(row['id'])
                for name,c in columns.items():
                    value=row[name]
                    if value is None:
                        if not c.nullable:fail('Pflichtangabe fehlt: '+name)
                        continue
                    if name in REFS:uuid.UUID(value);continue
                    if isinstance(c.type,Boolean) and type(value)!=bool:fail('Ungültiger Status.')
                    if isinstance(c.type,Integer) and type(value)!=int:fail('Ungültige Zahl.')
                    if isinstance(c.type,Numeric):
                        if not Decimal(str(value)).is_finite():fail('Ungültiger Zahlenwert.')
                    if isinstance(c.type,Date):date.fromisoformat(value)
                    if isinstance(c.type,String) and (not isinstance(value,str) or len(value)>(c.type.length or 100000)):fail('Ungültiger Text.')
                    if isinstance(c.type,JSON) and not isinstance(value,dict):fail('Ungültige Detailangaben.')
        for rows in data['records'].values():
            for row in rows:
                for ref,target in REFS.items():
                    if ref in row and row[ref] not in ids[target]:fail('Eine Zuordnung verweist auf fehlende Daten.')
        from backend.schemas import valid_class_code
        for c in data['records']['event_classes']:
            valid_class_code(c['code'])
            if c['color'] not in COLORS or not 1<=c['required_sections']<=300:fail('Ungültige Klasseneinstellung.')
        codes={c['code'] for c in data['records']['event_classes']}
        if any(e['class_code'] not in codes for e in data['records']['entries']):fail('Eine Nennung hat eine unbekannte Klasse.')
        if any(r.get(key) is not None and Decimal(str(r[key]))<0 for r in data['records']['section_results'] for key in ('error1','error2','points')):fail('Fehlerpunkte dürfen nicht negativ sein.')
        if any(not 1<=d['start_number']<=999 for d in data['records']['drivers']):fail('Startnummer außerhalb 1–999.')
        if data['revision']<1:fail('Ungültiger Änderungsstand.')
        datetime.fromisoformat(data['updated_at'])
        config=data.get('settings',{})
        if not isinstance(config,dict):fail('Ungültige Veranstaltereinstellungen.')
        # Never allow transport data to set a host clock or identity/access settings.
        logo=config.get('logo_png')
        if logo:
            if not isinstance(logo,str) or len(logo)>8*1024*1024:fail('Logo ist zu groß.')
            with Image.open(io.BytesIO(base64.b64decode(logo,validate=True))) as img:
                if img.format!='PNG' or img.width*img.height>16000000:fail('Ungültiges Logo.')
                img.verify()
        return data
    except HTTPException:raise
    except (ValueError,TypeError,KeyError,AttributeError,InvalidOperation,RecursionError,OSError,Image.DecompressionBombError):fail('Keine gültige Veranstaltungsdatei.')

def assess(db,data):
    if data['organizer']['id']!=current_tenant.get()['id']:
        raise HTTPException(409,'Diese Datei gehört zu einem anderen Veranstalter: '+str(data['organizer'].get('name',''))+' ('+data['organizer']['id']+'). Ein Administrator muss diesen Veranstalter zunächst mit dieser ID anlegen bzw. auswählen.')
    local=db.scalar(select(Event).where(Event.uid==data['event_id']))
    if not local:return 'new',None
    local_digest=digest(records(db,local))
    if local_digest==data['digest']:return 'identical',local
    baseline=db.get(AppSetting,'transfer:'+local.uid)
    if local_digest==data.get('base_digest'):return 'incoming_newer',local
    if baseline and baseline.value['digest']==data['digest']:return 'local_newer',local
    return 'both_changed',local

def import_event(db,data):
    state,local=assess(db,data)
    if state=='identical':return {'status':state,'event_id':local.id,'message':'Diese Veranstaltung ist bereits identisch vorhanden.'}
    if local:
        labels={'incoming_newer':'Die Datei enthält Änderungen gegenüber dem gemeinsamen Stand.','local_newer':'Der lokale Stand wurde seit dieser Datei geändert.','both_changed':'Die Stände unterscheiden sich oder wurden auf beiden Seiten geändert.'}
        raise HTTPException(409,labels[state]+' Es wurde nichts überschrieben. Automatische Zusammenführung ist noch nicht freigegeben.')
    db.info['importing']=True
    maps={key:{} for key in MODELS}
    try:
        for key,model in MODELS.items():
            for source in data['records'][key]:
                row=dict(source);uid=row.pop('id',None)
                for ref,target in REFS.items():
                    if ref in row:row[ref]=maps[target][row[ref]]
                for c in model.__table__.columns:
                    if c.name in row and row[c.name] is not None:
                        if isinstance(c.type,Date):row[c.name]=date.fromisoformat(row[c.name])
                        elif isinstance(c.type,Numeric):row[c.name]=Decimal(str(row[c.name]))
                if key=='entries':row['vehicle_snapshot']={**row['vehicle_snapshot'],'id':row['vehicle_id']}
                if key=='entry_changes':
                    for part in ('before','after'):
                        row[part]=dict(row[part])
                        if 'vehicle_id' in row[part]:row[part]['vehicle_id']=maps['vehicles'].get(row[part]['vehicle_id'],row[part]['vehicle_id'])
                if uid:
                    existing=db.scalar(select(model).where(model.uid==uid))
                    if existing:
                        # Master records can be reused only when they match exactly.
                        if key not in ('drivers','vehicles') or any(getattr(existing,k)!=v for k,v in row.items()):
                            raise HTTPException(409,'Ein vorhandener Stammdatensatz wurde anders geändert. Es wurde nichts importiert.')
                        maps[key][uid]=existing.id;continue
                    obj=model(uid=uid,**row);db.add(obj);db.flush();maps[key][uid]=obj.id
                else:
                    pk=tuple(row[c.name] for c in model.__table__.primary_key.columns)
                    existing=db.get(model,pk)
                    if existing:
                        if any(getattr(existing,k)!=v for k,v in row.items()):raise HTTPException(409,'Eine vorhandene Zuordnung unterscheidet sich. Es wurde nichts importiert.')
                    else:db.add(model(**row));db.flush()
        db.add(AppSetting(key='transfer:'+data['event_id'],value={'digest':data['digest']}))
        # Copy organizer appearance only for a fresh store, never overwrite a local logo.
        if current_user.get()['role'] in ('admin','organizer_admin') and db.get(AppSetting,'general') is None:
            config=data.get('settings',{})
            db.add(AppSetting(key='general',value={'logo_png':config.get('logo_png'),'logo_enabled':bool(config.get('logo_enabled',True))}))
        db.commit()
        # Fill missing profile details; preserve any locally maintained details.
        from backend.services.identity import catalog
        with catalog() as identity:
            for field in ('address','contact'):
                value=data['organizer'].get(field,'')
                if current_user.get()['role'] in ('admin','organizer_admin') and isinstance(value,str) and len(value)<=2000:
                    identity.execute(f"UPDATE organizers SET {field}=? WHERE id=? AND {field}=''",(value,current_tenant.get()['id']))
        return {'status':'imported','event_id':maps['events'][data['event_id']],'message':'Veranstaltung vollständig importiert.'}
    except HTTPException:db.rollback();raise
    except Exception as error:
        from sqlalchemy.exc import IntegrityError,StatementError
        db.rollback()
        if isinstance(error,(IntegrityError,StatementError,ValueError,KeyError)):
            raise HTTPException(409,'Startnummer, Zuordnung oder Daten widersprechen dem vorhandenen Stand. Es wurde nichts importiert.')
        raise
