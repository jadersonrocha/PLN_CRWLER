from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import re

try:
	from pypdf import PdfReader
except ImportError as erro:
	PdfReader = None
	PDF_IMPORT_ERROR = erro


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
PROCESSED_CATALOG_PATH = DATA_DIR / "processed" / "catalogo_processado.json"
RAW_DOCUMENTS_DIR = DATA_DIR / "raw" / "documentos"
CURATED_DIR = DATA_DIR / "curated"
TEXTS_DIR = CURATED_DIR / "texts"
PRETRAINING_DIR = CURATED_DIR / "pretraining"
FINETUNING_DIR = CURATED_DIR / "finetuning"
RAG_DIR = CURATED_DIR / "rag"
VERSION = "curated-v1"
CHUNK_SIZE = 2400
CHUNK_OVERLAP = 300
CURATOR_MAX_DOCUMENTS = int(os.getenv("CURATOR_MAX_DOCUMENTS", "0"))
logger = logging.getLogger("bdtd-curator")


def escrever_json(caminho, dados):
	caminho.parent.mkdir(parents=True, exist_ok=True)
	caminho.write_text(
		json.dumps(dados, ensure_ascii=False, indent=2),
		encoding="utf-8",
	)


def escrever_jsonl(caminho, registros):
	caminho.parent.mkdir(parents=True, exist_ok=True)
	with caminho.open("w", encoding="utf-8") as arquivo:
		for registro in registros:
			arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")


def normalizar_texto(texto):
	texto = str(texto or "")
	texto = re.sub(r"[ \t]+", " ", texto)
	texto = re.sub(r"\n{3,}", "\n\n", texto)
	return "\n".join(linha.strip() for linha in texto.splitlines()).strip()


def carregar_catalogo():
	if not PROCESSED_CATALOG_PATH.exists():
		return []
	return json.loads(PROCESSED_CATALOG_PATH.read_text(encoding="utf-8"))


def caminho_pdf(documento):
	caminho = documento.get("caminho_raw", "").replace("\\", "/")
	return BASE_DIR / caminho


def extrair_paginas(caminho):
	if PdfReader is None:
		raise RuntimeError(
			"Instale pypdf no ambiente virtual: python -m pip install pypdf"
		) from PDF_IMPORT_ERROR
	leitor = PdfReader(str(caminho), strict=False)
	paginas = []
	for numero, pagina in enumerate(leitor.pages, start=1):
		try:
			texto = normalizar_texto(pagina.extract_text() or "")
		except Exception as erro:
			logger.warning(
				"Falha na página %d de %s: %s",
				numero,
				caminho.name,
				erro,
			)
			continue
		if texto:
			paginas.append({"pagina": numero, "texto": texto})
	return paginas


def gerar_chunks(paginas):
	chunks = []
	for pagina in paginas:
		texto = pagina["texto"]
		inicio = 0
		while inicio < len(texto):
			fim = min(inicio + CHUNK_SIZE, len(texto))
			trecho = texto[inicio:fim].strip()
			if trecho:
				chunks.append({
					"pagina_inicio": pagina["pagina"],
					"pagina_fim": pagina["pagina"],
					"texto": trecho,
				})
			if fim == len(texto):
				break
			inicio = fim - CHUNK_OVERLAP
	return chunks


def split_documento(document_id):
	valor = int(hashlib.sha256(document_id.encode()).hexdigest(), 16) % 100
	if valor < 80:
		return "train"
	if valor < 90:
		return "validation"
	return "test"


def processar_documento(documento):
	caminho = caminho_pdf(documento)
	if not caminho.exists():
		return None, "arquivo_inexistente"
	cache = TEXTS_DIR / f"{documento['id']}.json"
	if cache.exists():
		try:
			registro = json.loads(cache.read_text(encoding="utf-8"))
			if registro.get("sha256") == documento.get("sha256"):
				paginas = registro.get("paginas", [])
				return {
					"metadados": {
						chave: registro.get(chave)
						for chave in (
							"document_id", "titulo", "categoria", "doi",
							"sha256", "arquivo", "versao",
						)
					},
					"texto": registro.get("texto", ""),
					"chunks": gerar_chunks(paginas),
				}, None
		except (OSError, json.JSONDecodeError):
			logger.warning("Cache inválido, reprocessando %s", documento.get("id"))
	try:
		paginas = extrair_paginas(caminho)
	except Exception as erro:
		logger.warning("Falha ao extrair %s: %s", documento.get("id"), erro)
		return None, "falha_extracao"
	if not paginas:
		return None, "sem_texto"

	document_id = documento["id"]
	texto = "\n\n".join(pagina["texto"] for pagina in paginas)
	chunks = gerar_chunks(paginas)
	metadados = {
		"document_id": document_id,
		"titulo": documento.get("titulo"),
		"categoria": documento.get("categoria"),
		"doi": documento.get("doi"),
		"sha256": documento.get("sha256"),
		"arquivo": documento.get("arquivo"),
		"versao": VERSION,
	}
	registro_texto = {**metadados, "paginas": paginas, "texto": texto}
	escrever_json(TEXTS_DIR / f"{document_id}.json", registro_texto)
	return {"metadados": metadados, "texto": texto, "chunks": chunks}, None


