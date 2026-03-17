SOURCES = [
    {
        "id": "europa-innovazione",
        "name": "Europa Innovazione",
        "url": "https://www.europainnovazione.com/bandi-europei/",
        "enabled": True,
        "mode": "playwright",

        # 🔥 FILTRO FORMAZIONE (ADERENTE AL PDF)
        "required_keyword_groups": [
            # gruppo 1 → contesto finanziamento
            ["bando", "finanziamento", "call", "grant"],

            # gruppo 2 → formazione vera
            [
                "formazione",
                "training",
                "reskilling",
                "upskilling",
                "capacity building",
                "educazione",
                "competenze"
            ],
        ]
    },

    {
        "id": "eu-funding",
        "name": "EU Funding Portal",
        "url": "https://ec.europa.eu/info/funding-tenders/opportunities/rss_en.xml",
        "enabled": True,
        "mode": "rss",

        # 🔥 FILTRO DIGITALE
        "required_keyword_groups": [
            ["call", "proposal", "funding"],

            [
                "digital",
                "ict",
                "ai",
                "cyber",
                "data",
                "cloud",
                "innovation"
            ]
        ]
    }
]