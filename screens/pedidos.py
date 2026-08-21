import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import datetime

from database.conexao import banco
from utils import impressora
from utils import config
from utils import busca
from utils import responsivo
from utils import caixa_estado
from utils import pedido_rascunho
from repositorios import motoboys as repositorio_motoboys

SEM_MOTOBOY = "— Nenhum —"


class Pedidos(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)

        self.pack(fill="both", expand=True, padx=15, pady=15)

        self.total = 0.0

        # Lista de itens do pedido em memória (fonte da verdade).
        # A Treeview é só a exibição; os dados reais ficam aqui.
        self.itens = []

        self.criar_interface()

        self.carregar_clientes()
        self.carregar_produtos()

        self.restaurar_rascunho()

    # ======================================================

    def destroy(self):

        # Guarda o carrinho em memória antes da tela ser destruída, pra
        # não perder o pedido ao navegar pra outra tela — ver
        # utils/pedido_rascunho.py.
        self.salvar_rascunho()

        super().destroy()

    # ======================================================

    def salvar_rascunho(self):

        if not self.itens:
            pedido_rascunho.limpar()
            return

        pedido_rascunho.salvar({
            "itens": self.itens,
            "total": self.total,
            "cliente_selecionado": self.cliente_selecionado,
            "pagamento": self.pagamento.get(),
            "valor_entrega": self.valor_entrega.get(),
            "motoboy": self.motoboy_combo.get(),
            "imprimir_cupom": bool(self.imprimir_cupom.get())
        })

    # ======================================================

    def restaurar_rascunho(self):
        """Repõe o pedido que ficou em andamento numa passagem anterior
        por essa tela (ver utils/pedido_rascunho.py). Sem rascunho
        guardado, ou rascunho vazio, não faz nada."""

        estado = pedido_rascunho.obter()

        if estado is None or not estado["itens"]:
            return

        self.itens = estado["itens"]
        self.total = estado["total"]

        for item in self.itens:
            self.tabela.insert(
                "", "end",
                values=(
                    item["nome"],
                    item["observacao"],
                    item["qtd"],
                    f"R$ {item['valor_unitario']:.2f}",
                    f"R$ {item['subtotal']:.2f}"
                )
            )

        self.cliente_selecionado = estado["cliente_selecionado"]

        if self.cliente_selecionado:
            cliente = self.cliente_selecionado
            self.lbl_cliente_selecionado.configure(
                text=f"✅ {cliente['nome']}" + (f"  —  {cliente['telefone']}" if cliente["telefone"] else ""),
                text_color="#2a7"
            )

        self.pagamento.set(estado["pagamento"])

        if estado["valor_entrega"]:
            self.valor_entrega.insert(0, estado["valor_entrega"])

        if estado["motoboy"] in self.motoboy_combo.cget("values"):
            self.motoboy_combo.set(estado["motoboy"])

        if estado["imprimir_cupom"]:
            self.imprimir_cupom.select()
        else:
            self.imprimir_cupom.deselect()

        self.atualizar_total()

    # ======================================================

    def criar_interface(self):

        # Frame com rolagem: em telas menores (notebooks antigos) o
        # conteúdo não cabia inteiro na altura da janela e não tinha
        # como rolar até o botão "Finalizar e Imprimir".
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        titulo = ctk.CTkLabel(
            self.scroll,
            text="Novo Pedido",
            font=("Arial", 28, "bold")
        )
        titulo.pack(pady=(5, 15))

        topo = ctk.CTkFrame(self.scroll)
        topo.pack(fill="x")

        # ---------------- Cliente (com busca, igual produto) ----------------
        # Faz a mesma busca por nome/telefone em vez de um combobox com
        # todos os clientes — com centenas de clientes cadastrados, rolar
        # uma lista enorme pra achar um fica inviável.

        ctk.CTkLabel(
            topo,
            text="Cliente"
        ).grid(row=0, column=0, padx=10, pady=10, sticky="n")

        coluna_cliente = ctk.CTkFrame(topo, fg_color="transparent")
        coluna_cliente.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        linha_busca_cliente = ctk.CTkFrame(coluna_cliente, fg_color="transparent")
        linha_busca_cliente.pack(anchor="w", fill="x")

        self.busca_cliente = ctk.CTkEntry(
            linha_busca_cliente,
            width=230,
            placeholder_text="Buscar por nome ou telefone..."
        )
        self.busca_cliente.pack(side="left")
        self.busca_cliente.bind("<KeyRelease>", self.filtrar_clientes)
        self.busca_cliente.bind("<Down>", self.focar_lista_resultados_cliente)

        ctk.CTkButton(
            linha_busca_cliente,
            text="Balcão",
            width=65,
            fg_color="gray40",
            hover_color="gray30",
            command=self.selecionar_cliente_balcao
        ).pack(side="left", padx=(8, 0))

        resultados_cliente_frame = ctk.CTkFrame(coluna_cliente, fg_color="transparent")

        self.lista_resultados_cliente = ttk.Treeview(
            resultados_cliente_frame,
            columns=("nome", "telefone"),
            show="headings",
            height=6
        )
        self.lista_resultados_cliente.heading("nome", text="Cliente")
        self.lista_resultados_cliente.heading("telefone", text="Telefone")
        self.lista_resultados_cliente.column("nome", width=200)
        self.lista_resultados_cliente.column("telefone", width=110)
        self.lista_resultados_cliente.bind("<<TreeviewSelect>>", self.selecionar_cliente_da_lista)
        self.lista_resultados_cliente.pack(side="left", fill="both", expand=True)

        scroll_resultados_cliente = ctk.CTkScrollbar(
            resultados_cliente_frame,
            orientation="vertical",
            command=self.lista_resultados_cliente.yview
        )
        scroll_resultados_cliente.pack(side="left", fill="y")
        self.lista_resultados_cliente.configure(yscrollcommand=scroll_resultados_cliente.set)

        self.resultados_cliente_frame = resultados_cliente_frame
        # Começa escondida; só aparece quando há resultados de busca

        self.cliente_selecionado = None  # None = Cliente Balcão

        self.lbl_cliente_selecionado = ctk.CTkLabel(
            coluna_cliente,
            text="🧍 Cliente Balcão",
            font=("Arial", 13, "italic"),
            text_color="gray"
        )
        self.lbl_cliente_selecionado.pack(anchor="w", pady=(5, 0))

        # ---------------- Produto (com busca) ----------------

        ctk.CTkLabel(
            topo,
            text="Buscar Produto"
        ).grid(row=1, column=0, padx=10, pady=10, sticky="n")

        coluna_produto = ctk.CTkFrame(topo, fg_color="transparent")
        coluna_produto.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        self.busca_produto = ctk.CTkEntry(
            coluna_produto,
            width=300,
            placeholder_text="Digite o nome do produto..."
        )
        self.busca_produto.pack(anchor="w")
        self.busca_produto.bind("<KeyRelease>", self.filtrar_produtos)
        self.busca_produto.bind("<Down>", self.focar_lista_resultados)

        resultados_frame = ctk.CTkFrame(coluna_produto, fg_color="transparent")

        self.lista_resultados = ttk.Treeview(
            resultados_frame,
            columns=("nome", "preco"),
            show="headings",
            height=6
        )
        self.lista_resultados.heading("nome", text="Produto")
        self.lista_resultados.heading("preco", text="Preço")
        self.lista_resultados.column("nome", width=220)
        self.lista_resultados.column("preco", width=80, anchor="e")
        self.lista_resultados.bind("<<TreeviewSelect>>", self.selecionar_produto_da_lista)
        self.lista_resultados.bind("<Double-1>", lambda e: self.quantidade.focus())
        self.lista_resultados.pack(side="left", fill="both", expand=True)

        scroll_resultados = ctk.CTkScrollbar(
            resultados_frame,
            orientation="vertical",
            command=self.lista_resultados.yview
        )
        scroll_resultados.pack(side="left", fill="y")
        self.lista_resultados.configure(yscrollcommand=scroll_resultados.set)

        self.resultados_frame = resultados_frame
        # Começa escondida; só aparece quando há resultados de busca

        self.lbl_produto_selecionado = ctk.CTkLabel(
            coluna_produto,
            text="Nenhum produto selecionado",
            font=("Arial", 13, "italic"),
            text_color="gray"
        )
        self.lbl_produto_selecionado.pack(anchor="w", pady=(5, 0))

        self.produto_selecionado = None

        # ---------------- Quantidade ----------------

        ctk.CTkLabel(
            topo,
            text="Qtd."
        ).grid(row=1, column=2, sticky="n", pady=10)

        self.quantidade = ctk.CTkEntry(
            topo,
            width=80
        )
        self.quantidade.insert(0, "1")
        self.quantidade.grid(row=1, column=3, sticky="n", pady=10)

        # ---------------- Observação + botões (linha própria) ----------------
        # Ficam numa segunda linha, dentro de um frame só deles, porque
        # tudo numa linha só não cabia em telas 1366x768 (PC antigo da
        # loja): os botões saíam para fora da área visível. O frame
        # isola essas larguras das colunas do grid de cima.

        linha_acoes = ctk.CTkFrame(topo, fg_color="transparent")
        linha_acoes.grid(row=2, column=0, columnspan=4, sticky="w", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            linha_acoes,
            text="Obs. do item"
        ).pack(side="left", padx=(0, 5))

        # Observação por item (não do pedido inteiro): é onde vai
        # "sem milho", "sem cebola", etc. Sai destacado no cupom pra
        # cozinha não passar batido.
        self.observacao_item = ctk.CTkEntry(
            linha_acoes,
            width=220,
            placeholder_text="Ex: retirar o milho"
        )
        self.observacao_item.pack(side="left")
        self.observacao_item.bind("<Return>", lambda e: self.adicionar_item())

        ctk.CTkButton(
            linha_acoes,
            text="Adicionar",
            width=130,
            command=self.adicionar_item
        ).pack(side="left", padx=(15, 8))

        ctk.CTkButton(
            linha_acoes,
            text="Remover selecionado",
            width=170,
            fg_color="#a33",
            hover_color="#822",
            command=self.remover_item
        ).pack(side="left")

        # =========================
        # Rodapé é criado (e empacotado) antes da tabela do carrinho só
        # para medir sua altura real; a tabela é inserida visualmente
        # ANTES dele via pack(before=...) logo abaixo.

        rodape = ctk.CTkFrame(self.scroll)
        rodape.pack(fill="x")

        ctk.CTkLabel(
            rodape,
            text="Pagamento"
        ).grid(row=0, column=0, padx=10)

        self.pagamento = ctk.CTkComboBox(
            rodape,
            values=[
                "PIX",
                "Dinheiro",
                "Débito",
                "Crédito"
            ],
            width=180
        )

        self.pagamento.set("PIX")
        self.pagamento.grid(row=0, column=1)

        ctk.CTkLabel(
            rodape,
            text="Entrega (motoboy)"
        ).grid(row=0, column=2, padx=(20, 5))

        self.valor_entrega = ctk.CTkEntry(
            rodape,
            width=90,
            placeholder_text="0,00"
        )
        self.valor_entrega.grid(row=0, column=3)
        self.valor_entrega.bind("<KeyRelease>", lambda e: self.atualizar_total())

        self.lbl_total = ctk.CTkLabel(
            rodape,
            text="TOTAL: R$ 0,00",
            font=("Arial", 22, "bold")
        )

        self.lbl_total.grid(
            row=0,
            column=4,
            padx=40
        )

        ctk.CTkButton(
            rodape,
            text="Finalizar Pedido",
            width=200,
            fg_color="#2a7",
            hover_color="#186",
            command=self.finalizar
        ).grid(row=0, column=5, padx=20)

        # Linha própria pro motoboy + opção de impressão: junto com a
        # linha 0 passaria de ~1040px de largura útil em telas 1366x768
        # (ver nota de largura no CLAUDE.md).

        ctk.CTkLabel(
            rodape,
            text="Motoboy"
        ).grid(row=1, column=0, padx=10, pady=(0, 10))

        self.motoboy_combo = ctk.CTkComboBox(
            rodape,
            values=[SEM_MOTOBOY],
            width=180
        )
        self.motoboy_combo.set(SEM_MOTOBOY)
        self.motoboy_combo.grid(row=1, column=1, pady=(0, 10))

        self.imprimir_cupom = ctk.CTkCheckBox(
            rodape,
            text="Imprimir cupom"
        )
        self.imprimir_cupom.select()
        self.imprimir_cupom.grid(row=1, column=2, columnspan=2, padx=(20, 5), pady=(0, 10), sticky="w")

        self.carregar_motoboys()

        # ---------------- Tabela do carrinho ----------------
        # Vem por último na construção (pra já poder medir a altura do
        # rodapé acima), mas é inserida visualmente antes dele via
        # pack(before=...).

        linhas = responsivo.linhas_para_tabela(self, self.scroll, pady_tabela=15)

        self.tabela = ttk.Treeview(
            self.scroll,
            columns=("produto", "observacao", "qtd", "valor", "subtotal"),
            show="headings",
            height=linhas
        )

        self.tabela.heading("produto", text="Produto")
        self.tabela.heading("observacao", text="Observação")
        self.tabela.heading("qtd", text="Qtd")
        self.tabela.heading("valor", text="Valor")
        self.tabela.heading("subtotal", text="Subtotal")

        self.tabela.column("produto", width=300)
        self.tabela.column("observacao", width=220)
        self.tabela.column("qtd", width=80, anchor="center")
        self.tabela.column("valor", width=120, anchor="e")
        self.tabela.column("subtotal", width=120, anchor="e")

        self.tabela.pack(fill="both", expand=True, pady=15, before=rodape)

        responsivo.tornar_dinamica(self, self.scroll, lambda: self.tabela, pady_tabela=15)

    # ======================================================

    def carregar_motoboys(self):

        self.motoboys_cache = repositorio_motoboys.listar_ativos()

        nomes = [SEM_MOTOBOY] + [nome for _id, nome in self.motoboys_cache]

        self.motoboy_combo.configure(values=nomes)
        self.motoboy_combo.set(SEM_MOTOBOY)

    # ======================================================

    def obter_motoboy_id(self):

        nome_escolhido = self.motoboy_combo.get()

        motoboy = next(
            (m for m in self.motoboys_cache if m[1] == nome_escolhido),
            None
        )

        return motoboy[0] if motoboy else None

    # ======================================================

    def obter_valor_entrega(self):

        texto = self.valor_entrega.get().strip().replace(",", ".")

        if texto == "":
            return 0.0

        try:
            valor = float(texto)
        except ValueError:
            return 0.0

        return valor if valor > 0 else 0.0

    # ======================================================

    def atualizar_total(self):

        entrega = self.obter_valor_entrega()
        total_final = self.total + entrega

        self.lbl_total.configure(
            text=f"TOTAL: R$ {total_final:.2f}"
        )

    # ======================================================

    def carregar_clientes(self):

        self.clientes_cache = banco.buscar(
            "SELECT id, nome, telefone FROM clientes ORDER BY nome"
        )

    # ======================================================

    def filtrar_clientes(self, evento=None):

        texto = self.busca_cliente.get().strip()

        # Esconde a lista se o campo de busca estiver vazio
        self.resultados_cliente_frame.pack_forget()

        for linha in self.lista_resultados_cliente.get_children():
            self.lista_resultados_cliente.delete(linha)

        if not texto:
            return

        prefixo = [
            c for c in self.clientes_cache
            if busca.comeca_com(texto, c[1])
        ]

        meio = [
            c for c in self.clientes_cache
            if busca.contem(texto, c[1]) and not busca.comeca_com(texto, c[1])
        ]

        # Também acha por telefone (contém, sem distinção de prefixo)
        por_telefone = [
            c for c in self.clientes_cache
            if busca.contem(texto, c[2]) and c not in prefixo and c not in meio
        ]

        encontrados = prefixo + meio + por_telefone

        if not encontrados:
            return

        for cliente_id, nome, telefone in encontrados[:15]:
            self.lista_resultados_cliente.insert(
                "", "end",
                iid=str(cliente_id),
                values=(nome, telefone or "")
            )

        self.resultados_cliente_frame.pack(anchor="w", pady=(5, 0), fill="x")

    # ======================================================

    def focar_lista_resultados_cliente(self, evento=None):

        filhos = self.lista_resultados_cliente.get_children()

        if filhos:
            self.lista_resultados_cliente.focus_set()
            self.lista_resultados_cliente.selection_set(filhos[0])
            self.lista_resultados_cliente.focus(filhos[0])

    # ======================================================

    def selecionar_cliente_da_lista(self, evento=None):

        selecionado = self.lista_resultados_cliente.selection()

        if not selecionado:
            return

        cliente_id = int(selecionado[0])

        cliente = next(
            (c for c in self.clientes_cache if c[0] == cliente_id),
            None
        )

        if cliente is None:
            return

        self.cliente_selecionado = {
            "id": cliente[0],
            "nome": cliente[1],
            "telefone": cliente[2]
        }

        self.lbl_cliente_selecionado.configure(
            text=f"✅ {cliente[1]}" + (f"  —  {cliente[2]}" if cliente[2] else ""),
            text_color="#2a7"
        )

        self.busca_cliente.delete(0, "end")
        self.resultados_cliente_frame.pack_forget()

    # ======================================================

    def selecionar_cliente_balcao(self):

        self.cliente_selecionado = None

        self.busca_cliente.delete(0, "end")
        self.resultados_cliente_frame.pack_forget()

        self.lbl_cliente_selecionado.configure(
            text="🧍 Cliente Balcão",
            text_color="gray"
        )

    # ======================================================

    def carregar_produtos(self):

        self.produtos_cache = banco.buscar(
            "SELECT id, nome, preco, estoque FROM produtos WHERE ativo=1 ORDER BY nome"
        )

    # ======================================================

    def filtrar_produtos(self, evento=None):

        texto = self.busca_produto.get().strip()

        # Esconde a lista se o campo de busca estiver vazio
        self.resultados_frame.pack_forget()

        for linha in self.lista_resultados.get_children():
            self.lista_resultados.delete(linha)

        if not texto:
            return

        prefixo = [
            p for p in self.produtos_cache
            if busca.comeca_com(texto, p[1])
        ]

        meio = [
            p for p in self.produtos_cache
            if busca.contem(texto, p[1]) and not busca.comeca_com(texto, p[1])
        ]

        # Produtos cujo nome começa com o termo aparecem primeiro
        # (ex: buscar "queijo" mostra "Queijo Mussarela" antes de
        # "Calabresa com Queijo", mesmo que ambos contenham "queijo")
        encontrados = prefixo + meio

        if not encontrados:
            return

        for produto_id, nome, preco, estoque in encontrados[:15]:
            self.lista_resultados.insert(
                "", "end",
                iid=str(produto_id),
                values=(nome, f"R$ {preco:.2f}")
            )

        self.resultados_frame.pack(anchor="w", pady=(5, 0), fill="x")

    # ======================================================

    def focar_lista_resultados(self, evento=None):

        filhos = self.lista_resultados.get_children()

        if filhos:
            self.lista_resultados.focus_set()
            self.lista_resultados.selection_set(filhos[0])
            self.lista_resultados.focus(filhos[0])

    # ======================================================

    def selecionar_produto_da_lista(self, evento=None):

        selecionado = self.lista_resultados.selection()

        if not selecionado:
            return

        produto_id = int(selecionado[0])

        produto = next(
            (p for p in self.produtos_cache if p[0] == produto_id),
            None
        )

        if produto is None:
            return

        self.produto_selecionado = {
            "id": produto[0],
            "nome": produto[1],
            "preco": produto[2],
            "estoque": produto[3]
        }

        self.lbl_produto_selecionado.configure(
            text=f"✅ {produto[1]}  —  R$ {produto[2]:.2f}  "
                 f"(estoque: {produto[3]})",
            text_color="#2a7"
        )

        self.busca_produto.delete(0, "end")
        self.resultados_frame.pack_forget()
        self.quantidade.focus()
        self.quantidade.select_range(0, "end")

    # ======================================================

    def calcular_consumo_ingredientes(self, itens):
        """Soma quanto de cada ingrediente essa lista de itens (dicts
        com produto_id/qtd) vai consumir, olhando a receita de cada
        produto. Retorna {ingrediente_id: quantidade_total}."""

        consumo = {}

        for item in itens:

            receita = banco.buscar(
                "SELECT ingrediente_id, quantidade FROM receita_produto WHERE produto_id=?",
                (item["produto_id"],)
            )

            for ingrediente_id, quantidade in receita:
                consumo[ingrediente_id] = consumo.get(ingrediente_id, 0) + quantidade * item["qtd"]

        return consumo

    # ======================================================

    def verificar_estoque_ingredientes(self, itens, nome_produto):
        """Confere se o estoque de ingredientes aguenta os `itens`
        simulados. Se faltar algo: bloqueia (se configurado) ou avisa
        e deixa o usuário decidir se continua. Retorna True se pode
        seguir com a adição do item, False se deve cancelar."""

        consumo = self.calcular_consumo_ingredientes(itens)

        if not consumo:
            return True

        placeholders = ",".join("?" * len(consumo))

        ingredientes_info = banco.buscar(
            f"SELECT id, nome, estoque_atual FROM ingredientes WHERE id IN ({placeholders})",
            tuple(consumo.keys())
        )

        faltando = []

        for ingrediente_id, nome_ingrediente, estoque_atual in ingredientes_info:

            necessario = consumo[ingrediente_id]

            if necessario > estoque_atual:
                faltando.append(
                    f"{nome_ingrediente} (precisa de {necessario:g}, tem {estoque_atual:g})"
                )

        if not faltando:
            return True

        mensagem = (
            f"Para vender \"{nome_produto}\" falta estoque de ingrediente(s):\n\n"
            + "\n".join(faltando)
        )

        if config.bloquear_venda_sem_estoque_ingrediente():
            messagebox.showerror(
                "Estoque de ingredientes insuficiente",
                mensagem + "\n\nA venda está bloqueada nas Configurações "
                "enquanto o estoque não for reposto."
            )
            return False

        return messagebox.askyesno(
            "Estoque de ingredientes insuficiente",
            mensagem + "\n\nDeseja adicionar mesmo assim?"
        )

    # ======================================================

    def adicionar_item(self):

        if self.produto_selecionado is None:
            messagebox.showwarning(
                "Pedido",
                "Busque e selecione um produto antes de adicionar."
            )
            return

        produto = self.produto_selecionado

        try:
            qtd = int(self.quantidade.get())
        except ValueError:
            messagebox.showwarning("Pedido", "Quantidade inválida.")
            return

        if qtd <= 0:
            messagebox.showwarning("Pedido", "Quantidade deve ser maior que zero.")
            return

        # Soma quanto desse produto já está no carrinho, pra checar o
        # estoque considerando também o que ainda não foi finalizado.
        ja_no_carrinho = sum(
            item["qtd"] for item in self.itens
            if item["produto_id"] == produto["id"]
        )

        total_pedido = ja_no_carrinho + qtd

        if produto["estoque"] is not None and total_pedido > produto["estoque"]:

            continuar = messagebox.askyesno(
                "Estoque insuficiente",
                f"O produto \"{produto['nome']}\" tem apenas "
                f"{produto['estoque']} em estoque, mas o pedido ficaria "
                f"com {total_pedido}.\n\nDeseja adicionar mesmo assim?"
            )

            if not continuar:
                return

        # Confere também o estoque dos ingredientes da receita (se o
        # produto tiver uma), somando o que já está no carrinho — um
        # ingrediente pode ser usado por vários produtos diferentes.
        itens_simulados = self.itens + [{"produto_id": produto["id"], "qtd": qtd}]

        if not self.verificar_estoque_ingredientes(itens_simulados, produto["nome"]):
            return

        subtotal = qtd * produto["preco"]

        self.total += subtotal

        observacao = self.observacao_item.get().strip()

        # Guarda o item na lista real (fonte da verdade)
        self.itens.append({
            "produto_id": produto["id"],
            "nome": produto["nome"],
            "qtd": qtd,
            "valor_unitario": produto["preco"],
            "subtotal": subtotal,
            "observacao": observacao
        })

        self.tabela.insert(
            "",
            "end",
            values=(
                produto["nome"],
                observacao,
                qtd,
                f"R$ {produto['preco']:.2f}",
                f"R$ {subtotal:.2f}"
            )
        )

        self.atualizar_total()
        self.produto_selecionado = None
        self.lbl_produto_selecionado.configure(
            text="Nenhum produto selecionado",
            text_color="gray"
        )
        self.quantidade.delete(0, "end")
        self.quantidade.insert(0, "1")
        self.observacao_item.delete(0, "end")
        self.busca_produto.focus()

    # ======================================================

    def remover_item(self):

        selecionado = self.tabela.selection()

        if not selecionado:
            return

        indice = self.tabela.index(selecionado[0])

        item_removido = self.itens.pop(indice)
        self.total -= item_removido["subtotal"]

        self.tabela.delete(selecionado[0])

        self.atualizar_total()

    # ======================================================

    def limpar_pedido(self):

        # Pedido finalizado: não há mais o que restaurar numa próxima
        # visita à tela.
        pedido_rascunho.limpar()

        self.itens = []
        self.total = 0.0

        for linha in self.tabela.get_children():
            self.tabela.delete(linha)

        self.lbl_total.configure(text="TOTAL: R$ 0,00")

        self.valor_entrega.delete(0, "end")

        self.motoboy_combo.set(SEM_MOTOBOY)
        self.imprimir_cupom.select()

        self.selecionar_cliente_balcao()

        self.produto_selecionado = None
        self.lbl_produto_selecionado.configure(
            text="Nenhum produto selecionado",
            text_color="gray"
        )
        self.busca_produto.delete(0, "end")
        self.resultados_frame.pack_forget()

        self.quantidade.delete(0, "end")
        self.quantidade.insert(0, "1")
        self.observacao_item.delete(0, "end")

    # ======================================================

    def proximo_numero_pedido(self):

        resultado = banco.buscar_um(
            "SELECT MAX(numero) FROM pedidos"
        )

        maior = resultado[0] if resultado and resultado[0] else 0

        return maior + 1

    # ======================================================

    def gravar_pedido(self):
        """Grava o pedido e os itens no banco. Retorna o dicionário
        com os dados do pedido (usado depois para imprimir)."""

        nome_cliente = self.cliente_selecionado["nome"] if self.cliente_selecionado else "Cliente Balcão"
        cliente_id = self.cliente_selecionado["id"] if self.cliente_selecionado else None

        agora = datetime.now()
        data_str = agora.strftime("%d/%m/%Y")
        hora_str = agora.strftime("%H:%M")

        numero = self.proximo_numero_pedido()
        pagamento = self.pagamento.get()

        entrega = self.obter_valor_entrega()
        total_final = self.total + entrega
        motoboy_id = self.obter_motoboy_id()

        # Pedido + itens + baixa de estoque viram uma transação só: se
        # algo falhar no meio, desfaz tudo (rollback) em vez de deixar
        # um pedido gravado pela metade.

        try:
            banco.executar_sem_commit(
                """
                INSERT INTO pedidos
                    (numero, cliente_id, data, hora, subtotal,
                     desconto, acrescimo, total, pagamento, status, observacao, motoboy_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    numero, cliente_id, data_str, hora_str, self.total,
                    0.0, entrega, total_final, pagamento, "Finalizado", "", motoboy_id
                )
            )

            pedido_id = banco.ultimo_id()

            for item in self.itens:

                banco.executar_sem_commit(
                    """
                    INSERT INTO itens_pedido
                        (pedido_id, produto_id, quantidade, valor_unitario,
                         subtotal, observacao)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pedido_id, item["produto_id"], item["qtd"],
                        item["valor_unitario"], item["subtotal"],
                        item.get("observacao", "")
                    )
                )

                # Desconta o estoque vendido. Não deixa ficar negativo no banco.
                banco.executar_sem_commit(
                    """
                    UPDATE produtos
                    SET estoque = MAX(0, estoque - ?)
                    WHERE id = ?
                    """,
                    (item["qtd"], item["produto_id"])
                )

                # Desconta também os ingredientes da receita desse produto
                # (ex: vender 1 Pastel Bacon com Queijo abate 1 porção de
                # bacon + 1 de queijo), registrando o histórico de cada saída.
                receita = banco.buscar(
                    "SELECT ingrediente_id, quantidade FROM receita_produto WHERE produto_id=?",
                    (item["produto_id"],)
                )

                for ingrediente_id, quantidade_unitaria in receita:

                    quantidade_total = quantidade_unitaria * item["qtd"]

                    banco.executar_sem_commit(
                        """
                        UPDATE ingredientes
                        SET estoque_atual = MAX(0, estoque_atual - ?)
                        WHERE id = ?
                        """,
                        (quantidade_total, ingrediente_id)
                    )

                    banco.executar_sem_commit(
                        """
                        INSERT INTO movimentos_ingrediente
                            (ingrediente_id, tipo, quantidade, pedido_id, data, hora)
                        VALUES (?, 'saida', ?, ?, ?, ?)
                        """,
                        (ingrediente_id, quantidade_total, pedido_id, data_str, hora_str)
                    )

        except Exception:
            banco.rollback()
            raise

        banco.commit()

        # Atualiza o cache local de produtos pra já refletir o novo
        # estoque na próxima busca, sem precisar reabrir a tela.
        self.carregar_produtos()

        return {
            "numero": numero,
            "cliente": nome_cliente,
            "endereco_cliente": self.obter_endereco_cliente(cliente_id),
            "data": data_str,
            "hora": hora_str,
            "subtotal": self.total,
            "desconto": 0.0,
            "acrescimo": entrega,
            "total": total_final,
            "pagamento": pagamento,
            "observacao": ""
        }

    # ======================================================

    def obter_endereco_cliente(self, cliente_id):
        """Monta o endereço principal do cliente numa linha só, pro
        cupom — motoboy não pode ter que abrir o cadastro pra saber
        pra onde entregar. Cliente Balcão (sem cliente_id) ou cliente
        sem nenhum endereço cadastrado devolve string vazia."""

        if cliente_id is None:
            return ""

        endereco = banco.buscar_um(
            """
            SELECT endereco, numero, bairro, cidade
            FROM enderecos_cliente
            WHERE cliente_id=? AND principal=1
            """,
            (cliente_id,)
        )

        if not endereco:
            return ""

        rua, numero, bairro, cidade = endereco

        linha = ", ".join(p for p in (rua, numero) if p)
        complemento = " - ".join(p for p in (bairro, cidade) if p)

        if complemento:
            linha = f"{linha} - {complemento}" if linha else complemento

        return linha

    # ======================================================

    def finalizar(self):

        # Trava também aqui, não só no menu: se o caixa for fechado com
        # a tela de Pedidos já aberta, a venda não pode ser gravada —
        # ela entraria num dia/caixa que não está mais aberto.
        if not caixa_estado.esta_aberto():

            messagebox.showwarning(
                "Caixa fechado",
                "Nenhum caixa aberto no momento.\n\n"
                "Abra o caixa antes de finalizar pedidos."
            )

            return

        if len(self.itens) == 0:

            messagebox.showwarning(
                "Pedido",
                "Nenhum produto foi adicionado."
            )

            return

        try:
            pedido_dados = self.gravar_pedido()

        except Exception as erro:

            messagebox.showerror(
                "Erro ao gravar pedido",
                f"Não foi possível salvar o pedido no banco:\n\n{erro}"
            )

            return

        if not self.imprimir_cupom.get():

            messagebox.showinfo(
                "Los Manager",
                f"Pedido Nº {pedido_dados['numero']:04d} salvo sem impressão do cupom."
            )

            self.limpar_pedido()
            return

        # -------- Tenta imprimir; se falhar, avisa mas NÃO perde o pedido --------
        # (o pedido já foi salvo no banco mesmo se a impressora falhar)

        try:
            dados_loja = config.obter_dados_loja()
            impressora.imprimir_cupom(dados_loja, pedido_dados, self.itens)

            messagebox.showinfo(
                "Los Manager",
                f"Pedido Nº {pedido_dados['numero']:04d} salvo e enviado para impressão!"
            )

        except Exception as erro:

            messagebox.showwarning(
                "Pedido salvo, mas houve erro ao imprimir",
                f"O pedido Nº {pedido_dados['numero']:04d} foi salvo normalmente, "
                f"mas não foi possível imprimir o cupom:\n\n{erro}\n\n"
                "Verifique se a impressora está ligada, instalada no Windows "
                "e se o nome em utils/impressora.py está correto."
            )

        self.limpar_pedido()
