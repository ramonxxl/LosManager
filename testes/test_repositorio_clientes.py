"""
Exclusão de cliente (repositorios/clientes.py). Banco em memória.

Rodar com:
    python -m testes
"""

import unittest

from database.conexao import Banco
from repositorios import clientes as repositorio_clientes
from repositorios import fidelidade as repositorio_fidelidade


class TesteExcluirCliente(unittest.TestCase):

    def setUp(self):
        self.banco = Banco(":memory:")
        self.banco.executar("INSERT INTO clientes(nome, telefone) VALUES('Ana', '12991112222')")
        self.ana = self.banco.ultimo_id()
        self.banco.executar("INSERT INTO clientes(nome, telefone) VALUES('Bruno', '12988881111')")
        self.bruno = self.banco.ultimo_id()

    def pedido(self, cliente_id, dia, total=30.0):
        self.banco.executar("INSERT INTO pedidos(numero, cliente_id, status, data, total) VALUES(?, ?, 'Finalizado', ?, ?)",
                            (dia, cliente_id, f"{dia:02d}/01/2026", total))
        pid = self.banco.ultimo_id()
        repositorio_fidelidade.registrar_pedido_concluido(cliente_id, pid, banco=self.banco)
        self.banco.commit()
        return pid

    def test_cliente_sem_pedido_some_de_vez(self):
        """Cliente sem pedidos é apagado junto com os endereços"""
        self.banco.executar("INSERT INTO enderecos_cliente(cliente_id, endereco, principal) VALUES(?, 'Rua A', 1)", (self.ana,))
        self.assertEqual(repositorio_clientes.excluir(self.ana, banco=self.banco), 0)
        self.assertIsNone(self.banco.buscar_um("SELECT id FROM clientes WHERE id=?", (self.ana,)))
        self.assertEqual(self.banco.buscar_um("SELECT COUNT(*) FROM enderecos_cliente WHERE cliente_id=?", (self.ana,))[0], 0)

    def test_pedidos_ficam_como_balcao_e_total_nao_muda(self):
        """Pedidos do cliente excluído continuam (como Balcão) e o total vendido não muda"""
        p1, p2 = self.pedido(self.ana, 1, 30.0), self.pedido(self.ana, 2, 20.0)
        self.pedido(self.bruno, 3, 10.0)
        antes = self.banco.buscar_um("SELECT SUM(total) FROM pedidos")[0]
        self.assertEqual(repositorio_clientes.excluir(self.ana, banco=self.banco), 2)
        self.assertEqual(self.banco.buscar_um("SELECT SUM(total) FROM pedidos")[0], antes)
        for pid in (p1, p2):
            self.assertIsNone(self.banco.buscar_um("SELECT cliente_id FROM pedidos WHERE id=?", (pid,))[0])

    def test_fidelidade_do_excluido_some_e_a_dos_outros_fica(self):
        """Pontos do cliente excluído somem; os dos outros clientes ficam iguais"""
        self.pedido(self.ana, 1)
        self.pedido(self.bruno, 2)
        repositorio_clientes.excluir(self.ana, banco=self.banco)
        self.assertEqual(self.banco.buscar_um("SELECT COUNT(*) FROM fidelidade WHERE cliente_id=?", (self.ana,))[0], 0)
        self.assertEqual(self.banco.buscar_um("SELECT COUNT(*) FROM historico_fidelidade WHERE cliente_id=?", (self.ana,))[0], 0)
        self.assertEqual(repositorio_fidelidade.obter_status_cliente(self.bruno, banco=self.banco)["total_pedidos"], 1)

    def test_resumo_antes_de_excluir(self):
        """O resumo mostra nome, pedidos, endereços e pontos antes de excluir"""
        self.pedido(self.ana, 1)
        self.pedido(self.ana, 2)
        self.banco.executar("INSERT INTO enderecos_cliente(cliente_id, endereco, principal) VALUES(?, 'Rua A', 1)", (self.ana,))
        self.assertEqual(repositorio_clientes.resumo_exclusao(self.ana, banco=self.banco),
                         {"nome": "Ana", "pedidos": 2, "enderecos": 1, "pontos": 2})
        self.assertIsNone(repositorio_clientes.resumo_exclusao(9999, banco=self.banco))


if __name__ == "__main__":
    unittest.main()
