"""Prayer.py - daily Islamic prayer times for any place on Earth.

Everything is worked out from the position of the sun, so it runs offline.
Run it with no arguments and it will ask for your location, or pass the
details on the command line:

    python Prayer.py
    python Prayer.py --lat 30.0444 --lon 31.2357 --madhhab hanafi
    python Prayer.py --lat 21.4225 --lon 39.8262 --date 2025-03-01

The default method is the one used by the Egyptian General Authority of Survey
(Fajr at 19.5 degrees below the horizon, Isha at 17.5). Change FAJR_ANGLE and
ISHA_ANGLE below if your community follows a different convention.
"""

from __future__ import annotations

import argparse
import math
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# How far below the horizon the sun is at Fajr and Isha (Egyptian method).
FAJR_ANGLE = 19.5
ISHA_ANGLE = 17.5

# Sunrise and sunset are measured when the top edge of the sun touches the
# horizon. -0.833 degrees accounts for atmospheric refraction plus the sun's radius.
HORIZON_ANGLE = -0.833

# Asr begins when an object's shadow is this many times its own length, plus
# the length of its shadow at noon. "shafii" also covers the Hanbali and Maliki schools.
ASR_SHADOW = {"shafii": 1, "hanafi": 2}

PRAYER_ORDER = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha", "Last third"]


# --------------------------------------------------------------------------
# Astronomy
# --------------------------------------------------------------------------

def julian_day(day: date) -> float:
    """Julian day number at 00:00 UT on the given calendar date."""
    # 2000-01-01 has proleptic ordinal 730120 and Julian day 2451544.5 at midnight.
    return day.toordinal() + 1721424.5


def sun_position(jd: float) -> tuple[float, float]:
    """Return (declination in radians, equation of time in hours) for a Julian day.

    These are the low-precision formulas from the Astronomical Almanac. They are
    good to a few hundredths of a degree, which is well under a minute of prayer time.
    """
    n = jd - 2451545.0
    mean_long = (280.460 + 0.9856474 * n) % 360
    anomaly = math.radians((357.528 + 0.9856003 * n) % 360)
    ecliptic_long = math.radians(
        mean_long + 1.915 * math.sin(anomaly) + 0.020 * math.sin(2 * anomaly))
    tilt = math.radians(23.439 - 0.0000004 * n)

    declination = math.asin(math.sin(tilt) * math.sin(ecliptic_long))
    right_ascension = math.degrees(
        math.atan2(math.cos(tilt) * math.sin(ecliptic_long), math.cos(ecliptic_long))) % 360

    # Equation of time: how far the real sun runs ahead of (or behind) the clock sun.
    diff = (mean_long - right_ascension + 180) % 360 - 180
    return declination, diff / 15


def hour_angle(altitude: float, lat: float, declination: float) -> float | None:
    """Hours between solar noon and the moment the sun is at `altitude` degrees.

    Returns None when the sun never reaches that altitude on this day, which is
    what happens to Fajr and Isha in summer at high latitudes.
    """
    lat = math.radians(lat)
    denominator = math.cos(lat) * math.cos(declination)
    if abs(denominator) < 1e-12:            # exactly at a pole
        return None
    cos_h = (math.sin(math.radians(altitude)) - math.sin(lat) * math.sin(declination)) / denominator
    if not -1 <= cos_h <= 1:
        return None
    return math.degrees(math.acos(cos_h)) / 15


def asr_altitude(lat: float, declination: float, shadow_factor: int) -> float:
    """Sun altitude (degrees) at which Asr begins.

    The shadow at that moment is `shadow_factor` times the object's height *plus*
    whatever shadow it already cast at solar noon, hence the tan term.
    """
    noon_shadow = math.tan(abs(math.radians(lat) - declination))
    return math.degrees(math.atan(1 / (shadow_factor + noon_shadow)))


def _sun_at(day: date, ut_hours: float) -> tuple[float, float]:
    return sun_position(julian_day(day) + ut_hours / 24)


