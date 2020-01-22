import requests
import json
import datetime
import logging
import meteoswiss as ms
import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    PLATFORM_SCHEMA,
    WeatherEntity,
)
import homeassistant.util.dt as dt_util
from homeassistant.const import (TEMP_CELSIUS,CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv
import async_timeout
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=1)

CONDITION_CLASSES = {
    "clear-night": [101,102],
    "cloudy": [5,35,103,104,105],
    "fog": [27,28],
    "hail": [],
    "lightning": [12],
    "lightning-rainy": [13,23,24,25,32,106],
    "partlycloudy": [2,3,4],
    "pouring": [20],
    "rainy": [6,9,14,17,33],
    "snowy": [8,11,16,19,22,30,34],
    "snowy-rainy": [7,10,15,18,21,29,31,107],
    "sunny": [1,26],
    "windy": [],
    "windy-variant": [],
    "exceptional": [],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        
        vol.Inclusive(CONF_LATITUDE, "latlon"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "latlon"): cv.longitude,
       }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.info("Starting asnyc setup platform")
   
    lat = config.get(CONF_LATITUDE, hass.config.latitude)
    lon = config.get(CONF_LONGITUDE, hass.config.longitude)
    async_add_entities([MeteoSwissWeather(lat,lon,config)], True)


class MeteoSwissWeather(WeatherEntity):
    def getPostCode(self,lat,lon):
        s = requests.Session()
        s.headers.update({"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Encoding":"gzip, deflate, sdch",'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/1337 Safari/537.36'})
        geoData= s.get("https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat="+lat+"&lon="+lon+"&zoom=18").text
        geoData = json.loads(geoData)
        return geoData["address"]["postcode"]

    def __init__(self,lat,lon,config):
        """Initialise the platform with a data instance and station name."""
        
        self._station_name = None
        self._condition = None
        self._forecast = None
        self._description = None
        
        _LOGGER.debug("meteo-swiss INIT")
        
        self.postCode = self.getPostCode(str(lat),str(lon))
        _LOGGER.debug("Lat : "+str(lat)+" lon : "+str(lon)+" --> found post code :"+self.postCode)
        with async_timeout.timeout(10):
            allStation = ms.get_all_stations()
            self._station_name = allStation['GVE']['name']

    async def async_update(self):
        """Update Condition and Forecast."""
        _LOGGER.debug("meteo-swiss async update")
        
        with async_timeout.timeout(10):
            self._condition = ms.get_current_condition("GVE")
            self._forecastData = ms.get_forecast(self.postCode)
            
        
        #with async_timeout.timeout(10):    
    @property
    def name(self):
        return self._station_name
    @property
    def temperature(self):
        return float(self._condition[0]['tre200s0'])
    @property
    def pressure(self):
        return float(self._condition[0]['prestas0'])
    @property
    def state(self):
        symbolId = self._forecastData["data"]["current"]['weather_symbol_id']
        print(self._forecastData)
        cond =  next(
                    (
                        k
                        for k, v in CONDITION_CLASSES.items()
                        if int(symbolId) in v
                    ),
                    None,
                )
        _LOGGER.debug("Current symbol is %s condition is : %s"%(symbolId,cond))
        return cond
    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS
    @property
    def humidity(self):
        """Return the name of the sensor."""
        return float(self._condition[0]['ure200s0'])
    @property
    def wind_speed(self):
        """Return the name of the sensor."""
        return float(self._condition[0]['fu3010z0'])
    @property
    def attribution(self):
        return "Weather forecast from MeteoSwiss (https://www.meteoswiss.admin.ch/)"
    @property
    def wind_bearing(self):
        return ms.get_wind_bearing(self._condition[0]['dkl010z0'])
   
    @property
    def forecast(self): 
        currentDate = datetime.datetime.now()
        one_day = datetime.timedelta(days=1)
        fcdata_out = []
        for forecast in self._forecastData["data"]["forecasts"]:
            currentDate = currentDate + one_day
            data_out = {}
            data_out[ATTR_FORECAST_TIME] = currentDate.strftime("%Y-%m-%d")
            data_out[ATTR_FORECAST_TEMP_LOW]=float(forecast["temp_low"])
            data_out[ATTR_FORECAST_TEMP]=float(forecast["temp_high"])
            data_out[ATTR_FORECAST_CONDITION] = next(
                            (
                                k
                                for k, v in CONDITION_CLASSES.items()
                                if int(forecast["weather_symbol_id"]) in v
                            ),
                            None,
                        )
            fcdata_out.append(data_out)
        return fcdata_out
        
    