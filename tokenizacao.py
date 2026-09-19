

import tiktoken


def main():
    # 1. Carregar o esquema de tokenização usado no modelo GPT-2
    enc = tiktoken.get_encoding("gpt2")

    # 2. Verificar o tamanho do vocabulário 
    vocab_size = enc.n_vocab

    print(f"Tamanho do vocabulário: {vocab_size} tokens")
    assert vocab_size == 50257, f"Esperado 50257, obtido {vocab_size}"
    print("Vocabulário confirmado: 50.257 tokens\n")

    # 3. Testar o texto "Raimundo Moura"
    texto = "Raimundo Moura"
    tokens = enc.encode(texto) # Gerar os tokens para o texto
    print(f"Texto: '{texto}'")
    print(f"Tokens gerados: {tokens}")
    print(f"Decodificado: '{enc.decode(tokens)}'") # decodificando os tokens
    print(f"Tokens esperados: [49, 1385, 41204, 49902, 403]")
    print(f"Bate com o esperado? {tokens == [49, 1385, 41204, 49902, 403]}\n")

    # 4. Teste
    textos_livres = [
        "Processamento de Linguagem Natural",
        "A Universidade Federal do Piauí",
        "Olá, mundo! Como você está?",
        "Estudando PLN, disciplina do mestrado da ufpi, com o professor Raimundo Moura",
    ]

    for t in textos_livres: # textos de saida
        tokens_t = enc.encode(t)
        print(f"Texto: '{t}'")
        print(f"Tokens gerados: {tokens_t}")
        print(f"Decodificado: '{enc.decode(tokens_t)}'\n")


if __name__ == "__main__":
    main()