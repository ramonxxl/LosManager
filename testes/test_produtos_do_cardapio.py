"""
Produtos que o cardápio online vende e o caixa precisa ter
(database/conexao.Banco._garantir_produtos_do_cardapio).

Rodar com:
    python -m testes
"""

import os
import tempfile
import unittest

from database.conexao import Banco
from repositorios import pedidos_online as po


class TesteProdutosDoCardapio(unittest.TestCase):

    def test_combo_mini_existe_e_casa_com_o_pedido_online(self):
        """Banco da loja (com produtos) ganha o Combo Mini Degustação ao abrir, e o pedido online do combo entra sem ⚠"""
        caminho = os.path.join(tempfile.mkdtemp(), "loja.db")
        banco = Banco(caminho)
        self.assertIsNone(banco.buscar_um("SELECT id FROM produtos WHERE nome='Combo Mini Degustação'"))   # vazio: não cria
        banco.executar("INSERT INTO produtos (nome, categoria, preco, estoque, ativo) VALUES ('Carne', 'Tradicionais', 15.9, 10, 1)")
        banco.conexao.close()
        banco = Banco(caminho)
        linha = banco.buscar_um("SELECT nome, categoria, preco, ativo FROM produtos WHERE nome='Combo Mini Degustação'")
        self.assertEqual(linha, ("Combo Mini Degustação", "Combos", 31.9, 1))
        pedido = {"id": 1, "status": "novo", "cliente": {"nome": "Ana", "whatsapp": "5512991112222"}, "entrega": {"tipo": "retirada"},
                  "pagamento": {"forma": "pix"}, "subtotal": 3190, "taxa": 0, "total": 3190, "obs": "",
                  "itens": [{"produto": 99, "nome": "Combo Mini Degustação", "qtd": 1, "unit": 3190, "total": 3190, "obs": "",
                             "escolhas": [{"grupo": "Escolha 3 sabores mini", "nome": "Carne", "n": 2, "preco": 0},
                                          {"grupo": "Escolha 3 sabores mini", "nome": "Pizza", "n": 1, "preco": 0}]}]}
        itens, avisos = po.montar_itens(pedido, banco)
        self.assertEqual(avisos, [])
        self.assertEqual([(i["nome"], i["valor_unitario"], i["observacao"]) for i in itens],
                         [("Combo Mini Degustação", 31.9, "+ 2x Carne | + Pizza")])
        banco.conexao.close()

    def test_apagado_pela_loja_nao_volta(self):
        """Se a loja apagar o produto, ele não é recriado na próxima abertura"""
        pasta = tempfile.mkdtemp()
        caminho = os.path.join(pasta, "teste.db")
        banco = Banco(caminho)
        banco.executar("INSERT INTO produtos (nome, categoria, preco, estoque, ativo) VALUES ('Carne', 'Tradicionais', 15.9, 10, 1)")
        banco.conexao.close()
        banco = Banco(caminho)
        self.assertIsNotNone(banco.buscar_um("SELECT id FROM produtos WHERE nome='Combo Mini Degustação'"))
        banco.executar("DELETE FROM produtos WHERE nome='Combo Mini Degustação'")
        banco.conexao.close()
        banco = Banco(caminho)
        self.assertIsNone(banco.buscar_um("SELECT id FROM produtos WHERE nome='Combo Mini Degustação'"))
        banco.conexao.close()

    def test_cadastrado_a_mao_nao_duplica(self):
        """Se já existir com o mesmo nome (cadastro manual), não cria outro"""
        pasta = tempfile.mkdtemp()
        caminho = os.path.join(pasta, "teste.db")
        import sqlite3
        c = sqlite3.connect(caminho)
        c.execute("CREATE TABLE produtos(id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, nome TEXT NOT NULL, categoria TEXT, custo REAL DEFAULT 0, preco REAL NOT NULL, estoque INTEGER DEFAULT 0, ativo INTEGER DEFAULT 1, foto TEXT)")
        c.execute("INSERT INTO produtos(nome, categoria, preco) VALUES ('combo mini degustação', 'Combos', 30.0)")
        c.commit(); c.close()
        banco = Banco(caminho)
        self.assertEqual(banco.buscar_um("SELECT COUNT(*) FROM produtos WHERE LOWER(nome)=LOWER('Combo Mini Degustação')")[0], 1)
        banco.conexao.close()


if __name__ == "__main__":
    unittest.main()
