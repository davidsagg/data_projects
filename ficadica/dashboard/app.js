/* ── State ── */
const S = {
  courses: [],
  plan: {},
  profile: {},
  section: 'plan',
  filters: { category: '', level: '', instructor: '', search: '' },
  scrapeJobId: null,
};

/* ── Category → badge class mapping ── */
const CAT_BADGE = cat => `badge badge-${(cat || 'outros').toLowerCase().replace(/ã/g,'a').replace(/ç/g,'c')}`;

/* ── Priority stars ── */
function stars(n) {
  const full = '★'.repeat(n), empty = '☆'.repeat(5 - n);
  return `<span class="priority priority-${n}">
    ${full.split('').map(() => `<span class="star">★</span>`).join('')}
    ${empty.split('').map(() => `<span class="star" style="opacity:.2">★</span>`).join('')}
  </span>`;
}

/* ── Duration formatting ── */
function fmtMins(m) {
  if (!m) return '—';
  const h = Math.floor(m / 60), min = m % 60;
  return h ? `${h}h${min ? String(min).padStart(2,'0')+'m' : ''}` : `${min}min`;
}

/* ── Initials for avatar ── */
const initials = name => (name || '?').split(' ').slice(0,2).map(w => w[0]).join('').toUpperCase();

/* ════════════════════════════════════
   API
════════════════════════════════════ */
async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(path, opts);
  return r.json();
}

async function loadAll() {
  const [courses, plan, profile] = await Promise.all([
    api('GET', '/api/courses'),
    api('GET', '/api/study_plan'),
    api('GET', '/api/profile'),
  ]);
  S.courses = Array.isArray(courses) ? courses : [];
  S.plan = plan && !plan.error ? plan : {};
  S.profile = profile && !profile.error ? profile : {};
  document.getElementById('sidebar-count').textContent =
    `${S.courses.length} curso${S.courses.length !== 1 ? 's' : ''} no catálogo`;
}

/* ════════════════════════════════════
   NAVIGATION
════════════════════════════════════ */
function navigateTo(section) {
  S.section = section;
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.section === section);
  });
  document.querySelectorAll('.section').forEach(el => {
    el.classList.toggle('active', el.id === `section-${section}`);
  });
  const renders = { plan: renderPlan, catalog: renderCatalog, stats: renderStats, settings: renderSettings };
  renders[section]?.();
  localStorage.setItem('fad_section', section);
}

