import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def _interpolar_angulo(theta_a, G_a, theta_b, G_b, G_corte):
    """Realiza a interpolação linear para encontrar o ângulo exato onde G = G_corte."""
    return theta_a + (theta_b - theta_a) * (G_corte - G_a) / (G_b - G_a)

def calcular_hpbw(df_resumo):
    """
    Calcula a largura de feixe de -3 dB (HPBW) a partir do DataFrame de resumo.
    """
    idx_max = df_resumo['ganho_dbi'].idxmax()
    G_max = df_resumo.loc[idx_max, 'ganho_dbi']
    G_corte = G_max - 3.01
    
    df_sorted = df_resumo.sort_values('angulo').reset_index(drop=True)
    n = len(df_sorted)
    
    # Procura o ponto de corte à esquerda
    theta_esq = None
    for i in range(n):
        idx_atual = (idx_max - i) % n
        idx_anterior = (idx_max - i - 1) % n
        G1, G2 = df_sorted.loc[idx_atual, 'ganho_dbi'], df_sorted.loc[idx_anterior, 'ganho_dbi']
        
        if G1 >= G_corte >= G2 or G1 <= G_corte <= G2:
            th1, th2 = df_sorted.loc[idx_atual, 'angulo'], df_sorted.loc[idx_anterior, 'angulo']
            if abs(th1 - th2) > 180:
                if th1 < th2: th1 += 360
                else: th2 += 360
            theta_esq = _interpolar_angulo(th1, G1, th2, G2, G_corte) % 360
            break

    # Procura o ponto de corte à direita
    theta_dir = None
    for i in range(n):
        idx_atual = (idx_max + i) % n
        idx_proximo = (idx_max + i + 1) % n
        G1, G2 = df_sorted.loc[idx_atual, 'ganho_dbi'], df_sorted.loc[idx_proximo, 'ganho_dbi']
        
        if G1 >= G_corte >= G2 or G1 <= G_corte <= G2:
            th1, th2 = df_sorted.loc[idx_atual, 'angulo'], df_sorted.loc[idx_proximo, 'angulo']
            if abs(th1 - th2) > 180:
                if th1 < th2: th1 += 360
                else: th2 += 360
            theta_dir = _interpolar_angulo(th1, G1, th2, G2, G_corte) % 360
            break

    # Calcula a diferença angular total (HPBW)
    if theta_esq is not None and theta_dir is not None:
        delta = abs(theta_dir - theta_esq)
        hpbw = delta if delta <= 180 else 360 - delta
    else:
        hpbw = np.nan

    return hpbw, theta_esq, theta_dir, G_max, G_corte


def calcular_fbr(df_resumo):
    """
    Calcula a Relação Frente-Costas (FBR) a partir do DataFrame de resumo.
    """
    idx_max = df_resumo['ganho_dbi'].idxmax()
    g_front = df_resumo.loc[idx_max, 'ganho_dbi']
    angulo_front = df_resumo.loc[idx_max, 'angulo']
    
    angulo_back = (angulo_front + 180) % 360
    
    df_resumo['diff_angulo'] = np.abs(df_resumo['angulo'] - angulo_back)
    idx_back = df_resumo['diff_angulo'].idxmin()
    g_back = df_resumo.loc[idx_back, 'ganho_dbi']
    
    fbr = g_front - g_back
    
    return fbr, g_front, g_back, angulo_front, df_resumo.loc[idx_back, 'angulo']


