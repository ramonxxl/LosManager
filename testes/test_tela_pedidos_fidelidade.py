"""
Teste de ponta a ponta do banner de recompensa disponível na tela de
Pedidos (regra 14 do Programa de Fidelidade): seleciona, pela busca de
cliente de verdade, um cliente que já tem recompensa disponível (via
repositorios/fidelidade.py) e confere que o banner + botão "Usar
Recompensa" aparecem — e que um cliente sem recompensa (ou Cliente
Balcão) não mostra nada.

Não chama `finalizar()` de propósito: ele abre `messagebox` (erro de
impressora sem impressora configurada, aviso de sucesso, etc.), que
bloqueia esperando clique — mesmo motivo de
`test_tela_produtos_criacao.py` só chamar `salvar()`.
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


class TesteBannerFidelidadeEmPedidos(unittest.TestCase):
    """Banner de recompensa disponível na tela de Pedidos"""

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

    def test_banner_aparece_para_cliente_com_recompensa_e_some_no_balcao(self):
        """Selecionar um cliente com recompensa mostra o banner; Cliente Balcão não mostra"""

        import customtkinter as ctk
        from screens.pedidos import Pedidos
        from repositorios import fidelidade as repositorio_fidelidade

        self.banco_teste.executar(
            "INSERT INTO clientes(nome, telefone) VALUES('Maria', '98888-8888')"
        )
        maria_id = self.banco_teste.ultimo_id()

        for indice, numero in enumerate(range(1, 11)):
            self.banco_teste.executar(
                "INSERT INTO pedidos(numero, status, data) VALUES(?, 'Finalizado', ?)",
                (numero, _data_do_dia(indice))
            )
            repositorio_fidelidade.registrar_pedido_concluido(maria_id, self.banco_teste.ultimo_id())

        root = ctk.CTk()
        root.geometry("1366x768")

        try:
            tela = Pedidos(root)
            root.update()

            # Começa em Cliente Balcão — sem banner.
            self.assertFalse(tela.frame_fidelidade.winfo_ismapped())

            tela.busca_cliente.insert(0, "Maria")
            tela.filtrar_clientes()
            root.update()

            itens = tela.lista_resultados_cliente.get_children()
            self.assertEqual(len(itens), 1)

            tela.lista_resultados_cliente.selection_set(itens[0])
            tela.selecionar_cliente_da_lista()
            root.update()

            self.assertTrue(tela.frame_fidelidade.winfo_ismapped())
            self.assertIn("RECOMPENSA DISPONÍVEL", tela.lbl_fidelidade.cget("text"))
            self.assertEqual(str(tela.botao_usar_recompensa.cget("state")), "normal")

            # Volta pro Balcão — o banner deve sumir de novo.
            tela.selecionar_cliente_balcao()
            root.update()

            self.assertFalse(tela.frame_fidelidade.winfo_ismapped())

        finally:
            fechar_janela(root)


if __name__ == "__main__":
    unittest.main()
