document.addEventListener("DOMContentLoaded", () => {
  let currentPath = "";

  const messagesDiv = document.getElementById("messages");
  const navigationDiv = document.getElementById("navigation");
  const filesTableBody = document.querySelector("#files-table tbody");
  const uploadForm = document.getElementById("upload-form");
  const createFolderForm = document.getElementById("create-folder-form");
  const searchForm = document.getElementById("search-form");
  const searchInput = document.getElementById("search-input");
  const deleteSelectedBtn = document.getElementById("delete-selected-btn");
  const selectAllCheckbox = document.getElementById("select-all");

  // Função para exibir mensagens
  function showMessage(message, isError = false) {
    const msg = document.createElement("div");
    msg.className = isError ? "error-message" : "success-message";
    msg.innerHTML = isError
      ? `<i class="fas fa-exclamation-circle"></i> ${message}`
      : `<i class="fas fa-check-circle"></i> ${message}`;
    messagesDiv.appendChild(msg);
    setTimeout(() => {
      msg.remove();
    }, 5000);
  }

  // Função para atualizar a navegação
  function updateNavigation() {
    navigationDiv.innerHTML = "";
    const pathParts = currentPath.split("/").filter((part) => part);
    let pathAccumulator = "";
    const backLink = document.createElement("a");
    backLink.href = "#";
    backLink.innerText = "Início";
    backLink.addEventListener("click", (e) => {
      e.preventDefault();
      currentPath = "";
      loadDirectory();
    });
    navigationDiv.appendChild(backLink);

    pathParts.forEach((part, index) => {
      navigationDiv.appendChild(document.createTextNode(" / "));
      pathAccumulator += part + "/";
      const link = document.createElement("a");
      link.href = "#";
      link.innerText = part;
      link.addEventListener("click", (e) => {
        e.preventDefault();
        currentPath = pathAccumulator.slice(0, -1);
        loadDirectory();
      });
      navigationDiv.appendChild(link);
    });
  }

  // Função para carregar o diretório atual
  function loadDirectory() {
    fetch(`/filemanager/api/list?path=${encodeURIComponent(currentPath)}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.type === "folder") {
          updateNavigation();
          renderFiles(data.items);
        } else {
          // Se for um arquivo, iniciar download
          window.location.href = `/download/${encodeURIComponent(currentPath)}`;
        }
      })
      .catch((error) => {
        showMessage("Erro ao carregar diretório", true);
        console.error(error);
      });
  }

  // Função para renderizar arquivos e pastas na tabela
  function renderFiles(items) {
    filesTableBody.innerHTML = "";

    // Adicionar link para voltar se não estivermos na raiz
    if (currentPath) {
      const row = document.createElement("tr");

      const checkboxCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.disabled = true; // Não permitir seleção deste item
      checkboxCell.appendChild(checkbox);
      row.appendChild(checkboxCell);

      const nameCell = document.createElement("td");
      const link = document.createElement("a");
      link.href = "#";
      link.innerHTML = '<i class="fas fa-arrow-left icon"></i> ..';
      link.addEventListener("click", (e) => {
        e.preventDefault();
        const parts = currentPath.split("/").filter((part) => part);
        parts.pop();
        currentPath = parts.join("/");
        loadDirectory();
      });
      nameCell.appendChild(link);
      row.appendChild(nameCell);

      filesTableBody.appendChild(row);
    }

    items.forEach((item) => {
      const row = document.createElement("tr");

      const checkboxCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "select-item";
      checkbox.value = item.name;
      checkboxCell.appendChild(checkbox);
      row.appendChild(checkboxCell);

      const nameCell = document.createElement("td");
      if (item.type === "folder") {
        const link = document.createElement("a");
        link.href = "#";
        link.innerHTML = `<i class="fas fa-folder icon"></i>${item.name}/`;
        link.addEventListener("click", (e) => {
          e.preventDefault();
          currentPath = currentPath ? `${currentPath}/${item.name}` : item.name;
          loadDirectory();
        });
        nameCell.appendChild(link);
      } else {
        const link = document.createElement("a");
        link.href = `/download/${encodeURIComponent(
          currentPath ? currentPath + "/" + item.name : item.name
        )}`;
        link.innerHTML = `<i class="fas fa-file icon"></i>${item.name}`;
        link.target = "_blank";
        nameCell.appendChild(link);
      }
      row.appendChild(nameCell);

      filesTableBody.appendChild(row);
    });

    // Resetar o checkbox "Selecionar Todos"
    selectAllCheckbox.checked = false;
  }

  // Função para deletar itens selecionados
  function deleteSelectedItems() {
    const selectedCheckboxes = document.querySelectorAll(
      ".select-item:checked"
    );
    if (selectedCheckboxes.length === 0) {
      showMessage("Nenhum item selecionado para deletar.", true);
      return;
    }

    const targets = Array.from(selectedCheckboxes).map((cb) => cb.value);

    if (
      !confirm(
        `Tem certeza que deseja deletar os itens selecionados: ${targets.join(
          ", "
        )}?`
      )
    ) {
      return;
    }

    fetch("/filemanager/api/delete_multiple", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        current_path: currentPath,
        targets: targets,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          showMessage(data.message);
          loadDirectory();
        } else {
          showMessage(data.message, true);
        }
      })
      .catch((error) => {
        showMessage("Erro ao deletar itens selecionados.", true);
        console.error(error);
      });
  }

  // Manipulador de envio do formulário de upload
  uploadForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const fileInput = document.getElementById("file-input");
    const files = fileInput.files;
    if (!files.length) {
      showMessage("Selecione pelo menos um arquivo para upload", true);
      return;
    }

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
    }
    formData.append("current_path", currentPath);

    fetch("/filemanager/api/upload", {
      method: "POST",
      body: formData,
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          showMessage(data.message);
          uploadForm.reset();
          loadDirectory();
        } else {
          showMessage(data.message, true);
        }
      })
      .catch((error) => {
        showMessage("Erro ao fazer upload", true);
        console.error(error);
      });
  });

  // Manipulador de envio do formulário de criação de pasta
  createFolderForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const folderNameInput = document.getElementById("folder-name-input");
    const folderName = folderNameInput.value.trim();
    if (!folderName) {
      showMessage("Digite um nome para a pasta", true);
      return;
    }

    const formData = new FormData();
    formData.append("folder_name", folderName);
    formData.append("current_path", currentPath);

    fetch("/filemanager/api/create_folder", {
      method: "POST",
      body: formData,
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          showMessage(data.message);
          createFolderForm.reset();
          loadDirectory();
        } else {
          showMessage(data.message, true);
        }
      })
      .catch((error) => {
        showMessage("Erro ao criar pasta", true);
        console.error(error);
      });
  });

  // Manipulador de envio do formulário de pesquisa
  searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = searchInput.value.trim();
    if (!query) {
      showMessage("Digite algo para pesquisar", true);
      return;
    }

    fetch(`/filemanager/api/search?q=${encodeURIComponent(query)}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          renderSearchResults(data.results);
        } else {
          showMessage(data.message, true);
        }
      })
      .catch((error) => {
        showMessage("Erro ao realizar pesquisa", true);
        console.error(error);
      });
  });

  // Função para renderizar resultados de pesquisa
  function renderSearchResults(results) {
    filesTableBody.innerHTML = "";

    if (results.length === 0) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 2;
      cell.innerText = "Nenhum resultado encontrado.";
      row.appendChild(cell);
      filesTableBody.appendChild(row);
      return;
    }

    results.forEach((item) => {
      const row = document.createElement("tr");

      const checkboxCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "select-item";
      checkbox.value = item.name;
      checkboxCell.appendChild(checkbox);
      row.appendChild(checkboxCell);

      const nameCell = document.createElement("td");
      if (item.type === "folder") {
        const link = document.createElement("a");
        link.href = "#";
        link.innerHTML = `<i class="fas fa-folder icon"></i>${item.name}/`;
        link.addEventListener("click", (e) => {
          e.preventDefault();
          currentPath = item.path;
          loadDirectory();
        });
        nameCell.appendChild(link);
      } else {
        const link = document.createElement("a");
        link.href = `/download/${encodeURIComponent(item.path)}`;
        link.innerHTML = `<i class="fas fa-file icon"></i>${item.name}`;
        link.target = "_blank";
        nameCell.appendChild(link);
      }
      row.appendChild(nameCell);

      filesTableBody.appendChild(row);
    });

    // Resetar o checkbox "Selecionar Todos"
    selectAllCheckbox.checked = false;
  }

  // Função para deletar itens selecionados
  function deleteSelectedItems() {
    const selectedCheckboxes = document.querySelectorAll(
      ".select-item:checked"
    );
    if (selectedCheckboxes.length === 0) {
      showMessage("Nenhum item selecionado para deletar.", true);
      return;
    }

    const targets = Array.from(selectedCheckboxes).map((cb) => cb.value);

    if (
      !confirm(
        `Tem certeza que deseja deletar os itens selecionados: ${targets.join(
          ", "
        )}?`
      )
    ) {
      return;
    }

    fetch("/filemanager/api/delete_multiple", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        current_path: currentPath,
        targets: targets,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          showMessage(data.message);
          loadDirectory();
        } else {
          showMessage(data.message, true);
        }
      })
      .catch((error) => {
        showMessage("Erro ao deletar itens selecionados.", true);
        console.error(error);
      });
  }

  // Adicionar evento ao botão "Deletar Selecionados"
  deleteSelectedBtn.addEventListener("click", deleteSelectedItems);

  // Adicionar evento ao checkbox "Selecionar Todos"
  selectAllCheckbox.addEventListener("change", (e) => {
    const isChecked = e.target.checked;
    const itemCheckboxes = document.querySelectorAll(".select-item");
    itemCheckboxes.forEach((cb) => {
      cb.checked = isChecked;
    });
  });

  // Carrega o diretório inicial
  loadDirectory();
});
