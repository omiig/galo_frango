import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import pandas as pd
import os
import random # Para simulação de geração inicial e outros

# Importa a classe SistemaGALO do arquivo modelo_previsao.py
from modelo_previsao import SistemaGALO

# --- Variáveis Globais ---
# Dicionário para armazenar informações de login de usuários e suas filiais
USERS = {
    "movimentador1": {"password": "123", "role": "movimentador", "filial": "Filial A"},
    "movimentador2": {"password": "123", "role": "movimentador", "filial": "Filial B"},
    "abastecedor1": {"password": "123", "role": "abastecedor", "filial": "Filial A"},
    "abastecedor2": {"password": "123", "role": "abastecedor", "filial": "Filial B"},
    "comprador1": {"password": "123", "role": "comprador", "filial": "Filial A"},
    "admin": {"password": "admin", "role": "controller", "filial": "Todas"}
}

# Definições de SKUs e seus rótulos para exibição
SKU_DEFINITIONS = {
    "237478": {"display_column_label": "Frango Inteiro Congelado"},
    "237479": {"display_column_label": "Asa de Frango Congelada"},
    "237496": {"display_column_label": "Coração de Frango Congelado"},
    "237497": {"display_column_label": "Sobre Coxa de Frango Congelada"},
    "237506": {"display_column_label": "Coxa de Frango Congelada"},
    "237508": {"display_column_label": "Peito de Frango Congelado"},
    "237511": {"display_column_label": "Moela de Frango Congelada"},
    "384706": {"display_column_label": "Pé de Frango Congelado"},
}

# Variáveis de estado do sistema
current_day = 0
current_hour = 0
generated_processes = []
logged_in_user_role = None
logged_in_user_filial = None
logged_in_username = None # Variável para armazenar o nome de usuário logado
next_process_number = 1
controller_window = None 

# Listas para controlar as janelas abertas
open_movimentador_windows = []
open_abastecedor_windows = []
controller_window = None
sku_quantity_config_window = None

# Dicionário para armazenar processos do Dia 2 concluídos, por filial
completed_day2_processes_by_filial = {filial: [] for filial in set(user["filial"] for user in USERS.values() if user["filial"] != "Todas")}
# Adicionar "Todas" se for um caso para a lógica do completed_day2_processes_by_filial
if "Todas" not in completed_day2_processes_by_filial:
     completed_day2_processes_by_filial["Todas"] = [] # ou não ter, dependendo de como "Todas" se comporta

# Dicionário para armazenar as quantidades padrão por SKU e por filial
# Carregado de arquivo, se existir, ou inicializado com valores padrão
sku_default_quantities = {}

# Limiar de alerta para abastecimento (em kg)
ALERT_THRESHOLD = 10.0 # kg

# Instância do sistema de previsão e controle GALO
sistema_galo = None # Será inicializado após o Tkinter

# --- Funções Auxiliares de Persistência ---
def load_sku_quantities():
    global sku_default_quantities
    try:
        with open('sku_quantities.json', 'r') as f:
            sku_default_quantities = json.load(f)
        # Convert keys back to int if they were SKUs that are ints
        # No, SKUs are strings in SKU_DEFINITIONS, so no conversion needed
        print("Quantidades de SKU carregadas com sucesso.")
    except (FileNotFoundError, json.JSONDecodeError):
        print("Arquivo 'sku_quantities.json' não encontrado ou corrompido. Usando valores padrão.")
        # Default values if file not found or corrupted
        for filial in KNOWN_FILIAIS:
            sku_default_quantities[filial] = {sku: 100.0 for sku in SKU_DEFINITIONS.keys()}

def save_sku_quantities(data):
    try:
        with open('sku_quantities.json', 'w') as f:
            json.dump(data, f, indent=4)
        print("Quantidades de SKU salvas com sucesso.")
    except Exception as e:
        print(f"Erro ao salvar quantidades de SKU: {e}")

# --- Funções Auxiliares do Tkinter ---
def create_toplevel_window(parent, title, geometry, window_ref_name, close_callback, allow_multiple=False, window_list_ref=None):
    if not allow_multiple:
        existing_window = globals().get(window_ref_name)
        if existing_window and existing_window.winfo_exists():
            existing_window.lift()
            return None

    window = tk.Toplevel(parent)
    window.title(title)
    window.geometry(geometry)
    window.transient(parent) # Faz com que a janela toplevel fique sempre acima da janela pai
    window.protocol("WM_DELETE_WINDOW", lambda: close_callback(window, window_ref_name, window_list_ref))
    
    if window_list_ref is not None:
        window_list_ref.append(window)

    return window

def on_toplevel_close(window, window_ref_name, window_list_ref=None):
    if window_list_ref and window in window_list_ref:
        window_list_ref.remove(window)
    window.destroy()
    # Limpar a referência global se houver apenas uma instância permitida
    if not (window_list_ref and len(window_list_ref) > 0):
        globals()[window_ref_name] = None

# --- Funções de Login e Interface ---
def login():
    global logged_in_user_role, logged_in_user_filial, logged_in_username, main_app_screen_ref

    username = entry_username.get()
    password = entry_password.get()

    user_info = USERS.get(username)

    if user_info and user_info["password"] == password:
        logged_in_user_role = user_info["role"]
        logged_in_user_filial = user_info["filial"]
        logged_in_username = username
        messagebox.showinfo("Login Sucesso", f"Bem-vindo, {username} ({logged_in_user_role} - {logged_in_user_filial})!")
        open_main_app_screen()
    else:
        messagebox.showerror("Erro de Login", "Usuário ou senha inválidos.")

def open_main_app_screen():
    global main_app_screen_ref, controller_window

    main_app_screen_ref = tk.Toplevel(login_screen_ref)
    main_app_screen_ref.title("Frango App - Menu Principal")
    main_app_screen_ref.geometry("500x400")
    main_app_screen_ref.protocol("WM_DELETE_WINDOW", on_main_app_close)

    label_welcome = tk.Label(main_app_screen_ref, text=f"Bem-vindo(a), {logged_in_username}!", font=("Arial", 16, "bold"))
    label_welcome.pack(pady=20)

    label_role = tk.Label(main_app_screen_ref, text=f"Função: {logged_in_user_role} | Filial: {logged_in_user_filial}", font=("Arial", 12))
    label_role.pack(pady=5)

    if logged_in_user_role == "movimentador":
        btn_movimentador = tk.Button(main_app_screen_ref, text="Abrir Interface do Movimentador", command=lambda: open_movimentador_interface(main_app_screen_ref, logged_in_username), font=("Arial", 12))
        btn_movimentador.pack(pady=10)
    elif logged_in_user_role == "abastecedor":
        btn_abastecedor = tk.Button(main_app_screen_ref, text="Abrir Interface do Abastecedor", command=lambda: open_abastecedor_interface(main_app_screen_ref), font=("Arial", 12))
        btn_abastecedor.pack(pady=10)
    elif logged_in_user_role == "comprador":
        btn_comprador = tk.Button(main_app_screen_ref, text="Abrir Interface do Comprador", command=lambda: open_comprador_interface(main_app_screen_ref), font=("Arial", 12))
        btn_comprador.pack(pady=10)
    elif logged_in_user_role == "controller":
        btn_controller = tk.Button(main_app_screen_ref, text="Abrir Painel de Controle (Admin)", command=open_controller_interface, font=("Arial", 12), bg="darkred", fg="white")
        btn_controller.pack(pady=10)
        # O controlador não fecha a janela de login, apenas abre a dele
        open_controller_interface() # Abre automaticamente para o controlador

    btn_logout = tk.Button(main_app_screen_ref, text="Logout", command=logout, font=("Arial", 12))
    btn_logout.pack(pady=20)

