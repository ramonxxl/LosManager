"""
=================================================================
PROGRAMA DE FIDELIDADE — pontuação por pedido, recompensas e
histórico
=================================================================
Segue o mesmo padrão de `repositorios/motoboys.py`/`produtos.py`:
nenhum import de GUI aqui, e toda função recebe `banco` opcional
(resolvido via `conexao.banco`, lido na hora da chamada — ver a
explicação completa em `repositorios/produtos.py`).

Diferença importante em relação aos outros repositórios: nenhuma
função aqui dá commit/rollback sozinha (todas usam
`executar_sem_commit`). Fidelidade quase sempre participa da
transação de outra tela (pedido criado, cancelado ou revertido —
regra 12 do pedido original: "tudo deve acontecer dentro de uma
transação"), então quem chama é quem decide quando dar
`banco.commit()` ou `banco.rollback()` — igual ao padrão já usado por
`Relatorios.devolver_estoque_pedido()`/`reconsumir_estoque_pedido()`.

Modelo de dados (ver `database/conexao.py`):

- `fidelidade`: um cache por cliente (total_pedidos,
  recompensas_disponiveis) — sempre RECALCULADO do zero a partir de
  `historico_fidelidade` (nunca incrementado direto), pra nunca
  desalinhar do histórico real.

- `historico_fidelidade`: fonte da verdade, nunca apagada (nem no
  resgate). Cada linha tem `tipo` (PEDIDO_CONCLUIDO / RECOMPENSA_GERADA
  / RECOMPENSA_RESGATADA / AJUSTE_MANUAL), `alvo` ('pedidos' ou
  'recompensas' — o que a linha afeta) e `quantidade` (inteiro, pode
  ser negativo num AJUSTE_MANUAL de remoção). Um `pedido_id` só pode
  ter UMA linha PEDIDO_CONCLUIDO pra sempre — garantido por um índice
  único parcial no banco (ver `_criar_tabelas_fidelidade`), então
  registrar o mesmo pedido duas vezes não duplica ponto. A `data`
  gravada nessa linha é a do PRÓPRIO PEDIDO (`pedidos.data`), não a de
  quando o ponto foi registrado — importa pra regra abaixo, e pra a
  migração retroativa (`database/conexao.py`) não jogar todo o
  histórico antigo pro dia em que ela rodou.

Regra de 1 ponto por dia: pedidos do MESMO cliente no MESMO dia não
somam pontos separados — um cliente que compra pastel, depois doce,
depois refrigerante no mesmo dia conta como 1 pedido de fidelidade, não
3. Por isso `total_pedidos` conta DIAS DISTINTOS com pelo menos 1
pedido válido, não pedidos individuais — ver fórmula abaixo. Cada
pedido do dia ainda ganha sua própria linha em `historico_fidelidade`
(útil pro histórico/auditoria e pra "promover" outro pedido do mesmo
dia automaticamente se o que tinha contado for cancelado — ver
`estornar_pedido_concluido`), só não move `total_pedidos` sozinho.

Fórmula (sempre recomputada — nunca um contador incremental solto):

    total_pedidos = COUNT(DISTINCT data) de linhas PEDIDO_CONCLUIDO
                    não estornadas
                    + SUM(quantidade) de linhas AJUSTE_MANUAL
                      alvo='pedidos'
                    nunca menor que 0

    recompensas_disponiveis = max(0,
        (total_pedidos // META)              # geradas automaticamente
        + SUM(AJUSTE_MANUAL alvo='recompensas')
        - SUM(RECOMPENSA_RESGATADA)
    )

RECOMPENSA_GERADA é só um registro informativo no histórico (marca
quando uma recompensa nasceu) — não entra nessa conta, pra não contar
em dobro com o `// META`.
=================================================================
"""

from datetime import datetime

from database import conexao
from utils import busca


TIPO_PEDIDO_CONCLUIDO = "PEDIDO_CONCLUIDO"
TIPO_RECOMPENSA_GERADA = "RECOMPENSA_GERADA"
TIPO_RECOMPENSA_RESGATADA = "RECOMPENSA_RESGATADA"
TIPO_AJUSTE_MANUAL = "AJUSTE_MANUAL"

ALVO_PEDIDOS = "pedidos"
ALVO_RECOMPENSAS = "recompensas"


