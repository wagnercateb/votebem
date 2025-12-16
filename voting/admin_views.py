from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
import time
import json
import logging
import re
import requests
from .models import Proposicao, ProposicaoVotacao, VotacaoVoteBem, Voto, Congressman, CongressmanVote, Referencia
from django.contrib.auth.models import User
from .services.camara_api import camara_api, CamaraAPIService
from votebem.utils.devlog import dev_log  # Dev logger for console + file output
from django.db import transaction
from django.core.cache import cache
import threading
import os
import glob
import hashlib
from typing import Dict, Any, List, Tuple
from pathlib import Path
from django.conf import settings
from decouple import config as env_config
from functools import wraps
from django.http import HttpResponseForbidden

# Background task helpers
# ------------------------
# We use a simple Redis-backed lock via Django cache to prevent duplicate runs,
# and update a status key with human-readable progress. This avoids request timeouts
# (e.g., from reverse proxies or WSGI workers) by moving heavy work off the request.

def _acquire_lock(lock_key: str, ttl_seconds: int = 1800) -> bool:
    """Try to acquire a cooperative lock using cache.add (SETNX semantics).
    Returns True if acquired, False if already locked.
    """
    try:
        # cache.add returns True if the key did not exist and is now set.
        return bool(cache.add(lock_key, '1', ttl_seconds))
    except Exception:
        return True

def _release_lock(lock_key: str):
    """Release the cooperative lock by deleting the cache key."""
    try:
        cache.delete(lock_key)
    except Exception:
        pass

def _set_status(status_key: str, payload: dict, ttl_seconds: int = 3600):
    """Store a status snapshot under `status_key` with a TTL, for polling by UI."""
    try:
        cache.set(status_key, payload, ttl_seconds)
    except Exception as e:
        dev_log(f"ERROR in _set_status for {status_key}: {e}")

def _get_status(status_key: str) -> dict:
    """Retrieve the latest status payload. Returns empty dict if missing."""
    try:
        return cache.get(status_key) or {}
    except Exception:
        return {}

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = getattr(settings, 'LOGIN_URL', '/accounts/login/')
            return redirect(f"{login_url}?next={request.get_full_path()}")
        if not request.user.is_staff:
            return HttpResponseForbidden("Você não tem permissão para acessar a área administrativa.")
        return view_func(request, *args, **kwargs)
    return _wrapped

@admin_required
def admin_dashboard(request):
    """
    Custom admin dashboard with statistics and management tools
    Similar to the PHP admin interface functionality
    """
    context = {
        'total_proposicoes': Proposicao.objects.count(),
        'total_votacoes_disponiveis': VotacaoVoteBem.objects.count(),
        'votacoes_ativas': VotacaoVoteBem.objects.filter(ativo=True).count(),
        'total_votos_populares': Voto.objects.count(),
        'total_congressistas': Congressman.objects.count(),
        'total_votos_congressistas': CongressmanVote.objects.count(),
        'total_usuarios': User.objects.count(),
    }
    
    return render(request, 'admin/voting/admin_dashboard.html', context)


