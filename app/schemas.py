"""Strict contracts for browser requests, model intents and tool execution."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)

class Location(StrictModel):
    id: str=Field(min_length=1,max_length=80)
    latitude: float=Field(ge=-90,le=90)
    longitude: float=Field(ge=-180,le=180)
    timezone: str=Field(min_length=1,max_length=80)

class Intent(StrictModel):
    action: Literal['weather','compare','risk','capabilities','winter_replay','explain','clarify','unsupported']
    location_ids: list[str]
    hazard: Literal['snow','heavy_precipitation','heat','cold','wind','winter','hurricane','flood','hurricane_flood','overall','ice_storm','tornado','drought'] | None
    start: date | None
    end: date | None
    threshold: float | None
    question: str | None

class IndexSettings(StrictModel):
    weights: list[float]=Field(default=[50,25,25],min_length=3,max_length=3)
    frequency_benchmark: float=Field(default=10,gt=0,le=10000)
    recovery_benchmark: float=Field(default=14,gt=0,le=365)
    recovery_days: list[float]=Field(default=[1,3,7],min_length=3,max_length=3)
    bands: dict[str,list[float]]=Field(default_factory=dict)
    event_benchmarks: dict[str,float]=Field(default_factory=lambda: {'hail_inches':3,'wind_knots':100})
    @model_validator(mode='after')
    def check_settings(self):
        if any(x<0 for x in self.weights) or abs(sum(self.weights)-100)>0.01:raise ValueError('Weights must be nonnegative and sum to 100')
        if any(x<0 or x>365 for x in self.recovery_days) or self.recovery_days!=sorted(self.recovery_days):raise ValueError('Recovery values must be ordered from 0 to 365 days')
        if set(self.event_benchmarks)!={'hail_inches','wind_knots'} or any(value<=0 for value in self.event_benchmarks.values()):raise ValueError('Event severity benchmarks must be positive')
        return self

class ChatRequest(StrictModel):
    message: str=Field(min_length=1,max_length=4000)
    conversation_id: str | None=None
    scenario: dict | None=None
    weather_source: Literal['auto','open-meteo','noaa'] | None=None
    index_settings: IndexSettings | None=None

class HubRankingRequest(IndexSettings):
    locations: list[str] = Field(min_length=1,max_length=25)
    hazards: list[str] = Field(min_length=1,max_length=60)
    weather_source: Literal['auto','open-meteo','noaa']='auto'
    @model_validator(mode='after')
    def check_selection(self):
        if len(set(self.locations))!=len(self.locations):raise ValueError('Choose distinct hubs')
        if len(set(self.hazards))!=len(self.hazards):raise ValueError('Choose each hazard once')
        return self

class HubComparisonRequest(HubRankingRequest):
    locations: list[str] = Field(min_length=2,max_length=2)
    selected_period: Literal[5,10,20,30]=10

class HubInput(StrictModel):
    id: str
    capacity: float=Field(gt=0)
    component: Literal['contiguous_us','alaska','hawaii']='contiguous_us'

class DemandInput(StrictModel):
    id: str
    units: float=Field(ge=0)
    component: Literal['contiguous_us','alaska','hawaii']='contiguous_us'

class LinkInput(StrictModel):
    hub_id: str
    demand_id: str
    distance_km: float=Field(ge=0)

class ScenarioInput(StrictModel):
    hubs: list[HubInput]=Field(min_length=1,max_length=30)
    demands: list[DemandInput]=Field(min_length=1,max_length=100)
    links: list[LinkInput]=Field(max_length=3000)
    max_distance_km: float=Field(gt=0)
    start: date
    end: date
    # Mapping to explicitly registered coordinates, never an automatic siting choice.
    hub_locations: dict[str,str]

    @model_validator(mode='after')
    def check_window(self):
        if self.end<self.start or (self.end-self.start).days>365:
            raise ValueError('Replay must span between 1 and 366 days')
        return self

class ComparisonInput(StrictModel):
    reference_name: str=Field(default='Reference network',min_length=1,max_length=80)
    candidate_name: str=Field(default='Candidate network',min_length=1,max_length=80)
    reference: ScenarioInput
    candidate: ScenarioInput

    @model_validator(mode='after')
    def comparable(self):
        a,b=self.reference,self.candidate
        if (a.start,a.end,a.max_distance_km)!=(b.start,b.end,b.max_distance_km):
            raise ValueError('Both networks require identical dates and service-distance limits')
        if sorted((d.id,d.units,d.component) for d in a.demands)!=sorted((d.id,d.units,d.component) for d in b.demands):
            raise ValueError('Both networks must serve identical demand areas and quantities')
        common=set(a.hub_locations)&set(b.hub_locations)
        for identifier in common:
            if a.hub_locations[identifier]!=b.hub_locations[identifier]:
                raise ValueError('A shared hub must retain the same weather location')
        ac={h.id:h.component for h in a.hubs}
        bc={h.id:h.component for h in b.hubs}
        if any(ac.get(i)!=bc.get(i) for i in common):
            raise ValueError('A shared hub must retain its service component')
        return self