/* ════════════════════════════════════
   PLAN SECTION
════════════════════════════════════ */
function renderPlan() {
  const el = document.getElementById('section-plan');
  if (!S.plan.phases) {
    el.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">Meu <span>Plano de Estudos</span></h1>
      </div>
      <div class="loading">
        <div class="spinner"></div> Nenhum plano encontrado — execute <code>python run_planner.py</code>
      </div>`;
    return;
  }

  const { phases = [], parallel_practices = [], total_weeks, total_hours, weekly_hours } = S.plan;

  // Timeline
  const timelineHTML = phases.map((ph, i) => `
    <div class="timeline-phase ${i === 0 ? 'active' : ''}">
      <div class="timeline-dot">${ph.phase}</div>
      <div class="timeline-label">${ph.title}</div>
      <div class="timeline-weeks">sem. ${ph.weeks}</div>
    </div>
  `).join('');

  // Phase cards
  const phasesHTML = phases.map(ph => {
    const coursesHTML = ph.courses && ph.courses.length
      ? ph.courses.map(c => {
          const fullCourse = S.courses.find(x => x.id === c.course_id) || {};
          const cat = fullCourse.category || '';
          return `
          <div class="phase-course-row" onclick="openModal('${c.course_id}')">
            <div class="phase-course-name">${c.title}</div>
            <div class="phase-course-instructor">${c.instructor || ''}</div>
            <div class="phase-course-meta">
              ${cat ? `<span class="${CAT_BADGE(cat)}">${cat}</span>` : ''}
              <span class="badge badge-${c.priority}">${c.priority}</span>
              <span class="phase-est">~${c.estimated_weeks}sem</span>
              ${fullCourse.priority_for_user ? stars(fullCourse.priority_for_user) : ''}
            </div>
          </div>`;
        }).join('')
      : `<div class="phase-empty">
           Nenhum curso agendado nesta fase ainda.<br>
           <span style="font-size:11px">Execute <code>python run_scraper.py</code> para mapear o catálogo completo.</span>
         </div>`;

    return `
      <div class="phase-card">
        <div class="phase-card-header">
          <div class="phase-card-header-left">
            <div class="phase-number">${ph.phase}</div>
            <div class="phase-title-group">
              <div class="phase-title">${ph.title}</div>
              <div class="phase-meta">${ph.focus}</div>
            </div>
          </div>
          <div class="phase-weeks-badge">semanas ${ph.weeks}</div>
        </div>
        <div class="phase-card-body">
          <p class="phase-desc">${ph.description}</p>
          <div class="phase-courses">${coursesHTML}</div>
          <div class="milestone-box">
            <span class="milestone-icon">🏆</span>
            <span class="milestone-text"><strong>Marco:</strong> ${ph.milestone}</span>
          </div>
        </div>
      </div>`;
  }).join('');

  const parallelHTML = parallel_practices.map(p =>
    `<div class="parallel-item">${p}</div>`
  ).join('');

  el.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Meu <span>Plano de Estudos</span></h1>
      <p class="page-subtitle">
        ${total_weeks} semanas · ~${total_hours}h totais · ${weekly_hours}h/semana
        ${S.profile.name ? ` · Planejado para ${S.profile.name}` : ''}
      </p>
    </div>

    <div class="phase-timeline">${timelineHTML}</div>
    <div class="phase-grid">${phasesHTML}</div>

    ${parallelHTML ? `
    <div class="parallel-box">
      <div class="parallel-title">♩ Práticas Paralelas — sempre ativas</div>
      <div class="parallel-list">${parallelHTML}</div>
    </div>` : ''}

    ${S.plan.recommended_order_rationale ? `
    <div class="card mt-16" style="margin-top:20px">
      <div style="font-size:12px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Racional da Sequência</div>
      <p style="font-size:13px;color:var(--text-muted);line-height:1.7">${S.plan.recommended_order_rationale}</p>
    </div>` : ''}
  `;
}

/* ════════════════════════════════════
   CATALOG SECTION
════════════════════════════════════ */
function renderCatalog() {
  const el = document.getElementById('section-catalog');
  el.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Catálogo <span>Completo</span></h1>
      <p class="page-subtitle">Todos os cursos mapeados do Fica a Dica Premium</p>
    </div>
    ${buildFilters()}
    <div class="course-grid" id="course-grid"></div>
  `;
  attachFilterListeners();
  applyFilters();
}

function buildFilters() {
  const cats = [...new Set(S.courses.map(c => c.category).filter(Boolean))].sort();
  const levels = [...new Set(S.courses.map(c => c.level).filter(Boolean))].sort();
  const instructors = [...new Set(S.courses.map(c => c.instructor).filter(Boolean))].sort();

  const opt = (arr, val) => arr.map(v => `<option value="${v}" ${v === val ? 'selected' : ''}>${v}</option>`).join('');

  return `
    <div class="catalog-filters">
      <div class="filter-group">
        <label class="filter-label">Categoria</label>
        <select class="filter-select" id="f-category">
          <option value="">Todas</option>${opt(cats, S.filters.category)}
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">Nível</label>
        <select class="filter-select" id="f-level">
          <option value="">Todos</option>${opt(levels, S.filters.level)}
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">Instrutor</label>
        <select class="filter-select" id="f-instructor">
          <option value="">Todos</option>${opt(instructors, S.filters.instructor)}
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">Buscar</label>
        <input class="filter-input" id="f-search" placeholder="Título do curso..." value="${S.filters.search}">
      </div>
      <button class="filter-clear" onclick="clearFilters()">✕ Limpar</button>
      <span class="catalog-count" id="catalog-count"></span>
    </div>`;
}

function attachFilterListeners() {
  ['category','level','instructor'].forEach(k => {
    const el = document.getElementById(`f-${k}`);
    if (el) el.addEventListener('change', () => { S.filters[k] = el.value; applyFilters(); saveFilters(); });
  });
  const search = document.getElementById('f-search');
  if (search) {
    search.addEventListener('input', () => { S.filters.search = search.value; applyFilters(); saveFilters(); });
  }
}

function clearFilters() {
  S.filters = { category: '', level: '', instructor: '', search: '' };
  renderCatalog();
}

function saveFilters() {
  localStorage.setItem('fad_filters', JSON.stringify(S.filters));
}

function applyFilters() {
  const { category, level, instructor, search } = S.filters;
  const q = search.toLowerCase();
  const filtered = S.courses.filter(c => {
    if (category && c.category !== category) return false;
    if (level && c.level !== level) return false;
    if (instructor && c.instructor !== instructor) return false;
    if (q && !c.title.toLowerCase().includes(q) && !(c.instructor || '').toLowerCase().includes(q)) return false;
    return true;
  });

  const countEl = document.getElementById('catalog-count');
  if (countEl) countEl.textContent = `${filtered.length} curso${filtered.length !== 1 ? 's' : ''}`;

  const grid = document.getElementById('course-grid');
  if (!grid) return;

  if (!filtered.length) {
    grid.innerHTML = `<div class="no-results">Nenhum curso encontrado com esses filtros</div>`;
    return;
  }

  grid.innerHTML = filtered
    .sort((a, b) => (b.priority_for_user || 0) - (a.priority_for_user || 0))
    .map(c => buildCourseCard(c)).join('');
}

function buildCourseCard(c) {
  const dur = fmtMins(c.total_duration_minutes);
  const prio = c.priority_for_user || 3;
  const styles = (c.style_focus || []).slice(0, 2).map(s =>
    `<span style="font-size:10px;color:var(--text-dim)">${s}</span>`
  ).join(' · ');

  return `
    <div class="course-card" onclick="openModal('${c.id}')">
      <div class="priority-bar priority-bar-${prio}"></div>
      <div class="course-card-thumb">
        ${c.thumbnail_url
          ? `<img src="${c.thumbnail_url}" alt="${c.title}" onerror="this.parentElement.innerHTML='<span class=course-card-thumb-icon>♪</span>'">`
          : `<span class="course-card-thumb-icon">♪</span>`}
      </div>
      <div class="course-card-body">
        <div class="course-card-header">
          <div class="course-card-title">${c.title}</div>
          ${stars(prio)}
        </div>
        <div class="course-card-instructor">${c.instructor || '—'}</div>
        <div class="flex gap-8 flex-wrap mt-4">
          <span class="${CAT_BADGE(c.category)}">${c.category || 'outros'}</span>
          ${c.level ? `<span style="font-size:11px;color:var(--text-dim)">${c.level}</span>` : ''}
        </div>
        ${styles ? `<div class="mt-4">${styles}</div>` : ''}
        <div class="course-card-footer">
          <span class="course-stat"><strong>${c.total_lessons}</strong> aulas</span>
          <span class="course-stat"><strong>${dur}</strong></span>
          <span class="course-stat">${(c.modules || []).length} módulos</span>
        </div>
      </div>
    </div>`;
}

/* ════════════════════════════════════
   STATS SECTION
════════════════════════════════════ */
function renderStats() {
  const el = document.getElementById('section-stats');
  const courses = S.courses;

  if (!courses.length) {
    el.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">Esta<span>tísticas</span></h1>
      </div>
      <div class="loading">Nenhum dado disponível — execute o scraper primeiro.</div>`;
    return;
  }

  const totalLessons  = courses.reduce((s, c) => s + (c.total_lessons || 0), 0);
  const totalMins     = courses.reduce((s, c) => s + (c.total_duration_minutes || 0), 0);
  const totalHours    = Math.round(totalMins / 60);
  const instructors   = [...new Set(courses.map(c => c.instructor).filter(Boolean))];

  // By category
  const byCat = {};
  courses.forEach(c => { byCat[c.category || 'outros'] = (byCat[c.category || 'outros'] || 0) + 1; });
  const maxCat = Math.max(...Object.values(byCat));

  // By instructor
  const byInstr = {};
  courses.forEach(c => {
    if (c.instructor) {
      if (!byInstr[c.instructor]) byInstr[c.instructor] = { count: 0, lessons: 0, hours: 0 };
      byInstr[c.instructor].count++;
      byInstr[c.instructor].lessons += c.total_lessons || 0;
      byInstr[c.instructor].hours += Math.round((c.total_duration_minutes || 0) / 60);
    }
  });
  const topInstr = Object.entries(byInstr).sort((a,b) => b[1].count - a[1].count).slice(0,5);

  // Phase hours
  const phases = S.plan.phases || [];
  const maxPhaseHours = Math.max(1, ...phases.map(ph =>
    (ph.courses || []).reduce((s, c) => {
      const fc = courses.find(x => x.id === c.course_id);
      return s + Math.round((fc?.total_duration_minutes || 0) / 60);
    }, 0)
  ));

  el.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Esta<span>tísticas</span></h1>
      <p class="page-subtitle">Visão geral do catálogo mapeado</p>
    </div>

    <div class="stats-summary">
      <div class="stat-card">
        <div class="stat-value">${courses.length}</div>
        <div class="stat-label">Cursos mapeados</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${totalLessons.toLocaleString('pt-BR')}</div>
        <div class="stat-label">Aulas no total</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${totalHours}h</div>
        <div class="stat-label">Horas de conteúdo</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${instructors.length}</div>
        <div class="stat-label">Instrutores</div>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stats-card">
        <div class="stats-card-title">Cursos por Categoria</div>
        <div class="bar-chart">
          ${Object.entries(byCat).sort((a,b) => b[1]-a[1]).map(([cat, count]) => `
            <div class="bar-row">
              <span class="bar-label">${cat}</span>
              <div class="bar-track">
                <div class="bar-fill" style="width:${Math.round(count/maxCat*100)}%"></div>
              </div>
              <span class="bar-value">${count} curso${count>1?'s':''}</span>
            </div>`).join('')}
        </div>
      </div>

      <div class="stats-card">
        <div class="stats-card-title">Top Instrutores</div>
        <div class="instructor-list">
          ${topInstr.map(([name, d]) => `
            <div class="instructor-row">
              <div class="instructor-avatar">${initials(name)}</div>
              <div class="instructor-info">
                <div class="instructor-name">${name}</div>
                <div class="instructor-courses">${d.count} curso${d.count>1?'s':''} · ${d.lessons} aulas</div>
              </div>
              <div class="instructor-hours">${d.hours}h</div>
            </div>`).join('')}
        </div>
      </div>

      ${phases.length ? `
      <div class="stats-card" style="grid-column:1/-1">
        <div class="stats-card-title">Horas do Plano por Fase</div>
        <div class="phase-hours-list">
          ${phases.map(ph => {
            const phHours = (ph.courses || []).reduce((s, c) => {
              const fc = courses.find(x => x.id === c.course_id);
              return s + Math.round((fc?.total_duration_minutes || 0) / 60);
            }, 0);
            const pct = maxPhaseHours > 0 ? Math.max(5, Math.round(phHours / maxPhaseHours * 100)) : 5;
            return `
            <div class="phase-hours-row">
              <div class="phase-hours-header">
                <span>Fase ${ph.phase}: ${ph.title}</span>
                <span>${phHours}h (sem. ${ph.weeks})</span>
              </div>
              <div class="phase-hours-track">
                <div class="phase-hours-fill" style="width:${pct}%"></div>
              </div>
            </div>`;
          }).join('')}
        </div>
      </div>` : ''}
    </div>`;
}

/* ════════════════════════════════════
   SETTINGS SECTION
════════════════════════════════════ */
function renderSettings() {
  const el = document.getElementById('section-settings');
  const p = S.profile;

  const styleOptions = ['jazz','mpb','bossa nova','blues','rock','pop','samba','forró','erudito','funk','soul'];
  const instrOptions = ['guitarra','violão','baixo','piano','bateria','voz'];

  el.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Confi<span>gurações</span></h1>
      <p class="page-subtitle">Ajuste o perfil e regenere o plano de estudos</p>
    </div>

    <div class="settings-grid">
      <!-- Profile Form -->
      <div class="settings-card" style="grid-column:1/-1">
        <div class="settings-title">Perfil do Estudante</div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
          <div class="form-group">
            <label class="form-label">Nome</label>
            <input class="form-input" id="s-name" value="${p.name || ''}">
          </div>
          <div class="form-group">
            <label class="form-label">Nível</label>
            <select class="form-select" id="s-level">
              ${['iniciante','intermediário','intermediário-avançado','avançado'].map(l =>
                `<option value="${l}" ${p.level===l?'selected':''}>${l}</option>`
              ).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Horas disponíveis por semana</label>
            <input class="form-input" id="s-hours" type="number" min="1" max="40" value="${p.available_hours_per_week || 5}">
          </div>
          <div class="form-group">
            <label class="form-label">Duração da sessão (minutos)</label>
            <input class="form-input" id="s-session" type="number" min="15" max="180" value="${p.study_session_minutes || 45}">
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Estilos musicais</label>
          <div class="form-tags" id="s-styles">
            ${styleOptions.map(s => `
              <span class="form-tag ${(p.styles||[]).includes(s)?'selected':''}"
                    onclick="toggleTag(this,'styles','${s}')">${s}</span>`).join('')}
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Instrumentos</label>
          <div class="form-tags" id="s-instruments">
            ${instrOptions.map(i => `
              <span class="form-tag ${(p.instruments||[]).includes(i)?'selected':''}"
                    onclick="toggleTag(this,'instruments','${i}')">${i}</span>`).join('')}
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Objetivos (um por linha)</label>
          <textarea class="form-input" id="s-goals" rows="4" style="resize:vertical">${(p.goals||[]).join('\n')}</textarea>
        </div>

        <div class="btn-group">
          <button class="btn btn-primary" onclick="saveProfile()">💾 Salvar Perfil</button>
        </div>
        <div class="action-result" id="profile-result"></div>
      </div>

      <!-- Actions -->
      <div class="settings-card">
        <div class="settings-title">Plano de Estudos</div>
        <p style="font-size:13px;color:var(--text-muted);margin-bottom:16px;line-height:1.6">
          Regenere o plano com base no catálogo atual e no perfil configurado acima.
        </p>
        <div class="btn-group">
          <button class="btn btn-primary" id="btn-regen" onclick="regeneratePlan()">
            🔄 Regenerar Plano
          </button>
        </div>
        <div class="action-result" id="regen-result"></div>
      </div>

      <div class="settings-card">
        <div class="settings-title">Atualizar Catálogo</div>
        <p style="font-size:13px;color:var(--text-muted);margin-bottom:16px;line-height:1.6">
          Executa o scraper para mapear novos cursos. Processo demorado (~5-15 min).
        </p>
        <div class="btn-group">
          <button class="btn btn-secondary" id="btn-scrape" onclick="startRescrape()">
            🕷️ Atualizar Catálogo
          </button>
        </div>
        <div class="action-result" id="scrape-result"></div>
      </div>
    </div>`;
}

