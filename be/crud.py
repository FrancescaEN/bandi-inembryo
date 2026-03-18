from datetime import date
from sqlalchemy.orm import Session
from models import Bando


# =========================
# CREATE
# =========================
def create_bando(db: Session, data: dict):

    existing = db.query(Bando).filter(Bando.url == data["url"]).first()

    if existing:
        existing.title = data["title"]
        existing.summary = data["summary"]
        existing.ente = data["ente"]
        existing.published_at = data["published_at"]
        existing.deadline = data["deadline"]
        existing.source = data["source"]
        db.commit()
        db.refresh(existing)
        return existing

    bando = Bando(
        id=data["hash"],
        title=data["title"],
        url=data["url"],
        summary=data["summary"],
        ente=data["ente"],
        published_at=data["published_at"],
        deadline=data["deadline"],
        source=data["source"],
    )

    db.add(bando)
    db.commit()
    db.refresh(bando)

    return bando


# =========================
# GET SOLO BANDI ATTIVI
# =========================
def get_bandi(db: Session, skip=0, limit=50):

    today = date.today().isoformat()

    return db.query(Bando).filter(
        (Bando.deadline == None) | (Bando.deadline >= today)
    ).offset(skip).limit(limit).all()


# =========================
# DELETE BANDI SCADUTI
# =========================
def delete_expired_bandi(db: Session):

    today = date.today().isoformat()

    db.query(Bando).filter(
        Bando.deadline != None,
        Bando.deadline < today
    ).delete()

    db.commit()
