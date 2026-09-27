from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from backend.models import Entry, SectionResult

def save_scores(entry, event, data):
    if entry.version != data.version:
        raise HTTPException(409, 'Die Bordkarte wurde inzwischen geändert. Bitte neu laden.')
    expected = event.section_count * event.rounds
    if len(data.sections) not in (0, expected):
        raise HTTPException(422, f'Es werden {expected} Sektionswerte benötigt.')
    if data.sections and data.card_status != 'received':
        raise HTTPException(422, 'Sektionswerte benötigen eine eingegangene Bordkarte.')
    reason = data.niw_reason.strip()
    complete = len(data.sections) == expected and all(s.points is not None for s in data.sections)
    if complete and not reason and sum(s.driven for s in data.sections) * 10 < expected * 7:
        raise HTTPException(422, 'Weniger als 70 % gefahren: NiW mit Begründung bestätigen.')
    existing = {r.ordinal:r for r in entry.results}
    entry.card_status = data.card_status
    entry.niw_reason = reason
    entry.scoring_status = 'niw' if reason else ('complete' if complete else 'pending')
    # Reuse child rows to avoid unique-index conflicts when replacing a full card.
    entry.results[:] = [existing.get(i) or SectionResult(ordinal=i) for i in range(1,len(data.sections)+1)]
    for row, value in zip(entry.results,data.sections):
        row.points, row.driven = value.points, value.driven
    entry.version += 1

def class_progress(db,event_id):
    groups = {}
    for e in db.scalars(select(Entry).where(Entry.event_id == event_id).order_by(Entry.class_code,Entry.start_number)):
        g = groups.setdefault(e.class_code,dict(class_code=e.class_code,total=0,complete=0,niw=0,missing=[]))
        g['total'] += 1
        if e.scoring_status in ('complete','niw'): g['complete'] += 1
        else: g['missing'].append(dict(start_number=e.start_number,name=e.driver_name,card_status=e.card_status))
        g['niw'] += int(e.scoring_status == 'niw')
    return [dict(g,ready=g['total'] == g['complete']) for g in groups.values()]

def ranked_results(db,event_id,class_code):
    group = next((g for g in class_progress(db,event_id) if g['class_code']==class_code),None)
    if not group: raise HTTPException(404,'Klasse ohne Nennungen')
    if not group['ready']: raise HTTPException(409,'Die Klasse ist noch nicht vollständig erfasst.')
    entries = list(db.scalars(select(Entry).where(Entry.event_id==event_id,Entry.class_code==class_code)))
    rows = [(e,sum((r.points for r in e.results),Decimal(0))) for e in entries if e.scoring_status=='complete']
    rows.sort(key=lambda x:(x[1],x[0].start_number))
    result, previous, rank = [], None, 0
    for index,(entry,total) in enumerate(rows,1):
        if total != previous: rank = index
        result.append(dict(rank=rank,entry=entry,total=total))
        previous = total
    result.extend(dict(rank='NiW',entry=e,total=None) for e in sorted(entries,key=lambda e:e.start_number) if e.scoring_status=='niw')
    return result