def logout():
    global logged_in_user_role, logged_in_user_filial, logged_in_username, main_app_screen_ref, controller_window

    if messagebox.askyesno("Logout", "Tem certeza que deseja sair?"):
        # Fecha todas as janelas toplevel abertas, exceto o controlador
        for win in open_movimentador_windows[:]: win.destroy()
        open_movimentador_windows.clear()
        for win in open_abastecedor_windows[:]:
            win_ref_name = "abastecedor_window_instance"
            on_toplevel_close(win, win_ref_name, open_abastecedor_windows)

        if sku_quantity_config_window and sku_quantity_config_window.winfo_exists():
            sku_quantity_config_window.destroy()
            globals()["sku_quantity_config_window"] = None # Limpa a referência

        if main_app_screen_ref and main_app_screen_ref.winfo_exists():
            main_app_screen_ref.destroy()

        logged_in_user_role = None
        logged_in_user_filial = None
        logged_in_username = None

        login_screen_ref.deiconify() # Mostra a tela de login novamente
        entry_password.delete(0, tk.END) # Limpa a senha
        messagebox.showinfo("Logout", "Você foi desconectado.")

def on_main_app_close():
    if messagebox.askyesno("Sair", "Tem certeza que deseja fechar o aplicativo?"):
        # Destruir todas as janelas toplevel para garantir que o aplicativo saia completamente
        for win in open_movimentador_windows[:]: win.destroy()
        for win in open_abastecedor_windows[:]: win.destroy()
        if controller_window and controller_window.winfo_exists():
            on_controller_close(controller_window, "controller_window") # Trata o fechamento do controlador
        if sku_quantity_config_window and sku_quantity_config_window.winfo_exists():
            sku_quantity_config_window.destroy()
        login_screen_ref.destroy() # Destrói a janela principal
    else:
        main_app_screen_ref.lift() # Traz a janela principal para frente se o usuário cancelar

# --- Funções de Tempo e Eventos ---
def advance_time(hours=0, days=0):
    global current_hour, current_day, generated_processes

    new_hour = current_hour + hours
    new_day = current_day + days

    if new_hour >= 24:
        days_from_hours = new_hour // 24
        new_day += days_from_hours
        new_hour %= 24

    # Regra de negócio: processos só começam a ser contabilizados/gerados a partir das 6h
    if current_hour < 6 and new_hour >= 6:
        # Se estamos "passando" pelas 6h em um novo dia (ou no mesmo dia se horas for grande o suficiente)
        # E se ainda não geramos os processos para este novo dia de "trabalho"
        # O ideal é que a geração ocorra APENAS no início do dia útil (06:00)
        print(f"DEBUG: Passando das 06:00, executando perform_daily_process_generation para o dia {new_day}.")
        perform_daily_process_generation(new_day) # Gera processos para o novo dia de operação

    current_day = new_day
    current_hour = new_hour
    
    print(f"Tempo avançado para Dia {current_day}, Hora {current_hour:02d}:00")

    update_process_states_on_time_change()
    update_controller_time_display() # Atualiza o display no controlador

def advance_x_hours():
    try:
        hours_to_jump = int(controller_window.hour_jump_entry.get())
        if hours_to_jump <= 0:
            messagebox.showerror("Erro", "Por favor, insira um número positivo de horas.")
            return
        advance_time(hours=hours_to_jump)
    except ValueError:
        messagebox.showerror("Erro", "Por favor, insira um número válido para as horas.")

def advance_day_complete():
    global current_hour, current_day
    
    # Simula o avanço do dia completo, passando pelas 00:00 até as 06:00 do próximo dia
    # Assim, a geração de processos é acionada corretamente.
    
    # Avança para 23:00 do dia atual para ter certeza que passaremos pela meia-noite
    # e teremos o dia 'virado' antes de perform_daily_process_generation ser chamado
    if current_hour < 23:
        advance_time(hours=(23 - current_hour))
    
    # Isso vai garantir que passe da meia-noite e atinja as 06:00 do próximo dia
    # O SistemaGALO precisa da data "real" para prever. current_day é o offset.
    # A data real para o sistema GALO seria algo como datetime.today() + timedelta(days=current_day)
    
    # Primeiro, simula a venda do dia que está terminando ANTES de avançar o dia
    # A data para a venda simulada é 'current_day' (o dia que está terminando)
    data_para_venda_simulada = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=current_day)
    sistema_galo.simular_venda_diaria(data_para_venda_simulada)

    # Prepara novas features com os dados de vendas atualizados e re-treina o modelo se necessário
    sistema_galo.preparar_features()
    sistema_galo.verificar_e_re_treinar_modelo()
    
    # Salva o estado do estoque do GALO antes de avançar o dia
    sistema_galo.salvar_estado()

    # Avança o tempo para o próximo dia (Dia X, Hora 06:00)
    # A lógica perform_daily_process_generation será chamada quando new_hour >= 6
    advance_time(hours=(24 - current_hour) + 6) 

    # Após o avanço do dia (e a geração de novos processos), execute o gerenciamento do GALO
    data_hoje_galo = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=current_day)
    sistema_galo.verificar_e_reabastecer_estoque(data_hoje_galo)
    sistema_galo.gerenciar_descongelamento_diario(data_hoje_galo) # Executa as movimentações para D-0, D-1, D-2
    sistema_galo.gerar_relatorio(sistema_galo.calcular_descongelamento(sistema_galo.prever_demanda(data_hoje_galo), data_hoje_galo + timedelta(days=2)), sufixo="descongelamento_diario")
    sistema_galo.gerar_relatorio_movimentacao()
    sistema_galo.salvar_estado() # Salva o estado do GALO após as movimentações

    messagebox.showinfo("Avanço de Tempo", f"O sistema avançou 1 dia completo para Dia {current_day}, Hora {current_hour:02d}:00.")
    update_controller_weight_panel() # Atualiza o painel do controlador
    for win in open_movimentador_windows:
        update_movimentador_processes(win)
    for win in open_abastecedor_windows:
        update_abastecedor_completed_processes_display(win)

def update_controller_time_display():
    if controller_window and controller_window.winfo_exists():
        controller_window.day_label.config(text=f"Dia Atual: {current_day}")
        controller_window.hour_label.config(text=f"Hora Atual: {current_hour:02d}:00")

def log_event(evento, filial, sku, process_id, dia_processo, quantidade_kg, usuario, info_adicional=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] EVENTO: {evento} | Filial: {filial} | SKU: {sku} | Processo ID: {process_id} | Dia Processo: {dia_processo} | Qtde: {quantidade_kg:.2f} kg | Usuário: {usuario} | Info: {info_adicional}\n"
    
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    with open(os.path.join(log_dir, "app_log.txt"), "a") as f:
        f.write(log_entry)
    print(f"LOG: {log_entry.strip()}")

# --- Funções de Geração e Gerenciamento de Processos ---
def generate_process_id():
    global next_process_number
    # Format as P-YYYYMMDD-XXXX
    date_part = (datetime.now() + timedelta(days=current_day)).strftime("%Y%m%d")
    process_id = f"P-{date_part}-{next_process_number:04d}"
    next_process_number += 1
    return process_id

