"""
Teste da migração retroativa de fidelidade (database/conexao.py,
`_migrar_pedidos_antigos_para_fidelidade`): quando o Programa de
Fidelidade chega a um banco que já tinha pedidos de antes dele
existir, cada pedido finalizado (não cancelado) com cliente
identificado precisa contar pra fidelidade — sem isso, clientes
antigos perderiam o que já tinham direito.

Usa um arquivo SQLite temporário de verdade (não ":memory:") porque o
cenário simulado é justamente "abrir um banco que já existia no disco,
escrito por uma versão anterior do sistema, sem nenhuma tabela de
fidelidade ainda" — só dá pra reproduzir isso criando as tabelas
antigas na mão com sqlite3 puro *antes* de qualquer `Banco(...)` tocar
no arquivo, e só então abrir com `Banco(caminho=...)`, que roda a
migração pela primeira vez.
"""

import os
import sqlite3
import tempfile
import unittest

from database.conexao import Banco
from repositorios import fidelidade as repositorio_fidelidade


class TesteMigracaoRetroativa(unittest.TestCase):
    """Migração retroativa: pedidos antigos passam a contar pra fidelidade"""

    def setUp(self):

        descritor, self.caminho = tempfile.mkstemp(suffix=".db")
        os.close(descritor)

        # Simula um banco de uma versão ANTERIOR ao Programa de
        # Fidelidade: só as tabelas/dados que já existiam antes,
        # escritos direto com sqlite3 (sem passar pelo Banco, que já
        # criaria as tabelas novas).
        conexao_crua = sqlite3.connect(self.caminho)
        # Schema igual ao de `clientes` em database/conexao.py (as
        # colunas de endereço são exigidas pela migração antiga de
        # enderecos_cliente, que roda antes da de fidelidade).
        conexao_crua.execute(
            """
            CREATE TABLE clientes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT, telefone TEXT, celular TEXT,
                endereco TEXT, numero TEXT, bairro TEXT, cidade TEXT, cep TEXT,
                observacao TEXT
            )
            """
        )
        conexao_crua.execute(
            """
            CREATE TABLE pedidos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero INTEGER, cliente_id INTEGER, status TEXT
            )
            """
        )

        joao_id = conexao_crua.execute(
            "INSERT INTO clientes(nome, telefone) VALUES('João', '99999-9999')"
        ).lastrowid

        for numero in range(1, 8):
            conexao_crua.execute(
                "INSERT INTO pedidos(numero, cliente_id, status) VALUES(?, ?, 'Finalizado')",
                (numero, joao_id)
            )

        # Um pedido cancelado antigo não deve contar na migração.
        cancelado_id = conexao_crua.execute(
            "INSERT INTO clientes(nome, telefone) VALUES('Desistiu', '90000-0000')"
        ).lastrowid
        conexao_crua.execute(
            "INSERT INTO pedidos(numero, cliente_id, status) VALUES(99, ?, 'Cancelado')",
            (cancelado_id,)
        )

        # Pedido de Cliente Balcão (sem cliente_id) também não conta.
        conexao_crua.execute(
            "INSERT INTO pedidos(numero, cliente_id, status) VALUES(100, NULL, 'Finalizado')"
        )

        conexao_crua.commit()
        conexao_crua.close()

        self.joao_id = joao_id
        self.cancelado_id = cancelado_id

    def tearDown(self):

        try:
            os.remove(self.caminho)
        except OSError:
            pass

    def _fechar(self, banco):
        banco.conexao.close()

    def test_backfill_registra_pedidos_antigos_nao_cancelados(self):
        """Ao abrir o banco antigo pela 1ª vez, pedidos não cancelados com cliente viram pontos"""

        banco = Banco(caminho=self.caminho)

        try:
            status_joao = repositorio_fidelidade.obter_status_cliente(self.joao_id, banco=banco)
            self.assertEqual(status_joao["total_pedidos"], 7)

            status_cancelado = repositorio_fidelidade.obter_status_cliente(self.cancelado_id, banco=banco)
            self.assertEqual(status_cancelado["total_pedidos"], 0)
        finally:
            self._fechar(banco)

    def test_backfill_nao_roda_de_novo_na_proxima_abertura(self):
        """Reabrir o mesmo banco depois não soma ponto duplicado pros pedidos antigos"""

        banco1 = Banco(caminho=self.caminho)
        self._fechar(banco1)

        banco2 = Banco(caminho=self.caminho)

        try:
            status = repositorio_fidelidade.obter_status_cliente(self.joao_id, banco=banco2)
            self.assertEqual(status["total_pedidos"], 7)
        finally:
            self._fechar(banco2)


if __name__ == "__main__":
    unittest.main()
