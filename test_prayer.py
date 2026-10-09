"""Tests for Prayer.py. Run with:  python -m pytest   (or just: python test_prayer.py)"""

import io
import math
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

import Prayer

CAIRO = (30.0444, 31.2357, ZoneInfo("Africa/Cairo"))


# --- an independent reference ------------------------------------------------
# NOAA's solar calculator uses a different (more precise) set of formulas than
# Prayer.py, so agreement between the two is a real check and not a tautology.

def noaa_sun(jd):
    t = (jd - 2451545.0) / 36525
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m = math.radians(357.52911 + t * (35999.05029 - 0.0001537 * t))
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    c = (math.sin(m) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * m) * (0.019993 - 0.000101 * t) + math.sin(3 * m) * 0.000289)
    omega = math.radians(125.04 - 1934.136 * t)
    app = math.radians(l0 + c - 0.00569 - 0.00478 * math.sin(omega))
    eps0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    eps = math.radians(eps0 + 0.00256 * math.cos(omega))
    decl = math.asin(math.sin(eps) * math.sin(app))
    y = math.tan(eps / 2) ** 2
    l0r = math.radians(l0)
    eqt = 4 * math.degrees(y * math.sin(2 * l0r) - 2 * e * math.sin(m)
                           + 4 * e * y * math.sin(m) * math.cos(2 * l0r)
                           - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * m))
    return decl, eqt / 60


def noaa_sunrise_sunset(lat, lon, day):
    """Sunrise and sunset in hours UT, the NOAA way."""
    jd = Prayer.julian_day(day) + 0.5 - lon / 360
    decl, eqt = noaa_sun(jd)
    lat_r = math.radians(lat)
    cos_h = (math.cos(math.radians(90.833)) / (math.cos(lat_r) * math.cos(decl))
             - math.tan(lat_r) * math.tan(decl))
    h = math.degrees(math.acos(cos_h)) / 15
    noon = 12 - lon / 15 - eqt
    return noon - h, noon + h


def noaa_event(lat, lon, day, after_noon, altitude):
    """Hours UT when the sun reaches `altitude` (a number, or a function of declination)."""
    decl, eqt = noaa_sun(Prayer.julian_day(day) + 0.5 - lon / 360)
    alt = altitude(decl) if callable(altitude) else altitude
    lat_r = math.radians(lat)
    cos_h = ((math.sin(math.radians(alt)) - math.sin(lat_r) * math.sin(decl))
             / (math.cos(lat_r) * math.cos(decl)))
    h = math.degrees(math.acos(cos_h)) / 15
    noon = 12 - lon / 15 - eqt
    return noon + h if after_noon else noon - h


def minutes_between(a, b):
    return abs((a - b).total_seconds()) / 60


# --- astronomy ---------------------------------------------------------------

def test_julian_day_matches_known_epochs():
    assert Prayer.julian_day(date(2000, 1, 1)) == 2451544.5
    assert Prayer.julian_day(date(1858, 11, 17)) == 2400000.5     # modified JD zero


def test_sun_position_agrees_with_noaa_all_year():
    for offset in range(0, 366, 15):
        day = date(2025, 1, 1) + timedelta(days=offset)
        jd = Prayer.julian_day(day) + 0.5
        decl, eqt = Prayer.sun_position(jd)
        ref_decl, ref_eqt = noaa_sun(jd)
        assert abs(math.degrees(decl - ref_decl)) < 0.02, day
        assert abs((eqt - ref_eqt) * 60) < 0.5, day               # half a minute


def test_solstices_and_equinox():
    june, _ = Prayer.sun_position(Prayer.julian_day(date(2025, 6, 21)) + 0.5)
    dec, _ = Prayer.sun_position(Prayer.julian_day(date(2025, 12, 21)) + 0.5)
    march, _ = Prayer.sun_position(Prayer.julian_day(date(2025, 3, 20)) + 0.5)
    assert abs(math.degrees(june) - 23.44) < 0.05
    assert abs(math.degrees(dec) + 23.44) < 0.05
    assert abs(math.degrees(march)) < 0.3


def test_asr_altitude_counts_the_noon_shadow():
    # the original script used a flat 45 degrees; the real value is far lower
    decl = math.radians(-21.2)                                     # mid January
    shafii = Prayer.asr_altitude(30.0444, decl, 1)
    hanafi = Prayer.asr_altitude(30.0444, decl, 2)
    assert 23 < shafii < 25
    assert hanafi < shafii
    # at the equator on an equinox the noon shadow is zero, so it IS 45 degrees
    assert abs(Prayer.asr_altitude(0, 0, 1) - 45) < 1e-9


# --- full calculations -------------------------------------------------------

