# Controle de Parâmetros e Execução | N6 | WissTek-IoT | Framework LoRa (Apenas MQTT)
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk  # Importante: precisa importar o ttk para usar o Combobox
import os

# Caminho para salvamento dos parâmetros
PASTA_ARMAZENAMENTO = os.path.join("4_N4_Armazenamento")
CAMINHO_PARAMETROS = os.path.join(PASTA_ARMAZENAMENTO, "Parametros")
os.makedirs(CAMINHO_PARAMETROS, exist_ok=True)
ARQUIVO_MQTT = os.path.join(CAMINHO_PARAMETROS, "MQTT.txt")

def configurar_mqtt(cmd_override=None):
    # Define o comando: se passado por parâmetro (botões), usa ele; senão, usa "1" como padrão
    comando = str(cmd_override) if cmd_override is not None else "1"

    medidas = entry_medidas.get().strip()
    tempo = entry_tempo.get().strip()
    broker = entry_broker.get().strip()
    porta_mqtt = entry_porta_mqtt.get().strip()
    topico_dl = entry_topico_dl.get().strip()
    topico_ul = entry_topico_ul.get().strip()
    qos = 1 if var_qos.get() else 0

    if not medidas or not tempo or not broker or not porta_mqtt or not topico_dl or not topico_ul:
        messagebox.showerror("Erro", "Todos os campos do MQTT devem ser preenchidos!")
        return

    try:
        int(porta_mqtt)
    except ValueError:
        messagebox.showerror("Erro", "A Porta MQTT deve ser um número inteiro válido!")
        return

    try:
        with open(ARQUIVO_MQTT, "w", encoding="utf-8") as f:
            f.write(f"{comando}\n")       # 1ª Linha: Comando (Iniciar/Pausar/Parar/Configurar)
            f.write(f"{medidas}\n")      # 2ª Linha: Número de medidas
            f.write(f"{tempo}\n")        # 3ª Linha: Tempo entre pacotes
            f.write(f"{broker}\n")       # 4ª Linha: Broker
            f.write(f"{porta_mqtt}\n")   # 5ª Linha: Porta MQTT
            f.write(f"{topico_dl}\n")    # 6ª Linha: Tópico DL
            f.write(f"{topico_ul}\n")    # 7ª Linha: Tópico UL
            f.write(f"{qos}\n")          # 8ª Linha: QoS
        #messagebox.showinfo("Sucesso", "Configurações do Framework MQTT salvas com sucesso!")
    except Exception as e:
        messagebox.showerror("Erro", f"Não foi possível salvar o arquivo MQTT.txt: {e}")

def btn_iniciar():
    configurar_mqtt(1)

def btn_pausar():
    configurar_mqtt(2)

def btn_parar():
    configurar_mqtt(0)

def btn_atualizar():
    configurar_mqtt(1)

def set_short_distance():
    entry_tempo.delete(0, tk.END)
    entry_tempo.insert(0, "1.5")

def set_long_distance():
    entry_tempo.delete(0, tk.END)
    entry_tempo.insert(0, "4.5")

# ================= INTERFACE GRÁFICA =================
root = tk.Tk()
root.title("FEE247 - LoRa - Parâmetros MQTT e Medidas")
root.geometry("480x500")
root.resizable(False, False)

tk.Label(root, text="Painel de Parâmetros - Comunicação MQTT", font=("Arial", 12, "bold")).pack(pady=10)

# Configurações do Broker MQTT
frame_mqtt = tk.LabelFrame(root, text=" Configurações do Broker MQTT ", font=("Arial", 10, "bold"))
frame_mqtt.pack(fill="x", padx=15, pady=5)

tk.Label(frame_mqtt, text="URL do Broker:").grid(row=0, column=0, sticky="w", padx=5, pady=2)

# Lista com os seus servidores de exemplo
lista_brokers = ["broker.hivemq.com", "test.mosquitto.org", "www.tpm.dev.br"]

# Substitui o Entry antigo armazenando o Combobox diretamente na variável 'entry_broker'
entry_broker = ttk.Combobox(frame_mqtt, width=28, values=lista_brokers)
entry_broker.current(0)
entry_broker.grid(row=0, column=1, padx=5, pady=2)


btn_config_mqtt = tk.Button(frame_mqtt, text="CONFIGURA MQTT", bg="yellow", fg="black", font=("Arial", 9, "bold"), width=15, command=configurar_mqtt)
btn_config_mqtt.grid(row=0, column=3, columnspan=2, pady=8) # 


tk.Label(frame_mqtt, text="Porta MQTT:").grid(row=4, column=0, sticky="w", padx=5, pady=2)
entry_porta_mqtt = tk.Entry(frame_mqtt, width=10)
entry_porta_mqtt.insert(0, "1883")
entry_porta_mqtt.grid(row=4, column=1, sticky="w", padx=5, pady=2)

tk.Label(frame_mqtt, text="Tópico DL:").grid(row=5, column=0, sticky="w", padx=5, pady=2)
entry_topico_dl = tk.Entry(frame_mqtt, width=30)
entry_topico_dl.insert(0, "mot_mqtt_SEU_RA/gateway/downlink")
entry_topico_dl.grid(row=5, column=1, padx=5, pady=2)

tk.Label(frame_mqtt, text="Tópico UL:").grid(row=6, column=0, sticky="w", padx=5, pady=2)
entry_topico_ul = tk.Entry(frame_mqtt, width=30)
entry_topico_ul.insert(0, "mot_mqtt_SEU_RA/gateway/uplink")
entry_topico_ul.grid(row=6, column=1, padx=5, pady=2)

