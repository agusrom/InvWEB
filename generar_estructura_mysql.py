"""Imprime el DDL MySQL completo definido por los modelos del sistema."""

from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

from app import db


def main():
    dialecto = mysql.dialect()
    print("SET NAMES utf8mb4;")
    print("SET FOREIGN_KEY_CHECKS=0;")
    for tabla in db.metadata.sorted_tables:
        print(str(CreateTable(tabla).compile(dialect=dialecto)).strip() + ";")
        for indice in tabla.indexes:
            print(str(CreateIndex(indice).compile(dialect=dialecto)).strip() + ";")
    print("SET FOREIGN_KEY_CHECKS=1;")


if __name__ == "__main__":
    main()
