import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import simpledialog
import json
import os
from datetime import datetime, timedelta
import csv
from main import SistemaGALO # Certifique-se de que main.py está no mesmo diretório

# --- NOVAS IMPORTAÇÕES PARA BACKTESTING ---
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
# --- FIM NOVAS IMPORTAÇÕES ---

# --- INÍCIO DA CORREÇÃO ---
# Garante que os caminhos para os arquivos de dados sejam absolutos,
# baseados na localização do script. Isso evita problemas ao executar
# o script de diretórios diferentes.
script_dir = os.path.dirname(os.path.abspath(__file__))

# Nome do arquivo JSON para armazenar os usuários
USERS_FILE = os.path.join(script_dir, "users.json")
# Nome do arquivo JSON para armazenar as quantidades padrão por SKU e Filial
SKU_QUANTITIES_FILE = os.path.join(script_dir, "sku_quantities.json")
# Nome do arquivo de Log para registrar eventos
LOG_FILE = os.path.join(script_dir, "log_movimentacoes.csv")
# --- FIM DA CORREÇÃO ---

# Inicialize o previsor de demanda
previsor = SistemaGALO()

def inicializar_json_com_previsoes_reais():
    # Esta função parece ser um duplicado de inicialização/treinamento
    # Para evitar conflitos, vou mantê-la, mas o principal previsor
    # é o global inicializado acima.
    dados_path = os.path.join(script_dir, 'dados_vendas.csv')
    temp_previsor = SistemaGALO() # Usar um temp_previsor para não conflitar com o global
    temp_previsor.carregar_dados_vendas(dados_path)
    temp_previsor.treinar_modelo()
    print("Previsões reais inicializadas (usando temp_previsor).")


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
    "FRANGO_INTEIRO": {"display_column_label": "Frango Inteiro Congelado"},
    "COXA_FRANGO": {"display_column_label": "Coxa de Frango Congelada"},
    "SOBRECOXA_FRANGO": {"display_column_label": "Sobrecoxa de Frango Congelada"},
    "ASA_FRANGO": {"display_column_label": "Asa de Frango Congelada"},
    "PEITO_FRANGO": {"display_column_label": "Peito de Frango Congelado"}
}

# Filiais conhecidas, usadas para inicialização de estoque e outras operações
KNOWN_FILIAIS = ["Filial A", "Filial B"]

# Simulação de tempo
current_day = datetime.now().date()
current_hour = 0
last_generated_day = None # Usado para controlar a geração diária

# Variáveis para controle de janelas Toplevel
manager_window = None
movimentador_window = None
abastecedor_window = None
comprador_window = None

# Lista para armazenar referências de janelas de relatório para poder fechá-las
report_windows = []

# Variáveis para simulação de processos
generated_processes = {} # Dicionário para armazenar os processos diários


