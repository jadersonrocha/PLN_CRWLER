from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib
import json
import logging
import os
import re
import shutil
import sys
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import truststore
except ImportError:
    truststore = None

BASE_DIR = Path(__file__).resolve().parents[2]
API_DIR = BASE_DIR / "api"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from api.pipeline import processar_catalogo
except ImportError:
    if str(API_DIR) not in sys.path:
        sys.path.insert(0, str(API_DIR))
    processar_catalogo = importlib.import_module("pipeline").processar_catalogo


BDTD_API_URL = "https://bdtd.ibict.br/vufind/api/v1"
BDTD_LIMIT = int(os.getenv("BDTD_LIMIT", "30"))
BDTD_MAX_PAGES = int(os.getenv("BDTD_MAX_PAGES", "200"))
BDTD_RETRIES = int(os.getenv("BDTD_RETRIES", "3"))
SSL_INSECURE_HOSTS = {
    host.strip().casefold()
    for host in os.getenv("CRAWLER_SSL_INSECURE_HOSTS", "").split(",")
    if host.strip()
}
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/html;q=0.9",
    "Accept-Language": "pt-BR,pt;q=0.8",
}
DATA_DIR = BASE_DIR / "data"
RAW_API_DIR = DATA_DIR / "raw" / "api"
RAW_DOCUMENTS_DIR = DATA_DIR / "raw" / "documentos"
STAGING_DIR = DATA_DIR / "staging"
CURATED_DIR = DATA_DIR / "curated"
CATALOG_PATH = CURATED_DIR / "catalogo.json"
CATEGORIAS = ("dissertacoes", "teses", "outros")
LEGACY_DIRS = {
    categoria: BASE_DIR / categoria
    for categoria in CATEGORIAS
}

logger = logging.getLogger("bdtd-crawler") # 

PROGRESSO = {
    "status": "parado",
    "pagina": 0,
    "paginas_maximas": BDTD_MAX_PAGES,
    "paginas_estimadas": None,
    "total_resultados": None,
    "registros_processados": 0,
    "downloads": 0,
    "ignorados": 0,
    "falhas": 0,
}


def garantir_diretorios():
    for diretorio in (RAW_API_DIR, RAW_DOCUMENTS_DIR, STAGING_DIR, CURATED_DIR):
        diretorio.mkdir(parents=True, exist_ok=True)


def classificar_tipo(formato):
    formato_normalizado = str(formato or "outros").casefold()
    if "masterthesis" in formato_normalizado or "disserta" in formato_normalizado:
        return "dissertacoes"
    if "doct" in formato_normalizado or "tese" in formato_normalizado:
        return "teses"
    return "outros"


def identificador_documento(registro_id, titulo):
    valor = registro_id or titulo
    valor = re.sub(r"[^\w-]", "_", str(valor), flags=re.UNICODE)
    return valor[:180] or "documento"


def caminho_documento(categoria, identificador):
    pasta = RAW_DOCUMENTS_DIR / categoria
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / f"{identificador}.pdf"


def sha256(conteudo):
    return hashlib.sha256(conteudo).hexdigest()


def extrair_doi(registro):
    candidatos = [registro.get("doi"), registro.get("DOI")]
    candidatos.extend(
        item.get("url", "")
        for item in registro.get("urls", [])
        if isinstance(item, dict)
    )
    padrao = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
    for candidato in candidatos:
        correspondencia = padrao.search(str(candidato or ""))
        if correspondencia:
            return correspondencia.group(0).rstrip(".,;)").casefold()
    return None


def carregar_catalogo():
    if not CATALOG_PATH.exists():
        return []
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Catálogo curado inválido: %s", CATALOG_PATH)
        return []


def registrar_staging(documento):
    garantir_diretorios()
    registro = STAGING_DIR / "documentos.jsonl"
    with registro.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(documento, ensure_ascii=False) + "\n")


