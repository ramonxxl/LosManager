"""
Testes do repositório de Motoboys (repositorios/motoboys.py). Cada
teste abre um banco SQLite ":memory:" isolado — não toca no
losmanager.db real e não precisa de nenhuma janela CustomTkinter.

Rodar com:
    python -m testes
"""

import unittest

from database.conexao import Banco
from repositorios import motoboys as repositorio_motoboys


class TesteValidacao(unittest.TestCase):
    """Validação do nome do motoboy"""

    def test_nome_vazio_e_invalido(self):
        """Nome vazio é rejeitado"""
        with self.assertRaises(repositorio_motoboys.MotoboyInvalido):
            repositorio_motoboys.validar_nome("   ")

    def test_nome_com_espacos_e_aparado(self):
        """Espaços extras no nome são removidos"""
        self.assertEqual(repositorio_motoboys.validar_nome("  Carlos  "), "Carlos")


class TesteRepositorio(unittest.TestCase):
    """Cadastro de Motoboys: criar, listar, excluir e ativar/desativar"""

    def setUp(self):
        # Banco novo e vazio a cada teste, isolado do losmanager.db real.
        self.banco = Banco(":memory:")

    def test_criar_motoboy_valido(self):
        """Cria um motoboy com nome válido"""
        motoboy_id = repositorio_motoboys.criar("Carlos", banco=self.banco)

        listagem = repositorio_motoboys.listar(banco=self.banco)
        self.assertEqual(listagem, [(motoboy_id, "Carlos", 1)])

    def test_criar_motoboy_com_nome_vazio_nao_grava(self):
        """Tentar criar com nome vazio não grava motoboy nenhum"""
        with self.assertRaises(repositorio_motoboys.MotoboyInvalido):
            repositorio_motoboys.criar("", banco=self.banco)

        self.assertEqual(repositorio_motoboys.listar(banco=self.banco), [])

    def test_listar_ativos_ignora_inativos(self):
        """listar_ativos() não traz motoboys desativados"""
        ativo_id = repositorio_motoboys.criar("Carlos", banco=self.banco)
        inativo_id = repositorio_motoboys.criar("João", banco=self.banco)
        repositorio_motoboys.alternar_ativo(inativo_id, banco=self.banco)

        ativos = repositorio_motoboys.listar_ativos(banco=self.banco)
        self.assertEqual(ativos, [(ativo_id, "Carlos")])

    def test_alternar_ativo(self):
        """Alterna um motoboy entre ativo e inativo"""
        motoboy_id = repositorio_motoboys.criar("Carlos", banco=self.banco)

        novo_status = repositorio_motoboys.alternar_ativo(motoboy_id, banco=self.banco)
        self.assertEqual(novo_status, 0)

        novo_status = repositorio_motoboys.alternar_ativo(motoboy_id, banco=self.banco)
        self.assertEqual(novo_status, 1)

    def test_excluir_motoboy_nunca_usado_apaga_de_vez(self):
        """Motoboy que nunca fez uma entrega é excluído de vez"""
        motoboy_id = repositorio_motoboys.criar("Carlos", banco=self.banco)

        resultado = repositorio_motoboys.excluir(motoboy_id, banco=self.banco)

        self.assertEqual(resultado, "excluido")
        self.assertEqual(repositorio_motoboys.listar(banco=self.banco), [])

    def test_excluir_motoboy_ja_usado_apenas_desativa(self):
        """Motoboy que já apareceu num pedido é apenas desativado (mantém o histórico)"""
        motoboy_id = repositorio_motoboys.criar("Carlos", banco=self.banco)

        self.banco.executar(
            "INSERT INTO pedidos(numero, motoboy_id, status) VALUES(1, ?, 'Finalizado')",
            (motoboy_id,)
        )

        resultado = repositorio_motoboys.excluir(motoboy_id, banco=self.banco)

        self.assertEqual(resultado, "desativado")
        listagem = repositorio_motoboys.listar(banco=self.banco)
        self.assertEqual(listagem, [(motoboy_id, "Carlos", 0)])


if __name__ == "__main__":
    unittest.main()
