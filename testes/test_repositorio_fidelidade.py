"""
Testes do repositório do Programa de Fidelidade
(repositorios/fidelidade.py). Cada teste abre um banco SQLite
":memory:" isolado — não toca no losmanager.db real e não precisa de
nenhuma janela CustomTkinter.

Rodar com:
    python -m testes
"""

import unittest
from datetime import date, timedelta

from database.conexao import Banco
from repositorios import fidelidade as repositorio_fidelidade


class TesteBase(unittest.TestCase):
    """Base comum: banco novo por teste + helper pra criar cliente."""

    def setUp(self):
        self.banco = Banco(":memory:")
        # Cada chamada padrão de criar_pedido() sem `data` explícita
        # pega o próximo dia desta sequência — garante que pedidos
        # "normais" de um teste caem em dias diferentes (a regra de 1
        # ponto por dia é testada à parte, passando `data` igual de
        # propósito).
        self._proximo_dia = 0

    def _proxima_data(self):

        dia = date(2026, 1, 1) + timedelta(days=self._proximo_dia)
        self._proximo_dia += 1

        return dia.strftime("%d/%m/%Y")

    def criar_cliente(self, nome="Cliente Teste", telefone="99999-0000"):

        self.banco.executar(
            "INSERT INTO clientes(nome, telefone) VALUES(?, ?)",
            (nome, telefone)
        )
        return self.banco.ultimo_id()

    def criar_pedido(self, numero=1, data=None):

        if data is None:
            data = self._proxima_data()

        self.banco.executar(
            "INSERT INTO pedidos(numero, status, data) VALUES(?, 'Finalizado', ?)",
            (numero, data)
        )
        return self.banco.ultimo_id()

    def concluir_pedidos(self, cliente_id, quantidade, numero_inicial=1):
        """Registra `quantidade` pedidos concluídos seguidos pro
        cliente, cada um num dia diferente, retornando a lista de
        pedido_ids gerados."""

        ids = []

        for numero in range(numero_inicial, numero_inicial + quantidade):
            pedido_id = self.criar_pedido(numero)
            repositorio_fidelidade.registrar_pedido_concluido(cliente_id, pedido_id, banco=self.banco)
            ids.append(pedido_id)

        return ids


class TestePontuacao(TesteBase):
    """Pontuação por pedido concluído e geração automática de recompensa"""

    def test_pedido_concluido_soma_um_ponto(self):
        """1 pedido concluído soma 1 ponto de fidelidade"""
        cliente_id = self.criar_cliente()
        pedido_id = self.criar_pedido()

        resultado = repositorio_fidelidade.registrar_pedido_concluido(cliente_id, pedido_id, banco=self.banco)

        self.assertEqual(resultado["total_pedidos"], 1)
        self.assertFalse(resultado["nova_recompensa"])

    def test_cliente_balcao_nao_participa(self):
        """Pedido sem cliente (Cliente Balcão) não gera ponto de fidelidade"""
        pedido_id = self.criar_pedido()

        resultado = repositorio_fidelidade.registrar_pedido_concluido(None, pedido_id, banco=self.banco)

        self.assertEqual(resultado["total_pedidos"], 0)
        self.assertFalse(resultado["nova_recompensa"])

    def test_decimo_pedido_gera_recompensa(self):
        """O 10º pedido concluído (meta padrão) gera 1 recompensa disponível"""
        cliente_id = self.criar_cliente()

        self.concluir_pedidos(cliente_id, 9)
        decimo_pedido_id = self.criar_pedido(99)
        resultado = repositorio_fidelidade.registrar_pedido_concluido(
            cliente_id, decimo_pedido_id, banco=self.banco
        )

        self.assertTrue(resultado["nova_recompensa"])
        self.assertEqual(resultado["recompensas_geradas"], 1)

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["recompensas_disponiveis"], 1)
        self.assertEqual(status["total_pedidos"], 10)

    def test_vigesimo_pedido_gera_segunda_recompensa(self):
        """20 pedidos concluídos (2x a meta) dão 2 recompensas disponíveis, cumulativo"""
        cliente_id = self.criar_cliente()
        self.concluir_pedidos(cliente_id, 20)

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["recompensas_disponiveis"], 2)

    def test_registrar_duas_vezes_o_mesmo_pedido_nao_duplica_ponto(self):
        """Chamar registrar_pedido_concluido duas vezes pro mesmo pedido não soma ponto duplicado"""
        cliente_id = self.criar_cliente()
        pedido_id = self.criar_pedido()

        repositorio_fidelidade.registrar_pedido_concluido(cliente_id, pedido_id, banco=self.banco)
        repositorio_fidelidade.registrar_pedido_concluido(cliente_id, pedido_id, banco=self.banco)

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["total_pedidos"], 1)

    def test_faltam_para_proxima_recompensa(self):
        """'faltam' calcula corretamente quantos pedidos faltam pro próximo múltiplo da meta"""
        cliente_id = self.criar_cliente()
        self.concluir_pedidos(cliente_id, 7)

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["faltam"], 3)


