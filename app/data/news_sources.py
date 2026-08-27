NEWS_SOURCES = [
    {
        "name": "Google News - India Business",
        "url": "https://news.google.com/rss/search?q=India+stock+market+business&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "MARKET",
        "is_international": False,
    },
    {
        "name": "Google News - Indian Economy",
        "url": "https://news.google.com/rss/search?q=India+economy+RBI+inflation+GDP&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "MACRO",
        "is_international": False,
    },
    {
        "name": "Google News - Indian Companies",
        "url": "https://news.google.com/rss/search?q=Indian+companies+earnings+stocks+results&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "COMPANY",
        "is_international": False,
    },
    {
        "name": "Google News - Commodities India",
        "url": "https://news.google.com/rss/search?q=India+commodity+prices+sugar+steel+crude+copper+coal&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "COMMODITY",
        "is_international": False,
    },
    {
        "name": "Google News - Agriculture & Crop Events",
        "url": "https://news.google.com/rss/search?q=India+crop+harvest+monsoon+agriculture+yield+damage&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "AGRICULTURE",
        "is_international": False,
    },
    {
        "name": "Google News - Weather & Disasters",
        "url": "https://news.google.com/rss/search?q=India+flood+drought+cyclone+rainfall+heatwave+weather&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "EXTERNAL_EVENT",
        "is_international": False,
    },
    {
        "name": "Google News - Government Policy & Schemes",
        "url": "https://news.google.com/rss/search?q=India+government+policy+scheme+subsidy+duty+tax+industry+business&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "POLICY",
        "is_international": False,
    },

    # --------------------------------------------------------------------
    # International sources.
    #
    # Everything above is India-filtered (gl=IN): a US Fed decision or a
    # China stimulus announcement only shows up if an Indian outlet chose to
    # cover it, which is secondhand and incomplete. These sources query
    # global-locale news directly (gl=US) for the exact five themes
    # global_intelligence.py's SIGNALS already know how to detect, plus one
    # direct international wire (not Google-mediated) for primary coverage.
    # --------------------------------------------------------------------
    {
        "name": "Google News - US Federal Reserve & Rates",
        "url": "https://news.google.com/rss/search?q=Federal+Reserve+interest+rate+decision+treasury+yields&hl=en-US&gl=US&ceid=US:en",
        "category": "GLOBAL_MACRO",
        "is_international": True,
    },
    {
        "name": "Google News - Global Crude Oil & OPEC",
        "url": "https://news.google.com/rss/search?q=crude+oil+price+OPEC+brent+wti&hl=en-US&gl=US&ceid=US:en",
        "category": "GLOBAL_COMMODITY",
        "is_international": True,
    },
    {
        "name": "Google News - China Economy & Policy",
        "url": "https://news.google.com/rss/search?q=China+economy+stimulus+demand+manufacturing&hl=en-US&gl=US&ceid=US:en",
        "category": "GLOBAL_MACRO",
        "is_international": True,
    },
    {
        "name": "Google News - Global Technology & AI Spending",
        "url": "https://news.google.com/rss/search?q=AI+spending+cloud+capex+technology+earnings+guidance&hl=en-US&gl=US&ceid=US:en",
        "category": "GLOBAL_TECH",
        "is_international": True,
    },
    {
        "name": "Google News - Geopolitical Risk",
        "url": "https://news.google.com/rss/search?q=geopolitical+conflict+sanctions+war+ceasefire&hl=en-US&gl=US&ceid=US:en",
        "category": "GLOBAL_GEOPOLITICAL",
        "is_international": True,
    },
    {
        "name": "Google News - Global Metals & Commodities",
        "url": "https://news.google.com/rss/search?q=copper+aluminium+steel+iron+ore+metal+prices&hl=en-US&gl=US&ceid=US:en",
        "category": "GLOBAL_METALS",
        "is_international": True,
    },
    {
        "name": "BBC Business",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "category": "GLOBAL_MARKET",
        "is_international": True,
    },
]