def perform_daily_process_generation(day_of_generation):
    """
    Gera novos processos de descongelamento e movimentação para o dia atual,
    baseando-se nas previsões de demanda do SistemaGALO.
    """
    global generated_processes

    # Data real para a previsão
    data_para_previsao_galo = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day_of_generation)
    
    # Obter previsões para D+2
    try:
        previsoes_d2 = sistema_galo.prever_demanda(data_para_previsao_galo)
    except RuntimeError as e:
        print(f"Erro ao prever demanda: {e}. Não será possível gerar processos baseados em previsão.")
        previsoes_d2 = pd.DataFrame(columns=['sku', 'data_previsao', 'qtd_prevista'])

    print(f"\n--- Gerando Processos para o Dia {day_of_generation} (Baseado em Previsão para {data_para_previsao_galo + timedelta(days=2)}) ---")
    
    for filial in KNOWN_FILIAIS:
        if filial == "Todas": # Pular filiais "Todas" se for um caso especial
            continue 
        
        # Filtrar previsões para os SKUs que a filial normalmente lida e têm previsão > 0
        for _, previsao_row in previsoes_d2.iterrows():
            sku = previsao_row['sku']
            # Pega a quantidade padrão configurada pelo controlador para este SKU e filial
            quantidade_base_sku = sku_default_quantities.get(filial, {}).get(sku, 100.0) # Fallback para 100kg

            # Usar a previsão para ajustar a quantidade
            # Para simplificar, se a previsão for alta, usar a previsão, senão usar a quantidade base
            # Uma lógica mais complexa poderia ser: max(quantidade_base_sku, previsao_row['qtd_prevista'] * fator_seguranca)
            quantidade_a_gerar = max(quantidade_base_sku, previsao_row['qtd_prevista'] * 1.1) # 10% de margem na previsão
            
            # Arredonda a quantidade para evitar números muito quebrados
            quantidade_a_gerar = round(quantidade_a_gerar, 2)

            if quantidade_a_gerar <= 0:
                print(f"  Pulando geração para SKU {sku} na Filial {filial}: Previsão muito baixa ou zero ({quantidade_a_gerar} kg).")
                continue

            # Verificar se já existe um processo ativo para este SKU nesta filial no dia de geração
            # E se a quantidade já presente no estoque e descongelamento para D+2 é suficiente
            
            # Calcula o estoque total (congelador + descongelando) válido para a data de previsão
            total_estoque_para_d2 = sistema_galo.estoque[
                (sistema_galo.estoque['sku'] == sku) &
                (sistema_galo.estoque['validade'] >= (data_para_previsao_galo + timedelta(days=2))) &
                (sistema_galo.estoque['localizacao_estante'] == 'congelador') # Considera apenas o congelador para novas gerações
            ]['kg'].sum()

            total_descongelando_para_d2 = sistema_galo.descongelando[
                (sistema_galo.descongelando['sku'] == sku) &
                (sistema_galo.descongelando['validade'] >= (data_para_previsao_galo + timedelta(days=2)))
            ]['kg'].sum()

            # Estoque total disponível para o dia da venda (D+2)
            estoque_disponivel_para_venda_d2 = total_estoque_para_d2 + total_descongelando_para_d2
            
            # Se a quantidade que seria gerada já é menor que o estoque disponível
            if quantidade_a_gerar * (1 / (1 - 0.15)) <= estoque_disponivel_para_venda_d2: # Considera a perda
                print(f"  Pulando geração para SKU {sku} na Filial {filial}: Estoque atual ({estoque_disponivel_para_venda_d2:.2f} kg) já cobre a previsão de {quantidade_a_gerar:.2f} kg para D+2.")
                continue

            # Agora, efetivamente "gera" o processo no sistema do FrangoApp
            # E adiciona ao estoque do sistema GALO
            process_id = generate_process_id()
            new_process = {
                "numero": process_id,
                "sku": sku,
                "quantidade_kg": quantidade_a_gerar,
                "dia_geracao": day_of_generation,
                "filial": filial,
                "sku_process_number": process_id,
                "days_cycle": 3, # D-0, D-1, D-2
                "peso_no_balcao": 0.0, # Começa com zero no balcão
                "steps_status": {
                    str(day_of_generation): {"status": "Desabilitado", "movimentacao_started": False}, # D-0 (hoje)
                    str(day_of_generation + 1): {"status": "Desabilitado", "movimentacao_started": False}, # D-1 (amanhã)
                    str(day_of_generation + 2): {"status": "Desabilitado", "movimentacao_started": False}  # D-2 (depois de amanhã)
                },
                "steps_descriptions": {
                    0: f"Retire {quantidade_a_gerar:.2f} kg de {SKU_DEFINITIONS[sku]['display_column_label']} do congelador e coloque na estante esquerda.",
                    1: "Retire da estante esquerda e coloque na central.",
                    2: "Retire da central e coloque no balcão."
                }
            }
            generated_processes.append(new_process)
            print(f"  Processo Gerado: {process_id} | SKU: {sku} | Qtde: {quantidade_a_gerar:.2f} kg | Filial: {filial} | Previsão D+2: {previsao_row['qtd_prevista']:.2f} kg")

            # Adicionar a quantidade gerada ao estoque do sistema GALO (localização 'congelador')
            # A validade é genérica, pode ser ajustada conforme a necessidade
            validade_nova_carga = datetime.now() + timedelta(days=day_of_generation + 7) # Ex: 7 dias a partir do dia de geração
            sistema_galo.reabastecer_estoque(sku, quantidade_a_gerar, data_para_previsao_galo) # Usa a data real de geração para o GALO

    print("--- Geração de Processos Concluída. ---\n")
    update_process_states_on_time_change()


def update_process_states_on_time_change():
    """
    Atualiza o status dos processos com base no tempo atual (current_day, current_hour).
    Chama as funções de atualização de interface se as janelas estiverem abertas.
    """
    global generated_processes

    # Lógica de atualização de status dos processos
    for process in generated_processes:
        process_generation_day = process["dia_geracao"]
        total_days_cycle = process.get("days_cycle", 3)

        for day_offset in range(total_days_cycle):
            absolute_step_day = process_generation_day + day_offset
            step_info = process["steps_status"].get(str(absolute_step_day))

            if step_info:
                if absolute_step_day < current_day:
                    # Se o dia da etapa já passou e não foi feito, marca como 'Atrasado'
                    if step_info["status"] == "Aguardando":
                        step_info["status"] = "Atrasado"
                        log_event(
                            evento="PROCESSO ATRASADO",
                            filial=process["filial"],
                            sku=process["sku"],
                            process_id=process["sku_process_number"],
                            dia_processo=day_offset,
                            quantidade_kg=process["quantidade_kg"],
                            usuario="SISTEMA",
                            info_adicional=f"Etapa do Dia {day_offset} marcada como Atrasada."
                        )
                elif absolute_step_day == current_day:
                    # Se for o dia atual, habilita se a hora for >= 6h
                    if current_hour >= 6:
                        if step_info["status"] == "Desabilitado":
                            step_info["status"] = "Aguardando"
                            log_event(
                                evento="PROCESSO HABILITADO",
                                filial=process["filial"],
                                sku=process["sku"],
                                process_id=process["sku_process_number"],
                                dia_processo=day_offset,
                                quantidade_kg=process["quantidade_kg"],
                                usuario="SISTEMA",
                                info_adicional=f"Etapa do Dia {day_offset} habilitada."
                            )
                    else: # Antes das 6h, desabilitado
                         step_info["status"] = "Desabilitado"
                # Se absolute_step_day > current_day, permanece "Desabilitado" até o dia chegar

    # Atualiza as interfaces abertas
    for win in open_movimentador_windows:
        update_movimentador_processes(win)
    for win in open_abastecedor_windows:
        update_abastecedor_completed_processes_display(win)
    if controller_window and controller_window.winfo_exists():
        update_controller_weight_panel()

# --- Interfaces de Usuário ---

def open_movimentador_interface(parent_screen, username): # <--- ALTERAÇÃO
    window = create_toplevel_window(parent_screen, f"Interface do Movimentador de Produto - Filial {logged_in_user_filial}", "1200x600", "movimentador_window_instance", on_toplevel_close, allow_multiple=True, window_list_ref=open_movimentador_windows)
    if window:
        window.current_logged_in_filial = logged_in_user_filial
        window.current_user = username # <--- ADIÇÃO
        
        label_title = tk.Label(window, text=f"Bem-vindo(a) {username} à Interface do Movimentador (Filial {logged_in_user_filial})", font=("Arial", 18, "bold"))
        label_title.pack(pady=20)

        main_display_container = tk.Frame(window, bd=2, relief="groove", padx=10, pady=10)
        main_display_container.pack(pady=20, fill="both", expand=True)

        canvas = tk.Canvas(main_display_container)
        
        scrollbar_y = ttk.Scrollbar(main_display_container, orient="vertical", command=canvas.yview)
        scrollbar_y.pack(side="right", fill="y")
        
        scrollbar_x = ttk.Scrollbar(main_display_container, orient="horizontal", command=canvas.xview)
        scrollbar_x.pack(side="bottom", fill="x")

        canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        canvas.pack(side="left", fill="both", expand=True)

        inner_scrollable_content_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=inner_scrollable_content_frame, anchor="nw")

        inner_scrollable_content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        
        window.process_frame = inner_scrollable_content_frame 

        update_movimentador_processes(window)

