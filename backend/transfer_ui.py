from fastapi import APIRouter,Depends,File,UploadFile,Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Event
from backend.services.transfer import export_event,read_package,import_event,MAX_SIZE,fail
router=APIRouter()

@router.get('/export/events/{event_id}/trialdata')
def export(event_id:int,db:Session=Depends(get_db)):
    from backend.main import get
    event=get(db,Event,event_id)
    return Response(export_event(db,event),media_type='application/vnd.autotrial.event+json',headers={'Content-Disposition':f'attachment; filename="Autotrial_{event.event_date}_{event.uid}.trialdata"'})

@router.post('/ui/events/import')
async def upload(request:Request,event_file:UploadFile=File(...),db:Session=Depends(get_db)):
    raw=await event_file.read(MAX_SIZE+1)
    if len(raw)>MAX_SIZE:fail('Veranstaltungsdatei maximal 20 MB.')
    result=import_event(db,read_package(raw))
    from backend.main import render
    return render(request,'import_result.html',result=result)
