"""
Testes de utils/tema.medidas_menu(): na tela da loja (1366x768) o menu
lateral precisa caber inteiro — antes o botão Configurações ficava
cortado embaixo. A função é pura (não abre janela).

Rodar com:
    python -m testes
"""

import unittest


class TesteMenuCompacto(unittest.TestCase):
    """Tamanho do menu lateral conforme a altura da tela"""

    def _altura_pedida(self, medidas, botoes=9, altura_logo_por_largura=0.88):
        """Altura que o menu pede: logo + espaços + botões (com seus espaços)."""
        logo = medidas["logo_largura"] * altura_logo_por_largura + sum(medidas["logo_pady"])
        return logo + botoes * (medidas["botao_altura"] + 2 * medidas["botao_pady"])

    def test_tela_da_loja_usa_menu_compacto_que_cabe(self):
        """Em 1366x768 o menu compacto cabe nos ~670px que sobram"""
        from utils.tema import medidas_menu
        medidas = medidas_menu(768)
        self.assertLessEqual(self._altura_pedida(medidas), 670)

    def test_tela_grande_mantem_menu_normal(self):
        """Em telas de 900px ou mais o menu continua com o tamanho original"""
        from utils.tema import medidas_menu
        self.assertEqual(medidas_menu(1080)["botao_altura"], 52)
        self.assertEqual(medidas_menu(1080)["logo_largura"], 170)


if __name__ == "__main__":
    unittest.main()
