from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.models import CLASSES
import re

def valid_class_code(value):
    if not re.fullmatch(r"[\w][\w .-]{0,29}",value) or value.casefold() in ("all","adac"):
        raise ValueError("Klasse: 1 bis 30 Zeichen, Buchstaben, Zahlen, Leerzeichen, Punkt oder Bindestrich.")
    return value

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
        return valid_class_code(v)

class EventInput(Input):
    name: str = Field(min_length=1,max_length=150)
    event_date: date
    location: str = ''
    organizer: str = ''
    section_count: int = Field(default=6,ge=1,le=30)
    rounds: int = Field(default=1,ge=1,le=10)

class LinkInput(Input):
    vehicle_id: int
    is_default: bool = False

class EntryInput(Input):
    class_code: str | None = None
    driver_id: int
    vehicle_id: int | None = None
    codriver: str = ''
    paid: bool = False
    technical_approved: bool = False
    paperwork_approved: bool = False

class ErrorCounts(Input):
    reverse: int = Field(ge=0,le=100000)
    ball: int = Field(ge=0,le=100000)
    pole: int = Field(ge=0,le=100000)
    foot: int = Field(ge=0,le=100000,default=0)
    band: int = Field(ge=0,le=100000)
    exit: int = Field(ge=0,le=100000)
    missed_gate: int = Field(ge=0,le=100000)
    not_driven: int = Field(ge=0,le=100000)

class SectionInput(Input):
    error_counts: ErrorCounts | None = None
    points: Decimal | None = Field(default=None,ge=0,max_digits=14,decimal_places=4,allow_inf_nan=False)
    error1: Decimal | None = Field(default=None,ge=0,max_digits=12,decimal_places=2,allow_inf_nan=False)
    error2: Decimal | None = Field(default=None,ge=0,max_digits=12,decimal_places=2,allow_inf_nan=False)
    driven: bool = True

    @model_validator(mode='after')
    def exclusive_values(self):
        if (self.points is not None and (self.error1 is not None or self.error2 is not None)) or (self.error_counts is not None and any(v is not None for v in (self.points,self.error1,self.error2))):
            raise ValueError('Gesamtwert und getrennte Fehler dürfen nicht gleichzeitig angegeben werden.')
        return self

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

class EntryEditInput(Input):
    version: int = Field(ge=1)
    vehicle_id: int
    class_code: str
    hcf: Decimal = Field(gt=0,max_digits=12,decimal_places=6,allow_inf_nan=False)
    codriver: str = ''
    paid: bool
    technical_approved: bool
    paperwork_approved: bool
    reason: str = Field(min_length=1,max_length=500)

    @field_validator('class_code')
    @classmethod
    def valid_class(cls,value):
        return valid_class_code(value)


class EventClassInput(Input):
    trophy_count: int | None = Field(default=None,ge=0,le=10000)
    code: str
    section_group: str = Field(default='',max_length=100)
    @field_validator('code')
    @classmethod
    def validate_code(cls,value): return valid_class_code(value)

class TeamInput(Input):
    name: str = Field(min_length=1,max_length=100)
    start_numbers: list[int] = Field(min_length=3,max_length=5)
    version: int = Field(default=1,ge=1)
    @field_validator('start_numbers')
    @classmethod
    def unique_members(cls,value):
        if len(set(value)) != len(value): raise ValueError('Jeder Fahrer darf innerhalb einer Mannschaft nur einmal vorkommen.')
        return value