/* Tags toggle */
window.toggleTag = function(el, field, value) {
  el.classList.toggle('selected');
};

/* ════════════════════════════════════
   MODAL
════════════════════════════════════ */
window.openModal = function(courseId) {
  const c = S.courses.find(x => x.id === courseId);
  if (!c) return;

  const backdrop = document.getElementById('modal-backdrop');
  const inner    = document.getElementById('modal-inner');

  const planCourse = (S.plan.phases || []).flatMap(ph => ph.courses || []).find(x => x.course_id === courseId);

  const modulesHTML = (c.modules || []).map((mod, i) => `
    <div class="module-item">
      <div class="module-header" onclick="this.parentElement.classList.toggle('open')">
        <span class="module-name">${mod.title}</span>
        <span class="module-count">${mod.lessons?.length || 0} aulas</span>
      </div>
      <div class="module-lessons">
        ${(mod.lessons || []).map(l => `
          <div class="lesson-row">
            <span class="lesson-title">${l.title}</span>
            <span class="lesson-dur">${fmtMins(l.duration_minutes)}</span>
          </div>`).join('')}
      </div>
    </div>`).join('');

  inner.innerHTML = `
    <div class="modal-header">
      <div>
        <div class="modal-title">${c.title}</div>
        <div class="modal-instructor">${c.instructor ? `por ${c.instructor}` : ''}</div>
      </div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body">
      <div class="modal-badges">
        <span class="${CAT_BADGE(c.category)}">${c.category || 'outros'}</span>
        ${c.level ? `<span class="badge" style="background:var(--surface-3);color:var(--text-muted)">${c.level}</span>` : ''}
        ${stars(c.priority_for_user || 3)}
        ${(c.style_focus || []).map(s => `<span class="badge" style="background:var(--surface-3);color:var(--text-dim)">${s}</span>`).join('')}
      </div>

      ${c.description ? `<p class="modal-desc">${c.description}</p>` : ''}

      <div class="modal-stats">
        <div class="modal-stat">
          <div class="modal-stat-val">${c.total_lessons}</div>
          <div class="modal-stat-lbl">aulas</div>
        </div>
        <div class="modal-stat">
          <div class="modal-stat-val">${fmtMins(c.total_duration_minutes)}</div>
          <div class="modal-stat-lbl">de conteúdo</div>
        </div>
        <div class="modal-stat">
          <div class="modal-stat-val">${(c.modules || []).length}</div>
          <div class="modal-stat-lbl">módulos</div>
        </div>
        <div class="modal-stat">
          <div class="modal-stat-val">${c.priority_for_user}/5</div>
          <div class="modal-stat-lbl">prioridade</div>
        </div>
      </div>

      ${planCourse ? `
      <div class="milestone-box" style="margin-bottom:20px">
        <span class="milestone-icon">🎯</span>
        <span class="milestone-text"><strong>No seu plano:</strong> ${planCourse.why}</span>
      </div>
      <div class="milestone-box" style="margin-bottom:20px;border-color:var(--border)">
        <span class="milestone-icon">💡</span>
        <span class="milestone-text"><strong>Como estudar:</strong> ${planCourse.session_focus}</span>
      </div>` : ''}

      ${modulesHTML ? `
      <div style="font-size:12px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">
        Currículo (clique para expandir)
      </div>
      <div class="module-list">${modulesHTML}</div>` : ''}

      <div class="modal-actions">
        ${c.url ? `<a href="${c.url}" target="_blank" class="btn btn-primary">🔗 Abrir no Site</a>` : ''}
        <button class="btn btn-secondary" onclick="closeModal()">Fechar</button>
      </div>
    </div>`;

  backdrop.classList.remove('hidden');
  requestAnimationFrame(() => backdrop.classList.add('open'));
};

