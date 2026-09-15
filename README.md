# BDTD Benchmarks

Projeto em Python para coletar documentos academicos da BDTD, baixar PDFs, organizar metadados, detectar duplicatas e preparar dados para pre-treino continuado, fine-tuning, RAG e benchmarks.

## Requisitos

- Python 3.11 ou superior
- Acesso a internet para consultar a BDTD e os repositorios
- PowerShell no Windows

## Instalacao

Na raiz do projeto, crie e ative o ambiente virtual:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Instale as dependencias:

```powershell
python -m pip install -r requirements.txt
```

Se o PowerShell bloquear a ativacao, execute uma vez na sessao:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

## Executar o servidor

Na raiz do projeto:

```powershell
python -m data.server.server
```

Servidor local:

```text
http://127.0.0.1:5000
```

Principais endpoints:

```text
GET /api/contadores
GET /api/progresso
GET /api/documentos
GET /api/documentos/dissertacoes
GET /api/documentos/teses
GET /arquivos/<categoria>/<arquivo>.pdf
```

A rota `/api` executa uma nova coleta completa. Para acompanhar o progresso durante a coleta:

```text
http://127.0.0.1:5000/api/progresso
```

## Executar o crawler

Em outro terminal, na raiz do projeto:

```powershell
$env:BDTD_MAX_PAGES="200"
$env:BDTD_RETRIES="5"
python -c "from data.server.crawler import scrape_bdtd; print(scrape_bdtd())"
```

O crawler consulta a API da BDTD, salva as respostas brutas, tenta baixar os PDFs e registra os metadados no staging. Documentos ja existentes sao ignorados quando identificados por ID ou DOI.

Variaveis opcionais:

```powershell
$env:BDTD_LIMIT="30"
$env:BDTD_MAX_PAGES="200"
$env:BDTD_RETRIES="5"
```

Para repositórios com certificado SSL problemático, mantenha a validação SSL ativa sempre que possível. O fallback inseguro deve ser restrito a hosts conhecidos:

```powershell
$env:CRAWLER_SSL_INSECURE_HOSTS="exemplo.org"
```

## Executar a curadoria

A curadoria extrai texto dos PDFs, cria chunks e gera datasets para pre-treino, fine-tuning e RAG:

```powershell
Remove-Item Env:CURATOR_MAX_DOCUMENTS -ErrorAction SilentlyContinue
python data/server/curator.py
```

Para testar com poucos documentos:

```powershell
$env:CURATOR_MAX_DOCUMENTS="10"
python data/server/curator.py
```

Os resultados sao acompanhados pelo arquivo:

```text
data/curated/manifest.json
data/curated/falhas_curadoria.json
```

## Camadas de dados

```text
data/
├── raw/
│   ├── api/                 Respostas brutas paginadas da BDTD
│   └── documentos/          PDFs baixados, separados por categoria
├── staging/
│   └── documentos.jsonl     Registros de entrada do pipeline
├── processed/
│   ├── catalogo_processado.json
│   ├── duplicatas.json
│   └── <documento>/metadata.json
├── curated/
│   ├── catalogo.json       Catalogo publico de documentos validos
│   ├── texts/               Texto extraido por documento
│   ├── pretraining/         Corpus textual e divisao de treino
│   ├── finetuning/          Exemplos de classificacao e QA
│   ├── rag/                 Documentos e chunks para recuperacao
│   ├── manifest.json        Estatisticas da curadoria
│   └── falhas_curadoria.json
└── server/
    ├── crawler.py           Coleta, download e staging
    └── server.py            Aplicacao Flask e endpoints
```

## Fluxo do projeto

```text
BDTD
  -> data/raw/api
  -> data/raw/documentos
  -> data/staging
  -> data/processed
  -> data/curated
```

- `raw` preserva a origem da coleta.
- `staging` registra os documentos recebidos pelo processamento.
- `processed` padroniza, anonimiza e deduplica.
- `curated` prepara os dados para experimentos de PLN.

## Observacoes

