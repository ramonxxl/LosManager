"""
Testes do repositório de Produtos (repositorios/produtos.py). Cada
teste abre um banco SQLite ":memory:" isolado — não toca no
losmanager.db real e não precisa de nenhuma janela CustomTkinter.

Rodar com:
    python -m unittest discover -s testes
"""

import unittest

from database.conexao import Banco
from repositorios import produtos as repositorio_produtos


class TesteValidacao(unittest.TestCase):
    """Validação dos campos do formulário de Produtos (nome/preço/estoque)"""

    def test_nome_vazio_e_invalido(self):
        """Nome vazio é rejeitado"""
        with self.assertRaises(repositorio_produtos.ProdutoInvalido):
            repositorio_produtos.validar_nome("   ")

    def test_nome_com_espacos_e_aparado(self):
        """Espaços extras no nome são removidos"""
        self.assertEqual(repositorio_produtos.validar_nome("  Pastel  "), "Pastel")

    def test_preco_aceita_virgula_decimal(self):
        """Preço aceita vírgula como separador decimal (ex: 16,90)"""
        self.assertEqual(repositorio_produtos.validar_preco("16,90"), 16.9)

    def test_preco_invalido(self):
        """Preço não numérico é rejeitado"""
        with self.assertRaises(repositorio_produtos.ProdutoInvalido):
            repositorio_produtos.validar_preco("abc")

    def test_estoque_vazio_vira_zero(self):
        """Estoque em branco é tratado como zero"""
        self.assertEqual(repositorio_produtos.validar_estoque(""), 0)

    def test_estoque_invalido(self):
        """Estoque não numérico é rejeitado"""
        with self.assertRaises(repositorio_produtos.ProdutoInvalido):
            repositorio_produtos.validar_estoque("dez")


class TesteRepositorio(unittest.TestCase):
    """Cadastro de Produtos: criar, editar, listar, excluir e ativar/desativar"""

    def setUp(self):
        # Banco novo e vazio a cada teste, isolado do losmanager.db real.
        self.banco = Banco(":memory:")

    def criar_pastel(self, estoque="10"):
        return repositorio_produtos.criar(
            "Pastel de Carne", "Pastéis", "16,90", estoque, banco=self.banco
        )

    def test_criar_produto_valido(self):
        """Cria um produto com dados válidos"""
        produto_id = self.criar_pastel()

        registro = repositorio_produtos.obter(produto_id, banco=self.banco)

        self.assertEqual(registro, ("Pastel de Carne", "Pastéis", 16.9, 10))

    def test_criar_produto_com_nome_vazio_nao_grava(self):
        """Tentar criar com nome vazio não grava produto nenhum"""
        with self.assertRaises(repositorio_produtos.ProdutoInvalido):
            repositorio_produtos.criar("", "Pastéis", "16,90", "10", banco=self.banco)

        self.assertEqual(repositorio_produtos.listar(banco=self.banco), [])

    def test_atualizar_produto(self):
        """Atualiza os dados de um produto já existente"""
        produto_id = self.criar_pastel()

        repositorio_produtos.atualizar(
            produto_id, "Pastel de Frango", "Pastéis", "15,50", "5", banco=self.banco
        )

        registro = repositorio_produtos.obter(produto_id, banco=self.banco)
        self.assertEqual(registro, ("Pastel de Frango", "Pastéis", 15.5, 5))

    def test_listar_filtra_por_nome_ignorando_acento(self):
        """Busca por nome encontra mesmo ignorando acentuação"""
        self.criar_pastel()
        repositorio_produtos.criar("Caldinho de Feijão", "Caldinhos", "8", "3", banco=self.banco)

        resultado = repositorio_produtos.listar("caldinho", "Nome", banco=self.banco)

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0][1], "Caldinho de Feijão")

    def test_listar_filtra_por_id_invalido_nao_estoura(self):
        """Buscar por um ID inválido não quebra, só não mostra nada"""
        self.criar_pastel()
        resultado = repositorio_produtos.listar("abc", "ID", banco=self.banco)
        self.assertEqual(resultado, [])

    def test_excluir_produto_nunca_vendido_apaga_de_vez(self):
        """Produto que nunca foi vendido é excluído de vez"""
        produto_id = self.criar_pastel()

        resultado = repositorio_produtos.excluir(produto_id, banco=self.banco)

        self.assertEqual(resultado, "excluido")
        self.assertIsNone(repositorio_produtos.obter(produto_id, banco=self.banco))

    def test_excluir_produto_ja_vendido_apenas_desativa(self):
        """Produto que já foi vendido é apenas desativado (mantém o histórico)"""
        produto_id = self.criar_pastel()

        self.banco.executar(
            "INSERT INTO clientes(nome) VALUES(?)", ("Cliente Teste",)
        )
        self.banco.executar(
            "INSERT INTO pedidos(numero, cliente_id, status) VALUES(1, 1, 'Finalizado')"
        )
        pedido_id = self.banco.ultimo_id()
        self.banco.executar(
            "INSERT INTO itens_pedido(pedido_id, produto_id, quantidade) VALUES(?,?,1)",
            (pedido_id, produto_id)
        )

        resultado = repositorio_produtos.excluir(produto_id, banco=self.banco)

        self.assertEqual(resultado, "desativado")
        nome, categoria, preco, estoque = repositorio_produtos.obter(produto_id, banco=self.banco)
        self.assertEqual(nome, "Pastel de Carne")

        ativo = self.banco.buscar_um("SELECT ativo FROM produtos WHERE id=?", (produto_id,))
        self.assertEqual(ativo[0], 0)

    def test_alternar_ativo(self):
        """Alterna um produto entre ativo e inativo"""
        produto_id = self.criar_pastel()

        novo_status = repositorio_produtos.alternar_ativo(produto_id, banco=self.banco)
        self.assertEqual(novo_status, 0)

        novo_status = repositorio_produtos.alternar_ativo(produto_id, banco=self.banco)
        self.assertEqual(novo_status, 1)


if __name__ == "__main__":
    unittest.main()
