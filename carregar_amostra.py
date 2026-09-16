import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[0] # Caminho para o diretório base do projeto
TEXTS_DIR = BASE_DIR / "data" / "curated" / "texts" # Caminho para o diretório de textos curados
SAIDA_TXT = BASE_DIR / "data" / "curated" / "pretraining" / "saida.txt" # Caminho para o arquivo de saída

# Delimitador para separar os textos no arquivo de saída
DELIMITADOR = "\n" + "=" * 80 + "\n" 

def carregar_amostra():

     documentos = []
     for arquivo in sorted(TEXTS_DIR.glob("*.json")):
          with open(arquivo, encoding = "utf-8") as f:
               doc = json.load(f) 

               texto_completo = "\n\n". join(pag["texto"] for pag in doc.get("paginas", []))               
               documentos.append({
                    "id": doc.get("document_id"),
                    "titulo": doc.get("titulo"),
                    "categoria": doc.get("categoria"),
                    "texto": texto_completo,
                    })
     return documentos

def qtd_paragrafo(texto): 
     # Retorna a quantidade de parágrafos em um texto  
     return len([linha for linha in texto.splitlines() if linha.strip()])

def qtd_palavras(texto): # Retorna a quantidade de palavras em um texto
     return len(texto.split())

def gerar_relatorio(documentos): # Retorna a quantidade de relatórios e a quantidade total de palavras
     qtd_documentos = len(documentos)
     total_paragrafos = [qtd_paragrafo(doc["texto"]) for doc in documentos]
     total_palavras = [qtd_palavras(doc["texto"]) for doc in documentos]

     
     print("INFORMAÇÕES DO DATASET")
     
     print(f"Número de documentos        : {qtd_documentos}")
     print(f"Média de parágrafos/doc     : {sum(total_paragrafos)/qtd_documentos:.1f}")
     print(f"Média de palavras/doc       : {sum(total_palavras)/qtd_documentos:.1f}")
     print(f"Total de palavras           : {sum(total_palavras):,}")
     print(f"Documento mais curto        : {min(total_palavras)} palavras")
     print(f"Documento mais longo        : {max(total_palavras)} palavras")
     
     

def gerar_txt(documentos):
     # gera um unico arquivo de texto com todos os documentos, separados por um delimitador
     with open(SAIDA_TXT, "w", encoding = "utf-8") as f:
         for i, doc in enumerate(documentos, start=1):
            f.write(f"### DOCUMENTO {i} | ID: {doc['id']} | CATEGORIA: {doc['categoria']}\n")
            f.write(f"### TÍTULO: {doc['titulo']}\n")
            f.write(DELIMITADOR)
            f.write(doc["texto"])
            f.write("\n" + DELIMITADOR + "\n")
     print(f"Arquivo gerado: {SAIDA_TXT}")   

if __name__ == "__main__":
     documentos = carregar_amostra()
     gerar_relatorio(documentos)
     gerar_txt(documentos)