def salvar_documento(conteudo, destino, metadados):
    destino.write_bytes(conteudo)
    documento = {
        **metadados,
        "arquivo": destino.name,
        "categoria": destino.parent.name,
        "caminho_raw": str(destino.relative_to(BASE_DIR)),
        "tamanho_bytes": len(conteudo),
        "sha256": sha256(conteudo),
        "baixado_em": datetime.now(timezone.utc).isoformat(),
        "status": "valido",
    }
    registrar_staging(documento)
    return destino


def registrar_documento_existente(arquivo, metadados):
    conteudo = arquivo.read_bytes()
    documento = {
        **metadados,
        "arquivo": arquivo.name,
        "categoria": arquivo.parent.name,
        "caminho_raw": str(arquivo.relative_to(BASE_DIR)),
        "tamanho_bytes": len(conteudo),
        "sha256": sha256(conteudo),
        "baixado_em": datetime.now(timezone.utc).isoformat(),
        "status": "valido",
    }
    registrar_staging(documento)


def atualizar_doi_existente(documento, doi):
    if not doi or documento.get("doi"):
        return
    arquivo = RAW_DOCUMENTS_DIR / documento["categoria"] / documento["arquivo"]
    if not arquivo.exists():
        return
    registrar_documento_existente(arquivo, {
        "id": documento.get("id"),
        "titulo": documento.get("titulo"),
        "tipo": documento.get("tipo"),
        "doi": doi,
        "url_origem": documento.get("url_origem"),
    })
    documento["doi"] = doi


def migrar_arquivos_legados():
    garantir_diretorios()
    if carregar_catalogo():
        return

    for categoria, pasta_legada in LEGACY_DIRS.items():
        if not pasta_legada.exists():
            continue
        for arquivo_legado in pasta_legada.glob("*.pdf"):
            identificador = identificador_documento(
                f"legacy-{sha256(arquivo_legado.name.encode())[:16]}",
                arquivo_legado.stem,
            )
            destino = caminho_documento(categoria, identificador)
            if destino.exists():
                continue
            shutil.copy2(arquivo_legado, destino)
            registrar_documento_existente(destino, {
                "id": identificador,
                "titulo": arquivo_legado.stem.replace("_", " "),
                "tipo": categoria,
                "url_origem": None,
            })
            logger.info("Arquivo legado migrado: %s", arquivo_legado.name)


def baixar_documento(urls, titulo, formato, registro_id, doi, sessao, documentos_existentes):
    categoria = classificar_tipo(formato)
    identificador = identificador_documento(registro_id, titulo)
    destino = caminho_documento(categoria, identificador)

    documento_existente = next(
        (
            item for item in documentos_existentes
            if (doi and item.get("doi") == doi)
            or (not doi and item.get("id") == registro_id)
        ),
        None,
    )
    if documento_existente:
        atualizar_doi_existente(documento_existente, doi)
        logger.info("Já existe: %s", destino.name)
        PROGRESSO["ignorados"] += 1
        return None

    if destino.exists() and destino.stat().st_size > 0:
        if not doi or not any(item.get("id") == registro_id for item in documentos_existentes):
            logger.info("Já existe: %s", destino.name)
            PROGRESSO["ignorados"] += 1
            return None
        identificador = f"{identificador}-doi-{sha256(doi.encode())[:12]}"
        destino = caminho_documento(categoria, identificador)

    logger.info("Baixando: %s | tipo=%s | urls=%d", titulo, formato, len(urls))
    for url in urls:
        try:
            logger.info("Tentando URL: %s", url)
            resposta = requisitar_documento(sessao, url, (10, 30))
            resposta.raise_for_status()
            content_type = resposta.headers.get("content-type", "").lower()
            if "pdf" in content_type or resposta.content.startswith(b"%PDF"):
                salvar_documento(resposta.content, destino, {
                    "id": registro_id or identificador,
                    "titulo": titulo,
                    "tipo": formato,
                    "doi": doi,
                    "url_origem": resposta.url,
                })
                logger.info("PDF salvo: %s (%d bytes)", destino, len(resposta.content))
                PROGRESSO["downloads"] += 1
                return destino

            soup = BeautifulSoup(resposta.text, "html.parser")
            pdf_links = soup.select(
                "a[href$='.pdf'], a[href*='.pdf?'], a[href*='/download'], a[download], iframe[src*='.pdf']"
            )
            for pdf_link in pdf_links:
                pdf_url = pdf_link.get("href") or pdf_link.get("src")
                if not pdf_url:
                    continue
                pdf = requisitar_documento(
                    sessao,
                    urljoin(resposta.url, pdf_url),
                    (10, 45),
                )
                pdf.raise_for_status()
                if "pdf" in pdf.headers.get("content-type", "").lower() or pdf.content.startswith(b"%PDF"):
                    salvar_documento(pdf.content, destino, {
                        "id": registro_id or identificador,
                        "titulo": titulo,
                        "tipo": formato,
                        "doi": doi,
                        "url_origem": pdf.url,
                    })
                    logger.info("PDF salvo: %s (%d bytes)", destino, len(pdf.content))
                    PROGRESSO["downloads"] += 1
                    return destino
        except requests.RequestException as erro:
            logger.warning("Falha na URL %s: %s", url, erro)
            continue
    PROGRESSO["falhas"] += 1
    logger.warning("Download não concluído: %s", titulo)
    return None