class TesteUmPontoPorDia(TesteBase):
    """Vários pedidos do mesmo cliente no mesmo dia contam como 1 só"""

    def test_tres_pedidos_no_mesmo_dia_somam_um_ponto_so(self):
        """Pastel + doce + refrigerante no mesmo dia contam 1 pedido de fidelidade, não 3"""
        cliente_id = self.criar_cliente()
        hoje = "10/03/2026"

        pastel_id = self.criar_pedido(1, data=hoje)
        doce_id = self.criar_pedido(2, data=hoje)
        refrigerante_id = self.criar_pedido(3, data=hoje)

        repositorio_fidelidade.registrar_pedido_concluido(cliente_id, pastel_id, banco=self.banco)
        repositorio_fidelidade.registrar_pedido_concluido(cliente_id, doce_id, banco=self.banco)
        resultado = repositorio_fidelidade.registrar_pedido_concluido(cliente_id, refrigerante_id, banco=self.banco)

        self.assertEqual(resultado["total_pedidos"], 1)

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["total_pedidos"], 1)

    def test_pedido_em_outro_dia_soma_ponto_novo(self):
        """Um pedido em outro dia já soma um 2º ponto normalmente"""
        cliente_id = self.criar_cliente()

        pedido_hoje = self.criar_pedido(1, data="10/03/2026")
        pedido_amanha = self.criar_pedido(2, data="11/03/2026")

        repositorio_fidelidade.registrar_pedido_concluido(cliente_id, pedido_hoje, banco=self.banco)
        repositorio_fidelidade.registrar_pedido_concluido(cliente_id, pedido_amanha, banco=self.banco)

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["total_pedidos"], 2)

    def test_historico_guarda_cada_pedido_do_dia_mesmo_sem_somar_ponto(self):
        """O 2º/3º pedido do mesmo dia ainda aparece no histórico, só não soma ponto"""
        cliente_id = self.criar_cliente()
        hoje = "10/03/2026"

        self.criar_pedido(1, data=hoje)
        pedido_id_1 = self.banco.ultimo_id()
        repositorio_fidelidade.registrar_pedido_concluido(cliente_id, pedido_id_1, banco=self.banco)

        pedido_id_2 = self.criar_pedido(2, data=hoje)
        repositorio_fidelidade.registrar_pedido_concluido(cliente_id, pedido_id_2, banco=self.banco)

        historico = repositorio_fidelidade.historico_cliente(cliente_id, banco=self.banco)
        self.assertEqual(len(historico), 2)

    def test_cancelar_o_pedido_do_dia_promove_outro_pedido_do_mesmo_dia(self):
        """Cancelar o pedido que tinha contado no dia não derruba o ponto se sobrar outro do mesmo dia"""
        cliente_id = self.criar_cliente()
        hoje = "10/03/2026"

        primeiro_id = self.criar_pedido(1, data=hoje)
        repositorio_fidelidade.registrar_pedido_concluido(cliente_id, primeiro_id, banco=self.banco)

        segundo_id = self.criar_pedido(2, data=hoje)
        repositorio_fidelidade.registrar_pedido_concluido(cliente_id, segundo_id, banco=self.banco)

        # Cancela o pedido que tinha contado — o outro do mesmo dia
        # assume o lugar dele automaticamente.
        repositorio_fidelidade.estornar_pedido_concluido(primeiro_id, banco=self.banco)

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["total_pedidos"], 1)


