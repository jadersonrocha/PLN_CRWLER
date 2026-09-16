
Relatório da Atividade de PLN

O Relatorio e Implementação podem ser acompanhadas no repositorio abaixo:
[github.com/jadersonrocha/PLN_CRWLER](https://github.com/jadersonrocha/PLN_CRWLER)

1. Carregamento e análise inicial do dataset - (carregar_amostra.py)
   Realizado o carregamento da amostra de teses e dissertações.
   A partir dela, foi gerado as informações básicas:
   •	Número total de documentos presentes na amostra.
   •	Número médio de parágrafos por documento.
   •	Número médio de palavras por documento. Em seguida, geramos um arquivo .txt contendo todos os documentos concatenados, separados por um delimitador para facilitar a distinção entre eles.
2. Tokenização com Byte Pair Encoding (BPE) - (tokenizacao.py)
   Instalamos a biblioteca tiktoken e carregamos o esquema de tokenização do modelo GPT-2.
   •	Confirmamos que o vocabulário possui 50.257 tokens.
   •	Utilizamos os métodos encode () e decode () para testar a codificação e decodificação de textos.
   •	Verificamos os tokens gerados para “Raimundo Moura” e comparamos com os valores esperados.
   •	Testamos também outros três textos livres para observar como diferentes entradas são representadas em tokens.
3. Geração de pares input-target
   Instalamos o PyTorch e implementamos a lógica de janelas deslizantes para criar pares input-target:
   •	Iteramos sobre o arquivo .txt para transformar os textos em tensores PyTorch.
   •	Criamos uma classe Dataset customizada para definir como os registros são carregados.
   •	Implementamos a classe DataLoader para embaralhar e organizar os dados em batches.
   •	Testamos parâmetros como max_length, stride e batch_size para observar o impacto na geração dos pares.
4. Tokens embeddings
   Construímos a camada de embeddings com torch.nn.Embedding(vocab_size=50257, output_dim=256).
   •	Imprimimos os embeddings gerados para todo o vocabulário.
   •	Geramos embeddings específicos para os tokens correspondentes à entrada “Raimundo Moura”, analisando como cada token é representado em um vetor de 256 dimensões.
5. Embeddings posicionais
   Implementamos uma função para tratar embeddings posicionais absolutos:
   •	Utilizamos valores sequenciais (1.1, 1.2, 1.3, …; 2.1, 2.2, 2.3, …) considerando uma janela de contexto de 6 tokens.
   •	Somamos os embeddings posicionais com os embeddings dos tokens para obter os input embeddings finais, que representam tanto o conteúdo quanto a posição dos tokens no contexto.

A atividade permitiu compreender o fluxo básico de pré-processamento de textos para modelos de linguagem: desde a análise inicial do dataset, passando pela tokenização e geração de pares input-target, até a construção de embeddings de tokens e posicionais. Cada etapa reforçou conceitos fundamentais para o treinamento de modelos do tipo GPT-like.
