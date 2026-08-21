"""
Testes do módulo utils/pedido_rascunho.py, que guarda o pedido em
andamento em memória entre uma navegação de tela e outra. É Python
puro (sem customtkinter/tkinter) — não precisa de nenhuma janela.

Rodar com:
    python -m testes
"""

import unittest

from utils import pedido_rascunho


class TesteRascunho(unittest.TestCase):
    """Guardar, recuperar e limpar o rascunho do pedido em andamento"""

    def setUp(self):
        # Cada teste começa sem nenhum rascunho guardado por um teste
        # anterior.
        pedido_rascunho.limpar()

    def tearDown(self):
        pedido_rascunho.limpar()

    def test_comeca_sem_rascunho(self):
        """Sem nenhum pedido salvo antes, obter() devolve None"""
        self.assertIsNone(pedido_rascunho.obter())

    def test_salvar_e_recuperar(self):
        """Um estado salvo é devolvido igual pelo obter()"""
        estado = {"itens": [{"produto_id": 1, "qtd": 2}], "total": 20.0}

        pedido_rascunho.salvar(estado)

        self.assertEqual(pedido_rascunho.obter(), estado)

    def test_limpar_remove_o_rascunho(self):
        """Depois de limpar(), obter() volta a devolver None"""
        pedido_rascunho.salvar({"itens": [{"produto_id": 1, "qtd": 1}], "total": 10.0})

        pedido_rascunho.limpar()

        self.assertIsNone(pedido_rascunho.obter())