class TesteCancelamento(TesteBase):
    """Estorno de ponto ao cancelar pedido e reversão ao desfazer o cancelamento"""

    def test_cancelar_pedido_estorna_ponto(self):
        """Cancelar um pedido concluído tira o ponto que ele tinha gerado"""
        cliente_id = self.criar_cliente()
        ids = self.concluir_pedidos(cliente_id, 3)

        repositorio_fidelidade.estornar_pedido_concluido(ids[0], banco=self.banco)

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["total_pedidos"], 2)

    def test_cancelar_pedido_que_completou_meta_retira_recompensa_nao_resgatada(self):
        """Cancelar o pedido que tinha completado a meta remove a recompensa ainda não resgatada"""
        cliente_id = self.criar_cliente()
        ids = self.concluir_pedidos(cliente_id, 10)

        repositorio_fidelidade.estornar_pedido_concluido(ids[-1], banco=self.banco)

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["total_pedidos"], 9)
        self.assertEqual(status["recompensas_disponiveis"], 0)

    def test_reverter_estorno_devolve_ponto(self):
        """Reverter o cancelamento devolve o ponto de fidelidade"""
        cliente_id = self.criar_cliente()
        ids = self.concluir_pedidos(cliente_id, 3)

        repositorio_fidelidade.estornar_pedido_concluido(ids[0], banco=self.banco)
        repositorio_fidelidade.reverter_estorno_pedido(ids[0], banco=self.banco)

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["total_pedidos"], 3)

    def test_estornar_pedido_de_cliente_balcao_nao_faz_nada(self):
        """Cancelar um pedido sem cliente (Cliente Balcão) não gera erro nem efeito"""
        pedido_id = self.criar_pedido()
        repositorio_fidelidade.registrar_pedido_concluido(None, pedido_id, banco=self.banco)

        # Não deve levantar exceção
        repositorio_fidelidade.estornar_pedido_concluido(pedido_id, banco=self.banco)


class TesteResgate(TesteBase):
    """Resgate de recompensa disponível"""

    def test_resgatar_recompensa_disponivel_decrementa_saldo(self):
        """Resgatar 1 recompensa disponível diminui o saldo em 1"""
        cliente_id = self.criar_cliente()
        self.concluir_pedidos(cliente_id, 10)

        repositorio_fidelidade.resgatar_recompensa(cliente_id, usuario="Caixa", banco=self.banco)

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["recompensas_disponiveis"], 0)

    def test_resgatar_sem_saldo_levanta_erro(self):
        """Tentar resgatar sem nenhuma recompensa disponível levanta FidelidadeInvalida"""
        cliente_id = self.criar_cliente()

        with self.assertRaises(repositorio_fidelidade.FidelidadeInvalida):
            repositorio_fidelidade.resgatar_recompensa(cliente_id, usuario="Caixa", banco=self.banco)

    def test_resgatar_sem_usuario_levanta_erro(self):
        """Resgatar sem informar quem autorizou levanta FidelidadeInvalida"""
        cliente_id = self.criar_cliente()
        self.concluir_pedidos(cliente_id, 10)

        with self.assertRaises(repositorio_fidelidade.FidelidadeInvalida):
            repositorio_fidelidade.resgatar_recompensa(cliente_id, usuario="   ", banco=self.banco)

    def test_resgate_fica_no_historico_mesmo_apos_resgatado(self):
        """O histórico de fidelidade não é apagado depois de um resgate"""
        cliente_id = self.criar_cliente()
        self.concluir_pedidos(cliente_id, 10)
        repositorio_fidelidade.resgatar_recompensa(cliente_id, usuario="Caixa", banco=self.banco)

        historico = repositorio_fidelidade.historico_cliente(cliente_id, banco=self.banco)
        tipos = [linha[0] for linha in historico]

        self.assertIn(repositorio_fidelidade.TIPO_RECOMPENSA_RESGATADA, tipos)
        # 10 x PEDIDO_CONCLUIDO + 1 RECOMPENSA_GERADA (no 10º) + 1 RECOMPENSA_RESGATADA
        self.assertEqual(len(historico), 12)


