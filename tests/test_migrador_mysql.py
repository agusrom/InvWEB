from migrar_a_mysql import clave_mysql, deduplicar_filas


def test_clave_mysql_equivale_mayusculas_acentos_y_espacios():
    assert clave_mysql("  Recepción ") == clave_mysql("RECEPCION")


def test_catalogos_duplicados_conservan_el_activo_y_remapean_ids():
    filas = [
        {
            "id": 4,
            "tipo": "CELULA",
            "codigo": "RECEPCION",
            "nombre": "Recepción anterior",
            "activo": False,
        },
        {
            "id": 20,
            "tipo": "celula",
            "codigo": "Recepcion ",
            "nombre": "Recepción",
            "activo": True,
        },
    ]

    resultado, mapa, conflictos = deduplicar_filas("catalogos", filas)

    assert [fila["id"] for fila in resultado] == [20]
    assert mapa == {4: 20, 20: 20}
    assert conflictos == [
        {"tabla": "catalogos", "conservado": 20, "combinados": [4]}
    ]
