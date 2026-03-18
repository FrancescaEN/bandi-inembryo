SOURCES = [

    # =========================
    # EUROPA INNOVAZIONE
    # =========================
    {
        "id": "europa-innovazione",
        "name": "Europa Innovazione",
        "url": "https://www.europainnovazione.com/bandi-europei/",
        "enabled": True,
        "mode": "playwright",
        "required_keyword_groups": [
            ["bando", "call", "finanziamento"],
            ["formazione", "training", "competenze", "digital", "ict"]
        ]
    },

    # =========================
    # EU RSS
    # =========================
    {
        "id": "eu-funding",
        "name": "EU Funding Portal",
        "url": "https://ec.europa.eu/info/funding-tenders/opportunities/rss_en.xml",
        "enabled": True,
        "mode": "rss",
        "required_keyword_groups": [
            ["call", "proposal"],
            ["digital", "innovation", "training", "skills"]
        ]
    },

    # =========================
    # EUROINFO SICILIA
    # =========================
    {
        "id": "euroinfo-sicilia",
        "name": "EuroInfo Sicilia",
        "url": "https://www.euroinfosicilia.it/bandi-e-avvisi-aperti/?sezione=aperti",
        "enabled": True,
        "mode": "html",
        "required_keyword_groups": [
            ["bando", "avviso"],
            ["formazione", "digitale", "innovazione"]
        ]
    },

    # =========================
    # ITALIA DOMANI (PNRR)
    # =========================
    {
        "id": "italia-domani",
        "name": "Italia Domani",
        "url": "https://www.italiadomani.gov.it/it/opportunita/bandi-amministrazioni-titolari.html",
        "enabled": True,
        "mode": "playwright",
        "required_keyword_groups": [
            ["bando", "avviso"],
            ["digitale", "innovazione", "formazione", "competenze"]
        ]
    },

    # =========================
    # FORMEZ
    # =========================
    {
        "id": "formez",
        "name": "Formez",
        "url": "https://www.formez.it/progetti",
        "enabled": True,
        "mode": "html",
        "required_keyword_groups": [
            ["progetto", "programma"],
            ["formazione", "capacity building", "competenze"]
        ]
    }
]