import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import datetime

import sys
import webbrowser

from utils import config
from utils import impressora
from utils import tema
from utils import atualizacao
from utils import autoatualizador
from repositorios import motoboys as repositorio_motoboys


class Configuracoes(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)

        self.pack(fill="both", expand=True, padx=15, pady=12)

        # Tudo fica dentro de um frame com rolagem: em telas menores
        # (notebooks antigos, resolução baixa) o conteúdo desta tela
        # não cabe inteiro na altura da janela — sem isso, os botões
        # de baixo ficavam inacessíveis, sem nenhuma barra de rolagem.
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        titulo = ctk.CTkLabel(
            self.scroll,
            text="Configurações",
            font=("Arial", 24, "bold")
        )
        titulo.pack(pady=(6, 12))

        # =========================================================
        # DADOS DA LOJA
        # =========================================================

        bloco_loja = ctk.CTkFrame(self.scroll)
        bloco_loja.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            bloco_loja,
            text="Dados da Loja (aparecem no topo do cupom)",
            font=("Arial", 14, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 6))

        ctk.CTkLabel(bloco_loja, text="Nome da loja").grid(
            row=1, column=0, sticky="w", padx=15, pady=4
        )
        self.loja_nome = ctk.CTkEntry(bloco_loja, width=350, height=26)
        self.loja_nome.grid(row=1, column=1, padx=15, pady=4, sticky="w")

        ctk.CTkLabel(bloco_loja, text="Endereço").grid(
            row=2, column=0, sticky="w", padx=15, pady=4
        )
        self.loja_endereco = ctk.CTkEntry(bloco_loja, width=350, height=26)
        self.loja_endereco.grid(row=2, column=1, padx=15, pady=4, sticky="w")

        ctk.CTkLabel(bloco_loja, text="Telefone").grid(
            row=3, column=0, sticky="w", padx=15, pady=(4, 8)
        )
        self.loja_telefone = ctk.CTkEntry(bloco_loja, width=350, height=26)
        self.loja_telefone.grid(row=3, column=1, padx=15, pady=(4, 8), sticky="w")

        # =========================================================
        # IMPRESSORA
        # =========================================================

        bloco_impressora = ctk.CTkFrame(self.scroll)
        bloco_impressora.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            bloco_impressora,
            text="Impressora Térmica",
            font=("Arial", 14, "bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 6))

        ctk.CTkLabel(bloco_impressora, text="Impressora instalada").grid(
            row=1, column=0, sticky="w", padx=15, pady=4
        )

        self.combo_impressoras = ctk.CTkComboBox(
            bloco_impressora,
            width=350,
            height=26,
            values=["(clique em Atualizar lista)"]
        )
        self.combo_impressoras.grid(row=1, column=1, padx=15, pady=4, sticky="w")

        ctk.CTkButton(
            bloco_impressora,
            text="🔄 Atualizar lista",
            width=150,
            height=26,
            fg_color=tema.COR_LARANJA,
            hover_color=tema.COR_LARANJA_ESCURO,
            command=self.atualizar_lista_impressoras
        ).grid(row=1, column=2, padx=15, pady=4)

        ctk.CTkLabel(bloco_impressora, text="Tamanho do papel").grid(
            row=2, column=0, sticky="w", padx=15, pady=(4, 8)
        )

        self.papel = ctk.CTkSegmentedButton(
            bloco_impressora,
            height=26,
            values=["58mm (32 col.)", "80mm (48 col.)"]
        )
        self.papel.set("58mm (32 col.)")
        self.papel.grid(row=2, column=1, padx=15, pady=(4, 8), sticky="w")

        # =========================================================
        # ESTOQUE DE INGREDIENTES
        # =========================================================

        bloco_ingredientes = ctk.CTkFrame(self.scroll)
        bloco_ingredientes.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            bloco_ingredientes,
            text="Estoque de Ingredientes",
            font=("Arial", 14, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 6))

        self.bloquear_estoque_ingrediente = ctk.CTkSwitch(
            bloco_ingredientes,
            text="Bloquear a venda quando faltar ingrediente no estoque",
            onvalue="1",
            offvalue="0"
        )
        self.bloquear_estoque_ingrediente.grid(
            row=1, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 4)
        )

        ctk.CTkLabel(
            bloco_ingredientes,
            text="Desligado (padrão): o sistema só avisa que falta ingrediente e\n"
                 "deixa continuar a venda mesmo assim, igual já acontece hoje\n"
                 "com o estoque de produto.",
            font=("Arial", 11),
            text_color="gray",
            justify="left"
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 8))

        # =========================================================
        # PROGRAMA DE FIDELIDADE
        # =========================================================

        bloco_fidelidade = ctk.CTkFrame(self.scroll)
        bloco_fidelidade.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            bloco_fidelidade,
            text="Programa de Fidelidade",
            font=("Arial", 14, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 6))

        ctk.CTkLabel(bloco_fidelidade, text="Pedidos para ganhar 1 recompensa").grid(
            row=1, column=0, sticky="w", padx=15, pady=(4, 4)
        )

        self.fidelidade_meta = ctk.CTkEntry(bloco_fidelidade, width=80, height=26)
        self.fidelidade_meta.grid(row=1, column=1, padx=15, pady=(4, 4), sticky="w")

        ctk.CTkLabel(
            bloco_fidelidade,
            text="A cada esse número de pedidos concluídos, o cliente ganha 1 pastel\n"
                 "grátis (cumulativo: o dobro dos pedidos dá 2 recompensas, e assim\n"
                 "por diante). Gerencie clientes e resgates na tela \"🎁 Fidelidade\".",
            font=("Arial", 11),
            text_color="gray",
            justify="left"
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 8))

        # =========================================================
        # MOTOBOYS (cadastro usado no combobox de Pedidos e na
        # tabela de taxa por motoboy dos Relatórios)
        # =========================================================

        bloco_motoboys = ctk.CTkFrame(self.scroll)
        bloco_motoboys.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            bloco_motoboys,
            text="Motoboys",
            font=("Arial", 14, "bold")
        ).pack(anchor="w", padx=15, pady=(10, 6))

        ctk.CTkLabel(
            bloco_motoboys,
            text="Cadastrados aqui, aparecem no combobox de \"Novo Pedido\" e "
                 "permitem ver a taxa de entrega separada por motoboy em "
                 "Relatórios.",
            font=("Arial", 11),
            text_color="gray",
            justify="left"
        ).pack(anchor="w", padx=15, pady=(0, 8))

        linha_motoboy = ctk.CTkFrame(bloco_motoboys, fg_color="transparent")
        linha_motoboy.pack(fill="x", padx=15, pady=(0, 8))

        self.novo_motoboy = ctk.CTkEntry(
            linha_motoboy, width=250, height=26, placeholder_text="Nome do motoboy"
        )
        self.novo_motoboy.pack(side="left", padx=(0, 10))
        self.novo_motoboy.bind("<Return>", lambda evento: self.adicionar_motoboy())

        ctk.CTkButton(
            linha_motoboy,
            text="➕ Adicionar",
            width=120,
            height=26,
            fg_color=tema.COR_LARANJA,
            hover_color=tema.COR_LARANJA_ESCURO,
            command=self.adicionar_motoboy
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            linha_motoboy,
            text="🗑 Remover selecionado",
            width=170,
            height=26,
            fg_color=tema.COR_VERMELHO,
            hover_color="#B93601",
            command=self.remover_motoboy
        ).pack(side="left")

        self.tabela_motoboys = ttk.Treeview(
            bloco_motoboys,
            columns=("id", "nome", "ativo"),
            show="headings",
            height=4
        )
        self.tabela_motoboys.heading("nome", text="Nome")
        self.tabela_motoboys.heading("ativo", text="Ativo")
        self.tabela_motoboys["displaycolumns"] = ("nome", "ativo")
        self.tabela_motoboys.column("nome", width=250)
        self.tabela_motoboys.column("ativo", width=80, anchor="center")
        self.tabela_motoboys.pack(fill="x", padx=15, pady=(0, 6))
        self.tabela_motoboys.bind("<Double-1>", self.alternar_ativo_motoboy)

        ctk.CTkLabel(
            bloco_motoboys,
            text="Dois cliques numa linha ativa/desativa o motoboy sem excluir "
                 "(some do combobox de Pedidos, mas fica no histórico).",
            font=("Arial", 11),
            text_color="gray",
            justify="left"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        # =========================================================
        # SEGURANÇA
        # =========================================================

        bloco_seguranca = ctk.CTkFrame(self.scroll)
        bloco_seguranca.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            bloco_seguranca,
            text="Segurança",
            font=("Arial", 14, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 6))

        ctk.CTkLabel(
            bloco_seguranca,
            text="Senha para zerar relatórios"
        ).grid(row=1, column=0, sticky="w", padx=15, pady=(4, 4))

        self.senha_reset = ctk.CTkEntry(bloco_seguranca, width=200, height=26, show="•")
        self.senha_reset.grid(row=1, column=1, padx=15, pady=(4, 4), sticky="w")

        ctk.CTkLabel(
            bloco_seguranca,
            text="Essa senha é pedida sempre que alguém tentar apagar\n"
                 "os pedidos/relatórios na tela de Relatórios.",
            font=("Arial", 11),
            text_color="gray",
            justify="left"
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 8))

        # =========================================================
        # ATUALIZAÇÕES
        # =========================================================

        bloco_atualizacao = ctk.CTkFrame(self.scroll)
        bloco_atualizacao.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            bloco_atualizacao,
            text="Atualizações do Sistema",
            font=("Arial", 14, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 6))

        ctk.CTkLabel(bloco_atualizacao, text="Repositório no GitHub").grid(
            row=1, column=0, sticky="w", padx=15, pady=(4, 4)
        )

        self.repo_atualizacao = ctk.CTkEntry(bloco_atualizacao, width=350, height=26)
        self.repo_atualizacao.grid(row=1, column=1, padx=15, pady=(4, 4), sticky="w")

        ctk.CTkLabel(
            bloco_atualizacao,
            text="Formato \"usuario/repositorio\", ex: ramonxxl/LosManager.\n"
                 "É onde o programa procura e baixa novas versões sozinho.",
            font=("Arial", 11),
            text_color="gray",
            justify="left"
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 8))

        # =========================================================
        # BOTÕES DE AÇÃO
        # =========================================================

        acoes = ctk.CTkFrame(self.scroll, fg_color="transparent")
        acoes.pack(fill="x", padx=10, pady=8)

        ctk.CTkButton(
            acoes,
            text="💾 Salvar Configurações",
            width=220,
            height=34,
            fg_color=tema.COR_VERDE,
            hover_color="#1F6B40",
            command=self.salvar
        ).pack(side="left", padx=(5, 10))

        ctk.CTkButton(
            acoes,
            text="🖨 Imprimir Cupom de Teste",
            width=220,
            height=34,
            fg_color=tema.COR_LARANJA,
            hover_color=tema.COR_LARANJA_ESCURO,
            command=self.imprimir_teste
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            acoes,
            text="🗄 Fazer Backup Agora",
            width=220,
            height=34,
            fg_color=tema.COR_TEXTO_CLARO,
            hover_color=tema.COR_TEXTO,
            command=self.fazer_backup_manual
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            acoes,
            text="🔄 Verificar Atualização",
            width=220,
            height=34,
            fg_color=tema.COR_TEXTO_CLARO,
            hover_color=tema.COR_TEXTO,
            command=self.verificar_atualizacao_manual
        ).pack(side="left", padx=10)

        self.lbl_status = ctk.CTkLabel(self.scroll, text="", font=("Arial", 13))
        self.lbl_status.pack(pady=(4, 0))

        # =========================================================
        # RODAPÉ - VERSÃO E CRÉDITOS
        # =========================================================

        rodape = ctk.CTkFrame(self.scroll, fg_color="transparent")
        rodape.pack(fill="x", pady=(10, 4))

        ctk.CTkLabel(
            rodape,
            text=atualizacao.texto_versao(),
            font=("Arial", 12, "bold"),
            text_color=tema.COR_TEXTO_CLARO
        ).pack()

        ctk.CTkLabel(
            rodape,
            text="Desenvolvido por Ramon Oliveira",
            font=("Arial", 11),
            text_color=tema.COR_TEXTO_CLARO
        ).pack()

        self.carregar()

    # ======================================================

    def carregar(self):
        """Carrega os valores salvos no banco pros campos da tela."""

        self.loja_nome.delete(0, "end")
        self.loja_nome.insert(0, config.obter("loja_nome"))

        self.loja_endereco.delete(0, "end")
        self.loja_endereco.insert(0, config.obter("loja_endereco"))

        self.loja_telefone.delete(0, "end")
        self.loja_telefone.insert(0, config.obter("loja_telefone"))

        largura_salva = config.obter_largura_papel()
        self.papel.set("80mm (48 col.)" if largura_salva == 48 else "58mm (32 col.)")

        if config.bloquear_venda_sem_estoque_ingrediente():
            self.bloquear_estoque_ingrediente.select()
        else:
            self.bloquear_estoque_ingrediente.deselect()

        self.fidelidade_meta.delete(0, "end")
        self.fidelidade_meta.insert(0, str(config.obter_meta_fidelidade()))

        self.senha_reset.delete(0, "end")
        self.senha_reset.insert(0, config.obter("senha_reset"))

        self.repo_atualizacao.delete(0, "end")
        self.repo_atualizacao.insert(0, config.obter("repo_atualizacao", atualizacao.REPOSITORIO_PADRAO))

        impressora_salva = config.obter_impressora_nome()

        if impressora_salva:
            self.combo_impressoras.configure(values=[impressora_salva])
            self.combo_impressoras.set(impressora_salva)

        self.carregar_motoboys()

    # ======================================================
    # MOTOBOYS
    # ======================================================

    def carregar_motoboys(self):

        for linha in self.tabela_motoboys.get_children():
            self.tabela_motoboys.delete(linha)

        for motoboy_id, nome, ativo in repositorio_motoboys.listar():
            self.tabela_motoboys.insert(
                "", "end",
                values=(motoboy_id, nome, "Sim" if ativo else "Não")
            )

    def adicionar_motoboy(self):

        try:
            repositorio_motoboys.criar(self.novo_motoboy.get())
        except repositorio_motoboys.MotoboyInvalido as erro:
            messagebox.showwarning("Motoboys", str(erro))
            return

        self.novo_motoboy.delete(0, "end")
        self.carregar_motoboys()

    def alternar_ativo_motoboy(self, evento=None):

        selecionado = self.tabela_motoboys.selection()

        if not selecionado:
            return

        valores = self.tabela_motoboys.item(selecionado[0], "values")
        motoboy_id, nome = valores[0], valores[1]

        novo_status = repositorio_motoboys.alternar_ativo(motoboy_id)

        acao = "desativado" if novo_status == 0 else "ativado"
        messagebox.showinfo("Motoboys", f"\"{nome}\" foi {acao}.")

        self.carregar_motoboys()

    def remover_motoboy(self):

        selecionado = self.tabela_motoboys.selection()

        if not selecionado:
            messagebox.showwarning(
                "Motoboys",
                "Selecione um motoboy na lista para remover."
            )
            return

        valores = self.tabela_motoboys.item(selecionado[0], "values")
        motoboy_id, nome = valores[0], valores[1]

        confirmar = messagebox.askyesno(
            "Remover Motoboy",
            f"Tem certeza que deseja remover \"{nome}\"?"
        )

        if not confirmar:
            return

        resultado = repositorio_motoboys.excluir(motoboy_id)

        if resultado == "desativado":
            messagebox.showinfo(
                "Motoboys",
                f"\"{nome}\" já aparece em pedidos anteriores, então foi apenas "
                "DESATIVADO (some do combobox de Pedidos), para manter o "
                "histórico intacto."
            )
        else:
            messagebox.showinfo("Motoboys", f"\"{nome}\" foi removido.")

        self.carregar_motoboys()

    # ======================================================

    def atualizar_lista_impressoras(self):
        """Consulta o Windows e lista as impressoras instaladas."""

        try:
            lista = impressora.listar_impressoras()

        except Exception as erro:

            messagebox.showerror(
                "Erro",
                f"Não foi possível listar as impressoras do Windows:\n\n{erro}\n\n"
                "Isso só funciona rodando o programa no Windows, com o "
                "pacote pywin32 instalado (pip install pywin32)."
            )
            return

        if not lista:
            messagebox.showwarning(
                "Impressoras",
                "Nenhuma impressora foi encontrada instalada no Windows."
            )
            return

        self.combo_impressoras.configure(values=lista)
        self.combo_impressoras.set(lista[0])

    # ======================================================

    def salvar(self):

        largura = 48 if self.papel.get().startswith("80mm") else 32

        try:
            meta_fidelidade = int(self.fidelidade_meta.get().strip())
            if meta_fidelidade <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Configurações",
                "\"Pedidos para ganhar 1 recompensa\" precisa ser um número "
                "inteiro maior que zero."
            )
            return

        config.definir("fidelidade_meta_pedidos", str(meta_fidelidade))

        config.definir("loja_nome", self.loja_nome.get().strip())
        config.definir("loja_endereco", self.loja_endereco.get().strip())
        config.definir("loja_telefone", self.loja_telefone.get().strip())
        config.definir("senha_reset", self.senha_reset.get().strip())
        config.definir("repo_atualizacao", self.repo_atualizacao.get().strip() or atualizacao.REPOSITORIO_PADRAO)
        config.definir("impressora_nome", self.combo_impressoras.get().strip())
        config.definir("impressora_largura", str(largura))
        config.definir("bloquear_venda_sem_estoque_ingrediente", self.bloquear_estoque_ingrediente.get())

        self.lbl_status.configure(
            text="✅ Configurações salvas com sucesso!",
            text_color="#2a7"
        )

        messagebox.showinfo("Configurações", "Configurações salvas com sucesso!")

    # ======================================================

    def imprimir_teste(self):
        """Salva as configurações atuais e imprime um cupom de teste,
        sem gravar nada na tabela de pedidos."""

        self.salvar()

        dados_loja = {
            "nome": self.loja_nome.get().strip(),
            "endereco": self.loja_endereco.get().strip(),
            "telefone": self.loja_telefone.get().strip(),
        }

        agora = datetime.now()

        pedido_teste = {
            "numero": 0,
            "cliente": "Cliente de Teste",
            "data": agora.strftime("%d/%m/%Y"),
            "hora": agora.strftime("%H:%M"),
            "subtotal": 10.00,
            "desconto": 0.00,
            "acrescimo": 0.00,
            "total": 10.00,
            "pagamento": "TESTE",
            "observacao": "Isto é apenas um teste de impressão."
        }

        # O item de teste leva uma observação de propósito: é assim que
        # se confere se a impressora imprime a tarja preta (vídeo
        # invertido) usada para destacar "sem cebola", "retirar o milho"...
        itens_teste = [
            {
                "nome": "Item de Teste",
                "qtd": 1,
                "valor_unitario": 10.00,
                "subtotal": 10.00,
                "observacao": "teste de destaque"
            }
        ]

        try:
            impressora.imprimir_cupom(dados_loja, pedido_teste, itens_teste)

            messagebox.showinfo(
                "Teste de Impressão",
                "Cupom de teste enviado! Verifique a impressora."
            )

        except Exception as erro:

            messagebox.showerror(
                "Erro ao imprimir",
                f"Não foi possível imprimir o cupom de teste:\n\n{erro}"
            )

    # ======================================================

    def fazer_backup_manual(self):
        """Copia o banco de dados agora mesmo pra pasta backups/,
        independente do backup automático feito na abertura do programa."""

        try:
            config.fazer_backup_banco()

            messagebox.showinfo(
                "Backup",
                "Backup do banco de dados feito com sucesso!\n\n"
                "O arquivo foi salvo na pasta \"backups\", do lado do programa."
            )

        except Exception as erro:

            messagebox.showerror(
                "Erro ao fazer backup",
                f"Não foi possível fazer o backup do banco de dados:\n\n{erro}"
            )

    # ======================================================

    def verificar_atualizacao_manual(self):
        """Checagem de atualização pedida na mão pelo usuário — ao
        contrário da checagem automática do startup, essa sempre dá uma
        resposta visível (achou, não achou, ou deu erro)."""

        if not getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Verificar Atualização",
                "A checagem de atualização só funciona na versão "
                "compilada (.exe), baixada do GitHub."
            )
            return

        if atualizacao.obter_versao_atual() is None:
            messagebox.showwarning(
                "Verificar Atualização",
                "Não foi possível identificar a versão deste "
                ".exe (ele não foi gerado pela Action do GitHub)."
            )
            return

        self.lbl_status.configure(text="🔎 Verificando atualização...", text_color="gray")

        atualizacao.verificar_manualmente(
            lambda atual, nova, url, url_download: self.after(0, lambda: self._resultado_atualizacao(atual, nova, url, url_download)),
            lambda erro: self.after(0, lambda: self._erro_atualizacao(erro))
        )

    # ======================================================

    def _resultado_atualizacao(self, versao_atual, versao_nova, url_release, url_download):

        self.lbl_status.configure(text="")

        if versao_nova > versao_atual:

            # Sem um .zip anexado ao release não tem o que baixar/instalar
            # sozinho — cai pro fluxo antigo de abrir a página no navegador.
            if not url_download:

                abrir = messagebox.askyesno(
                    "Atualização disponível",
                    f"Você está usando a versão {atualizacao.formatar_versao(versao_atual)}.\n"
                    f"A versão {atualizacao.formatar_versao(versao_nova)} já está disponível no GitHub.\n\n"
                    "Não foi possível encontrar o arquivo de instalação automática "
                    "nesse release. Deseja abrir a página de download agora?"
                )

                if abrir:
                    webbrowser.open(url_release)

                return

            atualizar = messagebox.askyesno(
                "Atualização disponível",
                f"Você está usando a versão {atualizacao.formatar_versao(versao_atual)}.\n"
                f"A versão {atualizacao.formatar_versao(versao_nova)} já está disponível.\n\n"
                "Deseja atualizar agora? O programa vai baixar a nova versão, "
                "fechar e abrir de novo sozinho."
            )

            if atualizar:
                autoatualizador.iniciar(self, url_download)

        else:

            messagebox.showinfo(
                "Verificar Atualização",
                f"Você já está com a versão mais recente "
                f"({atualizacao.formatar_versao(versao_atual)})."
            )

    # ======================================================

    def _erro_atualizacao(self, erro):

        self.lbl_status.configure(text="")

        # Repositório errado e falta de internet dão a mesma cara de
        # "não deu certo", mas o conserto é bem diferente — o primeiro
        # está a dois campos de distância, nesta mesma tela.
        if isinstance(erro, atualizacao.RepositorioInvalido):

            messagebox.showerror(
                "Verificar Atualização",
                f"Não foi possível encontrar o repositório \"{erro.repositorio}\" "
                "no GitHub.\n\n"
                "Ele pode estar escrito errado, ser privado ou não ter nenhuma "
                "versão publicada. Corrija o campo \"Repositório no GitHub\" "
                f"aqui em cima — o padrão é {atualizacao.REPOSITORIO_PADRAO} — "
                "e salve antes de tentar de novo."
            )

            return

        messagebox.showerror(
            "Verificar Atualização",
            f"Não foi possível verificar atualizações agora:\n\n{erro}\n\n"
            "Confira sua conexão com a internet."
        )
