from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.models import CLASSES

class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

class DriverInput(Input):
    start_number: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=150)
    address: str = ''
    email: str = ''
    club: str = ''
    adac_number: str = ''

class HcfInput(Input):
    kind: Literal['offroad','atv','quad','sbs'] = 'offroad'
    length_cm: int | None = Field(default=None,gt=0)
    width_cm: int | None = Field(default=None,gt=0)
    wheelbase_cm: int | None = Field(default=None,gt=0)
    front_lock: bool = False
    rear_lock: bool = False
    traction_control: bool = False
    closed_body: bool = False

class VehicleInput(HcfInput):
    manufacturer: str = Field(min_length=1,max_length=100)
    model: str = Field(min_length=1,max_length=100)
    year: str = ''
    plate: str = ''
    tyres: str = ''
    class_code: str
    hcf_mode: Literal['auto', 'manual'] = 'auto'
    hcf: Decimal | None = Field(default=None,gt=0, max_digits=12, decimal_places=6, allow_inf_nan=False)
    hcf_note: str = ''
    @field_validator('class_code')
    @classmethod
    def valid_class(cls,v):
        if v not in CLASSES: raise ValueError('Unbekannte Klasse nach Reglement 2026')
        return v

class EventInput(Input):
    name: str = Field(min_length=1,max_length=150)
    event_date: date
    location: str = ''
    organizer: str = ''
    section_count: int = Field(ge=1,le=30)
    rounds: int = Field(default=1,ge=1,le=10)

class LinkInput(Input):
    vehicle_id: int
    is_default: bool = False

class EntryInput(Input):
    driver_id: int
    vehicle_id: int | None = None
    codriver: str = ''
    paid: bool = False
    technical_approved: bool = False
    paperwork_approved: bool = False

class SectionInput(Input):
    points: Decimal | None = Field(default=None,ge=0,max_digits=14,decimal_places=4,allow_inf_nan=False)
    driven: bool = True

class ScoreInput(Input):
    version: int = Field(ge=1)
    card_status: Literal['missing','received']
    niw_reason: str = ''
    sections: list[SectionInput] = Field(default_factory=list,max_length=300)

class CheckinInput(Input):
    version: int = Field(ge=1)
    paid: bool
    technical_approved: bool
    paperwork_approved: bool
