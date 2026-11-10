# Controle de Parâmetros e Execução | N6 | WissTek-IoT | Framework LoRa
import tkinter as tk
from tkinter import messagebox
import serial.tools.list_ports
import os

# Caminho para salvamento dos parâmetros
PASTA_ARMAZENAMENTO = os.path.join("4_N4_Armazenamento")
CAMINHO_PARAMETROS = os.path.join(PASTA_ARMAZENAMENTO, "Parametros")
os.makedirs(CAMINHO_PARAMETROS, exist_ok=True)
ARQUIVO_PARAMETROS = os.path.join(CAMINHO_PARAMETROS, "PARAMETROS.txt")

def listar_portas_seriais():
    portas = serial.tools.list_ports.comports()
    lista = []
    for p in portas:
        lista.append(p.device)
    return lista if lista else ["Nenhuma COM encontrada"]

def escrever_parametros(comando):
    porta_selecionada = combo_serial.get().strip()
    tempo_str = entry_tempo.get().strip().replace(",", ".")
    medidas_str = entry_medidas.get().strip()

    if not porta_selecionada or "Nenhuma" in porta_selecionada:
        messagebox.showerror("Erro", "Selecione uma porta serial válida para o Gateway!")
        return

    try:
        tempo = float(tempo_str)
    except ValueError:
        messagebox.showerror("Erro", "O tempo entre pacotes deve ser um número válido!")
        return

    try:
        medidas = int(medidas_str)
        if medidas <= 0:
            raise ValueError()
    except ValueError:
        messagebox.showerror("Erro", "O número de medidas deve ser um inteiro maior que zero!")
        return

    if porta_selecionada.upper().startswith("COM"):
        num_serial = porta_selecionada.upper().replace("COM", "")
    else:
        num_serial = porta_selecionada

    try:
        with open(ARQUIVO_PARAMETROS, "w") as f:
            f.write(f"{comando}\n")
            f.write(f"{medidas}\n")
            f.write(f"{tempo}\n")
            f.write(f"{num_serial}\n")
        
        status_txt = {0: "PARADO", 1: "INICIADO / ATUALIZADO", 2: "PAUSADO"}
        lbl_status_val.config(text=status_txt[comando], fg="blue" if comando == 1 else ("orange" if comando == 2 else "red"))
    except Exception as e:
        messagebox.showerror("Erro", f"Não foi possível gravar o arquivo de parâmetros: {e}")

def btn_iniciar():
    escrever_parametros(1)

def btn_pausar():
    escrever_parametros(2)

def btn_parar():
    escrever_parametros(0)

def btn_atualizar():
    # Atualiza os parâmetros mantendo o estado de execução ativo (1)
    escrever_parametros(1)
    messagebox.showinfo("Atualização", "Parâmetros atualizados com sucesso para o teste em andamento!")

def set_short_distance():
    entry_tempo.delete(0, tk.END)
    entry_tempo.insert(0, "0.2")

def set_long_distance():
    entry_tempo.delete(0, tk.END)
    entry_tempo.insert(0, "3")

# ================= INTERFACE GRÁFICA =================
root = tk.Tk()
root.title("FEE247 - LoRa - Parâmetros de Medidas")
root.geometry("480x440")
root.resizable(False, False)

tk.Label(root, text="Painel de Parâmetros de Medidas com LoRa", font=("Arial", 12, "bold")).pack(pady=10)

# 1. Seleção da Porta Serial
frame_serial = tk.LabelFrame(root, text=" 1. Porta Serial do Gateway ", font=("Arial", 10, "bold"))
frame_serial.pack(fill="x", padx=15, pady=5)

portas_disponiveis = listar_portas_seriais()
combo_serial = tk.StringVar(root)
combo_serial.set(portas_disponiveis[0])

menu_serial = tk.OptionMenu(frame_serial, combo_serial, *portas_disponiveis)
menu_serial.config(width=20)
menu_serial.pack(side="left", padx=10, pady=8)

tk.Button(frame_serial, text="Atualizar Portas", command=lambda: [
    menu_serial['menu'].delete(0, 'end'),
    *[menu_serial['menu'].add_command(label=p, command=lambda val=p: combo_serial.set(val)) for p in listar_portas_seriais()]
]).pack(side="right", padx=10)

# 2. Tempo entre pacotes
frame_tempo = tk.LabelFrame(root, text=" 2. Tempo entre Pacotes ", font=("Arial", 10, "bold"))
frame_tempo.pack(fill="x", padx=15, pady=5)

entry_tempo = tk.Entry(frame_tempo, font=("Arial", 10), width=10)
entry_tempo.insert(0, "0.2")
entry_tempo.pack(side="left", padx=10, pady=8)
tk.Label(frame_tempo, text="segundos").pack(side="left")

tk.Button(frame_tempo, text="Long Distance (3s)", bg="#d9fdd3", command=set_long_distance).pack(side="right", padx=5)
tk.Button(frame_tempo, text="Short Distance (200ms)", bg="#d0e1fd", command=set_short_distance).pack(side="right", padx=5)

# 3. Número de medidas
frame_medidas = tk.LabelFrame(root, text=" 3. Número de Medidas ", font=("Arial", 10, "bold"))
frame_medidas.pack(fill="x", padx=15, pady=5)

entry_medidas = tk.Entry(frame_medidas, font=("Arial", 10), width=15)
entry_medidas.insert(0, "100")
entry_medidas.pack(side="left", padx=10, pady=8)

# 4. Botões de Controle de Execução
frame_botoes = tk.LabelFrame(root, text=" 4. Comandos de Execução ", font=("Arial", 10, "bold"))
frame_botoes.pack(fill="x", padx=15, pady=10)

btn_i = tk.Button(frame_botoes, text="INICIAR", bg="green", fg="white", font=("Arial", 9, "bold"), width=8, command=btn_iniciar)
btn_i.grid(row=0, column=0, padx=5, pady=8)

btn_p = tk.Button(frame_botoes, text="PAUSAR", bg="orange", fg="white", font=("Arial", 9, "bold"), width=8, command=btn_pausar)
btn_p.grid(row=0, column=1, padx=5, pady=8)

btn_s = tk.Button(frame_botoes, text="PARAR", bg="red", fg="white", font=("Arial", 9, "bold"), width=8, command=btn_parar)
btn_s.grid(row=0, column=2, padx=5, pady=8)

btn_att = tk.Button(frame_botoes, text="ATUALIZAR", bg="blue", fg="white", font=("Arial", 9, "bold"), width=9, command=btn_atualizar)
btn_att.grid(row=0, column=3, padx=5, pady=8)

# Status Atual na Tela
frame_status = tk.Frame(root)
frame_status.pack(fill="x", padx=15, pady=5)
tk.Label(frame_status, text="Status enviado: ", font=("Arial", 9)).pack(side="left")
lbl_status_val = tk.Label(frame_status, text="AGUARDANDO COMANDO", font=("Arial", 9, "bold"), fg="gray")
lbl_status_val.pack(side="left", padx=5)

def fechar():
    if messagebox.askokcancel("Sair", "Deseja fechar o parametrizador?"):
        btn_parar()        
        root.destroy()

root.protocol("WM_DELETE_WINDOW", fechar)
root.mainloop()