class TesteAjusteManual(TesteBase):
    """Ajuste manual de pontuação/recompensa"""

    def test_ajuste_manual_adiciona_pedidos(self):
        """Ajuste manual pode adicionar pedidos (ex: cartão fidelidade físico)"""
        cliente_id = self.criar_cliente()

        repositorio_fidelidade.ajuste_manual(
            cliente_id, repositorio_fidelidade.ALVO_PEDIDOS, 5,
            "Cliente apresentou cartão fidelidade físico", "Ramon",
            banco=self.banco
        )

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["total_pedidos"], 5)

    def test_ajuste_manual_remove_pedidos_sem_ficar_negativo(self):
        """Ajuste manual negativo não deixa o total de pedidos ficar abaixo de zero"""
        cliente_id = self.criar_cliente()
        self.concluir_pedidos(cliente_id, 2)

        repositorio_fidelidade.ajuste_manual(
            cliente_id, repositorio_fidelidade.ALVO_PEDIDOS, -10,
            "Correção", "Ramon", banco=self.banco
        )

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["total_pedidos"], 0)

    def test_ajuste_manual_adiciona_recompensa(self):
        """Ajuste manual pode adicionar 1 recompensa diretamente"""
        cliente_id = self.criar_cliente()

        repositorio_fidelidade.ajuste_manual(
            cliente_id, repositorio_fidelidade.ALVO_RECOMPENSAS, 1,
            "Cortesia da casa", "Ramon", banco=self.banco
        )

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["recompensas_disponiveis"], 1)

    def test_ajuste_manual_sem_justificativa_levanta_erro(self):
        """Ajuste manual sem justificativa é rejeitado"""
        cliente_id = self.criar_cliente()

        with self.assertRaises(repositorio_fidelidade.FidelidadeInvalida):
            repositorio_fidelidade.ajuste_manual(
                cliente_id, repositorio_fidelidade.ALVO_PEDIDOS, 1, "", "Ramon",
                banco=self.banco
            )

    def test_ajuste_manual_com_quantidade_zero_levanta_erro(self):
        """Ajuste manual com quantidade zero é rejeitado"""
        cliente_id = self.criar_cliente()

        with self.assertRaises(repositorio_fidelidade.FidelidadeInvalida):
            repositorio_fidelidade.ajuste_manual(
                cliente_id, repositorio_fidelidade.ALVO_PEDIDOS, 0, "Motivo", "Ramon",
                banco=self.banco
            )