@staff_member_required
def rag_tool(request):
    """
    Página administrativa simples para executar a lógica do notebook RAG (sem LangChain).

    - Lê valores padrão do notebook `.ipynb` para variáveis de página (DOC_FOLDER, CHROMA_COLLECTION_NAME, HASH_FILE,
      system_prompt, query). O `context_text` é preenchido dinamicamente ao rodar a consulta.
    - Permite editar esses valores via formulário e submeter a `query`.
    - Executa uma recuperação básica de contexto lendo arquivos `.md` (e `.pdf` se pdfplumber disponível) em `DOC_FOLDER`.
    - Tenta chamar a API OpenAI se `OPENAI_API_KEY` estiver configurada; caso contrário, retorna uma resposta de fallback.

    Observação: esta implementação evita dependências externas (chromadb) e oferece uma lógica de recuperação simplificada
    para manter compatibilidade imediata.
    """

    # Caminho do arquivo de configuração persistente (JSON) dentro do app
    config_path = os.path.join(os.path.dirname(__file__), 'rag_config.json')

    # Valores padrão (hardcoded) extraídos do notebook .ipynb;
    # O .ipynb NÃO é necessário para executar o app após esta cópia.
    HARDCODED_DEFAULTS: Dict[str, Any] = {
        # Default to project-relative docs/noticias/ where non-versioned inputs may reside
        'DOC_FOLDER': "docs/noticias/",
        'CHROMA_COLLECTION_NAME': "rag_docs",
        'HASH_FILE': "file_hashes.npy",
        'query': "Explique o que foi o pl antifaccção votado na câmara",
        'system_prompt': (
            "You are a helpful assistant. Write in portuguese with the simplest language possible. "
            "Answer the user’s questions using the provided context. DO NOT DEDUCE ANY EXPLANATION THAT IS NOT IN THE CONTEXT.\n"
            "If the context do not have information to answer the question, ignore the rest of this prompt.\n"
            "The answer should provide this information:\n"
            "1) votacao: inform when the proposta/lei was approved, formatted dd/mm/YYYY. if the article does not mention, inform the article date. \n"
            "    if possible, inform a code or number of the proposicao or PL (projeto de lei) or PEC (proposta de emenda à constituição)\n"
            "    or any code that helps identify it. If there is no code, do not mention anything about it. Mention the number of votes for and against it. \n"
            "2) titulo: provide a title explaining what this is about in up to 100 characters;\n"
            "3) resumo: do not repeat information provided in items (1) or (2). Provide an abstract of what was approved in no more than 500 characters.  Use a concise and simple language. \n"
            "4) explicacao: create a thorough explanation about the question in aproximately 2000 characters. Whenever more technical expressions are used (e.g., trânsito em julgado, ), avoid it or briefly explain them in parentheses right afterwards. Try to elaborate on who gains and who loses with it, how it can affect employment, its economic and political implications, etc. Explain how it is important or harmful to the country. At the end, briefly mention the sources of the information, including author, where and date.\n"
        ),
    }

    def _read_config_defaults(path: str) -> Dict[str, Any]:
        """Lê o arquivo JSON de configuração se existir; caso contrário, retorna hardcoded defaults."""
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Garantir chaves presentes; completar com hardcoded se faltar
                merged = {**HARDCODED_DEFAULTS, **(data or {})}
                return merged
        except Exception:
            pass
        return HARDCODED_DEFAULTS.copy()

    def _write_config_defaults(path: str, payload: Dict[str, Any]) -> bool:
        """Persiste as variáveis atuais no JSON. Retorna True em sucesso."""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def _read_md_file(path: str) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return ''

    def _read_pdf_file(path: str) -> str:
        try:
            import pdfplumber  # optional
            with pdfplumber.open(path) as pdf:
                return "\n\n".join(page.extract_text() or '' for page in pdf.pages)
        except Exception:
            return ''

    def _read_txt_file(path: str) -> str:
        """Leitura simples para arquivos .txt como contexto adicional."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return ''

    def _retrieve_context(doc_folder: str, query_text: str, max_chars: int = 3000) -> str:
        """Naive retrieval: read .md, .pdf and .txt from folder, score by keyword hits and join top snippets."""
        if not doc_folder:
            return ''
        try:
            files = (
                glob.glob(os.path.join(doc_folder, '*.md')) +
                glob.glob(os.path.join(doc_folder, '*.pdf')) +
                glob.glob(os.path.join(doc_folder, '*.txt'))
            )
        except Exception:
            files = []
        q = (query_text or '').strip().lower()
        tokens = [t for t in re.split(r"\W+", q) if t]
        scored: List[Tuple[str, int, str]] = []  # (path, score, content)
        for fp in files:
            lowfp = fp.lower()
            if lowfp.endswith('.md'):
                content = _read_md_file(fp)
            elif lowfp.endswith('.pdf'):
                content = _read_pdf_file(fp)
            else:
                content = _read_txt_file(fp)
            low = content.lower()
            score = sum(low.count(tok) for tok in tokens)
            if score > 0:
                scored.append((fp, score, content))
        scored.sort(key=lambda x: x[1], reverse=True)
        out = []
        total = 0
        for _, _, txt in scored:
            if not txt:
                continue
            if total >= max_chars:
                break
            chunk = txt[:max_chars - total]
            out.append(chunk)
            total += len(chunk)
        return "\n\n".join(out)

    defaults = _read_config_defaults(config_path)

    # Inputs from notebook or environment
    initial_doc_folder = defaults.get('DOC_FOLDER') or os.getenv('VB_DOC_FOLDER') or ''
    initial_collection = defaults.get('CHROMA_COLLECTION_NAME') or 'rag_docs'
    initial_hash_file = defaults.get('HASH_FILE') or 'file_hashes.npy'
    initial_query = defaults.get('query') or ''
    initial_system_prompt = defaults.get('system_prompt') or ''

    # Submitted values
    doc_folder = request.POST.get('DOC_FOLDER', initial_doc_folder)
    try:
        doc_folder = doc_folder.replace('\\', '/')
    except Exception:
        pass
    # Resolve DOC_FOLDER relative to app root (BASE_DIR) when given as relative
    # This ensures users can set paths like "docs\\nao_versionados\\" and we will search
    # under <project_root>/docs/nao_versionados/ for content files.
    # Resolve DOC_FOLDER to an absolute path. Many projects set BASE_DIR to the
    # Django package root (e.g., <project>/votebem), while content folders like
    # "docs" live at the project root (parent of BASE_DIR). We try both.
    if doc_folder and os.path.isabs(doc_folder):
        if os.path.isdir(doc_folder):
            doc_folder_abs = doc_folder
        else:
            env_mod = os.environ.get('DJANGO_SETTINGS_MODULE', '') or getattr(settings, 'SETTINGS_MODULE', '')
            candidates = []
            if env_mod.endswith('.production') or env_mod.endswith('.build'):
                candidates.append('/dados/votebem/docs/noticias')
                candidates.append('/app/votebem/docs/noticias')
            base_candidate = os.path.join(settings.BASE_DIR, 'docs', 'noticias')
            root_candidate = os.path.join(os.path.dirname(settings.BASE_DIR), 'docs', 'noticias')
            candidates.extend([base_candidate, root_candidate])
            found = ''
            for c in candidates:
                if os.path.isdir(c):
                    found = c
                    break
            doc_folder_abs = found or doc_folder
    elif doc_folder:
        base_candidate = os.path.join(settings.BASE_DIR, doc_folder)
        project_root = os.path.dirname(settings.BASE_DIR)
        root_candidate = os.path.join(project_root, doc_folder)
        env_mod = os.environ.get('DJANGO_SETTINGS_MODULE', '') or getattr(settings, 'SETTINGS_MODULE', '')
        data_root = '/dados/votebem' if (env_mod.endswith('.production') or env_mod.endswith('.build')) else ''
        data_candidate = os.path.join(data_root, doc_folder) if data_root else ''
        if data_candidate and os.path.isdir(data_candidate):
            doc_folder_abs = data_candidate
        elif os.path.isdir(base_candidate):
            doc_folder_abs = base_candidate
        elif os.path.isdir(root_candidate):
            doc_folder_abs = root_candidate
        else:
            doc_folder_abs = base_candidate
    else:
        doc_folder_abs = ''
    # Count candidate files in the resolved DOC_FOLDER (md, pdf, txt)
    try:
        _doc_candidates = []
        for pat in ('**/*.md', '**/*.pdf', '**/*.txt'):
            _doc_candidates.extend(glob.glob(os.path.join(doc_folder_abs, pat), recursive=True))
        doc_files_count = len(_doc_candidates)
    except Exception:
        doc_files_count = 0
    if doc_files_count == 0:
        try:
            from django.contrib import messages as dj_messages
            dj_messages.warning(request, f"Nenhum arquivo encontrado em {doc_folder_abs}.")
        except Exception:
            pass
    chroma_collection = request.POST.get('CHROMA_COLLECTION_NAME', initial_collection)
    hash_file = request.POST.get('HASH_FILE', initial_hash_file)
    system_prompt = request.POST.get('system_prompt', initial_system_prompt)
    query_text = request.POST.get('query', initial_query)
    context_text = request.POST.get('context_text', '')

    # Carregar OPENAI_API_KEY centralmente dos settings; fallback para decouple/env e leitura manual
    api_key = (
        getattr(settings, 'OPENAI_API_KEY', '')
        or env_config('OPENAI_API_KEY', default='')
        or os.getenv('OPENAI_API_KEY')
        or ''
    )
    if not api_key:
        # 2) Fallback manual: varrer possíveis caminhos do projeto
        try:
            base_dir = Path(getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(__file__))))
            candidates_dirs = [base_dir, base_dir.parent]
            candidates_files = ['.env.local', '.env']  # prioridade: .env.local, depois .env
            for d in candidates_dirs:
                for fname in candidates_files:
                    env_path = d / fname
                    if env_path.exists():
                        with open(env_path, 'r', encoding='utf-8') as f:
                            for raw_line in f:
                                line = raw_line.strip()
                                if not line or line.startswith('#'):
                                    continue
                                # Aceitar formatos: OPENAI_API_KEY=..., OPENAI_API_KEY="..."
                                if line.startswith('OPENAI_API_KEY'):
                                    try:
                                        k, v = line.split('=', 1)
                                        if k.strip() == 'OPENAI_API_KEY':
                                            v = v.strip().strip('"').strip("'")
                                            if v:
                                                api_key = v
                                                break
                                    except Exception:
                                        pass
                            if api_key:
                                break
                if api_key:
                    break
        except Exception:
            # Silencioso: se falhar, seguimos sem chave e o fluxo usará fallback
            pass

    answer = None
    ran_query = False
    error_msg = None
    embed_result = None  # textual summary after embedding
    # Track whether Chroma was the source for retrieved context (for UI status)
    chroma_used = False
    # Flag to indicate a context-only fetch was performed (no API call)
    context_fetched = False

    # Ação "Buscar contexto": apenas popula o textarea de contexto sem chamar a API
    if request.method == 'POST' and request.POST.get('fetch_context'):
        try:
            # Tenta recuperar via Chroma com o provider selecionado; fallback para leitura de arquivos
            try:
                import chromadb
                from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction, SentenceTransformerEmbeddingFunction
                provider = request.POST.get('embed_provider') or getattr(settings, 'EMBEDDING_PROVIDER', 'local')
                provider = provider if provider in ('openai', 'local') else 'local'
                local_model = getattr(settings, 'LOCAL_EMBED_MODEL', 'all-MiniLM-L6-v2')
                persist_path = getattr(settings, 'CHROMA_PERSIST_PATH', '')
                effective_collection = f"{chroma_collection}__{provider}"

                # Definir função de embedding conforme provider
                if provider == 'local':
                    ef = SentenceTransformerEmbeddingFunction(model_name=local_model)
                else:
                    if not api_key:
                        raise RuntimeError('OPENAI_API_KEY ausente para embeddings OpenAI')
                    ef = OpenAIEmbeddingFunction(api_key=api_key, model_name=getattr(settings, 'OPENAI_EMBED_MODEL', 'text-embedding-3-small'))

                # Cliente Chroma (persistente se caminho configurado)
                try:
                    client = chromadb.PersistentClient(path=persist_path) if persist_path else chromadb.Client()
                except Exception:
                    client = chromadb.Client()

                # Obter/criar coleção
                try:
                    names = [c.name for c in client.list_collections()]
                    if effective_collection in names:
                        coll = client.get_collection(effective_collection)
                    else:
                        coll = client.create_collection(name=effective_collection, embedding_function=ef)
                except Exception:
                    coll = client.get_or_create_collection(name=effective_collection)

                # Consulta por similaridade
                qr = coll.query(query_texts=[query_text], n_results=5)
                docs = (qr.get('documents') or [[]])[0]
                metas = (qr.get('metadatas') or [[]])[0]
                if docs:
                    parts = []
                    for i, d in enumerate(docs):
                        src = ''
                        try:
                            src = metas[i].get('source') if isinstance(metas[i], dict) else ''
                        except Exception:
                            src = ''
                        header = f"[Fonte: {src}]" if src else "[Fonte: desconhecida]"
                        parts.append(header)
                        parts.append(d or '')
                        parts.append("\n---\n")
                    context_text = "\n".join(parts)
                    chroma_used = True
                    try:
                        from django.contrib import messages as dj_messages
                        dj_messages.info(request, f"Contexto recuperado via ChromaDB (top-5). Persistência: {persist_path or 'memória'}")
                    except Exception:
                        pass
                else:
                    raise RuntimeError('Nenhum resultado na consulta da coleção Chroma.')
            except Exception:
                # Fallback: recuperar contexto diretamente dos arquivos locais
                ctx = _retrieve_context(doc_folder_abs, query_text)
                context_text = ctx
                chroma_used = False
                try:
                    from django.contrib import messages as dj_messages
                    dj_messages.warning(request, "ChromaDB indisponível ou vazio; usando contexto por leitura de arquivos.")
                except Exception:
                    pass
            context_fetched = True
        except Exception as e:
            error_msg = f'Erro ao buscar contexto: {e}'

    # Submissão de consulta: recupera contexto pelo ChromaDB (embeddings) com fallback para leitura de arquivos
    if request.method == 'POST' and request.POST.get('submit_query'):
        ran_query = True
        # Async execution to prevent timeouts
        lock_key = f"vb:rag:query:{request.user.id}"
        status_key = f"vb:rag:query:status:{request.user.id}"

        if not _acquire_lock(lock_key, ttl_seconds=300):
            messages.warning(request, "Já existe uma consulta em andamento.")
            query_status_key = status_key
        else:
            # Capture variables for thread
            _query_text = query_text
            _system_prompt = system_prompt
            _chroma_collection = chroma_collection
            _doc_folder_abs = doc_folder_abs
            _api_key = api_key
            _embed_provider = request.POST.get('embed_provider') or getattr(settings, 'EMBEDDING_PROVIDER', 'local')
            
            def _process_query():
                try:
                    _set_status(status_key, {'state': 'processing', 'message': 'Recuperando contexto...'})
                    
                    context_text = ''
                    chroma_used = False
                    warning_msg = ''
                    
                    # 1) Tenta recuperar contexto via ChromaDB
                    try:
                        print(f"[RAG] Starting context retrieval. Provider: {_embed_provider}")
                        import chromadb
                        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction, SentenceTransformerEmbeddingFunction
                        
                        provider = _embed_provider if _embed_provider in ('openai', 'local') else 'local'
                        local_model = getattr(settings, 'LOCAL_EMBED_MODEL', 'all-MiniLM-L6-v2')
                        persist_path = getattr(settings, 'CHROMA_PERSIST_PATH', '')
                        effective_collection = f"{_chroma_collection}__{provider}"

                        if provider == 'local':
                            print(f"[RAG] Using local model: {local_model}")
                            ef = SentenceTransformerEmbeddingFunction(model_name=local_model)
                        else:
                            if not _api_key:
                                raise RuntimeError('OPENAI_API_KEY ausente para embeddings OpenAI')
                            print(f"[RAG] Using OpenAI model: {getattr(settings, 'OPENAI_EMBED_MODEL', 'text-embedding-3-small')}")
                            ef = OpenAIEmbeddingFunction(api_key=_api_key, model_name=getattr(settings, 'OPENAI_EMBED_MODEL', 'text-embedding-3-small'))

                        try:
                            print(f"[RAG] Connecting to ChromaDB at {persist_path or 'memory'}")
                            client = chromadb.PersistentClient(path=persist_path) if persist_path else chromadb.Client()
                        except Exception as e:
                            print(f"[RAG] Failed to create PersistentClient: {e}. Fallback to Client()")
                            client = chromadb.Client()

                        try:
                            names = [c.name for c in client.list_collections()]
                            if effective_collection in names:
                                print(f"[RAG] Getting collection: {effective_collection}")
                                coll = client.get_collection(effective_collection)
                            else:
                                print(f"[RAG] Creating collection: {effective_collection}")
                                coll = client.create_collection(name=effective_collection, embedding_function=ef)
                        except Exception as e:
                            print(f"[RAG] get_collection failed: {e}. Trying get_or_create.")
                            coll = client.get_or_create_collection(name=effective_collection)

                        print(f"[RAG] Querying collection with text: {_query_text[:50]}...")
                        qr = coll.query(query_texts=[_query_text], n_results=5)
                        print(f"[RAG] Query finished. Documents found: {len(qr.get('documents', [[]])[0])}")
                        
                        docs = (qr.get('documents') or [[]])[0]
                        metas = (qr.get('metadatas') or [[]])[0]
                        
                        if docs:
                            parts = []
                            for i, d in enumerate(docs):
                                src = ''
                                try:
                                    src = metas[i].get('source') if isinstance(metas[i], dict) else ''
                                except Exception:
                                    src = ''
                                header = f"[Fonte: {src}]" if src else "[Fonte: desconhecida]"
                                parts.append(header)
                                parts.append(d or '')
                                parts.append("\n---\n")
                            context_text = "\n".join(parts)
                            chroma_used = True
                        else:
                            print("[RAG] No documents returned from query.")
                            raise RuntimeError('Nenhum resultado na consulta da coleção Chroma.')
                    except Exception as e:
                        print(f"[RAG] ChromaDB block failed: {e}")
                        # Fallback
                        ctx = _retrieve_context(_doc_folder_abs, _query_text)
                        context_text = ctx
                        chroma_used = False
                        warning_msg = "ChromaDB indisponível ou vazio; usando contexto por leitura de arquivos."

                    print("[RAG] Updating status: Consultando LLM...")
                    _set_status(status_key, {'state': 'processing', 'message': 'Consultando LLM...', 'context_text': context_text})

                    # Build prompt
                    try:
                        has_placeholders = bool(_system_prompt and ('{context_text}' in _system_prompt or '{query}' in _system_prompt))
                        if has_placeholders:
                            final_prompt = _system_prompt.format(context_text=context_text, query=_query_text)
                        else:
                            final_prompt = _system_prompt
                    except Exception as e:
                        print(f"[RAG] Prompt formatting error: {e}")
                        final_prompt = _system_prompt

                    # 3) Generation
                    answer = ''
                    try:
                        if _api_key:
                            print("[RAG] Calling OpenAI chat completion...")
                            from openai import OpenAI
                            client = OpenAI(api_key=_api_key, timeout=30.0)
                            system_content = (final_prompt or '')
                            try:
                                if not has_placeholders and (context_text or '').strip():
                                    ctx = (context_text or '').strip()
                                    if len(ctx) > 4000:
                                        ctx = ctx[:4000]
                                    system_content = f"{system_content}\n\nContexto:\n{ctx}"
                            except Exception:
                                pass
                            
                            resp = client.chat.completions.create(
                                model=getattr(settings, 'OPENAI_LLM_MODEL', 'gpt-4o-mini'),
                                messages=[
                                    {"role": "system", "content": system_content},
                                    {"role": "user", "content": _query_text or ""},
                                ],
                                temperature=0.2,
                            )
                            answer = (resp.choices[0].message.content if getattr(resp, 'choices', None) else '')
                            print(f"[RAG] OpenAI response received. Length: {len(answer)}")
                        else:
                            raise RuntimeError('OPENAI_API_KEY missing')
                    except Exception as e:
                        print(f"[RAG] OpenAI generation failed: {e}")
                        base = (context_text or '').strip()
                        if base:
                            answer = base[:800]
                        else:
                            answer = 'Nenhuma resposta disponível (contexto vazio e API indisponível).'

                    # Save to file
                    saved_path = ''
                    try:
                        from django.utils import timezone
                        now_date = timezone.localtime().date().isoformat()
                        prod_dir = '/dados/votebem/docs/respostas_ia'
                        local_dir = os.path.join(os.path.dirname(settings.BASE_DIR), 'docs', 'nao_versionados', 'respostas_ia')
                        
                        env_mod = os.environ.get('DJANGO_SETTINGS_MODULE', '') or getattr(settings, 'SETTINGS_MODULE', '')
                        is_dev = env_mod.endswith('.development')
                        is_prodlike = env_mod.endswith('.production') or env_mod.endswith('.build')
                        preferred_dir = local_dir if is_dev else (prod_dir if is_prodlike else local_dir)
                        
                        save_dir = preferred_dir
                        try:
                            os.makedirs(save_dir, exist_ok=True)
                        except Exception:
                            try:
                                save_dir = local_dir
                                os.makedirs(save_dir, exist_ok=True)
                            except Exception:
                                save_dir = prod_dir
                                os.makedirs(save_dir, exist_ok=True)

                        q = (_query_text or '').strip()
                        safe_q = re.sub(r"[^\w\-]+", "_", q)
                        if len(safe_q) > 80:
                            safe_q = safe_q[:80]
                        if not safe_q:
                            safe_q = 'consulta'
                        fname = f"{now_date}_{safe_q}.txt"
                        fpath = os.path.join(save_dir, fname)

                        sep = ["", "-" * 80, ""]
                        content_lines = [
                            (q or ''),
                            *sep,
                            (answer or ''),
                            *sep,
                            (context_text or ''),
                            *sep,
                            (context_text or ''), # duplicated in original, keeping strict
                            (_system_prompt or ''),
                        ]
                        # Fix potential list issue if original had error, but it looked like simple list
                        # Actually original had *sep, (_system_prompt or '')
                        with open(fpath, 'w', encoding='utf-8') as f:
                            f.write("\n".join(content_lines))
                        saved_path = fpath
                        print(f"[RAG] Saved response to {saved_path}")
                    except Exception as e:
                        print(f"[RAG] Failed to save response file: {e}")
                        pass

                    print("[RAG] Task completed successfully. Updating status.")
                    _set_status(status_key, {
                        'state': 'completed',
                        'answer': answer,
                        'context_text': context_text,
                        'warning_msg': warning_msg,
                        'saved_path': saved_path,
                        'message': 'Consulta concluída.'
                    })

                except Exception as e:
                    print(f"[RAG] Fatal error in background thread: {e}")
                    import traceback
                    traceback.print_exc()
                    _set_status(status_key, {'state': 'error', 'message': f'Erro: {str(e)}'})
                finally:
                    _release_lock(lock_key)

            threading.Thread(target=_process_query, daemon=True).start()
            query_status_key = status_key
            messages.info(request, "Consulta iniciada em segundo plano.")

    # Comando de embed: varre DOC_FOLDER por novos/atualizados arquivos e envia para Chroma
    if request.method == 'POST' and request.POST.get('embed_docs'):
        try:
            import numpy as np
            env_mod = os.environ.get('DJANGO_SETTINGS_MODULE', '') or getattr(settings, 'SETTINGS_MODULE', '')
            if hash_file and os.path.isabs(hash_file):
                hash_path = hash_file
            elif hash_file:
                if env_mod.endswith('.production') or env_mod.endswith('.build'):
                    hash_path = os.path.join('/dados/embeddings/votebem', hash_file)
                else:
                    hash_path = os.path.join(settings.BASE_DIR, hash_file)
            else:
                hash_path = ''
            force_flag = bool(request.POST.get('force_reembed'))
            provider = request.POST.get('embed_provider') or getattr(settings, 'EMBEDDING_PROVIDER', 'local')
            provider = provider if provider in ('openai', 'local') else 'openai'
            effective_collection = f"{chroma_collection}__{provider}"
            lock_key = f"vb:lock:rag_embed:{effective_collection}"
            status_key = f"vb:status:rag_embed:{effective_collection}"
            if not _acquire_lock(lock_key, ttl_seconds=3600):
                messages.warning(request, 'Uma tarefa de embedding já está em andamento.')
            else:
                def _run_embed():
                    try:
                        _set_status(status_key, {'state': 'starting', 'progress': 0, 'message': 'Preparando embedding...', 'collection': effective_collection})
                        try:
                            import chromadb
                            from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction, SentenceTransformerEmbeddingFunction
                        except Exception as e:
                            _set_status(status_key, {'state': 'error', 'message': str(e)})
                            return
                        persist_path = getattr(settings, 'CHROMA_PERSIST_PATH', '')
                        local_model = getattr(settings, 'LOCAL_EMBED_MODEL', 'all-MiniLM-L6-v2')
                        if provider == 'local':
                            ef = SentenceTransformerEmbeddingFunction(model_name=local_model)
                        else:
                            if not api_key:
                                _set_status(status_key, {'state': 'error', 'message': 'OPENAI_API_KEY ausente'})
                                return
                            ef = OpenAIEmbeddingFunction(api_key=api_key, model_name=getattr(settings, 'OPENAI_EMBED_MODEL', 'text-embedding-3-small'))
                        try:
                            client = chromadb.PersistentClient(path=persist_path) if persist_path else chromadb.Client()
                        except Exception:
                            client = chromadb.Client()
                        try:
                            names = [c.name for c in client.list_collections()]
                            if effective_collection in names:
                                collection = client.get_collection(effective_collection)
                            else:
                                collection = client.create_collection(name=effective_collection, embedding_function=ef)
                        except Exception:
                            collection = client.get_or_create_collection(name=effective_collection)
                        existing_hashes = {}
                        try:
                            if hash_path.endswith('.npy'):
                                try:
                                    arr = np.load(hash_path, allow_pickle=True)
                                    if isinstance(arr, np.ndarray) and arr.size == 1:
                                        existing_hashes = arr.item() if isinstance(arr.item(), dict) else {}
                                    elif isinstance(arr, dict):
                                        existing_hashes = arr
                                except Exception:
                                    existing_hashes = {}
                            else:
                                try:
                                    if os.path.exists(hash_path):
                                        with open(hash_path, 'r', encoding='utf-8') as f:
                                            existing_hashes = json.load(f)
                                except Exception:
                                    existing_hashes = {}
                        except Exception:
                            existing_hashes = {}
                        try:
                            files = []
                            for pat in ('**/*.md', '**/*.pdf', '**/*.txt'):
                                files.extend(glob.glob(os.path.join(doc_folder_abs, pat), recursive=True))
                        except Exception:
                            files = []
                        def compute_hash(fp: str) -> str:
                            h = hashlib.sha256()
                            try:
                                with open(fp, 'rb') as f:
                                    for chunk in iter(lambda: f.read(8192), b''):
                                        h.update(chunk)
                                return h.hexdigest()
                            except Exception:
                                return ''
                        new_or_updated = []
                        for fp in files:
                            h = compute_hash(fp)
                            if not h:
                                continue
                            prev = existing_hashes.get(fp)
                            prefixed_hash = f"{provider}:{h}"
                            if force_flag or prev != prefixed_hash:
                                new_or_updated.append((fp, prefixed_hash))
                        total = len(new_or_updated)
                        _set_status(status_key, {'state': 'running', 'progress': 0, 'total': total, 'message': 'Iniciando processamento...', 'collection': effective_collection})
                        def extract_text(fp: str) -> str:
                            lowfp = fp.lower()
                            if lowfp.endswith('.md'):
                                return _read_md_file(fp)
                            if lowfp.endswith('.pdf'):
                                return _read_pdf_file(fp)
                            return _read_txt_file(fp)
                        def split_text(text: str, chunk_size: int = 1500) -> list[str]:
                            t = text or ''
                            chunks = []
                            i = 0
                            while i < len(t):
                                chunks.append(t[i:i+chunk_size])
                                i += chunk_size
                            return chunks
                        processed_files = 0
                        total_chunks = 0
                        for fpath, file_hash in new_or_updated:
                            text = extract_text(fpath)
                            if not text:
                                processed_files += 1
                                _set_status(status_key, {'state': 'running', 'progress': int((processed_files / max(total, 1)) * 100), 'processed': processed_files, 'total': total, 'message': f'Ignorado: {os.path.basename(fpath)}'})
                                continue
                            chunks = split_text(text)
                            basename = os.path.basename(fpath)
                            ids = [f"{basename}_chunk_{i}" for i in range(len(chunks))]
                            metadatas = [{"source": basename, "chunk": i} for i in range(len(chunks))]
                            try:
                                if force_flag:
                                    try:
                                        collection.delete(where={"source": basename})
                                    except Exception:
                                        pass
                                collection.add(documents=chunks, metadatas=metadatas, ids=ids)
                                existing_hashes[fpath] = file_hash
                                total_chunks += len(chunks)
                                processed_files += 1
                                try:
                                    import shutil
                                    project_root = os.path.dirname(settings.BASE_DIR)
                                    is_dev = env_mod.endswith('.development')
                                    is_prodlike = env_mod.endswith('.production') or env_mod.endswith('.build')
                                    dev_embedded_dir = os.path.join(project_root, 'docs', 'nao_versionados', 'embeddings', 'noticias_ja_embedded')
                                    prod_embedded_dir = '/dados/embeddings/votebem/noticias_ja_embedded'
                                    archive_dir = dev_embedded_dir if is_dev else (prod_embedded_dir if is_prodlike else dev_embedded_dir)
                                    os.makedirs(archive_dir, exist_ok=True)
                                    dest_path = os.path.join(archive_dir, os.path.basename(fpath))
                                    shutil.move(fpath, dest_path)
                                except Exception:
                                    pass
                                _set_status(status_key, {'state': 'running', 'progress': int((processed_files / max(total, 1)) * 100), 'processed': processed_files, 'total': total, 'chunks': total_chunks, 'message': f'Processado: {basename}'})
                            except Exception as e:
                                processed_files += 1
                                _set_status(status_key, {'state': 'running', 'progress': int((processed_files / max(total, 1)) * 100), 'processed': processed_files, 'total': total, 'message': f'Falha em {basename}: {str(e)}'})
                                continue
                        try:
                            if hash_path.endswith('.npy'):
                                try:
                                    np.save(hash_path, existing_hashes)
                                except Exception:
                                    try:
                                        alt = os.path.splitext(hash_path)[0] + '.json'
                                        with open(alt, 'w', encoding='utf-8') as f:
                                            json.dump(existing_hashes, f, ensure_ascii=False, indent=2)
                                    except Exception:
                                        pass
                            else:
                                with open(hash_path, 'w', encoding='utf-8') as f:
                                    json.dump(existing_hashes, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                        _set_status(status_key, {
                            'state': 'completed',
                            'processed': processed_files,
                            'total': total,
                            'chunks': total_chunks,
                            'message': f'Concluído: {processed_files}/{total} arquivos, {total_chunks} chunks.'
                        })
                    finally:
                        _release_lock(lock_key)
                threading.Thread(target=_run_embed, daemon=True).start()
                messages.info(request, f"Tarefa de embedding iniciada. Status: {status_key}")
                embed_status_key = status_key
        except Exception as e:
            error_msg = f'Erro ao iniciar tarefa de embedding: {e}'

    # Botão "Estatísticas" da coleção Chroma: mostra contagem e persistência
    if request.method == 'POST' and request.POST.get('chroma_stats'):
        try:
            import chromadb
            persist_path = getattr(settings, 'CHROMA_PERSIST_PATH', '')
            try:
                client = chromadb.PersistentClient(path=persist_path) if persist_path else chromadb.Client()
            except Exception:
                client = chromadb.Client()

            provider_raw = request.POST.get('embed_provider')
            providers = [provider_raw] if provider_raw in ('openai', 'local') else ['openai', 'local']
            stats_parts = []
            sources_parts = []
            for provider_sel in providers:
                try:
                    effective_collection = f"{chroma_collection}__{provider_sel}"
                    coll = client.get_or_create_collection(name=effective_collection)
                except Exception:
                    coll = None

                total_items = 0
                if coll:
                    try:
                        total_items = coll.count()
                    except Exception:
                        total_items = 0

                if persist_path:
                    stats_parts.append(f"[{provider_sel}] '{effective_collection}': {total_items} itens · persistência: {persist_path}")
                else:
                    stats_parts.append(f"[{provider_sel}] '{effective_collection}': {total_items} itens · persistência: memória")

                try:
                    if coll and total_items:
                        sample_limit = min(total_items, 2000)
                        batch = coll.get(include=["metadatas"], limit=sample_limit)
                        metas = batch.get("metadatas") or []
                        from collections import Counter
                        c = Counter()
                        for m in metas:
                            if isinstance(m, dict):
                                src = m.get("source") or "(desconhecida)"
                                c[src] += 1
                            elif isinstance(m, list):
                                for mm in m:
                                    if isinstance(mm, dict):
                                        src = mm.get("source") or "(desconhecida)"
                                        c[src] += 1
                        if c:
                            ordered = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))
                            items = "".join([f"<li>{name} ({count})</li>" for name, count in ordered])
                            sources_parts.append(f"<div><strong>[{provider_sel}] Fontes (amostra de {sample_limit}):</strong><ul>{items}</ul></div>")
                        else:
                            sources_parts.append(f"<div><strong>[{provider_sel}] Fontes:</strong> nenhuma</div>")
                except Exception:
                    pass

            chroma_stats = " \n".join(stats_parts)
            chroma_sources_html = "".join(sources_parts)
        except Exception as e:
            chroma_stats = f"Falha ao obter estatísticas da coleção: {e}"

    # Atualização de variáveis sem consultar: persistir no arquivo JSON
    if request.method == 'POST' and not request.POST.get('submit_query'):
        to_save = {
            'DOC_FOLDER': doc_folder,
            'CHROMA_COLLECTION_NAME': chroma_collection,
            'HASH_FILE': hash_file,
            'system_prompt': system_prompt,
            'query': query_text,
        }
        ok = _write_config_defaults(config_path, to_save)
        if ok:
            messages.success(request, 'Configuração do RAG atualizada com sucesso.')
        else:
            messages.error(request, 'Falha ao salvar configuração do RAG.')

    # Build a concise status string about included context for the UI
    try:
        _ctx_len = len((context_text or '').strip())
    except Exception:
        _ctx_len = 0
    _ctx_source = 'ChromaDB' if (ran_query and chroma_used) else ('Arquivos' if ran_query else '')
    context_status = f"Contexto incluído: {_ctx_len} caracteres ({_ctx_source})" if (ran_query or context_fetched) else ''

    try:
        env_mod = os.environ.get('DJANGO_SETTINGS_MODULE', '') or getattr(settings, 'SETTINGS_MODULE', '')
        if hash_file:
            if os.path.isabs(hash_file):
                hash_file_abs = hash_file
            else:
                if env_mod.endswith('.production') or env_mod.endswith('.build'):
                    hash_file_abs = os.path.join('/dados/embeddings/votebem', hash_file)
                else:
                    hash_file_abs = os.path.join(settings.BASE_DIR, hash_file)
        else:
            hash_file_abs = ''
    except Exception:
        hash_file_abs = ''

    try:
        env_mod = os.environ.get('DJANGO_SETTINGS_MODULE', '') or getattr(settings, 'SETTINGS_MODULE', '')
        if env_mod.endswith('.production') or env_mod.endswith('.build'):
            config_path_display = '/dados/votebem/voting/rag_config.json'
        else:
            config_path_display = config_path
    except Exception:
        config_path_display = config_path
    submitted_action = None
    if request.method == 'POST':
        if request.POST.get('embed_docs'):
            submitted_action = 'embed_docs'
        elif request.POST.get('chroma_stats'):
            submitted_action = 'chroma_stats'
        elif request.POST.get('fetch_context'):
            submitted_action = 'fetch_context'
        elif request.POST.get('submit_query'):
            submitted_action = 'submit_query'
    active_tab = 'tab-embed' if submitted_action in ('embed_docs', 'chroma_stats') else 'tab-query'

    context = {
        'DOC_FOLDER': doc_folder,  # original value as shown in UI (can be relative)
        # Provide the resolved absolute folder for debugging purposes (not required in UI)
        'DOC_FOLDER_ABS': doc_folder_abs,
        'doc_files_count': doc_files_count,
        'CHROMA_COLLECTION_NAME': chroma_collection,
        'HASH_FILE': hash_file,
        'HASH_FILE_ABS': hash_file_abs,
        'system_prompt': system_prompt,
        'query': query_text,
        'context_text': context_text,
        'answer': answer,
        'context_status': context_status,
        'context_fetched': context_fetched,
        'embed_result': embed_result,
        'embed_log_items': locals().get('embed_log_items', []),
        'embed_summary': locals().get('embed_summary', None),
        'ran_query': ran_query,
        'error_msg': error_msg,
        'config_path': config_path,
        'CONFIG_PATH_DISPLAY': config_path_display,
        'OPENAI_API_KEY_set': bool(api_key),
        # Masked preview of the key to confirm it reached the template without exposing secrets
        'OPENAI_API_KEY': (f"{api_key[:8]}…" if api_key else ''),
        # Informações de provider e persistência do Chroma
        'EMBEDDING_PROVIDER': (request.POST.get('embed_provider') or getattr(settings, 'EMBEDDING_PROVIDER', 'local')),
        'LOCAL_EMBED_MODEL': getattr(settings, 'LOCAL_EMBED_MODEL', 'all-MiniLM-L6-v2'),
        'CHROMA_PERSIST_PATH_EFFECTIVE': getattr(settings, 'CHROMA_PERSIST_PATH', ''),
        'CHROMA_COLLECTION_NAME_EFFECTIVE': f"{chroma_collection}__" + (request.POST.get('embed_provider') or getattr(settings, 'EMBEDDING_PROVIDER', 'local')),
        'chroma_stats': locals().get('chroma_stats'),
        'chroma_sources_html': locals().get('chroma_sources_html'),
        'active_tab': active_tab,
        'submitted_action': submitted_action,
        'embed_status_key': locals().get('embed_status_key', ''),
        'query_status_key': locals().get('query_status_key', ''),
    }
    return render(request, 'admin/voting/rag_tool.html', context)


@staff_member_required
def votacoes_oficiais_list(request):
    """
    Lista as entradas oficiais de votações por proposição (tabela `voting_proposicaovotacao`).

    Para cada linha, anota a contagem de registros relacionados em `voting_congressmanvote`
    filtrando por `proposicao_votacao_id` correspondente, ou seja, o total de votos individuais
    oficiais obtidos para aquela votação.

    A consulta usa ORM com `annotate(Count('congressmanvote'))`, aproveitando a relação FK
    `CongressmanVote.proposicao_votacao -> ProposicaoVotacao`. Incluímos `select_related('proposicao')`
    para renderização eficiente de dados da proposição na tabela.

    Observação: esta tela é somente leitura e serve para fornecer uma visão rápida das
    votações oficiais já armazenadas, incluindo um indicador de quantos votos individuais
    oficiais foram obtidos para cada votação.
    """
    from django.db.models import Count, Prefetch
    from datetime import datetime
    # Novo: utilitários para subconsultas
    from django.db.models import Exists, OuterRef

    # Executar o loop de obtenção de votações por ano em segundo plano
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'loopObterVotacoes':
            ano_raw = request.POST.get('anoVotacao', datetime.now().year)
            try:
                ano = int(ano_raw)
            except Exception:
                messages.error(request, 'Ano inválido fornecido.')
                ano = None

            if ano is not None:
                lock_key = f"vb:votacoes_oficiais:loop_votacoes:{ano}"
                status_key = f"vb:status:votacoes_oficiais:loop_votacoes:{ano}"

                if not _acquire_lock(lock_key, ttl_seconds=3600):
                    messages.warning(request, f'Já existe uma sincronização em andamento para o ano {ano}.')
                else:
                    def _run_loop_votacoes():
                        try:
                            _set_status(status_key, {'ok': True, 'started': True, 'progress': 0, 'message': f'Iniciando sincronização de votações do ano {ano}...'})
                            from django.db.models import Exists, OuterRef

                            pv_with_votes_qs = (
                                ProposicaoVotacao.objects
                                .filter(proposicao_id=OuterRef('id_proposicao'))
                                .filter(congressmanvote__isnull=False)
                            )

                            proposicoes = (
                                Proposicao.objects
                                .filter(ano=ano)
                                .annotate(has_pv_with_votes=Exists(pv_with_votes_qs))
                                .filter(has_pv_with_votes=False)
                            )

                            total_props = proposicoes.count()
                            total_votacoes = 0
                            processed = 0
                            for proposicao in proposicoes:
                                processed += 1
                                try:
                                    if proposicao.id_proposicao:
                                        count = camara_api.sync_votacoes_for_proposicao(proposicao)
                                        total_votacoes += (count or 0)
                                except Exception:
                                    pass
                                # Atualiza status com progresso
                                _set_status(status_key, {
                                    'ok': True,
                                    'started': True,
                                    'progress': int((processed / max(total_props, 1)) * 100),
                                    'processed': processed,
                                    'total_props': total_props,
                                    'total_votacoes': total_votacoes,
                                    'message': f'Processadas {processed}/{total_props} proposições...'
                                })

                            _set_status(status_key, {
                                'ok': True,
                                'started': True,
                                'completed': True,
                                'processed': processed,
                                'total_props': total_props,
                                'total_votacoes': total_votacoes,
                                'message': f'Sincronização concluída para {total_props} proposições do ano {ano}. Votações obtidas: {total_votacoes}.'
                            })
                        finally:
                            _release_lock(lock_key)

                    threading.Thread(target=_run_loop_votacoes, daemon=True).start()
                    messages.info(request, f'Sincronização iniciada em segundo plano para {ano}. Status key: {status_key}')

    # Carrega votações oficiais e anota a contagem de votos individuais relacionados
    # Prefetch relacionado para VotacaoVoteBem, ordenando pelo mais recente
    vb_queryset = VotacaoVoteBem.objects.order_by('-created_at')

    votacoes_oficiais = (
        ProposicaoVotacao.objects
        .select_related('proposicao')
        .prefetch_related(Prefetch('votacaovotebem', queryset=vb_queryset))
        # Count only real votes: SIM (1) and NÃO (-1)
        .annotate(
            congressman_votes_count=
                Count(
                    'congressmanvote',
                    filter=Q(
                        congressmanvote__voto__in=[1, -1, 2]
                    )
                )
        )
        .order_by('-data_votacao', '-created_at')
    )

    # Paginação para evitar telas muito longas
    paginator = Paginator(votacoes_oficiais, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'title': 'Votações oficiais obtidas',
        'page_obj': page_obj,
        'current_year': datetime.now().year,
    }

    return render(request, 'admin/voting/votacoes_oficiais_list.html', context)


@staff_member_required
def proposicoes_atualizar_temas(request):
    """Atualiza vínculos de temas para proposições que não possuem nenhum tema vinculado.

    1) Buscar IDs de `voting_proposicao` sem correspondência na `voting_proposicao_tema`.
    2) Para cada ID, chamar API: https://dadosabertos.camara.leg.br/api/v2/proposicoes/<id>/temas
    3) Extrair `codTema` e inserir em `voting_proposicao_tema` (tema_id = codTema; proposicao_id = id).
    """
    from django.db.models import Exists, OuterRef
    from .models import Proposicao, ProposicaoTema, Tema

    proposicoes_sem_tema = Proposicao.objects.annotate(
        has_tema=Exists(
            ProposicaoTema.objects.filter(proposicao_id=OuterRef('id_proposicao'))
        )
    ).filter(has_tema=False)

    updated_props = 0
    created_links = 0
    for prop in proposicoes_sem_tema:
        prop_id = prop.id_proposicao
        try:
            url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{prop_id}/temas"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            temas = data.get('dados', [])
        except Exception:
            # Falha ao obter temas para esta proposição, continuar
            continue

        for item in temas:
            cod = item.get('codTema') or item.get('cod') or item.get('cod_tema')
            if cod is None:
                continue
            try:
                codigo_int = int(cod)
            except Exception:
                continue

            # Verifica existência do Tema por codigo
            try:
                tema_obj = Tema.objects.get(codigo=codigo_int)
            except Tema.DoesNotExist:
                # Se o tema não existe na referência, não cria vínculo
                continue

            _, created = ProposicaoTema.objects.get_or_create(
                proposicao_id=prop_id,
                tema_id=tema_obj.codigo,
            )
            if created:
                created_links += 1

        updated_props += 1

    messages.success(
        request,
        f"Atualização concluída: {updated_props} proposições processadas, {created_links} vínculos criados."
    )
    return redirect('gerencial:dashboard')


@admin_required
def votos_oficiais_app(request):
    """Subpágina embutível de Votação oficial com filtros e estatísticas client-side.
    Aceita query param `votacao_id` para carregar votos de uma votação específica.
    """
    votacao_id = request.GET.get('votacao_id')
    votacao = None
    votos_data = []
    if votacao_id:
        try:
            votacao = VotacaoVoteBem.objects.select_related('proposicao_votacao__proposicao').get(pk=int(votacao_id))
            # Votação oficial: por votação específica da proposição
            registros = (
                CongressmanVote.objects
                .select_related('congressman')
                .filter(proposicao_votacao=votacao.proposicao_votacao)
            )
            for r in registros:
                votos_data.append({
                    'nome': r.congressman.nome,
                    'id_cadastro': r.congressman.id_cadastro,
                    'partido': r.congressman.partido or '',
                    'uf': r.congressman.uf or '',
                    'voto': r.get_voto_display_text(),
                })
        except Exception:
            votacao = None

    # Compute prop id for header link reliably
    prefill_prop = request.GET.get('proposicao_id') or ''
    prop_id_for_header = None
    try:
        if votacao and getattr(votacao, 'proposicao_votacao', None) and getattr(votacao.proposicao_votacao, 'proposicao', None):
            pid = getattr(votacao.proposicao_votacao.proposicao, 'id_proposicao', None)
            if pid:
                prop_id_for_header = pid
    except Exception:
        prop_id_for_header = None
    if not prop_id_for_header and prefill_prop:
        prop_id_for_header = prefill_prop

    context = {
        'votacao': votacao,
        'votos_json': json.dumps(votos_data, ensure_ascii=False),
        'prefill_proposicao_id': prefill_prop,
        'prop_id_for_header': prop_id_for_header,
    }
    return render(request, 'admin/voting/votos_oficiais_app.html', context)


@staff_member_required
def votacoes_por_periodo(request):
    """Tela administrativa para obter votações oficiais por período (Câmara API).
    - Exibe inputs `datainicio` e `datafim` com preenchimento automático de 30 dias.
    - Faz consulta client-side à API pública de votações e permite importar votos
      para cada votação que se enquadre nos critérios de descrição.
    """
    context = {
        'default_inicio': request.GET.get('datainicio') or '',
        'default_fim': request.GET.get('datafim') or '',
    }
    return render(request, 'admin/voting/votacoes_por_periodo.html', context)


@staff_member_required
def ajax_import_congress_votes(request):
    """
    Importa votos oficiais de uma votação específica (proposicao_id + sufixo/consulta_id)
    e salva em CongressmanVote. Retorna resumo e lista de votos para atualizar UI.
    """
    try:
        proposicao_id = request.GET.get('proposicao_id')
        consulta_id = request.GET.get('consulta_id') or request.GET.get('votacao_sufixo') or request.GET.get('votacao_id')
        if not proposicao_id:
            return JsonResponse({'ok': False, 'error': 'proposicao_id é obrigatório'}, status=400)
        if not consulta_id:
            return JsonResponse({'ok': False, 'error': 'consulta_id (sufixo da votação) é obrigatório'}, status=400)

        # Normalizar/validar números
        try:
            prop_id_int = int(str(proposicao_id).strip())
            sufixo_int = int(str(consulta_id).strip()) if '-' not in str(consulta_id) else int(str(consulta_id).strip().split('-')[-1])
        except Exception:
            return JsonResponse({'ok': False, 'error': 'IDs inválidos fornecidos'}, status=400)

        # Construir ID de votação no formato esperado pela API: "<proposicao_id>-<sufixo>"
        # Observação: alguns ambientes da API podem não aceitar diretamente o ID composto.
        # Para robustez, faremos fallback consultando as votações da proposição e
        # localizando o ID exato correspondente ao sufixo.
        votacao_composta_id = f"{prop_id_int}-{sufixo_int}"
        api_url_votes = f"{CamaraAPIService.BASE_URL}/votacoes/{votacao_composta_id}/votos"

        # Garantir que a Proposição exista
        proposicao, _ = Proposicao.objects.get_or_create(
            id_proposicao=prop_id_int,
            defaults={
                'titulo': '', 'ementa': '', 'tipo': '', 'numero': 0, 'ano': 0,
            }
        )

        # Buscar detalhes e votos individuais na API com estratégia de fallback
        # 1) Tentar com ID composto diretamente
        detalhes_votacao = {}
        dados_det = {}
        votos_individuais = []

        def _try_fetch(v_id: str):
            """Helper para tentar buscar detalhes e votos por um ID de votação."""
            det = camara_api.get_votacao_details(v_id) or {}
            votes = camara_api.get_votacao_votos(v_id) or []
            return det, votes

        api_success = False  # Flag para indicar sucesso em obter JSON válido da API
        try:
            # Tentativa direta com ID composto; considerar sucesso quando retornos são estruturas válidas
            detalhes_votacao, votos_individuais = _try_fetch(votacao_composta_id)
            dados_det = detalhes_votacao.get('dados') or {}
            if isinstance(detalhes_votacao, dict) and isinstance(votos_individuais, (list, tuple)):
                api_success = True
        except Exception:
            # 2) Fallback: consultar lista de votações da proposição e localizar pelo sufixo
            try:
                lista = camara_api.get_proposicao_votacoes(prop_id_int) or []
                candidato_id = None
                for item in lista:
                    full_id = item.get('id') or item.get('idVotacao') or ''
                    if not full_id:
                        continue
                    try:
                        suf = None
                        if isinstance(full_id, str) and '-' in full_id:
                            suf = int(str(full_id).split('-')[-1])
                        elif isinstance(full_id, int):
                            suf = int(full_id)
                        if suf == sufixo_int:
                            candidato_id = str(full_id)
                            break
                    except Exception:
                        continue
                if candidato_id:
                    api_url_votes = f"{CamaraAPIService.BASE_URL}/votacoes/{candidato_id}/votos"
                    detalhes_votacao, votos_individuais = _try_fetch(candidato_id)
                    dados_det = detalhes_votacao.get('dados') or {}
                    if isinstance(detalhes_votacao, dict) and isinstance(votos_individuais, (list, tuple)):
                        api_success = True
                else:
                    # Sem candidato: manter erro original
                    raise Exception("Votação não encontrada para o sufixo informado")
            except Exception as e2:
                # Se o fallback também falhar, retornar erro para UI com a URL tentada
                return JsonResponse({'ok': False, 'error': f'Erro ao importar: {e2}', 'api_url': api_url_votes}, status=502)

        # Converter placar oficial
        try:
            # Converter placar oficial quando disponível
            sim_count = int(dados_det.get('placarSim') or 0)
            nao_count = int(dados_det.get('placarNao') or 0)
        except Exception:
            sim_count = 0
            nao_count = 0
        if (sim_count == 0 and nao_count == 0) and isinstance(votos_individuais, list):
            for v in votos_individuais:
                tipo = (v.get('tipoVoto') or '').strip().lower()
                if tipo == 'sim':
                    sim_count += 1
                elif tipo in ('não', 'nao'):
                    nao_count += 1

        # Atualizar campos oficiais na ProposicaoVotacao e garantir VotacaoVoteBem associado
        try:
            pv, _ = ProposicaoVotacao.objects.get_or_create(
                proposicao=proposicao,
                votacao_sufixo=sufixo_int,
                defaults={'descricao': (dados_det.get('descricao') or '')}
            )
            pv.sim_oficial = int(sim_count or 0)
            pv.nao_oficial = int(nao_count or 0)
            # Set data_votacao from API details (dataHoraRegistro)
            try:
                registro_str = (dados_det.get('dataHoraRegistro') or '').strip()
                if registro_str:
                    from datetime import datetime
                    from django.utils import timezone
                    dt_reg = datetime.fromisoformat(registro_str.replace('Z', '+00:00'))
                    pv.data_votacao = timezone.make_aware(dt_reg)
            except Exception:
                pass
            pv.save(update_fields=['sim_oficial', 'nao_oficial', 'data_votacao'])

            # Criar/atualizar VotacaoVoteBem para permitir linkagem em UI
            try:
                VotacaoVoteBem.objects.update_or_create(
                    proposicao_votacao=pv,
                    defaults={
                        'titulo': (dados_det.get('descricao') or '')[:200],
                        'resumo': (dados_det.get('descricao') or ''),
                        'ativo': False,
                    }
                )
            except Exception:
                pass
        except Exception:
            pass

        # Mapear e inserir/atualizar votes em CongressmanVote
        from unicodedata import normalize
        def norm(s: str) -> str:
            s = (s or '').strip().lower()
            try:
                return ''.join(c for c in normalize('NFKD', s) if not ord(c) > 127)
            except Exception:
                return s

        congressmen = list(Congressman.objects.only('id', 'id_cadastro', 'nome', 'partido', 'uf'))
        by_id = {cm.id_cadastro: cm for cm in congressmen if cm.id_cadastro}
        by_name = {norm(cm.nome): cm for cm in congressmen if cm.nome}

        def map_voto(tipo: str):
            # Map API vote strings to integer codes.
            # Unknown or absence from API must be treated as explicit absence (3).
            # Dummy (2) is used only by our fallback insertion when there are zero upserts.
            # Special case: "Artigo 17" / "Art. 17" => 4 (abstenção obrigatória do presidente).
            t = (tipo or '').strip().lower()
            if t == 'sim':
                return 1
            if t == 'não' or t == 'nao':
                return -1
            if t == 'abstenção' or t == 'abstencao':
                return 0
            if t == 'artigo 17' or t == 'art. 17':
                return 4
            return 3

        created = 0
        updated = 0
        skipped = 0
        votos_out = []

        for voto in votos_individuais or []:
            # Robustly extract deputy container across API variations
            # Primary key is usually 'deputado', but some payloads nest it under different names
            dep = voto.get('deputado') or {}
            if not dep and isinstance(voto, dict):
                # Heuristic: pick the first nested dict whose key contains 'deput'
                try:
                    cand_keys = [k for k in voto.keys() if isinstance(k, str) and 'deput' in k.lower()]
                    for ck in cand_keys:
                        if isinstance(voto.get(ck), dict):
                            dep = voto.get(ck) or {}
                            break
                except Exception:
                    dep = {}
            dep_id = (
                dep.get('id')
                or voto.get('idDeputado')
                or voto.get('deputadoId')
                or voto.get('id_deputado')
            )
            # fallback: procurar qualquer chave que pareça id de deputado
            if dep_id is None and isinstance(voto, dict):
                try:
                    for k, v in voto.items():
                        kl = k.lower() if isinstance(k, str) else ''
                        if 'id' in kl and 'deput' in kl and v is not None:
                            dep_id = v
                            break
                except Exception:
                    pass
            try:
                dep_id = int(dep_id) if dep_id is not None else None
            except Exception:
                dep_id = None

            nome_dep = (
                dep.get('nome')
                or voto.get('nome')
                or voto.get('deputadoNome')
                or voto.get('nome_deputado')
            )
            # fallback: procurar nome em qualquer chave
            if not nome_dep and isinstance(voto, dict):
                try:
                    for k, v in voto.items():
                        kl = k.lower() if isinstance(k, str) else ''
                        if 'nome' in kl and 'deput' in kl and v:
                            nome_dep = v
                            break
                except Exception:
                    pass

            voto_tipo = voto.get('tipoVoto') or voto.get('tipo_voto')
            voto_val = map_voto(voto_tipo)

            cm = None
            if dep_id and dep_id in by_id:
                cm = by_id.get(dep_id)
            elif nome_dep:
                cm = by_name.get(norm(nome_dep))
            if not cm and dep_id:
                try:
                    cm = Congressman.objects.create(
                        id_cadastro=dep_id,
                        nome=nome_dep or f"Deputado {dep_id}",
                        partido=(dep.get('siglaPartido') or ''),
                        uf=(dep.get('siglaUf') or ''),
                        ativo=True,
                    )
                    by_id[dep_id] = cm
                    by_name[norm(cm.nome)] = cm
                    created += 0  # only count votes below
                except Exception:
                    cm = None

            if not cm:
                skipped += 1
                continue

            pv, _ = ProposicaoVotacao.objects.get_or_create(
                proposicao=proposicao,
                votacao_sufixo=sufixo_int,
                defaults={'descricao': (dados_det.get('descricao') or '')}
            )
            obj, was_created = CongressmanVote.objects.update_or_create(
                congressman=cm,
                proposicao_votacao=pv,
                defaults={'voto': voto_val}
            )
            if was_created:
                created += 1
            else:
                updated += 1

            votos_out.append({
                'nome': cm.nome,
                'id_cadastro': cm.id_cadastro,
                'partido': cm.partido or '',
                'uf': cm.uf or '',
                'voto': obj.get_voto_display_text(),
            })

        # Caso nenhum voto tenha sido inserido/atualizado e a API tenha retornado JSON
        # corretamente (sem erro), inserir um registro dummy. Se houver qualquer
        # erro na chamada à API, NÃO insere dummy.
        try:
            if api_success and (created + updated) == 0:
                # Garantir ProposicaoVotacao existente
                try:
                    pv_dummy = pv
                except Exception:
                    pv_dummy, _ = ProposicaoVotacao.objects.get_or_create(
                        proposicao=proposicao,
                        votacao_sufixo=sufixo_int,
                        defaults={'descricao': (dados_det.get('descricao') or '')}
                    )

                # Obter/criar congressista dummy com id_cadastro negativo para evitar conflito
                cm_dummy, _ = Congressman.objects.get_or_create(
                    id_cadastro=-1,
                    defaults={
                        'nome': 'Dummy Deputado',
                        'partido': '',
                        'uf': '',
                        'ativo': True,
                    }
                )

                # Inserir voto dummy com valor 2 (Dummy) para não alterar placares
                obj_dummy, was_created_dummy = CongressmanVote.objects.update_or_create(
                    congressman=cm_dummy,
                    proposicao_votacao=pv_dummy,
                    defaults={'voto': 2}
                )
                if was_created_dummy:
                    created += 1
                else:
                    updated += 1
                votos_out.append({
                    'nome': cm_dummy.nome,
                    'id_cadastro': cm_dummy.id_cadastro,
                    'partido': cm_dummy.partido or '',
                    'uf': cm_dummy.uf or '',
                    'voto': obj_dummy.get_voto_display_text(),
                    'dummy': True,
                })
        except Exception:
            # Se o dummy falhar, não interromper a resposta; apenas seguir com contadores atuais
            pass

        return JsonResponse({
            'ok': True,
            'proposicao_id': prop_id_int,
            'consulta_id': sufixo_int,
            'votacao_id': votacao_composta_id,
            'sim': sim_count,
            'nao': nao_count,
            'created': created,
            'updated': updated,
            'skipped': skipped,
            'votos': votos_out,
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Erro ao importar: {e}', 'api_url': api_url_votes}, status=502)


@staff_member_required
def congressistas_update(request):
    """Update Congressman table from Câmara API with optional idLegislatura param (default 57).
    Fetches all pages, deduplicates by id (keep last), aggregates party siglas history.
    """
    id_legislatura = request.GET.get('idLegislatura')
    if not id_legislatura:
        id_legislatura = '57'

    created = 0
    updated = 0
    errors = 0
    api_url = (
        f"https://dadosabertos.camara.leg.br/api/v2/deputados"
    )
    params = {
        'idLegislatura': id_legislatura,
        'ordem': 'ASC',
        'ordenarPor': 'nome',
        'itens': 100
    }

    result_summary = None
    if request.GET.get('run') == '1':
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
            # Fetch all pages
            page = 1
            itens = 100
            deputados_all = []
            while True:
                params_page = {
                    'idLegislatura': id_legislatura,
                    'ordem': 'ASC',
                    'ordenarPor': 'nome',
                    'itens': itens,
                    'pagina': page,
                }
                resp = requests.get("https://dadosabertos.camara.leg.br/api/v2/deputados", params=params_page, headers=headers, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                dados = data.get('dados', [])
                if not dados:
                    break
                deputados_all.extend(dados)
                links = data.get('links', [])
                has_next = any(l.get('rel') == 'next' for l in links)
                if not has_next:
                    break
                page += 1
                if page > 1000:
                    break

            # Aggregate by id (keep last) and collect party siglas
            agg = {}
            order_counter = 0
            for dep in deputados_all:
                dep_id = dep.get('id')
                nome = dep.get('nome')
                partido = dep.get('siglaPartido') or ''
                uf = dep.get('siglaUf') or ''
                foto_url = dep.get('urlFoto') or ''
                if dep_id is None or not nome:
                    continue
                order_counter += 1
                entry = agg.get(dep_id, {'nome': nome, 'uf': uf, 'foto_url': foto_url, 'partido': partido, 'siglas': [], 'order': order_counter})
                if partido and partido not in entry['siglas']:
                    entry['siglas'].append(partido)
                entry['nome'] = nome
                entry['uf'] = uf
                entry['foto_url'] = foto_url or entry['foto_url']
                entry['partido'] = partido or entry['partido']
                entry['order'] = order_counter
                agg[dep_id] = entry

            # Persist aggregated deputies
            for dep_id, entry in agg.items():
                try:
                    nome = entry['nome']
                    partido = entry['partido']
                    uf = entry['uf']
                    foto_url = entry['foto_url']
                    partidos_hist = ", ".join(entry['siglas']) if entry['siglas'] else None
                    try:
                        cm = Congressman.objects.get(id_cadastro=dep_id)
                        cm.nome = nome
                        cm.partido = partido
                        cm.uf = uf
                        cm.foto_url = foto_url or cm.foto_url
                        cm.partidos_historico = partidos_hist
                        cm.ativo = True
                        cm.save()
                        updated += 1
                    except Congressman.DoesNotExist:
                        cm = Congressman.objects.filter(nome__iexact=nome).first()
                        if cm:
                            cm.id_cadastro = dep_id
                            cm.partido = partido
                            cm.uf = uf
                            cm.foto_url = foto_url or cm.foto_url
                            cm.partidos_historico = partidos_hist
                            cm.ativo = True
                            cm.save()
                            updated += 1
                        else:
                            Congressman.objects.create(
                                id_cadastro=dep_id,
                                nome=nome,
                                partido=partido,
                                uf=uf,
                                foto_url=foto_url or None,
                                partidos_historico=partidos_hist,
                                ativo=True,
                            )
                            created += 1
                except Exception:
                    errors += 1

            result_summary = {
                'total_api': len(deputados_all),
                'created': created,
                'updated': updated,
                'errors': errors,
                'id_legislatura': id_legislatura,
            }
            messages.success(request, f"Deputados atualizados (idLegislatura {id_legislatura}): total {len(deputados_all)}, criados {created}, atualizados {updated}, erros {errors}.")
        except Exception as e:
            messages.error(request, f"Erro ao atualizar deputados: {e}")

    context = {
        'id_legislatura': id_legislatura,
        'result_summary': result_summary,
    }
    return render(request, 'admin/voting/congressistas_update.html', context)


@staff_member_required
def votacao_obter_votacao(request, pk):
    """Fetch official voting for the proposition linked to a VotacaoDisponivel and store individual votes."""
    votacao = get_object_or_404(VotacaoDisponivel, pk=pk)
    proposicao = None
    try:
        proposicao = votacao.proposicao_votacao.proposicao
    except Exception:
        proposicao = None
    if not proposicao or not proposicao.id_proposicao:
        messages.error(request, 'Proposição sem id_proposicao; não é possível consultar votação oficial.')
        return redirect('gerencial:votacao_edit', pk=pk)

    try:
        logger = logging.getLogger(__name__)
        def log_step(message, data=None):
            prefix = f"[VotacaoImport id={votacao.id}] "
            if data is not None:
                try:
                    line = prefix + message + " | " + json.dumps(data, ensure_ascii=False)
                except Exception:
                    line = prefix + message + f" | {data}"
            else:
                line = prefix + message
            dev_log(line)
            try:
                logger.info(line)
            except Exception:
                pass
        log_step("Starting import flow", {"proposicao_id_proposicao": proposicao.id_proposicao})
        # Step 1: get all votações of the proposição
        votos_list = camara_api.get_proposicao_votacoes(proposicao.id_proposicao)
        log_step("Fetched votações list for proposição", {"count": len(votos_list) if isinstance(votos_list, list) else None})

        if not votos_list:
            messages.error(request, 'Nenhuma votação oficial encontrada para esta proposição.')
            return redirect('gerencial:votacao_edit', pk=pk)

        # Step 2: find main votação by descricao contains aprov/rejeit + proposta
        main_votacao_id = None
        for v in votos_list:
            desc = (v.get('descricao') or '').lower()
            # Critérios alinhados com a tela client-side (votacoes_por_periodo.html):
            # - contém "aprovad" OU "rejeitad"
            # - e contém "turno" OU "emenda" OU "projeto"
            # - e contém "total"
            # - e NÃO contém "requerimento"
            if (("aprovad" in desc or "rejeitad" in desc) and
                ("turno" in desc or "emenda" in desc or "projeto" in desc) and
                ("total" in desc) and
                ("requerimento" not in desc)):
                main_votacao_id = v.get('id')
                break
        # Fallback: first item
        if not main_votacao_id:
            main_votacao_id = votos_list[0].get('id')

        if not main_votacao_id:
            messages.error(request, 'Não foi possível determinar a votação principal.')
            return redirect('gerencial:votacao_edit', pk=pk)
        log_step("Selected main votação", {"main_votacao_id": main_votacao_id})

        # Step 3: get voting details (for official counts) and individual votes
        detalhes_votacao = camara_api.get_votacao_details(main_votacao_id) or {}
        dados_det = detalhes_votacao.get('dados') or {}
        votos_individuais = camara_api.get_votacao_votos(main_votacao_id)
        log_step("Fetched votação details and individual votes", {
            "details_keys": list(detalhes_votacao.keys()) if isinstance(detalhes_votacao, dict) else None,
            "dados_det_keys": list(dados_det.keys()) if isinstance(dados_det, dict) else None,
            "individual_votes_count": len(votos_individuais) if isinstance(votos_individuais, list) else None,
        })
        try:
            sample = []
            for i in range(min(3, len(votos_individuais) if isinstance(votos_individuais, list) else 0)):
                v = votos_individuais[i]
                dep_sample = v.get('deputado') if isinstance(v, dict) else None
                sample.append({
                    'keys': list(v.keys()) if isinstance(v, dict) else None,
                    'deputado_keys': list(dep_sample.keys()) if isinstance(dep_sample, dict) else None,
                    'tipoVoto': v.get('tipoVoto') if isinstance(v, dict) else None,
                })
            if sample:
                log_step("Vote payload sample", {"items": sample})
        except Exception:
            pass

        # Extract numeric congress vote id (e.g., from '2270800-160' -> 160)
        congress_vote_numeric_id = None
        try:
            if isinstance(main_votacao_id, str) and '-' in main_votacao_id:
                congress_vote_numeric_id = int(main_votacao_id.split('-')[-1])
            elif isinstance(main_votacao_id, (int, float)):
                congress_vote_numeric_id = int(main_votacao_id)
        except Exception:
            congress_vote_numeric_id = None

        # Map vote string to integers
        def map_voto(tipo: str):
            # Map API vote strings to integer codes.
            # Unknown/absence should map to 3; dummy (2) is reserved for fallback only.
            # Special case: "Artigo 17" / "Art. 17" => 4 (abstenção obrigatória do presidente).
            t = (tipo or '').strip().lower()
            if t == 'sim':
                return 1
            if t == 'não' or t == 'nao':
                return -1
            if t == 'abstenção' or t == 'abstencao':
                return 0
            if t == 'artigo 17' or t == 'art. 17':
                return 4
            return 3
        # Count SIM/NÃO independently of DB matches; prefer official counts from details
        # Fallback to computing from individual votes when details are missing
        sim_count = int(dados_det.get('placarSim') or 0)
        nao_count = int(dados_det.get('placarNao') or 0)
        if (sim_count == 0 and nao_count == 0) and votos_individuais:
            sim_count = 0
            nao_count = 0
            for v in votos_individuais:
                tipo = (v.get('tipoVoto') or '').strip().lower()
                if tipo == 'sim':
                    sim_count += 1
                elif tipo in ('não', 'nao'):
                    nao_count += 1
        log_step("Computed official counts", {"placarSim": sim_count, "placarNao": nao_count})

        # Prepare congressman lookup maps to reduce skipping
        from unicodedata import normalize
        def norm(s: str) -> str:
            s = (s or '').strip().lower()
            try:
                return ''.join(c for c in normalize('NFKD', s) if not ord(c) > 127)
            except Exception:
                return s

        congressmen = list(Congressman.objects.only('id', 'id_cadastro', 'nome'))
        by_id = {cm.id_cadastro: cm for cm in congressmen if cm.id_cadastro}
        by_name = {norm(cm.nome): cm for cm in congressmen if cm.nome}

        created = 0
        updated = 0
        skipped = 0
        auto_created_cm = 0

        for voto in votos_individuais:
            dep = voto.get('deputado') or {}
            # Heuristic: if 'deputado' key missing, look for any key containing 'deput'
            if not dep and isinstance(voto, dict):
                try:
                    cand_keys = [k for k in voto.keys() if isinstance(k, str) and 'deput' in k.lower()]
                    for ck in cand_keys:
                        if isinstance(voto.get(ck), dict):
                            dep = voto.get(ck) or {}
                            log_step("Detected alternative deputy container", {"key": ck})
                            break
                except Exception:
                    pass
            # Robust deputy id/name extraction across possible API variations
            dep_id = (
                dep.get('id')
                or voto.get('idDeputado')
                or voto.get('deputadoId')
                or voto.get('id_deputado')
            )
            # Generic scan for any key that looks like deputy id
            if dep_id is None and isinstance(voto, dict):
                try:
                    for k, v in voto.items():
                        kl = k.lower() if isinstance(k, str) else ''
                        if 'id' in kl and 'deput' in kl and v is not None:
                            dep_id = v
                            log_step("Detected deputy id from generic key", {"key": k, "value": v})
                            break
                except Exception:
                    pass
            try:
                if dep_id is not None:
                    dep_id = int(dep_id)
            except Exception:
                pass
            nome_dep = (
                dep.get('nome')
                or voto.get('nome')
                or voto.get('deputadoNome')
                or voto.get('nome_deputado')
            )
            if not nome_dep and isinstance(voto, dict):
                try:
                    for k, v in voto.items():
                        kl = k.lower() if isinstance(k, str) else ''
                        if 'nome' in kl and 'deput' in kl and v:
                            nome_dep = v
                            log_step("Detected deputy name from generic key", {"key": k, "value": v})
                            break
                except Exception:
                    pass
            voto_tipo = voto.get('tipoVoto') or voto.get('tipo_voto')
            voto_val = map_voto(voto_tipo)

            cm = None
            if dep_id and dep_id in by_id:
                cm = by_id.get(dep_id)
            elif nome_dep:
                cm = by_name.get(norm(nome_dep))
            if not cm:
                # As a robustness fallback, auto-create congressman from vote data when ID is present
                if dep_id:
                    try:
                        cm = Congressman.objects.create(
                            id_cadastro=dep_id,
                            nome=nome_dep or f"Deputado {dep_id}",
                            partido=(dep.get('siglaPartido') or ''),
                            uf=(dep.get('siglaUf') or ''),
                            ativo=True,
                        )
                        by_id[dep_id] = cm
                        by_name[norm(cm.nome)] = cm
                        auto_created_cm += 1
                        log_step("Auto-created missing congressman", {"id_cadastro": dep_id, "nome": cm.nome, "partido": cm.partido, "uf": cm.uf})
                    except Exception:
                        cm = None
                        log_step("Failed to auto-create congressman", {"id_cadastro": dep_id, "nome": nome_dep})
                if not cm:
                    skipped += 1
                    log_step("Skipped vote: no congressman match", {"dep_id": dep_id, "nome_dep": nome_dep, "tipoVoto": voto_tipo, "raw_vote": voto})
                    continue

            pv, _ = ProposicaoVotacao.objects.get_or_create(
                proposicao=proposicao,
                votacao_sufixo=congress_vote_numeric_id,
                defaults={'descricao': ''}
            )
            obj, was_created = CongressmanVote.objects.update_or_create(
                congressman=cm,
                proposicao_votacao=pv,
                defaults={'voto': voto_val}
            )
            if was_created:
                created += 1
                log_step("Inserted CongressmanVote", {"congressman_id": cm.id, "id_cadastro": cm.id_cadastro, "voto": voto_val})
            else:
                updated += 1
                log_step("Updated CongressmanVote", {"congressman_id": cm.id, "id_cadastro": cm.id_cadastro, "voto": voto_val})

        # Update official counts on ProposicaoVotacao (not on VotacaoDisponivel)
        try:
            pv_counts, _ = ProposicaoVotacao.objects.get_or_create(
                proposicao=proposicao,
                votacao_sufixo=congress_vote_numeric_id,
                defaults={'descricao': ''}
            )
            pv_counts.sim_oficial = sim_count
            pv_counts.nao_oficial = nao_count
            # Set data_votacao using dataHoraRegistro when available in contexto
            try:
                registro_str = (dados_det.get('dataHoraRegistro') or '').strip()
                if registro_str:
                    from datetime import datetime
                    from django.utils import timezone
                    dt_reg = datetime.fromisoformat(registro_str.replace('Z', '+00:00'))
                    pv_counts.data_votacao = timezone.make_aware(dt_reg)
            except Exception:
                pass
            pv_counts.save(update_fields=['sim_oficial', 'nao_oficial', 'data_votacao'])
            log_step("Saved official counts on ProposicaoVotacao", {"proposicao_id": proposicao.pk, "votacao_sufixo": congress_vote_numeric_id, "sim_oficial": sim_count, "nao_oficial": nao_count})
        except Exception:
            pass

        log_step("Import summary", {"novos": created, "atualizados": updated, "ignorados": skipped, "deputados_criados": auto_created_cm})
        messages.success(
            request,
            f"Votação oficial importada (id {main_votacao_id}). SIM: {sim_count}, NÃO: {nao_count}, "
            f"novos: {created}, atualizados: {updated}, ignorados: {skipped}, deputados criados: {auto_created_cm}."
        )
    except Exception as e:
        messages.error(request, f"Erro ao obter votação oficial: {e}")

    return redirect('gerencial:votacao_edit', pk=pk)

@admin_required
def proposicoes_statistics(request):
    """
    Display statistics about propositions similar to PHP admin
    """
    # Aggregations
    por_tipo = (
        Proposicao.objects
        .values('tipo')
        .annotate(count=Count('id_proposicao'))
        .order_by('-count')
    )

    # Base aggregation: total proposições por ano
    base_por_ano = list(
        Proposicao.objects
        .values('ano')
        .annotate(count=Count('id_proposicao'))
        .order_by('-ano')
    )

    # Additional aggregations per year
    pv_por_ano_qs = (
        ProposicaoVotacao.objects
        .values(ano=F('proposicao__ano'))
        .annotate(pv_count=Count('id'))
    )
    vvb_por_ano_qs = (
        VotacaoVoteBem.objects
        .values(ano=F('proposicao_votacao__proposicao__ano'))
        .annotate(vvb_count=Count('id'))
    )
    cv_por_ano_qs = (
        CongressmanVote.objects
        .values(ano=F('proposicao_votacao__proposicao__ano'))
        .annotate(cv_count=Count('id'))
    )

    # Build maps for quick lookup
    pv_map = {row['ano']: row['pv_count'] for row in pv_por_ano_qs}
    vvb_map = {row['ano']: row['vvb_count'] for row in vvb_por_ano_qs}
    cv_map = {row['ano']: row['cv_count'] for row in cv_por_ano_qs}

    # Merge counts into the base per-year list
    por_ano = []
    for item in base_por_ano:
        ano = item.get('ano')
        merged = {
            'ano': ano,
            'count': item.get('count', 0),
            'pv_count': pv_map.get(ano, 0),
            'vvb_count': vvb_map.get(ano, 0),
            'cv_count': cv_map.get(ano, 0),
        }
        por_ano.append(merged)

    por_estado = (
        Proposicao.objects
        .values('estado')
        .annotate(count=Count('id_proposicao'))
        .order_by('-count')
    )

    # Counts respecting the new relationships (Proposicao -> ProposicaoVotacao -> VotacaoVoteBem)
    total = Proposicao.objects.count()
    com_votacao = (
        Proposicao.objects
        .filter(votacoes_oficiais__votacaovotebem__isnull=False)
        .distinct()
        .count()
    )
    sem_votacao = max(total - com_votacao, 0)

    stats = {
        'por_tipo': por_tipo,
        'por_ano': por_ano,
        'por_estado': por_estado,
        'com_votacao': com_votacao,
        'sem_votacao': sem_votacao,
    }
    
    return render(request, 'admin/voting/proposicoes_statistics.html', {'stats': stats})


@admin_required
def proposicoes_list(request):
    """
    List and manage propositions
    """
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    # Get search parameters
    search = request.GET.get('search', '')
    tipo_filter = request.GET.get('tipo', '')
    ano_filter = request.GET.get('ano', '')
    estado_filter = request.GET.get('estado', '')
    
    # Base queryset
    proposicoes = Proposicao.objects.all().order_by('-ano', '-numero')
    
    # Apply filters
    if search:
        # Multi-word filter: enforce AND across words; each word must match
        # at least one column. We search across common columns displayed in
        # the table: titulo, ementa, estado, tipo, and numeric fields.
        #
        # Portuguese-friendly matching:
        # - Handle simple gender/plural variations (transformado/transformada, normas/norma).
        # - Numeric terms match numero/ano/id_proposicao using equality.
        #
        # This makes searches like "transformada norma" match rows with
        # "Transformado em Norma Jurídica" in the Estado column.
        terms = [t for t in re.split(r"\s+", search.strip()) if t]
        for term in terms:
            t = term.strip()
            base_variants = set()
            # Original term
            base_variants.add(t)
            tl = t.lower()
            # Handle plural endings 'os'/'as' by removing them
            if tl.endswith('os') or tl.endswith('as'):
                base_variants.add(tl[:-2])
            # Handle gender endings 'o'/'a' by removing last char
            if tl.endswith('o') or tl.endswith('a'):
                base_variants.add(tl[:-1])
                # Swap gender to catch the opposite form
                swapped = tl[:-1] + ('a' if tl.endswith('o') else 'o')
                base_variants.add(swapped)

            # Build a Q that matches any variant in any of the searchable fields
            term_q = Q()
            for v in base_variants:
                term_q |= (
                    Q(titulo__icontains=v) |
                    Q(ementa__icontains=v) |
                    Q(estado__icontains=v) |
                    Q(tipo__icontains=v)
                )

                # Numeric match: if variant looks like a number, try equality
                # on numero, ano e id_proposicao.
                if v.isdigit():
                    try:
                        vi = int(v)
                        term_q |= (
                            Q(numero=vi) |
                            Q(ano=vi) |
                            Q(id_proposicao=vi)
                        )
                    except Exception:
                        # Ignore conversion errors and continue with text filters
                        pass

                # Keep legacy support: if DB allows, also attempt icontains on id_proposicao as text
                term_q |= Q(id_proposicao__icontains=v)

            # AND across terms: progressively narrow the queryset
            proposicoes = proposicoes.filter(term_q)
    
    if tipo_filter:
        proposicoes = proposicoes.filter(tipo=tipo_filter)
    
    if ano_filter:
        proposicoes = proposicoes.filter(ano=ano_filter)
    
    if estado_filter:
        proposicoes = proposicoes.filter(estado=estado_filter)
    
    # Pagination
    # Allow the page size to be adjusted via querystring param `per_page`.
    # We validate it against a small set of allowed values to avoid
    # excessively large responses impacting performance.
    try:
        per_page_raw = request.GET.get('per_page', '25')
        per_page = int(per_page_raw)
    except Exception:
        per_page = 25
    if per_page not in (10, 25, 50, 100, 200):
        per_page = 25

    paginator = Paginator(proposicoes, per_page)  # Show N propositions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Annotate preferred votação info for each proposição on the current page
    # Prefer an active votação if present; otherwise use the first available
    try:
        for p in page_obj:
            # Preferida: tentativa de identificar votação disponível associada (novo modelo VotacaoVoteBem)
            qs = VotacaoVoteBem.objects.filter(proposicao_votacao__proposicao_id=p.id_proposicao)
            preferred = qs.filter(ativo=True).order_by('id').first() or qs.order_by('id').first()
            p.preferred_votacao_id = preferred.id if preferred else None
            p.has_votacao = qs.exists()
            # Use window checks (no_ar_desde/no_ar_ate) in addition to 'ativo'
            # to determine if the votação is active right now.
            p.preferred_votacao_is_active = preferred.is_active() if preferred else False

            # Flag: existe algum registro em ProposicaoVotacao para esta proposição?
            p.has_proposicao_votacao = ProposicaoVotacao.objects.filter(proposicao_id=p.id_proposicao).exists()
    except Exception:
        # In case of any unexpected error, ensure attributes exist to avoid template errors
        for p in page_obj:
            p.preferred_votacao_id = None
            p.has_votacao = False
            p.has_proposicao_votacao = False
            p.preferred_votacao_is_active = False
    
    # Get filter options
    tipos_disponiveis = Proposicao.objects.values_list('tipo', flat=True).distinct().order_by('tipo')
    anos_disponiveis = Proposicao.objects.values_list('ano', flat=True).distinct().order_by('-ano')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_filter': tipo_filter,
        'ano_filter': ano_filter,
        'estado_filter': estado_filter,
        'tipos_disponiveis': tipos_disponiveis,
        'anos_disponiveis': anos_disponiveis,
        'total_proposicoes': proposicoes.count(),
        # Expose current page size to the template so we can persist the selection
        'per_page': per_page,
    }
    
    return render(request, 'admin/voting/proposicoes_list.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def proposicao_edit(request, pk):
    """
    View para editar uma proposição específica
    """
    try:
        proposicao = get_object_or_404(Proposicao, pk=pk)
    except:
        messages.error(request, 'Proposição não encontrada.')
        return redirect('gerencial:proposicoes_list')
    
    if request.method == 'POST':
        # Processar formulário de edição
        titulo = request.POST.get('titulo', '').strip()
        ementa = request.POST.get('ementa', '').strip()
        tipo = request.POST.get('tipo', '').strip()
        numero = request.POST.get('numero', '').strip()
        ano = request.POST.get('ano', '').strip()
        estado = request.POST.get('estado', '').strip()
        conhecida_por = request.POST.get('conhecida_por', '').strip()
        
        # Validações básicas
        if not titulo:
            messages.error(request, 'Título é obrigatório.')
        elif not tipo:
            messages.error(request, 'Tipo é obrigatório.')
        elif not numero:
            messages.error(request, 'Número é obrigatório.')
        elif not ano:
            messages.error(request, 'Ano é obrigatório.')
        else:
            try:
                # Atualizar proposição
                proposicao.titulo = titulo
                proposicao.ementa = ementa
                proposicao.tipo = tipo
                proposicao.numero = int(numero)
                proposicao.ano = int(ano)
                proposicao.estado = estado
                proposicao.conhecida_por = conhecida_por
                proposicao.save()
                
                messages.success(request, f'Proposição "{proposicao.titulo}" atualizada com sucesso!')
                return redirect('gerencial:proposicoes_list')
                
            except ValueError:
                messages.error(request, 'Número e ano devem ser valores numéricos.')
            except Exception as e:
                messages.error(request, f'Erro ao salvar proposição: {str(e)}')
    
    # Buscar votações relacionadas via nova relação Proposicao -> ProposicaoVotacao -> VotacaoVoteBem
    # Seleciona VotacaoVoteBem vinculadas à proposição por meio de ProposicaoVotacao
    votacoes = (
        VotacaoVoteBem.objects
        .select_related('proposicao_votacao__proposicao')
        .filter(proposicao_votacao__proposicao_id=proposicao.id_proposicao)
        .order_by('-no_ar_desde')
    )
    
    context = {
        'proposicao': proposicao,
        'votacoes': votacoes,
        'title': f'Editar Proposição - {proposicao.tipo} {proposicao.numero}/{proposicao.ano}',
    }
    
    return render(request, 'admin/voting/proposicao_edit.html', context)

@staff_member_required
def proposicao_edit_choose(request):
    """
    Página simples para localizar uma proposição e redirecionar para edição.
    Aceita `pk` (ID interno) ou `id_proposicao` (ID da Câmara).
    """
    context = {
        'title': 'Editar Proposição',
    }
    if request.method == 'POST':
        pk_raw = (request.POST.get('pk') or '').strip()
        ext_raw = (request.POST.get('id_proposicao') or '').strip()
        target = None
        try:
            if pk_raw:
                target = Proposicao.objects.get(pk=int(pk_raw))
            elif ext_raw:
                target = Proposicao.objects.filter(id_proposicao=int(ext_raw)).first()
        except Exception:
            target = None

        if target:
            return redirect('gerencial:proposicao_edit', pk=target.pk)
        else:
            messages.error(request, 'Proposição não encontrada. Informe um ID válido.')

    return render(request, 'admin/voting/proposicao_edit_choose.html', context)

@staff_member_required
def votacao_edit(request, pk):
    """Edita uma votação disponível OU lista as votações por proposição.

    - Se existir VotacaoVoteBem com id=pk: renderiza a página de edição tradicional.
    - Caso contrário: interpreta pk como id_proposicao e lista todas as votações
      (VotacaoDisponivel) vinculadas via ProposicaoVotacao para essa proposição,
      permitindo editar cada uma individualmente.
    """

    try:
        # Caminho tradicional: editar uma única VotacaoVoteBem por ID
        votacao = VotacaoVoteBem.objects.get(pk=pk)

        if request.method == 'POST':
            # Deleção (confirmação feita no cliente via prompt)
            if request.POST.get('delete') == '1':
                try:
                    titulo_prev = votacao.titulo
                    votacao.delete()
                    messages.success(request, f'Votação "{titulo_prev}" apagada com sucesso.')
                    return redirect('gerencial:votacoes_management')
                except Exception as e:
                    messages.error(request, f'Erro ao apagar votação: {str(e)}')
                    return redirect('gerencial:votacao_edit', pk=pk)

            # Handle form submission
            votacao.titulo = request.POST.get('titulo', votacao.titulo)
            votacao.resumo = request.POST.get('resumo', votacao.resumo)
            # New field: explicacao (detailed explanation shown to users)
            # Accepts optional long text; keep existing value when missing from POST
            votacao.explicacao = request.POST.get('explicacao', votacao.explicacao)

            # Handle datetime fields
            data_hora_votacao = request.POST.get('data_hora_votacao')
            if data_hora_votacao:
                try:
                    dt_voto = timezone.datetime.fromisoformat(data_hora_votacao.replace('T', ' '))
                    # If linked to an official ProposicaoVotacao, update its official vote record date
                    if getattr(votacao, 'proposicao_votacao_id', None):
                        try:
                            pv = votacao.proposicao_votacao
                            pv.data_votacao = dt_voto
                            pv.save(update_fields=['data_votacao'])
                        except Exception:
                            # Fallback: set on VotacaoVoteBem if updating PV fails
                            votacao.data_hora_votacao = dt_voto
                    else:
                        # No official link; keep date on VotacaoVoteBem
                        votacao.data_hora_votacao = dt_voto
                except ValueError:
                    pass

            no_ar_desde = request.POST.get('no_ar_desde')
            if no_ar_desde:
                try:
                    votacao.no_ar_desde = timezone.datetime.fromisoformat(no_ar_desde.replace('T', ' '))
                except ValueError:
                    pass

            no_ar_ate = request.POST.get('no_ar_ate')
            if no_ar_ate:
                try:
                    votacao.no_ar_ate = timezone.datetime.fromisoformat(no_ar_ate.replace('T', ' '))
                except ValueError:
                    pass
            else:
                votacao.no_ar_ate = None

            # Official counts are stored on ProposicaoVotacao and populated via import; ignore any POST for them

            # Handle boolean field
            votacao.ativo = request.POST.get('ativo') == 'on'

            try:
                votacao.save()
                messages.success(request, 'Votação atualizada com sucesso!')
                return redirect('gerencial:votacao_edit', pk=pk)
            except Exception as e:
                messages.error(request, f'Erro ao salvar votação: {str(e)}')

        # Get related votes count
        total_votos = votacao.get_total_votos_populares() if hasattr(votacao, 'get_total_votos_populares') else 0

        # Provide related proposição details for template header convenience
        try:
            proposicao = (
                votacao.proposicao_votacao.proposicao
                if getattr(votacao, 'proposicao_votacao', None) and getattr(votacao.proposicao_votacao, 'proposicao', None)
                else None
            )
        except Exception:
            proposicao = None

        context = {
            'votacao': votacao,
            'proposicao': proposicao,
            'total_votos': total_votos,
            # Exibir o título completo sem truncamento para evitar confusão na identificação
            # do registro. O corte anterior ([:50] + "...") escondia informações úteis.
            'title': f'Editar Votação: {votacao.titulo}'
        }

        return render(request, 'admin/voting/votacao_edit.html', context)

    except VotacaoVoteBem.DoesNotExist:
        # Novo caminho: listar/gerenciar votações pela proposição (pk como id_proposicao)
        # Em vez de 404 direto, mostre mensagem amigável e redirecione
        try:
            proposicao = Proposicao.objects.get(pk=pk)
        except Proposicao.DoesNotExist:
            messages.error(request, f'Proposição com ID {pk} não encontrada.')
            return redirect('gerencial:proposicoes_list')
        # Seleciona todas as votações disponíveis associadas via ProposicaoVotacao
        votacoes = (
            VotacaoVoteBem.objects
            .select_related('proposicao_votacao__proposicao')
            .filter(proposicao_votacao__proposicao_id=pk)
            .order_by('-no_ar_desde')
        )

        context = {
            'proposicao': proposicao,
            'votacoes': votacoes,
            'title': f'Votações Votebem da Proposição: {proposicao.tipo} {proposicao.numero}/{proposicao.ano}',
        }

        return render(request, 'admin/voting/votacao_edit_by_proposicao.html', context)

@staff_member_required
def votacoes_management(request):
    """
    Manage voting sessions - activate/deactivate, view statistics
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create_votacao':
            proposicao_id = request.POST.get('proposicao_id')
            titulo = request.POST.get('titulo')
            resumo = request.POST.get('resumo')
            
            if proposicao_id and titulo:
                try:
                    # Fetch by new primary key (id_proposicao)
                    proposicao = Proposicao.objects.get(pk=proposicao_id)
                    votacao = VotacaoDisponivel.objects.create(
                        proposicao_votacao=None,
                        titulo=titulo,
                        resumo=resumo or "Votação",
                        data_hora_votacao=timezone.now(),
                        no_ar_desde=timezone.now(),
                        ativo=True
                    )
                    messages.success(request, f'Votação "{votacao.titulo}" criada com sucesso.')
                except Proposicao.DoesNotExist:
                    messages.error(request, 'Proposição não encontrada.')
    
    votacoes = VotacaoVoteBem.objects.select_related('proposicao_votacao__proposicao').order_by('-created_at')
    # Anotar status "ativa agora" considerando janela no_ar_desde/no_ar_ate
    try:
        for v in votacoes:
            # Usa método do modelo para garantir regra única
            v.is_active_now = v.is_active()
    except Exception:
        for v in votacoes:
            v.is_active_now = bool(v.ativo)
    proposicoes_sem_votacao = Proposicao.objects.none()
    
    context = {
        'votacoes': votacoes,
        'proposicoes_sem_votacao': proposicoes_sem_votacao,
    }
    
    return render(request, 'admin/voting/votacoes_management.html', context)