def _solar_noon(day: date, lon: float) -> float:
    """Solar noon in hours UT, counted from 00:00 UT of `day`."""
    t = 12 - lon / 15
    for _ in range(3):
        _, eqt = _sun_at(day, t)
        t = 12 - lon / 15 - eqt
    return t


def _event(day: date, lat: float, lon: float, altitude, after_noon: bool) -> float | None:
    """Time (hours UT from 00:00 UT of `day`) when the sun reaches an altitude.

    `altitude` is a function of the sun's declination so Asr can use it too.
    The sun moves a little during the day, so we repeat the calculation with
    the sun's position at the time we found until it settles.
    """
    t = _solar_noon(day, lon)
    for _ in range(4):
        declination, eqt = _sun_at(day, t)
        h = hour_angle(altitude(declination), lat, declination)
        if h is None:
            return None
        noon = 12 - lon / 15 - eqt
        t = noon + h if after_noon else noon - h
    return t


def _at(day: date, hours: float | None) -> datetime | None:
    """Turn 'hours after 00:00 UT of day' into an aware datetime."""
    if hours is None:
        return None
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(hours=hours)


def _nearest_minute(moment: datetime) -> datetime:
    return (moment + timedelta(seconds=30)).replace(second=0, microsecond=0)


# --------------------------------------------------------------------------
# Public calculation
# --------------------------------------------------------------------------

def calculate_prayer_times(lat: float, lon: float, day: date, tz: ZoneInfo,
                           madhhab: str = "shafii") -> dict[str, datetime | None]:
    """Prayer times for one calendar day at one place.

    `lat` is positive north, `lon` is positive east. `day` is the local calendar
    date. The result maps each name in PRAYER_ORDER to a timezone-aware datetime
    rounded to the nearest minute, or to None if it doesn't occur that day
    (for example Isha during a high-latitude summer).
    """
    if not -90 <= lat <= 90:
        raise ValueError("Latitude must be between -90 and 90.")
    if not -180 <= lon <= 180:
        raise ValueError("Longitude must be between -180 and 180.")
    if madhhab not in ASR_SHADOW:
        raise ValueError(f"madhhab must be one of: {', '.join(ASR_SHADOW)}")

    factor = ASR_SHADOW[madhhab]

    def fixed(angle):
        return lambda _declination: angle

    fajr = _event(day, lat, lon, fixed(-FAJR_ANGLE), after_noon=False)
    sunrise = _event(day, lat, lon, fixed(HORIZON_ANGLE), after_noon=False)
    dhuhr = _solar_noon(day, lon)
    asr = _event(day, lat, lon, lambda d: asr_altitude(lat, d, factor), after_noon=True)
    maghrib = _event(day, lat, lon, fixed(HORIZON_ANGLE), after_noon=True)
    isha = _event(day, lat, lon, fixed(-ISHA_ANGLE), after_noon=True)

    # The night runs from sunset until tomorrow's Fajr; the last third starts
    # two thirds of the way through it.
    next_day = day + timedelta(days=1)
    next_fajr = _at(next_day, _event(next_day, lat, lon, fixed(-FAJR_ANGLE), after_noon=False))
    sunset = _at(day, maghrib)
    last_third = None
    if sunset is not None and next_fajr is not None:
        last_third = sunset + (next_fajr - sunset) * 2 / 3

    moments = {
        "Fajr": _at(day, fajr),
        "Sunrise": _at(day, sunrise),
        "Dhuhr": _at(day, dhuhr),
        "Asr": _at(day, asr),
        "Maghrib": sunset,
        "Isha": _at(day, isha),
        "Last third": last_third,
    }
    return {name: (_nearest_minute(m).astimezone(tz) if m else None)
            for name, m in moments.items()}


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

def format_time(moment: datetime | None, day: date) -> str:
    if moment is None:
        return "does not occur on this date"
    text = moment.strftime("%H:%M")
    shift = (moment.date() - day).days
    if shift == 1:
        text += "  (after midnight)"
    elif shift == -1:
        text += "  (previous evening)"
    return text


def ask_number(prompt: str, low: float, high: float) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            value = float(raw)
        except ValueError:
            print("  Please type a number, for example 30.0444")
            continue
        if low <= value <= high:
            return value
        print(f"  That needs to be between {low:g} and {high:g}.")


