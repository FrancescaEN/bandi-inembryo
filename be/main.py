from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import pandas as pd
import json

from database import SessionLocal, engine, Base
import crud
import schemas
from scraper import run_pipeline

# crea tabelle DB
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Bandi InEmbryo API 🚀")


# =========================
# DB DEPENDENCY
# =========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================
# SCRAPE + SALVA + PULISCI
# =========================
@app.post("/scrape")
async def scrape_and_save(db: Session = Depends(get_db)):

    results = await run_pipeline()

    if not results:
        return {"message": "Nessun bando trovato"}

    saved = []

    for item in results:
        bando = crud.create_bando(db, item)
        saved.append(bando)

    # 🔥 elimina bandi scaduti dal DB
    crud.delete_expired_bandi(db)

    return {
        "total": len(saved),
        "message": "Scraping completato, DB aggiornato (solo bandi attivi)"
    }


# =========================
# GET BANDI ATTIVI
# =========================
@app.get("/bandi", response_model=list[schemas.BandoOut])
def get_bandi(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return crud.get_bandi(db, skip, limit)


# =========================
# EXPORT EXCEL (DA DB)
# =========================
@app.get("/export/excel")
def export_excel(db: Session = Depends(get_db)):

    bandi = crud.get_bandi(db, skip=0, limit=1000)

    if not bandi:
        return {"message": "Nessun bando trovato"}

    df = pd.DataFrame([{
        "title": b.title,
        "url": b.url,
        "summary": b.summary,
        "ente": b.ente,
        "published_at": b.published_at,
        "deadline": b.deadline,
        "source": b.source
    } for b in bandi])

    df = df.sort_values("deadline", ascending=True)

    file_path = "bandi.xlsx"
    df.to_excel(file_path, index=False)

    return FileResponse(
        path=file_path,
        filename="bandi.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# =========================
# EXPORT JSON (DA DB)
# =========================
@app.get("/export/json")
def export_json(db: Session = Depends(get_db)):

    bandi = crud.get_bandi(db, skip=0, limit=1000)

    if not bandi:
        return {"message": "Nessun bando trovato"}

    data = [{
        "title": b.title,
        "url": b.url,
        "summary": b.summary,
        "ente": b.ente,
        "published_at": b.published_at,
        "deadline": b.deadline,
        "source": b.source
    } for b in bandi]

    file_path = "bandi.json"

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return FileResponse(
        path=file_path,
        filename="bandi.json",
        media_type="application/json"
    )


# =========================
# HEALTH CHECK
# =========================
@app.get("/")
def root():
    return {"status": "API attiva 🚀"}