"""
Testes de repositorios/pedidos_online.py: conversão de um pedido do
cardápio online para o carrinho da tela de Pedidos (produtos,
adicionais, sabor do refrigerante, cliente, endereço e observação).
Banco isolado em memória — nunca toca o losmanager.db.

Rodar com:
    python -m testes
"""

import unittest

from database.conexao import Banco
from repositorios import pedidos_online as po


def pedido_exemplo(**mudancas):
    pedido = {
        "id": 7,
        "status": "novo",
        "cliente": {"nome": "Ana Souza", "whatsapp": "5512991112222"},
        "entrega": {"tipo": "entrega", "cep": "12030000", "cidade": "Taubaté", "bairro": "Jardim das Nações",
                    "rua": "Rua Emílio Winther", "numero": "45", "complemento": "casa 2", "referencia": "portão azul"},
        "pagamento": {"forma": "dinheiro", "troco": 10000},
        "itens": [
            {"produto": 59, "nome": "Los Pastelles", "qtd": 2, "unit": 2890, "total": 5780, "obs": "bem passado",
             "escolhas": [{"grupo": "Adicionais", "nome": "Catupiry", "n": 1, "preco": 400},
                          {"grupo": "Adicionais", "nome": "Bacon", "n": 1, "preco": 400}]},
            {"produto": 89, "nome": "Refrigerante Lata", "qtd": 1, "unit": 600, "total": 600, "obs": "",
             "escolhas": [{"grupo": "Sabor", "nome": "Guaraná Antarctica", "n": 1, "preco": 0}]},
        ],
        "subtotal": 6380, "taxa": 900, "total": 7280, "obs": "tocar interfone",
    }
    pedido.update(mudancas)
    return pedido


class BaseComBanco(unittest.TestCase):

    def setUp(self):
        self.banco = Banco(":memory:")
        produtos = [
            ("Los Pastelles", "Premium", 20.9), ("Catupiry (adicional)", "Adicionais", 4.0),
            ("Bacon (adicional)", "Adicionais", 4.0), ("Guarana Antarctica Lata", "Bebidas", 6.0),
            ("Coca Cola Lata", "Bebidas", 6.0), ("Pastel de Camarão", "Premium", 25.9),
            ("Caldinho de Mandioquinha Salsa", "Caldinhos", 19.9), ("Carne com Queijo", "Especiais", 16.9),
        ]
        for nome, categoria, preco in produtos:
            self.banco.executar(
                "INSERT INTO produtos (nome, categoria, preco, estoque, ativo) VALUES (?, ?, ?, 100, 1)",
                (nome, categoria, preco)
            )
        self.id_de = {nome: pid for pid, nome in self.banco.buscar("SELECT id, nome FROM produtos")}