class TesteListagemEResumos(TesteBase):
    """Tabela de participantes e resumos do Dashboard/Relatórios"""

    def test_listar_participantes_bate_com_exemplo_do_pedido(self):
        """listar_participantes calcula faltam/status igual ao exemplo (João 7/3, Maria 10/0/1, Carlos 23/7/2)"""

        joao = self.criar_cliente("João", "99999-9999")
        maria = self.criar_cliente("Maria", "98888-8888")
        carlos = self.criar_cliente("Carlos", "97777-7777")

        self.concluir_pedidos(joao, 7, numero_inicial=1)
        self.concluir_pedidos(maria, 10, numero_inicial=100)
        self.concluir_pedidos(carlos, 23, numero_inicial=200)

        participantes = {
            linha[1]: linha for linha in repositorio_fidelidade.listar_participantes(banco=self.banco)
        }

        # (cliente_id, nome, telefone, total_pedidos, faltam, recompensas, status)
        self.assertEqual(participantes["João"][3:], (7, 3, 0, "Em andamento"))
        self.assertEqual(participantes["Maria"][3:], (10, 0, 1, "🎁 Prêmio disponível"))
        self.assertEqual(participantes["Carlos"][3:], (23, 7, 2, "🎁 2 prêmios"))

    def test_listar_participantes_filtra_por_termo(self):
        """listar_participantes filtra por nome/telefone ignorando maiúscula e acento"""
        self.concluir_pedidos(self.criar_cliente("José", "91111-1111"), 1)
        self.concluir_pedidos(self.criar_cliente("Ana", "92222-2222"), 1)

        resultado = repositorio_fidelidade.listar_participantes("jose", banco=self.banco)

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0][1], "José")

    def test_resumo_dashboard_lista_clientes_proximos(self):
        """resumo_dashboard traz os clientes mais próximos da próxima recompensa, ordenados"""
        cliente_longe = self.criar_cliente("Longe")
        cliente_perto = self.criar_cliente("Perto")

        self.concluir_pedidos(cliente_longe, 2, numero_inicial=1)
        self.concluir_pedidos(cliente_perto, 9, numero_inicial=100)

        resumo = repositorio_fidelidade.resumo_dashboard(banco=self.banco)

        nomes_em_ordem = [nome for nome, _total, _faltam in resumo["proximos"]]
        self.assertEqual(nomes_em_ordem[0], "Perto")
        self.assertEqual(resumo["clientes_participantes"], 2)

    def test_resumo_relatorio_contabiliza_totais_e_ranking(self):
        """resumo_relatorio soma pedidos/recompensas geradas/resgatadas e monta o ranking"""
        cliente_id = self.criar_cliente("Fiel")
        self.concluir_pedidos(cliente_id, 10)
        repositorio_fidelidade.resgatar_recompensa(cliente_id, usuario="Caixa", banco=self.banco)

        resumo = repositorio_fidelidade.resumo_relatorio(banco=self.banco)

        self.assertEqual(resumo["clientes_participantes"], 1)
        self.assertEqual(resumo["pedidos_contabilizados"], 10)
        self.assertEqual(resumo["recompensas_geradas"], 1)
        self.assertEqual(resumo["recompensas_resgatadas"], 1)
        self.assertEqual(resumo["recompensas_disponiveis"], 0)
        self.assertEqual(resumo["ranking"][0][0], "Fiel")


class TesteConfiguracaoDaMeta(TesteBase):
    """A meta de pedidos por recompensa é configurável (regra 8)"""

    def test_meta_customizada_muda_quando_a_recompensa_e_gerada(self):
        """Com a meta configurada pra 5, a recompensa nasce no 5º pedido, não no 10º"""
        # A tabela `configuracoes` só existe depois da 1ª leitura de
        # `_obter_meta` (ver repositorios/fidelidade.py) — força a
        # criação antes de inserir o valor customizado.
        self.banco.executar(
            "CREATE TABLE IF NOT EXISTS configuracoes(chave TEXT PRIMARY KEY, valor TEXT)"
        )
        self.banco.executar(
            "INSERT INTO configuracoes(chave, valor) VALUES('fidelidade_meta_pedidos', '5')"
        )

        cliente_id = self.criar_cliente()
        self.concluir_pedidos(cliente_id, 5)

        status = repositorio_fidelidade.obter_status_cliente(cliente_id, banco=self.banco)
        self.assertEqual(status["recompensas_disponiveis"], 1)


if __name__ == "__main__":
    unittest.main()
