# Prayer Time Calculator

A small Python script that works out the five daily Islamic prayer times, plus sunrise and the last third of the night, for any place on Earth and any date. It does the maths itself from the position of the sun, so it works offline and doesn't depend on any website or API.

```
$ python Prayer.py --lat 30.0444 --lon 31.2357 --date 2025-01-15

Prayer times for 2025-01-15
Location : 30.0444, 31.2357   Timezone: Africa/Cairo
Method   : Egyptian General Authority of Survey (Fajr 19.5°, Isha 17.5°), Asr: Shafi'i / Hanbali / Maliki

  Fajr        05:21
  Sunrise     06:52
  Dhuhr       12:05
  Asr         14:58
  Maghrib     17:18
  Isha        18:39
  Last third  01:20  (after midnight)
```

## Why prayer times are a question for astronomers

Prayer in Islam is tied to the sky. The Qur'an describes prayer as something "decreed upon the believers at specified times" (4:103) and points to the markers of the day: the two ends of the day and the approach of night (11:114), and from the decline of the sun to the darkness of the night (17:78). The Prophet Muhammad ﷺ was taught the five times by Jibril (Gabriel), who led him in prayer at the beginning and end of each time-window over two days, as recorded in the collections of Abu Dawud and al-Tirmidhi. Each window is defined by something anyone can see:

- **Fajr** starts at true dawn, when light first spreads across the horizon.
- **Dhuhr** starts just after the sun passes its highest point.
- **Asr** starts when an object's shadow reaches a set length.
- **Maghrib** starts at sunset.
- **Isha** starts when the evening twilight has faded.

For the first Muslim communities, looking up was enough. As the community spread from Arabia across three continents, that stopped being practical. The length of the day changes with the seasons, and it changes more the further you are from the equator. Dawn and dusk come at different times in Cairo, Cordoba and Samarkand. A rule like "pray when the shadow is this long" needed a calendar, a latitude and some geometry to turn into a timetable. That need is a big part of why astronomy flourished in the Islamic world.

**A short history**

- **Baghdad, 9th century.** Scholars working in and around the House of Wisdom, such as al-Khwarizmi and Habash al-Hasib, produced *zijes* (astronomical tables) and developed the trigonometry needed to convert the sun's position into clock times. Al-Battani (c. 858-929) refined the measurements of the sun's motion and made trigonometry easier to use for exactly this kind of problem.
- **Cairo, around 1000.** Ibn Yunus observed from the Fatimid observatory on the Muqattam hills and compiled the *Hakimi Zij*, which included tables for timekeeping. Cairo remained a centre for this kind of work for centuries, and this project's default method is the Egyptian one.
- **The *muwaqqit*.** Larger mosques employed a *muwaqqit*, a timekeeper responsible for the correct times of prayer. They worked with sundials, astrolabes and tables of prayer times, and some compiled tables of their own. In 14th-century Damascus, Ibn al-Shatir held the post at the Umayyad Mosque and built a sundial for it. Another Damascus timekeeper, al-Khalili, compiled prayer-time tables for the city's latitude that were used for a long time afterwards.
- **Today.** The geometry is the same as it was then. What's changed is that a laptop can solve it in microseconds. This script uses the same idea the muwaqqits did: the sun's position, your latitude, and the date.

Accuracy matters beyond the daily prayers. In Ramadan the fast starts at Fajr and ends at Maghrib, so a few minutes' error in the timetable is a few minutes' error in someone's fast.

## How each time is defined

| Time | Defined as |
|---|---|
| Fajr | Sun 19.5° below the horizon, before sunrise |
| Sunrise | Top edge of the sun at the horizon (about 0.83° below the geometric horizon, allowing for refraction) |
| Dhuhr | Solar noon, when the sun crosses the meridian |
| Asr | Shadow length equals the object's height plus its noon shadow (Shafi'i, Maliki, Hanbali), or twice the height plus its noon shadow (Hanafi) |
| Maghrib | Sunset, with the same horizon definition as sunrise |
| Isha | Sun 17.5° below the horizon, after sunset |
| Last third | The night runs from Maghrib to the next Fajr; the last third begins two thirds of the way through it. Many Muslims use this time for voluntary night prayer and supplication |

The Fajr and Isha angles are the ones used by the Egyptian General Authority of Survey. Communities don't all agree on these angles. The Muslim World League uses 18° and 17°, ISNA uses 15° for both, and Umm al-Qura uses 18.5° with Isha fixed at 90 minutes after Maghrib. If your local authority uses a different convention, change `FAJR_ANGLE` and `ISHA_ANGLE` at the top of `Prayer.py`.

