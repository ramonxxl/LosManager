"""
Tamanho do pastel (Grande / Mini): a conta do preço do mini
(utils/tamanho.py) e a escolha na tela de Pedidos de verdade.

Rodar com:
    python -m testes
"""

import sys
import unittest

from database import conexao
from testes.gui_ambiente import ambiente_grafico, fechar_janela
from utils import tamanho


class TestePrecoMini(unittest.TestCase):
    """Preço do mini igual ao do cardápio online"""

    def test_mini_por_linha(self):
        """Mini = Grande menos a diferença da linha (mesmos valores do cardápio online)"""
        casos = [
            ("Tradicionais", 15.9, 7.9), ("Clássicos da Casa", 18.9, 10.9),
            ("Especiais – Linha Carne", 16.9, 7.9), ("Especiais - Linha Frango", 18.9, 9.9),
            ("Especiais - Linha Costela", 20.9, 10.9), ("Linha Fit", 16.9, 7.9),
            ("Premium", 20.9, 9.9), ("Premium", 25.9, 14.9), ("Pastéis Doces", 18.9, 9.9),
        ]
        for categoria, grande, mini in casos:
            self.assertEqual(tamanho.preco_mini(categoria, grande), mini, categoria)

    def test_premium_barato_segue_os_de_mesmo_preco(self):
        """Premium de R$ 16,90 (Explosão de Queijo) fica com mini R$ 7,90, não R$ 5,90"""
        self.assertEqual(tamanho.preco_mini("Premium", 16.9), 7.9)

    def test_sem_mini(self):
        """Bebidas, adicionais e produto sem preço não têm mini"""
        self.assertIsNone(tamanho.preco_mini("Bebidas", 6.0))
        self.assertIsNone(tamanho.preco_mini("Adicionais", 4.0))
        self.assertIsNone(tamanho.preco_mini("Tradicionais", 0))


class TesteTamanhoNaTelaDePedidos(unittest.TestCase):
    """Escolha Grande/Mini ao lançar pastel no balcão"""

    @classmethod
    def setUpClass(cls):
        cls._ambiente = ambiente_grafico()
        cls._ambiente.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ambiente.__exit__(None, None, None)

    def setUp(self):
        self._banco_producao = conexao.banco
        self.banco_teste = conexao.Banco(":memory:")
        conexao.banco = self.banco_teste

    def tearDown(self):
        conexao.banco = self._banco_producao

    def test_mini_entra_com_preco_e_aviso_e_bebida_nao_mostra_tamanho(self):
        """Pastel mostra Grande/Mini; Mini entra a R$ 7,90 com 'MINI (11 CM)'; Grande e bebida não mudam"""

        import customtkinter as ctk
        from screens import pedidos as tela_pedidos

        for nome, categoria, preco in [("Carne", "Tradicionais", 15.9), ("Coca Cola Lata", "Bebidas", 6.0)]:
            self.banco_teste.executar(
                "INSERT INTO produtos (nome, categoria, preco, estoque, ativo) VALUES (?, ?, ?, 100, 1)", (nome, categoria, preco))
        ids = {nome: pid for pid, nome in self.banco_teste.buscar("SELECT id, nome FROM produtos")}

        banco_da_tela = tela_pedidos.banco
        tela_pedidos.banco = self.banco_teste
        root = ctk.CTk()
        root.geometry("1366x768")

        def selecionar(nome):
            tela.carregar_produtos()
            tela.busca_produto.delete(0, "end")
            tela.busca_produto.insert(0, nome)
            tela.filtrar_produtos()
            tela.lista_resultados.selection_set(str(ids[nome]))
            tela.selecionar_produto_da_lista()
            root.update()

        try:
            tela = tela_pedidos.Pedidos(root)
            root.update()

            selecionar("Carne")
            self.assertTrue(tela.seletor_tamanho.winfo_ismapped())
            self.assertIn("Mini R$ 7.90", tela.lbl_produto_selecionado.cget("text"))
            tela.seletor_tamanho.set("Mini")
            tela.observacao_item.insert(0, "sem cebola")
            tela.adicionar_item()

            selecionar("Carne")
            self.assertEqual(tela.seletor_tamanho.get(), "Grande")   # volta para Grande a cada produto
            tela.adicionar_item()

            selecionar("Coca Cola Lata")
            self.assertFalse(tela.seletor_tamanho.winfo_ismapped())
            tela.adicionar_item()

            self.assertEqual(
                [(i["nome"], i["valor_unitario"], i["observacao"]) for i in tela.itens],
                [("Carne", 7.9, "MINI (11 CM) | sem cebola"), ("Carne", 15.9, ""), ("Coca Cola Lata", 6.0, "")])
            self.assertAlmostEqual(tela.total, 7.9 + 15.9 + 6.0)
        finally:
            tela_pedidos.banco = banco_da_tela
            fechar_janela(root)
            # screens.pedidos guarda o `banco` do momento do 1º import: tira o módulo
            # do cache para o próximo teste importar de novo com o banco dele
            sys.modules.pop("screens.pedidos", None)


if __name__ == "__main__":
    unittest.main()
