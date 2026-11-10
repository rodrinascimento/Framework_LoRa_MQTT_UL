# Setup | Cliente | WissTek-IoT | Framework Local DL-UL
# 13/10/2026
#====== Setup do Cliente ======
# Define o limiar de luminosidade e grava o parametros_cliente.txt
import tkinter as tk
from tkinter import messagebox
import os

# Caminho para salvamento dos parâmetros
PASTA_ARMAZENAMENTO = os.path.join("4_N4_Armazenamento")
CAMINHO_PARAMETROS = os.path.join(PASTA_ARMAZENAMENTO, "Parametros")
os.makedirs(CAMINHO_PARAMETROS, exist_ok=True)
caminho_cliente = os.path.join(CAMINHO_PARAMETROS, "parametros_cliente.txt")

# Faixa do ADC de 12 bits do ESP32
LIMIAR_MIN = 0
LIMIAR_MAX = 4095

def carregar_limiar():
    try:
        with open(caminho_cliente, "r") as f:
            return int(float(f.readline().strip().replace(",", ".")))
    except (FileNotFoundError, ValueError):
        return 2000

def salvar_limiar():
    try:
        limiar = int(entrada_limiar.get().strip())
        if limiar < LIMIAR_MIN or limiar > LIMIAR_MAX:
            raise ValueError
    except ValueError:
        messagebox.showerror("Erro", f"Limiar inválido. Use um inteiro de {LIMIAR_MIN} a {LIMIAR_MAX}.")
        return
    with open(caminho_cliente, "w") as f:
        f.write(str(limiar) + "\n")
    
    limiar_desligar = min(LIMIAR_MAX, limiar + 50)
    status.config(text=f"Ligar: {limiar} | Desligar: {limiar_desligar} salvo")
    print(f"Limpar Ligar: {limiar}, Desligar: {limiar_desligar} salvo em: {caminho_cliente}")

def slider_mudou(valor):
    val_int = int(float(valor))
    entrada_limiar.delete(0, tk.END)
    entrada_limiar.insert(0, str(val_int))
    # Atualiza o label do segundo limiar dinamicamente
    limiar_desl = min(LIMIAR_MAX, val_int + 50)
    label_histerese.config(text=f"Limiar de Desligar (+50): {limiar_desl}")

def entrada_mudou(event=None):
    try:
        val_int = int(entrada_limiar.get().strip())
        escala.set(val_int)
        limiar_desl = min(LIMIAR_MAX, val_int + 200)
        label_histerese.config(text=f"Limiar de Desligar (+50): {limiar_desl}")
    except ValueError:
        pass

# ===================== INTERFACE =====================
janela = tk.Tk()
janela.title("Setup - Cliente | Framework DL-UL")
janela.geometry("380x280")

tk.Label(janela, text="Limiar de Ligar (0 a 4095):", font=("Arial", 11)).pack(pady=(10, 0))
tk.Label(janela, text="Abaixo deste valor o LED acende", font=("Arial", 8)).pack()

escala = tk.Scale(janela, from_=LIMIAR_MIN, to=LIMIAR_MAX, orient="horizontal", length=320,
                  showvalue=False, command=slider_mudou)
escala.pack()

entrada_limiar = tk.Entry(janela, width=10, justify="center")
entrada_limiar.pack(pady=5)
entrada_limiar.bind("<Return>", entrada_mudou)
entrada_limiar.bind("<FocusOut>", entrada_mudou)

# Label informativo para o segundo limiar (histerese de +50)
label_histerese = tk.Label(janela, text="Limiar de Desligar (+50): --", font=("Arial", 9, "bold"), fg="darkred")
label_histerese.pack(pady=5)

limiar_inicial = carregar_limiar()
escala.set(limiar_inicial)
slider_mudou(limiar_inicial)

tk.Button(janela, text="Salvar limiar", width=20, command=salvar_limiar).pack(pady=5)

status = tk.Label(janela, text="", font=("Arial", 9), fg="gray")
status.pack(pady=5)

def fechar():
    if messagebox.askokcancel("Sair", "Deseja fechar o parametrizador?"):
            
        janela.destroy()

janela.protocol("WM_DELETE_WINDOW", fechar)

janela.mainloop()

