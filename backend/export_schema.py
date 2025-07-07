# backend/export_schema.py

from backend.app import app
from backend.models import db
from sqlalchemy.schema import CreateTable

with app.app_context():
    with open("schema.sql", "w") as f:
        for table in db.metadata.sorted_tables:
            ddl = str(CreateTable(table).compile(db.engine)) + ";\n\n"
            f.write(ddl)
