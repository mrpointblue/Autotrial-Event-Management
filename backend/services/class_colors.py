"""Class highlights based on the supplied 21 September 2025 cards."""
COLORS = {'neutral': 'Weiß (keine Farbe)', 'yellow': 'Gelb', 'green': 'Grün', 'red': 'Rot', 'orange': 'Orange', 'blue': 'Blau'}
DEFAULTS = {'Q1':'yellow','Q2N':'yellow','Q2-N':'yellow','S1':'yellow','S2':'yellow','Q2':'red','V1':'red','O2':'green','Q3':'green','J':'green','N':'green'}
def default_color(code):
    return DEFAULTS.get(code.upper().replace(' ', ''), 'neutral')
