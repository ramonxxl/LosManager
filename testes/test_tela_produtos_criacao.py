"""
Teste de ponta a ponta da criação de um produto pela tela de Produtos:
preenche os campos do formulário e "clica" em Salvar (chamando
`tela.salvar()`, o mesmo método ligado ao botão) como um usuário
faria, depois confere que o produto aparece na tabela e foi gravado
no banco.

É um teste de GUI de verdade — mesmo padrão de
`test_tela_produtos_largura.py`/`test_tela_produtos_responsividade.py`,
usando `ambiente_grafico()` pra garantir um display. A diferença é que
este teste ESCREVE dado, então cada teste troca `database.conexao.banco`
por um `Banco(":memory:")` isolado antes de montar a tela (ver setUp) —
sem isso, a tela gravaria de verdade no `losmanager.db` da loja.
"""

import unittest

from database import conexao
from testes.gui_ambiente import ambiente_grafico, fechar_janela


class TesteCriacaoProdutoPelaTela(unittest.TestCase):
    """Criação de produto pela tela de verdade (formulário + botão Salvar)"""

    @classmethod
    def setUpClass(cls):
        cls._ambiente = ambiente_grafico()
        cls._ambiente.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ambiente.__exit__(None, None, None)

    def setUp(self):
        # Troca o banco de produção por um isolado antes de CADA teste
        # — a tela chama `repositorios.produtos` sem passar `banco=`,
        # então ela usa o que estiver em `conexao.banco` neste momento.
        self._banco_producao = conexao.banco
        self.banco_teste = conexao.Banco(":memory:")
        conexao.banco = self.banco_teste

    def tearDown(self):
        conexao.banco = self._banco_producao

    def test_criar_produto_simples_pela_tela(self):
        """Cria um produto simples preenchendo o formulário e clicando em Salvar"""

        # Importados só agora (depois que o ambiente_grafico já
        # garantiu um display e o setUp já trocou o banco) —
        # customtkinter/screens.produtos criam widgets reais e já
        # carregam a lista do banco na hora de montar a tela.
        import customtkinter as ctk
        from screens.produtos import Produtos

        root = ctk.CTk()
        root.geometry("1366x768")

        try:
            tela = Produtos(root)
            root.update()

            self.assertEqual(tela.tabela.get_children(), ())

            tela.nome.insert(0, "Pastel de Carne")
            tela.categoria.insert(0, "Pastéis")
            tela.preco.insert(0, "16,90")
            tela.estoque.insert(0, "10")

            tela.salvar()
            root.update()

            linhas = tela.tabela.get_children()
            self.assertEqual(len(linhas), 1)

            produto_id, nome, categoria, preco, estoque, ativo = \
                tela.tabela.item(linhas[0], "values")

            self.assertEqual(nome, "Pastel de Carne")
            self.assertEqual(categoria, "Pastéis")
            self.assertEqual(preco, "16.9")
            self.assertEqual(estoque, "10")
            self.assertEqual(ativo, "Sim")

            # O formulário deve limpar depois de salvar, pronto pro
            # próximo cadastro.
            self.assertEqual(tela.nome.get(), "")
            self.assertEqual(tela.preco.get(), "")
        finally:
            fechar_janela(root)

        # Confirma que também foi gravado no banco (não só na tela) e
        # que foi no banco de TESTE, não no losmanager.db real.
        registro = self.banco_teste.buscar_um(
            "SELECT nome, categoria, preco, estoque, ativo FROM produtos WHERE id=?",
            (produto_id,)
        )
        self.assertEqual(registro, ("Pastel de Carne", "Pastéis", 16.9, 10, 1))


if __name__ == "__main__":
    unittest.main()
