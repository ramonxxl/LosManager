"""
Situação dos pedidos do cardápio online mudada pelo LosManager
(utils/cardapio_online.py + janela screens/pedidos_online.py): os
mesmos passos do painel, o envio para o site e o aviso no WhatsApp.
Nada aqui acessa a internet — a chamada ao site é substituída.

Rodar com:
    python -m testes
"""

import sys
import unittest
from unittest import mock

from database import conexao
from testes.gui_ambiente import ambiente_grafico, fechar_janela
from utils import cardapio_online


def pedido(id_, status, tipo="entrega", **extra):
    p = {"id": id_, "status": status, "criadoEm": "2026-11-05T22:10:00Z", "cliente": {"nome": "Ana Souza", "whatsapp": "5512991112222"},
         "entrega": {"tipo": tipo, "rua": "Rua A", "numero": "10", "bairro": "Centro"}, "pagamento": {"forma": "pix"},
         "itens": [{"qtd": 1, "nome": "Carne", "total": 1590, "escolhas": []}], "subtotal": 1590, "taxa": 500, "total": 2090,
         "mensagem": f"Olá, Ana! Seu pedido #{id_} ..."}
    p.update(extra)
    return p


class TesteRegras(unittest.TestCase):
    """Próximo passo, link do WhatsApp e envio ao cardápio"""

    def test_proximos_passos_iguais_ao_painel(self):
        """Novo → Aceitar; em preparo → Saiu para entrega (ou Pronto, se retirada); saiu/pronto → Entregue/Concluir"""
        passos = lambda st, tipo="entrega": [s for s, _ in cardapio_online.proximos_status(pedido(1, st, tipo))]
        self.assertEqual(passos("novo"), ["preparo"])
        self.assertEqual(passos("preparo"), ["entrega"])
        self.assertEqual(passos("preparo", "retirada"), ["pronto"])
        self.assertEqual(passos("entrega"), ["concluido"])
        self.assertEqual(passos("pronto", "retirada"), ["concluido"])
        self.assertEqual(passos("concluido"), [])
        self.assertEqual(passos("cancelado"), [])

    def test_link_whatsapp(self):
        """Link abre a conversa do cliente com a mensagem já escrita (acentos e emoji codificados)"""
        link = cardapio_online.link_whatsapp("55 (12) 99111-2222", "Olá! Saiu para entrega 🛵")
        self.assertTrue(link.startswith("https://api.whatsapp.com/send?phone=5512991112222&text=Ol%C3%A1%21%20Saiu"))
        self.assertIsNone(cardapio_online.link_whatsapp("", "oi"))
        self.assertIsNone(cardapio_online.link_whatsapp("5512991112222", ""))

    def test_mudar_status_envia_id_e_situacao(self):
        """mudar_status manda {id, status} para /api/integracao e devolve o pedido atualizado"""
        with mock.patch.object(cardapio_online, "_chamar", return_value={"pedido": {"id": 7, "status": "entrega"}}) as chamar:
            self.assertEqual(cardapio_online.mudar_status(7, "entrega", ("https://x", "t")), {"id": 7, "status": "entrega"})
        chamar.assert_called_once_with("/api/integracao", {"id": 7, "status": "entrega"}, cred=("https://x", "t"))