def contar_arquivos_baixados():
    return {
        categoria: len(list((RAW_DOCUMENTS_DIR / categoria).glob("*.pdf")))
        for categoria in CATEGORIAS
    }


def imprimir_progresso(mensagem):
    print(f"[CRAWLER] {mensagem}", flush=True)


def configurar_sessao():
    if truststore is not None:
        truststore.inject_into_ssl()
    sessao = requests.Session()
    sessao.headers.update(HEADERS)
    retry = Retry(
        total=BDTD_RETRIES,
        connect=BDTD_RETRIES,
        read=BDTD_RETRIES,
        status=BDTD_RETRIES,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adaptador = HTTPAdapter(max_retries=retry)
    sessao.mount("http://", adaptador)
    sessao.mount("https://", adaptador)
    return sessao


def requisitar_documento(sessao, url, timeout):
    try:
        return sessao.get(url, timeout=timeout, allow_redirects=True)
    except requests.exceptions.SSLError:
        host = (urlsplit(url).hostname or "").casefold()
        if host not in SSL_INSECURE_HOSTS:
            raise
        logger.warning(
            "Certificado SSL inválido em %s; tentando sem validação por configuração explícita",
            host,
        )
        return sessao.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            verify=False,
        )


def buscar_registros(sessao):
    garantir_diretorios()
    pagina = 1
    total = None
    while True:
        parametros = {
            "page": pagina,
            "limit": BDTD_LIMIT,
            "lookfor": "saúde",
            "sort": "year",
            "lng": "pt-br",
            "type": "AllFields",
        }
        try:
            resposta = sessao.get(
                f"{BDTD_API_URL}/search",
                params=parametros,
                headers=HEADERS,
                timeout=(10, 60),
            )
            resposta.raise_for_status()
        except requests.RequestException as erro:
            logger.error(
                "Não foi possível consultar a página %d após %d tentativas: %s",
                pagina,
                BDTD_RETRIES + 1,
                erro,
            )
            PROGRESSO["falhas"] += 1
            PROGRESSO["status"] = "parcial"
            break
        dados = resposta.json()
        (RAW_API_DIR / f"pagina-{pagina:03d}.json").write_text(
            json.dumps(dados, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        registros = dados.get("records", [])
        total = dados.get("resultCount", total)
        PROGRESSO["pagina"] = pagina
        PROGRESSO["total_resultados"] = total
        if total is not None:
            PROGRESSO["paginas_estimadas"] = min(
                BDTD_MAX_PAGES or (total + BDTD_LIMIT - 1) // BDTD_LIMIT,
                (total + BDTD_LIMIT - 1) // BDTD_LIMIT,
            )
        logger.info("Página %d: %d registros recebidos de %s", pagina, len(registros), total)
        imprimir_progresso(
            f"Página {pagina}/{PROGRESSO['paginas_estimadas'] or BDTD_MAX_PAGES} "
            f"recebida | registros: {PROGRESSO['registros_processados']} "
            f"| downloads: {PROGRESSO['downloads']}"
        )
        yield from registros

        if not registros or BDTD_MAX_PAGES and pagina >= BDTD_MAX_PAGES:
            break
        if total is not None and pagina * BDTD_LIMIT >= total:
            break
        pagina += 1


def scrape_bdtd():
    migrar_arquivos_legados()
    documentos = []
    documentos_existentes = carregar_catalogo()
    PROGRESSO.update({
        "status": "executando",
        "pagina": 0,
        "paginas_maximas": BDTD_MAX_PAGES,
        "paginas_estimadas": None,
        "total_resultados": None,
        "registros_processados": 0,
        "downloads": 0,
        "ignorados": 0,
        "falhas": 0,
    })
    sessao = configurar_sessao()
    logger.info("Iniciando crawler: limite=%d páginas=%d", BDTD_LIMIT, BDTD_MAX_PAGES)

    for numero, registro in enumerate(buscar_registros(sessao), start=1):
        titulo = registro.get("title", "Sem título")
        formatos = registro.get("formats", [])
        formato = formatos[0] if formatos else "outros"
        doi = extrair_doi(registro)
        urls = registro.get("urls", [])
        urls_validas = [
            item.get("url") if isinstance(item, dict) else item
            for item in urls
        ]
        urls_validas = [url for url in urls_validas if url]
        if not urls_validas:
            logger.warning("Registro sem URL: id=%s título=%s", registro.get("id"), titulo)
            PROGRESSO["registros_processados"] += 1
            continue

        arquivo = baixar_documento(
            urls_validas,
            titulo,
            formato,
            registro.get("id"),
            doi,
            sessao,
            documentos_existentes,
        )
        if arquivo:
            documentos.append({
                "titulo": titulo,
                "tipo": formato,
                "doi": doi,
                "arquivo": arquivo.name,
                "id": registro.get("id"),
            })
            documentos_existentes.append({
                "id": registro.get("id"),
                "doi": doi,
            })
        PROGRESSO["registros_processados"] += 1
        logger.info("Progresso: %d registros processados, %d downloads nesta execução", numero, len(documentos))
        if numero % 10 == 0:
            imprimir_progresso(
                f"Registros: {PROGRESSO['registros_processados']} "
                f"| downloads: {PROGRESSO['downloads']} "
                f"| ignorados: {PROGRESSO['ignorados']} "
                f"| falhas: {PROGRESSO['falhas']}"
            )

    processados = processar_catalogo()
    contadores = contar_arquivos_baixados()
    logger.info(
        "Crawler finalizado: dissertações=%d teses=%d outros=%d total=%d",
        contadores["dissertacoes"],
        contadores["teses"],
        contadores["outros"],
        sum(contadores.values()),
    )
    if PROGRESSO["status"] == "executando":
        PROGRESSO["status"] = "concluido"
    imprimir_progresso(
        f"Finalizado ({PROGRESSO['status']}) | página: {PROGRESSO['pagina']} "
        f"| downloads: {PROGRESSO['downloads']} "
        f"| ignorados: {PROGRESSO['ignorados']} "
        f"| falhas: {PROGRESSO['falhas']}"
    )
    return {
        "dissertacoes": contadores["dissertacoes"],
        "teses": contadores["teses"],
        "outros": contadores["outros"],
        "documentos_total": len(processados),
        "arquivos_fisicos": sum(contadores.values()),
        "documentos": documentos,
    }


def obter_progresso():
    return dict(PROGRESSO)
