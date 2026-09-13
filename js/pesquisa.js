function exibirDados(dados) {
    document.getElementById("dissertacoes").textContent = dados.dissertacoes.toLocaleString("pt-BR");
    document.getElementById("teses").textContent = dados.teses.toLocaleString("pt-BR");
    const totalDocumentos = dados.documentos_total ?? dados.dissertacoes + dados.teses + dados.outros;
    document.getElementById("documentos").textContent = totalDocumentos.toLocaleString("pt-BR");

    const lista = document.getElementById("lista-documentos");
    document.querySelector(".resultados").style.display = "block";
    lista.innerHTML = "";
    dados.documentos.forEach((documento) => {
        const item = document.createElement("li");
        item.textContent = `${documento.titulo} (${documento.tipo})`;
        lista.appendChild(item);
    });
}

let documentosDisponiveis = [];

function exibirCorrespondencias(termo) {
    const resultados = document.querySelector(".resultados");
    const lista = document.getElementById("lista-documentos");
    const busca = termo.trim().toLowerCase();

    if (!busca) {
        resultados.style.display = "none";
        lista.innerHTML = "";
        return;
    }

    const correspondencias = documentosDisponiveis.filter((documento) =>
        documento.nome.toLowerCase().includes(busca)
    );
    resultados.style.display = "block";
    lista.innerHTML = "";

    if (!correspondencias.length) {
        lista.innerHTML = "<li>Nenhum documento baixado corresponde à busca.</li>";
        return;
    }

    correspondencias.forEach((documento) => {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = `http://localhost:5000${documento.url}`;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = `${documento.nome} (${documento.categoria})`;
        item.appendChild(link);
        lista.appendChild(item);
    });
}

const dadosSalvos = localStorage.getItem("bdtd-dados-v2");
if (dadosSalvos) {
    try {
        exibirDados(JSON.parse(dadosSalvos));
    } catch (erro) {
        localStorage.removeItem("bdtd-dados-v2");
    }
}

async function atualizarContadores() {
    const resposta = await fetch("http://localhost:5000/api/contadores");
    if (!resposta.ok) {
        const erro = await resposta.json().catch(() => ({}));
        throw new Error(erro.erro || `API respondeu com status ${resposta.status}`);
    }

    const dados = await resposta.json();
    exibirDados({ ...dados, documentos: [] });
    localStorage.setItem("bdtd-dados-v2", JSON.stringify({ ...dados, documentos: [] }));
}

async function carregarDocumentosParaBusca() {
    const resposta = await fetch("http://localhost:5000/api/documentos");
    if (!resposta.ok) {
        throw new Error(`API de documentos respondeu com status ${resposta.status}`);
    }
    const dados = await resposta.json();
    documentosDisponiveis = dados.documentos;
}

document.getElementById("termo-busca").addEventListener("input", (evento) => {
    exibirCorrespondencias(evento.target.value);
});

Promise.all([atualizarContadores(), carregarDocumentosParaBusca()]).catch((erro) => {
    console.error("Não foi possível atualizar os contadores:", erro);
    const resultados = document.querySelector(".resultados");
    const lista = document.getElementById("lista-documentos");
    resultados.style.display = "block";
    lista.innerHTML = `<li>${erro.message}</li>`;
});

