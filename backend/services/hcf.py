"""HCF proposal according to ADAC SH regulations, 09 March 2026, section 3."""
from decimal import Decimal

REFERENCES = {'offroad': (300, 139, 193), 'atv': (185, 101, 115), 'quad': (166, 106, 110)}

def calculate_hcf(data):
    if data.kind not in REFERENCES:
        raise ValueError('Für Side-by-Side ist keine eindeutige HCF-Formel festgelegt. Manuelle Bestätigung mit Begründung erforderlich.')
    if any(getattr(data, key) is None for key in ('length_cm', 'width_cm', 'wheelbase_cm')):
        raise ValueError('Für die Berechnung bitte Länge, Breite und Radstand in ganzen cm eingeben.')
    length, width, wheelbase = REFERENCES[data.kind]
    base = (Decimal(data.length_cm-length) + Decimal(data.width_cm-width)*Decimal('2.6') + Decimal(data.wheelbase_cm-wheelbase)*Decimal('2.6'))/100+1
    corrections = []
    if data.kind == 'offroad' and data.closed_body: corrections.append(('Geschlossener Aufbau', 10))
    if data.kind in ('offroad', 'atv'):
        if data.front_lock: corrections.append(('Sperre vorne', -10))
        if data.rear_lock: corrections.append(('Sperre hinten', -10))
    if data.kind == 'offroad' and data.traction_control: corrections.append(('Elektronische Fahrhilfen', -20))
    percent = sum(value for _, value in corrections)
    result = base * (1 + Decimal(percent)/100)
    if result <= 0:
        raise ValueError('Die Maße ergeben keinen positiven HCF. Bitte Maße und Fahrzeugart prüfen.')
    if result >= 1000000:
        raise ValueError('Der HCF ist zu groß. Bitte Maße prüfen.')
    return dict(base=str(base), correction_percent=percent, hcf=str(result), references=[length,width,wheelbase],
                corrections=[dict(label=label,percent=value) for label,value in corrections],
                formula=f'(({data.length_cm} − {length}) / 100) + (({data.width_cm} − {width}) / 100 × 2,6) + (({data.wheelbase_cm} − {wheelbase}) / 100 × 2,6) + 1')

def vehicle_values(data):
    values = data.model_dump(exclude={'hcf_mode'})
    if data.hcf_mode == 'auto':
        result = calculate_hcf(data)
        values['hcf'] = Decimal(result['hcf'])
        values['hcf_note'] = f"Automatisch nach Reglement 2026: Basis {result['base']}; Korrektur {result['correction_percent']:+d} %; HCF {result['hcf']}."
    else:
        if data.hcf is None or not data.hcf_note.strip():
            raise ValueError('Manueller HCF benötigt einen positiven Wert und eine Begründung der technischen Abnahme.')
        values['hcf_note'] = 'Manuell bestätigt: ' + data.hcf_note
    return values
