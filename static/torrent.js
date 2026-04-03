// Variáveis globais
let isListingFiles = false;
let allDownloads = [];
let isSearching = false;

document.addEventListener("DOMContentLoaded", () => {
    const downloadsContainer = document.getElementById("downloads-container");
    const form = document.getElementById("add-download-form");
    const searchInput = document.getElementById("search-input");
    const btnClearSearch = document.getElementById("btn-clear-search");
    const btnSelectAll = document.getElementById("btn-select-all");
    const btnDeselectAll = document.getElementById("btn-deselect-all");
    const btnDeleteSelected = document.getElementById("btn-delete-selected");

    // Busca em tempo real conforme o usuário digita
    searchInput.addEventListener("input", () => applySearch());

    btnClearSearch.addEventListener("click", () => {
        searchInput.value = "";
        isSearching = false;
        btnClearSearch.style.display = "none";
        btnSelectAll.style.display = "none";
        btnDeselectAll.style.display = "none";
        btnDeleteSelected.style.display = "none";
        renderDownloads(allDownloads);
    });

    btnSelectAll.addEventListener("click", () => {
        downloadsContainer.querySelectorAll("input.select-delete").forEach(cb => cb.checked = true);
    });

    btnDeselectAll.addEventListener("click", () => {
        downloadsContainer.querySelectorAll("input.select-delete").forEach(cb => cb.checked = false);
    });

    btnDeleteSelected.addEventListener("click", () => {
        const checked = downloadsContainer.querySelectorAll("input.select-delete:checked");
        if (checked.length === 0) { alert("Nenhum item selecionado."); return; }
        if (!confirm(`Excluir ${checked.length} download(s) e TODOS os arquivos baixados?`)) return;

        const ids = Array.from(checked).map(cb => cb.dataset.id);
        Promise.all(ids.map(id =>
            fetch(`/torrent/delete/${id}`, { method: "POST" }).then(r => r.json())
        )).then(() => {
            alert("Downloads excluídos.");
            isSearching = false;
            searchInput.value = "";
            btnClearSearch.style.display = "none";
            btnDeleteSelected.style.display = "none";
            fetchDownloads();
        }).catch(err => alert("Erro ao excluir: " + err.message));
    });

    function applySearch() {
        const raw = searchInput.value.trim().toLowerCase();
        if (!raw) {
            isSearching = false;
            btnClearSearch.style.display = "none";
            btnDeleteSelected.style.display = "none";
            renderDownloads(allDownloads);
            return;
        }
        isSearching = true;
        btnClearSearch.style.display = "";
        btnSelectAll.style.display = "";
        btnDeselectAll.style.display = "";
        btnDeleteSelected.style.display = "";
        const terms = raw.split(/\s+/);
        const filtered = allDownloads.filter(d =>
            terms.some(t => d.name.toLowerCase().includes(t))
        );
        renderDownloads(filtered, true);
    }

    // Função para atualizar a lista de downloads
    function fetchDownloads() {
        if (isListingFiles) return; // Pausa o fetch se estiver listando arquivos
        fetch("/torrent/downloads")
            .then((response) => response.json())
            .then((data) => {
                allDownloads = data.downloads || [];
                if (isSearching) {
                    applySearch();
                } else {
                    renderDownloads(allDownloads);
                }
            })
            .catch((err) => {
                downloadsContainer.innerHTML = `<p>Erro ao carregar downloads: ${err.message}</p>`;
                console.error(err);
            });
    }

    function renderDownloads(downloads, showCheckbox = false) {
        if (downloads && downloads.length > 0) {
            downloadsContainer.innerHTML = "";
            downloads.forEach((download) => {
                const downloadItem = document.createElement("div");
                downloadItem.className = "download-item";
                downloadItem.setAttribute("data-id", download.id);

                // Determina qual botão mostrar com base no estado do download
                let actionButton;
                if (download.state === "Paused") {
                    actionButton = `<button class="btn-resume" data-id="${download.id}">Continuar</button>`;
                } else {
                    actionButton = `<button class="btn-stop" data-id="${download.id}">Parar</button>`;
                }

                const checkboxHtml = showCheckbox
                    ? `<input type="checkbox" class="select-delete" data-id="${download.id}" title="Selecionar para excluir" />`
                    : "";

                downloadItem.innerHTML = `
                  <div class="download-header">
                      ${checkboxHtml}
                      <span>${download.name}</span>
                  </div>
                  <div class="progress-bar">
                      <div class="progress-fill" style="width: ${download.progress}%"></div>
                  </div>
                  <div>Status: ${download.state} - ${download.progress}%</div>
                  <div class="actions">
                      ${actionButton}
                      <button class="btn-cancel" data-id="${download.id}">Cancelar</button>
                      <button class="btn-delete" data-id="${download.id}">Apagar</button>
                      <button class="btn-list-files" data-id="${download.id}">Listar Arquivos</button>
                  </div>
                `;

                downloadsContainer.appendChild(downloadItem);
                addActionListeners(downloadItem);
            });
        } else {
            downloadsContainer.innerHTML = isSearching
                ? "<p>Nenhum download encontrado para a busca.</p>"
                : "<p>Nenhum download ativo no momento.</p>";
        }
    }

    // Função para listar arquivos
    function listFiles(torrentId, container) {
        isListingFiles = true; // Pausa atualizações automáticas

        fetch(`/torrent/list-files/${torrentId}`, { method: "GET" })
            .then((response) => response.json())
            .then((data) => {
                let files = data.files;
                let sortDirection = {
                    name: 'asc',
                    size: 'asc',
                };

                const convertSizeToBytes = (size) => {
                    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
                    const [value, unit] = size.split(' ');
                    const unitIndex = units.indexOf(unit);
                    return parseFloat(value) * Math.pow(1024, unitIndex);
                };

                const renderTable = () => {
                    const fileTable = `
                        <div class="files-container">
                            <h3>Selecione os arquivos para download</h3>
                            <table class="file-table">
                                <thead>
                                    <tr>
                                        <th>Baixar</th>
                                        <th data-sort="name">Nome</th>
                                        <th data-sort="size">Tamanho</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${files
                            .map(
                                (file, index) => `
                                            <tr>
                                                <td><input type="checkbox" data-index="${index}" checked></td>
                                                <td>${file.name}</td>
                                                <td>${file.size}</td>
                                            </tr>`
                            )
                            .join("")}
                                </tbody>
                            </table>
                            <button class="btn-save-files">Salvar</button>
                            <button class="btn-close-files">Cancelar</button>
                        </div>
                    `;

                    container.innerHTML = fileTable;

                    // Adicionar eventos de ordenação
                    container.querySelectorAll("th[data-sort]").forEach((header) => {
                        header.addEventListener("click", () => {
                            const sortKey = header.getAttribute("data-sort");
                            const direction = sortDirection[sortKey] === 'asc' ? 1 : -1;

                            files.sort((a, b) => {
                                if (sortKey === 'size') {
                                    return direction * (convertSizeToBytes(a[sortKey]) - convertSizeToBytes(b[sortKey]));
                                } else {
                                    return direction * a[sortKey].localeCompare(b[sortKey]);
                                }
                            });

                            sortDirection[sortKey] = sortDirection[sortKey] === 'asc' ? 'desc' : 'asc';
                            renderTable(); // Re-renderiza a tabela após ordenar
                        });
                    });

                    // Evento para fechar sem salvar
                    container.querySelector(".btn-close-files").addEventListener("click", () => {
                        isListingFiles = false; // Retoma atualizações automáticas
                        container.innerHTML = ""; // Limpa a tabela
                        fetchDownloads(); // Atualiza os downloads
                    });

                    // Evento para salvar seleções
                    container.querySelector(".btn-save-files").addEventListener("click", () => {
                        // Gera o dicionário com base nos checkboxes
                        const fileSelections = {};
                        container.querySelectorAll("input[type=checkbox]").forEach((checkbox) => {
                            const index = checkbox.getAttribute("data-index");
                            fileSelections[files[index].name] = checkbox.checked;
                        });

                        console.log("Arquivo selecionado para download:", fileSelections);

                        // Envia fileSelections para o servidor
                        fetch(`/torrent/cancel-files/${torrentId}`, {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                            },
                            body: JSON.stringify({ file_selections: fileSelections }),
                        })
                            .then((response) => {
                                if (!response.ok) {
                                    throw new Error("Erro ao enviar seleção de arquivos");
                                }
                                return response.json();
                            })
                            .then((data) => {
                                console.log("Resposta do servidor:", data);
                                alert("Seleção de arquivos aplicada com sucesso!");
                            })
                            .catch((err) => {
                                console.error("Erro ao enviar seleção de arquivos:", err);
                                alert("Erro ao aplicar seleção: " + err.message);
                            });

                        isListingFiles = false; // Retoma atualizações automáticas
                        container.innerHTML = ""; // Limpa a tabela
                        fetchDownloads(); // Atualiza os downloads
                    });
                };

                renderTable();
            })
            .catch((err) => {
                console.error(err);
                alert("Erro ao listar arquivos: " + err.message);
                isListingFiles = false;
                container.innerHTML = "";
                fetchDownloads();
            });
    }

    // Adiciona listeners aos botões de ação
    function addActionListeners(downloadItem) {
        const torrentId = downloadItem.dataset.id;

        // Botão Parar (se presente)
        const stopButton = downloadItem.querySelector(".btn-stop");
        if (stopButton) {
            stopButton.addEventListener("click", () => {
                fetch(`/torrent/stop/${torrentId}`, { method: "POST" })
                    .then((response) => response.json())
                    .then((data) => {
                        alert(data.message);
                        fetchDownloads(); // Atualiza os downloads após parar
                    })
                    .catch((err) => console.error(err));
            });
        }

        // Botão Continuar (se presente)
        const resumeButton = downloadItem.querySelector(".btn-resume");
        if (resumeButton) {
            resumeButton.addEventListener("click", () => {
                fetch(`/torrent/resume/${torrentId}`, { method: "POST" })
                    .then((response) => response.json())
                    .then((data) => {
                        alert(data.message);
                        fetchDownloads(); // Atualiza os downloads após continuar
                    })
                    .catch((err) => console.error(err));
            });
        }

        // Botão Cancelar
        downloadItem
            .querySelector(".btn-cancel")
            .addEventListener("click", () => {
                if (confirm("Tem certeza que deseja cancelar este download? Os arquivos baixados serão mantidos.")) {
                    fetch(`/torrent/cancel/${torrentId}`, { method: "POST" })
                        .then((response) => response.json())
                        .then((data) => {
                            alert(data.message);
                            fetchDownloads(); // Atualiza os downloads após cancelar
                        })
                        .catch((err) => console.error(err));
                }
            });

        // Botão Apagar
        downloadItem
            .querySelector(".btn-delete")
            .addEventListener("click", () => {
                if (confirm("Tem certeza que deseja apagar este download e TODOS os arquivos já baixados?")) {
                    fetch(`/torrent/delete/${torrentId}`, { method: "POST" })
                        .then((response) => response.json())
                        .then((data) => {
                            alert(data.message);
                            fetchDownloads(); // Atualiza os downloads após apagar
                        })
                        .catch((err) => console.error(err));
                }
            });

        // Botão Listar Arquivos
        downloadItem
            .querySelector(".btn-list-files")
            .addEventListener("click", () => {
                const container = downloadItem.querySelector(".actions");
                listFiles(torrentId, container);
            });
    }

    // Manipula o envio do formulário para adicionar novo download
    form.addEventListener("submit", (event) => {
        event.preventDefault(); // Impede o comportamento padrão do formulário
        const magnetLink = document.getElementById("magnet_link").value;

        const formData = new FormData(); // Cria um FormData
        formData.append("magnet_link", magnetLink); // Adiciona o magnet link

        fetch("/torrent/", {
            method: "POST",
            body: formData, // Envia o FormData como corpo da requisição
        })
            .then((response) => {
                if (response.ok) {
                    // Se a resposta foi bem-sucedida, atualiza a lista de downloads
                    alert("Download adicionado com sucesso!");
                    document.getElementById("magnet_link").value = ""; // Limpa o campo de entrada
                    fetchDownloads(); // Atualiza a lista de downloads
                } else {
                    return response.text().then((text) => {
                        throw new Error(text || "Erro ao adicionar o download.");
                    });
                }
            })
            .catch((err) => {
                console.error(err);
                alert("Erro: " + err.message);
            });
    });

    // Atualiza a lista de downloads a cada 5 segundos
    setInterval(fetchDownloads, 5000);

    // Carrega os downloads inicialmente
    fetchDownloads();
});

