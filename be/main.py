from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import pandas as pd
import json
import os

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
# ROUTE: SCRAPE + SALVA
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

    return {
        "total": len(saved),
        "message": "Scraping completato e salvato nel DB"
    }


# =========================
# ROUTE: GET BANDI
# =========================
@app.get("/bandi", response_model=list[schemas.BandoOut])
def get_bandi(db: Session = Depends(get_db)):
    return crud.get_bandi(db)


# =========================
# ROUTE: EXPORT EXCEL
# =========================
@app.get("/export/excel")
async def export_excel():

    results = await run_pipeline()

    if not results:
        return {"message": "Nessun bando trovato"}

    df = pd.DataFrame(results)

    # ordina per deadline
    if "deadline" in df.columns:
        df = df.sort_values("deadline", ascending=True)

    file_path = "bandi.xlsx"
    df.to_excel(file_path, index=False)

    return FileResponse(
        path=file_path,
        filename="bandi.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# =========================
# ROUTE: EXPORT JSON
# =========================
@app.get("/export/json")
async def export_json():

    results = await run_pipeline()

    if not results:
        return {"message": "Nessun bando trovato"}

    file_path = "bandi.json"

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return FileResponse(
        path=file_path,
        filename="bandi.json",
        media_type="application/json"
    )


# =========================
# ROUTE: HEALTH CHECK
# =========================
@app.get("/")
def root():
    return {"status": "API attiva 🚀"}