MARKET_RELATIONSHIPS = [

    # -------------------------
    # COMMODITY → SECTOR
    # -------------------------

    {
        "source": "SUGAR",
        "target": "SUGAR_PRODUCER",
        "relationship": "commodity_exposure",
        "impact": "POSITIVE",
        "sensitivity": 0.9,
        "description": "Higher sugar prices can improve realization for sugar producers.",
    },

    {
        "source": "SUGAR",
        "target": "BEVERAGES",
        "relationship": "input_cost",
        "impact": "NEGATIVE",
        "sensitivity": 0.6,
        "description": "Higher sugar prices increase input costs for beverage companies.",
    },

    {
        "source": "CRUDE_OIL",
        "target": "AIRLINES",
        "relationship": "input_cost",
        "impact": "NEGATIVE",
        "sensitivity": 0.9,
        "description": "Jet fuel costs are strongly influenced by crude oil prices.",
    },

    {
        "source": "CRUDE_OIL",
        "target": "PAINTS",
        "relationship": "input_cost",
        "impact": "NEGATIVE",
        "sensitivity": 0.7,
        "description": "Crude derivatives are important paint inputs.",
    },

    {
        "source": "CRUDE_OIL",
        "target": "OIL_PRODUCERS",
        "relationship": "revenue_exposure",
        "impact": "POSITIVE",
        "sensitivity": 0.8,
        "description": "Higher crude prices can improve upstream realization.",
    },

    {
        "source": "STEEL",
        "target": "AUTO",
        "relationship": "input_cost",
        "impact": "NEGATIVE",
        "sensitivity": 0.6,
        "description": "Steel is an important automotive input.",
    },

    {
        "source": "STEEL",
        "target": "CAPITAL_GOODS",
        "relationship": "input_cost",
        "impact": "NEGATIVE",
        "sensitivity": 0.5,
        "description": "Steel affects manufacturing and infrastructure input costs.",
    },

    {
        "source": "COPPER",
        "target": "CABLES",
        "relationship": "input_cost",
        "impact": "NEGATIVE",
        "sensitivity": 0.8,
        "description": "Copper is a major raw material for cables.",
    },

    {
        "source": "COAL",
        "target": "POWER",
        "relationship": "input_cost",
        "impact": "NEGATIVE",
        "sensitivity": 0.7,
        "description": "Coal prices influence thermal power generation costs.",
    },

    # -------------------------
    # MACRO → SECTORS
    # -------------------------

    {
        "source": "INTEREST_RATES",
        "target": "BANKS",
        "relationship": "financial_condition",
        "impact": "MIXED",
        "sensitivity": 0.7,
        "description": "Interest-rate changes affect lending, deposits and margins.",
    },

    {
        "source": "INTEREST_RATES",
        "target": "REAL_ESTATE",
        "relationship": "financing_cost",
        "impact": "NEGATIVE",
        "sensitivity": 0.8,
        "description": "Higher rates increase borrowing costs and can reduce demand.",
    },

    {
        "source": "INFLATION",
        "target": "CONSUMER",
        "relationship": "purchasing_power",
        "impact": "NEGATIVE",
        "sensitivity": 0.6,
        "description": "Persistent inflation can reduce consumer purchasing power.",
    },

    {
        "source": "GDP_GROWTH",
        "target": "CAPITAL_GOODS",
        "relationship": "economic_growth",
        "impact": "POSITIVE",
        "sensitivity": 0.8,
        "description": "Economic expansion can increase capital expenditure.",
    },

    {
        "source": "GDP_GROWTH",
        "target": "BANKS",
        "relationship": "credit_growth",
        "impact": "POSITIVE",
        "sensitivity": 0.7,
        "description": "Economic growth can support credit demand and asset quality.",
    },
]