class TesteJanelaPedidosOnline(unittest.TestCase):
    """Botões de situação na janela de pedidos online"""

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
        cardapio_online.publicar([], None)

    def test_saiu_para_entrega_grava_no_cardapio_e_oferece_whatsapp(self):
        """'Saiu para entrega' manda a situação ao cardápio, atualiza a lista e abre o WhatsApp com a mensagem"""

        import customtkinter as ctk
        from screens import pedidos_online as tela

        enviados, abertos = [], []

        def mudar_falso(widget, pid, status, ao_terminar):
            enviados.append((pid, status))
            ao_terminar(pedido(pid, status, mensagem=f"Olá, Ana! Seu pedido #{pid} saiu para entrega. 🛵 Logo chega aí!"), None)

        cardapio_online.publicar([pedido(5, "preparo"), pedido(6, "novo", "retirada")], None)
        root = ctk.CTk()
        banco_da_tela = tela.banco
        tela.banco = self.banco_teste
        try:
            with mock.patch.object(cardapio_online, "buscar_em_segundo_plano"), \
                 mock.patch.object(cardapio_online, "mudar_status_em_segundo_plano", side_effect=mudar_falso), \
                 mock.patch.object(tela.messagebox, "askyesno", return_value=True) as pergunta, \
                 mock.patch.object(tela.webbrowser, "open", side_effect=abertos.append):
                janela = tela.JanelaPedidosOnline(root, ao_lancar=lambda *a: False)
                root.update()

                janela.tabela.selection_set("5")
                janela.mostrar_detalhe()
                root.update()
                botoes = {b.cget("text"): b for b in janela.acoes.winfo_children()}
                self.assertIn("🛵 Saiu para entrega", botoes)
                self.assertIn("📲 Mandar mensagem ao cliente", botoes)

                botoes["🛵 Saiu para entrega"].invoke()
                root.update()

                self.assertEqual(enviados, [(5, "entrega")])
                self.assertIn("saiu para entrega", pergunta.call_args[0][1])
                self.assertEqual(len(abertos), 1)
                self.assertTrue(abertos[0].startswith("https://api.whatsapp.com/send?phone=5512991112222&text="))
                self.assertIn("Saiu p/ entrega", janela.tabela.item("5", "values")[5])
                # o estado compartilhado (faixa da tela de Pedidos) também ficou com a situação nova
                self.assertEqual(next(p for p in cardapio_online.ultimo_resultado()["pedidos"] if p["id"] == 5)["status"], "entrega")
                # e o próximo passo agora é "Entregue"
                self.assertIn("✔ Entregue", [b.cget("text") for b in janela.acoes.winfo_children()])

                # mudou no painel? a consulta automática redesenha a lista
                cardapio_online.publicar([pedido(5, "concluido"), pedido(6, "preparo", "retirada")], None)
                root.update()
                self.assertIn("Concluído", janela.tabela.item("5", "values")[5])
                janela.destroy()
        finally:
            tela.banco = banco_da_tela
            fechar_janela(root)
            sys.modules.pop("screens.pedidos_online", None)

    def test_erro_do_cardapio_avisa_e_nao_muda(self):
        """Sem internet: avisa que a situação não mudou e a lista continua como estava"""

        import customtkinter as ctk
        from screens import pedidos_online as tela

        cardapio_online.publicar([pedido(5, "preparo")], None)
        root = ctk.CTk()
        banco_da_tela = tela.banco
        tela.banco = self.banco_teste
        try:
            with mock.patch.object(cardapio_online, "buscar_em_segundo_plano"), \
                 mock.patch.object(cardapio_online, "mudar_status_em_segundo_plano",
                                   side_effect=lambda w, pid, st, fim: fim(None, "Sem conexão com o cardápio online. Confira a internet.")), \
                 mock.patch.object(tela.messagebox, "showwarning") as aviso, \
                 mock.patch.object(tela.webbrowser, "open") as abrir:
                janela = tela.JanelaPedidosOnline(root, ao_lancar=lambda *a: False)
                root.update()
                janela.tabela.selection_set("5")
                janela.mostrar_detalhe()
                janela.mudar_status(janela._pedido_selecionado(), "entrega")
                root.update()
                self.assertIn("Sem conexão", aviso.call_args[0][1])
                abrir.assert_not_called()
                self.assertEqual(janela._pedido_selecionado()["status"], "preparo")
                janela.destroy()
        finally:
            tela.banco = banco_da_tela
            fechar_janela(root)
            sys.modules.pop("screens.pedidos_online", None)


if __name__ == "__main__":
    unittest.main()