class TesteItens(BaseComBanco):
    """Itens do pedido online viram linhas do carrinho"""

    def test_adicionais_viram_linhas_e_total_bate(self):
        """Adicionais pagos viram linhas '(adicional)' e o total é o mesmo que o cliente pagou"""
        itens, avisos = po.montar_itens(pedido_exemplo(), self.banco)
        nomes = [(i["nome"], i["qtd"], i["valor_unitario"]) for i in itens]
        self.assertIn(("Los Pastelles", 2, 20.9), nomes)
        self.assertIn(("Catupiry (adicional)", 2, 4.0), nomes)
        self.assertIn(("Bacon (adicional)", 2, 4.0), nomes)
        self.assertAlmostEqual(sum(i["subtotal"] for i in itens), 63.80)
        self.assertEqual(avisos, [])

    def test_observacao_do_item_vai_junto(self):
        """A observação do cliente fica no item principal"""
        itens, _ = po.montar_itens(pedido_exemplo(), self.banco)
        principal = next(i for i in itens if i["nome"] == "Los Pastelles")
        self.assertIn("bem passado", principal["observacao"])

    def test_sabor_escolhe_o_produto_do_refrigerante(self):
        """'Refrigerante Lata' sabor Guaraná entra como 'Guarana Antarctica Lata'"""
        itens, _ = po.montar_itens(pedido_exemplo(), self.banco)
        refri = [i for i in itens if "Lata" in i["nome"]]
        self.assertEqual(len(refri), 1)
        self.assertEqual(refri[0]["produto_id"], self.id_de["Guarana Antarctica Lata"])

    def test_apelidos_de_nome(self):
        """Nomes diferentes nos dois sistemas são casados (Explosão de Camarão, caldinho de batata-salsa, 'com' x 'c/')"""
        pedido = pedido_exemplo(itens=[
            {"nome": "Explosão de Camarão", "qtd": 1, "unit": 2590, "escolhas": []},
            {"nome": "Caldinho de Batata-Salsa 500ml", "qtd": 1, "unit": 1990, "escolhas": []},
            {"nome": "CARNE COM QUEIJO", "qtd": 1, "unit": 1690, "escolhas": []},
        ])
        itens, avisos = po.montar_itens(pedido, self.banco)
        self.assertEqual([i["produto_id"] for i in itens],
                         [self.id_de["Pastel de Camarão"], self.id_de["Caldinho de Mandioquinha Salsa"], self.id_de["Carne com Queijo"]])
        self.assertEqual(avisos, [])

    def test_opcao_sem_produto_vai_para_observacao_mantendo_valor(self):
        """Opção paga sem produto (ex: Nutella) vira observação e o valor continua no item"""
        pedido = pedido_exemplo(itens=[{"nome": "Carne com Queijo", "qtd": 1, "unit": 2290, "obs": "",
                                        "escolhas": [{"grupo": "Acompanhamentos", "nome": "Nutella", "n": 1, "preco": 600}]}])
        itens, _ = po.montar_itens(pedido, self.banco)
        self.assertEqual(len(itens), 1)
        self.assertAlmostEqual(itens[0]["valor_unitario"], 22.90)
        self.assertIn("Nutella", itens[0]["observacao"])

    def test_item_sem_produto_entra_marcado(self):
        """Item que não existe no LosManager entra sem produto, marcado com ⚠, e gera aviso"""
        pedido = pedido_exemplo(itens=[{"nome": "S'more", "qtd": 1, "unit": 1890, "escolhas": []}])
        itens, avisos = po.montar_itens(pedido, self.banco)
        self.assertIsNone(itens[0]["produto_id"])
        self.assertTrue(itens[0]["nome"].startswith("⚠"))
        self.assertEqual(len(avisos), 1)


class TesteCliente(BaseComBanco):
    """Cliente achado pelo telefone ou cadastrado, com o endereço da entrega"""

    def test_cadastra_cliente_novo_com_endereco_principal(self):
        """Telefone desconhecido cadastra o cliente com o endereço da entrega como principal"""
        cliente = po.encontrar_ou_criar_cliente(pedido_exemplo(), self.banco)
        self.assertEqual(cliente["nome"], "Ana Souza")
        self.assertEqual(cliente["telefone"], "(12) 99111-2222")
        endereco = self.banco.buscar("SELECT endereco, numero, bairro, cep, principal FROM enderecos_cliente WHERE cliente_id=?", (cliente["id"],))
        self.assertEqual(endereco, [("Rua Emílio Winther", "45 - casa 2", "Jardim das Nações", "12030-000", 1)])

    def test_acha_cliente_existente_pelo_telefone(self):
        """Cliente já cadastrado com o telefone em outro formato é reaproveitado (não duplica)"""
        self.banco.executar("INSERT INTO clientes (nome, telefone) VALUES ('Ana (balcão)', '12 99111.2222')")
        cliente = po.encontrar_ou_criar_cliente(pedido_exemplo(), self.banco)
        self.assertEqual(cliente["nome"], "Ana (balcão)")
        self.assertEqual(self.banco.buscar_um("SELECT COUNT(*) FROM clientes")[0], 1)

    def test_ddd_diferente_nao_confunde(self):
        """Mesmo final de telefone com outro DDD é outro cliente"""
        self.banco.executar("INSERT INTO clientes (nome, telefone) VALUES ('Outra Pessoa', '(11) 99111-2222')")
        cliente = po.encontrar_ou_criar_cliente(pedido_exemplo(), self.banco)
        self.assertEqual(cliente["nome"], "Ana Souza")

    def test_endereco_repetido_nao_duplica_e_vira_principal(self):
        """O mesmo endereço em outro pedido não é cadastrado de novo, e volta a ser o principal"""
        cliente = po.encontrar_ou_criar_cliente(pedido_exemplo(), self.banco)
        self.banco.executar("UPDATE enderecos_cliente SET principal=0")
        self.banco.executar("INSERT INTO enderecos_cliente (cliente_id, endereco, numero, principal) VALUES (?, 'Outra rua', '1', 1)", (cliente["id"],))
        po.encontrar_ou_criar_cliente(pedido_exemplo(), self.banco)
        linhas = self.banco.buscar("SELECT endereco, principal FROM enderecos_cliente WHERE cliente_id=? ORDER BY id", (cliente["id"],))
        self.assertEqual(linhas, [("Rua Emílio Winther", 1), ("Outra rua", 0)])

    def test_retirada_nao_mexe_no_endereco(self):
        """Pedido para retirar não cadastra endereço"""
        po.encontrar_ou_criar_cliente(pedido_exemplo(entrega={"tipo": "retirada"}), self.banco)
        self.assertEqual(self.banco.buscar_um("SELECT COUNT(*) FROM enderecos_cliente")[0], 0)