window.closeModal = function() {
  const backdrop = document.getElementById('modal-backdrop');
  backdrop.classList.remove('open');
  setTimeout(() => backdrop.classList.add('hidden'), 200);
};

document.addEventListener('click', e => {
  if (e.target.id === 'modal-backdrop') closeModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

/* ════════════════════════════════════
   SETTINGS ACTIONS
════════════════════════════════════ */
window.saveProfile = async function() {
  const name       = document.getElementById('s-name')?.value || '';
  const level      = document.getElementById('s-level')?.value || '';
  const hours      = parseInt(document.getElementById('s-hours')?.value) || 5;
  const session    = parseInt(document.getElementById('s-session')?.value) || 45;
  const goalsRaw   = document.getElementById('s-goals')?.value || '';
  const goals      = goalsRaw.split('\n').map(l => l.trim()).filter(Boolean);
  const styles     = [...document.querySelectorAll('#s-styles .form-tag.selected')].map(el => el.textContent.trim());
  const instruments = [...document.querySelectorAll('#s-instruments .form-tag.selected')].map(el => el.textContent.trim());

  const newProfile = {
    ...S.profile,
    name, level,
    available_hours_per_week: hours,
    study_session_minutes: session,
    goals, styles, instruments,
  };

  const result = document.getElementById('profile-result');
  result.className = 'action-result info';
  result.textContent = 'Salvando...';

  try {
    const r = await api('POST', '/api/profile', newProfile);
    if (r.ok) {
      S.profile = newProfile;
      result.className = 'action-result success';
      result.textContent = '✓ Perfil salvo com sucesso';
    } else {
      result.className = 'action-result error';
      result.textContent = `Erro: ${r.error || 'falha ao salvar'}`;
    }
  } catch(e) {
    result.className = 'action-result error';
    result.textContent = `Erro: ${e.message}`;
  }
};

window.regeneratePlan = async function() {
  const btn = document.getElementById('btn-regen');
  const result = document.getElementById('regen-result');
  btn.disabled = true;
  btn.textContent = '⏳ Gerando...';
  result.className = 'action-result info';
  result.textContent = 'Executando run_planner.py...';

  try {
    const r = await api('POST', '/api/regenerate');
    if (r.ok && r.plan) {
      S.plan = r.plan;
      result.className = 'action-result success';
      result.textContent = '✓ Plano regenerado com sucesso! Acesse "Meu Plano" para ver.';
    } else {
      result.className = 'action-result error';
      result.textContent = `Erro: ${r.error || 'falha ao regenerar'}`;
    }
  } catch(e) {
    result.className = 'action-result error';
    result.textContent = `Erro: ${e.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = '🔄 Regenerar Plano';
  }
};

window.startRescrape = async function() {
  const btn = document.getElementById('btn-scrape');
  const result = document.getElementById('scrape-result');
  btn.disabled = true;
  result.className = 'action-result info';
  result.textContent = 'Iniciando scraper em background...';

  try {
    const r = await api('POST', '/api/rescrape');
    if (r.job_id) {
      S.scrapeJobId = r.job_id;
      result.textContent = `Job iniciado (${r.job_id}). Verificando status...`;
      pollScrapeJob(r.job_id, btn, result);
    } else {
      result.className = 'action-result error';
      result.textContent = r.error || 'Erro ao iniciar scraper';
      btn.disabled = false;
    }
  } catch(e) {
    result.className = 'action-result error';
    result.textContent = e.message;
    btn.disabled = false;
  }
};

async function pollScrapeJob(jobId, btn, result) {
  const check = async () => {
    try {
      const job = await api('GET', `/api/status/${jobId}`);
      if (job.status === 'done') {
        result.className = 'action-result success';
        result.textContent = '✓ Catálogo atualizado! Recarregue a página para ver os novos dados.';
        btn.disabled = false;
        btn.textContent = '🕷️ Atualizar Catálogo';
        await loadAll();
      } else if (job.status === 'error') {
        result.className = 'action-result error';
        result.textContent = `Erro no scraper: ${job.output?.slice(-200) || ''}`;
        btn.disabled = false;
        btn.textContent = '🕷️ Atualizar Catálogo';
      } else {
        setTimeout(check, 4000);
      }
    } catch(e) {
      setTimeout(check, 4000);
    }
  };
  check();
}

/* ════════════════════════════════════
   INIT
════════════════════════════════════ */
document.getElementById('nav-list').addEventListener('click', e => {
  const item = e.target.closest('.nav-item');
  if (item?.dataset.section) navigateTo(item.dataset.section);
});

async function init() {
  // Restore filters
  try {
    const saved = localStorage.getItem('fad_filters');
    if (saved) S.filters = { ...S.filters, ...JSON.parse(saved) };
  } catch(_) {}

  await loadAll();

  const savedSection = localStorage.getItem('fad_section') || 'plan';
  navigateTo(savedSection);
}

init();