@staff_member_required
def proposicao_votacoes_management(request):
    qs = (
        ProposicaoVotacao.objects
        .select_related('proposicao')
        .annotate(
            total_referencias=Count('referencias'),
            total_votos_individuais=Count('congressmanvote')
        )
        .order_by('-updated_at')
    )
    context = {
        'proposicao_votacoes': qs,
    }
    return render(request, 'admin/voting/proposicao_votacoes_management.html', context)

@staff_member_required
def votacao_create(request):
    """Dedicated page to create a new votação, with optional prefill by proposição."""
    if request.method == 'POST':
        proposicao_id = request.POST.get('proposicao_id')
        proposicao_votacao_id = request.POST.get('proposicao_votacao_id')
        titulo = request.POST.get('titulo')
        resumo = request.POST.get('resumo')
        # New field: explicacao (optional long text)
        explicacao = request.POST.get('explicacao')
        data_hora_votacao = request.POST.get('data_hora_votacao')
        no_ar_desde = request.POST.get('no_ar_desde')
        no_ar_ate = request.POST.get('no_ar_ate')
        ativo = request.POST.get('ativo') == 'on'
        # If the proposição has official votações, force selecting one before creation
        if proposicao_id and not proposicao_votacao_id:
            try:
                if ProposicaoVotacao.objects.filter(proposicao_id=proposicao_id).exists():
                    messages.error(request, 'Selecione a votação oficial da proposição antes de criar a votação.')
                else:
                    # No official votações available; allow creation without linking
                    pass
            except Exception:
                # Silently allow if lookup fails; creation block below will handle DoesNotExist
                pass

        if (proposicao_id or proposicao_votacao_id) and titulo and (proposicao_votacao_id or not ProposicaoVotacao.objects.filter(proposicao_id=proposicao_id).exists()):
            try:
                # Opcional: buscar proposição pela nova PK (id_proposicao)
                proposicao = None
                if proposicao_id:
                    proposicao = Proposicao.objects.get(pk=proposicao_id)
                # Se informado, vincular à ProposicaoVotacao específica
                pv = None
                if proposicao_votacao_id:
                    pv = ProposicaoVotacao.objects.get(pk=int(proposicao_votacao_id))

                # Parse datetimes, default to now if invalid or missing
                try:
                    dt_voto = timezone.datetime.fromisoformat(data_hora_votacao.replace('T', ' ')) if data_hora_votacao else timezone.now()
                except Exception:
                    dt_voto = timezone.now()
                try:
                    dt_desde = timezone.datetime.fromisoformat(no_ar_desde.replace('T', ' ')) if no_ar_desde else timezone.now()
                except Exception:
                    dt_desde = timezone.now()
                try:
                    dt_ate = timezone.datetime.fromisoformat(no_ar_ate.replace('T', ' ')) if no_ar_ate else None
                except Exception:
                    dt_ate = None

                # Create voting record including the optional explicacao field.
                # Other official counts are stored on ProposicaoVotacao.
                votacao = VotacaoVoteBem.objects.create(
                    proposicao_votacao=pv,
                    titulo=titulo,
                    resumo=resumo or "Votação",
                    explicacao=explicacao or None,
                    data_hora_votacao=dt_voto,
                    no_ar_desde=dt_desde,
                    no_ar_ate=dt_ate,
                    ativo=ativo,
                )
                messages.success(request, f'Votação "{votacao.titulo}" criada com sucesso.')
                return redirect('gerencial:votacao_edit', pk=votacao.pk)
            except Proposicao.DoesNotExist:
                messages.error(request, 'Proposição não encontrada.')
            except ProposicaoVotacao.DoesNotExist:
                messages.error(request, 'Votação oficial da proposição não encontrada.')
        else:
            messages.error(request, 'Preencha os campos obrigatórios.')

    # Prefill from GET parameters or proposicao id
    prefill = {
        'proposicao_id': '',
        'proposicao_search': '',
        'titulo': '',
        'resumo': '',
        'data_hora_votacao': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        'no_ar_desde': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        'no_ar_ate': '',
        'ativo': True,
        # Contagens oficiais não pertencem a VotacaoVoteBem; são mantidas em ProposicaoVotacao durante importação
        'proposicao_display': ''
    }
    proposicao_id = request.GET.get('proposicao_id')
    if proposicao_id:
        try:
            proposicao = Proposicao.objects.get(pk=proposicao_id)
            # Use pk which now equals id_proposicao
            prefill['proposicao_id'] = proposicao.pk
            prefill['proposicao_search'] = proposicao.titulo
            prefill['titulo'] = f"Votação: {proposicao.titulo}"
            prefill['resumo'] = (proposicao.ementa or '').strip()
            prefill['proposicao_display'] = f"{proposicao.tipo} {proposicao.numero}/{proposicao.ano} - {proposicao.titulo}"
            # Listar ProposicaoVotacao ainda sem VotacaoVoteBem vinculada
            pv_candidates = (
                ProposicaoVotacao.objects
                .filter(proposicao_id=proposicao.pk)
                # Atualizado: relação reversa é 'votacaovotebem' após renomeação do modelo
                .filter(votacaovotebem__isnull=True)
                .order_by('votacao_sufixo')
            )
            prefill['pv_candidates'] = pv_candidates
        except Proposicao.DoesNotExist:
            messages.error(request, 'Proposição para preenchimento não encontrada.')

    # Handle GET prefill: allow default selection of ProposicaoVotacao via consulta_id
    try:
        params = request.GET
        consulta_id = params.get('consulta_id')  # e.g., "559138-241" or just "241"
        proposicao_id_param = params.get('proposicao_id')
        if consulta_id and proposicao_id_param and prefill.get('pv_candidates'):
            try:
                # Extract suffix (after last dash), or use value as-is when no dash
                suffix_str = str(consulta_id)
                if '-' in suffix_str:
                    suffix_str = suffix_str.split('-')[-1]
                suffix_int = int(suffix_str)
            except Exception:
                suffix_int = None

            if suffix_int is not None:
                # Find matching ProposicaoVotacao candidate by votacao_sufixo
                try:
                    match = next((pv for pv in prefill['pv_candidates'] if getattr(pv, 'votacao_sufixo', None) == suffix_int), None)
                    if match:
                        prefill['selected_pv_id'] = match.id
                except Exception:
                    pass
    except Exception:
        pass

    context = {
        'prefill': prefill,
    }
    return render(request, 'admin/voting/votacao_create.html', context)

