"""Mock-Systemlandschaft: ERP, CRM und MES als drei Teil-Apps mit eigener OpenAPI-Doku.
Start: uvicorn systeme.main:app --port 8050
"""
from fastapi import FastAPI

from systeme import crm, erp, mes

app = FastAPI(title="Systemlandschaft (Mocks)")
app.mount("/erp", erp.app)
app.mount("/crm", crm.app)
app.mount("/mes", mes.app)


@app.get("/")
def start():
    return {"systeme": ["/erp/docs", "/crm/docs", "/mes/docs"]}