class FidelidadeInvalida(Exception):
    """Erro de validação — a mensagem já vem pronta pra mostrar ao
    usuário."""


# ==========================================================
# INTERNO
# ==========================================================

def _agora():

    agora = datetime.now()
    return agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M")


def _obter_meta(banco):
    """Lê `fidelidade_meta_pedidos` direto do MESMO banco recebido por
    quem chamou — não usa `utils/config.py` porque aquele módulo fixa
    sua própria referência de banco no momento do import (`from
    database.conexao import banco`, e não o padrão `conexao.banco` de
    live-lookup usado no resto de `repositorios/`), o que impediria um
    teste com `Banco(":memory:")` de controlar a meta. Garante a
    tabela `configuracoes` (criada só sob demanda por `utils/config.py`
    em produção) pra funcionar também num banco de teste novo."""

    banco.executar_sem_commit(
        "CREATE TABLE IF NOT EXISTS configuracoes(chave TEXT PRIMARY KEY, valor TEXT)"
    )

    resultado = banco.buscar_um(
        "SELECT valor FROM configuracoes WHERE chave='fidelidade_meta_pedidos'"
    )

    if resultado is not None and resultado[0]:
        try:
            meta = int(resultado[0])
            if meta > 0:
                return meta
        except (TypeError, ValueError):
            pass

    return 10


def _data_hora_pedido(banco, pedido_id):
    """Data/hora do PRÓPRIO pedido (`pedidos.data`/`pedidos.hora`), não
    "agora" — a regra de 1 ponto por dia (ver docstring do módulo)
    precisa agrupar pelo dia em que o pedido foi feito, não pelo dia em
    que ele foi registrado na fidelidade (na migração retroativa isso
    seria sempre "hoje", muito depois do pedido de verdade). Sem
    pedido_id, ou pedido sem data gravada, cai em `_agora()`."""

    if pedido_id is not None:

        linha = banco.buscar_um("SELECT data, hora FROM pedidos WHERE id=?", (pedido_id,))

        if linha and linha[0]:
            return linha[0], linha[1] or ""

    return _agora()


