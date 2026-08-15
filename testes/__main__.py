"""
Permite rodar a suíte com

    python -m testes

em vez de decorar o comando completo do unittest — funciona igual
em qualquer sistema operacional (não precisa de testar.sh/testar.bat).
Usa `testes/relatorio.py` pra uma saída legível (agrupada por classe,
com a descrição do teste em vez do nome técnico) em vez do
TextTestRunner padrão do unittest. Ver CLAUDE.md, seção "Testable
cadastros".
"""

import os
import sys
import unittest

from testes.relatorio import rodar


def principal():

    pasta_testes = os.path.dirname(os.path.abspath(__file__))
    raiz_projeto = os.path.dirname(pasta_testes)

    suite = unittest.TestLoader().discover(
        start_dir=pasta_testes,
        top_level_dir=raiz_projeto
    )

    resultado = rodar(suite)

    sys.exit(0 if resultado.wasSuccessful() else 1)


if __name__ == "__main__":
    principal()
