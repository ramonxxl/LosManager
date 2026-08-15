"""
Teste da tabela responsiva da tela de Produtos (ver CLAUDE.md, seção
"Responsive screens" e `utils/responsivo.py`): a lista de produtos não
tem uma altura fixa de linhas — ela é recalculada a partir do espaço
realmente disponível sempre que a janela principal é redimensionada,
via `responsivo.tornar_dinamica`.

É um teste de GUI de verdade (cria a tela real e redimensiona a
janela raiz de verdade), então segue o mesmo padrão de
`test_tela_produtos_largura.py`: usa `ambiente_grafico()` pra garantir
um display utilizável (Windows / Linux com monitor / Xvfb automático),
e só importa customtkinter/screens depois que esse ambiente já está
pronto.

As alturas usadas não são fixas nem os 1366x768 do PC da loja — são
calculadas em cima do tamanho real da tela (`winfo_screenheight()`) na
hora do teste, e com retentativa, por dois problemas vistos na prática
rodando isso de verdade (não só localmente):

1. Numa primeira versão com 768/500/900 fixos: passava em todo lugar
   testado localmente, mas falhou na Action (windows-latest) — lá a
   mesma tela consome bem mais altura antes de chegar na tabela (a
   fonte "Arial" de verdade rende mais alta que a substituta do
   Linux/Xvfb), então 768px já batia no piso mínimo de linhas e a
   diferença entre os tamanhos desaparecia. E o windows-latest também
   se revelou ter uma tela pequena (~768px) — inclusive menor que a
   margem de segurança do item 2 abaixo, então uma margem fixa grande
   também não serve.
2. Tentando compensar com uma altura BEM maior que a tela (pra
   garantir folga): alguns window managers tratam um geometry() maior
   que a tela como um pedido de maximizar, e depois de "maximizado"
   passam a ignorar geometry() menores — reproduzido numa sessão
   gráfica real (Linux com monitor) aqui, com só 80px de margem.

Como as duas situações pedem margens opostas (pouca margem pra ter
folga numa tela pequena; bastante margem pra não travar num monitor
real), o teste tenta as duas em sequência e usa a primeira que
funcionar, em vez de arriscar acertar uma única margem pra todo
ambiente possível.

IMPORTANTE: após construir a tela, o teste espera o debounce do
`tornar_dinamica` antes de ler o `height` inicial da tabela. No Windows
a fonte "Arial" real consome mais espaço vertical que no Linux/Xvfb,
fazendo o `linhas_para_tabela` inicial (em `Produtos.__init__`) retornar
o piso de 4 linhas — mas o recálculo pós-`<Configure>` (que passa pelo
debounce) corrige pro valor real. Sem essa espera, o teste lia 4 linhas
tanto na janela grande quanto na pequena e pulava por achar que não
conseguia escapar do piso, quando na verdade o problema era só timing.

Na Action (`windows-latest`) ainda pode pular, dado que a tela do runner
é fixa em ~768px e a tabela pode não escapar do piso mesmo com o debounce
completo — isso é uma limitação da resolução daquele runner, não do teste.
"""

import time
import unittest

from testes.gui_ambiente import ambiente_grafico, fechar_janela
from utils.responsivo import ATRASO_DEBOUNCE_MS, MINIMO_LINHAS_PADRAO

# Bem mais folgado que o ATRASO_DEBOUNCE_MS do próprio
# utils/responsivo.py, pra não dar falso negativo numa máquina lenta
# ou momentaneamente carregada (a Action, por exemplo, é bem mais
# lenta que uma máquina de desenvolvedor pra isso).
ESPERA_DEBOUNCE_SEGUNDOS = (ATRASO_DEBOUNCE_MS + 1000) / 1000

ALTURA_JANELA_PEQUENA = 300

# Margens candidatas (px) subtraídas da altura real da tela pra montar
# o estado "grande" — tentadas nessa ordem. A primeira (quase sem
# margem) maximiza o espaço disponível pra escapar do piso mínimo de
# linhas em telas pequenas (ex: windows-latest, ~768px); a segunda é
# o fallback pra ambientes com um window manager que gruda a janela
# quando ela chega muito perto do tamanho da tela (ver docstring do
# módulo).
MARGENS_TELA_PX = [30, 200]

# Diferença mínima de altura real (px) entre as duas janelas pra
# considerar que o ambiente gráfico atual realmente deixou redimensionar
# o suficiente pra testar — abaixo disso, a tentativa não conta.
DIFERENCA_MINIMA_PX = 100