def handle_movimentacao_button(process_original_index, window_ref, step_absolute_day):
    global completed_day2_processes_by_filial

    if 0 <= process_original_index < len(generated_processes):
        process = generated_processes[process_original_index]
        
        if process.get("filial") != window_ref.current_logged_in_filial:
            messagebox.showwarning("Ação Inválida", "Este processo não pertence à sua filial.")
            return

        step_info = process["steps_status"].get(str(step_absolute_day))

        if not step_info or step_info["status"] not in ["Aguardando"]: 
            messagebox.showwarning("Ação Inválida", f"A etapa do Dia {step_absolute_day} do processo {process['numero']} não está no estado 'Aguardando'.")
            return

        # --- DADOS PARA O LOG ---
        user = window_ref.current_user
        filial = process["filial"]
        sku = process["sku"]
        process_id = process["sku_process_number"]
        quantidade = process["quantidade_kg"]
        day_offset = step_absolute_day - process["dia_geracao"]
        # --- FIM DOS DADOS PARA O LOG ---

        if not step_info.get("movimentacao_started", False):
            messagebox.showinfo(
                "Iniciar Movimentação",
                "CUIDADOS IMPORTANTES:\n\n"
                "- Lave bem as mãos.\n"
                "- Use luvas descartáveis.\n"
                "- Evite contaminação cruzada. Use utensílios limpos para cada SKU.\n"
                "- Mantenha a área de trabalho higienizada."
            )
            step_info["movimentacao_started"] = True

            # --- INÍCIO DA ADIÇÃO DO LOG (INÍCIO DA MOVIMENTAÇÃO) ---
            log_event(
                evento="MOVIMENTAÇÃO INICIADA",
                filial=filial,
                sku=sku,
                process_id=process_id,
                dia_processo=day_offset,
                quantidade_kg=quantidade,
                usuario=user,
                info_adicional=f"Início da movimentação para o dia {day_offset} do ciclo."
            )
            # --- FIM DA ADIÇÃO DO LOG ---

            update_movimentador_processes(window_ref)
        else:
            step_info["status"] = "Feito"
            step_info["data_movimentacao"] = f"Dia {current_day} - Hora {current_hour:02d}:00"
            step_info["dia_conclusao"] = current_day
            messagebox.showinfo("Movimentação Confirmada", f"Etapa do Dia {day_offset} do processo {process['numero']} marcada como FEITO.")

            # --- INÍCIO DA ADIÇÃO DO LOG (CONFIRMAÇÃO DA MOVIMENTAÇÃO) ---
            log_event(
                evento="MOVIMENTAÇÃO CONFIRMADA",
                filial=filial,
                sku=sku,
                process_id=process_id,
                dia_processo=day_offset,
                quantidade_kg=quantidade,
                usuario=user,
                info_adicional=f"Confirmação da movimentação para o dia {day_offset} do ciclo."
            )
            # --- FIM DA ADIÇÃO DO LOG ---
            
            # Lógica para movimentar o estoque no sistema GALO
            data_movimento_galo = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=current_day)
            
            if day_offset == 0: # Congelador para Estante Esquerda
                sistema_galo._simular_movimentacao_estante(
                    sku=sku,
                    qtd_movida=quantidade,
                    estante_origem='congelador',
                    estante_destino='estante_esquerda',
                    data_movimento=data_movimento_galo,
                    confirmacao_automatica=True # Confirmado pela ação no App
                )
            elif day_offset == 1: # Estante Esquerda para Estante Central
                # Para esta etapa, movemos a quantidade que "entrou" na estante esquerda no dia anterior
                # O ideal é que a lógica do _simular_movimentacao_estante já cuide disso buscando a data de entrada
                sistema_galo._simular_movimentacao_estante(
                    sku=sku,
                    qtd_movida=quantidade, # Quantidade original do processo
                    estante_origem='estante_esquerda',
                    estante_destino='estante_central',
                    data_movimento=data_movimento_galo,
                    confirmacao_automatica=True
                )
            elif day_offset == 2: # Estante Central para Balcão
                sistema_galo._simular_movimentacao_estante(
                    sku=sku,
                    qtd_movida=quantidade, # Quantidade original do processo
                    estante_origem='estante_central',
                    estante_destino='balcao',
                    data_movimento=data_movimento_galo,
                    confirmacao_automatica=True
                )
            
            total_days_cycle = process.get("days_cycle", 3)
            if day_offset == (total_days_cycle - 1): # Se for o último dia do ciclo (Dia 2)
                filial_do_processo = process["filial"]
                process_id_to_add = process["sku_process_number"]
                if process_id_to_add not in completed_day2_processes_by_filial.get(filial_do_processo, []):
                    completed_day2_processes_by_filial.setdefault(filial_do_processo, []).append(process_id_to_add)
                    print(f"Processo {process_id_to_add} (Filial {filial_do_processo}) concluído no Dia {day_offset}. Adicionado para exibição do abastecedor.")
                
                for win in open_abastecedor_windows:
                    update_abastecedor_completed_processes_display(win)

                update_controller_weight_panel()

            update_process_states_on_time_change()
            
            update_movimentador_processes(window_ref)
            sistema_galo.salvar_estado() # Salva o estado do GALO após cada movimentação confirmada
    else:
        messagebox.showerror("Erro", "Processo inválido.")

