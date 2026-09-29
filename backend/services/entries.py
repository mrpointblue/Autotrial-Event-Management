from datetime import datetime, timezone
from fastapi import HTTPException
from backend.models import Vehicle, EntryChange, Event
from backend.services.scoring import required_sections, recheck_summary
from backend.services.hcf import round_hcf


def edit_entry(db,entry,data):
    if entry.version != data.version:
        raise HTTPException(409,'Nennung inzwischen geändert. Bitte neu laden.')
    try: hcf=round_hcf(data.hcf)
    except ValueError as error: raise HTTPException(422,str(error))
    previous_required=required_sections(db,db.get(Event,entry.event_id),entry.class_code)
    class_changed=data.class_code!=entry.class_code
    vehicle_changed=data.vehicle_id != entry.vehicle_id
    if vehicle_changed:
        vehicle=db.get(Vehicle,data.vehicle_id)
        if vehicle is None: raise HTTPException(422,'Fahrzeug nicht gefunden.')
        snapshot={c.name:str(vehicle.hcf) if c.name=='hcf' else getattr(vehicle,c.name) for c in Vehicle.__table__.columns}
    else:
        # Retain historical technical data; never refresh from a changed master record.
        snapshot=dict(entry.vehicle_snapshot)
    has_results=bool(entry.results) or entry.card_summary is not None
    hcf_changed=hcf != entry.hcf
    fields=('vehicle_id','vehicle_snapshot','class_code','hcf','codriver','paid','technical_approved','paperwork_approved','scoring_status','version')
    def state():
        return {key:str(getattr(entry,key)) if key=='hcf' else getattr(entry,key) for key in fields}
    before=state()
    snapshot['class_code']=data.class_code
    snapshot['hcf']=str(hcf)
    if hcf_changed:
        snapshot['hcf_note']='Nennungskorrektur: '+data.reason
    entry.vehicle_id=data.vehicle_id
    entry.vehicle_snapshot=snapshot
    entry.class_code=data.class_code
    entry.hcf=hcf
    for key in ('codriver','paid','technical_approved','paperwork_approved'):
        setattr(entry,key,getattr(data,key))
    # Paper scores are final HCF-adjusted values: changing HCF/vehicle requires review.
    # Keep the entered figures for comparison, but block result printing until re-saved.
    if (vehicle_changed or hcf_changed) and has_results and entry.scoring_status!='niw':
        entry.scoring_status='pending'
    if class_changed and entry.card_summary:
        recheck_summary(entry,required_sections(db,db.get(Event,entry.event_id),entry.class_code),previous_required)
        if (vehicle_changed or hcf_changed) and entry.scoring_status!='niw': entry.scoring_status='pending'
    entry.version+=1
    db.add(EntryChange(entry_id=entry.id,changed_at=datetime.now(timezone.utc).isoformat(),
                       reason=data.reason,before=before,after=state()))
