"""
Tarefa consiste em:
Criar embeddings posicionais sequenciais e somar com embeddings de tokens
para obter os input embeddings finais. 
"""
import torch
import tiktoken

def pos_embedding(max_length: int, dim: int) -> torch.Tensor:   
    # Criar uma matriz de posições [max_length]
    positions = torch.arange(1, max_length + 1, dtype=torch.float32)
    pos_emb = torch.zeros(max_length, dim)
    for pos in range(max_length):       
        pos_emb[pos, :] = (pos + 1) + torch.arange(dim, dtype=torch.float32) * max_length    
    return pos_emb

def main():
    # Configurações
    vocab_size = 50257
    output_dim = 256
    max_length = 6  # janela de contexto de 6 tokens    

    print("Criando camada de embeddings de tokens")   
    # Criar embedding layer 
    embedding = torch.nn.Embedding(vocab_size, output_dim)
    print(f"\nEmbedding layer: vocab_size={vocab_size}, output_dim={output_dim}")
    print(f"Peso shape: {embedding.weight.shape}\n")
    
    # Carregar tokenizador e obter tokens de exemplo
    enc = tiktoken.get_encoding("gpt2")
    texto = "Raimundo Moura"
    token_ids = enc.encode(texto)
    
    print(f"Texto: '{texto}'")
    print(f"Token IDs: {token_ids}")
    print(f"Número de tokens: {len(token_ids)}")
    print(f"Max_length (janela): {max_length}\n")
    
    # Gerar embeddings de tokens   
    print("Gerando embeddings de tokens") 
    with torch.no_grad():
        token_embeddings = embedding(torch.LongTensor(token_ids))
    
    print(f"Token embeddings shape: {token_embeddings.shape}")    
    
    # Gerar embeddings posicionais    
    print("Gerando embeddings posicionais absolutos")    
    
    positional_emb = pos_embedding(max_length, output_dim)
    print(f"Positional embedding shape: {positional_emb.shape}")   
    
    # Mostrar alguns valores do positional embedding
    print(f"\nPrimeiras 3 posições do positional embedding (amostra):")
    for i in range(3):
        print(f"  Posição {i+1}: {positional_emb[i, :5].tolist()}...")  # primeiros 5 valores
    
    # Somar embeddings posicionais com token embeddings
    
    print("Somando token embeddings + positional embeddings")
  
    num_tokens = len(token_ids)
    
    # Opção 1: Pegar os primeiros max_length embeddings de token e somar com positional_emb
    if num_tokens >= max_length:
        token_subset = token_embeddings[:max_length]  
    else:
        # Se tiver menos tokens que max_length, repete o positional
        repeats = (max_length // num_tokens) + 1
        token_emb_extended = token_embeddings.repeat(max_length // num_tokens + 1, 1)[:max_length]
        token_subset = token_emb_extended    
    
    input_embeddings = token_subset + positional_emb
    
    print(f"\nEmbeddings de entrada shape: {input_embeddings.shape}")
    
    
    # Resultados
    print(f"\n Exemplos de Input Embeddings ")
    for i in range(max_length):
        if i < num_tokens:
            token_id = token_ids[i]
            print(f"\nPosição {i+1} (token ID {token_id}):")
        else:
            print(f"\nPosição {i+1} (padding):")
        
        print(f"  Embedding de entrada[:5]: {input_embeddings[i, :5].tolist()}")
        print(f"  Token embedding[:5]: {token_subset[i, :5].tolist() if i < len(token_subset) else 'N/A'}")
        print(f"  Embedding posicional[:5]: {positional_emb[i, :5].tolist()}")
    
    # Verificar embedding médio por posição
    print(f"\n Estatísticas ")
    print(f"Embeddings  de entrada mean (por posição): {input_embeddings.mean(dim=0)[:5].tolist()}")
    print(f"Embeddings de entrada std (por posição): {input_embeddings.std(dim=0)[:5].tolist()}")
    
    # Comparação com embeddings sem posição
    print(f"\n Comparação ")
    print(f"Sem embedding posicional (apenas token):")
    print(f"Token 0 embedding[:5]: {token_embeddings[0, :5].tolist()}")
    print(f"Com embedding posicional:")
    print(f"Posição 0 embedding de entrada[:5]: {input_embeddings[0, :5].tolist()}")   
    
    print("Conclusão: Input embeddings = Token Embeddings + Positional Embeddings")
    


if __name__ == "__main__":
    main()