def test_sunrise_and_sunset_match_noaa_in_many_places():
    places = [("Cairo", 30.0444, 31.2357, "Africa/Cairo"), ("Mecca", 21.4225, 39.8262, "Asia/Riyadh"),
              ("London", 51.5072, -0.1276, "Europe/London"), ("Jakarta", -6.2, 106.85, "Asia/Jakarta"),
              ("Sydney", -33.87, 151.21, "Australia/Sydney"), ("Anchorage", 61.2, -149.9, "America/Anchorage"),
              ("Tahiti", -17.55, -149.57, "Pacific/Tahiti"), ("Auckland", -36.85, 174.76, "Pacific/Auckland")]
    for day in (date(2025, 1, 15), date(2025, 4, 10), date(2025, 9, 23)):
        for name, lat, lon, tzname in places:
            tz = ZoneInfo(tzname)
            got = Prayer.calculate_prayer_times(lat, lon, day, tz)
            rise_ut, set_ut = noaa_sunrise_sunset(lat, lon, day)
            base = datetime(day.year, day.month, day.day, tzinfo=ZoneInfo("UTC"))
            assert minutes_between(got["Sunrise"], base + timedelta(hours=rise_ut)) < 1.5, (name, day)
            assert minutes_between(got["Maghrib"], base + timedelta(hours=set_ut)) < 1.5, (name, day)


def test_fajr_isha_and_asr_match_the_reference():
    places = [(30.0444, 31.2357, "Africa/Cairo"), (21.4225, 39.8262, "Asia/Riyadh"),
              (51.5072, -0.1276, "Europe/London"), (-6.2, 106.85, "Asia/Jakarta"),
              (-33.87, 151.21, "Australia/Sydney")]
    for day in (date(2025, 1, 15), date(2025, 4, 10), date(2025, 9, 23)):
        for lat, lon, tzname in places:
            got = Prayer.calculate_prayer_times(lat, lon, day, ZoneInfo(tzname))
            base = datetime(day.year, day.month, day.day, tzinfo=ZoneInfo("UTC"))
            for name, after, alt in [("Fajr", False, -Prayer.FAJR_ANGLE), ("Isha", True, -Prayer.ISHA_ANGLE)]:
                ref = base + timedelta(hours=noaa_event(lat, lon, day, after, alt))
                assert minutes_between(got[name], ref) < 2, (name, lat, day)
            for school, factor in [("shafii", 1), ("hanafi", 2)]:
                got = Prayer.calculate_prayer_times(lat, lon, day, ZoneInfo(tzname), school)
                ref = base + timedelta(hours=noaa_event(
                    lat, lon, day, True, lambda d: Prayer.asr_altitude(lat, d, factor)))
                assert minutes_between(got["Asr"], ref) < 2, (school, lat, day)


def test_times_come_in_the_right_order():
    for day in (date(2025, 1, 15), date(2025, 6, 21)):
        t = Prayer.calculate_prayer_times(CAIRO[0], CAIRO[1], day, CAIRO[2])
        order = [t[n] for n in ("Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha")]
        assert order == sorted(order)
        assert t["Last third"] > t["Isha"] - timedelta(hours=3)


def test_dhuhr_is_halfway_between_sunrise_and_sunset():
    t = Prayer.calculate_prayer_times(CAIRO[0], CAIRO[1], date(2025, 3, 1), CAIRO[2])
    middle = t["Sunrise"] + (t["Maghrib"] - t["Sunrise"]) / 2
    assert minutes_between(t["Dhuhr"], middle) < 2


def test_hanafi_asr_is_later_than_shafii():
    day = date(2025, 1, 15)
    s = Prayer.calculate_prayer_times(CAIRO[0], CAIRO[1], day, CAIRO[2], "shafii")
    h = Prayer.calculate_prayer_times(CAIRO[0], CAIRO[1], day, CAIRO[2], "hanafi")
    assert h["Asr"] > s["Asr"]
    assert 30 < minutes_between(h["Asr"], s["Asr"]) < 90
    assert s["Fajr"] == h["Fajr"]                                  # only Asr differs


def test_cairo_january_regression():
    t = Prayer.calculate_prayer_times(CAIRO[0], CAIRO[1], date(2025, 1, 15), CAIRO[2])
    expected = {"Fajr": "05:21", "Sunrise": "06:52", "Dhuhr": "12:05",
                "Asr": "14:58", "Maghrib": "17:18", "Isha": "18:39"}
    for name, hhmm in expected.items():
        assert t[name].strftime("%H:%M") == hhmm, name


