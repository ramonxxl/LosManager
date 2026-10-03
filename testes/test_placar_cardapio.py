"""
Placar da fidelidade enviado ao cardápio online
(repositorios/fidelidade.placar_para_cardapio). Banco em memória.

Rodar com:
    python -m testes
"""

import unittest

from database.conexao import Banco
from repositorios import fidelidade as repositorio_fidelidade
from utils import cardapio_online


class TestePlacarCardapio(unittest.TestCase):

    def setUp(self):
        self.banco = Banco(":memory:")
        self.dia = 0

    def cliente(self, nome, telefone):
        self.banco.executar("INSERT INTO clientes(nome, telefone) VALUES(?, ?)", (nome, telefone))
        return self.banco.ultimo_id()

    def pedidos(self, cliente_id, quantidade):
        for _ in range(quantidade):
            self.dia += 1
            self.banco.executar("INSERT INTO pedidos(numero, status, data) VALUES(?, 'Finalizado', ?)",
                                (self.dia, f"{self.dia:02d}/01/2026"))
            repositorio_fidelidade.registrar_pedido_concluido(cliente_id, self.banco.ultimo_id(), banco=self.banco)
        self.banco.commit()

    def test_so_telefone_e_numeros(self):
        """Vai telefone (só dígitos), pontos e prêmios — sem nome"""
        ana = self.cliente("Ana", "(12) 99111-2222")
        self.pedidos(ana, 12)
        placar = repositorio_fidelidade.placar_para_cardapio(banco=self.banco)
        self.assertEqual(placar, [{"tel": "12991112222", "pontos": 12, "premios": 1}])

    def test_sem_telefone_ou_curto_fica_fora(self):
        """Cliente sem telefone (ou com número incompleto) não entra no placar"""
        self.pedidos(self.cliente("Balcão", ""), 2)
        self.pedidos(self.cliente("Bruno", "1234"), 2)
        self.pedidos(self.cliente("Carla", "99777-3333"), 3)
        placar = repositorio_fidelidade.placar_para_cardapio(banco=self.banco)
        self.assertEqual(placar, [{"tel": "997773333", "pontos": 3, "premios": 0}])

    def test_envio_repetido_igual_nao_sai_de_novo(self):
        """Placar igual ao último enviado com sucesso não é reenviado"""
        cardapio_online._placar["ultimo"] = None
        placar = [{"tel": "12991112222", "pontos": 3, "premios": 0}]
        cardapio_online._placar["ultimo"] = __import__("json").dumps([placar, 10], sort_keys=True)
        self.assertFalse(cardapio_online.enviar_placar_em_segundo_plano(placar, 10))
        cardapio_online._placar["ultimo"] = None


if __name__ == "__main__":
    unittest.main()
