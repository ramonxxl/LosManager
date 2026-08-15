import customtkinter as ctk
from tkinter import ttk, messagebox
from database.conexao import banco
from utils import tema
from utils import responsivo
from repositorios import produtos as repositorio_produtos


class Produtos(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)

        self.pack(fill="both", expand=True, padx=20, pady=20)

        # Tudo fica dentro de um frame com rolagem: em telas menores
        # (notebooks antigos, resolução baixa) o conteúdo não cabia
        # inteiro na altura da janela e não tinha como rolar pra ver
        # os botões/tabela de baixo.
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        titulo = ctk.CTkLabel(
            self.scroll,
            text="Cadastro de Produtos",
            font=("Arial", 30, "bold")
        )
        titulo.pack(pady=(10, 20))

        filtro_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        filtro_frame.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(
            filtro_frame,
            text="🔍 Filtrar por"
        ).pack(side="left", padx=(0, 10))

        self.campo_filtro = ctk.CTkComboBox(
            filtro_frame,
            values=["Nome", "ID", "Preço"],
            width=110,
            command=lambda valor: self.carregar()
        )
        self.campo_filtro.set("Nome")
        self.campo_filtro.pack(side="left", padx=(0, 10))

        self.busca = ctk.CTkEntry(
            filtro_frame,
            width=280,
            placeholder_text="Digite para buscar..."
        )
        self.busca.pack(side="left")
        self.busca.bind("<KeyRelease>", lambda evento: self.carregar())

        ctk.CTkButton(
            filtro_frame,
            text="Limpar filtro",
            width=120,
            command=self.limpar_filtro
        ).pack(side="left", padx=10)

        formulario = ctk.CTkFrame(self.scroll)
        formulario.pack(fill="x", padx=20)

        ctk.CTkLabel(formulario, text="Nome").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.nome = ctk.CTkEntry(formulario, width=250)
        self.nome.grid(row=0, column=1, padx=10)

        ctk.CTkLabel(formulario, text="Categoria").grid(row=0, column=2, padx=10, pady=10)
        self.categoria = ctk.CTkEntry(formulario, width=180)
        self.categoria.grid(row=0, column=3, padx=10)

        ctk.CTkLabel(formulario, text="Preço").grid(row=1, column=0, padx=10, pady=10)
        self.preco = ctk.CTkEntry(formulario, width=120)
        self.preco.grid(row=1, column=1, padx=10)

        ctk.CTkLabel(formulario, text="Estoque").grid(row=1, column=2, padx=10, pady=10)
        self.estoque = ctk.CTkEntry(formulario, width=120)
        self.estoque.grid(row=1, column=3, padx=10)

        botoes_form = ctk.CTkFrame(formulario, fg_color="transparent")
        botoes_form.grid(row=2, column=0, columnspan=4, pady=20)

        self.btn_salvar = ctk.CTkButton(
            botoes_form,
            text="Salvar Produto",
            fg_color=tema.COR_LARANJA,
            hover_color=tema.COR_LARANJA_ESCURO,
            command=self.salvar
        )
        self.btn_salvar.pack(side="left", padx=(0, 10))

        self.btn_cancelar = ctk.CTkButton(
            botoes_form,
            text="Cancelar edição",
            fg_color="gray40",
            hover_color="gray30",
            command=self.cancelar_edicao
        )
        # Só aparece quando estiver editando um produto existente

        ctk.CTkButton(
            botoes_form,
            text="✏️ Editar Selecionado",
            fg_color=tema.COR_LARANJA_ESCURO,
            hover_color="#A85D08",
            command=self.carregar_para_edicao
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            botoes_form,
            text="🧂 Receita do Produto Selecionado",
            fg_color=tema.COR_TEXTO_CLARO,
            hover_color=tema.COR_TEXTO,
            command=self.abrir_receita
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            botoes_form,
            text="🗑 Excluir Produto Selecionado",
            fg_color=tema.COR_VERMELHO,
            hover_color="#B93601",
            command=self.excluir_produto
        ).pack(side="left", padx=10)

        self.produto_id_editando = None

        dica = ctk.CTkLabel(
            self.scroll,
            text="Dica: selecione um produto na lista e use os botões acima "
                 "para editar ou excluir. Dê dois cliques numa linha "
                 "para ativar/desativar o produto sem excluir.",
            font=("Arial", 12),
            text_color="gray"
        )
        dica.pack(anchor="w", padx=20, pady=(0, 5))

        linhas = responsivo.linhas_para_tabela(self, self.scroll, pady_tabela=20)

        self.tabela = ttk.Treeview(
            self.scroll,
            columns=("id", "nome", "categoria", "preco", "estoque", "ativo"),
            show="headings",
            height=linhas
        )

        self.tabela.heading("id", text="ID")
        self.tabela.heading("nome", text="Nome")
        self.tabela.heading("categoria", text="Categoria")
        self.tabela.heading("preco", text="Preço")
        self.tabela.heading("estoque", text="Estoque")
        self.tabela.heading("ativo", text="Ativo")

        self.tabela.column("id", width=60)
        self.tabela.column("nome", width=250)
        self.tabela.column("categoria", width=180)
        self.tabela.column("preco", width=100)
        self.tabela.column("estoque", width=100)
        self.tabela.column("ativo", width=80, anchor="center")

        self.tabela.pack(fill="both", expand=True, padx=20, pady=20)

        self.tabela.bind("<Double-1>", self.alternar_ativo)

        responsivo.tornar_dinamica(self, self.scroll, lambda: self.tabela, pady_tabela=20)

        self.carregar()

    def salvar(self):

        nome = self.nome.get().strip()
        categoria = self.categoria.get().strip()
        preco_texto = self.preco.get().strip()
        estoque_texto = self.estoque.get().strip()

        try:

            if self.produto_id_editando is not None:

                repositorio_produtos.atualizar(
                    self.produto_id_editando, nome, categoria, preco_texto, estoque_texto
                )

                self.produto_id_editando = None
                self.btn_salvar.configure(text="Salvar Produto")
                self.btn_cancelar.pack_forget()

            else:

                repositorio_produtos.criar(nome, categoria, preco_texto, estoque_texto)

        except repositorio_produtos.ProdutoInvalido as erro:
            messagebox.showwarning("Produtos", str(erro))
            return

        self.limpar_formulario()
        self.carregar()

    # ======================================================
    # EDITAR / CANCELAR EDIÇÃO
    # ======================================================

    def carregar_para_edicao(self):

        selecionado = self.tabela.selection()

        if not selecionado:
            messagebox.showwarning(
                "Produtos",
                "Selecione um produto na lista para editar."
            )
            return

        valores = self.tabela.item(selecionado[0], "values")
        produto_id = valores[0]

        registro = repositorio_produtos.obter(produto_id)

        if not registro:
            return

        nome, categoria, preco, estoque = registro

        self.produto_id_editando = produto_id

        self.nome.delete(0, "end")
        self.nome.insert(0, nome or "")

        self.categoria.delete(0, "end")
        self.categoria.insert(0, categoria or "")

        self.preco.delete(0, "end")
        self.preco.insert(0, str(preco).replace(".", ","))

        self.estoque.delete(0, "end")
        self.estoque.insert(0, str(estoque))

        self.btn_salvar.configure(text="Atualizar Produto")
        self.btn_cancelar.pack(side="left", padx=10)

        self.nome.focus()

    # ======================================================

    def abrir_receita(self):

        selecionado = self.tabela.selection()

        if not selecionado:
            messagebox.showwarning(
                "Produtos",
                "Selecione um produto na lista para editar a receita."
            )
            return

        valores = self.tabela.item(selecionado[0], "values")
        produto_id = valores[0]
        nome = valores[1]

        JanelaReceita(self, produto_id, nome)

    # ======================================================

    def cancelar_edicao(self):

        self.produto_id_editando = None
        self.limpar_formulario()

        self.btn_salvar.configure(text="Salvar Produto")
        self.btn_cancelar.pack_forget()

    # ======================================================

    def limpar_formulario(self):

        self.nome.delete(0, "end")
        self.categoria.delete(0, "end")
        self.preco.delete(0, "end")
        self.estoque.delete(0, "end")

    # ======================================================

    def limpar_filtro(self):

        self.busca.delete(0, "end")
        self.campo_filtro.set("Nome")
        self.carregar()

    def carregar(self):

        for item in self.tabela.get_children():
            self.tabela.delete(item)

        termo = self.busca.get().strip()
        campo = self.campo_filtro.get()

        produtos = repositorio_produtos.listar(termo, campo)

        for produto_id, nome, categoria, preco, estoque, ativo in produtos:
            self.tabela.insert(
                "", "end",
                values=(
                    produto_id, nome, categoria, preco, estoque,
                    "Sim" if ativo else "Não"
                )
            )

    # ======================================================

    def excluir_produto(self):

        selecionado = self.tabela.selection()

        if not selecionado:
            messagebox.showwarning(
                "Produtos",
                "Selecione um produto na lista para excluir."
            )
            return

        valores = self.tabela.item(selecionado[0], "values")
        produto_id = valores[0]
        nome = valores[1]

        confirmar = messagebox.askyesno(
            "Excluir Produto",
            f"Tem certeza que deseja excluir \"{nome}\"?"
        )

        if not confirmar:
            return

        resultado = repositorio_produtos.excluir(produto_id)

        if resultado == "desativado":
            messagebox.showinfo(
                "Produtos",
                f"\"{nome}\" já foi vendido antes, então ele foi apenas "
                "DESATIVADO (some das telas de novo pedido), para manter "
                "o histórico de vendas intacto."
            )
        else:
            messagebox.showinfo(
                "Produtos",
                f"\"{nome}\" foi excluído definitivamente."
            )

        self.carregar()

    # ======================================================

    def alternar_ativo(self, evento=None):

        selecionado = self.tabela.selection()

        if not selecionado:
            return

        valores = self.tabela.item(selecionado[0], "values")
        produto_id = valores[0]
        nome = valores[1]

        novo_status = repositorio_produtos.alternar_ativo(produto_id)

        acao = "desativado" if novo_status == 0 else "ativado"
        messagebox.showinfo("Produtos", f"\"{nome}\" foi {acao}.")

        self.carregar()