# --- FUNÇÃO DE BACKTESTING (ADICIONADA AQUI) ---
def perform_backtesting_and_generate_report():
    print("Iniciando o processo de backtesting...")

    global previsor, KNOWN_FILIAIS, SKU_DEFINITIONS, script_dir # Garante que as globais sejam acessíveis

    if previsor.modelo is None:
        print("Modelo não treinado. Treinando agora...")
        try:
            previsor.verificar_e_re_treinar_modelo() # Chama o método de re-treinamento
        except Exception as e:
            print(f"Erro ao treinar o modelo para backtesting: {e}")
            messagebox.showerror("Erro no Modelo", f"Erro ao treinar o modelo para backtesting: {e}")
            return

    if previsor.dados_vendas is None or previsor.dados_vendas.empty:
        print("Dados de vendas não carregados. Carregando agora...")
        dados_vendas_path = os.path.join(script_dir, 'dados_vendas.csv')
        try:
            previsor.carregar_dados_vendas(dados_vendas_path)
        except Exception as e:
            print(f"Erro ao carregar dados de vendas para backtesting: {e}")
            messagebox.showerror("Erro de Dados", f"Erro ao carregar dados de vendas para backtesting: {e}")
            return

    datas_unicas_vendas = previsor.dados_vendas['data_dia'].unique()
    datas_unicas_vendas = pd.to_datetime(datas_unicas_vendas).sort_values()

    if len(datas_unicas_vendas) < 3: # Precisamos de dados suficientes para pelo menos uma previsão D+2
        print("Dados de vendas insuficientes para backtesting (precisa de pelo menos 3 datas).")
        messagebox.showinfo("Backtesting", "Dados de vendas insuficientes para backtesting (mínimo de 3 datas necessárias).")
        return

    resultados_comparacao = []

    for data_prevista_real in datas_unicas_vendas:
        # A data_base_previsao é o "hoje" em que a previsão para data_prevista_real (D+2) seria feita
        data_base_previsao = data_prevista_real - timedelta(days=2)

        # Gerar previsões para (data_base_previsao + 2), que é data_prevista_real
        previsoes_do_modelo = previsor.prever_demanda(data_base_previsao)

        # Filtrar dados de vendas reais para a data_prevista_real
        vendas_reais_data = previsor.dados_vendas[previsor.dados_vendas['data'] == data_prevista_real]

        for sku_key in SKU_DEFINITIONS.keys(): # Itera sobre todas as chaves de SKUs
            sku = sku_key
            for filial in KNOWN_FILIAIS:
                # Encontrar a previsão correspondente do modelo
                previsao_sku_filial = next((
                    p.get('demanda_prevista', 0)
                    for p in previsoes_do_modelo
                    if p.get('sku') == sku and p.get('filial') == filial and p.get('data') == data_prevista_real.strftime('%Y-%m-%d')
                ), 0) # Retorna 0 se não encontrar previsão

                # Encontrar a venda real correspondente
                venda_real_sku_filial = vendas_reais_data[
                    (vendas_reais_data['SKU'] == sku) &
                    (vendas_reais_data['Filial'] == filial)
                ]['Quantidade'].sum() # Soma, caso haja múltiplas entradas para o mesmo SKU/Filial no dia

                resultados_comparacao.append({
                    'Data': data_prevista_real.strftime('%Y-%m-%d'),
                    'Filial': filial,
                    'SKU': sku,
                    'Venda Real (kg)': venda_real_sku_filial,
                    'Previsão (kg)': previsao_sku_filial
                })

    # Gerar um DataFrame com os resultados e calcular métricas de erro
    df_resultados = pd.DataFrame(resultados_comparacao)

    if not df_resultados.empty:
        # Calcular Erro Absoluto
        df_resultados['Erro Absoluto'] = abs(df_resultados['Venda Real (kg)'] - df_resultados['Previsão (kg)'])
        
        # Calcular Erro Percentual, tratando divisão por zero
        df_resultados['Erro Percentual'] = (df_resultados['Erro Absoluto'] / df_resultados['Venda Real (kg)']) * 100
        df_resultados.loc[df_resultados['Venda Real (kg)'] == 0, 'Erro Percentual'] = float('nan') # NaN para vendas zero

        # Salvar o relatório em um arquivo Excel
        relatorios_dir = os.path.join(script_dir, 'relatorios')
        os.makedirs(relatorios_dir, exist_ok=True)
        nome_arquivo_relatorio = os.path.join(relatorios_dir, f"relatorio_backtesting_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        
        df_resultados.to_excel(nome_arquivo_relatorio, index=False)

        print(f"Relatório de Backtesting gerado: {nome_arquivo_relatorio}")
        messagebox.showinfo("Backtesting Concluído", f"Relatório de backtesting gerado em:\n{nome_arquivo_relatorio}")

        # Exibir resumo das métricas de erro
        print("\n--- Resumo das Métricas de Erro (para vendas reais > 0) ---")
        df_erros_validos = df_resultados[df_resultados['Venda Real (kg)'] > 0].dropna(subset=['Erro Percentual'])
        if not df_erros_validos.empty:
            mae = mean_absolute_error(df_erros_validos['Venda Real (kg)'], df_erros_validos['Previsão (kg)'])
            rmse = mean_squared_error(df_erros_validos['Venda Real (kg)'], df_erros_validos['Previsão (kg)'], squared=False)
            mape = df_erros_validos['Erro Percentual'].mean()

            print(f"MAE (Erro Médio Absoluto): {mae:.2f} kg")
            print(f"RMSE (Raiz do Erro Quadrático Médio): {rmse:.2f} kg")
            print(f"MAPE (Erro Percentual Médio Absoluto): {mape:.2f}%")
        else:
            print("Não há dados de vendas reais > 0 para calcular métricas de erro válidas.")
    else:
        print("Nenhum dado de comparação gerado para o backtesting.")
        messagebox.showinfo("Backtesting", "Nenhum dado de comparação gerado para o backtesting.")

# --- FIM FUNÇÃO DE BACKTESTING ---


# --- Funções para Janelas ---
def create_toplevel_window(parent_screen, title, geometry, window_ref_var_name, on_close_callback=None, allow_multiple=False, window_list_ref=None):
    current_window_ref = globals().get(window_ref_var_name)
    if not allow_multiple and (current_window_ref is not None and current_window_ref.winfo_exists()):
        current_window_ref.lift()
        return None
    else:
        new_window = tk.Toplevel(parent_screen)
        new_window.title(title)
        new_window.geometry(geometry)
        # new_window.transient(parent_screen) # COMENTADO CONFORME AJUSTE ANTERIOR
        # new_window.grab_set() # COMENTE OU REMOVA SE ESTIVER PRESENTE E CAUSANDO PROBLEMAS

        if on_close_callback:
            new_window.protocol("WM_DELETE_WINDOW", lambda: on_toplevel_close(new_window, window_ref_var_name, allow_multiple, window_list_ref))
        if allow_multiple and window_list_ref is not None:
            window_list_ref.append(new_window)
        else:
            globals()[window_ref_var_name] = new_window
        
        # Garante que a janela seja exibida e trazida para a frente
        new_window.deiconify()
        new_window.lift()

        return new_window

def on_toplevel_close(window, window_ref_var_name):
    window.destroy()
    # Limpa a referência global para a janela fechada
    if window_ref_var_name == "movimentador_window_ref":
        global movimentador_window_ref
        movimentador_window_ref = None
    elif window_ref_var_name == "abastecedor_window_ref":
        global abastecedor_window_ref
        abastecedor_window_ref = None
    elif window_ref_var_name == "comprador_window_ref":
        global comprador_window_ref
        comprador_window_ref = None
    elif window_ref_var_name == "admin_window_ref":
        global admin_window_ref
        admin_window_ref = None

    # Reexibe a janela de login quando a janela secundária é fechada
    login_screen_ref.deiconify() # Esta linha é a chave!

# --- Funções de gerenciamento de Usuários (simplificadas para o contexto) ---
# Implemente as funções load_users, save_users, add_user, remove_user, get_sku_quantity, set_sku_quantity aqui
# ou certifique-se de que elas estão presentes no seu arquivo Frango_app.py
# Exemplo de stubs (se você já as tem, ignore):

# load_users, save_users, etc. ...
# Apenas stubs para compilar. Substitua pelo seu código real se necessário.
def load_users():
    global USERS
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            USERS = json.load(f)
            print("Usuários carregados.")
    else:
        print("Arquivo de usuários não encontrado. Usando usuários padrão.")

def save_users():
    with open(USERS_FILE, 'w') as f:
        json.dump(USERS, f, indent=4)
        print("Usuários salvos.")

def add_user(username, password, role, filial):
    if username and password and role and filial:
        if username in USERS:
            messagebox.showwarning("Erro", "Nome de usuário já existe.")
            return
        USERS[username] = {"password": password, "role": role, "filial": filial}
        save_users()
        messagebox.showinfo("Sucesso", f"Usuário {username} adicionado.")
    else:
        messagebox.showwarning("Erro", "Todos os campos devem ser preenchidos.")

def remove_user(username, update_callback):
    if username in USERS:
        if messagebox.askyesno("Confirmar", f"Tem certeza que deseja remover o usuário {username}?"):
            del USERS[username]
            save_users()
            messagebox.showinfo("Sucesso", f"Usuário {username} removido.")
            update_callback() # Atualiza a combobox
    else:
        messagebox.showwarning("Erro", "Usuário não encontrado.")

sku_quantities = {} # Dicionário global para armazenar quantidades padrão por SKU e Filial

def load_sku_quantities():
    global sku_quantities
    if os.path.exists(SKU_QUANTITIES_FILE):
        with open(SKU_QUANTITIES_FILE, 'r') as f:
            sku_quantities = json.load(f)
            print("Quantidades padrão de SKU carregadas.")
    else:
        print("Arquivo de quantidades padrão de SKU não encontrado. Usando padrões internos.")

def save_sku_quantities():
    with open(SKU_QUANTITIES_FILE, 'w') as f:
        json.dump(sku_quantities, f, indent=4)
        print("Quantidades padrão de SKU salvas.")

def get_sku_quantity(sku, filial):
    return sku_quantities.get(sku, {}).get(filial, 0) # Retorna 0 se não encontrar

def set_sku_quantity(sku, filial, quantity):
    if sku not in sku_quantities:
        sku_quantities[sku] = {}
    sku_quantities[sku][filial] = quantity
    save_sku_quantities()

# Funções de simulação diária e status (certifique-se que o seu código real está aqui)
# Apenas stubs para compilar. Substitua pelo seu código real se necessário.
def show_process_status():
    messagebox.showinfo("Status de Processos", "Função de status de processos a ser implementada/detalhada.")

def perform_daily_process_generation():
    # Isso deve ser o seu código existente para gerar processos diários
    print("Gerando processos diários (placeholder)...")
    # Exemplo simples:
    global generated_processes, current_day
    generated_processes[current_day.strftime('%Y-%m-%d')] = {
        "FRANGO_INTEIRO": {"Filial A": {"descongelar": 50, "produzir": 100}}
    }

def advance_day_complete(label_date_widget, parent_window):
    global current_day, current_hour, last_generated_day, generated_processes
    
    # Simula o avanço do dia completo
    if current_hour < 23: # Garante que o dia anterior foi "concluído"
        messagebox.showwarning("Avançar Dia", "Por favor, simule o avanço do tempo até o final do dia (23:00) antes de avançar para o próximo dia completo.")
        return

    # Salva o estado atual antes de avançar
    previsor.salvar_estado_sistema()
    
    current_day += timedelta(days=1)
    current_hour = 0 # Reseta a hora para o início do novo dia
    label_date_widget.config(text=f"Data Atual Simulada: {current_day.strftime('%d/%m/%Y')}")
    print(f"Dia avançado para: {current_day.strftime('%d/%m/%Y')}")

    # Gera novos processos para o novo dia
    perform_daily_process_generation()
    
    # Atualiza status dos processos e relatórios (chama as funções que você já tem)
    update_process_states_on_time_change()

    messagebox.showinfo("Avanço de Dia", f"O sistema avançou para {current_day.strftime('%d/%m/%Y')}.")

def update_process_states_on_time_change():
    # Isso deve ser o seu código existente para atualizar os estados dos processos
    print("Atualizando estados de processo (placeholder)...")


def open_movimentador_interface():
    global movimentador_window, current_user_filial
    if movimentador_window is None or not movimentador_window.winfo_exists():
        movimentador_window = create_toplevel_window(login_screen_ref, f"Interface do Movimentador - {current_user_filial}", "600x400", "movimentador_window", on_close_callback=True)
        if movimentador_window:
            tk.Label(movimentador_window, text=f"Bem-vindo, Movimentador da {current_user_filial}!", font=("Arial", 14)).pack(pady=20)
            
            # Adicionar funcionalidade real de movimentação
            # Exibir estoque atual
            btn_show_estoque = ttk.Button(movimentador_window, text="Ver Estoque", command=lambda: show_estoque(current_user_filial))
            btn_show_estoque.pack(pady=10)

            # Formulário de Movimentação (Exemplo)
            mov_frame = ttk.LabelFrame(movimentador_window, text="Registrar Movimentação")
            mov_frame.pack(pady=10, padx=10, fill="x")

            tk.Label(mov_frame, text="SKU:").grid(row=0, column=0, padx=5, pady=5)
            sku_mov_combo = ttk.Combobox(mov_frame, values=list(SKU_DEFINITIONS.keys()), state="readonly")
            sku_mov_combo.grid(row=0, column=1, padx=5, pady=5)
            sku_mov_combo.set(list(SKU_DEFINITIONS.keys())[0])

            tk.Label(mov_frame, text="Quantidade (kg):").grid(row=1, column=0, padx=5, pady=5)
            qty_mov_entry = tk.Entry(mov_frame)
            qty_mov_entry.grid(row=1, column=1, padx=5, pady=5)

            tk.Label(mov_frame, text="Tipo:").grid(row=2, column=0, padx=5, pady=5)
            tipo_mov_combo = ttk.Combobox(mov_frame, values=["ENTRADA", "SAIDA"], state="readonly")
            tipo_mov_combo.grid(row=2, column=1, padx=5, pady=5)
            tipo_mov_combo.set("SAIDA")

            btn_registrar_mov = ttk.Button(mov_frame, text="Registrar", command=lambda: registrar_movimentacao_ui(current_user_filial, sku_mov_combo.get(), qty_mov_entry.get(), tipo_mov_combo.get()))
            btn_registrar_mov.grid(row=3, column=0, columnspan=2, pady=10)
    else:
        movimentador_window.lift()

def registrar_movimentacao_ui(filial, sku, quantidade_str, tipo):
    try:
        quantidade = float(quantidade_str)
        if quantidade <= 0:
            messagebox.showwarning("Erro", "Quantidade deve ser maior que zero.")
            return
        
        # Chama o método do SistemaGALO para registrar a movimentação
        previsor.registrar_movimentacao(sku, filial, quantidade, tipo)
        messagebox.showinfo("Sucesso", f"Movimentação de {quantidade}kg de {sku} ({tipo}) na {filial} registrada.")
        show_estoque(filial) # Atualiza o estoque exibido
    except ValueError:
        messagebox.showwarning("Erro", "Quantidade inválida. Por favor, insira um número.")
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao registrar movimentação: {e}")

def show_estoque(filial_para_mostrar):
    estoque_str = f"Estoque Atual para {filial_para_mostrar}:\n"
    for sku_key, sku_label in SKU_DEFINITIONS.items():
        qty = previsor.estoque.get(sku_key, {}).get(filial_para_mostrar, 0)
        estoque_str += f"{sku_label['display_column_label']}: {qty:.2f} kg\n"
    messagebox.showinfo("Estoque Atual", estoque_str)

def open_abastecedor_interface():
    global abastecedor_window, current_user_filial
    if abastecedor_window is None or not abastecedor_window.winfo_exists():
        abastecedor_window = create_toplevel_window(login_screen_ref, f"Interface do Abastecedor - {current_user_filial}", "600x400", "abastecedor_window", on_close_callback=True)
        if abastecedor_window:
            tk.Label(abastecedor_window, text=f"Bem-vindo, Abastecedor da {current_user_filial}!", font=("Arial", 14)).pack(pady=20)
            
            # Adicionar funcionalidades de abastecimento
            # Exibir status de descongelamento e estoque
            btn_status_abastecimento = ttk.Button(abastecedor_window, text="Ver Status Abastecimento/Estoque", command=lambda: show_abastecimento_status(current_user_filial))
            btn_status_abastecimento.pack(pady=10)

            # Formulário de Abastecimento (Exemplo)
            abast_frame = ttk.LabelFrame(abastecedor_window, text="Registrar Abastecimento (Descongelamento Concluído)")
            abast_frame.pack(pady=10, padx=10, fill="x")

            tk.Label(abast_frame, text="SKU:").grid(row=0, column=0, padx=5, pady=5)
            sku_abast_combo = ttk.Combobox(abast_frame, values=list(SKU_DEFINITIONS.keys()), state="readonly")
            sku_abast_combo.grid(row=0, column=1, padx=5, pady=5)
            sku_abast_combo.set(list(SKU_DEFINITIONS.keys())[0])

            tk.Label(abast_frame, text="Quantidade (kg):").grid(row=1, column=0, padx=5, pady=5)
            qty_abast_entry = tk.Entry(abast_frame)
            qty_abast_entry.grid(row=1, column=1, padx=5, pady=5)

            btn_registrar_abast = ttk.Button(abast_frame, text="Registrar Descongelamento Concluído", command=lambda: registrar_descongelamento_concluido_ui(current_user_filial, sku_abast_combo.get(), qty_abast_entry.get()))
            btn_registrar_abast.grid(row=2, column=0, columnspan=2, pady=10)
    else:
        abastecedor_window.lift()

def show_abastecimento_status(filial):
    status_str = f"Status de Abastecimento para {filial}:\n"
    # Adicionar informações de estoque
    status_str += f"\nEstoque Atual:\n"
    for sku_key, sku_label in SKU_DEFINITIONS.items():
        qty_estoque = previsor.estoque.get(sku_key, {}).get(filial, 0)
        status_str += f"{sku_label['display_column_label']}: {qty_estoque:.2f} kg (Estoque)\n"
    
    # Adicionar informações de descongelamento
    status_str += f"\nEm Descongelamento:\n"
    for sku_key, sku_label in SKU_DEFINITIONS.items():
        qty_desc = previsor.descongelando.get(sku_key, {}).get(filial, 0)
        status_str += f"{sku_label['display_column_label']}: {qty_desc:.2f} kg\n"
    
    messagebox.showinfo("Status de Abastecimento", status_str)

def registrar_descongelamento_concluido_ui(filial, sku, quantidade_str):
    try:
        quantidade = float(quantidade_str)
        if quantidade <= 0:
            messagebox.showwarning("Erro", "Quantidade deve ser maior que zero.")
            return
        
        # Atualiza o estoque e registra a movimentação
        previsor.registrar_descongelamento_concluido(sku, filial, quantidade)
        messagebox.showinfo("Sucesso", f"{quantidade}kg de {sku} descongelados e adicionados ao estoque da {filial}.")
        show_abastecimento_status(filial) # Atualiza o status
    except ValueError:
        messagebox.showwarning("Erro", "Quantidade inválida. Por favor, insira um número.")
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao registrar descongelamento: {e}")

def open_comprador_interface():
    global comprador_window, current_user_filial
    if comprador_window is None or not comprador_window.winfo_exists():
        comprador_window = create_toplevel_window(login_screen_ref, f"Interface do Comprador - {current_user_filial}", "600x400", "comprador_window", on_close_callback=True)
        if comprador_window:
            tk.Label(comprador_window, text=f"Bem-vindo, Comprador da {current_user_filial}!", font=("Arial", 14)).pack(pady=20)
            
            # Adicionar funcionalidades para o comprador
            # Exibir necessidades de compra (Ponto de Pedido)
            btn_show_necessidades = ttk.Button(comprador_window, text="Ver Necessidades de Compra", command=lambda: show_necessidades_compra(current_user_filial))
            btn_show_necessidades.pack(pady=10)
    else:
        comprador_window.lift()

def show_necessidades_compra(filial):
    necessidades_str = f"Necessidades de Compra para {filial} (Baseado no Ponto de Pedido):\n"
    compra_necessaria = False
    for sku_key, sku_label in SKU_DEFINITIONS.items():
        estoque_atual = previsor.estoque.get(sku_key, {}).get(filial, 0)
        ponto_pedido = previsor.ponto_pedido_default # Ou defina por SKU/Filial
        
        if estoque_atual < ponto_pedido:
            qtd_a_comprar = previsor.qtd_pedido_default # Ou defina por SKU/Filial
            necessidades_str += f"{sku_label['display_column_label']}: Estoque atual {estoque_atual:.2f}kg < Ponto de Pedido {ponto_pedido:.2f}kg. Sugestão de compra: {qtd_a_comprar:.2f}kg.\n"
            compra_necessaria = True
    
    if not compra_necessaria:
        necessidades_str += "Nenhuma necessidade de compra identificada no momento."
    
    messagebox.showinfo("Necessidades de Compra", necessidades_str)

# --- Funções de Interface ---

def open_manager_interface():
    global manager_window, current_user_role, current_user_filial
    if manager_window is None or not manager_window.winfo_exists():
        manager_window = create_toplevel_window(login_screen_ref, "Gerenciamento do Sistema - Controller", "800x600", "manager_window", on_close_callback=True)
        if manager_window:
            # Layout principal com Notebook (abas)
            notebook = ttk.Notebook(manager_window)
            notebook.pack(pady=10, expand=True, fill="both")

            # Aba de Simulação de Tempo
            time_frame = ttk.Frame(notebook)
            notebook.add(time_frame, text="Simulação de Tempo")

            # Conteúdo da Aba de Simulação de Tempo
            label_current_date = tk.Label(time_frame, text=f"Data Atual Simulada: {current_day.strftime('%d/%m/%Y')}", font=("Arial", 12))
            label_current_date.pack(pady=10)

            btn_advance_day = ttk.Button(time_frame, text="Avançar Dia (Completo)", command=lambda: advance_day_complete(label_current_date, manager_window))
            btn_advance_day.pack(pady=5)
            
            # --- Botão para o Backtesting (NOVO) ---
            btn_backtesting = ttk.Button(time_frame, text="Executar Backtesting de Previsão", command=perform_backtesting_and_generate_report)
            btn_backtesting.pack(pady=10)
            # --- FIM NOVO BOTÃO ---


            # Aba de Status de Processos
            status_frame = ttk.Frame(notebook)
            notebook.add(status_frame, text="Status de Processos")

            # Conteúdo da Aba de Status de Processos
            btn_show_processes = ttk.Button(status_frame, text="Ver Status dos Processos", command=show_process_status)
            btn_show_processes.pack(pady=10)

            # Aba de Relatórios
            reports_frame = ttk.Frame(notebook)
            notebook.add(reports_frame, text="Relatórios")
            
            # Conteúdo da Aba de Relatórios
            btn_gerar_relatorio_movimentacao = ttk.Button(reports_frame, text="Gerar Relatório de Movimentação", command=previsor.gerar_relatorio_movimentacao)
            btn_gerar_relatorio_movimentacao.pack(pady=5)

            btn_gerar_relatorio_abastecimento = ttk.Button(reports_frame, text="Gerar Relatório de Abastecimento", command=previsor.gerar_relatorio_abastecimento)
            btn_gerar_relatorio_abastecimento.pack(pady=5)

            btn_gerar_relatorio_descongelamento = ttk.Button(reports_frame, text="Gerar Relatório de Descongelamento", command=previsor.gerar_relatorio_descongelamento)
            btn_gerar_relatorio_descongelamento.pack(pady=5)

            btn_gerar_relatorio_consolidado = ttk.Button(reports_frame, text="Gerar Relatório Consolidado Filial 7", command=previsor.gerar_relatorio_consolidado_filial7)
            btn_gerar_relatorio_consolidado.pack(pady=5)

            # Aba de Gerenciamento de Usuários (para administradores)
            if current_user_role == "controller": # Apenas admin pode gerenciar usuários
                user_management_frame = ttk.Frame(notebook)
                notebook.add(user_management_frame, text="Gerenciar Usuários")

                # Conteúdo da Aba de Gerenciamento de Usuários
                label_new_username = tk.Label(user_management_frame, text="Novo Usuário:", font=("Arial", 10))
                label_new_username.grid(row=0, column=0, padx=5, pady=5)
                entry_new_username = tk.Entry(user_management_frame, font=("Arial", 10))
                entry_new_username.grid(row=0, column=1, padx=5, pady=5)

                label_new_password = tk.Label(user_management_frame, text="Senha:", font=("Arial", 10))
                label_new_password.grid(row=1, column=0, padx=5, pady=5)
                entry_new_password = tk.Entry(user_management_frame, font=("Arial", 10), show="*")
                entry_new_password.grid(row=1, column=1, padx=5, pady=5)

                label_new_role = tk.Label(user_management_frame, text="Função:", font=("Arial", 10))
                label_new_role.grid(row=2, column=0, padx=5, pady=5)
                combo_new_role = ttk.Combobox(user_management_frame, values=["movimentador", "abastecedor", "comprador", "controller"], state="readonly")
                combo_new_role.grid(row=2, column=1, padx=5, pady=5)
                combo_new_role.set("movimentador") # Valor padrão

                label_new_filial = tk.Label(user_management_frame, text="Filial:", font=("Arial", 10))
                label_new_filial.grid(row=3, column=0, padx=5, pady=5)
                combo_new_filial = ttk.Combobox(user_management_frame, values=KNOWN_FILIAIS + ["Todas"], state="readonly")
                combo_new_filial.grid(row=3, column=1, padx=5, pady=5)
                combo_new_filial.set(KNOWN_FILIAIS[0]) # Valor padrão

                btn_add_user = ttk.Button(user_management_frame, text="Adicionar Usuário", command=lambda: add_user(entry_new_username.get(), entry_new_password.get(), combo_new_role.get(), combo_new_filial.get()))
                btn_add_user.grid(row=4, column=0, columnspan=2, pady=5)

                label_remove_user = tk.Label(user_management_frame, text="Remover Usuário:", font=("Arial", 10))
                label_remove_user.grid(row=5, column=0, padx=5, pady=5)
                combo_remove_user = ttk.Combobox(user_management_frame, values=list(USERS.keys()), state="readonly")
                combo_remove_user.grid(row=5, column=1, padx=5, pady=5)
                
                def update_remove_user_combobox():
                    combo_remove_user['values'] = list(USERS.keys())
                    if list(USERS.keys()):
                        combo_remove_user.set(list(USERS.keys())[0])
                    else:
                        combo_remove_user.set("")

                update_remove_user_combobox() # Carrega usuários existentes na combobox

                btn_remove_user = ttk.Button(user_management_frame, text="Remover Usuário", command=lambda: remove_user(combo_remove_user.get(), update_remove_user_combobox))
                btn_remove_user.grid(row=6, column=0, columnspan=2, pady=5)

            # Aba de Gerenciamento de Quantidades Padrão (para administradores)
            if current_user_role == "controller": # Apenas admin pode gerenciar quantidades
                sku_quantities_frame = ttk.Frame(notebook)
                notebook.add(sku_quantities_frame, text="Gerenciar Qtd. Padrão")

                # Variáveis para armazenar as entradas
                sku_var = tk.StringVar(sku_quantities_frame)
                filial_var = tk.StringVar(sku_quantities_frame)
                quantity_var = tk.StringVar(sku_quantities_frame)

                # Combobox para SKUs
                label_sku_config = tk.Label(sku_quantities_frame, text="SKU:", font=("Arial", 10))
                label_sku_config.grid(row=0, column=0, padx=5, pady=5)
                combo_sku_config = ttk.Combobox(sku_quantities_frame, textvariable=sku_var, values=list(SKU_DEFINITIONS.keys()), state="readonly")
                combo_sku_config.grid(row=0, column=1, padx=5, pady=5)
                combo_sku_config.bind("<<ComboboxSelected>>", lambda e: update_quantity_entry(sku_var.get(), filial_var.get(), quantity_var))

                # Combobox para Filiais
                label_filial_config = tk.Label(sku_quantities_frame, text="Filial:", font=("Arial", 10))
                label_filial_config.grid(row=1, column=0, padx=5, pady=5)
                combo_filial_config = ttk.Combobox(sku_quantities_frame, textvariable=filial_var, values=KNOWN_FILIAIS, state="readonly")
                combo_filial_config.grid(row=1, column=1, padx=5, pady=5)
                combo_filial_config.bind("<<ComboboxSelected>>", lambda e: update_quantity_entry(sku_var.get(), filial_var.get(), quantity_var))

                # Campo para Quantidade
                label_quantity_config = tk.Label(sku_quantities_frame, text="Qtd. Padrão (kg):", font=("Arial", 10))
                label_quantity_config.grid(row=2, column=0, padx=5, pady=5)
                entry_quantity_config = tk.Entry(sku_quantities_frame, textvariable=quantity_var, font=("Arial", 10))
                entry_quantity_config.grid(row=2, column=1, padx=5, pady=5)

                btn_save_quantity = ttk.Button(sku_quantities_frame, text="Salvar Qtd. Padrão", command=lambda: save_sku_quantity(sku_var.get(), filial_var.get(), quantity_var.get(), entry_quantity_config))
                btn_save_quantity.grid(row=3, column=0, columnspan=2, pady=5)

                # Funções auxiliares para gerenciamento de quantidades (devem estar definidas antes de serem usadas)
                def update_quantity_entry(sku, filial, quantity_var_obj):
                    if sku and filial:
                        qty = get_sku_quantity(sku, filial)
                        quantity_var_obj.set(str(qty))
                    else:
                        quantity_var_obj.set("")

                def save_sku_quantity(sku, filial, quantity_str, entry_widget):
                    if not sku or not filial:
                        messagebox.showwarning("Erro", "SKU e Filial devem ser selecionados.")
                        return
                    try:
                        quantity = float(quantity_str)
                        if quantity < 0:
                            messagebox.showwarning("Erro", "Quantidade não pode ser negativa.")
                            return
                        set_sku_quantity(sku, filial, quantity)
                        messagebox.showinfo("Sucesso", f"Quantidade padrão para {sku} na {filial} salva como {quantity} kg.")
                        update_quantity_entry(sku, filial, quantity_var) # Atualiza a entry após salvar
                    except ValueError:
                        messagebox.showwarning("Erro", "Quantidade inválida. Por favor, insira um número.")
                        entry_widget.delete(0, tk.END) # Limpa o campo se for inválido


    else:
        manager_window.lift()

# --- Funções de Login ---
def login():
    username = entry_username.get()
    password = entry_password.get()

    user_data = USERS.get(username)

    if user_data and user_data["password"] == password:
        messagebox.showinfo("Login", "Login bem-sucedido!")
        global current_user_role, current_user_filial
        current_user_role = user_data["role"]
        current_user_filial = user_data["filial"]

        login_screen_ref.withdraw() # Oculta a janela de login

        if current_user_role == "movimentador":
            open_movimentador_interface() # Agora, open_*_interface não precisa receber login_screen_ref se a referencia for global
        elif current_user_role == "abastecedor":
            open_abastecedor_interface()
        elif current_user_role == "comprador":
            open_comprador_interface()
        elif current_user_role == "controller": # Admin role
            open_manager_interface()
    else:
        messagebox.showerror("Login", "Usuário ou senha inválidos.")


# --- Configuração Inicial do Aplicativo ---
login_screen_ref = tk.Tk()
login_screen_ref.title("Sistema de Gerenciamento")
login_screen_ref.geometry("400x300")

label_title = tk.Label(login_screen_ref, text="Bem-vindo(a)! Sistema GALO", font=("Arial", 16, "bold"))
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
entry_password = tk.Entry(login_frame, font=("Arial", 12), show="*")
entry_password.grid(row=1, column=1, padx=5, pady=5)

btn_login = ttk.Button(login_frame, text="Login", command=login)
btn_login.grid(row=2, column=0, columnspan=2, pady=10)

# --- Inicialização SistemaGALO ---
# O previsor é inicializado globalmente no topo do arquivo.
# Carregar dados e treinar modelo na inicialização para garantir que esteja pronto.
try:
    dados_vendas_path_init = os.path.join(script_dir, 'dados_vendas.csv')
    previsor.carregar_dados_vendas(dados_vendas_path_init)
    previsor.verificar_e_re_treinar_modelo()
except Exception as e:
    messagebox.showerror("Erro de Inicialização do Modelo", f"Não foi possível inicializar o sistema de previsão: {e}\nPor favor, verifique os arquivos de dados (dados_vendas.csv) e o diretório 'dados'. O aplicativo pode não funcionar corretamente.")
# --- Fim Inicialização SistemaGALO ---

# Outras inicializações...
load_users() # Carrega usuários do JSON
load_sku_quantities() # Carrega as quantidades padrão

# --- Initial Process Generation and State Update ---
if not generated_processes: # Se nenhum processo foi gerado ainda (primeira execução)
    print("Iniciando a primeira geração de processos para o Dia 0.")
    current_hour = 6 # Define a hora para 6 para permitir a geração inicial
    perform_daily_process_generation() # Chama a função que já usa current_day e KNOWN_FILIAIS
    current_hour = 0 # Reseta a hora para 0 para o ciclo normal

update_process_states_on_time_change()
# --- End of Initial Process Generation and State Update ---

login_screen_ref.mainloop()