def _inserir_historico(banco, cliente_id, pedido_id, tipo, alvo, quantidade, observacao="", usuario="", data_hora=None):

    data_str, hora_str = data_hora if data_hora else _agora()

    banco.executar_sem_commit(
        """
        INSERT INTO historico_fidelidade
            (cliente_id, pedido_id, tipo, alvo, quantidade, data, hora, observacao, usuario)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (cliente_id, pedido_id, tipo, alvo, quantidade, data_str, hora_str, observacao, usuario)
    )


def _calcular_total_pedidos(banco, cliente_id):
    """Conta DIAS distintos com pelo menos 1 pedido válido, não
    pedidos individuais — vários pedidos do mesmo cliente no mesmo dia
    somam só 1. Cancelar um deles não derruba o dia enquanto sobrar
    outro pedido daquele dia ainda não estornado ("promoção"
    automática, de graça, só por isso ser um COUNT(DISTINCT ...) em vez
    de um contador manual)."""

    dias_com_pedido = banco.buscar_um(
        """
        SELECT COUNT(DISTINCT data)
        FROM historico_fidelidade
        WHERE cliente_id=? AND alvo=? AND tipo=? AND estornado=0
        """,
        (cliente_id, ALVO_PEDIDOS, TIPO_PEDIDO_CONCLUIDO)
    )[0]

    ajuste = banco.buscar_um(
        """
        SELECT COALESCE(SUM(quantidade), 0)
        FROM historico_fidelidade
        WHERE cliente_id=? AND alvo=? AND tipo=?
        """,
        (cliente_id, ALVO_PEDIDOS, TIPO_AJUSTE_MANUAL)
    )[0]

    return max(0, dias_com_pedido + ajuste)


def _calcular_recompensas_disponiveis(banco, cliente_id, total_pedidos):

    meta = _obter_meta(banco)
    geradas_automaticas = total_pedidos // meta

    ajuste = banco.buscar_um(
        """
        SELECT COALESCE(SUM(quantidade), 0)
        FROM historico_fidelidade
        WHERE cliente_id=? AND alvo=? AND tipo=?
        """,
        (cliente_id, ALVO_RECOMPENSAS, TIPO_AJUSTE_MANUAL)
    )[0]

    resgatadas = banco.buscar_um(
        "SELECT COALESCE(SUM(quantidade), 0) FROM historico_fidelidade WHERE cliente_id=? AND tipo=?",
        (cliente_id, TIPO_RECOMPENSA_RESGATADA)
    )[0]

    return max(0, geradas_automaticas + ajuste - resgatadas)


def _calcular_faltam(banco, total_pedidos):

    meta = _obter_meta(banco)
    resto = total_pedidos % meta

    return 0 if resto == 0 else meta - resto


def _status(total_pedidos, recompensas_disponiveis):

    if recompensas_disponiveis > 0:
        return "🎁 Prêmio disponível" if recompensas_disponiveis == 1 else f"🎁 {recompensas_disponiveis} prêmios"

    if total_pedidos > 0:
        return "Em andamento"

    return "Novo"


def _recalcular(banco, cliente_id):
    """Recomputa total_pedidos/recompensas_disponiveis do zero a
    partir do histórico e grava o cache em `fidelidade`. Retorna o
    registro atualizado."""

    total_pedidos = _calcular_total_pedidos(banco, cliente_id)
    recompensas_disponiveis = _calcular_recompensas_disponiveis(banco, cliente_id, total_pedidos)

    data_str, hora_str = _agora()
    agora_str = f"{data_str} {hora_str}"

    existente = banco.buscar_um("SELECT id FROM fidelidade WHERE cliente_id=?", (cliente_id,))

    if existente is None:
        banco.executar_sem_commit(
            """
            INSERT INTO fidelidade
                (cliente_id, total_pedidos, recompensas_disponiveis, data_criacao, data_atualizacao)
            VALUES (?, ?, ?, ?, ?)
            """,
            (cliente_id, total_pedidos, recompensas_disponiveis, agora_str, agora_str)
        )
    else:
        banco.executar_sem_commit(
            """
            UPDATE fidelidade
            SET total_pedidos=?, recompensas_disponiveis=?, data_atualizacao=?
            WHERE cliente_id=?
            """,
            (total_pedidos, recompensas_disponiveis, agora_str, cliente_id)
        )

    return {
        "cliente_id": cliente_id,
        "total_pedidos": total_pedidos,
        "recompensas_disponiveis": recompensas_disponiveis
    }


# ==========================================================
# PEDIDO CONCLUÍDO (chamado de dentro de Pedidos.gravar_pedido)
# ==========================================================

def registrar_pedido_concluido(cliente_id, pedido_id, banco=None):
    """Registra o ponto de fidelidade de 1 pedido recém-finalizado.
    Cliente Balcão (cliente_id None) não participa — não faz nada.
    Idempotente: chamar de novo para o mesmo pedido_id não duplica (o
    índice único de `historico_fidelidade` garante isso mesmo numa
    corrida). Retorna um dict com `nova_recompensa` (bool) e
    `recompensas_geradas`, pra Pedidos avisar quando o cliente acabou
    de bater a meta."""

    banco = banco or conexao.banco

    if cliente_id is None:
        return {"nova_recompensa": False, "recompensas_geradas": 0,
                "cliente_id": None, "total_pedidos": 0, "recompensas_disponiveis": 0}

    ja_registrado = banco.buscar_um(
        "SELECT id FROM historico_fidelidade WHERE pedido_id=? AND tipo=?",
        (pedido_id, TIPO_PEDIDO_CONCLUIDO)
    )

    if ja_registrado is not None:
        total_pedidos = _calcular_total_pedidos(banco, cliente_id)
        recompensas_disponiveis = _calcular_recompensas_disponiveis(banco, cliente_id, total_pedidos)
        return {"nova_recompensa": False, "recompensas_geradas": 0, "cliente_id": cliente_id,
                "total_pedidos": total_pedidos, "recompensas_disponiveis": recompensas_disponiveis}

    recompensas_antes = _calcular_recompensas_disponiveis(
        banco, cliente_id, _calcular_total_pedidos(banco, cliente_id)
    )

    # A data usada é a do PRÓPRIO pedido (não "agora") — é o que faz o
    # COUNT(DISTINCT data) de _calcular_total_pedidos agrupar certo,
    # inclusive na migração retroativa (ver database/conexao.py).
    data_hora_pedido = _data_hora_pedido(banco, pedido_id)
    data_pedido = data_hora_pedido[0]

    # Cliente já tem outro pedido válido no mesmo dia? Esse aqui ainda
    # entra no histórico (auditoria, e pra poder "promover" sozinho se
    # o outro for cancelado depois), só não soma um 2º ponto no mesmo
    # dia — regra: pastel + doce + refrigerante no mesmo dia = 1 pedido
    # de fidelidade, não 3.
    ja_tinha_pedido_no_dia = banco.buscar_um(
        """
        SELECT COUNT(*) FROM historico_fidelidade
        WHERE cliente_id=? AND tipo=? AND data=? AND estornado=0
        """,
        (cliente_id, TIPO_PEDIDO_CONCLUIDO, data_pedido)
    )[0] > 0

    observacao = (
        "Cliente já tinha um pedido nesse dia — não soma ponto adicional"
        if ja_tinha_pedido_no_dia else ""
    )

    _inserir_historico(
        banco, cliente_id, pedido_id, TIPO_PEDIDO_CONCLUIDO, ALVO_PEDIDOS, 1,
        observacao=observacao, data_hora=data_hora_pedido
    )

    registro = _recalcular(banco, cliente_id)

    geradas = registro["recompensas_disponiveis"] - recompensas_antes

    if geradas > 0:
        _inserir_historico(
            banco, cliente_id, pedido_id, TIPO_RECOMPENSA_GERADA, ALVO_RECOMPENSAS, geradas,
            observacao=f"Meta de {_obter_meta(banco)} pedidos atingida",
            data_hora=data_hora_pedido
        )

    return {"nova_recompensa": geradas > 0, "recompensas_geradas": geradas, **registro}


# ==========================================================
# CANCELAMENTO / REVERSÃO (chamado de Relatorios)
# ==========================================================

def estornar_pedido_concluido(pedido_id, banco=None):
    """Estorna o ponto de fidelidade de um pedido cancelado — pedido
    cancelado não conta pra fidelidade (regra 3). Sem efeito se o
    pedido nunca gerou ponto (Cliente Balcão) ou já estava estornado."""

    banco = banco or conexao.banco

    linha = banco.buscar_um(
        "SELECT cliente_id FROM historico_fidelidade WHERE pedido_id=? AND tipo=? AND estornado=0",
        (pedido_id, TIPO_PEDIDO_CONCLUIDO)
    )

    if linha is None:
        return

    cliente_id = linha[0]

    banco.executar_sem_commit(
        "UPDATE historico_fidelidade SET estornado=1 WHERE pedido_id=? AND tipo=?",
        (pedido_id, TIPO_PEDIDO_CONCLUIDO)
    )

    _recalcular(banco, cliente_id)


def reverter_estorno_pedido(pedido_id, banco=None):
    """Desfaz `estornar_pedido_concluido` — devolve o ponto de
    fidelidade (e, se fizer sentido, a recompensa que ele completava)
    quando um cancelamento é revertido."""

    banco = banco or conexao.banco

    linha = banco.buscar_um(
        "SELECT cliente_id FROM historico_fidelidade WHERE pedido_id=? AND tipo=? AND estornado=1",
        (pedido_id, TIPO_PEDIDO_CONCLUIDO)
    )

    if linha is None:
        return

    cliente_id = linha[0]

    recompensas_antes = _calcular_recompensas_disponiveis(
        banco, cliente_id, _calcular_total_pedidos(banco, cliente_id)
    )

    banco.executar_sem_commit(
        "UPDATE historico_fidelidade SET estornado=0 WHERE pedido_id=? AND tipo=?",
        (pedido_id, TIPO_PEDIDO_CONCLUIDO)
    )

    registro = _recalcular(banco, cliente_id)

    geradas = registro["recompensas_disponiveis"] - recompensas_antes

    if geradas > 0:
        _inserir_historico(
            banco, cliente_id, pedido_id, TIPO_RECOMPENSA_GERADA, ALVO_RECOMPENSAS, geradas,
            observacao="Recompensa restabelecida (cancelamento revertido)",
            data_hora=_data_hora_pedido(banco, pedido_id)
        )


# ==========================================================
# CONSULTA (tela de Pedidos e tela de Fidelidade)
# ==========================================================

def obter_status_cliente(cliente_id, banco=None):
    """Status de fidelidade de 1 cliente — usado no banner de Pedidos.
    Cliente Balcão ou cliente sem nenhum pedido de fidelidade ainda
    retorna zerado."""

    banco = banco or conexao.banco

    if cliente_id is None:
        return {"total_pedidos": 0, "recompensas_disponiveis": 0, "faltam": _obter_meta(banco)}

    registro = banco.buscar_um(
        "SELECT total_pedidos, recompensas_disponiveis FROM fidelidade WHERE cliente_id=?",
        (cliente_id,)
    )

    total_pedidos, recompensas_disponiveis = registro if registro else (0, 0)

    return {
        "total_pedidos": total_pedidos,
        "recompensas_disponiveis": recompensas_disponiveis,
        "faltam": _calcular_faltam(banco, total_pedidos)
    }


def listar_participantes(termo="", banco=None):
    """Uma linha por cliente participante (já com pelo menos 1 pedido
    de fidelidade) para a tabela da tela de Fidelidade: (cliente_id,
    nome, telefone, total_pedidos, faltam, recompensas_disponiveis,
    status)."""

    banco = banco or conexao.banco

    linhas = banco.buscar(
        """
        SELECT f.cliente_id, c.nome, c.telefone, f.total_pedidos, f.recompensas_disponiveis
        FROM fidelidade f
        JOIN clientes c ON c.id = f.cliente_id
        ORDER BY c.nome
        """
    )

    termo = (termo or "").strip()
    resultado = []

    for cliente_id, nome, telefone, total_pedidos, recompensas_disponiveis in linhas:

        if termo and not (busca.contem(termo, nome) or busca.contem(termo, telefone)):
            continue

        resultado.append((
            cliente_id, nome, telefone or "", total_pedidos,
            _calcular_faltam(banco, total_pedidos), recompensas_disponiveis,
            _status(total_pedidos, recompensas_disponiveis)
        ))

    return resultado


def historico_cliente(cliente_id, banco=None):
    """Linha do tempo de fidelidade de 1 cliente, mais recente
    primeiro: (tipo, alvo, quantidade, pedido_id, numero_pedido, data,
    hora, observacao, usuario, estornado)."""

    banco = banco or conexao.banco

    return banco.buscar(
        """
        SELECT h.tipo, h.alvo, h.quantidade, h.pedido_id, p.numero,
               h.data, h.hora, h.observacao, h.usuario, h.estornado
        FROM historico_fidelidade h
        LEFT JOIN pedidos p ON p.id = h.pedido_id
        WHERE h.cliente_id=?
        ORDER BY h.id DESC
        """,
        (cliente_id,)
    )


# ==========================================================
# RESGATE E AJUSTE MANUAL (tela de Fidelidade / botão em Pedidos)
# ==========================================================

def resgatar_recompensa(cliente_id, usuario, pedido_id=None, banco=None):
    """Resgata 1 recompensa disponível do cliente: debita o saldo e
    registra no histórico quem autorizou, quando e (se aplicável) em
    qual pedido foi usada. Levanta FidelidadeInvalida sem saldo ou sem
    usuário informado."""

    banco = banco or conexao.banco

    registro = banco.buscar_um(
        "SELECT recompensas_disponiveis FROM fidelidade WHERE cliente_id=?",
        (cliente_id,)
    )
    saldo = registro[0] if registro else 0

    if saldo <= 0:
        raise FidelidadeInvalida("Este cliente não tem nenhuma recompensa disponível para resgatar.")

    usuario = (usuario or "").strip()
    if not usuario:
        raise FidelidadeInvalida("Informe quem está autorizando o resgate.")

    _inserir_historico(
        banco, cliente_id, pedido_id, TIPO_RECOMPENSA_RESGATADA, ALVO_RECOMPENSAS, 1,
        usuario=usuario
    )

    return _recalcular(banco, cliente_id)


def ajuste_manual(cliente_id, alvo, quantidade, justificativa, usuario, banco=None):
    """Ajuste manual de pontuação/recompensa (ação administrativa — a
    tela já pede a senha antes de chamar isto). `alvo` é 'pedidos' ou
    'recompensas'; `quantidade` pode ser negativa (remover). Exige
    justificativa e quem autorizou. Levanta FidelidadeInvalida se
    algum dado estiver errado."""

    banco = banco or conexao.banco

    if alvo not in (ALVO_PEDIDOS, ALVO_RECOMPENSAS):
        raise FidelidadeInvalida("Escolha se o ajuste é em pedidos ou em recompensas.")

    try:
        quantidade = int(quantidade)
    except (TypeError, ValueError):
        raise FidelidadeInvalida("Quantidade inválida. Use um número inteiro (ex: 1 ou -1).")

    if quantidade == 0:
        raise FidelidadeInvalida("Informe uma quantidade diferente de zero.")

    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise FidelidadeInvalida("Informe a justificativa do ajuste manual.")

    usuario = (usuario or "").strip()
    if not usuario:
        raise FidelidadeInvalida("Informe quem está autorizando o ajuste.")

    _inserir_historico(
        banco, cliente_id, None, TIPO_AJUSTE_MANUAL, alvo, quantidade,
        observacao=justificativa, usuario=usuario
    )

    return _recalcular(banco, cliente_id)


# ==========================================================
# RESUMOS (Dashboard e Relatórios)
# ==========================================================

def resumo_dashboard(limite_proximos=5, banco=None):
    """Números pro card de Fidelidade do Dashboard + lista dos
    clientes mais próximos da próxima recompensa (ainda sem nenhuma
    disponível)."""

    banco = banco or conexao.banco

    participantes = banco.buscar_um("SELECT COUNT(*) FROM fidelidade")[0]
    disponiveis = banco.buscar_um("SELECT COALESCE(SUM(recompensas_disponiveis), 0) FROM fidelidade")[0]
    resgatadas = banco.buscar_um(
        "SELECT COALESCE(SUM(quantidade), 0) FROM historico_fidelidade WHERE tipo=?",
        (TIPO_RECOMPENSA_RESGATADA,)
    )[0]

    candidatos = banco.buscar(
        """
        SELECT c.nome, f.total_pedidos
        FROM fidelidade f
        JOIN clientes c ON c.id = f.cliente_id
        WHERE f.recompensas_disponiveis = 0 AND f.total_pedidos > 0
        """
    )

    proximos = sorted(
        ((nome, total_pedidos, _calcular_faltam(banco, total_pedidos)) for nome, total_pedidos in candidatos),
        key=lambda item: item[2]
    )

    return {
        "clientes_participantes": participantes,
        "recompensas_disponiveis": disponiveis,
        "recompensas_resgatadas": resgatadas,
        "proximos": proximos[:limite_proximos]
    }


def resumo_relatorio(limite_ranking=10, banco=None):
    """Números agregados pro bloco de Fidelidade dos Relatórios —
    cumulativo/vitalício, não filtrado por período (fidelidade não é
    uma métrica do dia, é histórico do cliente)."""

    banco = banco or conexao.banco

    participantes = banco.buscar_um("SELECT COUNT(*) FROM fidelidade")[0]

    pedidos_contabilizados = banco.buscar_um(
        "SELECT COALESCE(SUM(quantidade), 0) FROM historico_fidelidade WHERE tipo=? AND estornado=0",
        (TIPO_PEDIDO_CONCLUIDO,)
    )[0]

    geradas = banco.buscar_um(
        "SELECT COALESCE(SUM(quantidade), 0) FROM historico_fidelidade WHERE tipo=?",
        (TIPO_RECOMPENSA_GERADA,)
    )[0]

    resgatadas = banco.buscar_um(
        "SELECT COALESCE(SUM(quantidade), 0) FROM historico_fidelidade WHERE tipo=?",
        (TIPO_RECOMPENSA_RESGATADA,)
    )[0]

    disponiveis = banco.buscar_um("SELECT COALESCE(SUM(recompensas_disponiveis), 0) FROM fidelidade")[0]

    ranking = banco.buscar(
        """
        SELECT c.nome, f.total_pedidos, f.recompensas_disponiveis
        FROM fidelidade f
        JOIN clientes c ON c.id = f.cliente_id
        ORDER BY f.total_pedidos DESC
        LIMIT ?
        """,
        (limite_ranking,)
    )

    return {
        "clientes_participantes": participantes,
        "pedidos_contabilizados": pedidos_contabilizados,
        "recompensas_geradas": geradas,
        "recompensas_resgatadas": resgatadas,
        "recompensas_disponiveis": disponiveis,
        "ranking": ranking
    }