def update_movimentador_processes(window_ref):
    if window_ref and window_ref.winfo_exists() and hasattr(window_ref, 'process_frame'):
        for widget in window_ref.process_frame.winfo_children():
            widget.destroy()

        filial_desta_janela = window_ref.current_logged_in_filial
        
        filtered_processes = []
        for p in generated_processes:
            if p.get("filial") == filial_desta_janela:
                total_days_cycle = p.get("days_cycle", 3)
                last_day_offset = total_days_cycle - 1
                absolute_last_day = p["dia_geracao"] + last_day_offset
                
                last_step_info = p["steps_status"].get(str(absolute_last_day))
                
                mostrar_processo = False
                if not last_step_info or last_step_info.get("status") != "Feito":
                    mostrar_processo = True
                elif last_step_info.get("status") == "Feito":
                    dia_de_conclusao = last_step_info.get("dia_conclusao")
                    if dia_de_conclusao is not None and dia_de_conclusao == current_day:
                        mostrar_processo = True

                if mostrar_processo:
                    filtered_processes.append(p)

        processes_by_sku = {}
        for sku_key in SKU_DEFINITIONS.keys():
            processes_by_sku[sku_key] = []
        
        for process in filtered_processes:
            if process['sku'] in processes_by_sku:
                processes_by_sku[process['sku']].append(process)
        
        if not filtered_processes:
            tk.Label(window_ref.process_frame, text=f"Nenhum processo gerado para a Filial {filial_desta_janela} ainda.", font=("Arial", 12)).pack(pady=10)
        else:
            sorted_skus = sorted(list(processes_by_sku.keys()))

            for sku_key in sorted_skus:
                display_label = SKU_DEFINITIONS[sku_key]['display_column_label']
                column_frame = tk.LabelFrame(window_ref.process_frame, text=f"{display_label} ({sku_key})",
                                             font=("Arial", 12, "bold"), bd=2, relief="groove", padx=5, pady=5)
                column_frame.pack(side="left", fill="y", expand=False, padx=5, pady=5)

                processes_in_column = processes_by_sku[sku_key]
                processes_in_column.sort(key=lambda p: p['sku_process_number'])

                for process in processes_in_column:
                    main_process_frame = tk.LabelFrame(column_frame, text=f"Processo {process['sku_process_number']}",
                                                        font=("Arial", 10, "bold"), bd=2, relief="raised", padx=5, pady=3)
                    main_process_frame.pack(pady=5, padx=3, fill="x")

                    tk.Label(main_process_frame, text=f"SKU: {process['sku']} - Qtde: {process['quantidade_kg']} kg", font=("Arial", 9)).pack(anchor="w")

                    daily_steps_container = tk.Frame(main_process_frame)
                    daily_steps_container.pack(pady=3, padx=3, fill="x")

                    steps_descriptions = process.get('steps_descriptions', {})
                    total_days_cycle = process.get('days_cycle', 3)

                    for day_offset in range(total_days_cycle):
                        absolute_step_day = process["dia_geracao"] + day_offset
                        step_info = process["steps_status"].get(str(absolute_step_day))

                        if step_info and (step_info["status"] != "Desabilitado" or (current_day == absolute_step_day and current_hour < 6)):
                            bg_color = "lightgray"

                            step_frame = tk.LabelFrame(daily_steps_container, text=f"Dia {day_offset}",
                                                         font=("Arial", 8, "bold"), bd=1, relief="solid", padx=3, pady=2)
                            step_frame.pack(side="left", padx=2, pady=2, fill="both", expand=True)

                            if step_info["status"] == "Aguardando":
                                if day_offset == (total_days_cycle - 1):
                                    bg_color = "lightblue"
                                else:
                                    bg_color = "lightcoral"
                                
                                if day_offset == 0:
                                    description_text = f"Retire {process['quantidade_kg']} kg de {SKU_DEFINITIONS[process['sku']]['display_column_label']} do congelador e coloque na estante esquerda."
                                elif day_offset == 1:
                                    description_text = "Retire da estante esquerda e coloque na central."
                                elif day_offset == 2:
                                    description_text = "Retire da central e coloque na da direita."
                                else:
                                    description_text = steps_descriptions.get(day_offset, "Descrição não disponível.")

                                tk.Label(step_frame, text=f"Estado: {step_info['status']}", font=("Arial", 8), bg=bg_color).pack(anchor="w")
                                tk.Label(step_frame, text=description_text, font=("Arial", 7, "italic"), wraplength=80, justify="left", bg=bg_color).pack(anchor="w", pady=(2,0))
                                
                                button_text = "Iniciar Movimentação" if not step_info.get("movimentacao_started", False) else "Confirmar Movimentação"
                                
                                btn_movimentacao = tk.Button(step_frame, text=button_text,
                                                              command=lambda idx=generated_processes.index(process), current_win=window_ref, s_day=absolute_step_day: handle_movimentacao_button(idx, current_win, s_day),
                                                              font=("Arial", 7), bg="lightblue", state="normal")
                                btn_movimentacao.pack(pady=2)

                            elif step_info["status"] == "Desabilitado":
                                bg_color = "gray"
                                tk.Label(step_frame, text="Iniciando rotinas às 06:00", font=("Arial", 8, "bold"), bg=bg_color, fg="white", wraplength=80, justify="center").pack(expand=True, fill="both")

                            elif step_info["status"] == "Feito":
                                bg_color = "lightgreen"
                                description = steps_descriptions.get(day_offset, "Descrição não disponível.")
                                
                                tk.Label(step_frame, text=f"Estado: {step_info['status']}", font=("Arial", 8), bg=bg_color).pack(anchor="w")
                                tk.Label(step_frame, text=description, font=("Arial", 7, "italic"), wraplength=80, justify="left", bg=bg_color).pack(anchor="w", pady=(2,0))
                                tk.Label(step_frame, text=f"Concluído: {step_info['data_movimentacao']}", font=("Arial", 7), bg=bg_color).pack(anchor="w")
                                
                                btn_movimentacao = tk.Button(step_frame, text="Movimentação Concluída",
                                                              font=("Arial", 7), bg="lightgreen", state="disabled")
                                btn_movimentacao.pack(pady=2)
                            
                            step_frame.config(bg=bg_color)

def update_abastecedor_completed_processes_display(window_ref):
    """Atualiza a exibição de processos na tela do abastecedor com a nova lógica de alerta."""
    if not (window_ref and window_ref.winfo_exists() and hasattr(window_ref, 'completed_display_frame')):
        return

    for widget in window_ref.completed_display_frame.winfo_children():
        widget.destroy()

    filial_desta_janela = window_ref.current_logged_in_filial
    process_ids_for_display = completed_day2_processes_by_filial.get(filial_desta_janela, [])

    if not process_ids_for_display:
        tk.Label(window_ref.completed_display_frame, text="Nenhum processo pronto para abastecimento nesta filial.",
                 font=("Arial", 10), wraplength=350).pack(pady=10)
        return

    process_objects = {p['sku_process_number']: p for p in generated_processes}
    cards_container = tk.Frame(window_ref.completed_display_frame)
    cards_container.pack(fill="x", pady=5, padx=5)

    display_count = 0
    for process_id in sorted(process_ids_for_display):
        process_data = process_objects.get(process_id)
        if not process_data:
            continue

        card_bg_color = "SystemButtonFace" 
        
        # --- BUSCA OS DADOS DE ESTOQUE ATUAIS DO SISTEMA GALO ---
        sku_do_processo = process_data['sku']
        # Peso no balcão: Soma dos itens no "balcao" para este SKU que ainda não foram "comprados"
        peso_no_balcao = sistema_galo.descongelando[
            (sistema_galo.descongelando['sku'] == sku_do_processo) &
            (sistema_galo.descongelando['localizacao_estante'] == 'balcao')
        ]['kg'].sum()

        # Estoque na estante (esquerda e central) para este SKU
        estoque_na_estante = sistema_galo.descongelando[
            (sistema_galo.descongelando['sku'] == sku_do_processo) &
            ((sistema_galo.descongelando['localizacao_estante'] == 'estante_esquerda') |
             (sistema_galo.descongelando['localizacao_estante'] == 'estante_central'))
        ]['kg'].sum()
        # --- FIM DA BUSCA DOS DADOS DE ESTOQUE ---

        # Adiciona previsão de demanda para D+1 (a previsão D+2 já foi usada para gerar o processo)
        # Aqui, a previsão D+1 seria para a data "current_day + 1"
        data_para_previsao_amanha = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=current_day + 1)
        previsao_demanda_amanha_df = sistema_galo.prever_demanda(data_para_previsao_amanha)
        previsao_demanda_amanha = previsao_demanda_amanha_df[previsao_demanda_amanha_df['sku'] == sku_do_processo]['qtd_prevista'].iloc[0] if not previsao_demanda_amanha_df[previsao_demanda_amanha_df['sku'] == sku_do_processo].empty else 0.0

        card_frame = tk.LabelFrame(cards_container, text=f"Processo {process_id}",
                                     font=("Arial", 10, "bold"), bd=2, relief="groove", padx=10, pady=5)
        
        col = display_count % 3
        row = display_count // 3
        card_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        cards_container.grid_columnconfigure(col, weight=1)

        sku_info = SKU_DEFINITIONS.get(process_data['sku'], {})
        display_name = sku_info.get('display_column_label', 'SKU Desconhecido')
        
        tk.Label(card_frame, text=f"Produto: {display_name}", font=("Arial", 9, "bold")).pack(anchor="w")

        tk.Label(card_frame, text=f"Estoque (Estante):", font=("Arial", 9)).pack(anchor="w", pady=(5, 0))
        tk.Label(card_frame, text=f"{estoque_na_estante:.2f} kg", font=("Arial", 12, "bold"), fg="blue").pack(anchor="w")

        tk.Label(card_frame, text=f"No Balcão:", font=("Arial", 9)).pack(anchor="w", pady=(5, 0))
        tk.Label(card_frame, text=f"{peso_no_balcao:.2f} kg", font=("Arial", 12, "bold"), fg="green").pack(anchor="w")
        
        tk.Label(card_frame, text=f"Previsão Demanda D+1:", font=("Arial", 9)).pack(anchor="w", pady=(5, 0))
        tk.Label(card_frame, text=f"{previsao_demanda_amanha:.2f} kg", font=("Arial", 12, "bold"), fg="purple").pack(anchor="w")


        if estoque_na_estante <= 0 and peso_no_balcao <= ALERT_THRESHOLD:
            card_bg_color = "red"
            status_label = tk.Label(card_frame, text="CRÍTICO (Estoque Esgotado e Balcão Vazio)", font=("Arial", 9, "bold"), fg="white", bg="red")
            status_label.pack(pady=5, fill="x")
        elif estoque_na_estante <= 0:
            card_bg_color = "lightblue"
            status_label = tk.Label(card_frame, text="COMPLETO (Estoque Estante Esgotado)", font=("Arial", 9, "bold"), fg="white", bg="blue")
            status_label.pack(pady=5, fill="x")
        elif peso_no_balcao <= ALERT_THRESHOLD:
            card_bg_color = "gold"
            btn_abastecer = tk.Button(card_frame, text="Abasteça o balcão", 
                                        font=("Arial", 9, "bold"), bg="red", fg="white",
                                        command=lambda p_id=process_id, win=window_ref: start_abastecimento_process(p_id, win))
            btn_abastecer.pack(pady=5, fill="x")

        card_frame.config(bg=card_bg_color)
        for widget in card_frame.winfo_children():
            widget.config(bg=card_bg_color)
            
        display_count += 1
    
