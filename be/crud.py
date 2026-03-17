from sqlalchemy.orm import Session
from models import Bando


def create_bando(db: Session, data: dict):

    existing = db.query(Bando).filter(Bando.url == data["url"]).first()

    if existing:
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


def get_bandi(db: Session, skip=0, limit=50):
    return db.query(Bando).offset(skip).limit(limit).all()