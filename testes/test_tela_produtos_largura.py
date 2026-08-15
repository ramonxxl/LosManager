"""
Teste do "orçamento de largura de tela" (ver CLAUDE.md, seção "Screen
width budget") aplicado à tela de Produtos: builda a tela sob uma
janela 1366x768 (o PC da loja) e garante que nenhum filho direto do
`self.scroll` estoura a largura disponível (~1040px, depois da
sidebar/paddings do main.py) — foi exatamente isso que vazou o botão
"Remover selecionado" da tela de Pedidos pra fora da tela uma vez.

Esse é um teste de GUI de verdade — cria widgets Tk/CustomTkinter de
verdade, então precisa de um display utilizável. `testes/gui_ambiente.py`
descobre sozinho o que já está disponível (Windows, Linux com monitor,
ou Linux só de terminal via Xvfb) — ver esse módulo para detalhes.
"""

import unittest

from testes.gui_ambiente import ambiente_grafico, fechar_janela


LARGURA_MAXIMA_CONTEUDO = 1040


class TesteLarguraTelaProdutos(unittest.TestCase):
    """Orçamento de largura de tela no PC da loja (1366x768)"""

    @classmethod
    def setUpClass(cls):
        cls._ambiente = ambiente_grafico()
        cls._ambiente.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ambiente.__exit__(None, None, None)

    def test_nenhum_widget_estoura_a_largura_disponivel(self):
        """Nenhum widget da tela estoura a largura disponível"""

        # Importados só agora (depois que o ambiente_grafico já
        # garantiu um display) — customtkinter/screens.produtos criam
        # widgets reais na hora de montar a tela.
        import customtkinter as ctk
        from screens.produtos import Produtos

        root = ctk.CTk()
        root.geometry("1366x768")

        try:
            tela = Produtos(root)
            root.update_idletasks()

            estouros = [
                (widget, widget.winfo_reqwidth())
                for widget in tela.scroll.winfo_children()
                if widget.winfo_reqwidth() > LARGURA_MAXIMA_CONTEUDO
            ]
        finally:
            fechar_janela(root)

        self.assertEqual(
            estouros, [],
            "Widget(s) estourando os ~{}px de largura disponível no PC "
            "da loja (1366x768, sidebar + paddings já descontados): {}"
            .format(LARGURA_MAXIMA_CONTEUDO, estouros)
        )


if __name__ == "__main__":
    unittest.main()
