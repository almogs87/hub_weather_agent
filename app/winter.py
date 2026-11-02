"""Versioned daily snowfall sensitivity profile; not a closure prediction."""
from dataclasses import dataclass
from datetime import date
from .scenarios import Disruption
from .weather import finite

SOURCES=[
    'https://www.weather.gov/safety/winter-ww',
    'https://www.weather.gov/safety/winter-snow-squall',
    'https://ops.fhwa.dot.gov/weather/roadimpact.htm',
    'https://www.faa.gov/air_traffic/publications/aim_html/chap4_section_3.html',
]

@dataclass(frozen=True)
class SnowBand:
    threshold_cm: float
    available_fraction: float
    recovery_days: int

@dataclass(frozen=True)
class WinterProfile:
    id: str = 'daily-snow-sensitivity-v1'
    bands: tuple = (SnowBand(5,.8,0),SnowBand(15,.5,1),SnowBand(25,.1,2))

    def validate(self):
        previous=0
        for band in self.bands:
            if not finite(band.threshold_cm) or band.threshold_cm<=previous:
                raise ValueError('Snow thresholds must be positive and strictly increasing')
            if not finite(band.available_fraction) or not 0<=band.available_fraction<=1:
                raise ValueError('Invalid available fraction')
            if type(band.recovery_days) is not int or not 0<=band.recovery_days<=30:
                raise ValueError('Invalid recovery period')
            previous=band.threshold_cm
        if not self.bands:
            raise ValueError('At least one band required')

    def describe(self):
        self.validate()
        return dict(id=self.id,bands=[vars(b) for b in self.bands],basis='Illustrative sensitivity assumptions; neither official warning thresholds nor calibrated operational impacts.',sources=SOURCES,limitations=[
            'Daily local-calendar snowfall cannot reproduce rolling 12/24-hour warning criteria.',
            'No inference of blizzard, freezing rain, snow squalls, road closure or flight cancellation.',
            'Official heavy-snow criteria vary geographically.',
            'Capacity loss and recovery require validation against company operations.'])

def snowfall_disruptions(hub_id,rows,profile=None):
    profile=profile or WinterProfile()
    profile.validate()
    events=[]
    seen=set()
    for row in rows:
        day=date.fromisoformat(row['date'])
        if day in seen:
            raise ValueError('Duplicate weather date')
        seen.add(day)
        snow=row.get('snowfall_sum')
        if snow is None or not finite(snow) or snow<0:
            raise ValueError('Replay requires valid snowfall on every supplied day')
        selected=[b for b in profile.bands if snow>=b.threshold_cm]
        if selected:
            band=selected[-1]
            events.append(Disruption((hub_id,),day,1,band.available_fraction,band.recovery_days,'snow-proxy:'+day.isoformat()))
    return events