def ask_madhhab() -> str:
    print("\nWhich school should be used for Asr?")
    print("  1 - Shafi'i / Hanbali / Maliki (shadow equals the object)")
    print("  2 - Hanafi (shadow is twice the object)")
    while True:
        choice = input("Enter 1 or 2 [1]: ").strip() or "1"
        if choice in ("1", "2"):
            return "shafii" if choice == "1" else "hanafi"
        print("  Please type 1 or 2.")


def find_timezone(lat: float, lon: float, override: str | None) -> ZoneInfo:
    """Work out the timezone from coordinates (or use the one the user gave)."""
    if override:
        try:
            return ZoneInfo(override)
        except (ZoneInfoNotFoundError, ValueError):
            sys.exit(f"Unknown timezone '{override}'. Use a name like Africa/Cairo.")

    try:
        from timezonefinder import TimezoneFinder
    except ImportError:
        print("Note: 'timezonefinder' isn't installed, so times are shown in UTC.\n"
              "      Install it with:  pip install timezonefinder  (or pass --tz).\n")
        return ZoneInfo("UTC")

    name = TimezoneFinder().timezone_at(lat=lat, lng=lon)
    if name is None:
        print("Note: couldn't detect a timezone for these coordinates, showing UTC.\n")
        return ZoneInfo("UTC")
    return ZoneInfo(name)


def build_parser() -> argparse.ArgumentParser:
    def latitude(text):
        value = float(text)
        if not -90 <= value <= 90:
            raise argparse.ArgumentTypeError("must be between -90 and 90")
        return value

    def longitude(text):
        value = float(text)
        if not -180 <= value <= 180:
            raise argparse.ArgumentTypeError("must be between -180 and 180")
        return value

    def iso_date(text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            raise argparse.ArgumentTypeError("use the form YYYY-MM-DD, e.g. 2025-03-01") from None

    parser = argparse.ArgumentParser(
        description="Calculate daily Islamic prayer times for any location. "
                    "Run without options to be asked for your location.")
    parser.add_argument("--lat", type=latitude, help="latitude, north is positive (e.g. 30.0444)")
    parser.add_argument("--lon", type=longitude, help="longitude, east is positive (e.g. 31.2357)")
    parser.add_argument("--madhhab", choices=sorted(ASR_SHADOW), default=None,
                        help="school used for Asr (default: shafii)")
    parser.add_argument("--date", type=iso_date, metavar="YYYY-MM-DD",
                        help="day to calculate (default: today at that location)")
    parser.add_argument("--tz", metavar="NAME",
                        help="timezone name such as Africa/Cairo (default: detected from coordinates)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        interactive = args.lat is None or args.lon is None
        if interactive:
            print("Enter your location to get today's prayer times.")
            lat = args.lat if args.lat is not None else ask_number(
                "Latitude  (north is positive, e.g. 30.0444): ", -90, 90)
            lon = args.lon if args.lon is not None else ask_number(
                "Longitude (east is positive, e.g. 31.2357): ", -180, 180)
        else:
            lat, lon = args.lat, args.lon
        madhhab = args.madhhab or (ask_madhhab() if interactive else "shafii")
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 1

    tz = find_timezone(lat, lon, args.tz)
    day = args.date or datetime.now(tz).date()
    times = calculate_prayer_times(lat, lon, day, tz, madhhab)

    school = "Shafi'i / Hanbali / Maliki" if madhhab == "shafii" else "Hanafi"
    print(f"\nPrayer times for {day.isoformat()}")
    print(f"Location : {lat:.4f}, {lon:.4f}   Timezone: {tz.key}")
    print(f"Method   : Egyptian General Authority of Survey "
          f"(Fajr {FAJR_ANGLE:g}\N{DEGREE SIGN}, Isha {ISHA_ANGLE:g}\N{DEGREE SIGN}), Asr: {school}\n")
    for name in PRAYER_ORDER:
        print(f"  {name:<11} {format_time(times[name], day)}")
    print("\nTimes are calculated, not observed. Check with your local mosque if you need certainty.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