// Função para buscar e atualizar informações de armazenamento
function updateStorageInfo() {
    fetch('/torrent/storage')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Erro ao obter armazenamento:', data.error);
                document.getElementById('storage-used').textContent = 'Erro';
                document.getElementById('storage-total').textContent = 'N/A';
                document.getElementById('storage-percent').textContent = '0';
                document.getElementById('storage-free').textContent = 'N/A';
                return;
            }

            // Atualizar textos
            document.getElementById('storage-used').textContent = `${data.used} GB`;
            document.getElementById('storage-total').textContent = `${data.total} GB`;
            document.getElementById('storage-percent').textContent = data.percent.toFixed(1);
            document.getElementById('storage-free').textContent = `${data.free} GB`;

            // Atualizar barra de progresso
            const storageBar = document.getElementById('storage-bar');
            storageBar.style.width = `${data.percent}%`;

            // Mudar cor baseado na porcentagem
            storageBar.classList.remove('low', 'medium', 'high');
            if (data.percent < 60) {
                storageBar.classList.add('low');
            } else if (data.percent < 85) {
                storageBar.classList.add('medium');
            } else {
                storageBar.classList.add('high');
            }
        })
        .catch(error => {
            console.error('Erro ao buscar informações de armazenamento:', error);
        });
}

// Atualizar informações de armazenamento ao carregar a página
document.addEventListener('DOMContentLoaded', function () {
    updateStorageInfo();

    // Atualizar a cada 30 segundos
    setInterval(updateStorageInfo, 30000);
});