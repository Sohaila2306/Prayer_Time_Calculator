import math
from datetime import datetime, timedelta, timezone
from timezonefinder import TimezoneFinder
import pytz
import requests

def julian_day(year, month, day):
    if month <= 2:
        year -= 1
        month += 12
    A = year // 100
    B = 2 - A + (A // 4)
    JD = int(365.25*(year + 4716)) + int(30.6001*(month + 1)) + day + B - 1524.5
    return JD

def solar_declination(JD):
    n = JD - 2451545.0
    g = math.radians((357.529 + 0.98560028 * n) % 360)
    q = (280.459 + 0.98564736 * n) % 360
    L = (q + 1.915 * math.sin(g) + 0.020 * math.sin(2*g)) % 360
    e = math.radians(23.439 - 0.00000036 * n)
    sin_decl = math.sin(e) * math.sin(math.radians(L))
    return math.asin(sin_decl)

def equation_of_time(JD):
    n = JD - 2451545.0
    g = math.radians((357.529 + 0.98560028 * n) % 360)
    q = (280.459 + 0.98564736 * n) % 360
    L = (q + 1.915 * math.sin(g) + 0.020 * math.sin(2*g)) % 360
    e = math.radians(23.439 - 0.00000036 * n)
    RA = math.degrees(math.atan2(math.cos(e)*math.sin(math.radians(L)), math.cos(math.radians(L)))) % 360
    eq_time = q/15 - RA/15
    if eq_time > 12:
        eq_time -= 24
    elif eq_time < -12:
        eq_time += 24
    return eq_time * 60

def solar_noon(longitude, JD):
    eqt = equation_of_time(JD)
    noon = 12 - (longitude / 15) - (eqt / 60)
    return noon

def asr_time(lat, lon, date, shadow_len, tz):
    JD = julian_day(date.year, date.month, date.day)
    decl = solar_declination(JD)
    noon_utc = solar_noon(lon, JD)
    lat_rad = math.radians(lat)
    angle = math.atan(1 / shadow_len)
    cosH = (math.sin(angle) - math.sin(lat_rad)*math.sin(decl)) / (math.cos(lat_rad)*math.cos(decl))
    cosH = min(1, max(-1, cosH))
    H = math.acos(cosH)
    H_h = math.degrees(H) / 15
    asr_utc = noon_utc + H_h
    hr = int(asr_utc)
    mn = int((asr_utc - hr) * 60)
    dt = datetime(date.year, date.month, date.day, hr, mn, tzinfo=timezone.utc)
    return dt.astimezone(pytz.timezone(tz)).strftime("%H:%M")

def last_third_time(sunset_str, fajr_str, timezone_str, date):
    # Calculate last third of night: time between Maghrib (sunset) and Fajr
    fmt = "%H:%M"
    tz = pytz.timezone(timezone_str)

    sunset = datetime.strptime(sunset_str, fmt).replace(year=date.year, month=date.month, day=date.day)
    fajr = datetime.strptime(fajr_str, fmt).replace(year=date.year, month=date.month, day=date.day)

    # If Fajr is earlier than sunset time (since Fajr is next day)
    if fajr <= sunset:
        fajr += timedelta(days=1)

    night_duration = fajr - sunset
    last_third = sunset + (night_duration * 2/3)
    return last_third.strftime(fmt)

def get_prayer_times(latitude, longitude, madhhab, timezone_str):
    madhab_api = 0 if madhhab == 1 else 1
    url = "https://api.aladhan.com/v1/timings"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "method": 5,
        "madhab": madhab_api,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timezonestring": timezone_str,
    }
    response = requests.get(url, params=params)
    data = response.json()

    if data["code"] != 200:
        raise Exception("API error: " + data.get("status", "Unknown"))

    timings = data["data"]["timings"]
    date_str = data["data"]["date"]["gregorian"]["date"]

    shadow_length = 1 if madhhab == 1 else 2
    asr_corrected = asr_time(latitude, longitude, datetime.now(), shadow_length, timezone_str)
    timings["Asr"] = asr_corrected

    # Calculate last third of the night
    lastthird = last_third_time(timings["Sunset"], timings["Fajr"], timezone_str, datetime.now())
    timings["Lastthird"] = lastthird

    # Filter only requested prayers
    filtered_timings = {k: v for k, v in timings.items() if k in ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha", "Lastthird"]}

    return filtered_timings, date_str

def main():
    print("Enter your location to get today's prayer times:")
    lat = float(input("Latitude (e.g. 30.0444): "))
    lon = float(input("Longitude (e.g. 31.2357): "))

    print("\nChoose Asr shadow length based on madhhab:")
    print("1 - Shafii/Hanbali/Maliki")
    print("2 - Hanafi")
    madhhab = int(input("Enter 1 or 2: "))
    if madhhab not in [1, 2]:
        print("Invalid choice, defaulting to Shafii/Hanbali/Maliki.")
        madhhab = 1

    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=lat, lng=lon)
    if timezone_str is None:
        timezone_str = "UTC"
        print("Warning: Could not detect timezone, using UTC.")

    timings, date_str = get_prayer_times(lat, lon, madhhab, timezone_str)

    print(f"\nPrayer times for {date_str} at ({lat},{lon}) — Timezone: {timezone_str}")
    for prayer in ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha", "Lastthird"]:
        print(f"{prayer}: {timings[prayer]}")

if __name__ == "__main__":
    main()
