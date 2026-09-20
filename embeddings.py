"""
Criar embedding layer: torch.nn.Embedding(vocab_size=50257, output_dim=256)
Imprimir embeddings para todo o vocabulário usando .weight
Gerar embeddings para "Raimundo Moura" usando os token IDs da questão 2
"""

import torch
import tiktoken


def main():
    # Criando a camada de embeddings
    vocab_size = 50257  # tamanho do vocabulário do GPT-2
    output_dim = 256    # dimensão do embedding 

    embedding = torch.nn.Embedding(vocab_size, output_dim)
    print(f"Embedding layer criada:")
    print(f"vocab_size: {vocab_size}")
    print(f"output_dim: {output_dim}")
    print(f"Peso shape: {embedding.weight.shape}  ->  [vocab_size, output_dim]\n")

    # Embeddings para todo o vocabulário
    print("Pesos do vocabulário completo ")
    print(f"Dimensões da matriz de pesos: {embedding.weight.shape}")
    # Mostrar apenas as primeiras 5 linhas
    print("Primeiras 5 linhas da matriz de pesos (shape: [5, 5]):")
    print(embedding.weight[:5, :5])
    print(f"\nTotal de parâmetros: {embedding.weight.numel()}")
    print(f"Representa {embedding.weight.numel() / 1e6:.2f} milhões de parâmetros\n")

    # Carregando o tokenizador GPT-2 e obter IDs de "Raimundo Moura"
    enc = tiktoken.get_encoding("gpt2")
    texto = "Raimundo Moura"
    token_ids = enc.encode(texto)

    print(f"Texto: '{texto}'")
    print(f"Token IDs: {token_ids}")
    print(f"Número de tokens: {len(token_ids)}\n")

    #Gerando os embeddings para os tokens de "Raimundo Moura"
    print("Embeddings gerados para 'Raimundo Moura' ")
    with torch.no_grad():  
        token_embeddings = embedding(torch.LongTensor(token_ids))

    print(f"Formatos dos embeddings: {token_embeddings.shape}")
    # Formato esperado: [num_tokens, output_dim] = [num_tokens, 256]

    # Lista de token e seu embedding
    for i, (token_id, embedding_vec) in enumerate(zip(token_ids, token_embeddings)):
        print(f"  Token {i}: id={token_id}, embedding[:5]={embedding_vec[:5].tolist()}")

    # Embedding médio 
    print(f"\nEmbedding médio (média de todos os tokens):")
    mean_embedding = token_embeddings.mean(dim=0)
    print(f"Formato: {mean_embedding.shape}")
    print(f"Valores médios (primeiros 5): {mean_embedding[:5].tolist()}")

    # Comparação com embedding do token 0 
    print(f"\nEmbedding correspondente ao token de ID 0:")
    print(f"  Valor: {embedding.weight[0].tolist()[:5]}...")


if __name__ == "__main__":
    main()