def open_abastecedor_interface(parent_screen):
    window = create_toplevel_window(parent_screen, f"Interface do Abastecedor - Filial {logged_in_user_filial}", "800x600", "abastecedor_window_instance", on_toplevel_close, allow_multiple=True, window_list_ref=open_abastecedor_windows)
    if window:
        window.current_logged_in_filial = logged_in_user_filial

        label_title = tk.Label(window, text=f"Bem-vindo(a) à Interface do Abastecedor (Filial {logged_in_user_filial})", font=("Arial", 18, "bold"))
        label_title.pack(pady=20)
        
        label_info = tk.Label(window, text="Processos Prontos para Reabastecimento:", font=("Arial", 12, "bold"))
        label_info.pack(pady=10)

        display_canvas_frame = tk.Frame(window, bd=2, relief="sunken")
        display_canvas_frame.pack(pady=10, fill="both", expand=True)

        canvas = tk.Canvas(display_canvas_frame)
        scrollbar_y = ttk.Scrollbar(display_canvas_frame, orient="vertical", command=canvas.yview)
        scrollbar_y.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar_y.set)

        window.completed_display_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=window.completed_display_frame, anchor="nw")
        
        window.completed_display_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        update_abastecedor_completed_processes_display(window)

def start_abastecimento_process(process_id, window_ref):
    """
    Inicia o processo de abastecimento (movendo da estante para o balcão).
    Simula a movimentação do 'estoque na estante' para o 'peso_no_balcao'.
    """
    found_process = None
    for p in generated_processes:
        if p["sku_process_number"] == process_id:
            found_process = p
            break
    
    if not found_process:
        messagebox.showerror("Erro", "Processo não encontrado.")
        return
    
    sku_do_processo = found_process['sku']
    
    # Quantidade atual na estante central (que deveria ir para o balcão)
    qtd_na_estante_central = sistema_galo.descongelando[
        (sistema_galo.descongelando['sku'] == sku_do_processo) &
        (sistema_galo.descongelando['localizacao_estante'] == 'estante_central')
    ]['kg'].sum()

    if qtd_na_estante_central <= 0:
        messagebox.showwarning("Aviso", "Não há mais estoque na estante central para abastecer este produto.")
        return

    # Mover a quantidade da estante central para o balcão no sistema GALO
    data_movimento_galo = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=current_day)
    sistema_galo._simular_movimentacao_estante(
        sku=sku_do_processo,
        qtd_movida=qtd_na_estante_central,
        estante_origem='estante_central',
        estante_destino='balcao',
        data_movimento=data_movimento_galo,
        confirmacao_automatica=True # Confirmado pela ação no App
    )
    
    messagebox.showinfo("Abastecimento", f"Abastecimento do processo {process_id} concluído. {qtd_na_estante_central:.2f} kg movidos para o balcão.")
    
    # Remove o processo da lista de "completed_day2_processes" após o abastecimento
    # Isso impede que ele apareça novamente, a menos que uma nova necessidade surja (novo processo)
    if process_id in completed_day2_processes_by_filial.get(found_process['filial'], []):
        completed_day2_processes_by_filial[found_process['filial']].remove(process_id)
        print(f"Processo {process_id} removido da lista de abastecimento.")

    update_abastecedor_completed_processes_display(window_ref)
    update_controller_weight_panel() # Para atualizar o painel do controlador
    sistema_galo.salvar_estado() # Salva o estado do GALO

def open_comprador_interface(parent_screen):
    window = create_toplevel_window(parent_screen, f"Interface do Comprador da Distribuidora - Filial {logged_in_user_filial}", "600x400", "comprador_window", on_toplevel_close)
    if window:
        label_title = tk.Label(window, text=f"Bem-vindo(a) à Interface do Comprador da Distribuidora (Filial {logged_in_user_filial})", font=("Arial", 18, "bold"))
        label_title.pack(pady=50)
        label_info = tk.Label(window, text="Aqui serão implementadas as funcionalidades de compra filtradas por filial.", font=("Arial", 12))
        label_info.pack(pady=10)

# --- Interface do Controlador ---
def register_purchase():
    """
    Registra uma 'compra', ou seja, uma retirada de produto do balcão.
    E simula a venda no sistema GALO.
    """
    selected_process_id = controller_window.process_selector.get()
    if not selected_process_id:
        messagebox.showwarning("Seleção Inválida", "Por favor, selecione um processo da lista.")
        return

    try:
        amount_removed = float(controller_window.purchase_entry.get())
        if amount_removed <= 0:
            messagebox.showerror("Erro de Validação", "A quantidade retirada deve ser um número positivo.")
            return
    except ValueError:
        messagebox.showerror("Erro de Validação", "Por favor, insira um valor numérico válido para a quantidade.")
        return

    process_found = False
    sku_do_processo = None
    
    # Encontra o SKU do processo selecionado
    for process in generated_processes:
        if process["sku_process_number"] == selected_process_id:
            sku_do_processo = process["sku"]
            process_found = True
            break
            
    if not process_found:
        messagebox.showerror("Erro", f"Não foi possível encontrar o processo {selected_process_id}.")
        return

    # Verifica o estoque no balcão do SistemaGALO
    current_weight_on_counter = sistema_galo.descongelando[
        (sistema_galo.descongelando['sku'] == sku_do_processo) &
        (sistema_galo.descongelando['localizacao_estante'] == 'balcao')
    ]['kg'].sum()

    if amount_removed > current_weight_on_counter:
        messagebox.showerror(
            "Estoque Insuficiente",
            f"Não é possível retirar {amount_removed:.2f} kg.\n"
            f"O balcão possui apenas {current_weight_on_counter:.2f} kg de {SKU_DEFINITIONS[sku_do_processo]['display_column_label']}."
        )
        return
    
    # Realiza a "venda" no estoque do sistema GALO (remove do balcão)
    # E registra nos dados de venda do GALO para o modelo aprender
    
    # Primeiro, remove do balcão, priorizando os mais antigos
    itens_no_balcao = sistema_galo.descongelando[
        (sistema_galo.descongelando['sku'] == sku_do_processo) &
        (sistema_galo.descongelando['localizacao_estante'] == 'balcao')
    ].sort_values(by='data_entrada_estante', ascending=True).copy() # Assume que data_entrada_estante é uma proxy para "idade" no balcão

    removed_total = 0
    indices_to_drop = []

    for index, row in itens_no_balcao.iterrows():
        if removed_total >= amount_removed:
            break
        
        qtd_disponivel_item = row['kg']
        qtd_a_remover_item = min(qtd_disponivel_item, amount_removed - removed_total)
        
        if qtd_a_remover_item > 0.01:
            # Atualiza o item no DataFrame original (se estiver operando por referência ou ID)
            # Para DataFrames do Pandas, é melhor recriar ou usar loc
            original_index_in_descongelando = sistema_galo.descongelando[
                (sistema_galo.descongelando['sku'] == row['sku']) &
                (sistema_galo.descongelando['validade'] == row['validade']) &
                (sistema_galo.descongelando['data_entrada_estante'] == row['data_entrada_estante']) &
                (sistema_galo.descongelando['localizacao_estante'] == 'balcao')
            ].index.min() # Pega o primeiro índice correspondente

            if not pd.isna(original_index_in_descongelando):
                sistema_galo.descongelando.loc[original_index_in_descongelando, 'kg'] -= qtd_a_remover_item
                removed_total += qtd_a_remover_item

                if sistema_galo.descongelando.loc[original_index_in_descongelando, 'kg'] < 0.001:
                    indices_to_drop.append(original_index_in_descongelando)
    
    # Remove itens que ficaram com 0kg
    if indices_to_drop:
        sistema_galo.descongelando = sistema_galo.descongelando.drop(indices_to_drop).reset_index(drop=True)

    # Adiciona a venda aos dados de vendas históricos do GALO
    data_venda_galo = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=current_day)
    
    # Cria um DataFrame temporário para a nova venda
    new_sale_df = pd.DataFrame([{
        'data_dia': data_venda_galo,
        'sku': sku_do_processo,
        'total_venda_dia_kg': amount_removed
    }])

    # Concatena com os dados existentes. Se já houver uma venda para o mesmo SKU e dia, soma.
    # Primeiro, tenta encontrar e atualizar. Se não encontrar, adiciona.
    existing_sale_index = sistema_galo.dados_vendas[
        (sistema_galo.dados_vendas['data_dia'] == data_venda_galo) &
        (sistema_galo.dados_vendas['sku'] == sku_do_processo)
    ].index

    if not existing_sale_index.empty:
        sistema_galo.dados_vendas.loc[existing_sale_index, 'total_venda_dia_kg'] += amount_removed
    else:
        sistema_galo.dados_vendas = pd.concat([sistema_galo.dados_vendas, new_sale_df], ignore_index=True)
    
    # Re-prepara features e verifica/re-treina o modelo após a adição de dados de vendas
    sistema_galo.preparar_features()
    sistema_galo.verificar_e_re_treinar_modelo()
    sistema_galo.salvar_estado()

    messagebox.showinfo("Sucesso", f"Compra de {amount_removed:.2f} kg registrada para o processo {selected_process_id}.")
    controller_window.purchase_entry.delete(0, tk.END)
    for win in open_abastecedor_windows:
        update_abastecedor_completed_processes_display(win) # Atualiza o abastecedor pois o peso do balcão mudou
    update_controller_weight_panel() # Atualiza o painel do controlador

