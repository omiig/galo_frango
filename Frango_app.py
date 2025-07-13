import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import simpledialog
import json
import os
from datetime import datetime, timedelta
import csv
from main import PrevisorDemanda

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
previsor = PrevisorDemanda(script_dir)

def inicializar_json_com_previsoes_reais():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dados_path = os.path.join(script_dir, 'dados_vendas.csv')

    previsor = PrevisorDemanda(script_dir)
    previsor.carregar_dados_vendas(dados_path)
    previsor.preparar_features()
    previsor.treinar_modelo()

    data_base = datetime.now()
    novo_json = {}
    for filial in KNOWN_FILIAIS:
        if filial not in novo_json:
            novo_json[filial] = {}
        for sku in SKU_DEFINITIONS.keys():
            try:
                previsao = previsor.prever_demanda(data_base, sku)
                novo_json[filial][str(sku)] = {
                    "previsao": previsao,
                    "data_previsao": data_base.strftime("%Y-%m-%d %H:%M:%S")
                }
            except Exception as e:
                print(f"Erro ao prever demanda para SKU {sku}: {e}")
                novo_json[filial][str(sku)] = {
                    "previsao": 100.0,
                    "data_previsao": data_base.strftime("%Y-%m-%d %H:%M:%S")
                }

    with open(SKU_QUANTITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(novo_json, f, indent=4, ensure_ascii=False)
    print("Previsões salvas com sucesso em formato por filial e SKU.")

def inicializar_previsor():
    vendas_path = os.path.join(script_dir, "dados_vendas.csv")  # ajuste o nome se necessário
    if not os.path.exists(vendas_path):
        messagebox.showerror("Erro", f"Arquivo de vendas não encontrado: {vendas_path}")
        return
    previsor.carregar_dados_vendas(vendas_path)
    previsor.preparar_features()
    previsor.treinar_modelo()
    inicializar_json_com_previsoes_reais()
    
def atualizar_previsao_e_json(sku, data_base=None):
    if data_base is None:
        data_base = datetime.now()
    previsao = previsor.prever_demanda(data_base, sku)
    timestamp = data_base.strftime("%Y-%m-%d %H:%M:%S")
    if os.path.exists(SKU_QUANTITIES_FILE):
        with open(SKU_QUANTITIES_FILE, "r", encoding="utf-8") as f:
            sku_quantities = json.load(f)
    else:
        sku_quantities = {}

    filial = logged_in_user_filial or "7"  # Use a filial do usuário logado ou padrão

    if filial not in sku_quantities:
        sku_quantities[filial] = {}
    sku_quantities[filial][sku] = {
        "previsao": previsao,
        "data_previsao": timestamp
    }

    with open(SKU_QUANTITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(sku_quantities, f, ensure_ascii=False, indent=2)
    return previsao

def sugerir_quantidade_para_sku(sku):
    previsao = atualizar_previsao_e_json(sku)
    messagebox.showinfo("Previsão de Demanda", f"Previsão para SKU {sku} em D+2: {previsao} kg")
    return previsao

# --- Constantes de Lógica de Negócio ---
BALCAO_CAPACITY = 20.0 # Capacidade recomendada do balcão em kg
ALERT_THRESHOLD = 10.0 # Limite em kg para gerar alerta de reabastecimento

# --- Variáveis Globais de Dados ---
users = {}
generated_processes = []
# Agora, filial_process_counters será aninhado: filial_process_counters[filial][sku]
filial_process_counters = {}
current_day = 0
current_hour = 0
end_of_day_cleanup_done_for_day = -1
logged_in_user_filial = 7

# #############################################################################
# ############# INÍCIO DA SEÇÃO DE CÓDIGO ADICIONADO ##########################
# #############################################################################
# Define a data de início da simulação como o dia atual, à meia-noite.
simulation_start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
# ###########################################################################
# ############## FIM DA SEÇÃO DE CÓDIGO ADICIONADO ##########################
# ###########################################################################

# ... (o restante do seu código permanece o mesmo) ...

# Dicionário para armazenar as quantidades padrão por SKU e Filial
sku_default_quantities = {}

# Dicionário para armazenar os processos que tiveram o Dia 2 concluído, por filial
completed_day2_processes_by_filial = {}

# --- Definição de SKUs com suas lógicas e rótulos de coluna ---
SKU_DEFINITIONS = {
    "237478": { # FILE DE PEITO FGO INTERF CONG KG
        "days_cycle": 3,
        "display_column_label": "FILE DE PEITO FGO",
        "steps_descriptions": {
            0: "237478 Peito de Frango: Retirado do congelador para estante de descongelamento inicial.",
            1: "237478 Peito de Frango: Movido para estante intermediária de descongelamento.",
            2: "237478 Peito de Frango: Pronto para embalagem/exposição."
        }
    },
    "237479": { # ASA DE FGO INTERF CONG KG
        "days_cycle": 3,
        "display_column_label": "ASA DE FGO",
        "steps_descriptions": {
            0: "237479 Asa de Frango: Retirada do congelador para estante 1 do armazém.",
            1: "237479 Asa de Frango: Movida para estante de descongelamento esquerda para a central.",
            2: "237479 Asa de Frango: Movida para estante central para a direita (pronta para exposição)."
        }
    },
    "237496": { # CORACAO DE FGO INTERF CONG KG
        "days_cycle": 3,
        "display_column_label": "CORACAO DE FGO",
        "steps_descriptions": {
            0: "237496 Coração de Frango: Retirado do congelador para estante de descongelamento inicial.",
            1: "237496 Coração de Frango: Movido para estante intermediária de descongelamento.",
            2: "237496 Coração de Frango: Pronto para embalagem/exposição."
        }
    },
    "237497": { # COXA C/SOB FGO INTERF CONG KG
        "days_cycle": 3,
        "display_column_label": "COXA C/SOB FGO",
        "steps_descriptions": {
            0: "237497 Coxa c/ Sobrecoxa: Retirada do congelador e movida para área inicial de descongelamento.",
            1: "237497 Coxa c/ Sobrecoxa: Movida para área intermediária de descongelamento.",
            2: "237497 Coxa c/ Sobrecoxa: Movida para área final, pronto para exposição."
        }
    },
    "237506": { # COXA DE FGO INTERF CONG KG
        "days_cycle": 3,
        "display_column_label": "COXA DE FGO",
        "steps_descriptions": {
            0: "237506 Coxa de Frango: Retirada do congelador e movida para área inicial de descongelamento.",
            1: "237506 Coxa de Frango: Movida para área intermediária de descongelamento.",
            2: "237506 Coxa de Frango: Movido para área final, pronto para exposição."
        }
    },
    "237508": { # COXINHA DA ASA FGO INTERF CONG KG
        "days_cycle": 3,
        "display_column_label": "COXINHA DA ASA FGO",
        "steps_descriptions": {
            0: "237508 Coxinha da Asa: Retirada do congelador para estante de descongelamento inicial.",
            1: "237508 Coxinha da Asa: Movida para estante intermediária de descongelamento.",
            2: "237508 Coxinha da Asa: Pronto para embalagem/exposição."
        }
    },
    "237511": { # MOELA DE FRANGO INTERF CONG KG
        "days_cycle": 3,
        "display_column_label": "MOELA DE FRANGO",
        "steps_descriptions": {
            0: "237511 Moela de Frango: Retirada do congelador para estante de descongelamento inicial.",
            1: "237511 Moela de Frango: Movido para estante intermediária de descongelamento.",
            2: "237511 Moela de Frango: Pronto para embalagem/exposição."
        }
    },
    "384706": { # PE FRANGO INTERF CONG KG
        "days_cycle": 3,
        "display_column_label": "PE FRANGO",
        "steps_descriptions": {
            0: "384706 Pé de Frango: Retirado do congelador para estante de descongelamento inicial.",
            1: "384706 Pé de Frango: Movido para estante intermediária de descongelamento.",
            2: "384706 Pé de Frango: Pronto para embalagem/exposição."
        }
    }
}
KNOWN_FILIAIS = ["7", "8", "9", "10"]

# --- Variáveis Globais de Referência de Janelas ---
login_screen_ref = None
manager_window = None
register_window = None
fueling_log_window = None
consumption_chart_window = None
abastecedor_window_instance = None
comprador_window = None
controller_window = None
sku_quantity_config_window = None

open_movimentador_windows = []
open_abastecedor_windows = []

# --- Funções de Manipulação de Dados (JSON) ---

def log_event(evento, filial, sku, process_id, dia_processo, quantidade_kg, usuario, info_adicional=""):
    """
    Registra um evento em um arquivo CSV.

    Args:
        evento (str): Descrição do evento (ex: "PROCESSO CRIADO", "MOVIMENTAÇÃO INICIADA").
        filial (str): A filial onde o evento ocorreu.
        sku (str): O código do SKU.
        process_id (str): O identificador único do processo.
        dia_processo (int/str): O dia do ciclo do processo (0, 1, 2) ou 'N/A'.
        quantidade_kg (float): A quantidade em KG associada ao processo.
        usuario (str): O usuário que realizou a ação (ou "SISTEMA").
        info_adicional (str, optional): Qualquer informação extra.
    """
    try:
        # Define o cabeçalho do arquivo CSV
        header = [
            "Timestamp", "Evento", "Filial", "SKU", "Descricao_SKU",
            "ID_Processo", "Dia_Processo", "Quantidade_Kg_Processo", "Usuario", "Info_Adicional"
        ]

        # Verifica se o arquivo existe para não escrever o cabeçalho novamente
        file_exists = os.path.isfile(LOG_FILE)

        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Se o arquivo não existe, escreve o cabeçalho
            if not file_exists:
                writer.writerow(header)

            # Prepara a linha de dados para ser escrita
            timestamp = get_current_simulated_datetime().strftime("%Y-%m-%d %H:%M:%S")
            sku_description = SKU_DEFINITIONS.get(sku, {}).get("display_column_label", "N/A")

            data_row = [
                timestamp, evento, filial, sku, sku_description,
                process_id, dia_processo, f"{quantidade_kg:.2f}", usuario, info_adicional
            ]
            writer.writerow(data_row)

    except Exception as e:
        print(f"ERRO AO ESCREVER NO LOG: {e}")

# #############################################################################
# ############# INÍCIO DA SEÇÃO DE CÓDIGO ADICIONADO ##########################
# #############################################################################
def get_current_simulated_datetime():
    """
    Calcula o datetime simulado atual com base na data de início da simulação,
    o dia atual e a hora atual da simulação.
    """
    global simulation_start_date, current_day, current_hour
    return simulation_start_date + timedelta(days=current_day, hours=current_hour)

# ###########################################################################
# ############## INÍCIO DA FUNÇÃO CORRIGIDA #################################
# ###########################################################################
def gerar_relatorio_abastecimento(process_id):
    """
    Gera um relatório CSV com abastecimentos e compras detalhados, atualizando estoque e balcão em tempo real.
    """
    process = next((p for p in generated_processes if p['sku_process_number'] == process_id), None)
    if not process:
        print(f"Processo {process_id} não encontrado.")
        return

    try:
        report_dir = os.path.join(script_dir, "relatorios_abastecimento")
        os.makedirs(report_dir, exist_ok=True)

        timestamp_geracao = get_current_simulated_datetime().strftime("%Y%m%d")
        filename = os.path.join(report_dir, f"relatorio_abastecimento_{process_id}_{timestamp_geracao}.csv")

        headers = [
            "ID_Processo", "Filial", "SKU", "Descricao_SKU",
            "Timestamp", "Usuario", "Quantidade_Abastecida_Kg", "Quantidade_Comprada_Kg",
            "Estoque_Atual_Kg", "Valor_no_Balcao_Kg", "Sobras_Totais_Kg"
        ]

        filial = process.get("filial")
        sku = process.get("sku")
        descricao = SKU_DEFINITIONS.get(sku, {}).get("display_column_label", "N/A")
        quantidade_inicial = process.get("quantidade_inicial_kg", 0.0)

        # Inicializa valores
        estoque = quantidade_inicial
        balcao = 0.0

        # Carrega abastecimentos
        eventos = []
        for log in process.get("replenishment_log", []):
            eventos.append({
                "timestamp": log["timestamp"],
                "usuario": log["usuario"],
                "tipo": "ABASTECIMENTO",
                "qtd_abastecida": log["quantidade_abastecida"],
                "qtd_comprada": 0.0
            })

        # Carrega compras do log geral
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["Evento"] == "COMPRA" and row["ID_Processo"] == process_id:
                        eventos.append({
                            "timestamp": datetime.strptime(row["Timestamp"], "%Y-%m-%d %H:%M:%S"),
                            "usuario": row["Usuario"],
                            "tipo": "COMPRA",
                            "qtd_abastecida": 0.0,
                            "qtd_comprada": float(row["Quantidade_Kg_Processo"])
                        })

        # Ordena todos os eventos
        eventos.sort(key=lambda e: e["timestamp"])

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            # Linha inicial
            writer.writerow([
                process_id, filial, sku, descricao,
                "INICIAL", "SISTEMA", "0.00", "0.00",
                f"{estoque:.2f}", f"{balcao:.2f}", f"{estoque + balcao:.2f}"
            ])

            # Linha por evento
            for evento in eventos:
                if evento["tipo"] == "ABASTECIMENTO":
                    estoque -= evento["qtd_abastecida"]
                    balcao += evento["qtd_abastecida"]
                elif evento["tipo"] == "COMPRA":
                    balcao -= evento["qtd_comprada"]

                writer.writerow([
                    process_id, filial, sku, descricao,
                    evento["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                    evento["usuario"],
                    f"{evento['qtd_abastecida']:.2f}",
                    f"{evento['qtd_comprada']:.2f}",
                    f"{estoque:.2f}", f"{balcao:.2f}", f"{estoque + balcao:.2f}"
                ])

        print(f"✅ Relatório gerado com sucesso: {filename}")

    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")


def gerar_relatorio_consolidado_filial7():
    """
    Gera um relatório CSV consolidado para todos os processos da filial 7.
    CORREÇÃO FINAL: Lê a "quantidade_inicial_kg" que foi salva em cada
    processo no momento de sua criação, garantindo a precisão histórica.
    """
    print("Gerando relatório consolidado para a Filial 7...")
    try:
        timestamp = get_current_simulated_datetime().strftime("%Y%m%d%H%M%S")
        filename = os.path.join(script_dir, f"relatorio_movimentacoes_consolidado_filial7_{timestamp}.csv")

        headers = [
            "ID_Processo", "Filial", "SKU", "Descricao_SKU", "Quantidade_Inicial_Kg"
        ]

        for i in range(3):
            headers.extend([
                f"Idade_Dia_{i}",
                f"Peso_Dia_{i}",
                f"Inicio_Movimentacao_Dia_{i}",
                f"Confirmacao_Movimentacao_Dia_{i}",
                f"Responsavel_Dia_{i}"
            ])

        report_data = []
        for process in generated_processes:
            if process.get("filial") != "7":
                continue

            # --- CORREÇÃO PRINCIPAL ---
            # Lê o valor do campo 'quantidade_inicial_kg' salvo no próprio processo.
            # Este valor é o registro histórico da criação do processo.
            quantidade_historica = process.get('quantidade_inicial_kg', 0.0)

            row_data = {
                "ID_Processo": process.get("sku_process_number"),
                "Filial": process.get("filial"),
                "SKU": process.get("sku"),
                "Descricao_SKU": SKU_DEFINITIONS.get(process.get("sku"), {}).get("display_column_label", "N/A"),
                # Usa a quantidade histórica para o relatório.
                "Quantidade_Inicial_Kg": f"{quantidade_historica:.2f}",
            }

            # --- CORREÇÃO NO CÁLCULO ---
            # Os cálculos de peso para os dias seguintes agora são baseados
            # na quantidade_historica, garantindo a consistência do relatório.
            for day_offset in range(process.get("days_cycle", 3)):
                absolute_step_day = process["dia_geracao"] + day_offset
                step_info = process["steps_status"].get(str(absolute_step_day), {})

                # Calcula o peso para cada dia baseado no valor HISTÓRICO
                peso_dia = 0.0
                if day_offset == 0:
                    peso_dia = quantidade_historica
                elif day_offset == 1:
                    # Aplica a perda de peso sobre a quantidade histórica
                    peso_dia = quantidade_historica * (1 - 0.0725)
                elif day_offset == 2:
                    # Aplica a perda de peso sobre a quantidade histórica
                    peso_dia = quantidade_historica * (1 - 0.15)

                # Formata os dados
                start_ts = step_info.get('inicio_movimentacao_ts')
                confirm_ts = step_info.get('confirmacao_movimentacao_ts')

                row_data[f"Idade_Dia_{day_offset}"] = day_offset
                row_data[f"Peso_Dia_{day_offset}"] = f"{peso_dia:.2f}"
                row_data[f"Inicio_Movimentacao_Dia_{day_offset}"] = start_ts.strftime("%Y-%m-%d %H:%M:%S") if start_ts else ""
                row_data[f"Confirmacao_Movimentacao_Dia_{day_offset}"] = confirm_ts.strftime("%Y-%m-%d %H:%M:%S") if confirm_ts else ""
                row_data[f"Responsavel_Dia_{day_offset}"] = step_info.get("responsavel_movimentacao", "")

            report_data.append(row_data)

        # Escreve o arquivo CSV
        if not report_data:
            print("Nenhum dado da Filial 7 para gerar relatório.")
            return

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(report_data)

        print(f"Relatório consolidado '{filename}' gerado com sucesso!")
        messagebox.showinfo("Relatório Gerado", f"O relatório consolidado para a Filial 7 foi salvo como:\n\n{filename}")

    except Exception as e:
        print(f"ERRO AO GERAR RELATÓRIO CONSOLIDADO: {e}")
        messagebox.showerror("Erro de Relatório", f"Ocorreu um erro ao gerar o relatório:\n{e}")

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            loaded_users = json.load(f)
            for user_data in loaded_users.values():
                if 'filial' not in user_data:
                    user_data['filial'] = "7"
            return loaded_users
    return {
        "admin": {"password": "admin", "type": "gerente", "filial": "7"},
        "mov1": {"password": "123", "type": "movimentador_de_produto", "filial": "7"},
    }

def save_users(users_data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, indent=4)

def load_sku_quantities():
    global logged_in_user_filial
    if os.path.exists(SKU_QUANTITIES_FILE):
        with open(SKU_QUANTITIES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Detecta formato antigo (apenas SKUs, sem filial)
            if all(isinstance(v, (int, float)) for v in data.values()):
                new_data = {}
                for filial in KNOWN_FILIAIS:
                    new_data[filial] = {sku: qty for sku, qty in data.items()}
                with open(SKU_QUANTITIES_FILE, 'w', encoding='utf-8') as fw:
                    json.dump(new_data, fw, ensure_ascii=False, indent=2)
                return new_data.get(logged_in_user_filial, {})
            else:
                return data.get(logged_in_user_filial, {})
    # Se não existe, inicializa com previsão e recarrega
    inicializar_json_com_previsoes_reais()
    with open(SKU_QUANTITIES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get(logged_in_user_filial, {})


def save_sku_quantities(quantities_data):
    with open(SKU_QUANTITIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(quantities_data, f, indent=4)

users = load_users()
sku_default_quantities = load_sku_quantities()

def initialize_filial_counters():
    global filial_process_counters, completed_day2_processes_by_filial
    for filial in KNOWN_FILIAIS:
        filial_process_counters[filial] = {}
        completed_day2_processes_by_filial[filial] = []
    for filial in KNOWN_FILIAIS:
        for sku_key in SKU_DEFINITIONS.keys():
            filial_process_counters[filial][sku_key] = 0

initialize_filial_counters()

# --- Funções Auxiliares para Gerenciamento de Janelas ---
def show_placeholder_message(feature_name):
    messagebox.showinfo("Funcionalidade em Desenvolvimento", f"A funcionalidade '{feature_name}' ainda será implementada.")

def create_toplevel_window(parent_screen, title, geometry, window_ref_var_name, on_close_callback=None, allow_multiple=False, window_list_ref=None):
    current_window_ref = globals().get(window_ref_var_name)

    if not allow_multiple and (current_window_ref is not None and current_window_ref.winfo_exists()):
        current_window_ref.lift()
        return None
    else:
        new_window = tk.Toplevel(parent_screen)
        new_window.title(title)
        new_window.geometry(geometry)
        new_window.transient(parent_screen)
        if on_close_callback:
            new_window.protocol("WM_DELETE_WINDOW", lambda: on_toplevel_close(new_window, window_ref_var_name, allow_multiple, window_list_ref))

        if allow_multiple and window_list_ref is not None:
            window_list_ref.append(new_window)
        else:
            globals()[window_ref_var_name] = new_window

        return new_window

def on_toplevel_close(window, window_ref_var_name, allow_multiple=False, window_list_ref=None):
    if allow_multiple and window_list_ref is not None and window in window_list_ref:
        window_list_ref.remove(window)
    elif not allow_multiple:
        globals()[window_ref_var_name] = None
    window.destroy()

# --- Funções de Processamento de Lógica de Negócio ---

# ###########################################################################
# ############## INÍCIO DA SEÇÃO DE CÓDIGO MODIFICADO #######################
# ###########################################################################
def generate_new_process(sku, quantidade_kg, filial_processo):
    global filial_process_counters

    if sku not in SKU_DEFINITIONS:
        print(f"Erro: SKU '{sku}' não encontrado nas definições. Pulando a geração do processo.")
        return

    if filial_processo not in filial_process_counters:
        filial_process_counters[filial_processo] = {}
    if sku not in filial_process_counters[filial_processo]:
        filial_process_counters[filial_processo][sku] = 0

    filial_process_counters[filial_processo][sku] += 1

    sku_process_number = f"{sku}-{filial_process_counters[filial_processo][sku]}-{filial_processo}"

    sku_config = SKU_DEFINITIONS[sku]

    steps_status = {}
    for day_offset in range(sku_config["days_cycle"]):
        absolute_step_day = current_day + day_offset
        steps_status[str(absolute_step_day)] = {
            "status": "Desabilitado",
            "movimentacao_started": False,
            "data_movimentacao": None
        }

    new_process = {
        "numero": f"{filial_process_counters[filial_processo][sku]}-{filial_processo}",
        "sku_process_number": sku_process_number,
        "dia_geracao": current_day,
        "hora_criacao": current_hour,
        "sku": sku,
        "quantidade_inicial_kg": quantidade_kg,
        "quantidade_kg": quantidade_kg,
        "peso_no_balcao": 0.0,
        "filial": filial_processo,
        "days_cycle": sku_config["days_cycle"],
        "steps_descriptions": sku_config["steps_descriptions"],
        "steps_status": steps_status,
        "replenishment_log": []
    }
    generated_processes.append(new_process)
    print(f"Processo {sku_process_number} (Dia {current_day} - Hora {current_hour:02d}:00, SKU {sku}, Qty {quantidade_kg} kg) gerado com sucesso! Todos os passos iniciais: Desabilitado")

    log_event(
        evento="PROCESSO CRIADO",
        filial=filial_processo,
        sku=sku,
        process_id=sku_process_number,
        dia_processo="N/A",
        quantidade_kg=quantidade_kg,
        usuario="SISTEMA"
    )
# ###########################################################################
# ############## FIM DA SEÇÃO DE CÓDIGO MODIFICADO ##########################
# ###########################################################################

def perform_daily_process_generation():
    global sku_default_quantities
    print(f"\n--- Gerando processos para o Dia {current_day} (00:00) ---")

    for filial in KNOWN_FILIAIS:
        for sku in SKU_DEFINITIONS.keys():
            data_base = get_current_simulated_datetime()
            quantidade = previsor.prever_demanda(data_base, sku)
            generate_new_process(sku, quantidade, filial)

    print(f"--- Geração de processos diária concluída para o Dia {current_day} ---")

def update_process_states_on_time_change():
    print(f"\n--- Verificando e atualizando estados dos processos (Dia {current_day} Hora {current_hour:02d}:00) ---")
    for process in generated_processes:
        total_days_cycle = process.get("days_cycle", 3)

        for day_offset in range(total_days_cycle):
            absolute_step_day = process["dia_geracao"] + day_offset

            previous_step_status_completed = False
            if day_offset == 0:
                previous_step_status_completed = True
            else:
                previous_absolute_step_day = process["dia_geracao"] + (day_offset - 1)
                prev_step_info = process["steps_status"].get(str(previous_absolute_step_day))
                if prev_step_info and prev_step_info["status"] == "Feito":
                    previous_step_status_completed = True

            current_step_info = process["steps_status"].get(str(absolute_step_day))

            if not current_step_info:
                process["steps_status"][str(absolute_step_day)] = {
                    "status": "Desabilitado", "movimentacao_started": False, "data_movimentacao": None
                }
                current_step_info = process["steps_status"][str(absolute_step_day)]

            activation_condition_met = False
            if previous_step_status_completed:
                if current_day > absolute_step_day:
                    activation_condition_met = True
                elif current_day == absolute_step_day:
                    if current_hour >= 6:
                        activation_condition_met = True

            if activation_condition_met:
                if current_step_info["status"] == "Desabilitado":
                    current_step_info["status"] = "Aguardando"
                    current_step_info["movimentacao_started"] = False
                    print(f"Processo {process['sku_process_number']} - Etapa Dia {day_offset} (Absoluto {absolute_step_day}) ATIVADA para AGUARDANDO no Dia {current_day} Hora {current_hour:02d}:00.")
            else:
                if current_step_info["status"] == "Aguardando":
                    current_step_info["status"] = "Desabilitado"
                    current_step_info["movimentacao_started"] = False
                    print(f"Processo {process['sku_process_number']} - Etapa Dia {day_offset} (Absoluto {absolute_step_day}) voltou para DESABILITADO no Dia {current_day} Hora {current_hour:02d}:00.")
    print("--- Verificação e atualização de estados concluída ---")

# ###########################################################################
# ############## INÍCIO DA SEÇÃO DE CÓDIGO MODIFICADO #######################
# ###########################################################################
def handle_end_of_day_cleanup():
    """Rotina de fim de expediente (18:00) para registrar sobras, gerar relatórios e limpar a tela."""
    global end_of_day_cleanup_done_for_day, completed_day2_processes_by_filial

    print(f"--- Iniciando Rotina de Fim de Expediente (Dia {current_day}) ---")

    processes_to_remove_by_filial = {}
    any_leftovers = False

    for filial, process_ids in list(completed_day2_processes_by_filial.items()):
        processes_to_remove_by_filial[filial] = []

        for process_id in process_ids:
            process_data = next((p for p in generated_processes if p['sku_process_number'] == process_id), None)

            if process_data:
                sobra_estante = process_data['quantidade_kg']
                sobra_balcao = process_data.get('peso_no_balcao', 0.0)
                total_sobra = sobra_estante + sobra_balcao

                if total_sobra > 0:
                    any_leftovers = True
                    sku_label = SKU_DEFINITIONS[process_data['sku']]['display_column_label']
                    message = (
                        f"Filial {filial} - Recolher Sobras:\n\n"
                        f"Produto: {sku_label} (Processo: {process_id})\n"
                        f"---------------------------------------------------\n"
                        f"Sobra na Estante: {sobra_estante:.2f} kg\n"
                        f"Sobra no Balcão: {sobra_balcao:.2f} kg\n"
                        f"---------------------------------------------------\n"
                        f"TOTAL A RECOLHER: {total_sobra:.2f} kg\n\n"
                        "Pedido enviado ao setor de alimentos para preparo."
                    )
                    messagebox.showinfo("Fim de Expediente - Registro de Sobras", message)
                    print(f"Filial {filial}: Registrado sobra de {total_sobra:.2f} kg para o processo {process_id}.")

                # --- ADICIONADO: Gatilho para gerar o relatório de abastecimento ---
                gerar_relatorio_abastecimento(process_id)

                processes_to_remove_by_filial[filial].append(process_id)

    for filial, ids_to_remove in processes_to_remove_by_filial.items():
        if filial in completed_day2_processes_by_filial:
            current_list = completed_day2_processes_by_filial[filial]
            completed_day2_processes_by_filial[filial] = [pid for pid in current_list if pid not in ids_to_remove]
            print(f"Filial {filial}: Removidos {len(ids_to_remove)} processos da tela de abastecimento.")

    if not any_leftovers:
        messagebox.showinfo("Fim de Expediente", "Rotina de fim de dia executada. Não houve sobras para registrar.")

    end_of_day_cleanup_done_for_day = current_day

    for win in open_abastecedor_windows:
        update_abastecedor_completed_processes_display(win)

    print("--- Rotina de Fim de Expediente Concluída ---")
# ###########################################################################
# ############## FIM DA SEÇÃO DE CÓDIGO MODIFICADO ##########################
# ###########################################################################

def check_for_time_based_events():
    """Verifica se algum evento baseado em tempo deve ser acionado."""
    global end_of_day_cleanup_done_for_day

    # Se o dia mudou, reseta a flag de limpeza
    if current_day > end_of_day_cleanup_done_for_day:
        end_of_day_cleanup_done_for_day = -1

    # Aciona a limpeza de fim de dia às 18:00 ou depois, mas apenas uma vez por dia
    if current_hour >= 18 and end_of_day_cleanup_done_for_day != current_day:
        print(f"Acionando rotina de fim de expediente para o Dia {current_day}.")
        handle_end_of_day_cleanup()


def advance_x_hours():
    global current_hour, current_day
    try:
        hours_to_advance = int(controller_window.hour_jump_entry.get().strip())
        if hours_to_advance <= 0:
            messagebox.showwarning("Avançar Horas", "Por favor, insira um número positivo de horas.")
            return
    except ValueError:
        messagebox.showerror("Avançar Horas", "Por favor, insira um número inteiro válido de horas.")
        return

    for _ in range(hours_to_advance):
        current_hour += 1
        if current_hour >= 24:
            current_hour = 0
            current_day += 1
            perform_daily_process_generation()
        # Chama a verificação de eventos a cada hora avançada
        check_for_time_based_events()

    if controller_window and controller_window.winfo_exists():
        controller_window.day_label.config(text=f"Dia Atual: {current_day}")
        controller_window.hour_label.config(text=f"Hora Atual: {current_hour:02d}:00")

    messagebox.showinfo("Avanço de Tempo", f"A hora foi avançada para {current_hour:02d}:00 do Dia {current_day}.")

    update_process_states_on_time_change()
    for win in open_movimentador_windows:
        update_movimentador_processes(win)
    for win in open_abastecedor_windows:
        update_abastecedor_completed_processes_display(win)

    update_controller_weight_panel()


def advance_day_complete():
    global current_day, current_hour

    # Roda a limpeza do dia atual antes de avançar para o próximo
    check_for_time_based_events()

    current_day += 1
    current_hour = 0
    perform_daily_process_generation()

    if controller_window and controller_window.winfo_exists():
        controller_window.day_label.config(text=f"Dia Atual: {current_day}")
        controller_window.hour_label.config(text=f"Hora Atual: {current_hour:02d}:00")
    messagebox.showinfo("Avanço de Dia", f"O dia foi avançado para o Dia {current_day} (00:00).")

    update_process_states_on_time_change()
    for win in open_movimentador_windows:
        update_movimentador_processes(win)
    for win in open_abastecedor_windows:
        update_abastecedor_completed_processes_display(win)

    update_controller_weight_panel()
# --- Lógica de Login ---
# ###########################################################################
# ############## INÍCIO DA SEÇÃO DE CÓDIGO MODIFICADO #######################
# ###########################################################################
def login():
    global logged_in_user_filial
    username = entry_username.get()
    password = entry_password.get()

    if username in users and users[username]["password"] == password:
        user_data = users[username]
        user_type = user_data["type"]
        logged_in_user_filial = user_data.get("filial", "Não Definida")
        

        messagebox.showinfo("Login Bem-Sucedido", f"Bem-vindo(a), {username}! Você é um {user_type} da Filial {logged_in_user_filial}.")
        entry_password.delete(0, tk.END)
        entry_username.delete(0, tk.END)
        entry_username.focus_set()

        if user_type == "gerente":
            open_manager_interface(login_screen_ref)
        elif user_type == "abastecedor":
            # MODIFICADO: Passa o nome de usuário para a interface do abastecedor
            open_abastecedor_interface(login_screen_ref, username)
        elif user_type == "movimentador_de_produto":
            open_movimentador_interface(login_screen_ref, username)
        elif user_type == "comprador_da_distribuidora":
            open_comprador_interface(login_screen_ref)
        else:
            messagebox.showwarning("Tipo de Usuário Desconhecido", f"O tipo de usuário '{user_type}' não possui uma interface definida.")
    else:
        messagebox.showerror("Erro de Login", "Nome de usuário ou senha inválidos.")
# ###########################################################################
# ############## FIM DA SEÇÃO DE CÓDIGO MODIFICADO ##########################
# ###########################################################################

# --- Interfaces Específicas dos Usuários ---
def open_manager_interface(parent_screen):
    window = create_toplevel_window(parent_screen, f"Interface do Gerente - Filial {logged_in_user_filial}", "800x600", "manager_window", on_toplevel_close)
    if window:
        label_title = tk.Label(window, text=f"Bem-vindo(a) à Interface do Gerente (Filial {logged_in_user_filial})", font=("Arial", 20, "bold"))
        label_title.pack(pady=20)

        btn_register_user = tk.Button(window, text="Cadastrar Novo Usuário", command=lambda: open_register_user_interface(window), font=("Arial", 14))
        btn_register_user.pack(pady=10)

        btn_fueling_log = tk.Button(window, text="Log de Abastecimento (Filial)", command=lambda: show_placeholder_message(f"Log de Abastecimento da Filial {logged_in_user_filial}"), font=("Arial", 14))
        btn_fueling_log.pack(pady=10)

        btn_consumption_chart = tk.Button(window, text="Gráfico de Consumo (Filial)", command=lambda: show_placeholder_message(f"Gráfico de Consumo da Filial {logged_in_user_filial}"), font=("Arial", 14))
        btn_consumption_chart.pack(pady=10)

def open_register_user_interface(parent_screen):
    window = create_toplevel_window(parent_screen, "Cadastro de Usuário", "700x700", "register_window", on_toplevel_close)
    if window:
        label_title = tk.Label(window, text="Formulário de Cadastro de Usuário", font=("Arial", 18, "bold"))
        label_title.pack(pady=20)

        form_frame = tk.Frame(window)
        form_frame.pack(pady=10, padx=20, fill="both", expand=True)

        labels = ["Nome Completo:", "CPF:", "Endereço:", "Telefone:", "Email:", "Nome de Usuário:", "Senha:"]
        entries = {}

        key_mapping = {
            "Nome Completo": "nome_completo", "CPF": "cpf", "Endereço": "endereco",
            "Telefone": "telefone", "Email": "email", "Nome de Usuário": "nome_de_usuario",
            "Senha": "senha"
        }

        for i, text in enumerate(labels):
            label = tk.Label(form_frame, text=text, font=("Arial", 12))
            label.grid(row=i, column=0, sticky="w", pady=5, padx=5)
            entry = tk.Entry(form_frame, font=("Arial", 12), width=40)
            entry.grid(row=i, column=1, sticky="ew", pady=5, padx=5)
            entries[key_mapping[text.replace(":", "").strip()]] = entry

        label_user_type = tk.Label(form_frame, text="Tipo de Usuário:", font=("Arial", 12))
        label_user_type.grid(row=len(labels), column=0, sticky="w", pady=5, padx=5)

        user_types = ["abastecedor", "movimentador_de_produto", "comprador_da_distribuidora", "gerente"]
        selected_user_type = ttk.Combobox(form_frame, values=user_types, state="readonly", font=("Arial", 12), width=38)
        selected_user_type.set(user_types[0])
        selected_user_type.grid(row=len(labels), column=1, sticky="ew", pady=5, padx=5)

        label_filial = tk.Label(form_frame, text="Filial:", font=("Arial", 12))
        label_filial.grid(row=len(labels)+1, column=0, sticky="w", pady=5, padx=5)
        filiais_disponiveis = KNOWN_FILIAIS
        selected_filial = ttk.Combobox(form_frame, values=filiais_disponiveis, state="readonly", font=("Arial", 12), width=38)
        selected_filial.set("7")
        selected_filial.grid(row=len(labels)+1, column=1, sticky="ew", pady=5, padx=5)

        def register_new_user():
            global users
            new_user_data = {key: entry.get() for key, entry in entries.items()}
            new_user_data["user_type"] = selected_user_type.get()
            new_user_data["filial"] = selected_filial.get()

            for key, value in new_user_data.items():
                if not value and key not in ["endereco", "telefone", "email"]:
                    messagebox.showerror("Erro de Cadastro", f"O campo '{key.replace('_', ' ').title()}' não pode estar vazio.")
                    return
            if not new_user_data["filial"]:
                 messagebox.showerror("Erro de Cadastro", "A filial não pode estar vazia.")
                 return

            if new_user_data["nome_de_usuario"] in users:
                messagebox.showerror("Erro de Cadastro", "Nome de usuário já existe. Escolha outro.")
                return

            users[new_user_data["nome_de_usuario"]] = {
                "password": new_user_data["senha"],
                "type": new_user_data["user_type"],
                "nome_completo": new_user_data["nome_completo"],
                "cpf": new_user_data["cpf"],
                "endereco": new_user_data["endereco"],
                "telefone": new_user_data["telefone"],
                "email": new_user_data["email"],
                "filial": new_user_data["filial"]
            }
            save_users(users)
            messagebox.showinfo("Cadastro Bem-Sucedido", f"Usuário '{new_user_data['nome_de_usuario']}' do tipo '{new_user_data['user_type']}' da Filial '{new_user_data['filial']}' cadastrado com sucesso!")
            for entry_widget in entries.values():
                entry_widget.delete(0, tk.END)
            selected_user_type.set(user_types[0])
            selected_filial.set("7")

        btn_register = tk.Button(window, text="Cadastrar", command=register_new_user, font=("Arial", 14), bg="#28a745", fg="white")
        btn_register.pack(pady=20)

# ###########################################################################
# ############## INÍCIO DA SEÇÃO DE CÓDIGO MODIFICADO #######################
# ###########################################################################
def start_abastecimento_process(process_id, window_ref):
    """Gerencia o fluxo de reabastecimento do balcão para um processo."""
    process_data = next((p for p in generated_processes if p['sku_process_number'] == process_id), None)
    if not process_data:
        messagebox.showerror("Erro", f"Processo {process_id} não encontrado.")
        return

    # MODIFICADO: Recupera o usuário da janela que iniciou a ação
    current_user = window_ref.current_user

    estoque_atual = process_data['quantidade_kg']
    peso_no_balcao = process_data['peso_no_balcao']
    sku_info = SKU_DEFINITIONS.get(process_data['sku'], {})
    display_name = sku_info.get('display_column_label', 'SKU Desconhecido')

    if estoque_atual <= 0:
        messagebox.showinfo("Estoque Esgotado", f"O estoque da estante para o processo {process_id} ({display_name}) já está esgotado.")
        return

    quantidade_a_levar = BALCAO_CAPACITY - peso_no_balcao
    if quantidade_a_levar <= 0:
        messagebox.showinfo("Informação", "O balcão já está com a capacidade máxima ou acima dela. Não é necessário reabastecer agora.")
        return

    quantidade_sugerida = min(quantidade_a_levar, estoque_atual)

    messagebox.showinfo(
        "Instrução de Abastecimento",
        f"Abasteça o balcão com o produto '{display_name}'.\n\n"
        f"Quantidade recomendada: {quantidade_sugerida:.2f} kg\n"
        f"(Estoque disponível na estante: {estoque_atual:.2f} kg)"
    )

    quantidade_levada = simpledialog.askfloat(
        "Confirmar Abastecimento",
        f"Informe a quantidade exata (kg) de '{display_name}' que foi levada para o balcão:",
        parent=window_ref,
        minvalue=0.0
    )

    if quantidade_levada is None:
        return

    if quantidade_levada > estoque_atual:
        messagebox.showerror(
            "Erro de Validação",
            f"A quantidade informada ({quantidade_levada:.2f} kg) é maior que o estoque disponível na estante ({estoque_atual:.2f} kg).\n"
            "Ação cancelada."
        )
        return

    # Atualizar dados do processo
    process_data['quantidade_kg'] -= quantidade_levada
    process_data['peso_no_balcao'] += quantidade_levada

    # --- ADICIONADO: Registro do abastecimento no log do processo ---
    log_entry = {
        "usuario": current_user,
        "timestamp": get_current_simulated_datetime(),
        "quantidade_abastecida": quantidade_levada
    }
    process_data['replenishment_log'].append(log_entry)

    # --- ADICIONADO: Log geral do evento de abastecimento ---
    log_event(
        evento="ABASTECIMENTO",
        filial=process_data['filial'],
        sku=process_data['sku'],
        process_id=process_id,
        dia_processo="N/A", # Abastecimento não tem dia de ciclo
        quantidade_kg=quantidade_levada, # Loga a quantidade que foi movida
        usuario=current_user,
        info_adicional=f"Abastecimento do balcão. Saldo estante: {process_data['quantidade_kg']:.2f}kg, Saldo balcão: {process_data['peso_no_balcao']:.2f}kg"
    )

    messagebox.showinfo("Sucesso", f"Abastecimento de {quantidade_levada:.2f} kg registrado com sucesso!")

    if process_data['quantidade_kg'] <= 0:
        messagebox.showinfo("Estoque da Estante Esgotado", f"O estoque da estante do processo {process_id} foi totalmente utilizado. O card ficará azul até o fim do expediente.")
        print(f"Processo {process_id} teve seu estoque da estante esgotado, mas permanecerá visível.")

    update_abastecedor_completed_processes_display(window_ref)
    update_controller_weight_panel()
# ###########################################################################
# ############## FIM DA SEÇÃO DE CÓDIGO MODIFICADO ##########################
# ###########################################################################

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
        estoque_na_estante = process_data['quantidade_kg']
        peso_no_balcao = process_data.get('peso_no_balcao', 0.0)

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

        if estoque_na_estante <= 0:
            card_bg_color = "lightblue"
            status_label = tk.Label(card_frame, text="COMPLETO (Estoque Esgotado)", font=("Arial", 9, "bold"), fg="white", bg="blue")
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

# ###########################################################################
# ############## INÍCIO DA SEÇÃO DE CÓDIGO MODIFICADO #######################
# ###########################################################################
def open_abastecedor_interface(parent_screen, username): # MODIFICADO: Recebe username
    window = create_toplevel_window(parent_screen, f"Interface do Abastecedor - Filial {logged_in_user_filial}", "800x600", "abastecedor_window_instance", on_toplevel_close, allow_multiple=True, window_list_ref=open_abastecedor_windows)
    if window:
        window.current_logged_in_filial = logged_in_user_filial
        window.current_user = username # <--- ADICIONADO: Armazena o usuário na janela

        label_title = tk.Label(window, text=f"Bem-vindo(a) {username} à Interface do Abastecedor (Filial {logged_in_user_filial})", font=("Arial", 18, "bold"))
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
# ###########################################################################
# ############## FIM DA SEÇÃO DE CÓDIGO MODIFICADO ##########################
# ###########################################################################

def open_movimentador_interface(parent_screen, username):
    window = create_toplevel_window(parent_screen, f"Interface do Movimentador de Produto - Filial {logged_in_user_filial}", "1200x600", "movimentador_window_instance", on_toplevel_close, allow_multiple=True, window_list_ref=open_movimentador_windows)
    if window:
        window.current_logged_in_filial = logged_in_user_filial
        window.current_user = username

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

            step_info["inicio_movimentacao_ts"] = get_current_simulated_datetime()
            step_info["responsavel_movimentacao"] = user

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

            update_movimentador_processes(window_ref)
        else:
            step_info["status"] = "Feito"
            step_info["data_movimentacao"] = f"Dia {current_day} - Hora {current_hour:02d}:00"
            step_info["dia_conclusao"] = current_day

            step_info["confirmacao_movimentacao_ts"] = get_current_simulated_datetime()

            messagebox.showinfo("Movimentação Confirmada", f"Etapa do Dia {day_offset} do processo {process['numero']} marcada como FEITO.")

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

            total_days_cycle = process.get("days_cycle", 3)
            if day_offset == (total_days_cycle - 1):
                filial_do_processo = process["filial"]
                process_id_to_add = process["sku_process_number"]
                if process_id_to_add not in completed_day2_processes_by_filial[filial_do_processo]:
                    completed_day2_processes_by_filial[filial_do_processo].append(process_id_to_add)
                    print(f"Processo {process_id_to_add} (Filial {filial_do_processo}) concluído no Dia {day_offset}. Adicionado para exibição do abastecedor.")

                for win in open_abastecedor_windows:
                    update_abastecedor_completed_processes_display(win)

                update_controller_weight_panel()

            update_process_states_on_time_change()

            update_movimentador_processes(window_ref)
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

                    filial = window_ref.current_logged_in_filial
                    sku = process['sku']
                    quantidade = None
                    if filial in sku_default_quantities and sku in sku_default_quantities[filial]:
                        val = sku_default_quantities[filial][sku]
                        if isinstance(val, dict):
                            quantidade = val.get("previsao")
                        else:
                            quantidade = val
                    else:
                        quantidade = process.get('quantidade_kg', 0)
                    tk.Label(main_process_frame, text=f"SKU: {sku} - Qtde: {quantidade} kg", font=("Arial", 9)).pack(anchor="w")
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


def open_comprador_interface(parent_screen):
    window = create_toplevel_window(parent_screen, f"Interface do Comprador da Distribuidora - Filial {logged_in_user_filial}", "600x400", "comprador_window", on_toplevel_close)
    if window:
        label_title = tk.Label(window, text=f"Bem-vindo(a) à Interface do Comprador da Distribuidora (Filial {logged_in_user_filial})", font=("Arial", 18, "bold"))
        label_title.pack(pady=50)
        label_info = tk.Label(window, text="Aqui serão implementadas as funcionalidades de compra filtradas por filial.", font=("Arial", 12))
        label_info.pack(pady=10)

# --- Interface do Controlador ---
def register_purchase():
    """Registra uma 'compra', ou seja, uma retirada de produto do balcão."""
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
    for process in generated_processes:
        if process["sku_process_number"] == selected_process_id:
            current_weight = process.get("peso_no_balcao", 0.0)

            if amount_removed > current_weight:
                messagebox.showerror(
                    "Estoque Insuficiente",
                    f"Não é possível retirar {amount_removed:.2f} kg.\n"
                    f"O balcão possui apenas {current_weight:.2f} kg deste processo."
                )
                return

            process["peso_no_balcao"] -= amount_removed
            process_found = True
            break

    if process_found:
        messagebox.showinfo("Sucesso", f"Compra de {amount_removed:.2f} kg registrada para o processo {selected_process_id}.")
        controller_window.purchase_entry.delete(0, tk.END)
        for win in open_abastecedor_windows:
            update_abastecedor_completed_processes_display(win)
    else:
        messagebox.showerror("Erro", f"Não foi possível encontrar o processo {selected_process_id}.")

def update_controller_weight_panel():
    if not (controller_window and controller_window.winfo_exists()):
        return

    processos_prontos = []
    for lista_processos in list(completed_day2_processes_by_filial.values()):
        processos_prontos.extend(lista_processos)

    controller_window.process_selector['values'] = sorted(processos_prontos)
    if not processos_prontos:
        controller_window.process_selector.set('')

def open_controller_interface():
    global controller_window, login_screen_ref

    parent = login_screen_ref

    if controller_window is None or not controller_window.winfo_exists():
        controller_window = tk.Toplevel(parent)
        controller_window.title("Controlador do Sistema")
        controller_window.geometry("500x750")
        controller_window.transient(parent)
        controller_window.protocol("WM_DELETE_WINDOW", lambda: on_controller_close(controller_window, "controller_window"))

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

        btn_retrain_model = tk.Button(controller_window, text="Re-treinar Modelo de Demanda", command=retrain_model, font=("Arial", 12), bg="#FF9800", fg="white")
        btn_retrain_model.pack(pady=5)

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

        update_controller_weight_panel()
        for win in open_movimentador_windows:
            update_movimentador_processes(win)
        for win in open_abastecedor_windows:
            update_abastecedor_completed_processes_display(win)

    else:
        controller_window.lift()
        update_controller_weight_panel()

def retrain_model():
    vendas_path = os.path.join(script_dir, "dados_vendas.csv")
    previsor.carregar_dados_vendas(vendas_path)
    previsor.preparar_features()
    previsor.treinar_modelo()
    messagebox.showinfo("Modelo", "Modelo re-treinado com sucesso!")

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
                current_qty = None
                if filial in sku_default_quantities and sku in sku_default_quantities[filial]:
                    # Se o valor for um dicionário com "previsao"
                    if isinstance(sku_default_quantities[filial][sku], dict):
                        current_qty = sku_default_quantities[filial][sku].get("previsao")
                    else:
                        current_qty = sku_default_quantities[filial][sku]
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
    # Modificado para gerar o relatório antes de fechar.
    if messagebox.askyesno("Sair", "Tem certeza que deseja fechar o Controlador? O relatório consolidado da Filial 7 será gerado e o aplicativo encerrado."):
        gerar_relatorio_consolidado_filial7()  # Gera o relatório
        on_toplevel_close(window, window_ref_var_name)
        login_screen_ref.destroy()
    else:
        window.lift()


# --- Configuração Inicial do Aplicativo ---
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

inicializar_previsor()
# --- Initial Process Generation and State Update ---
perform_daily_process_generation()
update_process_states_on_time_change()
# --- End of Initial Process Generation and State Update ---

open_controller_interface()

login_screen_ref.mainloop()