@staff_member_required
def users_management(request):
    """
    Manage users - view statistics, change user details
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        
        if action == 'toggle_active' and user_id:
            try:
                user = User.objects.get(id=user_id)
                user.is_active = not user.is_active
                user.save()
                status = "ativado" if user.is_active else "desativado"
                messages.success(request, f'Usuário "{user.username}" foi {status} com sucesso.')
            except User.DoesNotExist:
                messages.error(request, 'Usuário não encontrado.')
    
    users_stats = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'users_with_votes': User.objects.filter(voto__isnull=False).distinct().count(),
        'recent_users': User.objects.order_by('-date_joined')[:10],
        'top_voters': User.objects.annotate(
            vote_count=Count('voto')
        ).filter(vote_count__gt=0).order_by('-vote_count')[:10],
    }
    
    return render(request, 'admin/voting/users_management.html', {'stats': users_stats})

@staff_member_required
def data_import_export(request):
    """
    Tools for importing and exporting data
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Simulate processing time for demonstration
        time.sleep(2)  # Remove this in production
        
        # Export actions
        if action == 'export_proposicoes':
            # This would implement data export functionality
            message = 'Funcionalidade de exportação será implementada em breve.'
            if is_ajax:
                return JsonResponse({'success': True, 'message': message})
            messages.info(request, message)
        
        elif action == 'import_congressmen':
            # This would implement congressman import functionality
            message = 'Funcionalidade de importação será implementada em breve.'
            if is_ajax:
                return JsonResponse({'success': True, 'message': message})
            messages.info(request, message)
        
        elif action == 'import_dados_index':
            try:
                # Import data from dadosIndex.txt file
                import json
                import re
                from bs4 import BeautifulSoup
                
                dados_index_path = r'C:\Users\User\Dados\Tecnicos\HardESoftware\EmDesenvolvimento\VotoBomPython\00_VB_php\direct\admin\dadosIndex.txt'
                
                with open(dados_index_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    # Extract JSON data from the JavaScript variable assignment
                    json_match = re.search(r'dados = (\[.*\]);', content, re.DOTALL)
                    if not json_match:
                        raise ValueError('Formato de dados inválido no arquivo dadosIndex.txt')
                    
                    dados = json.loads(json_match.group(1))
                
                imported_count = 0
                updated_count = 0
                errors = []
                
                for item in dados:
                    try:
                        id_proposicao = int(item['idProposicao'])
                        votacao_html = item['Votacao']
                        
                        # Parse HTML content to extract structured data
                        soup = BeautifulSoup(votacao_html, 'html.parser')
                        li_items = soup.find_all('li')
                        
                        data = {}
                        for li in li_items:
                            text = li.get_text()
                            if text.startswith('Ementa: '):
                                data['ementa'] = text[8:].strip()
                            elif text.startswith('Numero/ano: '):
                                numero_ano = text[12:].strip()
                                if '/' in numero_ano:
                                    numero, ano = numero_ano.split('/')
                                    data['numero'] = int(numero)
                                    data['ano'] = int(ano)
                            elif text.startswith('Situacao: '):
                                data['situacao'] = text[10:].strip()
                            elif text.startswith('Título: '):
                                data['titulo'] = text[8:].strip()
                            elif text.startswith('Resumo: '):
                                data['resumo'] = text[8:].strip()
                            elif text.startswith('Pergunta: '):
                                data['pergunta'] = text[10:].strip()
                            elif text.startswith('Indexacao: '):
                                data['indexacao'] = text[11:].strip()
                        
                        # Create or update Proposicao
                        proposicao, created = Proposicao.objects.get_or_create(
                            id_proposicao=id_proposicao,
                            defaults={
                                'titulo': data.get('titulo', f'Proposição {id_proposicao}'),
                                'ementa': data.get('ementa', ''),
                                'tipo': 'PL',  # Default type, could be extracted from titulo if needed
                                'numero': data.get('numero', 0),
                                'ano': data.get('ano', 2024),
                                'estado': data.get('situacao', ''),
                            }
                        )
                        
                        if created:
                            imported_count += 1
                        else:
                            # Update existing proposition with new data
                            if data.get('titulo'):
                                proposicao.titulo = data['titulo']
                            if data.get('ementa'):
                                proposicao.ementa = data['ementa']
                            if data.get('numero'):
                                proposicao.numero = data['numero']
                            if data.get('ano'):
                                proposicao.ano = data['ano']
                            if data.get('situacao'):
                                proposicao.estado = data['situacao']
                            proposicao.save()
                            updated_count += 1
                        
                        # Create VotacaoDisponivel if we have voting data
                        if data.get('resumo') or data.get('pergunta'):
                            # Criar uma votação disponível desvinculada (por enquanto) de ProposicaoVotacao
                            votacao = VotacaoDisponivel.objects.create(
                                proposicao_votacao=None,
                                titulo=data.get('titulo', f'Votação da Proposição {id_proposicao}'),
                                resumo=data.get('resumo', data.get('pergunta', '')),
                                data_hora_votacao=timezone.now(),
                                no_ar_desde=timezone.now(),
                                ativo=True,
                            )
                    
                    except Exception as e:
                        errors.append(f'Erro ao processar proposição {item.get("idProposicao", "desconhecida")}: {str(e)}')
                        continue
                
                if errors:
                    error_summary = f'Importação concluída com {len(errors)} erros. '
                    if len(errors) <= 3:
                        error_summary += f'Erros: {"; ".join(errors)}'
                    else:
                        error_summary += f'Primeiros erros: {"; ".join(errors[:3])}...'
                    
                    message = f'Dados importados: {imported_count} novas proposições, {updated_count} atualizadas. {error_summary}'
                    if is_ajax:
                        return JsonResponse({'success': True, 'message': message})
                    messages.warning(request, message)
                else:
                    message = f'Importação concluída com sucesso! {imported_count} novas proposições importadas, {updated_count} atualizadas.'
                    if is_ajax:
                        return JsonResponse({'success': True, 'message': message})
                    messages.success(request, message)
                    
            except FileNotFoundError:
                error_message = 'Arquivo dadosIndex.txt não encontrado no caminho especificado.'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
            except Exception as e:
                error_message = f'Erro ao importar dados: {str(e)}'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
        
        # Maintenance actions
        elif action == 'sync_camara':
            try:
                # Simulate synchronization with Câmara dos Deputados API
                # In a real implementation, this would call external APIs
                message = 'Sincronização com dados da Câmara iniciada com sucesso. Processo pode levar alguns minutos.'
                if is_ajax:
                    return JsonResponse({'success': True, 'message': message})
                messages.success(request, message)
                # Here you would implement the actual sync logic
            except Exception as e:
                error_message = f'Erro ao sincronizar dados: {str(e)}'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
        
        elif action == 'clear_cache':
            try:
                # Clear Django cache
                from django.core.cache import cache
                cache.clear()
                message = 'Cache do sistema limpo com sucesso.'
                if is_ajax:
                    return JsonResponse({'success': True, 'message': message})
                messages.success(request, message)
            except Exception as e:
                error_message = f'Erro ao limpar cache: {str(e)}'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
        
        elif action == 'verify_integrity':
            try:
                # Perform data integrity checks
                issues = []
                
                # Check for propositions without required fields
                proposicoes_sem_titulo = Proposicao.objects.filter(titulo__isnull=True).count()
                if proposicoes_sem_titulo > 0:
                    issues.append(f'{proposicoes_sem_titulo} proposições sem título')
                
                # Check for votes without valid users
                votos_invalidos = Voto.objects.filter(user__isnull=True).count()
                if votos_invalidos > 0:
                    issues.append(f'{votos_invalidos} votos sem usuário válido')
                
                # Check for active votations without linked ProposicaoVotacao (after refactor)
                votacoes_sem_proposicao = VotacaoVoteBem.objects.filter(proposicao_votacao__isnull=True).count()
                if votacoes_sem_proposicao > 0:
                    issues.append(f'{votacoes_sem_proposicao} votações sem proposição')
                
                if issues:
                    message = f'Problemas de integridade encontrados: {", ".join(issues)}'
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': message})
                    messages.warning(request, message)
                else:
                    message = 'Verificação de integridade concluída. Nenhum problema encontrado.'
                    if is_ajax:
                        return JsonResponse({'success': True, 'message': message})
                    messages.success(request, message)
                    
            except Exception as e:
                error_message = f'Erro ao verificar integridade: {str(e)}'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
        
        else:
            error_message = 'Ação não reconhecida.'
            if is_ajax:
                return JsonResponse({'success': False, 'message': error_message})
            messages.error(request, error_message)
            
        if not is_ajax:
            return redirect('gerencial:data_import_export')
    
    context = {
        'export_options': [
            {'name': 'Proposições', 'action': 'export_proposicoes'},
            {'name': 'Votações', 'action': 'export_votacoes'},
            {'name': 'Votos Populares', 'action': 'export_votos'},
        ],
        'import_options': [
            {'name': 'Dados Index (dadosIndex.txt)', 'action': 'import_dados_index'},
            {'name': 'Congressistas', 'action': 'import_congressmen'},
            {'name': 'Proposições', 'action': 'import_proposicoes'},
            {'name': 'Votações Oficiais', 'action': 'import_votacoes'},
        ],
    }
    
    return render(request, 'admin/voting/data_import_export.html', context)

@staff_member_required
def proposicao_add(request):
    """
    Add a new proposition
    """
    if request.method == 'POST':
        # Get form data
        titulo = request.POST.get('titulo', '').strip()
        ementa = request.POST.get('ementa', '').strip()
        tipo = request.POST.get('tipo', '').strip().upper()
        numero = request.POST.get('numero', '').strip()
        ano = request.POST.get('ano', '').strip()
        estado = request.POST.get('estado', '').strip()
        id_proposicao = request.POST.get('id_proposicao', '').strip()
        
        # Validate required fields
        if not all([titulo, tipo, numero, ano]):
            messages.error(request, 'Título, tipo, número e ano são obrigatórios.')
        else:
            try:
                # Convert numeric fields
                numero = int(numero)
                ano = int(ano)
                
                # Check if proposition already exists
                if Proposicao.objects.filter(tipo=tipo, numero=numero, ano=ano).exists():
                    messages.error(request, f'Proposição {tipo} {numero}/{ano} já existe no sistema.')
                else:
                    # Create new proposition
                    proposicao = Proposicao.objects.create(
                        titulo=titulo,
                        ementa=ementa,
                        tipo=tipo,
                        numero=numero,
                        ano=ano,
                        estado=estado,
                        id_proposicao=id_proposicao if id_proposicao else None
                    )
                    
                    messages.success(request, f'Proposição {tipo} {numero}/{ano} criada com sucesso!')
                    return redirect('gerencial:proposicao_edit', pk=proposicao.pk)
                    
            except ValueError:
                messages.error(request, 'Número e ano devem ser valores numéricos válidos.')
            except Exception as e:
                messages.error(request, f'Erro ao criar proposição: {str(e)}')
    
    # Get current year as default
    from datetime import datetime
    current_year = datetime.now().year
    
    context = {
        'title': 'Adicionar Proposição Manualmente',
        'current_year': current_year,
    }
    
    return render(request, 'admin/voting/proposicao_add.html', context)


@staff_member_required
def proposicao_import(request):
    """Import a proposição from Câmara by id_proposicao and redirect to edit"""
    context = {
        'title': 'Importar Proposição por ID da Câmara',
    }

    if request.method == 'POST':
        id_proposicao = request.POST.get('id_proposicao', '').strip()
        if not id_proposicao:
            messages.error(request, 'Informe o ID da proposição da Câmara (idProposicao).')
        else:
            try:
                ext_id = int(id_proposicao)
                from .services.camara_api import camara_api

                # Use the service to sync a single proposição by its ID
                try:
                    proposicao = camara_api._sync_single_proposicao({'id': ext_id})
                except Exception as e:
                    messages.error(request, f'Erro ao obter dados da Câmara: {str(e)}')
                    proposicao = None

                if proposicao:
                    messages.success(request, f'Proposição {proposicao.tipo} {proposicao.numero}/{proposicao.ano} importada/atualizada com sucesso!')
                    return redirect('gerencial:proposicao_edit', pk=proposicao.pk)
                else:
                    messages.error(request, 'Não foi possível criar a proposição a partir do ID informado.')
            except ValueError:
                messages.error(request, 'O ID informado deve ser um número inteiro válido.')

    return render(request, 'admin/voting/proposicao_import.html', context)

@login_required
def camara_admin(request):
    """
    Administrative tools for managing Chamber propositions
    Equivalent to vb01c_ProposicoesCamara.php
    """
    from datetime import datetime, timedelta
    import json
    
    context = {
        'title': 'Administrar Proposições da Câmara',
        'current_year': datetime.now().year,
        'default_year': 2017,
        'date_7_days_ago': (datetime.now() - timedelta(days=7)).strftime('%d/%m/%Y'),
        'date_today': datetime.now().strftime('%d/%m/%Y'),
        'date_2_months_ago': (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d'),
        'date_today_iso': datetime.now().strftime('%Y-%m-%d'),
        # Default dates for "Listar Proposições por Período" form
        'default_data_inicio': (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),  # One year ago
        'default_data_fim': datetime.now().strftime('%Y-%m-%d'),  # Today
    }
    

    
    # Restrict to staff in a friendly way (no redirect to admin login)
    # If the user is authenticated but not staff, show a clear message instead of
    # bouncing through the Django admin login page, which can appear as a loop.
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Acesso restrito: é necessário ser usuário de staff.')
        return render(request, 'admin/voting/camara_admin.html', context)

    # Handle POST actions (refactored: long-running tasks now execute in background)
    if request.method == 'POST':
        action = request.POST.get('action')
        dev_log(f"DEBUG: POST request received with action: {action}")
        dev_log(f"DEBUG: All POST data: {dict(request.POST)}")
        
        
            
        if action == 'listarProposicoesVotadas':
            # List propositions that have been voted
            # Ajustado para novo relacionamento: Proposicao -> ProposicaoVotacao -> VotacaoVoteBem
            # Filtra proposições que possuem ao menos uma VotacaoVoteBem vinculada via ProposicaoVotacao
            from django.db.models import Count
            proposicoes_votadas = (
                Proposicao.objects
                .filter(votacoes_oficiais__votacaovotebem__isnull=False)
                .annotate(total_votacoes=Count('votacoes_oficiais__votacaovotebem', distinct=True))
                .distinct()
                .order_by('-ano', '-numero')[:50]
            )
            context['proposicoes_votadas'] = proposicoes_votadas
            context['action_result'] = 'proposicoes_votadas'
            
           
        elif action == 'atualizarProposicoesVotadasPlenario':
            # Long-running: execute in background with lock + status
            data_inicial = request.POST.get('dataInicial')
            data_final = request.POST.get('dataFinal')
            try:
                if not data_inicial or not data_final:
                    raise ValueError("Data inicial e final são obrigatórias")

                lock_key = f"vb:camara_admin:sync_plenario:{data_inicial}:{data_final}"
                status_key = f"vb:status:camara_admin:sync_plenario:{data_inicial}:{data_final}"
                if not _acquire_lock(lock_key, ttl_seconds=3600):
                    messages.info(request, 'Uma sincronização semelhante já está em execução. Aguarde a conclusão.')
                else:
                    _set_status(status_key, {
                        'state': 'starting',
                        'range': {'inicio': data_inicial, 'fim': data_final},
                        'created': 0, 'updated': 0, 'errors': 0,
                    })
                    from .services.camara_api import camara_api

                    def _runner():
                        try:
                            stats = camara_api.sync_proposicoes_by_date_range(data_inicial, data_final)
                            _set_status(status_key, {
                                'state': 'finished',
                                'range': {'inicio': data_inicial, 'fim': data_final},
                                'created': int(stats.get('created', 0)),
                                'updated': int(stats.get('updated', 0)),
                                'errors': int(stats.get('errors', 0)),
                            })
                        except Exception as e:
                            _set_status(status_key, {'state': 'error', 'message': str(e)})
                        finally:
                            _release_lock(lock_key)

                    threading.Thread(target=_runner, daemon=True).start()
                    messages.success(request, 'Sincronização iniciada em segundo plano. Você pode continuar usando o painel.')

                context['action_result'] = 'update_result'
            except ValueError as e:
                context['error'] = f'Erro de validação: {str(e)}'
            except Exception as e:
                context['error'] = f'Erro ao iniciar sincronização: {str(e)}'
                
        
                
        elif action == 'loopObterVotacoes':
            # Long-running: execute in background with lock + status
            ano = request.POST.get('anoVotacao', datetime.now().year)
            try:
                ano = int(ano)
                lock_key = f"vb:camara_admin:loop_votacoes:{ano}"
                status_key = f"vb:status:camara_admin:loop_votacoes:{ano}"
                if not _acquire_lock(lock_key, ttl_seconds=3600):
                    messages.info(request, f'Um loop de votações para o ano {ano} já está em execução. Aguarde a conclusão.')
                else:
                    _set_status(status_key, {'state': 'starting', 'ano': ano, 'processed': 0, 'total_votacoes': 0})
                    from .services.camara_api import camara_api

                    def _runner():
                        total_votacoes = 0
                        try:
                            proposicoes = Proposicao.objects.filter(ano=ano)[:100]
                            count = 0
                            for proposicao in proposicoes:
                                try:
                                    if proposicao.id_proposicao:
                                        votacoes_count = camara_api.sync_votacoes_for_proposicao(proposicao)
                                        total_votacoes += int(votacoes_count or 0)
                                except Exception:
                                    # continue silently; record aggregate only
                                    pass
                                count += 1
                                if count % 5 == 0:
                                    _set_status(status_key, {
                                        'state': 'running', 'ano': ano,
                                        'processed': count, 'total_votacoes': total_votacoes
                                    })
                            _set_status(status_key, {
                                'state': 'finished', 'ano': ano,
                                'processed': count, 'total_votacoes': total_votacoes
                            })
                        except Exception as e:
                            _set_status(status_key, {'state': 'error', 'message': str(e)})
                        finally:
                            _release_lock(lock_key)

                    threading.Thread(target=_runner, daemon=True).start()
                    messages.success(request, f'Loop de votações para {ano} iniciado em segundo plano.')

                context['action_result'] = 'loop_result'
            except ValueError:
                context['error'] = 'Ano inválido fornecido.'
            except Exception as e:
                context['error'] = f'Erro ao iniciar loop de votações: {str(e)}'
                
        elif action == 'atualizarNProposicoes':
            # Long-running: execute in background with lock + status
            n_proposicoes = request.POST.get('nProximasProposicoes', 1)
            partir_da = request.POST.get('aPartirDaProposicao', '')
            tempo_max = request.POST.get('tempoMaximoProcess', 150)

            try:
                n_proposicoes = int(n_proposicoes)
                tempo_max = int(tempo_max)

                lock_key = f"vb:camara_admin:update_n:{n_proposicoes}:{partir_da or 'none'}"
                status_key = f"vb:status:camara_admin:update_n:{n_proposicoes}:{partir_da or 'none'}"
                if not _acquire_lock(lock_key, ttl_seconds=3600):
                    messages.info(request, 'Uma atualização semelhante já está em execução. Aguarde a conclusão.')
                else:
                    _set_status(status_key, {
                        'state': 'starting', 'n': n_proposicoes, 'partir_da': partir_da or '',
                        'created': 0, 'updated': 0
                    })

                    from .services.camara_api import camara_api

                    def _runner():
                        created_count = 0
                        updated_count = 0
                        ids = []
                        try:
                            proposicoes_api = camara_api.get_recent_proposicoes(days=30, limit=n_proposicoes)
                            for idx, prop_data in enumerate(proposicoes_api):
                                try:
                                    result = camara_api._sync_single_proposicao(prop_data)
                                    ids.append(str(prop_data.get('id')))
                                    if result.get('created'):
                                        created_count += 1
                                    else:
                                        updated_count += 1
                                except Exception:
                                    pass
                                if (idx + 1) % 5 == 0:
                                    _set_status(status_key, {
                                        'state': 'running', 'processed': idx + 1,
                                        'created': created_count, 'updated': updated_count,
                                    })
                            _set_status(status_key, {
                                'state': 'finished', 'processed': len(ids),
                                'created': created_count, 'updated': updated_count,
                                'ids': ','.join(ids)
                            })
                        except Exception as e:
                            _set_status(status_key, {'state': 'error', 'message': str(e)})
                        finally:
                            _release_lock(lock_key)

                    threading.Thread(target=_runner, daemon=True).start()
                    messages.success(request, 'Atualização iniciada em segundo plano. Você pode continuar usando o painel.')

                context['action_result'] = 'update_n_result'
            except ValueError:
                context['error'] = 'Valores numéricos inválidos fornecidos.'
            except Exception as e:
                context['error'] = f'Erro ao iniciar atualização: {str(e)}'
                
        elif action == 'listarProposicoesTramitacao':
            # List propositions in processing within date range
            data_inicio = request.POST.get('dataInicio')
            data_fim = request.POST.get('dataFim')
            api_type = request.POST.get('apiType', 'producao')
            
            try:
                from .services.camara_api import camara_api
                
                if not data_inicio or not data_fim:
                    # Default to last 30 days
                    data_fim = datetime.now().strftime('%Y-%m-%d')
                    data_inicio = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                
                proposicoes = camara_api.get_proposicoes_by_date_range(data_inicio, data_fim)
                context['tramitacao_result'] = {
                    'proposicoes': proposicoes[:50],  # Limit for display
                    'total': len(proposicoes),
                    'data_inicio': data_inicio,
                    'data_fim': data_fim,
                    'api_type': api_type
                }
                context['action_result'] = 'tramitacao_result'
                messages.success(request, f'Encontradas {len(proposicoes)} proposições tramitando entre {data_inicio} e {data_fim}')
            except Exception as e:
                context['error'] = f'Erro ao listar proposições em tramitação: {str(e)}'
    
    # Get last proposition ID for JavaScript
    try:
        # Proposicao uses 'id_proposicao' as primary key; use created_at for latest
        ultima = Proposicao.objects.latest('created_at')
        ultima_proposicao_id = ultima.id_proposicao
        context['ultima_proposicao_id'] = ultima_proposicao_id
    except Proposicao.DoesNotExist:
        context['ultima_proposicao_id'] = 0
    
    return render(request, 'admin/voting/camara_admin.html', context)


@staff_member_required
def ajax_proposicao_search(request):
    """
    AJAX endpoint for searching propositions
    """
    query = request.GET.get('q', '')
    if len(query) < 3:
        return JsonResponse({'results': []})
    
    proposicoes = Proposicao.objects.filter(
        Q(titulo__icontains=query) | 
        Q(ementa__icontains=query) |
        Q(id_proposicao__icontains=query)
    )[:20]
    
    results = [
        {
            'id': p.id,
            'text': f"{p.tipo} {p.numero}/{p.ano} - {p.titulo}",
            'id_proposicao': p.id_proposicao,
        }
        for p in proposicoes
    ]
    
    return JsonResponse({'results': results})

@staff_member_required
def ajax_proposicao_votacoes(request):
    """Endpoint de votações por proposição com modos de busca configuráveis.
    Modos suportados:
    - Padrão (cache-first): se existir em ProposicaoVotacao, retorna do banco; senão, consulta API.
    - `db_only=1`: retorna apenas o que está no banco; não consulta API.
    - `force_api=1`: ignora cache do banco e consulta a API diretamente.
    """
    prop_id = request.GET.get('proposicao_id')
    db_only_raw = request.GET.get('db_only')
    db_only = str(db_only_raw).lower() in ('1', 'true', 'yes', 'y')
    force_api_raw = request.GET.get('force_api')
    force_api = str(force_api_raw).lower() in ('1', 'true', 'yes', 'y')
    if not prop_id:
        return JsonResponse({'ok': False, 'error': 'Parâmetro proposicao_id é obrigatório.'}, status=400)
    try:
        prop_id_int = int(prop_id)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'proposicao_id deve ser numérico.'}, status=400)

    # Tenta localizar/garantir Proposicao
    proposicao = Proposicao.objects.filter(id_proposicao=prop_id_int).first()
    # Quando db_only, não consultar API para criar proposição ausente
    if proposicao is None and db_only:
        return JsonResponse({'ok': True, 'source': 'db', 'dados': []})
    if proposicao is None:
        # Buscar detalhes mínimos para criar Proposicao e poder relacionar
        try:
            details = camara_api.get_proposicao_details(prop_id_int) or {}
            dados = details.get('dados') or {}
            # Campos obrigatórios
            titulo = (dados.get('ementa') or '')[:500]
            ementa = dados.get('ementa') or ''
            tipo = dados.get('siglaTipo') or ''
            numero = int(dados.get('numero') or 0)
            ano = int(dados.get('ano') or 0)
            autor = ''
            estado = dados.get('statusProposicao', {}).get('descricaoSituacao') or ''
            proposicao = Proposicao.objects.create(
                id_proposicao=prop_id_int,
                titulo=titulo,
                ementa=ementa,
                tipo=tipo,
                numero=numero,
                ano=ano,
                autor=autor,
                estado=estado,
            )
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'Falha ao garantir proposição: {e}'}, status=500)

    # 1) Consulta cache local
    cached = list(ProposicaoVotacao.objects.filter(proposicao=proposicao).order_by('votacao_sufixo'))
    # Quando "force_api" está ativo, ignorar resultados em cache e seguir para a API.
    if cached and not force_api:
        # Precompute counts for all cached votações to avoid N queries
        counts_qs = (
            CongressmanVote.objects
            .filter(proposicao_votacao__in=cached)
            .values('proposicao_votacao_id')
            .annotate(cnt=Count('id'))
        )
        counts_map = {row['proposicao_votacao_id']: row['cnt'] for row in counts_qs}

        # Mapear VotacaoVoteBem (se existir) para cada ProposicaoVotacao
        vb_map = {}
        try:
            vb_rows = (
                VotacaoVoteBem.objects
                .filter(proposicao_votacao__in=cached)
                .order_by('-no_ar_desde')
                .values('id', 'proposicao_votacao_id')
            )
            for r in vb_rows:
                # Se houver múltiplas, escolher a mais recente (primeira encontrada)
                pv_id = r['proposicao_votacao_id']
                if pv_id not in vb_map:
                    vb_map[pv_id] = r['id']
        except Exception:
            vb_map = {}

        dados = [
            {
                'id': f"{prop_id_int}-{pv.votacao_sufixo}",
                'pv_id': pv.id,
                'descricao': pv.descricao or '',
                'dataHora': '',
                'resultado': '',
                'votes_count': int(counts_map.get(pv.id, 0)),
                'vb_id': vb_map.get(pv.id),
                'prioridade': pv.prioridade,
            }
            for pv in cached
        ]
        return JsonResponse({'ok': True, 'source': 'db', 'dados': dados})

    # 2) Fallback: Câmara API (omitido quando db_only)
    if db_only:
        # Não consultar API; retornar vazio para fluxo "somente banco"
        return JsonResponse({'ok': True, 'source': 'db', 'dados': []})
    # 2) Fallback: Câmara API
    try:
        #url correta: https://dadosabertos.camara.leg.br/api/v2/votacoes?idProposicao=2270800&idOrgao=180&ordem=DESC&ordenarPor=dataHoraRegistro
        api_url = f"{CamaraAPIService.BASE_URL}/proposicoes/{prop_id_int}/votacoes"
        api_url = f"{CamaraAPIService.BASE_URL}/votacoes?idProposicao={prop_id_int}&idOrgao=180"
        api_items = camara_api.get_proposicao_votacoes(prop_id_int) or []
        # Para force_api, devolver TODOS os itens da API sem filtro.
        # Caso contrário, manter filtro por chaves relevantes.
        needles = [
            'em primeiro turno',
            'em segundo turno',
            'emenda aglutinativa',
            'projeto'
        ]
        def _desc(item):
            return (item.get('descricao') or item.get('descrição') or '').lower()
        filtered = api_items if force_api else [i for i in api_items if any(n in _desc(i) for n in needles)]

        # Inserção no banco SEM duplicar: verificar sufixos existentes para a proposição
        existing_sufixos = set(
            ProposicaoVotacao.objects
            .filter(proposicao=proposicao)
            .values_list('votacao_sufixo', flat=True)
        )
        to_create = []
        sufixos = []
        for item in filtered:
            full_id = item.get('id') or item.get('idVotacao') or ''
            sufixo = None
            try:
                if isinstance(full_id, str) and '-' in full_id:
                    sufixo = int(full_id.split('-')[-1])
                elif isinstance(full_id, int):
                    sufixo = full_id
            except Exception:
                sufixo = None
            if sufixo is None:
                continue
            sufixos.append(sufixo)
            # Apenas inserir se NÃO existir (evita duplicação por (proposicao_id, votacao_sufixo))
            if sufixo not in existing_sufixos:
                to_create.append(ProposicaoVotacao(
                    proposicao=proposicao,
                    votacao_sufixo=sufixo,
                    descricao=item.get('descricao') or item.get('descrição') or '',
                    prioridade=None,
                ))

        # Evitar conflitos com unique_together; inserir apenas os novos
        if to_create:
            try:
                with transaction.atomic():
                    ProposicaoVotacao.objects.bulk_create(to_create, ignore_conflicts=True)
            except Exception:
                pass

        # Mapear counts para sufixos existentes
        pv_qs = ProposicaoVotacao.objects.filter(proposicao=proposicao, votacao_sufixo__in=sufixos)
        counts_qs = (
            CongressmanVote.objects
            .filter(proposicao_votacao__in=pv_qs)
            .values('proposicao_votacao_id')
            .annotate(cnt=Count('id'))
        )
        counts_map_by_pv_id = {row['proposicao_votacao_id']: row['cnt'] for row in counts_qs}
        # Criar mapa sufixo -> pv.id
        pv_id_by_sufixo = {pv.votacao_sufixo: pv.id for pv in pv_qs}

        # Mapear vb_id por pv_id
        vb_id_by_pv_id = {}
        try:
            vb_rows = (
                VotacaoVoteBem.objects
                .filter(proposicao_votacao__in=pv_qs)
                .order_by('-no_ar_desde')
                .values('id', 'proposicao_votacao_id')
            )
            for r in vb_rows:
                pv_id = r['proposicao_votacao_id']
                if pv_id not in vb_id_by_pv_id:
                    vb_id_by_pv_id[pv_id] = r['id']
        except Exception:
            vb_id_by_pv_id = {}

        dados = []
        for item in filtered:
            full_id = item.get('id') or item.get('idVotacao') or ''
            # Extrair sufixo numérico da votação
            sufixo_val = None
            try:
                if isinstance(full_id, str) and '-' in full_id:
                    sufixo_val = int(full_id.split('-')[-1])
                elif isinstance(full_id, int):
                    sufixo_val = full_id
            except Exception:
                sufixo_val = None
            pv_id = pv_id_by_sufixo.get(sufixo_val)
            votes_count = int(counts_map_by_pv_id.get(pv_id, 0))
            vb_id = vb_id_by_pv_id.get(pv_id)

            dados.append({
                'id': full_id,
                'pv_id': pv_id,
                'descricao': item.get('descricao') or item.get('descrição') or '',
                'dataHora': item.get('dataHoraRegistro') or item.get('dataHora') or '',
                'resultado': item.get('resultado') or '',
                'votes_count': votes_count,
                'vb_id': vb_id,
                'prioridade': None,
            })
        return JsonResponse({'ok': True, 'source': 'api', 'dados': dados})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Erro ao consultar API: {e}', 'api_url': api_url}, status=502)