def update_controller_weight_panel():
    if not (controller_window and controller_window.winfo_exists()):
        return

    processos_prontos = []
    # Usar a lista de completed_day2_processes_by_filial para popular o combobox
    for filial_procs in completed_day2_processes_by_filial.values():
        for pid in filial_procs:
            if pid not in processos_prontos: # Evita duplicatas se um processo por algum motivo aparecer em mais de uma lista (não deveria)
                processos_prontos.append(pid)
    
    # Mostrar informações detalhadas dos processos no painel do controlador
    if hasattr(controller_window, 'current_process_info_frame') and controller_window.current_process_info_frame.winfo_exists():
        for widget in controller_window.current_process_info_frame.winfo_children():
            widget.destroy()
    else:
        controller_window.current_process_info_frame = tk.Frame(controller_window, bd=2, relief="sunken", padx=5, pady=5)
        controller_window.current_process_info_frame.pack(pady=5, fill="x", padx=20)
        
    if not processos_prontos:
        tk.Label(controller_window.current_process_info_frame, text="Nenhum processo pronto para abastecimento.", font=("Arial", 10)).pack(pady=5)
        controller_window.process_selector['values'] = []
        controller_window.process_selector.set('')
        return

    controller_window.process_selector['values'] = sorted(processos_prontos)
    if not controller_window.process_selector.get() in processos_prontos and processos_prontos:
        controller_window.process_selector.set(processos_prontos[0]) # Seleciona o primeiro por padrão

    # Exibe os detalhes do processo selecionado no combobox
    selected_process_id = controller_window.process_selector.get()
    
    process_data = None
    for p in generated_processes:
        if p['sku_process_number'] == selected_process_id:
            process_data = p
            break

    if process_data:
        sku_do_processo = process_data['sku']
        display_name = SKU_DEFINITIONS.get(sku_do_processo, {}).get('display_column_label', 'SKU Desconhecido')

        # Busca as quantidades reais do sistema GALO
        peso_no_balcao_galo = sistema_galo.descongelando[
            (sistema_galo.descongelando['sku'] == sku_do_processo) &
            (sistema_galo.descongelando['localizacao_estante'] == 'balcao')
        ]['kg'].sum()

        estoque_na_estante_galo = sistema_galo.descongelando[
            (sistema_galo.descongelando['sku'] == sku_do_processo) &
            ((sistema_galo.descongelando['localizacao_estante'] == 'estante_esquerda') |
             (sistema_galo.descongelando['localizacao_estante'] == 'estante_central'))
        ]['kg'].sum()

        tk.Label(controller_window.current_process_info_frame, text=f"Detalhes do Processo: {selected_process_id}", font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Label(controller_window.current_process_info_frame, text=f"Produto: {display_name}", font=("Arial", 9)).pack(anchor="w")
        tk.Label(controller_window.current_process_info_frame, text=f"Filial: {process_data['filial']}", font=("Arial", 9)).pack(anchor="w")
        tk.Label(controller_window.current_process_info_frame, text=f"Estoque (Estante): {estoque_na_estante_galo:.2f} kg", font=("Arial", 9), fg="blue").pack(anchor="w")
        tk.Label(controller_window.current_process_info_frame, text=f"No Balcão: {peso_no_balcao_galo:.2f} kg", font=("Arial", 9), fg="green").pack(anchor="w")

        # Exibir previsão para o SKU selecionado
        data_para_previsao_d2 = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=current_day + 2)
        previsao_demanda_d2_df = sistema_galo.prever_demanda(data_para_previsao_d2)
        previsao_demanda_d2 = previsao_demanda_d2_df[previsao_demanda_d2_df['sku'] == sku_do_processo]['qtd_prevista'].iloc[0] if not previsao_demanda_d2_df[previsao_demanda_d2_df['sku'] == sku_do_processo].empty else 0.0
        tk.Label(controller_window.current_process_info_frame, text=f"Previsão Demanda D+2: {previsao_demanda_d2:.2f} kg", font=("Arial", 9), fg="purple").pack(anchor="w")

    controller_window.process_selector.bind("<<ComboboxSelected>>", lambda event: update_controller_weight_panel())


