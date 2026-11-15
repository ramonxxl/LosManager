"""
Venda a funcionário a preço de custo: botão "Alterar valor (funcionário)"
da tela de Pedidos (screens/pedidos.py, alterar_valor_item). Pede a senha
de administrador e troca o valor unitário do item selecionado do carrinho.

Não chama `finalizar()` (abre messagebox que bloqueia) — as caixas de
diálogo são trocadas por falsas.

Rodar com:
    python -m testes
"""

import unittest
from unittest import mock

from database import conexao
from testes.gui_ambiente import ambiente_grafico, fechar_janela


class TesteAlterarValorFuncionario(unittest.TestCase):
    """Alterar o valor de um item do carrinho (venda a funcionário)"""

    @classmethod
    def setUpClass(cls):
        cls._ambiente = ambiente_grafico()
        cls._ambiente.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ambiente.__exit__(None, None, None)

    def setUp(self):
        from utils import pedido_rascunho
        self._banco_producao = conexao.banco
        self.banco_teste = conexao.Banco(":memory:")
        conexao.banco = self.banco_teste
        pedido_rascunho.limpar()   # a tela restaura o rascunho do teste anterior

    def tearDown(self):
        from utils import pedido_rascunho
        conexao.banco = self._banco_producao
        pedido_rascunho.limpar()

    def _tela_com_um_item(self, root):
        from screens.pedidos import Pedidos

        tela = Pedidos(root)
        root.update()

        tela.itens.append({"produto_id": 1, "nome": "Smoke Bacon", "qtd": 2, "valor_unitario": 29.90,
                           "subtotal": 59.80, "observacao": ""})
        tela.total += 59.80
        tela.tabela.insert("", "end", values=("Smoke Bacon", "", 2, "R$ 29.90", "R$ 59.80"))
        tela.tabela.selection_set(tela.tabela.get_children()[0])
        return tela

    def _digitando(self, *respostas):
        """CTkInputDialog falso: devolve as respostas na ordem (senha, valor)."""
        fila = list(respostas)

        class Falso:
            def __init__(self, *a, **k):
                pass

            def get_input(self):
                return fila.pop(0)

        return mock.patch("screens.pedidos.ctk.CTkInputDialog", Falso)

    def test_senha_certa_troca_valor_total_e_marca_observacao(self):
        """Com a senha certa o valor unitário muda, o subtotal e o total acompanham e o item fica marcado"""
        import customtkinter as ctk
        from screens import pedidos

        root = ctk.CTk()
        root.geometry("1366x768")
        try:
            tela = self._tela_com_um_item(root)
            with mock.patch.object(pedidos.config, "obter", return_value="1234"), self._digitando("1234", "14,50"):
                tela.alterar_valor_item()
            item = tela.itens[0]
            self.assertEqual(item["valor_unitario"], 14.5)
            self.assertEqual(item["subtotal"], 29.0)
            self.assertAlmostEqual(tela.total, 29.0)
            self.assertIn("(Preço funcionário)", item["observacao"])
            linha = tela.tabela.item(tela.tabela.get_children()[0])["values"]
            self.assertEqual(list(linha)[3:], ["R$ 14.50", "R$ 29.00"])
        finally:
            fechar_janela(root)

    def test_senha_errada_nao_muda_nada(self):
        """Com a senha errada o item continua com o valor original"""
        import customtkinter as ctk
        from screens import pedidos

        root = ctk.CTk()
        root.geometry("1366x768")
        try:
            tela = self._tela_com_um_item(root)
            with mock.patch.object(pedidos.config, "obter", return_value="1234"), \
                 mock.patch.object(pedidos.messagebox, "showerror") as erro, \
                 self._digitando("0000"):
                tela.alterar_valor_item()
            erro.assert_called_once()
            self.assertEqual(tela.itens[0]["valor_unitario"], 29.90)
            self.assertAlmostEqual(tela.total, 59.80)
        finally:
            fechar_janela(root)

    def test_valor_invalido_ou_negativo_e_recusado(self):
        """Texto que não é número e valor negativo não alteram o item"""
        import customtkinter as ctk
        from screens import pedidos

        root = ctk.CTk()
        root.geometry("1366x768")
        try:
            tela = self._tela_com_um_item(root)
            with mock.patch.object(pedidos.config, "obter", return_value="1234"), \
                 mock.patch.object(pedidos.messagebox, "showwarning") as aviso, \
                 self._digitando("1234", "abc"):
                tela.alterar_valor_item()
            with mock.patch.object(pedidos.config, "obter", return_value="1234"), \
                 mock.patch.object(pedidos.messagebox, "showwarning") as aviso2, \
                 self._digitando("1234", "-5"):
                tela.alterar_valor_item()
            aviso.assert_called_once()
            aviso2.assert_called_once()
            self.assertEqual(tela.itens[0]["valor_unitario"], 29.90)
        finally:
            fechar_janela(root)

    def test_sem_item_selecionado_avisa(self):
        """Sem selecionar um item do carrinho, só mostra o aviso"""
        import customtkinter as ctk
        from screens import pedidos

        root = ctk.CTk()
        root.geometry("1366x768")
        try:
            tela = self._tela_com_um_item(root)
            tela.tabela.selection_remove(tela.tabela.selection())
            with mock.patch.object(pedidos.messagebox, "showwarning") as aviso:
                tela.alterar_valor_item()
            aviso.assert_called_once()
            self.assertEqual(tela.itens[0]["valor_unitario"], 29.90)
        finally:
            fechar_janela(root)


if __name__ == "__main__":
    unittest.main()
