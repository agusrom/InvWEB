"""Entrada conservada por compatibilidad; sólo verifica MySQL."""

import sys
from migrar_a_mysql import main


if __name__ == "__main__":
    sys.argv.append("--solo-verificar")
    main()