@staff_member_required
def ajax_update_proposicao_votacao_prioridade(request):
    """Atualiza o campo prioridade de um registro ProposicaoVotacao (AJAX).
    Espera POST com 'pv_id' e 'prioridade' (string vazia ou null para remover).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método não permitido.'}, status=405)

    pv_id = request.POST.get('pv_id')
    prioridade_raw = request.POST.get('prioridade')
    if not pv_id:
        return JsonResponse({'ok': False, 'error': 'Parâmetro pv_id é obrigatório.'}, status=400)
    try:
        pv_id_int = int(pv_id)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'pv_id deve ser numérico.'}, status=400)

    try:
        pv = ProposicaoVotacao.objects.get(pk=pv_id_int)
    except ProposicaoVotacao.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Registro não encontrado.'}, status=404)

    # Converter prioridade; valores vazios ou não numéricos (exceto string vazia) geram erro
    prioridade_val = None
    if prioridade_raw is not None:
        pr = prioridade_raw.strip()
        if pr == '':
            prioridade_val = None
        else:
            try:
                prioridade_val = int(pr)
            except ValueError:
                return JsonResponse({'ok': False, 'error': 'prioridade deve ser inteiro ou vazio.'}, status=400)

    # Atualizar e salvar
    pv.prioridade = prioridade_val
    pv.save(update_fields=['prioridade'])

    return JsonResponse({'ok': True, 'pv_id': pv.id, 'prioridade': pv.prioridade})


@staff_member_required
def ajax_delete_proposicao_votacao(request):
    """Exclui registros de `ProposicaoVotacao` por `proposicao_id` e `votacao_sufixo` (consulta_id).
    - Espera `POST` com uma das formas:
      * `proposicao_id` e `consulta_id` (numéricos)
      * `composed_id` no formato `<proposicao_id>-<consulta_id>` (ex.: `2270800-160`)
    - Remove todos os registros que correspondam ao par informado.
    - A exclusão CASCADE apaga também `VotacaoVoteBem`, `CongressmanVote` e, por consequência, `Voto`.
    Retorna JSON com contagens estimadas de remoção.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método não permitido.'}, status=405)

    composed = (request.POST.get('composed_id') or '').strip()
    proposicao_id = (request.POST.get('proposicao_id') or '').strip()
    consulta_id = (request.POST.get('consulta_id') or '').strip()

    # Extrair de composed_id quando fornecido
    if composed and ('-' in composed) and (not proposicao_id or not consulta_id):
        try:
            parts = composed.split('-')
            proposicao_id = proposicao_id or parts[0].strip()
            consulta_id = consulta_id or parts[1].strip()
        except Exception:
            return JsonResponse({'ok': False, 'error': 'Formato inválido de composed_id.'}, status=400)

    # Validar numéricos
    try:
        prop_id_int = int(proposicao_id)
        sufixo_int = int(consulta_id)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Parâmetros proposicao_id e consulta_id devem ser numéricos.'}, status=400)

    # Preparar queryset
    qs = ProposicaoVotacao.objects.filter(
        proposicao__id_proposicao=prop_id_int,
        votacao_sufixo=sufixo_int
    )

    # Levantar contagens antes da exclusão para relatar impacto
    pv_ids = list(qs.values_list('id', flat=True))
    from .models import VotacaoVoteBem, CongressmanVote, Voto
    vb_qs = VotacaoVoteBem.objects.filter(proposicao_votacao_id__in=pv_ids)
    cv_qs = CongressmanVote.objects.filter(proposicao_votacao_id__in=pv_ids)
    # votos relacionados via VotacaoVoteBem
    voto_qs = Voto.objects.filter(votacao_id__in=list(vb_qs.values_list('id', flat=True)))

    counts_before = {
        'proposicao_votacao': len(pv_ids),
        'votacao_votebem': vb_qs.count(),
        'congressman_vote': cv_qs.count(),
        'voto': voto_qs.count(),
    }

    # Executar exclusão em transação
    with transaction.atomic():
        deleted_total, deleted_breakdown = qs.delete()

    return JsonResponse({
        'ok': True,
        'params': {'proposicao_id': prop_id_int, 'consulta_id': sufixo_int},
        'counts_before': counts_before,
        'deleted_total': deleted_total,
        'deleted_breakdown': deleted_breakdown,
    })


