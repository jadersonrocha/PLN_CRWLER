from pathlib import Path
from datetime import datetime, timezone
import json
import logging
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STAGING_PATH = DATA_DIR / "staging" / "documentos.jsonl"
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_CATALOG_PATH = PROCESSED_DIR / "catalogo_processado.json"
DUPLICATES_PATH = PROCESSED_DIR / "duplicatas.json"
CURATED_DIR = DATA_DIR / "curated"
CATALOG_PATH = CURATED_DIR / "catalogo.json"
CATEGORIAS = ("dissertacoes", "teses", "outros")

logger = logging.getLogger("bdtd-crawler.pipeline")


def normalizar_texto(valor):
    valor = unicodedata.normalize("NFKC", str(valor or ""))
    return re.sub(r"\s+", " ", valor).strip()


def chave_normalizada(valor):
    valor = unicodedata.normalize("NFKD", normalizar_texto(valor))
    return "".join(
        caractere
        for caractere in valor
        if not unicodedata.combining(caractere)
    ).casefold()


def limpar_url(url):
    if not url:
        return None
    partes = urlsplit(url)
    campos_sensiveis = {
        "token", "key", "email", "cpf", "session",
        "utm_source", "utm_medium", "utm_campaign",
    }
    parametros = [
        (chave, valor)
        for chave, valor in parse_qsl(partes.query)
        if chave.casefold() not in campos_sensiveis
    ]
    return urlunsplit(
        (partes.scheme, partes.netloc, partes.path, urlencode(parametros), "")
    )


def normalizar_doi(valor):
    correspondencia = re.search(
        r"10\.\d{4,9}/[-._;()/:A-Z0-9]+",
        str(valor or ""),
        flags=re.IGNORECASE,
    )
    if not correspondencia:
        return None
    return correspondencia.group(0).rstrip(".,;)").casefold()


def anonimizar_documento(documento):
    campos_sensiveis = {
        "autor", "autores", "email", "cpf", "telefone", "contato",
    }
    anonimizado = {
        chave: valor
        for chave, valor in documento.items()
        if chave.casefold() not in campos_sensiveis
    }
    anonimizado["anonimizado"] = True
    return anonimizado


def classificar_tipo(formato):
    formato_normalizado = str(formato or "outros").casefold()
    if "masterthesis" in formato_normalizado or "disserta" in formato_normalizado:
        return "dissertacoes"
    if "doct" in formato_normalizado or "tese" in formato_normalizado:
        return "teses"
    return "outros"


def padronizar_documento(documento):
    titulo = normalizar_texto(documento.get("titulo")) or "Sem título"
    categoria = documento.get("categoria") or classificar_tipo(documento.get("tipo"))
    categoria = categoria if categoria in CATEGORIAS else "outros"
    return {
        "id": normalizar_texto(documento.get("id")),
        "titulo": titulo,
        "titulo_normalizado": chave_normalizada(titulo),
        "tipo": normalizar_texto(documento.get("tipo", categoria)).casefold(),
        "categoria": categoria,
        "doi": normalizar_doi(documento.get("doi")),
        "arquivo": normalizar_texto(documento.get("arquivo")),
        "caminho_raw": normalizar_texto(documento.get("caminho_raw")),
        "url_origem": limpar_url(documento.get("url_origem")),
        "tamanho_bytes": documento.get("tamanho_bytes", 0),
        "sha256": normalizar_texto(documento.get("sha256")),
        "baixado_em": documento.get("baixado_em"),
    }


def carregar_staging():
    if not STAGING_PATH.exists():
        return []

    documentos = []
    with STAGING_PATH.open(encoding="utf-8") as arquivo:
        for numero, linha in enumerate(arquivo, start=1):
            if not linha.strip():
                continue
            try:
                documento = json.loads(linha)
            except json.JSONDecodeError:
                logger.warning("Registro JSON inválido no staging, linha %d", numero)
                continue
            if isinstance(documento, dict):
                documentos.append(documento)
            else:
                logger.warning("Registro ignorado no staging, linha %d não é objeto", numero)
    return documentos


def escrever_json(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def processar_catalogo():
    documentos_processados = []
    duplicatas = []
    hashes_vistos = {}
    indices_por_hash = {}

    for documento_bruto in carregar_staging():
        documento = padronizar_documento(anonimizar_documento(documento_bruto))
        hash_documento = documento["sha256"]
        duplicado_de = hashes_vistos.get(hash_documento) if hash_documento else None

        if duplicado_de:
            documento["status"] = "duplicado"
            documento["duplicado_de"] = duplicado_de
            duplicatas.append(documento)
            indice_original = indices_por_hash[hash_documento]
            original = documentos_processados[indice_original]
            if documento.get("doi") and not original.get("doi"):
                original["doi"] = documento["doi"]
        else:
            documento["status"] = "processado"
            documentos_processados.append(documento)
            if hash_documento:
                hashes_vistos[hash_documento] = documento["id"]
                indices_por_hash[hash_documento] = len(documentos_processados) - 1

        pasta = PROCESSED_DIR / (documento["id"] or "sem-id")
        pasta.mkdir(parents=True, exist_ok=True)
        escrever_json(pasta / "metadata.json", documento)

    documentos_processados.sort(key=lambda item: item["titulo"].casefold())
    duplicatas.sort(key=lambda item: item["titulo"].casefold())
    for documento in documentos_processados:
        pasta = PROCESSED_DIR / (documento["id"] or "sem-id")
        escrever_json(pasta / "metadata.json", documento)
    escrever_json(PROCESSED_CATALOG_PATH, documentos_processados)
    escrever_json(DUPLICATES_PATH, duplicatas)
    escrever_json(CATALOG_PATH, documentos_processados)

    relatorio = {
        "executado_em": datetime.now(timezone.utc).isoformat(),
        "recebidos": len(documentos_processados) + len(duplicatas),
        "processados": len(documentos_processados),
        "duplicados": len(duplicatas),
    }
    escrever_json(PROCESSED_DIR / "relatorio_pipeline.json", relatorio)
    logger.info(
        "Pipeline Processed concluído: %d válidos, %d duplicados",
        len(documentos_processados),
        len(duplicatas),
    )
    return documentos_processados
