from scraper.parsers import assistance_ph

SOURCES = [
    {
        "name": "assistance.ph",
        "url": "https://assistance.ph",
        "parser": assistance_ph.parse,
    },
]