@staff_member_required
def ajax_referencias_list(request):
    """Lista referências (voting_referencias) para um `ProposicaoVotacao` específico.
    Espera `GET` com `pv_id`.
    """
    pv_id = request.GET.get('pv_id')
    if not pv_id:
        return JsonResponse({'ok': False, 'error': 'Parâmetro pv_id é obrigatório.'}, status=400)
    try:
        pv_id_int = int(pv_id)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'pv_id deve ser numérico.'}, status=400)

    try:
        pv = ProposicaoVotacao.objects.select_related('proposicao').get(pk=pv_id_int)
    except ProposicaoVotacao.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Registro ProposicaoVotacao não encontrado.'}, status=404)

    refs = (
        Referencia.objects
        .filter(proposicao_votacao=pv)
        .order_by('-created_at')
        .values('id', 'url', 'kind', 'created_at')
    )
    # Serialize datetime to ISO
    dados = []
    for r in refs:
        c_at = r.get('created_at')
        dados.append({
            'id': r['id'],
            'url': r['url'],
            'kind': r['kind'],
            'created_at': c_at.isoformat() if hasattr(c_at, 'isoformat') else str(c_at)
        })
    return JsonResponse({'ok': True, 'pv_id': pv.id, 'dados': dados})


@staff_member_required
def ajax_referencias_create(request):
    """Cria uma referência vinculada a `ProposicaoVotacao`.
    Espera `POST` com `pv_id`, `url`, `kind`.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método não permitido.'}, status=405)

    pv_id = request.POST.get('pv_id')
    url = (request.POST.get('url') or '').strip()
    kind = (request.POST.get('kind') or '').strip()
    if not pv_id:
        return JsonResponse({'ok': False, 'error': 'pv_id é obrigatório.'}, status=400)
    if not url:
        return JsonResponse({'ok': False, 'error': 'url é obrigatória.'}, status=400)
    if kind not in dict(Referencia.Kind.choices):
        return JsonResponse({'ok': False, 'error': 'kind inválido.'}, status=400)

    try:
        pv = ProposicaoVotacao.objects.get(pk=int(pv_id))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'ProposicaoVotacao inválido.'}, status=404)

    ref = Referencia.objects.create(
        proposicao_votacao=pv,
        url=url,
        kind=kind,
    )
    return JsonResponse({
        'ok': True,
        'ref': {'id': ref.id, 'url': ref.url, 'kind': ref.kind, 'created_at': ref.created_at.isoformat()},
    })


@staff_member_required
def ajax_referencias_update(request):
    """Atualiza uma referência existente.
    Espera `POST` com `ref_id` e campos opcionais `url`, `kind`.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método não permitido.'}, status=405)

    ref_id = request.POST.get('ref_id')
    url = request.POST.get('url')
    kind = request.POST.get('kind')
    if not ref_id:
        return JsonResponse({'ok': False, 'error': 'ref_id é obrigatório.'}, status=400)

    try:
        ref = Referencia.objects.get(pk=int(ref_id))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Referência não encontrada.'}, status=404)

    updates = {}
    if url is not None:
        u = url.strip()
        if not u:
            return JsonResponse({'ok': False, 'error': 'url não pode ser vazia.'}, status=400)
        ref.url = u
        updates['url'] = u
    if kind is not None:
        k = kind.strip()
        if k not in dict(Referencia.Kind.choices):
            return JsonResponse({'ok': False, 'error': 'kind inválido.'}, status=400)
        ref.kind = k
        updates['kind'] = k

    if updates:
        ref.save(update_fields=list(updates.keys()) + ['updated_at'])

    return JsonResponse({'ok': True, 'ref': {'id': ref.id, 'url': ref.url, 'kind': ref.kind}})


@staff_member_required
def ajax_referencias_delete(request):
    """Exclui uma referência.
    Espera `POST` com `ref_id`.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método não permitido.'}, status=405)
    ref_id = request.POST.get('ref_id')
    if not ref_id:
        return JsonResponse({'ok': False, 'error': 'ref_id é obrigatório.'}, status=400)
    try:
        ref = Referencia.objects.get(pk=int(ref_id))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Referência não encontrada.'}, status=404)
    ref.delete()
    return JsonResponse({'ok': True, 'deleted': True, 'ref_id': int(ref_id)})


def ajax_task_status(request):
    """Lightweight JSON endpoint to poll status of background tasks started from camara_admin.
    Expects GET with `key` (the status_key used by the task). Returns whatever payload was stored.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)
        
    if not (request.user.is_staff or request.user.is_superuser):
        # Return 403-like JSON to keep UX clean for non-staff users
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)

    status_key = (request.GET.get('key') or '').strip()
    if not status_key:
        return JsonResponse({'ok': False, 'error': 'Parâmetro key é obrigatório.'}, status=400)
    payload = _get_status(status_key)
    return JsonResponse({'ok': True, 'status': payload, 'key': status_key})
