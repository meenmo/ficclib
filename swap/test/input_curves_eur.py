from datetime import date

CURVE_DATE = date(2025, 11, 10)

OIS_QUOTES = [
    {"rate": 1.93000, "tenor": "1W"},
    {"rate": 1.93075, "tenor": "2W"},
    {"rate": 1.93130, "tenor": "1M"},
    {"rate": 1.92980, "tenor": "2M"},
    {"rate": 1.92900, "tenor": "3M"},
    {"rate": 1.92710, "tenor": "4M"},
    {"rate": 1.92050, "tenor": "5M"},
    {"rate": 1.91450, "tenor": "6M"},
    {"rate": 1.91020, "tenor": "7M"},
    {"rate": 1.90370, "tenor": "8M"},
    {"rate": 1.89830, "tenor": "9M"},
    {"rate": 1.89230, "tenor": "10M"},
    {"rate": 1.88900, "tenor": "11M"},
    {"rate": 1.88700, "tenor": "1Y"},
    {"rate": 1.87800, "tenor": "15M"},
    {"rate": 1.88000, "tenor": "18M"},
    {"rate": 1.89000, "tenor": "21M"},
    {"rate": 1.90500, "tenor": "2Y"},
    {"rate": 1.97800, "tenor": "3Y"},
    {"rate": 2.06100, "tenor": "4Y"},
    {"rate": 2.14300, "tenor": "5Y"},
    {"rate": 2.21700, "tenor": "6Y"},
    {"rate": 2.28800, "tenor": "7Y"},
    {"rate": 2.35720, "tenor": "8Y"},
    {"rate": 2.42320, "tenor": "9Y"},
    {"rate": 2.48400, "tenor": "10Y"},
    {"rate": 2.54000, "tenor": "11Y"},
    {"rate": 2.59070, "tenor": "12Y"},
    {"rate": 2.71100, "tenor": "15Y"},
    {"rate": 2.80400, "tenor": "20Y"},
    {"rate": 2.82600, "tenor": "25Y"},
    {"rate": 2.82500, "tenor": "30Y"},
    {"rate": 2.82300, "tenor": "35Y"},
    {"rate": 2.81240, "tenor": "40Y"},

]

IBOR3M_QUOTES = [
    {"rate": 2.00500 , "tenor": "3M"},
    {"rate": 2.03080 , "tenor": "1Y"},
    {"rate": 2.05900 , "tenor": "2Y"},
    {"rate": 2.13500 , "tenor": "3Y"},
    {"rate": 2.21800 , "tenor": "4Y"},
    {"rate": 2.29700 , "tenor": "5Y"},
    {"rate": 2.36900 , "tenor": "6Y"},
    {"rate": 2.43900 , "tenor": "7Y"},
    {"rate": 2.50700 , "tenor": "8Y"},
    {"rate": 2.57100 , "tenor": "9Y"},
    {"rate": 2.63000 , "tenor": "10Y"},
    {"rate": 2.68700 , "tenor": "11Y"},
    {"rate": 2.73700 , "tenor": "12Y"},
    {"rate": 2.85700 , "tenor": "15Y"},
    {"rate": 2.94700 , "tenor": "20Y"},
    {"rate": 2.96435 , "tenor": "25Y"},
    {"rate": 2.96220 , "tenor": "30Y"},
    {"rate": 2.94000 , "tenor": "40Y"},
    {"rate": 2.89200 , "tenor": "50Y"},

]

IBOR6M_QUOTES = [
    {"rate": 2.00500, "tenor": "6M"},
    {"rate": 2.13200, "tenor": "1Y"},
    {"rate": 2.12000, "tenor": "18M"},
    {"rate": 2.15200, "tenor": "2Y"},
    {"rate": 2.22300, "tenor": "3Y"},
    {"rate": 2.30100, "tenor": "4Y"},
    {"rate": 2.38000, "tenor": "5Y"},
    {"rate": 2.44300, "tenor": "6Y"},
    {"rate": 2.50825, "tenor": "7Y"},
    {"rate": 2.57000, "tenor": "8Y"},
    {"rate": 2.62790, "tenor": "9Y"},
    {"rate": 2.68100, "tenor": "10Y"},
    {"rate": 2.73200, "tenor": "11Y"},
    {"rate": 2.77600, "tenor": "12Y"},
    {"rate": 2.88120, "tenor": "15Y"},
    {"rate": 2.95420, "tenor": "20Y"},
    {"rate": 2.96400, "tenor": "25Y"},
    {"rate": 2.95300, "tenor": "30Y"},
    {"rate": 2.92115, "tenor": "40Y"},

]

__all__ = [
    "CURVE_DATE",
    "OIS_QUOTES",
    "IBOR3M_QUOTES",
    "IBOR6M_QUOTES",
]

