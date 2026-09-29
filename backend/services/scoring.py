from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import select
from backend.models import Entry, SectionResult, EventClass
from backend.services.table_b import table_b_points

def raw_values(value):
    if value.error_counts is None:
        return value.error1, value.error2
    c=value.error_counts
    return (Decimal(c.reverse*8+c.ball*20+c.pole*40+c.foot*40),
            Decimal((c.band+c.exit+c.missed_gate+c.assistance)*80+(c.not_driven+c.seatbelt+c.helmet)*900))


def save_scores(entry, event, data):
    if entry.version != data.version:
        raise HTTPException(409, 'Die Bordkarte wurde inzwischen geändert. Bitte neu laden.')
    expected = event.section_count * event.rounds
    if data.card_summary is not None:
        value=data.card_summary
        if data.card_status != 'received':
            raise HTTPException(422,'Bordkartensummen benötigen eine eingegangene Bordkarte.')
        if value.driven_sections is not None and value.driven_sections > expected:
            raise HTTPException(422,f'Es gibt nur {expected} vorgeschriebene Sektionsbefahrungen.')
        reason=data.niw_reason.strip()
        error1,error2=raw_values(value)
        complete=(value.points is not None or (error1 is not None and error2 is not None)) and value.driven_sections is not None
        if complete and not reason and value.driven_sections*10 < expected*7:
            raise HTTPException(422,'Weniger als 70 % gefahren: NiW mit Begründung bestätigen.')
        entry.card_summary=value.model_dump(mode='json',exclude={'driven'})
        entry.card_summary.update(error1=str(error1) if error1 is not None else None,error2=str(error2) if error2 is not None else None)
        entry.results.clear()
        entry.card_status=data.card_status
        entry.niw_reason=reason
        entry.scoring_status='niw' if reason else ('complete' if complete else 'pending')
        entry.version+=1
        return
    if len(data.sections) not in (0, expected):
        raise HTTPException(422, f'Es werden {expected} Sektionswerte benötigt.')
    if data.sections and data.card_status != 'received':
        raise HTTPException(422, 'Sektionswerte benötigen eine eingegangene Bordkarte.')
    reason = data.niw_reason.strip()
    complete = len(data.sections) == expected and all(s.error_counts is not None or s.points is not None or (s.error1 is not None and s.error2 is not None) for s in data.sections)
    if complete and not reason and sum(s.driven for s in data.sections) * 10 < expected * 7:
        raise HTTPException(422, 'Weniger als 70 % gefahren: NiW mit Begründung bestätigen.')
    entry.card_summary=None
    existing = {r.ordinal:r for r in entry.results}
    entry.card_status = data.card_status
    entry.niw_reason = reason
    entry.scoring_status = 'niw' if reason else ('complete' if complete else 'pending')
    # Reuse child rows to avoid unique-index conflicts when replacing a full card.
    entry.results[:] = [existing.get(i) or SectionResult(ordinal=i) for i in range(1,len(data.sections)+1)]
    for row, value in zip(entry.results,data.sections):
        row.error_counts=value.error_counts.model_dump(exclude_unset=True) if value.error_counts is not None else None
        error1,error2=raw_values(value)
        row.error1, row.error2, row.driven = error1,error2,value.driven
        row.points = ((error1 / entry.hcf + error2).quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP)
                      if error1 is not None and error2 is not None else value.points)
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

def score_totals(entry):
    summary=getattr(entry,'card_summary',None)
    if summary:
        raw1,raw2=summary.get('error1'),summary.get('error2')
        if raw1 is not None and raw2 is not None:
            adjusted=Decimal(raw1)/entry.hcf
            return dict(total=(adjusted+Decimal(raw2)).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP),
                        error1=adjusted.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP),error2=Decimal(raw2))
        return dict(total=Decimal(summary.get('points') or 0).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP),error1=None,error2=None)
    # Divide the accumulated raw points once, avoiding per-section rounding drift.
    split=[r for r in entry.results if r.error1 is not None and r.error2 is not None]
    raw1=sum((r.error1 for r in split),Decimal(0))
    error2=sum((r.error2 for r in split),Decimal(0))
    adjusted1=(raw1/entry.hcf).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    legacy=sum((r.points for r in entry.results if r not in split and r.points is not None),Decimal(0))
    total=(raw1/entry.hcf+error2+legacy).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    separated=len(split)==len(entry.results) and bool(split)
    return dict(total=total,error1=adjusted1 if separated else None,error2=error2 if separated else None)


def ranked_results(db,event_id,class_code):
    group = next((g for g in class_progress(db,event_id) if g['class_code']==class_code),None)
    if not group: raise HTTPException(404,'Klasse ohne Nennungen')
    if not group['ready']: raise HTTPException(409,'Die Klasse ist noch nicht vollständig erfasst.')
    entries = list(db.scalars(select(Entry).where(Entry.event_id==event_id,Entry.class_code==class_code)))
    rows = [(e,score_totals(e)['total']) for e in entries if e.scoring_status=='complete']
    rows.sort(key=lambda x:(x[1],x[0].start_number))
    result, previous, rank = [], None, 0
    for index,(entry,total) in enumerate(rows,1):
        if total != previous: rank = index
        result.append(dict(rank=rank,entry=entry,**score_totals(entry),points_b=table_b_points(rank,len(entries)),participant_count=len(entries)))
        previous = total
    result.extend(dict(rank='NiW',entry=e,total=None,error1=None,error2=None,points_b=None,participant_count=len(entries)) for e in sorted(entries,key=lambda e:e.start_number) if e.scoring_status=='niw')
    return result


def result_groups(db,event_id):
    groups=class_progress(db,event_id)
    for group in groups:
        config=db.get(EventClass,(event_id,group['class_code']))
        group['trophies']=config.trophy_count if config and config.trophy_count is not None else max(1,int((Decimal(group['total'])*Decimal('0.3')).quantize(Decimal('1'),rounding=ROUND_HALF_UP)))
        group['rows']=ranked_results(db,event_id,group['class_code']) if group['ready'] else []
    return groups
