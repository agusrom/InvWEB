"""Exporta candidatos a catálogo de clientes sin cambiar inventarios ni plantillas."""
import argparse
import csv
from collections import Counter
from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def normalizar(valor):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", valor)
                            if not unicodedata.combining(c)).upper().split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    from sqlalchemy import select
    from app.database import SessionLocal
    from app.models import Inventario, Plantilla
    with SessionLocal() as db:
        plantillas = Counter(db.scalars(select(Plantilla.cliente)).all())
        inventarios = Counter(db.scalars(select(Inventario.cliente)).all())
    # No fusionar automáticamente: algunos valores actuales son códigos de pieza.
    with args.output.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["grupo_normalizado", "valor_actual", "plantillas", "inventarios", "cliente_canonico", "codigo_cliente", "decision"])
        for valor in sorted(set(plantillas) | set(inventarios), key=lambda value: (normalizar(value), value)):
            writer.writerow([normalizar(valor), valor, plantillas[valor], inventarios[valor], "", "", "REVISAR"])
    print(f"Revisión exportada: {args.output}. No se modificó la base.")


if __name__ == "__main__":
    main()