def test_last_third_is_two_thirds_of_the_way_through_the_night():
    day = date(2025, 1, 15)
    t = Prayer.calculate_prayer_times(CAIRO[0], CAIRO[1], day, CAIRO[2])
    next_fajr = Prayer.calculate_prayer_times(CAIRO[0], CAIRO[1], day + timedelta(days=1), CAIRO[2])["Fajr"]
    night = (next_fajr + timedelta(days=1)) - t["Maghrib"] if next_fajr < t["Maghrib"] else next_fajr - t["Maghrib"]
    expected = t["Maghrib"] + night * 2 / 3
    assert minutes_between(t["Last third"], expected) < 1.5


def test_places_that_crashed_the_old_script_now_work():
    # hour of the UT result went past 24 for far-west longitudes
    for lat, lon, tz in [(-17.55, -149.57, "Pacific/Tahiti"), (-14.28, -170.7, "Pacific/Pago_Pago")]:
        t = Prayer.calculate_prayer_times(lat, lon, date(2025, 1, 15), ZoneInfo(tz))
        assert all(t[n] is not None for n in Prayer.PRAYER_ORDER)
        assert t["Fajr"] < t["Sunrise"] < t["Dhuhr"] < t["Asr"] < t["Maghrib"] < t["Isha"]


def test_far_east_and_the_date_line():
    t = Prayer.calculate_prayer_times(-36.85, 179.9, date(2025, 1, 15), ZoneInfo("Pacific/Auckland"))
    assert t["Dhuhr"].date() == date(2025, 1, 15)


def test_high_latitude_summer_has_no_fajr_or_isha():
    oslo = Prayer.calculate_prayer_times(59.91, 10.75, date(2025, 6, 21), ZoneInfo("Europe/Oslo"))
    assert oslo["Fajr"] is None and oslo["Isha"] is None and oslo["Last third"] is None
    assert oslo["Sunrise"] is not None and oslo["Maghrib"] is not None
    tromso = Prayer.calculate_prayer_times(69.65, 18.96, date(2025, 6, 21), ZoneInfo("Europe/Oslo"))
    assert tromso["Sunrise"] is None and tromso["Maghrib"] is None      # midnight sun


def test_poles_do_not_crash():
    Prayer.calculate_prayer_times(90, 0, date(2025, 6, 21), ZoneInfo("UTC"))
    Prayer.calculate_prayer_times(-90, 0, date(2025, 12, 21), ZoneInfo("UTC"))


def test_bad_input_is_rejected():
    for args in [(91, 0), (-91, 0), (0, 181), (0, -181)]:
        try:
            Prayer.calculate_prayer_times(*args, date(2025, 1, 1), ZoneInfo("UTC"))
        except ValueError:
            continue
        raise AssertionError(f"{args} should have been rejected")
    try:
        Prayer.calculate_prayer_times(0, 0, date(2025, 1, 1), ZoneInfo("UTC"), "nonsense")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown madhhab should be rejected")


# --- command line ------------------------------------------------------------

def run(argv, typed=()):
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()), mock.patch("builtins.input", side_effect=list(typed)):
        try:
            code = Prayer.main(argv)
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue()


def test_cli_with_arguments():
    code, out = run(["--lat", "30.0444", "--lon", "31.2357", "--tz", "Africa/Cairo", "--date", "2025-01-15"])
    assert code == 0
    for name in Prayer.PRAYER_ORDER:
        assert name in out
    assert "05:21" in out and "(after midnight)" in out


def test_cli_interactive_recovers_from_typos():
    # not a number, out of range, good latitude, out-of-range longitude, good longitude, bad menu choice, Hanafi
    typed = ["abc", "95", "30.0444", "999", "31.2357", "7", "2"]
    code, out = run(["--tz", "Africa/Cairo", "--date", "2025-01-15"], typed)
    assert code == 0
    assert "Please type a number" in out and "needs to be between" in out and "Please type 1 or 2" in out
    assert "Hanafi" in out


def test_cli_default_school_on_enter():
    code, out = run(["--tz", "Africa/Cairo", "--date", "2025-01-15"], ["30.0444", "31.2357", ""])
    assert code == 0 and "Shafi'i" in out


def test_cli_rejects_bad_arguments():
    assert run(["--lat", "95", "--lon", "0"])[0] == 2
    assert run(["--lat", "1", "--lon", "1", "--date", "tomorrow"])[0] == 2
    code, _ = run(["--lat", "1", "--lon", "1", "--tz", "Mars/Olympus"])
    assert isinstance(code, str) and "Unknown timezone" in code


def test_cli_ctrl_c_exits_politely():
    out = io.StringIO()
    with redirect_stdout(out), mock.patch("builtins.input", side_effect=KeyboardInterrupt):
        assert Prayer.main([]) == 1
    assert "Cancelled" in out.getvalue()


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, func in tests:
        try:
            func()
        except Exception as error:                                  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {type(error).__name__}: {error}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