## Install

You need Python 3.9 or newer.

Download this repository (green **Code** button, then **Download ZIP**, or use `git clone`), open a terminal in the folder, and run:

```bash
pip install -r requirements.txt
```

The only dependency is [`timezonefinder`](https://pypi.org/project/timezonefinder/), which turns coordinates into a timezone so the times come out in local time. (Windows also installs `tzdata`, which Python needs there for timezone names.) If you'd rather not install anything, the script still runs. It will show times in UTC, or in any timezone you name with `--tz`.

## Use

**Just run it** and answer the questions:

```bash
python Prayer.py
```

It asks for your latitude, longitude and school for Asr, then prints today's times. Typos are fine; it asks again. North and east are positive, so Cairo is `30.0444, 31.2357` and Los Angeles is `34.05, -118.24`.

**Or pass everything as options:**

```bash
python Prayer.py --lat 21.4225 --lon 39.8262                      # Mecca, today
python Prayer.py --lat 30.0444 --lon 31.2357 --madhhab hanafi     # Hanafi Asr
python Prayer.py --lat 51.5072 --lon -0.1276 --date 2025-03-01    # a specific day
python Prayer.py --lat 40.7128 --lon -74.0060 --tz America/New_York
```

| Option | Meaning |
|---|---|
| `--lat`, `--lon` | Location in decimal degrees (north and east are positive) |
| `--madhhab` | `shafii` (default, also covers Hanbali and Maliki) or `hanafi` |
| `--date` | Day to calculate, as `YYYY-MM-DD` (default: today at that location) |
| `--tz` | Timezone name such as `Africa/Cairo` (default: detected from the coordinates) |

**Or use it from your own code:**

```python
from datetime import date
from zoneinfo import ZoneInfo
from Prayer import calculate_prayer_times

times = calculate_prayer_times(30.0444, 31.2357, date(2025, 1, 15), ZoneInfo("Africa/Cairo"))
print(times["Fajr"].strftime("%H:%M"))      # 05:21
```

The function returns a dictionary of timezone-aware datetimes, rounded to the nearest minute.

## Places where the sun doesn't follow the rules

Far from the equator in summer, the sky may never get dark enough for Fajr and Isha as defined above. In Oslo on the longest day of the year, for example, the sun never gets 17.5° below the horizon. In that situation the script says "does not occur on this date" instead of printing a number that looks right but isn't:

```
$ python Prayer.py --lat 59.91 --lon 10.75 --date 2025-06-21
  Fajr        does not occur on this date
  Sunrise     03:54
  Dhuhr       13:19
  Asr         18:01
  Maghrib     22:44
  Isha        does not occur on this date
```

Scholars have proposed several ways to handle this, such as taking the night as a fraction of its length or copying the times from a lower latitude. Those are a matter of religious judgement, not calculation, so this script leaves the decision with you and your local scholars.

## How accurate is it?

The sun's position comes from the standard low-precision formulas in the *Astronomical Almanac*, good to a few hundredths of a degree. In the tests, sunrise, sunset, Fajr, Isha and Asr agree with an independent, higher-precision implementation (NOAA's solar calculator formulas) to within a minute or two in places from Alaska to Sydney.

Even so, expect small differences from your mosque's timetable or your phone app:

- Different organisations use different Fajr and Isha angles.
- Many timetables add a minute or two of caution to Dhuhr, Maghrib or Fajr.
- Local altitude, weather and the real horizon all affect what you actually see.

Treat the output as a good calculation, not an observation. If you need certainty, follow your local mosque.

## Tests

```bash
python test_prayer.py          # no extra packages needed
# or, if you use pytest:
python -m pytest
```

The tests cover the sun's position, the Asr formula, every prayer time against the independent NOAA reference, far-east and far-west longitudes, the poles, high-latitude summers, and the command-line behaviour including bad input.

## Files

| File | What it is |
|---|---|
| `Prayer.py` | The calculator and command-line tool |
| `test_prayer.py` | Tests |
| `requirements.txt` | Dependencies |

## Further reading

- Qur'an 2:187, 4:103, 11:114 and 17:78 on the times of prayer and the signs of dawn and night
- David A. King, *In Synchrony with the Heavens*, a detailed study of Islamic astronomical timekeeping
- Jean Meeus, *Astronomical Algorithms*, for the formulas behind sun-position calculations