class TesteResponsividadeTelaProdutos(unittest.TestCase):
    """Tabela de produtos responsiva ao redimensionar a janela"""

    @classmethod
    def setUpClass(cls):
        cls._ambiente = ambiente_grafico()
        cls._ambiente.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ambiente.__exit__(None, None, None)

    def _redimensionar_e_esperar(self, root, geometria):
        """Aplica uma nova geometria na janela raiz e dá tempo pro
        `<Configure>` disparar e pro debounce de utils/responsivo.py
        (recalcula só depois de ATRASO_DEBOUNCE_MS parado) terminar,
        antes de ler a altura resultante da tabela."""

        root.geometry(geometria)
        root.update()

        time.sleep(ESPERA_DEBOUNCE_SEGUNDOS)
        root.update()

    def _tentar_com_margem(self, margem):
        """Monta a tela do zero com o estado 'grande' calculado a
        partir dessa margem, redimensiona pro 'pequeno' e de volta pro
        'grande', e devolve (sucesso, dados). `dados` traz os números
        medidos nos dois casos (pra usar na asserção ou no diagnóstico
        de skip)."""

        import customtkinter as ctk
        from screens.produtos import Produtos

        root = ctk.CTk()

        altura_grande = max(root.winfo_screenheight() - margem, 500)
        geometria_grande = f"1366x{altura_grande}"

        root.geometry(geometria_grande)

        try:
            tela = Produtos(root)
            root.update()

            # Esperar o debounce do tornar_dinamica antes de ler o
            # height inicial — sem isso, no Windows o cálculo inicial
            # de linhas_para_tabela retorna o piso (4) porque as fontes
            # reais consomem mais espaço, e só o recálculo pós-Configure
            # (que passa pelo debounce) corrige pro valor real.
            time.sleep(ESPERA_DEBOUNCE_SEGUNDOS)
            root.update()

            altura_janela_grande = root.winfo_height()
            linhas_janela_grande = int(tela.tabela.cget("height"))

            self._redimensionar_e_esperar(root, f"1366x{ALTURA_JANELA_PEQUENA}")
            altura_janela_pequena = root.winfo_height()
            linhas_janela_pequena = int(tela.tabela.cget("height"))

            self._redimensionar_e_esperar(root, geometria_grande)
            linhas_apos_crescer_de_novo = int(tela.tabela.cget("height"))
        finally:
            fechar_janela(root)

        dados = {
            "margem": margem,
            "altura_janela_grande": altura_janela_grande,
            "altura_janela_pequena": altura_janela_pequena,
            "linhas_janela_grande": linhas_janela_grande,
            "linhas_janela_pequena": linhas_janela_pequena,
            "linhas_apos_crescer_de_novo": linhas_apos_crescer_de_novo,
        }

        redimensionou_o_suficiente = (
            altura_janela_grande - altura_janela_pequena >= DIFERENCA_MINIMA_PX
        )
        escapou_do_piso = linhas_janela_grande > MINIMO_LINHAS_PADRAO

        return (redimensionou_o_suficiente and escapou_do_piso), dados

    def test_altura_da_tabela_muda_ao_redimensionar_a_janela(self):
        """A altura da tabela acompanha o redimensionamento da janela"""

        tentativas = []

        for margem in MARGENS_TELA_PX:
            sucesso, dados = self._tentar_com_margem(margem)
            tentativas.append(dados)

            if sucesso:
                break
        else:
            self.skipTest(
                "Este ambiente gráfico não deu pra testar com nenhuma das "
                f"margens tentadas ({MARGENS_TELA_PX}px): " +
                "; ".join(
                    f"margem={d['margem']}px -> grande={d['altura_janela_grande']}px"
                    f"/{d['linhas_janela_grande']}linhas, "
                    f"pequena={d['altura_janela_pequena']}px"
                    f"/{d['linhas_janela_pequena']}linhas"
                    for d in tentativas
                )
            )

        self.assertLess(
            dados["linhas_janela_pequena"], dados["linhas_janela_grande"],
            "A tabela deveria ter MENOS linhas na janela pequena do que "
            f"na grande (grande: {dados['linhas_janela_grande']} linhas em "
            f"{dados['altura_janela_grande']}px; pequena: "
            f"{dados['linhas_janela_pequena']} linhas em "
            f"{dados['altura_janela_pequena']}px)."
        )
        self.assertGreater(
            dados["linhas_apos_crescer_de_novo"], dados["linhas_janela_pequena"],
            "A tabela deveria voltar a ter MAIS linhas depois que a "
            f"janela cresceu de novo (tinha {dados['linhas_janela_pequena']}, "
            f"ficou {dados['linhas_apos_crescer_de_novo']})."
        )


if __name__ == "__main__":
    unittest.main()
