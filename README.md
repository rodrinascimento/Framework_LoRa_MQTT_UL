# Framework LoRa — Campo de Testes

Interface única (Qt/PySide6) que reúne os painéis de **gerência**, **cliente** e **caracterização**
e os cálculos das planilhas de **link budget**, **time on air** e **perda sistêmica**.

```
python app_framework_lora.py
```

ou execute `FrameworkLoRa.exe` (veja *Gerar o .exe* abaixo).

## O que tem em cada seção

| Seção | Substitui | O que faz |
|---|---|---|
| **Gerência (Serial)** | `Setup_Parametros_Serial.py` | Porta COM, tempo entre pacotes e nº de medidas; INICIAR / PAUSAR / PARAR / ATUALIZAR gravando `PARAMETROS.txt` no mesmo formato. Mostra ao vivo os pacotes que chegam no log do gateway. |
| **Cliente** | `Setup_Parametros_Cliente.py` | Limiar de luminosidade (0–4095) com histerese de +50, gravando `parametros_cliente.txt`. |
| **Link budget** | planilha *Tópico 3.2 - Linkbudget* | Espaço livre, log-distance, zona de Fresnel e gráfico Prx × distância. Projeto com vários nós (paredes, armários, máquinas, margem de fading) e comparação com a Prx medida, sugerindo o *n* ajustado. |
| **Time on Air** | planilha *LoRa Time on Air DataRate* | ToA pela fórmula da Semtech, LDRO automático, bit rate, taxa efetiva, intervalo mínimo para um duty cycle e tabela de todas as combinações SF × BW × CR. |
| **Site survey (logs)** | abas *MedidasSensor* das planilhas | Acompanha ao vivo o log mais recente do gateway (ou abre um arquivo), calcula máx./mín., média, média móvel em mW, desvio padrão, desvio médio e PER, com gráficos. |
| **Caracterização de antena** | `Diagrama de Radiacao HPBW*.py` e planilha *Perda Sistêmica* | **Assistente guiado**: mede a antena de referência, depois pede para girar a antena sob teste ângulo a ângulo, coletando N pacotes em cada posição. Monta o diagrama polar (±1σ), HPBW, FBR e ganho traseiro. Aba de perda sistêmica preenchida a partir das medidas. |

## Pasta de trabalho

Os arquivos ficam em `<pasta de trabalho>/4_N4_Armazenamento/`, o mesmo caminho dos scripts antigos:

- `Parametros/PARAMETROS.txt` e `Parametros/parametros_cliente.txt`: lidos pelo gateway e pelo nó.
- `Exportacoes/<data>/<hora>_<tipo>/`: cada exportação gera um `.xlsx` com abas organizadas,
  CSVs (separador `;`, decimal `,`) e as figuras em PNG.

A pasta de trabalho é escolhida na barra superior. Por padrão é a pasta do `.exe` (ou a pasta atual,
rodando pelo Python). Ela deve ser a mesma em que o gateway lê `PARAMETROS.txt`.

## Logs do gateway

O importador aceita CSV/TXT/LOG separados por vírgula, ponto e vírgula ou tabulação, com ou sem
cabeçalho, e também planilhas `.xlsx` no formato das abas *MedidasSensor*. A ordem esperada sem
cabeçalho é: `timestamp, contador, RSSI DL, SNR DL, RSSI UL, SNR UL`. No modo "acompanhar pasta",
o arquivo mais recente cujo nome contém o texto indicado (padrão `log`) é usado.

## Projetos

*Salvar projeto* grava todos os parâmetros das abas num `.json`; *Abrir projeto* restaura. A última
sessão também é restaurada automaticamente ao abrir o programa.

## Diferenças em relação às planilhas e scripts antigos

- **Time on Air:** a planilha usava preâmbulo `8 + 4,5`, CRC = 2 e arredondava depois de multiplicar
  por `(CR + 4)`. Agora segue a Semtech (`n + 4,25`, CRC 0/1, `ceil(...)·(CR+4)`), e o LDRO também
  liga em SF12/250 kHz (Ts > 16 ms). O valor antigo aparece na tabela só para comparação.
- **Site survey:** a planilha calculava a média a partir da 10ª amostra (`AVERAGE(N11:N990)`); aqui
  a média usa todas as amostras.
- **Cliente:** o campo de texto mostrava histerese +200 enquanto o arquivo usava +50; agora é +50 em tudo.
- **FBR:** a busca do ângulo traseiro passou a considerar a volta de 360°.
- **MQTT:** fora desta versão (só Serial). `Setup_Parametros_MQTT.py` continua no repositório.

## Gerar o .exe

- **GitHub Actions:** todo push/PR roda os testes e publica `FrameworkLoRa.exe` como artefato do
  workflow *Testes e executável Windows*. Tags `v*` anexam o `.exe` ao release.
- **Local (Windows):** execute `build_exe.bat`. O executável fica em `dist\FrameworkLoRa.exe`.

## Desenvolvimento

```
pip install -r requirements-dev.txt
python -m pytest -q tests
```

Os testes conferem os cálculos contra os valores salvos nas próprias planilhas do repositório e
simulam o gateway escrevendo um log durante o assistente do diagrama.
