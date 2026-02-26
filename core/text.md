Perfeito — aqui está uma **versão redigida da seção de metodologia** de um projeto de pesquisa, elaborada com base no funcionamento técnico da aplicação descrita no seu TCC, mas **adaptada** para uma **nova implementação modular em Python**.
O texto está estruturado com tom acadêmico e foco em clareza metodológica (pronto para integrar ao seu TCC, relatório ou artigo).

---

## Metodologia

### 1. Visão geral do sistema desenvolvido

O presente trabalho propõe o desenvolvimento de uma aplicação computacional, em linguagem **Python**, voltada à **simulação do comportamento de transformadores de corrente (TCs)** durante condições de regime permanente e transitório, com ênfase na **análise da saturação do núcleo magnético**.
A aplicação foi concebida de forma **modular**, permitindo a adição de novas classes de transformadores ou modelos de excitação sem alterar a estrutura principal do código. Essa arquitetura visa garantir a escalabilidade do sistema e sua adequação a futuras normas e tecnologias de instrumentação.

O software tem como principais objetivos:

- Calcular a corrente secundária do TC sob diferentes condições de curto-circuito;
- Estimar a tensão requerida no secundário e verificar a ocorrência de saturação;
- Apresentar graficamente o comportamento temporal das correntes e fluxos magnéticos;
- Servir como ferramenta de apoio ao dimensionamento e estudo de TCs conforme parâmetros definidos pela IEC 61869-100.

---

### 2. Estrutura modular da aplicação

A aplicação foi organizada segundo uma **arquitetura orientada a objetos**, composta por três módulos principais:

1. **Módulo de Modelagem Física (`ct_model.py`)**
   Contém as classes e métodos responsáveis pela representação matemática do transformador de corrente.
   A classe principal, `CurrentTransformer`, encapsula os parâmetros físicos e elétricos do TC, tais como relação de transformação, resistência do enrolamento, tensão de saturação, carga secundária e parâmetros de saturação.
   Essa classe também implementa os métodos fundamentais de cálculo da corrente secundária ideal, corrente de excitação e fluxo magnético.

2. **Módulo de Simulação (`simulator.py`)**
   Responsável pela execução numérica do modelo, iterando no domínio do tempo segundo o passo temporal definido (∆t).
   Utiliza métodos discretos para o cálculo incremental do fluxo magnético, conforme as equações diferenciais apresentadas no TCC original (Eqs. 18–24).
   Esse módulo também realiza o cálculo de valores RMS por janela deslizante e a verificação da saturação com base na comparação entre a tensão requerida e a tensão de saturação estimada.

3. **Módulo de Visualização e Interface (`visualizer.py`)**
   Destinado à apresentação dos resultados, com geração de gráficos e relatórios dos parâmetros calculados.
   Os dados são organizados em estruturas `DataFrame` (biblioteca **pandas**), permitindo exportação para CSV e integração com ferramentas externas de análise.

---

### 3. Modelagem matemática implementada

A modelagem física do transformador segue as equações apresentadas no trabalho base, derivadas da teoria clássica de transformadores de corrente e das recomendações da norma IEC 61869-100.
O cálculo se desenvolve conforme as seguintes etapas:

1. **Corrente secundária ideal**
   Calculada conforme:
   [
   i*{s,ideal}(t) = \frac{\sqrt{2},I_p}{R*{TC}}\left[e^{-t/T_p} - \cos(\omega t)\right]
   ]
   onde (I*p) é a corrente de falta primária, (R*{TC}) a relação nominal do transformador, (T_p) a constante de tempo primária e (\omega) a frequência angular do sistema.

2. **Fluxo magnético e corrente de excitação**
   A excitação do núcleo é modelada por uma função não linear dependente do fluxo magnético.
   O fluxo instantâneo (\lambda(t)) é obtido pelo somatório incremental:
   [
   \lambda(t) = \sum*{i=0}^{n}\Delta\lambda(i\cdot\Delta t)
   \quad\text{com}\quad
   \Delta\lambda = \frac{R*{TC},[i_{s,ideal}-i_e]}{1+S\cdot A\cdot|\lambda|^{S-1}}\cdot\Delta t
   ]
   O termo (S) representa o coeficiente de inclinação da curva de magnetização e (A) é determinado a partir das condições de ensaio ou da tensão de saturação nominal.

3. **Corrente secundária real**
   Considerando as perdas de excitação:
   [
   i_{s}(t) = i_{s,ideal}(t) - i_e(t)
   ]

4. **Tensão de saturação**
   Quando o dado não é informado, é estimada por:
   [
   V_{sat} = K_h \cdot K_{ssc} \cdot K_{td} \cdot (R_{ct} + R_b) \cdot I_{sn}
   ]
   conforme recomendações da IEC 61869-100.

5. **Critério de saturação**
   A saturação é detectada quando a tensão requerida no secundário ((V*{req})) excede o valor de (V*{sat}), ou quando a diferença entre (i\_{s,ideal}) e (i_s) ultrapassa um limite predefinido.

---

### 4. Execução e parâmetros de simulação

A simulação é conduzida em passos discretos de tempo ((\Delta t)), definidos de forma a obter 200 pontos por ciclo fundamental, o que proporciona boa resolução numérica.
O algoritmo percorre um intervalo de 2 a 3 ciclos completos, suficiente para observar o início e o regime da saturação.
Os parâmetros de entrada incluem:

- Relação nominal do TC (por exemplo, 3000/1 A);
- Resistência do enrolamento secundário ((R\_{ct}));
- Resistência da carga ((R_b));
- Corrente de falta ((I_p));
- Constante de tempo primária ((T_p));
- Frequência do sistema ((f));
- Tensão de saturação ((V\_{sat})), quando disponível.

Todos os valores são armazenados em dicionários de configuração (`config.json`), permitindo a fácil replicação de experimentos e a inserção de novos modelos de transformador.

---

### 5. Saídas e análise dos resultados

Ao término da simulação, o sistema fornece:

- Gráficos da corrente secundária ideal e real, sobrepostos no tempo;
- Evolução do fluxo magnético (\lambda(t));
- Tensão requerida e comparação com (V\_{sat});
- Indicação de ocorrência e instante de saturação;
- Relatório numérico dos valores RMS e das margens de saturação.

Esses resultados são exportados automaticamente em formato `.csv` e `.png`, facilitando a análise comparativa entre diferentes tipos de TCs.

---

### 6. Expansão modular

A estrutura modular permite a inclusão de novos modelos, como transformadores de corrente do tipo **TPY**, **TPZ** ou baseados em núcleos de materiais não lineares específicos.
Para tal, basta criar novas classes herdando de `BaseTransformer`, sobrescrevendo os métodos de cálculo de (i_e(t)) e (\lambda(t)).
Essa abordagem favorece a pesquisa contínua sobre o comportamento transitório de TCs e a integração futura com sistemas de proteção digital ou ambientes de simulação elétrica completos, como **PSCAD** ou **OpenDSS**.

---

### 7. Ferramentas e bibliotecas

O desenvolvimento será realizado utilizando:

- **Python 3.12**;
- **NumPy** e **SciPy** para operações numéricas;
- **Pandas** para manipulação de dados;
- **Matplotlib** e **Plotly** para visualização;
- **pytest** para validação modular;
- **Poetry** para gestão de dependências e versionamento.

---
