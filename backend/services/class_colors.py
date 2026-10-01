"""Class highlights based on the supplied 21 September 2025 cards."""
COLORS = {'neutral': 'Keine Farbe', 'yellow': 'Gelb', 'pink': 'Rosa', 'green': 'Grün', 'blue': 'Blau', 'orange': 'Orange', 'purple': 'Violett'}
DEFAULTS = {'Q1':'yellow','Q2N':'yellow','Q2-N':'yellow','S1':'yellow','S2':'yellow','Q2':'pink','V1':'pink','O2':'green','Q3':'green','J':'green','N':'green'}
def default_color(code):
    return DEFAULTS.get(code.upper().replace(' ', ''), 'neutral')
