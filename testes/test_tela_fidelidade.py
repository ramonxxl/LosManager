"""
Teste de ponta a ponta da tela de Fidelidade: popula participantes via
o repositório (repositorios/fidelidade.py, exatamente como
Pedidos.finalizar() faz) e confere que a Treeview real da tela mostra
as colunas certas — mesmo padrão de `test_tela_produtos_criacao.py`,
usando `ambiente_grafico()` pra garantir um display e trocando
`database.conexao.banco` por um `Banco(":memory:")` isolado antes de
montar a tela (senão a tela gravaria/leria do losmanager.db real).
"""

import unittest
from datetime import date, timedelta

from database import conexao
from testes.gui_ambiente import ambiente_grafico, fechar_janela


def _data_do_dia(indice):
    """Uma data (dd/mm/aaaa) diferente por índice — a regra de 1 ponto
    por dia (repositorios/fidelidade.py) agrupa pela coluna `data` do
    pedido, então cada pedido de teste precisa de um dia distinto pra
    contar como pedidos separados."""

    return (date(2026, 1, 1) + timedelta(days=indice)).strftime("%d/%m/%Y")


class TesteTelaFidelidade(unittest.TestCase):
    """Tela de Fidelidade mostrando clientes participantes de verdade"""

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

    def test_tabela_mostra_clientes_em_andamento_e_com_recompensa(self):
        """A tabela mostra pedidos/faltam/recompensas/status corretos por cliente"""

        import customtkinter as ctk
        from screens.fidelidade import Fidelidade
        from repositorios import fidelidade as repositorio_fidelidade

        self.banco_teste.executar("INSERT INTO clientes(nome, telefone) VALUES('João', '99999-9999')")
        joao_id = self.banco_teste.ultimo_id()

        self.banco_teste.executar("INSERT INTO clientes(nome, telefone) VALUES('Maria', '98888-8888')")
        maria_id = self.banco_teste.ultimo_id()

        for indice, numero in enumerate(range(1, 8)):
            self.banco_teste.executar(
                "INSERT INTO pedidos(numero, status, data) VALUES(?, 'Finalizado', ?)",
                (numero, _data_do_dia(indice))
            )
            repositorio_fidelidade.registrar_pedido_concluido(joao_id, self.banco_teste.ultimo_id())

        for indice, numero in enumerate(range(100, 110)):
            self.banco_teste.executar(
                "INSERT INTO pedidos(numero, status, data) VALUES(?, 'Finalizado', ?)",
                (numero, _data_do_dia(indice))
            )
            repositorio_fidelidade.registrar_pedido_concluido(maria_id, self.banco_teste.ultimo_id())

        root = ctk.CTk()
        root.geometry("1366x768")

        try:
            tela = Fidelidade(root)
            root.update()

            linhas = tela.tabela.get_children()
            self.assertEqual(len(linhas), 2)

            por_nome = {
                tela.tabela.item(linha, "values")[1]: tela.tabela.item(linha, "values")
                for linha in linhas
            }

            _id, _nome, _telefone, pedidos, faltam, recompensas, status = por_nome["João"]
            self.assertEqual((pedidos, faltam, recompensas, status), ("7", "3", "0", "Em andamento"))

            _id, _nome, _telefone, pedidos, faltam, recompensas, status = por_nome["Maria"]
            self.assertEqual((pedidos, faltam, recompensas, status), ("10", "0", "1", "🎁 Prêmio disponível"))

        finally:
            fechar_janela(root)

    def test_busca_filtra_a_tabela(self):
        """O campo de busca da tela filtra os clientes mostrados"""

        import customtkinter as ctk
        from screens.fidelidade import Fidelidade
        from repositorios import fidelidade as repositorio_fidelidade

        self.banco_teste.executar("INSERT INTO clientes(nome, telefone) VALUES('José', '91111-1111')")
        jose_id = self.banco_teste.ultimo_id()
        self.banco_teste.executar("INSERT INTO clientes(nome, telefone) VALUES('Ana', '92222-2222')")
        ana_id = self.banco_teste.ultimo_id()

        self.banco_teste.executar("INSERT INTO pedidos(numero, status) VALUES(1, 'Finalizado')")
        repositorio_fidelidade.registrar_pedido_concluido(jose_id, self.banco_teste.ultimo_id())

        self.banco_teste.executar("INSERT INTO pedidos(numero, status) VALUES(2, 'Finalizado')")
        repositorio_fidelidade.registrar_pedido_concluido(ana_id, self.banco_teste.ultimo_id())

        root = ctk.CTk()
        root.geometry("1366x768")

        try:
            tela = Fidelidade(root)
            root.update()

            tela.busca.insert(0, "jose")
            tela.carregar()
            root.update()

            linhas = tela.tabela.get_children()
            self.assertEqual(len(linhas), 1)
            self.assertEqual(tela.tabela.item(linhas[0], "values")[1], "José")

        finally:
            fechar_janela(root)


if __name__ == "__main__":
    unittest.main()
