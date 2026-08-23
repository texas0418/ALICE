#!/usr/bin/env python3
"""Pull current conditions and the hourly outlook from Open-Meteo.

No API key, no account, no rate limit worth worrying about — which is why it was
chosen over the usual providers. Coordinates come from config.local.json so the
home location never appears in committed source.
"""
import json, os, urllib.parse, urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {'User-Agent': 'jarvis-mirror/0.1 (personal smart mirror)'}

# WMO codes, worded for a HUD: short, uppercase, no meteorologist adjectives
WMO = {0:'CLEAR', 1:'MAINLY CLEAR', 2:'PARTLY CLOUDY', 3:'OVERCAST',
       45:'FOG', 48:'FREEZING FOG', 51:'LIGHT DRIZZLE', 53:'DRIZZLE',
       55:'HEAVY DRIZZLE', 56:'FREEZING DRIZZLE', 57:'FREEZING DRIZZLE',
       61:'LIGHT RAIN', 63:'RAIN', 65:'HEAVY RAIN', 66:'FREEZING RAIN',
       67:'FREEZING RAIN', 71:'LIGHT SNOW', 73:'SNOW', 75:'HEAVY SNOW',
       77:'SNOW GRAINS', 80:'RAIN SHOWERS', 81:'RAIN SHOWERS',
       82:'HEAVY SHOWERS', 85:'SNOW SHOWERS', 86:'SNOW SHOWERS',
       95:'THUNDERSTORM', 96:'STORM WITH HAIL', 99:'STORM WITH HAIL'}
PTS = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW']

# US AQI bands. Pollen is deliberately not fetched: Open-Meteo only covers Europe
# for it, and empty fields on a mirror read as a broken sensor.
AQI_BANDS = [(50, 'GOOD'), (100, 'MODERATE'), (150, 'SENSITIVE GROUPS'),
             (200, 'UNHEALTHY'), (300, 'VERY UNHEALTHY'), (10**9, 'HAZARDOUS')]


def aqi_label(v):
    for hi, name in AQI_BANDS:
        if v <= hi:
            return name
    return 'UNKNOWN'


def air(lat, lng, tz):
    q = urllib.parse.urlencode({
        'latitude': lat, 'longitude': lng,
        'current': 'us_aqi,pm2_5,pm10,ozone', 'hourly': 'us_aqi',
        'timezone': tz, 'forecast_days': 1})
    url = 'https://air-quality-api.open-meteo.com/v1/air-quality?' + q
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            d = json.load(r)
        c = d.get('current', {})
        v = c.get('us_aqi')
        if v is None:
            return None
        hourly = [x for x in (d.get('hourly', {}).get('us_aqi') or []) if x is not None]
        return {'aqi': round(v), 'aqiLabel': aqi_label(v),
                'pm25': c.get('pm2_5'), 'pm10': c.get('pm10'), 'ozone': c.get('ozone'),
                'aqiPeak': round(max(hourly)) if hourly else None}
    except Exception:
        return None   # air quality is a bonus; never fail the weather run over it


def compass(deg):
    return PTS[int((deg % 360) / 22.5 + 0.5) % 16]


def hour_label(iso):
    h = int(iso[11:13])
    ap = 'A' if h < 12 else 'P'
    return f'{(h % 12) or 12}{ap}'


def main():
    cfg = json.load(open(os.path.join(ROOT, 'config.local.json')))
    home = cfg.get('home') or {}
    lat, lng = home.get('lat'), home.get('lng')
    if lat is None:
        raise SystemExit('config.local.json needs a "home": {lat, lng, label}')

    q = urllib.parse.urlencode({
        'latitude': lat, 'longitude': lng,
        'current': 'temperature_2m,apparent_temperature,relative_humidity_2m,is_day,'
                   'weather_code,wind_speed_10m,wind_direction_10m,pressure_msl',
        'hourly': 'temperature_2m,precipitation_probability,weather_code',
        'daily': 'sunrise,sunset,temperature_2m_max,temperature_2m_min',
        'temperature_unit': 'fahrenheit', 'wind_speed_unit': 'mph',
        'timezone': home.get('tz', 'America/New_York'), 'forecast_days': 2})
    url = 'https://api.open-meteo.com/v1/forecast?' + q
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        d = json.load(r)

    c, H, D = d['current'], d['hourly'], d['daily']
    now = c['time']
    i0 = H['time'].index(now[:13] + ':00') if (now[:13] + ':00') in H['time'] else 0

    hours = [{'h': hour_label(H['time'][i]),
              't': round(H['temperature_2m'][i]),
              'p': H['precipitation_probability'][i] or 0}
             for i in range(i0, min(i0 + 8, len(H['time'])))]

    # the wettest hour ahead is what actually changes your day
    ahead = [(H['precipitation_probability'][i] or 0, H['time'][i])
             for i in range(i0, min(i0 + 12, len(H['time'])))]
    pk, pk_time = max(ahead) if ahead else (0, '')

    out = {
        'temp': round(c['temperature_2m']), 'feels': round(c['apparent_temperature']),
        'humidity': c['relative_humidity_2m'], 'code': c['weather_code'],
        'sky': WMO.get(c['weather_code'], 'UNKNOWN'),
        'wind': round(c['wind_speed_10m']), 'windDir': compass(c['wind_direction_10m']),
        'pressure': round(c['pressure_msl'] * 0.02953, 2),
        'isDay': bool(c['is_day']),
        'hours': hours, 'peak': pk, 'peakAt': hour_label(pk_time) if pk_time else '',
        'peakClock': pk_time[11:16] if pk_time else '',
        'sunrise': D['sunrise'][0][11:16], 'sunset': D['sunset'][0][11:16],
        'hi': round(D['temperature_2m_max'][0]), 'lo': round(D['temperature_2m_min'][0]),
        'place': home.get('place', 'HOME'),
        'fetched': datetime.now().strftime('%H:%M'),
    }
    a = air(lat, lng, home.get('tz', 'America/New_York'))
    if a:
        out.update(a)

    open(os.path.join(ROOT, 'weatherdata.js'), 'w').write(
        'const WEATHER=' + json.dumps(out, separators=(',', ':')) + ';\n')
    print(f"  {out['temp']}°F (feels {out['feels']}°)  {out['sky']}  "
          f"hum {out['humidity']}%  wind {out['wind']} {out['windDir']}")
    print(f"  hi {out['hi']} / lo {out['lo']}   sunrise {out['sunrise']}  sunset {out['sunset']}")
    print(f"  wettest hour ahead: {out['peak']}% at {out['peakClock'] or 'n/a'}")
    if a:
        print(f"  air quality: AQI {a['aqi']} ({a['aqiLabel']})"
              f"   PM2.5 {a['pm25']}   peak today {a['aqiPeak']}")
    else:
        print('  air quality: unavailable')
    print('  weatherdata.js updated')


if __name__ == '__main__':
    main()
