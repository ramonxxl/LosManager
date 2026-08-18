"""
=================================================================
MÓDULO DE IMPRESSÃO TÉRMICA (ESC/POS via Windows Spooler)
=================================================================

Como funciona:
- Usa a biblioteca pywin32 (win32print) para enviar bytes "crus"
  (RAW) diretamente para a impressora já instalada no Windows.
- Não depende de marca específica: funciona com Epson, Elgin,
  Bematech, Diebold, Sweda, Vox, etc., desde que a impressora
  esteja instalada normalmente no Windows (Configurações >
  Impressoras e scanners) e ela entenda comandos ESC/POS
  (99% das térmicas de cupom entendem).

O nome da impressora e a largura do papel agora são lidos da
tela de Configurações do sistema (guardados no banco via
utils/config.py) — não precisa mais editar este arquivo.

INSTALAÇÃO NECESSÁRIA (no notebook onde a impressora está):

    pip install pywin32
=================================================================
"""

import win32print
import os

from utils import config


CODEPAGE = "cp860"


# =================================================================
# COMANDOS ESC/POS (não mexer)
# =================================================================

ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"
NEGRITO_ON = ESC + b"E" + b"\x01"
NEGRITO_OFF = ESC + b"E" + b"\x00"
ALINHAR_ESQ = ESC + b"a" + b"\x00"
ALINHAR_CENTRO = ESC + b"a" + b"\x01"
FONTE_NORMAL = GS + b"!" + b"\x00"
FONTE_DUPLA = GS + b"!" + b"\x11"
PULAR_LINHAS = lambda n: b"\n" * n
CORTAR_PAPEL = GS + b"V" + b"\x01"

# Vídeo invertido (letra branca em fundo preto). É assim que a
# observação do item sai destacada no cupom, pra cozinha não passar
# batido num "sem cebola". Comando padrão ESC/POS, entendido pela
# grande maioria das térmicas.
INVERTIDO_ON = GS + b"B" + b"\x01"
INVERTIDO_OFF = GS + b"B" + b"\x00"


# =================================================================
# FUNÇÕES DE APOIO
# =================================================================

def listar_impressoras():
    """Retorna a lista de impressoras instaladas no Windows."""

    impressoras = win32print.EnumPrinters(
        win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    )

    return [p[2] for p in impressoras]


def _texto(txt):

    return txt.encode(CODEPAGE, errors="replace")


def _linha_dupla_coluna(esquerda, direita, largura):

    espacos = largura - len(esquerda) - len(direita)

    if espacos < 1:
        espacos = 1

    return esquerda + (" " * espacos) + direita


def _quebrar_texto(texto, largura):

    linhas = []
    atual = ""

    for palavra in texto.split(" "):

        if len(atual) + len(palavra) + 1 > largura:
            linhas.append(atual)
            atual = palavra
        else:
            atual = (atual + " " + palavra).strip()

    if atual:
        linhas.append(atual)

    return linhas


def _bloco_destacado(texto, largura):
    """Monta um bloco em vídeo invertido (fundo preto) ocupando a
    largura inteira do papel. Cada linha é preenchida com espaços até o
    fim justamente para o fundo preto virar uma tarja cheia, em vez de
    parar onde o texto acaba."""

    buffer = b""

    for linha in _quebrar_texto(texto, largura - 2):
        buffer += INVERTIDO_ON + NEGRITO_ON
        buffer += _texto(" " + linha.ljust(largura - 1))
        buffer += NEGRITO_OFF + INVERTIDO_OFF
        buffer += b"\n"

    return buffer


def _logo_para_escpos(largura):
    """Carrega a logo (arquivo já preto-e-branco, gerado sob medida
    para 58mm ou 80mm) e converte pro formato bitmap que a impressora
    térmica entende (comando ESC/POS GS v 0). Se não achar o arquivo,
    retorna vazio — o cupom imprime normal, só sem a imagem."""

    nome_arquivo = "logo_cupom_80mm.png" if largura >= 40 else "logo_cupom_58mm.png"
    caminho = config.caminho_asset(nome_arquivo)

    if not os.path.isfile(caminho):
        return b""

    try:
        from PIL import Image
    except ImportError:
        return b""

    try:
        imagem = Image.open(caminho).convert("1")
    except Exception:
        return b""

    largura_px, altura_px = imagem.size
    largura_bytes = (largura_px + 7) // 8
    pixels = imagem.load()

    dados = bytearray()

    for y in range(altura_px):
        for xb in range(largura_bytes):

            byte = 0

            for bit in range(8):

                x = xb * 8 + bit

                if x < largura_px and pixels[x, y] == 0:
                    byte |= (1 << (7 - bit))

            dados.append(byte)

    xL = largura_bytes & 0xFF
    xH = (largura_bytes >> 8) & 0xFF
    yL = altura_px & 0xFF
    yH = (altura_px >> 8) & 0xFF

    comando = GS + b"v" + b"\x30" + bytes([0, xL, xH, yL, yH]) + bytes(dados)

    return comando


# =================================================================
# MONTAGEM DO CUPOM
# =================================================================

