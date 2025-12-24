(function() {
    // Helper to get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    class ReferenciasManager {
        constructor(container, pvId) {
            this.container = container;
            this.pvId = pvId;
            this.elements = {
                body: container.querySelector('.vb-refs-body'),
                addBtn: container.querySelector('.vb-ref-add'),
                urlInp: container.querySelector('.vb-ref-url'),
                kindSel: container.querySelector('.vb-ref-kind'),
                tableBody: container.querySelector('.vb-refs-table tbody'),
                statusEl: container.querySelector('.vb-refs-status')
            };

            this.init();
        }

        init() {
            this.bindEvents();
            this.loadReferences();
        }

        bindEvents() {
            if (this.elements.addBtn) {
                this.elements.addBtn.addEventListener('click', () => this.createReference());
            }
            // Bind Enter key on input
            if (this.elements.urlInp) {
                this.elements.urlInp.addEventListener('keyup', (e) => {
                    if (e.key === 'Enter') this.createReference();
                });
            }
        }

        loadReferences() {
            this.elements.statusEl.textContent = 'Carregando referências...';
            fetch(`/gerencial/ajax/referencias/list/?pv_id=${encodeURIComponent(this.pvId)}`, { 
                headers: { 'Accept': 'application/json' } 
            })
            .then(r => r.json())
            .then(json => {
                if (!json?.ok) { 
                    this.elements.statusEl.textContent = json?.error || 'Falha ao carregar.'; 
                    return; 
                }
                const count = (json.dados || []).length;
                this.elements.statusEl.textContent = count === 0 ? 'Nenhuma referência cadastrada.' : `${count} referência(s).`;
                this.renderRows(json.dados || []);
            })
            .catch(e => { 
                console.error(e);
                this.elements.statusEl.textContent = 'Erro de rede ao carregar referências.'; 
            });
        }

        createReference() {
            const url = (this.elements.urlInp.value || '').trim();
            const kind = this.elements.kindSel.value || 'web_page';

            if (!url) { 
                this.elements.statusEl.textContent = 'Informe uma URL válida.'; 
                return; 
            }

            const formData = new URLSearchParams();
            formData.append('pv_id', this.pvId);
            formData.append('url', url);
            formData.append('kind', kind);

            this.elements.statusEl.textContent = 'Adicionando...';

            fetch(`/gerencial/ajax/referencias/create/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': getCookie('csrftoken') || ''
                },
                body: formData.toString(),
                credentials: 'same-origin'
            })
            .then(r => r.json())
            .then(json => {
                if (!json?.ok) { 
                    this.elements.statusEl.textContent = json?.error || 'Falha ao criar referência.'; 
                    return; 
                }
                this.elements.urlInp.value = '';
                this.elements.kindSel.value = 'web_page';
                this.elements.statusEl.textContent = 'Referência adicionada.';
                this.appendRow(json.ref);
                
                // Refresh count text
                const currentCount = this.elements.tableBody.children.length;
                this.elements.statusEl.textContent = `${currentCount} referência(s).`;
            })
            .catch(e => { 
                console.error(e);
                this.elements.statusEl.textContent = 'Erro de rede ao criar referência.'; 
            });
        }

        renderRows(refs) {
            this.elements.tableBody.innerHTML = '';
            refs.forEach(r => this.appendRow(r));
        }

        appendRow(r) {
            const tr = document.createElement('tr');
            const esc = (s) => String(s || '').replace(/"/g, '&quot;');
            
            tr.innerHTML = `
                <td style="padding:6px;">
                    <input type="url" class="form-control form-control-sm vb-ref-url-edit" value="${esc(r.url)}" data-ref-id="${r.id}">
                </td>
                <td style="padding:6px;">
                    <select class="form-select form-select-sm vb-ref-kind-edit" data-ref-id="${r.id}">
                        <option value="web_page" ${r.kind === 'web_page' ? 'selected' : ''}>Página Web</option>
                        <option value="sound" ${r.kind === 'sound' ? 'selected' : ''}>Áudio</option>
                        <option value="social_media" ${r.kind === 'social_media' ? 'selected' : ''}>Vídeo no YouTube</option>
                    </select>
                </td>
                <td style="padding:6px;">
                    <button type="button" class="btn btn-sm btn-success vb-ref-save" data-ref-id="${r.id}" title="Salvar alterações"><i class="bi bi-check"></i> Salvar</button>
                    <button type="button" class="btn btn-sm btn-outline-danger vb-ref-del" data-ref-id="${r.id}" title="Excluir"><i class="bi bi-trash"></i> Excluir</button>
                </td>
            `;
            
            // Insert at top (descending order)
            if (this.elements.tableBody.firstChild) {
                this.elements.tableBody.insertBefore(tr, this.elements.tableBody.firstChild);
            } else {
                this.elements.tableBody.appendChild(tr);
            }
            
            this.bindRowActions(tr);
        }

        bindRowActions(tr) {
            const saveBtn = tr.querySelector('.vb-ref-save');
            const delBtn = tr.querySelector('.vb-ref-del');
            
            saveBtn.addEventListener('click', () => this.updateReference(tr, saveBtn));
            delBtn.addEventListener('click', () => this.deleteReference(tr, delBtn));
        }

        updateReference(tr, btn) {
            const refId = btn.getAttribute('data-ref-id');
            const urlInp = tr.querySelector('.vb-ref-url-edit');
            const kindSel = tr.querySelector('.vb-ref-kind-edit');
            
            const formData = new URLSearchParams();
            formData.append('ref_id', refId);
            formData.append('url', (urlInp.value || '').trim());
            formData.append('kind', kindSel.value || 'web_page');

            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';

            fetch(`/gerencial/ajax/referencias/update/`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/x-www-form-urlencoded', 
                    'X-CSRFToken': getCookie('csrftoken') || '' 
                },
                body: formData.toString(),
                credentials: 'same-origin'
            })
            .then(r => r.json())
            .then(json => {
                if (!json?.ok) { 
                    alert(json?.error || 'Falha ao salvar.'); 
                    return; 
                }
                // Visual feedback
                const prevClass = btn.className;
                btn.className = 'btn btn-sm btn-success'; // Ensure success color
                setTimeout(() => btn.className = prevClass, 1000);
            })
            .catch(e => { 
                console.error(e);
                alert('Erro de rede ao salvar.'); 
            })
            .finally(() => {
                btn.disabled = false;
                btn.innerHTML = originalText;
            });
        }

        deleteReference(tr, btn) {
            const refId = btn.getAttribute('data-ref-id');
            if (!confirm('Tem certeza que deseja excluir esta referência?')) return;

            btn.disabled = true;

            const formData = new URLSearchParams();
            formData.append('ref_id', refId);

            fetch(`/gerencial/ajax/referencias/delete/`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/x-www-form-urlencoded', 
                    'X-CSRFToken': getCookie('csrftoken') || '' 
                },
                body: formData.toString(),
                credentials: 'same-origin'
            })
            .then(r => r.json())
            .then(json => {
                if (!json?.ok) { 
                    alert(json?.error || 'Falha ao excluir.'); 
                    btn.disabled = false;
                    return; 
                }
                tr.remove();
                
                // Refresh count text
                const currentCount = this.elements.tableBody.children.length;
                this.elements.statusEl.textContent = currentCount === 0 ? 'Nenhuma referência cadastrada.' : `${currentCount} referência(s).`;
            })
            .catch(e => { 
                console.error(e);
                alert('Erro de rede ao excluir.'); 
                btn.disabled = false;
            });
        }
    }

    // Expose init function globally
    window.initReferenciasManager = function(container, pvId) {
        new ReferenciasManager(container, pvId);
    };

})();