var_qos = tk.BooleanVar(value=True)
chk_qos = tk.Checkbutton(frame_mqtt, text="Habilitar QoS 1", variable=var_qos)
chk_qos.grid(row=7, column=0, columnspan=2, sticky="w", padx=5, pady=2)

# 2. Tempo entre pacotes
frame_tempo = tk.LabelFrame(root, text=" 2. Tempo entre Pacotes [s] ", font=("Arial", 10, "bold"))
frame_tempo.pack(fill="x", padx=15, pady=5)

entry_tempo = tk.Entry(frame_tempo, font=("Arial", 10), width=10)
entry_tempo.insert(0, "4.5")
entry_tempo.pack(side="left", padx=10, pady=8)
tk.Label(frame_tempo, text="[s]").pack(side="left")

tk.Button(frame_tempo, text="Long Distance (4.5s)", bg="#d9fdd3", command=set_long_distance).pack(side="right", padx=5)
tk.Button(frame_tempo, text="Short Distance (1.5s)", bg="#d0e1fd", command=set_short_distance).pack(side="right", padx=5)

# 3. Número de medidas
frame_medidas = tk.LabelFrame(root, text=" 3. Número de Medidas ", font=("Arial", 10, "bold"))
frame_medidas.pack(fill="x", padx=15, pady=5)

entry_medidas = tk.Entry(frame_medidas, font=("Arial", 10), width=15)
entry_medidas.insert(0, "100")
entry_medidas.pack(side="left", padx=10, pady=8)

# 4. Botões de Controle de Execução
frame_botoes = tk.LabelFrame(root, text=" 4. Comandos de Execução ", font=("Arial", 10, "bold"))
frame_botoes.pack(fill="x", padx=15, pady=10)

btn_i = tk.Button(frame_botoes, text="INICIAR", bg="green", fg="white", font=("Arial", 9, "bold"), width=9, command=btn_iniciar)
btn_i.grid(row=0, column=0, padx=5, pady=8)

btn_p = tk.Button(frame_botoes, text="PAUSAR", bg="orange", fg="white", font=("Arial", 9, "bold"), width=9, command=btn_pausar)
btn_p.grid(row=0, column=1, padx=5, pady=8)

btn_s = tk.Button(frame_botoes, text="PARAR", bg="red", fg="white", font=("Arial", 9, "bold"), width=9, command=btn_parar)
btn_s.grid(row=0, column=2, padx=5, pady=8)

btn_att = tk.Button(frame_botoes, text="ATUALIZAR", bg="blue", fg="white", font=("Arial", 9, "bold"), width=9, command=btn_atualizar)
btn_att.grid(row=0, column=3, padx=5, pady=8)


# Status Atual na Tela
frame_status = tk.Frame(root)
frame_status.pack(fill="x", padx=15, pady=5)
tk.Label(frame_status, text="Status enviado: ", font=("Arial", 9)).pack(side="left")
lbl_status_val = tk.Label(frame_status, text="AGUARDANDO COMANDO", font=("Arial", 9, "bold"), fg="gray")
lbl_status_val.pack(side="left", padx=5)

def carregar_parametros_iniciais():
    """Lê o arquivo MQTT.txt ao iniciar e preenche os campos da interface se o arquivo existir."""
    if os.path.exists(ARQUIVO_MQTT):
        try:
            with open(ARQUIVO_MQTT, "r", encoding="utf-8") as f:
                linhas = [l.strip() for l in f.readlines()]
            
            # Verifica se o arquivo contém todas as 8 linhas esperadas
            if len(linhas) >= 8:
                # Linha 0: Comando (ignorado na interface visual, mas mantido no arquivo)
                num_medidas = linhas[1]
                tempo = linhas[2]
                broker = linhas[3]
                porta_mqtt = linhas[4]
                topico_dl = linhas[5]
                topico_ul = linhas[6]
                qos = linhas[7]

                # Preenche Número de Medidas
                if num_medidas:
                    entry_medidas.delete(0, tk.END)
                    entry_medidas.insert(0, num_medidas)

                # Preenche Tempo entre pacotes
                if tempo:
                    entry_tempo.delete(0, tk.END)
                    entry_tempo.insert(0, tempo)

                # Preenche Broker MQTT
                if broker:
                    entry_broker.set(broker)

                # Preenche Porta MQTT
                if porta_mqtt:
                    entry_porta_mqtt.delete(0, tk.END)
                    entry_porta_mqtt.insert(0, porta_mqtt)

                # Preenche Tópico DL
                if topico_dl:
                    entry_topico_dl.delete(0, tk.END)
                    entry_topico_dl.insert(0, topico_dl)

                # Preenche Tópico UL
                if topico_ul:
                    entry_topico_ul.delete(0, tk.END)
                    entry_topico_ul.insert(0, topico_ul)

                # Preenche QoS
                if qos in ("1", "0"):
                    var_qos.set(qos == "1")
                    
        except Exception as e:
            print(f"[Aviso] Não foi possível carregar os parâmetros iniciais do MQTT.txt: {e}")

# Executa o carregamento automático dos parâmetros ao abrir a aplicação
carregar_parametros_iniciais()

def fechar():
    if messagebox.askokcancel("Sair", "Deseja fechar o parametrizador?"):
        btn_parar()        
        root.destroy()

root.protocol("WM_DELETE_WINDOW", fechar)
root.mainloop()
