"""Pure ranking shared by live tournaments and read-only result projections."""
import math

ENGINE = 'rule-engine-v1'


def rank_rows(rows):
    rows.sort(key=lambda row: (-(row['rating'] if row['rating'] is not None else -math.inf), row['id']))
    previous = None
    for index, row in enumerate(rows):
        # Equal ratings share the same rank; no arbitrary tie-breaking by name.
        rounded = round(row['rating'], 8) if row['rating'] is not None else None
        row['rank'] = (previous['rank'] if previous and rounded == previous['_rating'] else index+1) if rounded is not None else None
        row['_rating'] = rounded
        previous = row
    for row in rows:
        row.pop('_rating')
    return rows
