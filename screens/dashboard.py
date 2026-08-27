import customtkinter as ctk
from datetime import datetime

from database.conexao import banco
from utils import config
from repositorios import fidelidade as repositorio_fidelidade


class Dashboard(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.pack(fill="both", expand=True, padx=30, pady=30)

        # Frame com rolagem: em telas menores (notebooks antigos) o
        # conteúdo não cabia inteiro na altura da janela.
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        self.montar_cabecalho()
        self.montar_cards()
        self.montar_alerta_estoque()
        self.montar_fidelidade()

    # ======================================================
    # CABEÇALHO
    # ======================================================

    def montar_cabecalho(self):

        cabecalho = ctk.CTkFrame(self.scroll, fg_color="transparent")
        cabecalho.pack(fill="x", pady=(10, 30))

        ctk.CTkLabel(
            cabecalho,
            text="LOS MANAGER",
            font=("Arial", 34, "bold"),
            text_color=("#2b1d14", "#f5a623")
        ).pack()

        ctk.CTkLabel(
            cabecalho,
            text="Sistema de Gestão  •  Los Pastelles",
            font=("Arial", 16),
            text_color="gray"
        ).pack(pady=(4, 0))

        # Linha decorativa fininha, cor da marca
        linha = ctk.CTkFrame(cabecalho, height=3, fg_color="#f5a623")
        linha.pack(fill="x", padx=120, pady=(14, 0))

    # ======================================================
    # CARDS
    # ======================================================

    def montar_cards(self):

        dados = self.buscar_dados()

        grade = ctk.CTkFrame(self.scroll, fg_color="transparent")
        grade.pack(expand=True)

        # Venda e taxa de motoboy aparecem separadas (mesmo critério do
        # Caixa e dos Relatórios: a taxa só repassa pro motoboy, não é
        # faturamento da pastelaria), com o total logo ao lado.
        cartoes = [
            ("🧾", "#3b82f6", "Pedidos Hoje", str(dados["pedidos_hoje"])),
            ("💰", "#22a559", "Vendas Hoje", f"R$ {dados['vendas']:.2f}"),
            ("🛵", "#ef7c1a", "Taxa Motoboy Hoje", f"R$ {dados['motoboy']:.2f}"),
            ("🧮", "#0ea5e9", "Faturamento Hoje", f"R$ {dados['faturamento']:.2f}"),
            ("👥", "#8b5cf6", "Clientes", str(dados["clientes"])),
            ("🥟", "#f5a623", "Produtos", str(dados["produtos"])),
        ]

        # 2 colunas x 2 linhas, todas do mesmo tamanho
        for coluna in range(2):
            grade.grid_columnconfigure(coluna, weight=1, uniform="cards")

        for indice, (icone, cor, titulo, valor) in enumerate(cartoes):

            linha = indice // 2
            coluna = indice % 2

            self.criar_card(grade, icone, cor, titulo, valor, linha, coluna)

    # ======================================================

    def criar_card(self, pai, icone, cor, titulo, valor, linha, coluna):

        card = ctk.CTkFrame(
            pai,
            width=280,
            height=150,
            corner_radius=16,
            fg_color=("white", "#242424"),
            border_width=1,
            border_color=("#e5e5e5", "#333333")
        )

        card.grid(
            row=linha,
            column=coluna,
            padx=14,
            pady=14,
            sticky="nsew"
        )

        card.grid_propagate(False)

        conteudo = ctk.CTkFrame(card, fg_color="transparent")
        conteudo.pack(fill="both", expand=True, padx=20, pady=18)

        # ---------------- Ícone dentro de um círculo colorido ----------------

        selo = ctk.CTkFrame(
            conteudo,
            width=46,
            height=46,
            corner_radius=23,
            fg_color=cor
        )
        selo.pack(anchor="w")
        selo.pack_propagate(False)

        ctk.CTkLabel(
            selo,
            text=icone,
            font=("Arial", 20),
            text_color="white"
        ).place(relx=0.5, rely=0.5, anchor="center")

        # ---------------- Título ----------------

        ctk.CTkLabel(
            conteudo,
            text=titulo,
            font=("Arial", 14),
            text_color="gray",
            anchor="w"
        ).pack(fill="x", pady=(14, 2))

        # ---------------- Valor ----------------

        ctk.CTkLabel(
            conteudo,
            text=valor,
            font=("Arial", 26, "bold"),
            anchor="w"
        ).pack(fill="x")

    # ======================================================
    # ALERTA DE ESTOQUE BAIXO (ingredientes)
    # ======================================================

    def montar_alerta_estoque(self):

        ingredientes_baixos = banco.buscar(
            """
            SELECT nome, estoque_atual, estoque_minimo
            FROM ingredientes
            WHERE ativo=1 AND estoque_atual <= estoque_minimo
            ORDER BY nome
            """
        )

        if not ingredientes_baixos:
            return

        nomes = ", ".join(nome for nome, _, _ in ingredientes_baixos)

        alerta = ctk.CTkFrame(
            self.scroll,
            corner_radius=14,
            fg_color="#fef2f2",
            border_width=1,
            border_color="#fca5a5"
        )
        alerta.pack(fill="x", padx=14, pady=(0, 14))

        ctk.CTkLabel(
            alerta,
            text=f"⚠️ Estoque baixo de {len(ingredientes_baixos)} ingrediente(s): {nomes}",
            font=("Arial", 14, "bold"),
            text_color="#b91c1c",
            wraplength=900,
            justify="left"
        ).pack(padx=18, pady=12, anchor="w")

    # ======================================================
    # PROGRAMA DE FIDELIDADE
    # ======================================================

    def montar_fidelidade(self):

        resumo = repositorio_fidelidade.resumo_dashboard()

        bloco = ctk.CTkFrame(
            self.scroll,
            corner_radius=14,
            fg_color=("white", "#242424"),
            border_width=1,
            border_color=("#e5e5e5", "#333333")
        )
        bloco.pack(fill="x", padx=14, pady=(0, 14))

        ctk.CTkLabel(
            bloco,
            text="🎁 Fidelidade",
            font=("Arial", 16, "bold")
        ).pack(anchor="w", padx=18, pady=(14, 6))

        linha_numeros = ctk.CTkFrame(bloco, fg_color="transparent")
        linha_numeros.pack(fill="x", padx=18, pady=(0, 10))

        def numero(titulo, valor, coluna):
            coluna_frame = ctk.CTkFrame(linha_numeros, fg_color="transparent")
            coluna_frame.grid(row=0, column=coluna, sticky="w", padx=(0, 40))
            ctk.CTkLabel(
                coluna_frame, text=titulo, font=("Arial", 12), text_color="gray"
            ).pack(anchor="w")
            ctk.CTkLabel(
                coluna_frame, text=str(valor), font=("Arial", 20, "bold")
            ).pack(anchor="w")

        numero("Clientes cadastrados", resumo["clientes_participantes"], 0)
        numero("Recompensas disponíveis", resumo["recompensas_disponiveis"], 1)
        numero("Recompensas resgatadas", resumo["recompensas_resgatadas"], 2)

        if resumo["proximos"]:

            ctk.CTkLabel(
                bloco,
                text="🔥 Clientes próximos da recompensa",
                font=("Arial", 13, "bold")
            ).pack(anchor="w", padx=18, pady=(6, 4))

            meta = config.obter_meta_fidelidade()

            for nome, _total_pedidos, faltam in resumo["proximos"]:
                ctk.CTkLabel(
                    bloco,
                    text=f"{nome}    {meta - faltam}/{meta}",
                    font=("Arial", 12),
                    anchor="w"
                ).pack(fill="x", padx=24, pady=1)

            ctk.CTkLabel(bloco, text="", height=1).pack(pady=4)

    # ======================================================
    # BANCO: números reais do sistema
    # ======================================================

    def buscar_dados(self):

        hoje = datetime.now().strftime("%d/%m/%Y")

        # Pedido cancelado não conta nem na quantidade nem no
        # faturamento — o mesmo critério já usado em Caixa e Relatórios.
        # O `status IS NULL` cobre pedidos antigos, gravados antes da
        # coluna de status passar a ser sempre preenchida.
        nao_cancelado = "(status IS NULL OR status != 'Cancelado')"

        pedidos_hoje = banco.buscar_um(
            f"SELECT COUNT(*) FROM pedidos WHERE data=? AND {nao_cancelado}",
            (hoje,)
        )

        clientes = banco.buscar_um(
            "SELECT COUNT(*) FROM clientes"
        )

        produtos = banco.buscar_um(
            "SELECT COUNT(*) FROM produtos WHERE ativo=1"
        )

        # Venda = produtos (subtotal - desconto); motoboy = taxa de
        # entrega (acrescimo); faturamento = o que o cliente pagou.
        valores = banco.buscar_um(
            f"""
            SELECT COALESCE(SUM(COALESCE(subtotal, 0) - COALESCE(desconto, 0)), 0),
                   COALESCE(SUM(COALESCE(acrescimo, 0)), 0),
                   COALESCE(SUM(COALESCE(total, 0)), 0)
            FROM pedidos
            WHERE data=? AND {nao_cancelado}
            """,
            (hoje,)
        )

        vendas, motoboy, faturamento = valores if valores else (0.0, 0.0, 0.0)

        return {
            "pedidos_hoje": pedidos_hoje[0] if pedidos_hoje else 0,
            "clientes": clientes[0] if clientes else 0,
            "produtos": produtos[0] if produtos else 0,
            "vendas": vendas,
            "motoboy": motoboy,
            "faturamento": faturamento,
        }