class TesteRascunho(BaseComBanco):
    """Rascunho pronto para a tela de Pedidos"""

    def test_rascunho_completo(self):
        """Pagamento, taxa de entrega, motoboy em aberto e observação com troco e referência"""
        estado, _ = po.montar_rascunho(pedido_exemplo(), self.banco)
        self.assertEqual(estado["pagamento"], "Dinheiro")
        self.assertEqual(estado["valor_entrega"], "9,00")
        self.assertEqual(estado["motoboy"], po.SEM_MOTOBOY)
        self.assertAlmostEqual(estado["total"], 63.80)
        obs = estado["pedido_online"]["observacao"]
        self.assertIn("Cardápio online #7", obs)
        self.assertIn("Troco p/ R$ 100,00", obs)
        self.assertIn("portão azul", obs)
        self.assertIn("tocar interfone", obs)
        self.assertEqual(estado["pedido_online"]["id"], 7)

    def test_retirada_ja_marca_retirada(self):
        """Pedido para retirar já vem com 'Retirada (sem motoboy)' e sem taxa"""
        estado, _ = po.montar_rascunho(pedido_exemplo(entrega={"tipo": "retirada"}, taxa=0, pagamento={"forma": "pix"}), self.banco)
        self.assertEqual(estado["motoboy"], po.RETIRADA)
        self.assertEqual(estado["valor_entrega"], "")
        self.assertEqual(estado["pagamento"], "PIX")

    def test_taxa_a_combinar_avisa_na_observacao(self):
        """Entrega com taxa a combinar aparece na observação do cupom"""
        p = pedido_exemplo(taxa=0)
        p["entrega"]["combinar"] = True
        estado, _ = po.montar_rascunho(p, self.banco)
        self.assertIn("a combinar", estado["pedido_online"]["observacao"])

    def test_ja_lancado(self):
        """Pedido online já gravado (e não cancelado) é reconhecido; cancelado libera de novo"""
        self.assertIsNone(po.ja_lancado(7, self.banco))
        self.banco.executar("INSERT INTO pedidos (numero, status, pedido_online_id) VALUES (57, 'Finalizado', 7)")
        self.assertEqual(po.ja_lancado(7, self.banco), 57)
        self.banco.executar("UPDATE pedidos SET status='Cancelado' WHERE pedido_online_id=7")
        self.assertIsNone(po.ja_lancado(7, self.banco))

    def test_pedido_sem_itens(self):
        """Pedido online sem itens não é lançado"""
        with self.assertRaises(po.PedidoOnlineInvalido):
            po.montar_rascunho(pedido_exemplo(itens=[]), self.banco)


if __name__ == "__main__":
    unittest.main()
