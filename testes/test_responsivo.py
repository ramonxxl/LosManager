"""
Teste direto de `utils/responsivo.py` (`linhas_para_tabela` +
`tornar_dinamica`) usando uma tela mínima — apenas um label e uma
Treeview dentro de um CTkScrollableFrame, sem o formulário completo
de nenhuma tela real.

Isso garante que a lógica de responsividade é exercitada de verdade
(janela redimensionada, debounce disparado, height da tabela muda)
em qualquer ambiente gráfico, inclusive o CI `windows-latest` com
~768px de altura — o que o teste em `test_tela_produtos_responsividade`
não consegue lá, porque a tela de Produtos tem conteúdo demais acima
da tabela pra sair do piso mínimo numa tela tão pequena.
"""

import time
import tkinter.ttk as ttk
import unittest

from testes.gui_ambiente import ambiente_grafico, fechar_janela
from utils.responsivo import (
    ATRASO_DEBOUNCE_MS,
    MINIMO_LINHAS_PADRAO,
    linhas_para_tabela,
    tornar_dinamica,
)

ESPERA_DEBOUNCE_SEGUNDOS = (ATRASO_DEBOUNCE_MS + 1000) / 1000
ALTURA_JANELA_PEQUENA = 300


class TesteResponsivo(unittest.TestCase):
    """Responsividade da tabela com tornar_dinamica (tela mínima)"""

    @classmethod
    def setUpClass(cls):
        cls._ambiente = ambiente_grafico()
        cls._ambiente.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ambiente.__exit__(None, None, None)

    def _redimensionar_e_esperar(self, root, geometria):
        """Aplica a geometria e espera o debounce do tornar_dinamica."""
        root.geometry(geometria)
        root.update()
        time.sleep(ESPERA_DEBOUNCE_SEGUNDOS)
        root.update()

    def test_tabela_acompanha_redimensionamento(self):
        """tornar_dinamica recalcula a altura da tabela ao redimensionar"""

        import customtkinter as ctk
        from utils.tema import aplicar_estilo_tabela

        root = ctk.CTk()
        aplicar_estilo_tabela()

        altura_tela = root.winfo_screenheight()
        margem = 30
        altura_grande = max(altura_tela - margem, 500)

        root.geometry(f"1366x{altura_grande}")

        try:
            tela = ctk.CTkFrame(root)
            tela.pack(fill="both", expand=True)

            scroll = ctk.CTkScrollableFrame(tela)
            scroll.pack(fill="both", expand=True, padx=10, pady=10)

            label = ctk.CTkLabel(scroll, text="Título de teste")
            label.pack(pady=5)

            root.update_idletasks()

            linhas_iniciais = linhas_para_tabela(tela, scroll, pady_tabela=5)

            tabela = ttk.Treeview(
                scroll,
                columns=("col1", "col2"),
                show="headings",
                height=linhas_iniciais,
            )
            tabela.heading("col1", text="Coluna 1")
            tabela.heading("col2", text="Coluna 2")
            tabela.pack(fill="x", pady=5)

            tornar_dinamica(
                tela, scroll, lambda: tabela, pady_tabela=5
            )

            root.update()
            time.sleep(ESPERA_DEBOUNCE_SEGUNDOS)
            root.update()

            linhas_grande = int(tabela.cget("height"))

            self.assertGreater(
                linhas_grande, MINIMO_LINHAS_PADRAO,
                f"Com uma tela mínima a {altura_grande}px, a tabela "
                f"deveria ter mais que {MINIMO_LINHAS_PADRAO} linhas, "
                f"mas tem {linhas_grande}."
            )

            self._redimensionar_e_esperar(
                root, f"1366x{ALTURA_JANELA_PEQUENA}"
            )
            linhas_pequena = int(tabela.cget("height"))

            self._redimensionar_e_esperar(
                root, f"1366x{altura_grande}"
            )
            linhas_volta = int(tabela.cget("height"))

            self.assertLess(
                linhas_pequena, linhas_grande,
                f"A tabela deveria ter MENOS linhas na janela pequena "
                f"(grande: {linhas_grande}, pequena: {linhas_pequena})."
            )
            self.assertGreater(
                linhas_volta, linhas_pequena,
                f"A tabela deveria voltar a ter MAIS linhas depois de "
                f"crescer (tinha {linhas_pequena}, ficou {linhas_volta})."
            )
        finally:
            fechar_janela(root)


if __name__ == "__main__":
    unittest.main()