def open_controller_interface():
    global controller_window, login_screen_ref

    parent = login_screen_ref

    if controller_window is None or not controller_window.winfo_exists():
        controller_window = tk.Toplevel()
        controller_window.title("Controlador do Sistema")
        controller_window.geometry("500x750")
        controller_window.transient(parent)
        controller_window.protocol("WM_DELETE_WINDOW", lambda: None)

        label_title = tk.Label(controller_window, text="Painel de Controle", font=("Arial", 20, "bold"))
        label_title.pack(pady=10)

        btn_configure_quantities = tk.Button(controller_window, text="Configurar Quantidades Diárias por SKU", command=open_sku_quantity_config_interface, font=("Arial", 14))
        btn_configure_quantities.pack(pady=10)

        time_frame = tk.LabelFrame(controller_window, text="Controle de Tempo", padx=10, pady=10)
        time_frame.pack(pady=10, fill="x", padx=20)

        controller_window.day_label = tk.Label(time_frame, text=f"Dia Atual: {current_day}", font=("Arial", 12))
        controller_window.day_label.pack(pady=5)

        controller_window.hour_label = tk.Label(time_frame, text=f"Hora Atual: {current_hour:02d}:00", font=("Arial", 12))
        controller_window.hour_label.pack(pady=5)

        tk.Label(time_frame, text="Avançar Horas:", font=("Arial", 12)).pack(pady=(10,0))
        controller_window.hour_jump_entry = tk.Entry(time_frame, font=("Arial", 12), width=10)
        controller_window.hour_jump_entry.insert(0, "1")
        controller_window.hour_jump_entry.pack(pady=5)

        btn_jump_hours = tk.Button(time_frame, text="Avançar X Horas", command=advance_x_hours, font=("Arial", 12))
        btn_jump_hours.pack(pady=5)

        btn_advance_day = tk.Button(time_frame, text="Avançar 1 Dia Completo", command=advance_day_complete, font=("Arial", 12))
        btn_advance_day.pack(pady=5)
        
        purchase_sim_frame = tk.LabelFrame(controller_window, text="Simulador de Compra", padx=10, pady=10)
        purchase_sim_frame.pack(pady=10, fill="x", padx=20)

        tk.Label(purchase_sim_frame, text="Selecione o Processo:", font=("Arial", 12)).pack(pady=5)
        controller_window.process_selector = ttk.Combobox(purchase_sim_frame, state="readonly", font=("Arial", 10))
        controller_window.process_selector.pack(pady=5, fill="x")

        tk.Label(purchase_sim_frame, text="Registrar Retirada/Compra (kg):", font=("Arial", 12)).pack(pady=5)
        controller_window.purchase_entry = tk.Entry(purchase_sim_frame, font=("Arial", 12), width=10)
        controller_window.purchase_entry.pack(pady=5)

        btn_register_purchase = tk.Button(purchase_sim_frame, text="Registrar Compra", command=register_purchase, font=("Arial", 12), bg="#28a745", fg="white")
        btn_register_purchase.pack(pady=10)

        # --- Botão para gerar relatório de previsão do SistemaGALO ---
        btn_gerar_relatorio_previsao = tk.Button(controller_window, text="Gerar Relatório de Descongelamento (Previsão D+2)", 
                                                 command=lambda: sistema_galo.gerar_relatorio(sistema_galo.calcular_descongelamento(sistema_galo.prever_demanda(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=current_day)), datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=current_day + 2))), 
                                                 font=("Arial", 12), bg="gray", fg="white")
        btn_gerar_relatorio_previsao.pack(pady=10)
        # --- Fim do Botão de Relatório ---

        update_controller_weight_panel()
        for win in open_movimentador_windows:
            update_movimentador_processes(win)
        for win in open_abastecedor_windows:
            update_abastecedor_completed_processes_display(win)

    else:
        controller_window.lift()
        update_controller_weight_panel()

def open_sku_quantity_config_interface():
    global sku_quantity_config_window
    window = create_toplevel_window(controller_window, "Configurar Quantidades Diárias por SKU e Filial", "700x500", "sku_quantity_config_window", on_toplevel_close)
    if window:
        window.quantity_entries = {}

        label_title = tk.Label(window, text="Definir Quantidades Padrão por SKU e Filial", font=("Arial", 16, "bold"))
        label_title.pack(pady=10)

        canvas = tk.Canvas(window)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        tk.Label(scrollable_frame, text="Filial", font=("Arial", 10, "bold"), bd=1, relief="solid").grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        
        col = 1
        sku_order = sorted(SKU_DEFINITIONS.keys())
        for sku in sku_order:
            tk.Label(scrollable_frame, text=SKU_DEFINITIONS[sku]["display_column_label"] + f" ({sku})", font=("Arial", 10, "bold"), bd=1, relief="solid").grid(row=0, column=col, sticky="nsew", padx=1, pady=1)
            col += 1

        row = 1
        for filial in KNOWN_FILIAIS:
            tk.Label(scrollable_frame, text=filial, font=("Arial", 10), bd=1, relief="solid").grid(row=row, column=0, sticky="nsew", padx=1, pady=1)
            window.quantity_entries[filial] = {}
            col = 1
            for sku in sku_order:
                current_qty = sku_default_quantities.get(filial, {}).get(sku, 100)
                entry = tk.Entry(scrollable_frame, font=("Arial", 10), width=8, justify="center")
                entry.insert(0, str(current_qty))
                entry.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
                window.quantity_entries[filial][sku] = entry
                col += 1
            row += 1

        def save_quantities():
            global sku_default_quantities
            new_quantities_data = {}
            for filial, sku_entries in window.quantity_entries.items():
                new_quantities_data[filial] = {}
                for sku, entry_widget in sku_entries.items():
                    try:
                        qty = float(entry_widget.get())
                        if qty < 0:
                            messagebox.showerror("Erro de Validação", f"Quantidade para Filial {filial}, SKU {sku} não pode ser negativa.")
                            return
                        new_quantities_data[filial][sku] = qty
                    except ValueError:
                        messagebox.showerror("Erro de Validação", f"Quantidade para Filial {filial}, SKU {sku} deve ser um número válido.")
                        return
            sku_default_quantities = new_quantities_data
            save_sku_quantities(sku_default_quantities)
            messagebox.showinfo("Configuração Salva", "Quantidades padrão salvas com sucesso!")

        btn_save = tk.Button(window, text="Salvar Quantidades", command=save_quantities, font=("Arial", 12), bg="#007BFF", fg="white")
        btn_save.pack(pady=10)


def on_controller_close(window, window_ref_var_name):
    if messagebox.askyesno("Sair", "Tem certeza que deseja fechar o Controlador? Isso encerrará o aplicativo."):
        on_toplevel_close(window, window_ref_var_name)
        login_screen_ref.destroy()
    else:
        window.lift()

# --- Configuração Inicial do Aplicativo ---
# Defina KNOWN_FILIAIS a partir de USERS antes de qualquer uso
KNOWN_FILIAIS = list(set(user["filial"] for user in USERS.values() if user["filial"] != "Todas"))

import json # Importa o módulo json

login_screen_ref = tk.Tk()
login_screen_ref.title("Sistema de Gerenciamento")
login_screen_ref.geometry("400x300")

label_title = tk.Label(login_screen_ref, text="Bem-vindo(a)!", font=("Arial", 16, "bold"))
label_title.pack(pady=20)

login_frame = tk.Frame(login_screen_ref)
login_frame.pack(pady=10)

label_username = tk.Label(login_frame, text="Usuário:", font=("Arial", 12))
label_username.grid(row=0, column=0, padx=5, pady=5, sticky="e")
entry_username = tk.Entry(login_frame, font=("Arial", 12))
entry_username.grid(row=0, column=1, padx=5, pady=5)
entry_username.focus_set()

label_password = tk.Label(login_frame, text="Senha:", font=("Arial", 12))
label_password.grid(row=1, column=0, padx=5, pady=5, sticky="e")
entry_password = tk.Entry(login_frame, show="*", font=("Arial", 12))
entry_password.grid(row=1, column=1, padx=5, pady=5)

btn_login = tk.Button(login_screen_ref, text="Entrar", command=login, font=("Arial", 12), bg="#007BFF", fg="white")
btn_login.pack(pady=10)

# --- Inicialização do SistemaGALO ---
sistema_galo = SistemaGALO()
try:
    sistema_galo.carregar_dados()
    sistema_galo.preparar_features()
    sistema_galo.verificar_e_re_treinar_modelo()
except Exception as e:
    messagebox.showerror("Erro de Inicialização do Modelo", f"Não foi possível inicializar o sistema de previsão: {e}\nPor favor, verifique os arquivos de dados (dados_vendas.xlsx, etc.) e o diretório 'dados'. O aplicativo pode não funcionar corretamente.")
    # Considerar desabilitar funcionalidades de previsão se houver erro crítico
    # Ou permitir que o app continue com funcionalidades limitadas
# --- Fim Inicialização SistemaGALO ---

load_sku_quantities() # Carrega as quantidades padrão

# --- Initial Process Generation and State Update ---
# A geração inicial agora é chamada através do advance_day_complete para simular o início do dia
# Ou pode ser chamada aqui para o 'Dia 0' inicial
# Para o 'Dia 0', se não houver processos, geramos baseados nas quantidades padrão iniciais


update_process_states_on_time_change()
# --- End of Initial Process Generation and State Update ---

open_controller_interface() # Abre a interface do controlador por padrão para o administrador

login_screen_ref.mainloop()