def montar_cupom(dados_loja, pedido, itens, largura=32):
    """
    dados_loja = {"nome": "...", "endereco": "...", "telefone": "..."}

    pedido = {
        "numero": 12, "cliente": "João da Silva",
        "endereco_cliente": "Rua Exemplo, 123 - Centro - Cidade",
        "data": "30/07/2026", "hora": "19:45",
        "subtotal": 45.00, "desconto": 0.00, "acrescimo": 0.00,
        "total": 45.00, "pagamento": "PIX", "observacao": ""
    }

    "endereco_cliente" é opcional (Cliente Balcão ou cliente sem
    endereço cadastrado não manda essa chave) e sai logo abaixo do
    nome do cliente, pro motoboy não precisar abrir o cadastro.

    itens = [
        {"nome": "Pastel de Carne", "qtd": 2,
         "valor_unitario": 12.00, "subtotal": 24.00,
         "observacao": "retirar o milho"}, ...
    ]

    A "observacao" de cada item é opcional e sai logo abaixo do produto
    em tarja preta (vídeo invertido), pra cozinha não passar batido.
    """

    buffer = b""

    buffer += INIT
    buffer += ALINHAR_CENTRO

    buffer += _logo_para_escpos(largura)

    buffer += NEGRITO_ON + FONTE_DUPLA
    buffer += _texto(dados_loja.get("nome", "") + "\n")
    buffer += FONTE_NORMAL + NEGRITO_OFF

    if dados_loja.get("endereco"):
        buffer += _texto(dados_loja["endereco"] + "\n")

    if dados_loja.get("telefone"):
        buffer += _texto(dados_loja["telefone"] + "\n")

    buffer += _texto("-" * largura + "\n")

    buffer += ALINHAR_ESQ
    buffer += NEGRITO_ON
    buffer += _texto(f"PEDIDO Nº {pedido['numero']:04d}\n")
    buffer += NEGRITO_OFF
    buffer += _texto(f"{pedido['data']}  {pedido['hora']}\n")
    buffer += _texto(f"Cliente: {pedido['cliente']}\n")

    if pedido.get("endereco_cliente"):
        for linha in _quebrar_texto(f"Endereço: {pedido['endereco_cliente']}", largura):
            buffer += _texto(linha + "\n")

    buffer += _texto("-" * largura + "\n")

    # ---------------- Itens ----------------

    for item in itens:

        linha_nome = f"{item['qtd']}x {item['nome']}"

        for linha in _quebrar_texto(linha_nome, largura):
            buffer += _texto(linha + "\n")

        valor_str = f"R$ {item['subtotal']:.2f}"
        unit_str = f"(R$ {item['valor_unitario']:.2f} un)"

        buffer += _texto(
            _linha_dupla_coluna(unit_str, valor_str, largura) + "\n"
        )

        # Observação do item (ex: "retirar o milho") sai em tarja preta
        # logo abaixo do produto a que pertence.
        if item.get("observacao"):
            buffer += _bloco_destacado(f"** {item['observacao'].upper()}", largura)

    buffer += _texto("-" * largura + "\n")

    # ---------------- Totais ----------------

    buffer += _texto(
        _linha_dupla_coluna("Subtotal:", f"R$ {pedido['subtotal']:.2f}", largura) + "\n"
    )

    if pedido.get("desconto", 0) > 0:
        buffer += _texto(
            _linha_dupla_coluna("Desconto:", f"-R$ {pedido['desconto']:.2f}", largura) + "\n"
        )

    if pedido.get("acrescimo", 0) > 0:
        buffer += _texto(
            _linha_dupla_coluna("Acréscimo:", f"R$ {pedido['acrescimo']:.2f}", largura) + "\n"
        )

    buffer += NEGRITO_ON + FONTE_DUPLA
    buffer += _texto(f"TOTAL: R$ {pedido['total']:.2f}\n")
    buffer += FONTE_NORMAL + NEGRITO_OFF

    buffer += _texto(f"Pagamento: {pedido['pagamento']}\n")

    if pedido.get("observacao"):
        buffer += _texto("-" * largura + "\n")
        buffer += _texto(f"Obs: {pedido['observacao']}\n")

    buffer += _texto("-" * largura + "\n")
    buffer += ALINHAR_CENTRO
    buffer += _texto("Obrigado pela preferência!\n")
    buffer += _texto("Volte sempre :)\n")

    buffer += PULAR_LINHAS(4)
    buffer += CORTAR_PAPEL

    return buffer


# =================================================================
# ENVIO PARA A IMPRESSORA
# =================================================================

def imprimir_cupom(dados_loja, pedido, itens, nome_impressora=None, largura=None):
    """Monta o cupom e envia para a impressora térmica.
    Se nome_impressora/largura não forem informados, lê da tela
    de Configurações (salva no banco via utils/config.py)."""

    if not nome_impressora:
        nome_impressora = config.obter_impressora_nome()

    if not nome_impressora:
        raise ValueError(
            "Nenhuma impressora configurada. Vá em Configurações "
            "e selecione a impressora térmica."
        )

    if largura is None:
        largura = config.obter_largura_papel()

    dados_bytes = montar_cupom(dados_loja, pedido, itens, largura=largura)

    handle = win32print.OpenPrinter(nome_impressora)

    try:
        win32print.StartDocPrinter(handle, 1, ("Cupom Pedido", None, "RAW"))

        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, dados_bytes)
            win32print.EndPagePrinter(handle)

        finally:
            win32print.EndDocPrinter(handle)

    finally:
        win32print.ClosePrinter(handle)


if __name__ == "__main__":

    print("Impressoras instaladas no Windows:\n")

    for nome in listar_impressoras():
        print(" -", nome)
