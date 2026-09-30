from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from backend.database import SessionLocal
from backend.models import AppSetting

DEFAULTS=dict(timezone='Europe/Berlin',offset_seconds=0,logo_enabled=True,logo_png=None)

def settings(db=None):
    if db is None:
        with SessionLocal() as session: return settings(session)
    row=db.get(AppSetting,'general')
    return {**DEFAULTS,**(row.value if row else {})}


def save_settings(db,changes):
    value={**settings(db),**changes}
    row=db.get(AppSetting,'general')
    if row is None: db.add(AppSetting(key='general',value=value))
    else: row.value=value
    db.commit()
    return value


def app_now(db=None):
    config=settings(db)
    return datetime.now(timezone.utc)+timedelta(seconds=config['offset_seconds'])


def display_time(value,config):
    return datetime.fromisoformat(value).astimezone(ZoneInfo(config['timezone'])).strftime('%d.%m.%Y %H:%M:%S %Z')
