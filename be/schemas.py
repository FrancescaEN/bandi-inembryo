from pydantic import BaseModel

class BandoBase(BaseModel):
    title: str
    url: str
    summary: str
    ente: str
    published_at: str | None
    deadline: str | None
    source: str

class BandoOut(BandoBase):
    id: str

    class Config:
        from_attributes = True