"""Whole-analysis source selection: never silently blend reanalysis and stations."""
import os
from .weather import WeatherClient
from .noaa import NOAAClient

class WeatherSources:
    def __init__(self,primary=None,secondary=None,source=None):
        self.primary=primary or WeatherClient()
        self.secondary=secondary or NOAAClient()
        self.source=source or os.environ.get('WEATHER_SOURCE','auto')
        if self.source not in ('auto','open-meteo','noaa'):raise ValueError('WEATHER_SOURCE must be auto, open-meteo or noaa')

    def fetch_group(self,requests,hazard='snow',refresh=False):
        if self.source=='open-meteo':
            results={}
            for i,r in requests.items():
                try:results[i]=self.primary.fetch(r,refresh=refresh)
                except (RuntimeError,ValueError) as exc:results[i]=exc
            return results
        failure=None
        if self.source=='auto':
            try:return {i:self.primary.fetch(r,refresh=refresh) for i,r in requests.items()}
            except RuntimeError as exc:failure=str(exc)
        results={}
        for identifier,request in requests.items():
            try:
                result=self.secondary.fetch(request,hazard=hazard,refresh=refresh)
                result['evidence']['fallback_reason']=failure
                result['evidence']['source_policy']='All locations in this analysis use NOAA; no ERA5/station mixing'
                results[identifier]=result
            except RuntimeError as exc:results[identifier]=RuntimeError('NOAA weather data for '+identifier+': '+str(exc))
        return results

    def fetch(self,request,refresh=False,hazard='snow'):
        result=self.fetch_group({'location':request},hazard,refresh)['location']
        if isinstance(result,Exception):raise result
        return result
