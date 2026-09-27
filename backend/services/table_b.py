"""ADAC Schleswig-Holstein Wertungstabelle B (user supplied PDF, 27.09.2026)."""
from decimal import Decimal, ROUND_HALF_UP


def table_b_points(rank: int, participants: int) -> int:
    if participants < 1 or rank < 1 or rank > participants:
        raise ValueError('Wertungstabelle B benötigt 1 <= Platz <= Teilnehmerzahl.')
    points = Decimal(800) - Decimal(rank * 300) / Decimal(participants + 1)
    return int(points.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