# ==========================================================
# JANELA DE RECEITA (ficha técnica) DE UM PRODUTO
# ==========================================================

class JanelaReceita(ctk.CTkToplevel):
    """Lista/edita os ingredientes que compõem um produto (ex: Pastel
    Bacon com Queijo = 1 porção de Bacon + 1 porção de Queijo). Cada
    ingrediente da receita fica em `receita_produto`, na unidade de
    medida já cadastrada no próprio ingrediente."""

    def __init__(self, master, produto_id, nome_produto):
        super().__init__(master)

        self.produto_id = produto_id

        self.title(f"Receita — {nome_produto}")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        # Frame com rolagem: em telas pequenas (notebooks antigos) o
        # conteúdo dessa janela pode não caber inteiro na altura
        # disponível da tela.
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self.scroll,
            text=f"Receita de \"{nome_produto}\"",
            font=("Arial", 20, "bold")
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            self.scroll,
            text="Quando esse produto for vendido, cada ingrediente abaixo é\n"
                 "descontado do estoque na quantidade informada.",
            font=("Arial", 12),
            text_color="gray",
            justify="center"
        ).pack(pady=(0, 10))

        formulario = ctk.CTkFrame(self.scroll)
        formulario.pack(fill="x", padx=15)

        ctk.CTkLabel(formulario, text="Ingrediente").grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.combo_ingrediente = ctk.CTkComboBox(formulario, width=260, values=[])
        self.combo_ingrediente.grid(row=0, column=1, padx=10)

        ctk.CTkLabel(formulario, text="Qtd.").grid(row=0, column=2, padx=(15, 5), pady=10)

        self.quantidade = ctk.CTkEntry(formulario, width=80)
        self.quantidade.grid(row=0, column=3, padx=5)

        botoes_form = ctk.CTkFrame(self.scroll, fg_color="transparent")
        botoes_form.pack(pady=(5, 10))

        self.btn_adicionar = ctk.CTkButton(
            botoes_form,
            text="Adicionar à Receita",
            fg_color=tema.COR_LARANJA,
            hover_color=tema.COR_LARANJA_ESCURO,
            command=self.adicionar
        )
        self.btn_adicionar.pack(side="left", padx=(0, 10))

        self.btn_cancelar_edicao = ctk.CTkButton(
            botoes_form,
            text="Cancelar edição",
            fg_color="gray40",
            hover_color="gray30",
            command=self.cancelar_edicao
        )
        # Só aparece quando um ingrediente da lista está selecionado para edição

        self.receita_id_editando = None

        dica_edicao = ctk.CTkLabel(
            self.scroll,
            text="Dica: clique numa linha da lista abaixo para carregar ela nos "
                 "campos acima e corrigir a quantidade, ou use o botão vermelho "
                 "no final da janela para remover essa linha da receita.",
            font=("Arial", 12),
            text_color="gray",
            wraplength=500,
            justify="center"
        )
        dica_edicao.pack(pady=(0, 5))

        self.tabela = ttk.Treeview(
            self.scroll,
            columns=("id", "ingrediente", "quantidade", "unidade"),
            show="headings",
            height=10
        )

        self.tabela.heading("ingrediente", text="Ingrediente")
        self.tabela.heading("quantidade", text="Quantidade")
        self.tabela.heading("unidade", text="Unidade")

        # Coluna "id" fica fora de displaycolumns: guarda o id da linha
        # sem mostrar na tela (é só pra saber o que remover depois).
        self.tabela["displaycolumns"] = ("ingrediente", "quantidade", "unidade")

        self.tabela.column("ingrediente", width=260)
        self.tabela.column("quantidade", width=110, anchor="e")
        self.tabela.column("unidade", width=100, anchor="center")

        self.tabela.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self.tabela.bind("<<TreeviewSelect>>", self.carregar_para_edicao)

        ctk.CTkButton(
            self.scroll,
            text="🗑 Remover Ingrediente Selecionado",
            fg_color=tema.COR_VERMELHO,
            hover_color="#B93601",
            command=self.remover
        ).pack(pady=(0, 15))

        self.carregar_ingredientes_disponiveis()
        self.carregar()

        # O CTkToplevel do customtkinter ignora um geometry() chamado
        # direto no __init__ (faz uma dança interna de cor da barra de
        # título no Windows que reseta o tamanho logo em seguida) — um
        # pequeno atraso deixa isso assentar antes de aplicar o
        # tamanho de verdade.
        self.after(60, self._ajustar_tamanho)

    # ======================================================

    def _ajustar_tamanho(self):
        """Calcula o tamanho pelo conteúdo real (em vez de um valor
        fixo chutado), limitado ao tamanho da tela — em telas pequenas
        o conteúdo continua acessível rolando dentro do self.scroll."""

        self.update_idletasks()

        # max() aqui garante que o teto nunca fique menor que o piso
        # mínimo usável, mesmo se winfo_screenwidth/height vier com um
        # valor inesperadamente pequeno (evita uma janela minúscula).
        largura_maxima = max(int(self.winfo_screenwidth() * 0.9), 580)
        altura_maxima = max(int(self.winfo_screenheight() * 0.85), 450)

        largura = min(max(self.winfo_reqwidth() + 30, 580), largura_maxima)
        altura = min(max(self.winfo_reqheight() + 40, 450), altura_maxima)

        self.geometry(f"{largura}x{altura}")
        self.minsize(min(580, largura_maxima), min(400, altura_maxima))

    # ======================================================

    def carregar_ingredientes_disponiveis(self):

        self.ingredientes_cache = banco.buscar(
            "SELECT id, nome, unidade_medida FROM ingredientes WHERE ativo=1 ORDER BY nome"
        )

        nomes = [i[1] for i in self.ingredientes_cache]

        self.combo_ingrediente.configure(values=nomes)

        if nomes:
            self.combo_ingrediente.set(nomes[0])
        else:
            self.combo_ingrediente.set("")
            messagebox.showinfo(
                "Receita",
                "Nenhum ingrediente cadastrado ainda. Cadastre ingredientes "
                "na aba \"Ingredientes\" antes de montar a receita."
            )

    # ======================================================

    def adicionar(self):

        nome_escolhido = self.combo_ingrediente.get()

        ingrediente = next(
            (i for i in self.ingredientes_cache if i[1] == nome_escolhido),
            None
        )

        if ingrediente is None:
            messagebox.showwarning("Receita", "Selecione um ingrediente válido.")
            return

        try:
            quantidade = float(self.quantidade.get().strip().replace(",", "."))
        except ValueError:
            messagebox.showwarning("Receita", "Quantidade inválida. Use números, ex: 1 ou 0,5")
            return

        if quantidade <= 0:
            messagebox.showwarning("Receita", "Quantidade deve ser maior que zero.")
            return

        ingrediente_id = ingrediente[0]

        ja_existe = banco.buscar_um(
            "SELECT id FROM receita_produto WHERE produto_id=? AND ingrediente_id=?",
            (self.produto_id, ingrediente_id)
        )

        if ja_existe:
            banco.executar(
                "UPDATE receita_produto SET quantidade=? WHERE id=?",
                (quantidade, ja_existe[0])
            )
        else:
            banco.executar(
                """
                INSERT INTO receita_produto (produto_id, ingrediente_id, quantidade)
                VALUES (?, ?, ?)
                """,
                (self.produto_id, ingrediente_id, quantidade)
            )

        self.quantidade.delete(0, "end")
        self.receita_id_editando = None
        self.btn_adicionar.configure(text="Adicionar à Receita")
        self.btn_cancelar_edicao.pack_forget()
        self.carregar()

    # ======================================================

    def carregar_para_edicao(self, evento=None):

        selecionado = self.tabela.selection()

        if not selecionado:
            return

        valores = self.tabela.item(selecionado[0], "values")
        receita_id, nome_ingrediente, quantidade, _unidade = valores

        self.receita_id_editando = receita_id

        self.combo_ingrediente.set(nome_ingrediente)

        self.quantidade.delete(0, "end")
        self.quantidade.insert(0, str(quantidade).replace(".", ","))

        self.btn_adicionar.configure(text="Atualizar Ingrediente")
        self.btn_cancelar_edicao.pack(side="left")

    # ======================================================

    def cancelar_edicao(self):

        self.receita_id_editando = None

        self.quantidade.delete(0, "end")

        self.btn_adicionar.configure(text="Adicionar à Receita")
        self.btn_cancelar_edicao.pack_forget()

        self.tabela.selection_remove(self.tabela.selection())

    # ======================================================

    def remover(self):

        selecionado = self.tabela.selection()

        if not selecionado:
            messagebox.showwarning("Receita", "Selecione um ingrediente da receita para remover.")
            return

        valores = self.tabela.item(selecionado[0], "values")
        receita_id, nome_ingrediente, _quantidade, _unidade = valores

        confirmar = messagebox.askyesno(
            "Remover da Receita",
            f"Remover \"{nome_ingrediente}\" da receita deste produto?\n\n"
            "Isso só tira o ingrediente DESSA receita — o cadastro do "
            "ingrediente em si continua existindo normalmente na aba "
            "\"Ingredientes\" e em qualquer outra receita que o use."
        )

        if not confirmar:
            return

        banco.executar("DELETE FROM receita_produto WHERE id=?", (receita_id,))

        if receita_id == self.receita_id_editando:
            self.cancelar_edicao()

        self.carregar()

        messagebox.showinfo("Receita", f"\"{nome_ingrediente}\" foi removido da receita.")

    # ======================================================

    def carregar(self):

        for item in self.tabela.get_children():
            self.tabela.delete(item)

        linhas = banco.buscar(
            """
            SELECT r.id, i.nome, r.quantidade, i.unidade_medida
            FROM receita_produto r
            JOIN ingredientes i ON i.id = r.ingrediente_id
            WHERE r.produto_id=?
            ORDER BY i.nome
            """,
            (self.produto_id,)
        )

        for receita_id, nome_ingrediente, quantidade, unidade in linhas:
            self.tabela.insert(
                "", "end",
                values=(receita_id, nome_ingrediente, f"{quantidade:g}", unidade)
            )