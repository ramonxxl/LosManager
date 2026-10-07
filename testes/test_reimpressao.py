"""
Testes da reimpressão de cupom (Relatórios > "🖨 Reimprimir Cupom"):
os dados lidos do banco para a 2ª via, a tarja "2ª VIA" no cupom e a
largura da tela de Relatórios com o botão novo no PC da loja.
Banco isolado em memória — nunca toca o losmanager.db.

Rodar com:
    python -m testes
"""

import unittest

from database.conexao import Banco
from repositorios import reimpressao
from testes.gui_ambiente import ambiente_grafico, fechar_janela


def gravar_pedido_exemplo(banco, status="Finalizado"):
    banco.executar("INSERT INTO clientes (nome, telefone) VALUES ('Ana Souza', '12991112222')")
    cliente_id = banco.ultimo_id()
    banco.executar(
        "INSERT INTO enderecos_cliente (cliente_id, endereco, numero, bairro, cidade, principal) "
        "VALUES (?, 'Rua Emílio Winther', '45', 'Jardim das Nações', 'Taubaté', 1)",
        (cliente_id,)
    )
    banco.executar("INSERT INTO produtos (nome, categoria, preco, estoque, ativo) VALUES ('Pastel de Carne', 'Pastéis', 12, 10, 1)")
    produto_id = banco.ultimo_id()
    banco.executar(
        "INSERT INTO pedidos (numero, cliente_id, data, hora, subtotal, desconto, acrescimo, total, "
        "pagamento, status, observacao) VALUES (12, ?, '06/10/2026', '19:45', 24, 2, 5, 27, 'PIX', ?, 'Troco para 50')",
        (cliente_id, status)
    )
    pedido_id = banco.ultimo_id()
    banco.executar(
        "INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, valor_unitario, subtotal, observacao) "
        "VALUES (?, ?, 2, 12, 24, 'sem cebola')",
        (pedido_id, produto_id)
    )
    return pedido_id


class TesteDadosDaSegundaVia(unittest.TestCase):
    """Dados do pedido lidos do banco para a 2ª via"""

    def setUp(self):
        self.banco = Banco(":memory:")

    def test_monta_pedido_e_itens_como_na_finalizacao(self):
        """Pedido finalizado volta com cliente, endereço, totais e itens"""
        pedido_id = gravar_pedido_exemplo(self.banco)
        pedido, itens = reimpressao.dados_do_pedido(pedido_id, banco=self.banco)
        self.assertEqual(pedido["numero"], 12)
        self.assertEqual(pedido["cliente"], "Ana Souza")
        self.assertEqual(pedido["endereco_cliente"], "Rua Emílio Winther, 45 - Jardim das Nações - Taubaté")
        self.assertEqual((pedido["subtotal"], pedido["desconto"], pedido["acrescimo"], pedido["total"]), (24, 2, 5, 27))
        self.assertEqual(pedido["observacao"], "Troco para 50")
        self.assertEqual(itens, [{"nome": "Pastel de Carne", "qtd": 2, "valor_unitario": 12,
                                  "subtotal": 24, "observacao": "sem cebola"}])

    def test_nao_mexe_no_estoque(self):
        """Reimprimir não baixa estoque do produto"""
        pedido_id = gravar_pedido_exemplo(self.banco)
        reimpressao.dados_do_pedido(pedido_id, banco=self.banco)
        self.assertEqual(self.banco.buscar_um("SELECT estoque FROM produtos")[0], 10)

    def test_pedido_cancelado_nao_reimprime(self):
        """Pedido cancelado avisa para reverter antes"""
        pedido_id = gravar_pedido_exemplo(self.banco, status="Cancelado")
        with self.assertRaisesRegex(reimpressao.ReimpressaoInvalida, "cancelado"):
            reimpressao.dados_do_pedido(pedido_id, banco=self.banco)

    def test_pedido_inexistente(self):
        """Pedido que não existe avisa em vez de quebrar"""
        with self.assertRaisesRegex(reimpressao.ReimpressaoInvalida, "não encontrado"):
            reimpressao.dados_do_pedido(999, banco=self.banco)

    def test_cliente_balcao_sem_endereco(self):
        """Cliente Balcão sai sem linha de endereço"""
        self.banco.executar(
            "INSERT INTO pedidos (numero, cliente_id, data, hora, subtotal, desconto, acrescimo, total, pagamento, status) "
            "VALUES (3, NULL, '06/10/2026', '12:00', 10, 0, 0, 10, 'Dinheiro', 'Finalizado')"
        )
        pedido, itens = reimpressao.dados_do_pedido(self.banco.ultimo_id(), banco=self.banco)
        self.assertEqual((pedido["cliente"], pedido["endereco_cliente"], itens), ("Cliente Balcão", "", []))


class TesteTarjaSegundaVia(unittest.TestCase):
    """Tarja "2ª VIA" no cupom impresso"""

    def test_so_a_segunda_via_tem_a_tarja(self):
        """Só a reimpressão sai marcada como 2ª via"""
        from utils import impressora
        banco = Banco(":memory:")
        pedido, itens = reimpressao.dados_do_pedido(gravar_pedido_exemplo(banco), banco=banco)
        marca = "2ª VIA".encode(impressora.CODEPAGE)
        self.assertIn(marca, impressora.montar_cupom({"nome": "Los Pastelles"}, pedido, itens, segunda_via=True))
        self.assertNotIn(marca, impressora.montar_cupom({"nome": "Los Pastelles"}, pedido, itens))


class TesteLarguraTelaRelatorios(unittest.TestCase):
    """Tela de Relatórios cabe no PC da loja (1366x768) com o botão novo"""

    @classmethod
    def setUpClass(cls):
        cls._ambiente = ambiente_grafico()
        cls._ambiente.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ambiente.__exit__(None, None, None)

    def test_nenhum_widget_estoura_a_largura_disponivel(self):
        """Nenhum widget da tela de Relatórios estoura a largura disponível"""
        import customtkinter as ctk
        from screens import relatorios

        banco_real = relatorios.banco
        relatorios.banco = Banco(":memory:")
        root = ctk.CTk()
        root.geometry("1366x768")

        try:
            tela = relatorios.Relatorios(root)
            root.update_idletasks()
            estouros = [
                (widget, widget.winfo_reqwidth())
                for widget in tela.scroll.winfo_children()
                if widget.winfo_reqwidth() > 1040
            ]
        finally:
            fechar_janela(root)
            relatorios.banco = banco_real

        self.assertEqual(estouros, [])


if __name__ == "__main__":
    unittest.main()
