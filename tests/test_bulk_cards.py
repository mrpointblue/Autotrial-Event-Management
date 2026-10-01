from html.parser import HTMLParser
from test_workflow import client, setup, post
from test_entry_edit import payload


class PrintedPages(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.pages=[]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='article' and 'bordcard-page' in attrs.get('class',''):
            self.pages.append((attrs['data-entry-id'],attrs['data-sheet'],attrs['class'].split()[-1]))


def test_bulk_cards_require_all_approvals_and_never_skip_pending_entries(client):
    event,_,entries=setup(client,count=2,sections=5)
    path=f"/print/cards/{event['id']}"
    ui=f"/ui/events/{event['id']}/checkin"
    assert client.get(path).status_code==200
    assert f'href="{path}"' in client.get(ui).text
    change=dict(version=1,paid=False,technical_approved=False,paperwork_approved=True)
    assert client.put(f"/api/entries/{entries[1]['id']}/checkin",json=change).status_code==200
    blocked=client.get(path)
    assert blocked.status_code==409 and '101' in blocked.text
    assert f'href="{path}"' not in client.get(ui).text
    change.update(version=2,technical_approved=True,paperwork_approved=False)
    assert client.put(f"/api/entries/{entries[1]['id']}/checkin",json=change).status_code==200
    assert client.get(path).status_code==409
    change.update(version=3,paperwork_approved=True)
    assert client.put(f"/api/entries/{entries[1]['id']}/checkin",json=change).status_code==200
    assert client.get(path).status_code==200 # Payment has never been a card-print prerequisite.


def test_duplex_pairs_repeat_for_each_sheet_and_respect_class_section_counts(client):
    event,_,entries=setup(client,count=2,sections=5)
    assert client.post(f"/api/events/{event['id']}/classes",json=dict(code='V1',required_sections=11)).status_code==201
    assert client.put(f"/api/entries/{entries[1]['id']}",json=payload(entries[1])).status_code==200
    html=client.get(f"/print/cards/{event['id']}").text
    expected=[(str(e['id']),str(sheet),side) for e,sheets in [(entries[0],1),(entries[1],3)]
              for sheet in range(1,sheets+1) for side in ['bordcard-front','bordcard-back']]
    assert PrintedPages(html).pages==expected
    assert '5 vorgeschriebene Sektionen' in html and '11 vorgeschriebene Sektionen' in html
    assert 'Sektionen 11 bis 11' in html
    assert 'mindestens 4 zu fahren' in html and 'mindestens 8 zu fahren' in html
    assert '8</td>' in html and '900</td>' in html and 'Abbruchsumme höchstens 900' in html
    single=client.get(f"/print/entries/{entries[1]['id']}").text
    assert PrintedPages(single).pages==expected[2:]


def test_bulk_print_is_event_scoped_read_only_and_empty_safe(client):
    event,_,entries=setup(client,count=1,sections=5)
    other=post(client,'events',dict(name='Andere Veranstaltung',event_date='2026-10-04'))
    assert client.get(f"/print/cards/{other['id']}").status_code==409
    post(client,f"events/{other['id']}/entries",dict(driver_id=entries[0]['driver_id'])) # Unapproved other event.
    path=f"/api/events/{event['id']}/entries/100"
    before=client.get(path).json()
    html=client.get(f"/print/cards/{event['id']}")
    assert html.status_code==200 and len(PrintedPages(html.text).pages)==2
    assert client.get(path).json()==before
    assert client.get('/print/cards/999999').status_code==404


def test_judge_error_descriptions_stay_inside_table_cells(client):
    event,_,_=setup(client,count=1,sections=5)

    class JudgeTable(HTMLParser):
        def __init__(self):
            super().__init__()
            self.active=False
            self.in_cell=False
            self.rows=[]
            self.cells=None
            self.outside=[]
        def handle_starttag(self,tag,attrs):
            if tag=='table' and dict(attrs).get('class')=='judge-errors': self.active=True
            if not self.active: return
            if tag=='tr': self.cells=[]
            if tag in ('td','th'):
                self.in_cell=True
                self.cells.append('')
        def handle_data(self,data):
            if not self.active or not data.strip(): return
            if self.in_cell: self.cells[-1]+=data
            else: self.outside.append(data)
        def handle_endtag(self,tag):
            if not self.active: return
            if tag in ('td','th'): self.in_cell=False
            if tag=='tr': self.rows.append(self.cells)
            if tag=='table': self.active=False

    table=JudgeTable()
    table.feed(client.get(f"/print/cards/{event['id']}").text)
    assert not table.outside, 'Descriptions must not be foster-parented above the table by browsers'
    assert len(table.rows)==12
    assert all(len(row)==2 and all(cell.strip() for cell in row) for row in table.rows)
    assert [row[0] for row in table.rows[1:]]==['8','20','40','40','80','80','80','80','900','900','900']