def gerar_datasets():
	if not PROCESSED_CATALOG_PATH.exists():
		raise FileNotFoundError(PROCESSED_CATALOG_PATH)

	textos = []
	chunks_saida = []
	classificacao = []
	qa_pendente = []
	falhas = []

	documentos = carregar_catalogo()
	if CURATOR_MAX_DOCUMENTS:
		documentos = documentos[:CURATOR_MAX_DOCUMENTS]

	for numero, documento in enumerate(documentos, start=1):
		resultado, motivo = processar_documento(documento)
		if resultado is None:
			falhas.append({"document_id": documento.get("id"), "motivo": motivo})
			print(
				f"[CURATOR] {numero}/{len(documentos)} | falha: {motivo}",
				flush=True,
			)
			continue

		metadados = resultado["metadados"]
		split = split_documento(metadados["document_id"])
		textos.append({**metadados, "text": resultado["texto"], "split": split})
		classificacao.append({
			"id": f"classificacao-{metadados['document_id']}",
			"text": metadados["titulo"],
			"label": metadados["categoria"],
			"document_id": metadados["document_id"],
			"split": split,
		})
		for chunk_numero, chunk in enumerate(resultado["chunks"], start=1):
			chunks_saida.append({
				"chunk_id": f"{metadados['document_id']}-chunk-{chunk_numero:04d}",
				"document_id": metadados["document_id"],
				"text": chunk["texto"],
				"metadata": {
					**metadados,
					"pagina_inicio": chunk["pagina_inicio"],
					"pagina_fim": chunk["pagina_fim"],
					"split": split,
				},
			})
			qa_pendente.append({
				"id": f"qa-{metadados['document_id']}-{chunk_numero:04d}",
				"question": "",
				"context": chunk["texto"],
				"answer": "",
				"document_id": metadados["document_id"],
				"chunk_id": f"{metadados['document_id']}-chunk-{chunk_numero:04d}",
				"status": "needs_annotation",
				"split": split,
			})
		if numero % 10 == 0 or numero == len(documentos):
			print(
				f"[CURATOR] {numero}/{len(documentos)} | "
				f"documentos: {len(textos)} | chunks: {len(chunks_saida)}",
				flush=True,
			)

	escrever_jsonl(PRETRAINING_DIR / "corpus.jsonl", textos)
	escrever_jsonl(
		PRETRAINING_DIR / "train.jsonl",
		[item for item in textos if item["split"] == "train"],
	)
	escrever_jsonl(
		PRETRAINING_DIR / "validation.jsonl",
		[item for item in textos if item["split"] == "validation"],
	)
	escrever_jsonl(RAG_DIR / "documentos.jsonl", textos)
	escrever_jsonl(RAG_DIR / "chunks.jsonl", chunks_saida)
	escrever_jsonl(FINETUNING_DIR / "classificacao.jsonl", classificacao)
	escrever_jsonl(FINETUNING_DIR / "qa.jsonl", qa_pendente)

	manifest = {
		"versao": VERSION,
		"gerado_em": datetime.now(timezone.utc).isoformat(),
		"documentos_catalogo": len(carregar_catalogo()),
		"documentos_solicitados": len(documentos),
		"documentos_com_texto": len(textos),
		"chunks": len(chunks_saida),
		"classificacao": len(classificacao),
		"qa_needs_annotation": len(qa_pendente),
		"falhas": len(falhas),
		"splits": {
			nome: sum(1 for item in textos if item["split"] == nome)
			for nome in ("train", "validation", "test")
		},
	}
	escrever_json(CURATED_DIR / "manifest.json", manifest)
	escrever_json(CURATED_DIR / "falhas_curadoria.json", falhas)
	return manifest


if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
	print(json.dumps(gerar_datasets(), ensure_ascii=False, indent=2))
