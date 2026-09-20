"""
 Instalar PyTorch: pip install torch
 Iterar sobre o arquivo txt de entrada e retornar inputs e targets como tensores
 Criar Dataset customizada para carregar os dados
 Criar DataLoader para embaralhar e montar em batches
 Testar parâmetros: max_length, stride e batch_size
"""

import os
from typing import Self
import tiktoken
import torch
from torch.utils.data import Dataset, DataLoader
from pathlib import Path


# --- Configurações ---
BASE_DIR = Path(__file__).resolve().parents[0]
SAIDA_TXT = BASE_DIR / "data" / "curated" / "pretraining" / "saida.txt"

# Hiperparâmetros 
MAX_LENGTH = 4  # tamanho da janela (quantos tokens por input)
STRIDE = 1      # passo da janela
BATCH_SIZE = 2  # quantos exemplos por batch


def ler_texto(arquivo_path: Path) -> str:
    """Lê o arquivo de texto gerado"""
    with open(arquivo_path, encoding="utf-8") as f:
        texto = f.read()
    return texto


class TextoDataset(Dataset):
    """Dataset que retorna pares (input, target) usando janelas deslizantes."""

    def __init__(self, texto: str, max_length: int = MAX_LENGTH, stride: int = STRIDE):
        self.max_length = max_length
        self.stride = stride

        # Carrega o tokenizador GPT-2         
        self.enc = tiktoken.get_encoding("gpt2")

        # Converte o texto em tokens 
        self.tokens = self.enc.encode(texto)

        # Gera todos os pares (input, target) usando a janela deslizante
        self.examples = []
        for i in range(0, len(self.tokens) - max_length, stride):
            input_tokens = self.tokens[i: i + max_length]
            target_tokens = self.tokens[i + 1: i + max_length + 1]  # deslocado por 1
            self.examples.append((input_tokens, target_tokens))

        print(f"Dataset criado: {len(self.examples)} exemplos (max_length={max_length}, stride={stride})")

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        """Retorna o par (input, target) no índice idx como tensores torch.LongTensor."""
        input_tokens, target_tokens = self.examples[idx]

        # Converte para tensores PyTorch
        input_tensor = torch.LongTensor(input_tokens)
        target_tensor = torch.LongTensor(target_tokens)

        return input_tensor, target_tensor


def main():
    # Lendo os arquivo de texto
    if not SAIDA_TXT.exists():
        print(f"Arquivo não encontrado: {SAIDA_TXT}")
        print("Carregando amostras para gerar o arquivo saida.txt")
        return

    texto = ler_texto(SAIDA_TXT)
    print(f"Texto lido: {len(texto)} caracteres, {len(texto.split())} palavras")

    # Criando o Dataset
    dataset = TextoDataset(texto, max_length=MAX_LENGTH, stride=STRIDE)

    # Criando o DataLoader
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    # Testando o DataLoader
    print("\n Testando DataLoader ")
    for batch_idx, (inputs, targets) in enumerate(dataloader):
        print(f"Batch {batch_idx}:")
        print(f"inputs shape: {inputs.shape}  ->  [batch_size, max_length]")
        print(f"inputs: {inputs}")
        print(f"targets shape: {targets.shape}  ->  [batch_size, max_length]")
        print(f"targets: {targets}")

        # Apenas alguns batches para teste
        if batch_idx >= 2:
            print("Exibindos os primeiros batches para teste")
            break

    # 6. Testar com diferentes parâmetros
    print("\nTestando com diferentes parâmetros ")
    for ml in [2, 4, 8]:
        for st in [1, 2]:
            print(f"\n max_length={ml}, stride={st} ")
            ds_temp = TextoDataset(texto, max_length=ml, stride=st)
            print(f"  Total de exemplos: {len(ds_temp)}")
            dl_temp = DataLoader(ds_temp, batch_size=BATCH_SIZE, shuffle=False)
            for i, (inp, tgt) in enumerate(dl_temp):
                print(f"  Batch {i}: input shape={inp.shape}, target shape={tgt.shape}")
                if i >= 1:
                    break


if __name__ == "__main__":
    main()