def processar_diagrama_radiacao(
    caminho_csv: str,
    rssi_ref_0deg: float = -35.0,
    ganho_ref_dbi: float = 12.5,
    salvar_grafico: bool = False
):
    """
    Lê amostras de RSSI por ângulo de um CSV, calcula médias,
    aplica calibração por substituição, calcula HPBW, FBR e plota o gráfico polar.
    """
    # 1. Carregar os dados
    df = pd.read_csv(caminho_csv)
    
    # 2. Agrupar por ângulo e calcular média e desvio padrão das amostras
    df_resumo = df.groupby('angulo')['rssi'].agg(['mean', 'std', 'count']).reset_index()
    df_resumo = df_resumo.sort_values('angulo')
    
    # 3. Aplicar a calibração por substituição: G_aut(θ) = G_ref + (RSSI_aut(θ) - RSSI_ref_0°)
    df_resumo['ganho_dbi'] = ganho_ref_dbi + (df_resumo['mean'] - rssi_ref_0deg)
    
    # 4. Cálculo de Metrologia (HPBW e FBR)
    hpbw, th_esq, th_dir, G_max, G_corte = calcular_hpbw(df_resumo)
    fbr, g_front, g_back, ang_front, ang_back = calcular_fbr(df_resumo)
    
    print("\n--- RELATÓRIO DE METROLOGIA DA ANTENA ---")
    print(f"Ganho Máximo (Boresight): {G_max:.2f} dBi em {ang_front}°")
    print(f"Nível de Corte (-3 dB): {G_corte:.2f} dBi")
    print(f"Largura de Feixe (HPBW): {hpbw:.1f}°")
    print(f"Ganho na Traseira ({ang_back}°): {g_back:.2f} dBi")
    print(f"Relação Frente-Costas (FBR): {fbr:.2f} dB")
    print("------------------------------------------\n")

    # 5. Fechar o círculo completo de 0° a 360° para a plotagem
    if 0 in df_resumo['angulo'].values and 360 not in df_resumo['angulo'].values:
        linha_0 = df_resumo[df_resumo['angulo'] == 0].copy()
        linha_0['angulo'] = 360
        df_plot = pd.concat([df_resumo, linha_0], ignore_index=True)
    else:
        df_plot = df_resumo.copy()

    angulos_rad = np.radians(df_plot['angulo'])
    ganhos = df_plot['ganho_dbi'].values
    
    # 6. Cálculo das Bandas de Incerteza (ex: Desvio Padrão propagado para dBi)
    # Como a calibração por substituição é linear, o desvio padrão em dBi 
    # é idêntico ao desvio padrão das amostras de RSSI (já que a referência e o ganho fixo são constantes).
    std_dbi = df_plot['std'].values if 'std' in df_plot.columns else np.zeros_like(ganhos)
    
    ganho_superior = ganhos + std_dbi  # Limite superior (+1 sigma)
    ganho_inferior = ganhos - std_dbi  # Limite inferior (-1 sigma)

    # 7. Configuração do Plot Polar com Banda de Erro
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'projection': 'polar'})
    
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    
    # Desenhar a banda de confiança (Incerteza do RSSI)
    ax.fill_between(
        angulos_rad, 
        ganho_inferior, 
        ganho_superior, 
        color='#1f77b4', 
        alpha=0.25, 
        label='Incerteza ($\pm 1\sigma$)'
    )
    
    # Plotar a curva central do ganho médio (dBi)
    ax.plot(angulos_rad, ganhos, color='#1f77b4', linewidth=2.5, label='Ganho Médio (dBi)')
    
    # Destaca o feixe de -3 dB no gráfico se calculado com sucesso
    if not np.isnan(hpbw):
        ax.plot([np.radians(th_esq), np.radians(th_dir)], [G_corte, G_corte], 
                color='red', linestyle='--', linewidth=1.5, label=f'HPBW: {hpbw:.1f}° (-3 dB)')
        ax.scatter([np.radians(th_esq), np.radians(th_dir)], [G_corte, G_corte], 
                   color='red', zorder=5)

    piso_radial = np.floor(ganhos.min() / 5) * 5 - 5
    teto_radial = np.ceil(ganhos.max() / 5) * 5 + 5
    ax.set_rlim(piso_radial, teto_radial)
    
    ax.set_title(f"Diagrama de Radiação com Incerteza (HPBW = {hpbw:.1f}°)   |   FBR = {fbr:.1f} dB   |   Back Gain ({ang_back}°): {g_back:.2f} dBi", va='bottom', fontsize=13, pad=20)
    ax.set_rlabel_position(135)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='lower right', frameon=True)
    
    plt.tight_layout()
    
    if salvar_grafico:
        plt.savefig('diagrama_radiacao_com_erro.png', dpi=300)
        print("Gráfico salvo como 'diagrama_radiacao_com_erro.png'")
        
    plt.show()
    
    return df_resumo


def gerar_csv_ficticio(nome_arquivo='amostras_rssi.csv', n_amostras_por_angulo=1000):
    """Gera um arquivo CSV simulando 1000 medições de RSSI por ângulo."""
    angulos = np.arange(0, 360, 30)
    rssi_perfil_ideal = -48 + 10 * np.cos(np.radians(angulos))
    
    dados = []
    np.random.seed(42)
    
    for angulo, rssi_ideal in zip(angulos, rssi_perfil_ideal):
        amostras_rssi = np.random.normal(loc=rssi_ideal, scale=0.8, size=n_amostras_por_angulo)
        for rssi in amostras_rssi:
            dados.append({'angulo': angulo, 'rssi': round(rssi, 2)})
            
    df_ficticio = pd.DataFrame(dados)
    df_ficticio.to_csv(nome_arquivo, index=False)
    print(f"Arquivo '{nome_arquivo}' gerado com sucesso com {len(df_ficticio)} linhas!")


if __name__ == '__main__':
    # 1. Gera o CSV de teste
    gerar_csv_ficticio('amostras_rssi.csv')

    # 2. Processa os dados, calcula métricas e exibe o gráfico
    df_resultados = processar_diagrama_radiacao(
        caminho_csv='amostras_rssi.csv', 
        rssi_ref_0deg=-35.0, 
        ganho_ref_dbi=12.5, 
        salvar_grafico=True
    )